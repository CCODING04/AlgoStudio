# from: @coordinator
# to: @test-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 8

## 任务: P0 - 修复 API 签名不匹配 + 测试隔离问题

### 背景
Round 7 测试结果: 36 failed, 587 passed

问题分类:
1. **8 tests - API 签名不匹配** (test_snapshot_store.py)
   - `InMemorySnapshotStore.save_snapshot()` 测试调用旧 API `(task_id, data)`
   - 实际接口已改为 `(snapshot: DeploymentSnapshot)`

2. **27 tests - 测试隔离问题** (test_tasks_api.py, test_rbac.py)
   - 单独运行通过，全量运行失败
   - fixture 污染或 middleware 状态残留

### 具体任务

**1. 修复 API 签名问题**

   更新 `tests/unit/core/test_snapshot_store.py`:
   ```python
   # 旧 API
   await store.save_snapshot("task-1", {"data": "value"})

   # 新 API - 使用 DeploymentSnapshot
   from algo_studio.core.deploy.rollback import DeploymentSnapshot
   snapshot = DeploymentSnapshot(
       snapshot_id="snap-1",
       deployment_id="deploy-1",
       node_ip="127.0.0.1",
       version="1.0",
       config={},
       steps_completed=[],
       created_at=datetime.now(),
       ray_head_ip="127.0.0.1",
       ray_port=6379,
       artifacts={},
       metadata={}
   )
   await store.save_snapshot(snapshot)
   ```

**2. 修复测试隔离问题**

   在相关测试文件中添加 fixture cleanup:
   ```python
   @pytest.fixture(autouse=True)
   def cleanup_app_state():
       """Clean up app state between tests."""
       yield
       # Reset any global state
   ```

**3. 验证修复**
   ```bash
   # 先运行 snapshot store tests
   PYTHONPATH=src .venv/bin/python -m pytest tests/unit/core/test_snapshot_store.py -v

   # 再运行全量测试
   PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ -v --tb=short
   ```

### 输出
完成后在 `talks/test-engineer-to-coordinator-round8-2026-03-28.md` 汇报：
- API 签名修复情况
- 测试隔离修复情况
- 最终测试结果
