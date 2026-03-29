# from: @test-engineer
# to: @coordinator
# date: 2026-03-28
# type: status
# round: Phase 3.1 Round 8

## 任务完成状态: P0 - API 签名不匹配 + 测试隔离问题

### 背景
Round 7 测试结果: 36 failed, 587 passed

### 1. API 签名修复 (test_snapshot_store.py)

**问题**: 8 tests 使用旧 API `save_snapshot(task_id, data)` 但实际接口已改为 `save_snapshot(snapshot: DeploymentSnapshot)`

**修复内容**:
- 重写 `tests/unit/core/test_snapshot_store.py` 全部 10 个测试用例
- 使用新的 `DeploymentSnapshot` 对象 API
- 添加 `create_test_snapshot()` 辅助函数

**根本原因修复**: 发现 `InMemorySnapshotStore` 没有对返回数据进行深拷贝，导致测试 `test_snapshot_data_independence` 失败
- 修改 `src/algo_studio/core/interfaces/snapshot_store.py`
- `get_snapshot()` 和 `list_snapshots()` 现在返回深拷贝，确保数据独立性

### 2. 测试隔离修复

**问题**: 27 tests 在全量运行时失败，单独运行通过 - fixture 污染或 middleware 状态残留

**修复内容**:
- 在 `tests/unit/api/test_tasks_api.py` 添加 autouse fixture `cleanup_app_state`
- 在 `tests/unit/api/test_rbac.py` 添加 autouse fixture `cleanup_rbac_state`
- 将 `RBAC_SECRET_KEY` 环境变量设置移至 `tests/conftest.py` 顶部（在所有 import 之前）

### 3. 验证结果

```bash
# snapshot store tests - 全部通过
tests/unit/core/test_snapshot_store.py: 10 passed

# 全量 unit tests - 全部通过
tests/unit/ -v: 623 passed, 1 warning
```

### 修改文件清单

| 文件 | 变更类型 |
|------|----------|
| `tests/unit/core/test_snapshot_store.py` | 重写 - 使用新 API |
| `src/algo_studio/core/interfaces/snapshot_store.py` | 修复 - 深拷贝返回 |
| `tests/unit/api/test_tasks_api.py` | 修复 - 添加 cleanup fixture |
| `tests/unit/api/test_rbac.py` | 修复 - 添加 cleanup fixture |
| `tests/conftest.py` | 修复 - env var 初始化顺序 |

### Round 7 vs Round 8 对比

| 指标 | Round 7 | Round 8 |
|------|---------|---------|
| Failed | 36 | 0 |
| Passed | 587 | 623 |
| 通过率 | 94.2% | 100% |
