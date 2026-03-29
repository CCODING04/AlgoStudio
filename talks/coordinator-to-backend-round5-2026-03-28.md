# from: @coordinator
# to: @backend-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 5

## 任务: Q4 Phase 2 - RollbackService 重构使用接口注入

### 背景
Phase 1 已完成:
- SnapshotStoreInterface 创建
- InMemorySnapshotStore 实现 (10/10 passed)
- RedisSnapshotStore 实现 (10/10 passed)

现在需要将 RollbackService 重构使用接口注入。

### 具体任务

1. **分析现有 RollbackService**
   查看 `src/algo_studio/core/deploy/rollback.py` 中的 RollbackService 类

2. **重构为使用 SnapshotStoreInterface**
   ```python
   class RollbackService:
       def __init__(self, snapshot_store: SnapshotStoreInterface = None):
           self.snapshot_store = snapshot_store or RedisSnapshotStore()
       # ... 其他方法使用 self.snapshot_store 而非直接调用 Redis
   ```

3. **运行测试验证**
   ```bash
   PYTHONPATH=src .venv/bin/python -m pytest tests/unit/core/test_rollback.py -v
   ```

### 输出
完成后在 `talks/backend-to-coordinator-round5-2026-03-28.md` 汇报：
- 重构内容
- 测试结果
