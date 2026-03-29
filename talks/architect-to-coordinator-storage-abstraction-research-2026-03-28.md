# Storage Abstraction Layer Research Report

**From:** @architect-alpha
**To:** @coordinator
**Date:** 2026-03-28
**Subject:** P3-2: DeploymentSnapshotStore Storage Abstraction Layer重构

---

## 1. 问题分析

### 当前问题

`DeploymentSnapshotStore` (在 `src/algo_studio/core/deploy/rollback.py`) 存在以下紧耦合问题：

```python
# 直接导入 Redis
import redis.asyncio as redis

# 在 __init__ 中硬编码 Redis 连接
def __init__(self, redis_host: str = "localhost", redis_port: int = 6380):
    self._redis: Optional[redis.Redis] = None
    self._redis_host = redis_host
    self._redis_port = redis_port

# Redis 特定操作分散在各处
async def _get_redis(self) -> redis.Redis:
    if self._redis is None:
        self._redis = redis.Redis(
            host=self._redis_host,
            port=self._redis_port,
            decode_responses=True,
        )
    return self._redis

# Redis key 前缀硬编码
REDIS_SNAPSHOT_PREFIX = "deploy:snapshot:"
REDIS_NODE_SNAPSHOTS_PREFIX = "deploy:snapshots:node:"
```

### 影响

1. **测试困难**: 必须 mock `redis.asyncio` 的所有操作
2. **无法切换存储**: 生产用 Redis，测试只能用 mock
3. **违反开闭原则**: 更换存储后端需修改核心逻辑
4. **代码重复**: 与 `QuotaStoreInterface` 模式不一致

---

## 2. 参考现有模式

### QuotaStore 的正确示范

```python
# Abstract Interface
class QuotaStoreInterface(ABC):
    @abstractmethod
    def get_quota(self, quota_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def create_quota(self, quota_data: Dict[str, Any]) -> bool:
        pass

    # ... 其他抽象方法

# SQLite 实现
class SQLiteQuotaStore(QuotaStoreInterface):
    def __init__(self, db_path: str = None):
        # SQLite 特定逻辑

# Redis 实现
class RedisQuotaStore(QuotaStoreInterface):
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6380):
        # Redis 特定逻辑
```

**优点**: 遵循接口隔离，依赖注入，Mock 测试友好

---

## 3. 推荐方案

### 方案: Repository Pattern + Abstract Base Class

**核心思想**: 将数据访问抽象为接口，具体实现分离，通过依赖注入使用

#### 3.1 定义抽象接口

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class DeploymentSnapshot:
    """快照数据结构 - 保持不变"""
    snapshot_id: str
    deployment_id: str
    node_ip: str
    version: str
    config: Dict[str, Any]
    steps_completed: List[str]
    created_at: datetime
    ray_head_ip: str
    ray_port: int
    artifacts: List[str]
    metadata: Dict[str, Any]

@dataclass
class RollbackHistoryEntry:
    """回滚历史记录"""
    rollback_id: str
    deployment_id: str
    snapshot_id: str
    status: str
    initiated_by: str
    initiated_at: datetime
    completed_at: Optional[datetime]
    verification_result: Optional[Dict[str, Any]]
    error: Optional[str]


class SnapshotStoreInterface(ABC):
    """快照存储抽象接口"""

    @abstractmethod
    async def create_snapshot(
        self,
        deployment_id: str,
        node_ip: str,
        version: str,
        config: Dict[str, Any],
        steps_completed: List[str],
        ray_head_ip: str,
        ray_port: int = 6379,
        artifacts: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DeploymentSnapshot:
        """创建部署快照"""
        pass

    @abstractmethod
    async def get_snapshot(self, deployment_id: str) -> Optional[DeploymentSnapshot]:
        """获取部署的最新快照"""
        pass

    @abstractmethod
    async def get_snapshots_by_node(self, node_ip: str) -> List[DeploymentSnapshot]:
        """获取节点的所有快照"""
        pass

    @abstractmethod
    async def save_rollback_history(self, entry: RollbackHistoryEntry) -> None:
        """保存回滚历史"""
        pass

    @abstractmethod
    async def get_rollback_history(self, deployment_id: str) -> List[RollbackHistoryEntry]:
        """获取回滚历史"""
        pass
```

#### 3.2 Redis 实现

```python
class RedisSnapshotStore(SnapshotStoreInterface):
    """Redis 快照存储实现"""

    REDIS_SNAPSHOT_PREFIX = "deploy:snapshot:"
    REDIS_SNAPSHOT_ID_PREFIX = "deploy:snapshot:id:"
    REDIS_NODE_SNAPSHOTS_PREFIX = "deploy:snapshots:node:"
    REDIS_ROLLBACK_HISTORY_PREFIX = "deploy:rollback_history:"

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6380):
        self._redis: Optional[redis.Redis] = None
        self._redis_host = redis_host
        self._redis_port = redis_port

    async def _get_redis(self) -> redis.Redis:
        """获取 Redis 连接 (懒加载)"""
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = redis.Redis(
                host=self._redis_host,
                port=self._redis_port,
                decode_responses=True,
            )
        return self._redis

    async def create_snapshot(self, ...) -> DeploymentSnapshot:
        # Redis 特定实现
        ...
```

#### 3.3 内存实现 (用于测试)

```python
class InMemorySnapshotStore(SnapshotStoreInterface):
    """内存快照存储 - 用于测试和开发"""

    def __init__(self):
        self._snapshots: Dict[str, DeploymentSnapshot] = {}
        self._snapshots_by_node: Dict[str, List[str]] = {}
        self._rollback_history: Dict[str, List[RollbackHistoryEntry]] = {}

    async def create_snapshot(self, ...) -> DeploymentSnapshot:
        # 纯内存实现，无外部依赖
        ...
```

#### 3.4 使用依赖注入

```python
class RollbackService:
    """回滚服务 - 通过依赖注入获取存储"""

    def __init__(self, snapshot_store: SnapshotStoreInterface):
        self.snapshot_store = snapshot_store

    async def rollback(self, deployment_id: str, task_id: str, ...) -> RollbackHistoryEntry:
        snapshot = await self.snapshot_store.get_snapshot(deployment_id)
        # ...
```

---

## 4. 关键设计模式

### 4.1 Interface Segregation Principle (接口隔离原则)

```python
# 错误: 一个大接口
class BadStoreInterface:
    async def create_snapshot(self, ...): pass
    async def get_snapshot(self, ...): pass
    async def delete_snapshot(self, ...): pass  # 不需要的方法

# 正确: 按需分割接口
class SnapshotStoreInterface(ABC):
    """快照存储核心接口"""
    ...

class SnapshotQueryInterface(ABC):
    """快照查询接口"""
    async def get_snapshots_by_node(self, node_ip: str): pass
```

### 4.2 Dependency Injection (依赖注入)

```python
# 构造函数注入
class MyService:
    def __init__(self, store: SnapshotStoreInterface):
        self.store = store

# 或者工厂函数
def create_rollback_service(use_redis: bool = True) -> RollbackService:
    if use_redis:
        store = RedisSnapshotStore()
    else:
        store = InMemorySnapshotStore()
    return RollbackService(store)
```

### 4.3 Mock 测试策略

```python
# 使用内存实现进行测试
@pytest.fixture
def snapshot_store():
    return InMemorySnapshotStore()

@pytest.fixture
def rollback_service(snapshot_store):
    return RollbackService(snapshot_store)

async def test_rollback_flow(rollback_service, snapshot_store):
    # 创建快照
    snapshot = await snapshot_store.create_snapshot(...)

    # 执行回滚
    result = await rollback_service.rollback(...)

    assert result.status == RollbackStatus.COMPLETED
```

---

## 5. 迁移策略

### Phase 1: 创建接口 (不修改现有代码)
1. 定义 `SnapshotStoreInterface` 抽象类
2. 创建 `RedisSnapshotStore` 实现 (从现有代码迁移)
3. 创建 `InMemorySnapshotStore` 实现 (用于测试)

### Phase 2: 修改依赖注入点
1. 修改 `RollbackService.__init__` 接受 `SnapshotStoreInterface`
2. 更新 `DeploySnapshotMixin` 使用注入的 store

### Phase 3: 清理
1. 删除旧的 `DeploymentSnapshotStore` 类
2. 更新所有调用点

---

## 6. 参考资料

### 设计模式
1. **Repository Pattern** - Martin Fowler
   - https://martinfowler.com/eaaCatalog/repository.html
   - 核心思想: 集合对数据访问的抽象

2. **Interface Segregation Principle** - Robert C. Martin
   - https://web.archive.org/web/20151124014140/http://www.objectmentor.com/resources/articles/isp.pdf
   - 客户端不应依赖不使用的接口

3. **Dependency Injection** - Microsoft .NET
   - https://docs.microsoft.com/en-us/dotnet/core/extensions/dependency-injection
   - 依赖通过构造函数/方法注入，而非内部创建

### Python 异步存储最佳实践
4. **AsyncIO Storage Patterns**
   - https://docs.python.org/3/library/abc.html
   - 使用 `abc.ABC` 和 `@abstractmethod` 定义异步接口

5. **Testing Async Code**
   - https://docs.pytest.org/en/7.0.x/asyncio.html
   - pytest-asyncio 支持异步测试 fixtures

### 项目内参考
6. `src/algo_studio/core/quota/store.py` - QuotaStoreInterface 模式
7. `tests/unit/core/test_rollback.py` - 现有 MockSnapshotStore 用法

---

## 7. 推荐结论

**推荐采用: Repository Pattern + Abstract Base Class**

### 理由

| 因素 | 评分 | 说明 |
|------|------|------|
| 接口隔离 | 5/5 | 与现有 QuotaStore 模式一致 |
| 测试友好 | 5/5 | 可用 InMemory 实现替代 mock |
| 迁移成本 | 3/5 | 需重构但风险可控 |
| 可扩展性 | 5/5 | 易于添加新存储后端 |
| 团队熟悉度 | 5/5 | 已在 quota store 验证 |

### 实施优先级

1. **P0**: 创建 `SnapshotStoreInterface` + `InMemorySnapshotStore`
2. **P1**: 迁移 `RedisSnapshotStore` 实现
3. **P2**: 更新 `RollbackService` 依赖注入
4. **P3**: 清理旧代码

### 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 迁移过程业务中断 | 保持接口兼容，逐步替换 |
| 异步接口复杂性 | 参考 quota store 的同步版本 |
| 测试覆盖遗漏 | 使用 InMemoryStore 进行集成测试 |

---

## 8. 后续行动

1. **@coordinator**: 确认此方案是否可以进入 Phase 2.3 Round 4
2. **@backend-engineer**: 准备 Phase 1 的具体实现任务
3. **@qa-engineer**: 准备测试用例设计

---

*Architect Alpha - 2026-03-28*
