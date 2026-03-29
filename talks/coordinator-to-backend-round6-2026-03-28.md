# from: @coordinator
# to: @backend-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 6

## 任务: P0 - algorithms router 注册 + RedisSnapshotStore 测试

### 背景
Round 3 评审发现两个 P0 问题:
1. **algorithms router 未注册** - `/api/algorithms/` 端点不可访问
2. **RedisSnapshotStore 无测试** - 10/10 测试只验证了 InMemorySnapshotStore

### 具体任务

**1. 注册 algorithms router (P0)**

   检查 `src/algo_studio/api/main.py`:
   ```python
   # 当前导入
   from algo_studio.api.routes import tasks, hosts, cluster, deploy, audit

   # 需要添加
   from algo_studio.api.routes import tasks, hosts, cluster, deploy, audit, algorithms
   ```

   在 app 对象上注册:
   ```python
   app.include_router(algorithms.router, prefix="/api/algorithms", tags=["algorithms"])
   ```

**2. 为 RedisSnapshotStore 添加测试**

   文件: `tests/unit/core/test_redis_snapshot_store.py`

   测试用例:
   - `test_save_and_get_snapshot` - 保存并获取
   - `test_get_nonexistent_returns_none` - 不存在返回 None
   - `test_delete_snapshot` - 删除
   - `test_list_snapshots` - 列表

   使用 `fakeredis` 或 mock Redis:
   ```python
   @pytest.fixture
   def redis_store():
       return RedisSnapshotStore(redis_url="redis://localhost:6380")
   ```

**3. 验证**

   ```bash
   # 确认 router 注册
   PYTHONPATH=src .venv/bin/python -c "from algo_studio.api.main import app; print([r.path for r in app.routes])"

   # 运行 RedisSnapshotStore 测试
   PYTHONPATH=src .venv/bin/python -m pytest tests/unit/core/test_redis_snapshot_store.py -v
   ```

### 输出
完成后在 `talks/backend-to-coordinator-round6-2026-03-28.md` 汇报：
- router 注册结果
- RedisSnapshotStore 测试结果
