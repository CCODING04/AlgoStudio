# Round 2 Architecture Review

## Round 1 Issues Status

| ID | Issue | Status | Verification |
|----|-------|--------|---------------|
| 1 | team_membership.py `Mapped[User]` NameError | **FIXED** | Lines 35, 39 use proper forward references `Mapped["User"]` and `Mapped["Team"]` with `from __future__ import annotations` |
| 2 | Deploy API RBAC missing | **FIXED** | All 4 endpoints have `@require_permission` decorators: `DEPLOY_READ` on GET endpoints (lines 88, 170, 309), `DEPLOY_WRITE` on POST endpoint (line 211) |
| 4 | VFT state never updated | **FIXED** | `update_wfq_state()` called in `global_queue.py` line 141 after dequeue, passing `task_weight = 0.5 + (task.priority / 100)`. Method exists in `TenantQueue.update_wfq_state()` (tenant_queue.py line 117) |
| 5 | Response models not Pydantic | **FIXED** | All response models use Pydantic `BaseModel`: `DeployProgressResponse` (line 47), `DeployWorkerResponse` (line 62), `DeployListResponse` (line 77). Serialization uses `.model_dump()` (line 164) |

## New Issues Found

None.

## Code Quality Observations

1. **team_membership.py**: Clean implementation with proper forward references and `from __future__ import annotations` at line 4.
2. **deploy.py**: Well-structured with Pydantic models for all request/response types. SSE progress streaming properly implemented with heartbeat mechanism.
3. **global_queue.py**: WFQ state correctly updated after each dequeue. The `update_wfq_state(task_weight)` is called with a priority-based weight calculation.

## Conclusion: PASS

All Round 1 issues have been properly resolved. No new issues detected. The implementation is consistent with the architecture requirements.

---

## API/Security Review

**日期:** 2026-03-27
**评审人:** @architect-beta (Platform Architect)
**评审范围:** Deploy API RBAC + E2E api_client fixture

### Round 1 P0 Issue Verification

| ID | Issue | Status | Evidence |
|----|-------|--------|----------|
| 2 | Deploy API RBAC missing | **FIXED** | All 4 endpoints have `@require_permission` decorators: `DEPLOY_READ` on GET endpoints (lines 88, 170, 309), `DEPLOY_WRITE` on POST endpoint (line 211) |
| 3 | api_client fixture missing methods | **FIXED** | All 4 deploy methods added: `list_deployments()` (line 141), `get_deployment()` (line 150), `create_deployment()` (line 154), `get_deployment_progress()` (line 158) |
| 5 | Response models not Pydantic | **FIXED** | All response models use Pydantic `BaseModel`: `DeployProgressResponse` (line 47), `DeployWorkerResponse` (line 62), `DeployListResponse` (line 77) |

### RBAC Decorator Verification

| 端点 | Method | Path | Decorator | Line |
|------|--------|------|-----------|------|
| list_workers | GET | `/api/deploy/workers` | `@require_permission(Permission.DEPLOY_READ)` | 88 |
| get_worker | GET | `/api/deploy/worker/{task_id}` | `@require_permission(Permission.DEPLOY_READ)` | 170 |
| create_worker | POST | `/api/deploy/worker` | `@require_permission(Permission.DEPLOY_WRITE)` | 211 |
| get_worker_progress | GET | `/api/deploy/worker/{task_id}/progress` | `@require_permission(Permission.DEPLOY_READ)` | 309 |

### Permission Enum Alignment

| Permission | Defined In | Used In |
|------------|------------|---------|
| `DEPLOY_READ = "deploy.read"` | rbac.py:56 | deploy.py:88, 170, 309 |
| `DEPLOY_WRITE = "deploy.write"` | rbac.py:57 | deploy.py:211 |

### api_client Fixture Methods Added

```python
# tests/e2e/playwright.config.py lines 141-161
def list_deployments(self, status: Optional[str] = None, node_ip: Optional[str] = None)
def get_deployment(self, task_id: str)
def create_deployment(self, deploy_data: dict)
def get_deployment_progress(self, task_id: str)
```

### Pydantic Response Models

All models in `deploy.py` lines 47-81 use `BaseModel`:
- `DeployProgressResponse`
- `DeployWorkerResponse`
- `DeployListResponse`

### Non-Blocking Observations

| Item | Status | Note |
|------|--------|------|
| IP format validation | Partial | Basic null check (lines 239-258), regex validation not implemented |
| Global mutable state | Known | `_progress_store`, `_deployer` remain module-level |
| Password in request body | Handled | Password not echoed in responses |

### Conclusion

| Metric | Result |
|--------|--------|
| P0 Issue 2 (RBAC) | ✅ FIXED |
| P0 Issue 3 (api_client) | ✅ FIXED |
| Pydantic Models | ✅ COMPLETE |
| **Overall** | **READY** |
