# from: @coordinator
# to: @backend-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 3

## 任务: Q4 Phase 1 - RedisSnapshotStore 实现

### 背景
InMemorySnapshotStore 已完成并通过测试 (10/10)。
现在需要创建 RedisSnapshotStore 实现。

### 具体任务

1. **创建 RedisSnapshotStore 实现**

   文件: `src/algo_studio/core/interfaces/redis_snapshot_store.py`

   参考: `src/algo_studio/core/deploy/rollback.py` 中的现有实现

   ```python
   class RedisSnapshotStore(SnapshotStoreInterface):
       def __init__(self, redis_url: str = "redis://localhost:6380"):
           self.redis_url = redis_url
           self._redis = None

       async def _get_redis(self):
           if self._redis is None:
               import redis.asyncio as redis
               self._redis = await redis.from_url(self.redis_url)
           return self._redis

       async def save_snapshot(self, task_id: str, snapshot_data: Dict[str, Any]) -> bool:
           # 使用 redis.setex 或类似的异步方法
           pass

       async def get_snapshot(self, task_id: str) -> Optional[Dict[str, Any]]:
           pass

       async def list_snapshots(self, limit: int = 10) -> List[Dict[str, Any]]:
           pass

       async def delete_snapshot(self, task_id: str) -> bool:
           pass
   ```

2. **关键设计考虑**
   - Key 格式: `snapshot:{task_id}`
   - 序列化: JSON
   - 过期时间: 可选 (如 7 天)

3. **运行测试验证**
   ```bash
   PYTHONPATH=src .venv/bin/python -m pytest tests/unit/core/test_snapshot_store.py -v
   ```

### 输出
完成后在 `talks/backend-to-coordinator-round3-2026-03-28.md` 汇报：
- RedisSnapshotStore 实现情况
- 测试结果
