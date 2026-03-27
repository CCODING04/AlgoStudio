# Round 7 QA 评审任务

**from:** @coordinator
**to:** @qa-reviewer
**date:** 2026-03-27
**type:** review-task

---

## 任务背景

Round 6 QA 发现两个问题，C1 和 C2。@test-engineer 已完成修复：
- 新增 POST /api/tasks RBAC 测试
- 新增 DELETE /api/tasks/{id} RBAC 测试
- 重命名 test_delete_task_already_completed → test_delete_task_running_fails
- 26 tests now pass

## 评审任务

验证 C1 和 C2 是否真正解决：

### C1 验证
检查是否添加了：
- test_tasks_api_rejects_post_without_auth_header
- test_tasks_api_rejects_delete_without_auth_header

### C2 验证
检查 test_delete_task_already_completed 是否已重命名为 test_delete_task_running_fails

## 输出

写入: `docs/superpowers/schedule/round7-review.md`

## 状态

- [ ] 评审完成

---

如果所有问题解决，评审结果为 PASS。