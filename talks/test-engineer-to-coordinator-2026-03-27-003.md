# test-engineer to coordinator - 2026-03-27-003

## Round 6 QA Review Fixes Completed

### Changes Made

**File:** `tests/unit/api/test_tasks_api.py`

### C1: Added POST/DELETE RBAC Authentication Tests (Critical)

Added to `TestTasksAPIRBAC` class:
- `test_tasks_api_rejects_post_without_auth_header` - Verifies POST /api/tasks without auth returns 401
- `test_tasks_api_rejects_delete_without_auth_header` - Verifies DELETE /api/tasks/{id} without auth returns 401

### C2: Renamed Misleading Test (Important)

Renamed `test_delete_task_already_completed` to `test_delete_task_running_fails` to accurately reflect that the DELETE endpoint blocks RUNNING tasks, not COMPLETED tasks.

### Test Results

All 26 tests passed:
```
tests/unit/api/test_tasks_api.py::TestTasksAPI ............................ 14 passed
tests/unit/api/test_tasks_api.py::TestTasksAPIResponseFormat ................. 2 passed
tests/unit/api/test_tasks_api.py::TestTasksAPIRBAC ........................... 6 passed
tests/unit/api/test_tasks_api.py::TestDeleteTaskEndpoint ..................... 4 passed
```

### Commit

```
2a79ed8 test: add POST/DELETE RBAC auth tests, rename misleading test
```

## Status: COMPLETED