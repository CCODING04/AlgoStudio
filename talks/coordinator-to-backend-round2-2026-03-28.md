# from: @coordinator
# to: @backend-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 2

## 任务: Q4 Phase 1 - InMemorySnapshotStore 单元测试

### 背景
SnapshotStoreInterface 和 InMemorySnapshotStore 已创建 (Round 1)。
现在需要为 InMemorySnapshotStore 添加单元测试。

### 具体任务

1. **创建 InMemorySnapshotStore 单元测试**

   文件: `tests/unit/core/test_snapshot_store.py`

   测试用例:
   ```python
   import pytest
   from algo_studio.core.interfaces.snapshot_store import (
       SnapshotStoreInterface,
       InMemorySnapshotStore
   )

   @pytest.fixture
   def store():
       return InMemorySnapshotStore()

   @pytest.mark.asyncio
   async def test_save_and_get_snapshot(store):
       snapshot_data = {"version": "1.0", "config": {"key": "value"}}
       result = await store.save_snapshot("task-1", snapshot_data)
       assert result is True

       retrieved = await store.get_snapshot("task-1")
       assert retrieved == snapshot_data

   @pytest.mark.asyncio
   async def test_get_nonexistent(store):
       result = await store.get_snapshot("nonexistent")
       assert result is None

   @pytest.mark.asyncio
   async def test_list_snapshots(store):
       await store.save_snapshot("task-1", {"data": "1"})
       await store.save_snapshot("task-2", {"data": "2"})
       await store.save_snapshot("task-3", {"data": "3"})

       snapshots = await store.list_snapshots(limit=2)
       assert len(snapshots) == 2

   @pytest.mark.asyncio
   async def test_delete_snapshot(store):
       await store.save_snapshot("task-1", {"data": "1"})
       result = await store.delete_snapshot("task-1")
       assert result is True

       retrieved = await store.get_snapshot("task-1")
       assert retrieved is None
   ```

2. **验证测试通过**
   ```bash
   PYTHONPATH=src .venv/bin/python -m pytest tests/unit/core/test_snapshot_store.py -v
   ```

3. **创建 task_factory.py (如时间允许)**
   文件: `tests/factories/task_factory.py`

### 输出
完成后在 `talks/backend-to-coordinator-round2-2026-03-28.md` 汇报：
- InMemorySnapshotStore 测试结果
- 测试用例数量
