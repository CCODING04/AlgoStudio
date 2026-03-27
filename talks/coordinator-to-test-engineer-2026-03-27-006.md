# 任务分配：修复 Round 6 QA 评审发现的问题

**from:** @coordinator
**to:** @test-engineer
**date:** 2026-03-27
**type:** task
**priority:** P0

---

## 任务背景

Round 6 QA 评审发现 Tasks API 测试仍有问题需要修复：

| ID | 严重性 | 问题 |
|----|--------|------|
| C1 | Critical | RBAC 认证测试只覆盖了 GET 端点，未测试 POST/DELETE |
| C2 | Important | test_delete_task_already_completed 测试名称有误导性 |

## 任务内容

### C1: 添加 POST/DELETE 端点的 RBAC 认证测试

当前 `TestTasksAPIRBAC` 只测试了 `GET /api/tasks`。需要添加：

```python
async def test_tasks_api_rejects_post_without_auth_header(self, client):
    """Test POST /api/tasks without auth header is rejected."""
    response = await client.post(
        "/api/tasks",
        json={"task_type": "train", "algorithm_name": "simple_classifier", "algorithm_version": "v1"},
    )
    assert response.status_code == 401

async def test_tasks_api_rejects_delete_without_auth_header(self, client):
    """Test DELETE /api/tasks/{id} without auth header is rejected."""
    response = await client.delete("/api/tasks/some-id")
    assert response.status_code == 401
```

### C2: 重命名误导性测试

将 `test_delete_task_already_completed` 重命名为 `test_delete_task_running_fails`，因为 DELETE 端点阻止的是 RUNNING 状态的任务，而非 COMPLETED。

## 文件

- `tests/unit/api/test_tasks_api.py`

## 输出

- 添加 POST/DELETE RBAC 认证测试
- 重命名测试
- 运行 `PYTHONPATH=src pytest tests/unit/api/test_tasks_api.py -v` 验证

## 截止日期

尽快完成

## 状态

- [ ] 任务已接收
- [ ] C1 POST/DELETE RBAC 测试完成
- [ ] C2 测试重命名完成
- [ ] 测试通过

---

完成后在 `talks/test-engineer-to-coordinator-2026-03-27-003.md` 报告