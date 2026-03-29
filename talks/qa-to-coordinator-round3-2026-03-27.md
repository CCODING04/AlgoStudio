# QA Engineer Report - Round 3 E2E Tests

## Test Summary

| Metric | Count |
|--------|-------|
| **Total** | 79 |
| **Passed** | 8 |
| **Failed** | 11 |
| **Skipped** | 4 |
| **Errors** | 56 |

## Test Breakdown

### Passed Tests (8)
All from `cluster/test_real_failure.py`:
- `test_real_node_failure_detection_via_ray_nodes`
- `test_real_node_monitor_actor_health_check`
- `test_real_task_heartbeat_timeout_detection`
- `test_real_task_status_update_on_ray_failure`
- `test_real_progress_store_actor_accessible`
- `test_real_actor_call_timeout`
- `test_real_node_query_timeout_handling`
- `test_real_task_config_preservation`

### Failed Tests (11)

#### Critical Code Bugs (FAILURES):

1. **`test_real_task_resubmission_after_node_failure`** - `cluster/test_real_failure.py`
   - Bug: `TaskManager.update_progress()` does NOT persist progress
   - Expected: progress == 50 after `update_progress(task_id, 50)`
   - Actual: progress stays at 0
   - Root cause: `update_progress` likely not syncing to ProgressStore

2. **SSE endpoint 500 errors** - `web/test_sse_real.py` (7 tests)
   - The SSE endpoint `/api/cluster/events` returns 500 Internal Server Error
   - Affected tests: `test_real_sse_endpoint_accessible`, `test_real_sse_long_connection_keepalive`, `test_real_sse_connection_recovery_after_network_blip`, `test_real_sse_event_format_validity`, `test_real_sse_client_handles_idle_timeout`
   - Root cause: Backend exception in the SSE generator (needs investigation in `src/algo_studio/api/routes/cluster.py`)

3. **SSEClient iteration errors** - 4 tests
   - `TypeError: 'SSEClient' object is not iterable`
   - Likely version mismatch with sseclient library

4. **SSE mock CI timeout** - `test_sse_mock_preserves_ci_compatibility`
   - httpx.ReadTimeout: timed out

### Error Tests (56) - Missing `page` Fixture

All web UI tests fail with: `fixture 'page' not found`

**Root Cause:** Playwright (`pytest-playwright`) is NOT installed in the environment.

Affected test files:
- `web/test_deploy_page.py` (14 tests)
- `web/test_hosts_page.py` (15 tests)
- `web/test_sse_progress.py` (3 tests)
- `cluster/test_failure_recovery.py` (4 tests)
- `cluster/test_rbac_e2e.py` (10 tests)
- `cluster/test_scheduling_e2e.py` (10 tests)

**Fix:** Install Playwright:
```bash
uv pip install playwright pytest-playwright
playwright install chromium
```

### Skipped Tests (4)
- SSE mock tests with `skip_ci` marker

## Priority Issues

### P0 - Blocking
1. **TaskManager.update_progress() bug** - Progress not persisted
2. **SSE endpoint 500 error** - Backend crashes on `/api/cluster/events`

### P1 - Infrastructure
1. **Playwright not installed** - Blocks all web UI E2E tests

## Recommendations

1. **@backend-engineer**: Investigate SSE endpoint crash in `cluster.py`
2. **@backend-engineer**: Fix `TaskManager.update_progress()` to persist progress
3. **Install Playwright** before web UI E2E tests can run
