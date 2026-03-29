# 配额体系设计文档

**任务:** Phase 2 Round 1 - 配额数据模型设计
**负责人:** @ai-scheduling-engineer
**日期:** 2026-03-26
**版本:** v1.0

---

## 1. 配额体系概述

### 1.1 设计目标

- 实现 3 级配额体系：GLOBAL → TEAM → USER
- 支持配额继承和覆盖机制
- 定义完整的配额类型体系

### 1.2 配额作用域

```python
class QuotaScope(Enum):
    """配额作用域"""
    GLOBAL = "global"       # 全局配额 (所有用户共享)
    TEAM = "team"           # 团队配额 (团队内用户共享)
    USER = "user"           # 用户配额 (单个用户独占)
```

### 1.3 配额类型定义

```python
@dataclass
class ResourceQuota:
    """资源配额项"""
    cpu_cores: int = 0           # CPU 核心数上限 (0=无限制)
    gpu_count: int = 0           # GPU 数量上限 (0=无限制)
    gpu_memory_gb: float = 0.0   # GPU 显存上限 GB (0=无限制)
    memory_gb: float = 0.0       # 内存上限 GB (0=无限制)
    disk_gb: float = 0.0         # 磁盘上限 GB (0=无限制)
    concurrent_tasks: int = 0    # 并发任务数上限 (0=无限制)

    def is_unlimited(self) -> bool:
        """检查是否所有维度都无限制"""
        return (self.cpu_cores == 0 and
                self.gpu_count == 0 and
                self.gpu_memory_gb == 0.0 and
                self.memory_gb == 0.0 and
                self.disk_gb == 0.0 and
                self.concurrent_tasks == 0)
```

---

## 2. 配额实体设计

### 2.1 Quota 核心数据结构

```python
@dataclass
class Quota:
    """配额实体"""
    quota_id: str
    scope: QuotaScope
    scope_id: str               # user_id 或 team_id
    name: str                   # 配额名称

    # 配额限制
    limits: ResourceQuota

    # 配额预警阈值 (百分比, 0-100)
    alert_threshold: int = 80   # 80% 时告警

    # 配额继承
    parent_quota_id: Optional[str] = None  # 父配额 ID

    # 状态
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
```

### 2.2 配额使用量

```python
@dataclass
class QuotaUsage:
    """资源使用量"""
    cpu_cores_used: float = 0.0
    gpu_count_used: int = 0
    gpu_memory_gb_used: float = 0.0
    memory_gb_used: float = 0.0
    disk_gb_used: float = 0.0
    concurrent_tasks_used: int = 0

    def to_dict(self) -> dict:
        return {
            "cpu_cores_used": self.cpu_cores_used,
            "gpu_count_used": self.gpu_count_used,
            "gpu_memory_gb_used": self.gpu_memory_gb_used,
            "memory_gb_used": self.memory_gb_used,
            "disk_gb_used": self.disk_gb_used,
            "concurrent_tasks_used": self.concurrent_tasks_used,
        }
```

---

## 3. 层级配额继承

### 3.1 继承关系图

```
全局配额 (GLOBAL: global)
    │
    ├── 团队 A 配额 (TEAM: team_a)
    │       │
    │       ├── 用户 A1 配额 (USER: user_a1)  → 继承团队 A
    │       └── 用户 A2 配额 (USER: user_a2)  → 继承团队 A
    │
    ├── 团队 B 配额 (TEAM: team_b)
    │       │
    │       └── 用户 B1 配额 (USER: user_b1)  → 继承团队 B
    │
    └── 团队 C 无独立配额 → 直接继承全局
            │
            └── 用户 C1 配额 (USER: user_c1)  → 继承全局
```

### 3.2 继承规则

| 规则 | 说明 |
|------|------|
| **有效性检查** | 子配额各项限制不能超过父配额对应项 |
| **宽松方向** | 子配额可设置更严格的限制（小于父配额），不能放宽 |
| **继承传递** | 用户继承团队，团队继承全局，不可跨级继承 |
| **默认继承** | 无显式父配额时，默认继承上一层级 |

### 3.3 继承优先级

```
优先级: USER > TEAM > GLOBAL

当用户配额不足时，依次检查:
1. 用户配额 (USER) - 最优先
2. 团队配额 (TEAM) - 次优先
3. 全局配额 (GLOBAL) - 最后兜底
4. 无配额限制 - 完全不限制
```

### 3.4 配额检查算法

```python
def can_allocate(self, usage: QuotaUsage, requested: ResourceQuota) -> tuple[bool, List[str]]:
    """
    检查是否可以分配指定资源

    Returns:
        (can_allocate, reasons)
    """
    reasons = []

    if requested.cpu_cores > 0:
        available = self.limits.cpu_cores - usage.cpu_cores_used
        if available < requested.cpu_cores:
            reasons.append(f"CPU: 请求 {requested.cpu_cores}, 可用 {available}")

    if requested.gpu_count > 0:
        available = self.limits.gpu_count - usage.gpu_count_used
        if available < requested.gpu_count:
            reasons.append(f"GPU: 请求 {requested.gpu_count}, 可用 {available}")

    if requested.gpu_memory_gb > 0:
        available = self.limits.gpu_memory_gb - usage.gpu_memory_gb_used
        if available < requested.gpu_memory_gb:
            reasons.append(f"GPU 显存: 请求 {requested.gpu_memory_gb:.1f}GB, 可用 {available:.1f}GB")

    if requested.memory_gb > 0:
        available = self.limits.memory_gb - usage.memory_gb_used
        if available < requested.memory_gb:
            reasons.append(f"内存: 请求 {requested.memory_gb:.1f}GB, 可用 {available:.1f}GB")

    if requested.concurrent_tasks > 0:
        available = self.limits.concurrent_tasks - usage.concurrent_tasks_used
        if available < requested.concurrent_tasks:
            reasons.append(f"并发任务: 请求 {requested.concurrent_tasks}, 可用 {available}")

    return (len(reasons) == 0, reasons)
```

---

## 4. 任务与配额关联

### 4.1 Task 扩展字段

```python
@dataclass
class Task:
    # ... 现有字段 ...
    user_id: Optional[str] = None      # 用户 ID
    team_id: Optional[str] = None      # 团队 ID
    quota_id: Optional[str] = None     # 使用的配额 ID
    allocated_resources: Optional[ResourceQuota] = None  # 已分配资源
```

### 4.2 任务创建时指定用户

```python
@staticmethod
def create(task_type: TaskType, algorithm_name: str, algorithm_version: str,
           config: Dict, user_id: Optional[str] = None, team_id: Optional[str] = None) -> "Task":
    """创建新任务"""
    task_id = f"{task_type.value}-{uuid.uuid4().hex[:8]}"
    return Task(
        task_id=task_id,
        task_type=task_type,
        algorithm_name=algorithm_name,
        algorithm_version=algorithm_version,
        config=config,
        user_id=user_id,
        team_id=team_id,
    )
```

---

## 5. 默认配额设置

### 5.1 全局默认配额

```yaml
global_default:
  cpu_cores: 128
  gpu_count: 16
  gpu_memory_gb: 384.0  # 16 x RTX 4090 24GB
  memory_gb: 512.0
  disk_gb: 10000.0  # 10TB
  concurrent_tasks: 100
  alert_threshold: 80
```

### 5.2 团队默认配额

```yaml
team_default:
  cpu_cores: 64
  gpu_count: 8
  gpu_memory_gb: 192.0
  memory_gb: 256.0
  disk_gb: 5000.0
  concurrent_tasks: 50
  alert_threshold: 80
```

### 5.3 用户默认配额

```yaml
user_default:
  cpu_cores: 16
  gpu_count: 2
  gpu_memory_gb: 48.0
  memory_gb: 64.0
  disk_gb: 1000.0
  concurrent_tasks: 5
  alert_threshold: 80
```

---

## 6. 配额超载处理策略

### 6.1 策略类型

| 策略 | 行为 | 适用场景 |
|------|------|----------|
| **REJECT** | 直接拒绝任务 | 硬性配额限制 (默认) |
| **QUEUE** | 任务进入等待队列 | 暂时性资源紧张 |
| **FALLBACK** | 降级使用公共资源池 | 有公共资源池时 |

### 6.2 排队超时机制

- **排队超时阈值**: 默认 30 分钟
- **超时告警**: 任务排队超过阈值时触发 WARNING
- **饿死检测**: 连续等待超过 2 小时的任务标记为 CRITICAL

### 6.3 异常定义

```python
class QuotaExceededAction(Enum):
    REJECT = "reject"
    QUEUE = "queue"
    FALLBACK = "fallback"

@dataclass
class QuotaExceededError(Exception):
    quota_id: str
    requested: ResourceQuota
    available: ResourceQuota
    action: QuotaExceededAction
    reasons: List[str]
    queue_position: Optional[int] = None
    estimated_wait_minutes: Optional[int] = None
```

---

## 7. 实施计划

### 7.1 Week 1 任务

| 任务 | 交付物 |
|------|--------|
| 创建 quota/ 目录结构 | 目录创建 |
| 实现 Quota, ResourceQuota, QuotaUsage 数据类 | quota/models.py |
| 实现 QuotaStoreInterface | quota/stores/base.py |
| 实现 SQLite 配额存储 | quota/stores/sqlite_store.py |

### 7.2 代码目录结构

```
src/algo_studio/core/quota/
├── __init__.py
├── models.py           # Quota, ResourceQuota, QuotaUsage
├── quota_manager.py    # 配额管理核心逻辑
├── quota_validator.py  # 调度验证器
├── alert_manager.py    # 告警管理
└── stores/
    ├── __init__.py
    ├── base.py         # QuotaStoreInterface
    └── sqlite_store.py  # SQLite 实现
```

---

## 8. 验收标准

- [ ] Quota 数据类正确实现，包含层级继承支持
- [ ] ResourceQuota 包含所有 6 种资源类型
- [ ] QuotaUsage 正确跟踪使用量
- [ ] 配额继承优先级: USER > TEAM > GLOBAL
- [ ] 子配额不能超过父配额限制
- [ ] 默认配额设置符合规格

---

**文档状态:** 设计完成
**下一步:** 实现 QuotaManager 架构
