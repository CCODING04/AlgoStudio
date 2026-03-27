# 任务分配：修复 Tasks API 测试缺口 (Round 5 反馈)

**from:** @coordinator
**to:** @test-engineer
**date:** 2026-03-27
**type:** task
**priority:** P0

---

## 任务背景

Round 5 评审发现以下 Critical 测试缺口需要修复：

| ID | 问题 | 严重性 |
|----|------|--------|
| C1 | 没有测试 RBAC 认证缺失时 Tasks API 的拒绝行为 | Critical |
| C2 | DELETE /api/tasks/{id} 端点没有测试覆盖 | Critical |
| I1 | test_missing_secret_key_rejects_all_requests 是空实现 | Important |

## 任务内容

### 1. 添加 RBAC 认证测试 (C1)
在 `tests/unit/api/test_tasks_api.py` 中添加：
- `test_tasks_api_rejects_request_without_auth_header`
- `test_tasks_api_rejects_request_with_invalid_signature`
- `test_tasks_api_rejects_expired_timestamp`

### 2. 添加 DELETE 端点测试 (C2)
- `test_delete_task_success`
- `test_delete_task_not_found`
- `test_delete_task_already_completed`
- `test_delete_task_requires_task_delete_permission`

### 3. 修复空测试 (I1)
实现 `test_missing_secret_key_rejects_all_requests` 或删除它

## 输入

- Round 5 评审报告: `docs/superpowers/schedule/round5-review.md`
- RBAC 中间件: `src/algo_studio/api/middleware/rbac.py`
- Tasks API: `src/algo_studio/api/routes/tasks.py`
- 现有测试: `tests/unit/api/test_tasks_api.py`

## 输出

- 更新的 `tests/unit/api/test_tasks_api.py` (24+ tests)
- 修复的 DELETE 端点 (如需要)
- 测试运行结果

## 截止日期

尽快完成

## 状态

- [ ] 任务已接收
- [ ] C1 RBAC 认证测试完成
- [ ] C2 DELETE 端点测试完成
- [ ] I1 空测试修复
- [ ] 所有测试通过

---

## 执行指南

1. 读取现有测试文件了解当前结构
2. 读取 `src/algo_studio/api/routes/tasks.py` 了解 DELETE 端点
3. 如需实现 DELETE 端点，先在 `src/algo_studio/core/task.py` 添加 `delete_task` 方法
4. 添加测试用例
5. 运行 `PYTHONPATH=src pytest tests/unit/api/test_tasks_api.py -v`
6. 确保所有测试通过后 commit
7. 在 `talks/test-engineer-to-coordinator-2026-03-27-002.md` 报告完成