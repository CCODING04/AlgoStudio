# from: @coordinator
# to: @backend-engineer
# date: 2026-03-29
# type: task
# round: Phase 3.2 Round 2

## 任务: DeploymentSnapshotStore 错误处理修复

### 背景
评审发现 DeploymentSnapshotStore 有以下问题：
1. 4个方法缺少 try/except 错误处理（get_snapshot, get_snapshots_by_node, save_rollback_history, get_rollback_history）
2. create_snapshot() 忽略 save_snapshot() 的返回值

### 具体任务

**1. 分析现有代码**

查看 `src/algo_studio/core/deploy/rollback.py` 中 DeploymentSnapshotStore 的错误处理模式。

**2. 添加错误处理**

参考 RedisSnapshotStore 的错误处理，为以下方法添加 try/except：
- `get_snapshot()`
- `get_snapshots_by_node()`
- `save_rollback_history()`
- `get_rollback_history()`

**3. 修复 create_snapshot() 返回值检查**

```python
async def create_snapshot(self, deployment_id: str, ...) -> DeploymentSnapshot:
    snapshot = DeploymentSnapshot(...)
    success = await self.save_snapshot(snapshot)
    if not success:
        # 应该处理失败情况
        raise RuntimeError(f"Failed to save snapshot for {deployment_id}")
    return snapshot
```

**4. 验证**

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/core/test_deployment_snapshot_store.py -v
```

### 输出
完成后在 `talks/backend-to-coordinator-round2-2026-03-29.md` 汇报：
- 错误处理修复情况
- 测试结果
