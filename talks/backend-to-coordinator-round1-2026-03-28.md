# from: @backend-engineer
# to: @coordinator
# date: 2026-03-28
# type: update
# round: Phase 3.1 Round 1

## Phase 3.1 Round 1 汇报: 存储抽象层接口设计

### 1. 现有 DeploymentSnapshotStore 分析

**位置**: `src/algo_studio/core/deploy/rollback.py`

**核心特征**:
- **存储后端**: Redis (端口 6380)
- **数据模型**: `DeploymentSnapshot` dataclass (包含 snapshot_id, deployment_id, node_ip, version, config, steps_completed, created_at, ray_head_ip, ray_port, artifacts, metadata)
- **Redis Key 结构**:
  - `deploy:snapshot:{deployment_id}` - 当前快照
  - `deploy:snapshot:id:{snapshot_id}` - 按 snapshot_id 索引
  - `deploy:snapshots:node:{node_ip}` - 节点快照列表 (保留最近 10 个)
  - `deploy:rollback_history:{deployment_id}` - 回滚历史
- **异步模式**: `async def` + `await`，使用 `redis.asyncio`
- **懒连接**: `_get_redis()` 方法延迟初始化 Redis 连接
- **序列化**: JSON (`json.dumps`/`json.loads`)

**主要方法**:
| 方法 | 签名 |
|------|------|
| create_snapshot | async def create_snapshot(deployment_id, node_ip, version, config, steps_completed, ray_head_ip, ray_port, artifacts, metadata) -> DeploymentSnapshot |
| get_snapshot | async def get_snapshot(deployment_id) -> Optional[DeploymentSnapshot] |
| get_snapshots_by_node | async def get_snapshots_by_node(node_ip) -> List[DeploymentSnapshot] |
| save_rollback_history | async def save_rollback_history(entry: RollbackHistoryEntry) -> None |
| get_rollback_history | async def get_rollback_history(deployment_id) -> List[RollbackHistoryEntry] |

### 2. QuotaStoreInterface 参考

**位置**: `src/algo_studio/core/quota/store.py`

**核心特征**:
- **接口模式**: ABC + `@abstractmethod`
- **返回类型**: `Dict[str, Any]` (非 dataclass)
- **实现**: `SQLiteQuotaStore`, `RedisQuotaStore`

### 3. SnapshotStoreInterface 设计草案

**位置**: `src/algo_studio/core/interfaces/snapshot_store.py`

**接口定义** (Phase 1 最小集):
```python
class SnapshotStoreInterface(ABC):
    @abstractmethod
    async def save_snapshot(self, task_id: str, snapshot_data: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    async def get_snapshot(self, task_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def list_snapshots(self, limit: int = 10) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def delete_snapshot(self, task_id: str) -> bool:
        pass
```

**InMemorySnapshotStore 实现** (Phase 1 测试用):
- 内存字典存储，非持久化
- 用于接口验证和单元测试
- 保留 insertion_order 实现类 FIFO 行为

### 4. 设计决策说明

| 决策 | 选择 | 原因 |
|------|------|------|
| async/await | Yes | 与 DeploymentSnapshotStore 保持一致 |
| 返回 Dict | Yes | 与 QuotaStoreInterface 保持一致，便于 JSON 序列化 |
| task_id 作为主键 | Yes | 任务文件要求，DeploymentSnapshotStore 用 deployment_id |
| 最小方法集 | 4 个 | Phase 1 需求，后续可扩展 |

### 5. 下一步 (Phase 1 Round 2)

- [ ] 创建 RedisSnapshotStore 实现
- [ ] 创建 SQLiteSnapshotStore 实现 (WAL mode)
- [ ] 添加单元测试
- [ ] 更新 schedule.md
