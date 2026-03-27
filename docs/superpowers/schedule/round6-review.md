# Round 6 QA Review - Tasks API Tests

**Reviewer:** @qa-reviewer (Senior Code Reviewer)
**Date:** 2026-03-27
**File Reviewed:** `tests/unit/api/test_tasks_api.py`

---

## Summary

The test file has been improved with RBAC authentication tests and DELETE endpoint tests. However, my independent review found issues that require attention.

---

## QA Score: 7/10

---

## Critical Issues

### C1: RBAC Tests Only Cover GET Endpoint

**Severity:** Critical
**Location:** `TestTasksAPIRBAC` class (lines 312-362)

**Problem:** All three main RBAC tests only verify authentication on `GET /api/tasks`:
- Line 323: `response = await client.get("/api/tasks")`
- Line 337: `response = await client.get("/api/tasks", headers=headers)`
- Line 351: `response = await client.get("/api/tasks", headers=headers)`

**Impact:** If RBAC middleware is not properly applied to POST, DELETE, or dispatch endpoints, the test suite would not detect this vulnerability.

**Recommendation:** Add RBAC tests for other HTTP methods:

```python
@pytest.mark.asyncio
async def test_tasks_api_rejects_post_without_auth_header(self, client):
    """Test POST /api/tasks without auth header is rejected."""
    response = await client.post(
        "/api/tasks",
        json={"task_type": "train", "algorithm_name": "simple_classifier", "algorithm_version": "v1"},
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_tasks_api_rejects_delete_without_auth_header(self, client):
    """Test DELETE /api/tasks/{id} without auth header is rejected."""
    response = await client.delete("/api/tasks/some-id")
    assert response.status_code == 401
```

---

### C2: Misleading Test Name

**Severity:** Important
**Location:** Line 416, `test_delete_task_already_completed`

**Problem:** The test name implies testing deletion of a COMPLETED task, but the actual DELETE endpoint (`src/algo_studio/api/routes/tasks.py` line 157-158) blocks RUNNING tasks:

```python
if task.status == TaskStatus.RUNNING:
    raise HTTPException(status_code=400, detail=f"Cannot delete running task")
```

The test dispatches a task (making it RUNNING), then tries to delete it. The name should reflect this.

**Recommendation:** Rename to `test_delete_task_running_fails` and update docstring accordingly.

---

## Minor Suggestions

### S1: `test_missing_secret_key_rejects_all_requests` Does Not Test Its Claim

**Location:** Lines 355-361

The test sets `RBAC_SECRET_KEY` at line 10 before importing the app, then claims to test missing secret key behavior by making a request without auth headers. This tests missing auth (401), not missing secret key.

**Recommendation:** Either remove as redundant with other tests, or properly test the missing key scenario by temporarily unsetting the env var.

---

### S2: No Test for Deleting Completed Task

The DELETE endpoint allows deletion of completed tasks (only blocks running). There is no test verifying that a completed task CAN be deleted.

---

## Positive Findings

1. RBAC auth tests are well-structured with proper HMAC-SHA256 signature generation
2. DELETE tests cover success, not found, running-task-blocked, and permission denial
3. Helper functions `make_auth_headers` and `generate_valid_signature` are clean and reusable
4. All 24 tests have actual implementations (empty test issue I1 is fixed)
5. Test assertions are appropriate (status codes, error messages, response fields)

---

## Pass/Fail Recommendation

**Status:** CONDITIONAL PASS

| Issue | Severity | Must Fix |
|-------|----------|----------|
| C1: RBAC only tested on GET endpoint | Critical | Yes |
| C2: Misleading test name | Important | Yes |

**Action Required:** @test-engineer should address C1 and C2 before final approval.

**C1 Fix:** Add RBAC tests for POST `/api/tasks` and DELETE `/api/tasks/{id}` endpoints.

**C2 Fix:** Rename `test_delete_task_already_completed` to `test_delete_task_running_fails`.