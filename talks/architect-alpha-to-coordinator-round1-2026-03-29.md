# Phase 3.2 Round 1 Architecture Review
**From:** @architect-alpha
**To:** @coordinator
**Date:** 2026-03-29
**Review Items:** Sentinel Config, DeploymentSnapshotStore Phase 2, test_tasks_sse.py

---

## 1. Sentinel Configuration Audit

**File:** `configs/sentinel/sentinel-26380.conf`

### Assessment: PARTIAL CONCERN

**Findings:**

1. **Quorum Configuration Issue (Medium)**
   - Quorum set to `2` but only 1 Sentinel visible in config
   - Sentinel cannot achieve quorum alone - failover will never trigger
   - **Recommendation:** Either reduce quorum to `1` for single-Sentinel setup, or add more Sentinel instances

2. **No Replica Definition (Critical)**
   - Sentinel monitors master at `192.168.0.126:6380`
   - No `sentinel known-replica` or actual replica discovered
   - Without replicas, failover cannot promote a new master
   - **Recommendation:** Add replica configuration or verify replication is working

3. **Security: No Authentication (Low)**
   - Lines 36-37 (auth-pass) commented out
   - Acceptable for internal networks, but should be documented
   - **Recommendation:** Add auth if accessible from less trusted networks

4. **Test Script: DEBUG SLEEP Usage (Warning)**
   - `scripts/test_sentinel_failover.sh` uses `DEBUG SLEEP` to simulate failure
   - This is Redis internal command, requires admin privileges
   - Document clearly this is for test environments only

---

## 2. DeploymentSnapshotStore Phase 2 - Interface Registration

**Files:**
- `src/algo_studio/core/deploy/rollback.py`
- `src/algo_studio/core/interfaces/snapshot_store.py`

### Assessment: NEEDS IMPROVEMENT

### Issue 1: Runtime Registration Without Verification

The registration pattern at lines 1011-1032 in `rollback.py`:

```python
def _register_as_snapshot_store_interface():
    try:
        from algo_studio.core.interfaces.snapshot_store import SnapshotStoreInterface
        SnapshotStoreInterface.register(DeploymentSnapshotStore)
    except ImportError:
        pass

_register_as_snapshot_store_interface()
del _register_as_snapshot_store_interface
```

**Problem:** `ABC.register()` is a virtual subclass mechanism that does NOT verify the class actually implements the interface. If `DeploymentSnapshotStore` is missing a method or has an incorrect signature, this will silently pass.

**Risk:** Someone could add a method to `SnapshotStoreInterface` and forget to implement it in `DeploymentSnapshotStore`, and the registration would still "succeed."

**Recommendation:** Add explicit verification:
```python
# Verify all abstract methods are implemented
for method_name in ['save_snapshot', 'get_snapshot', 'list_snapshots',
                    'delete_snapshot', 'save_rollback_history', 'get_rollback_history']:
    if not hasattr(DeploymentSnapshotStore, method_name):
        raise TypeError(f"DeploymentSnapshotStore missing method: {method_name}")
```

### Issue 2: Inconsistent Error Handling in DeploymentSnapshotStore

Comparing method implementations in `DeploymentSnapshotStore`:

| Method | Has try/except | Catches Redis Errors |
|--------|---------------|---------------------|
| `save_snapshot` | Yes | Yes |
| `get_snapshot` | **NO** | **NO** |
| `list_snapshots` | Yes | Yes |
| `delete_snapshot` | Yes | Yes |
| `get_snapshots_by_node` | **NO** | **NO** |
| `save_rollback_history` | **NO** | **NO** |
| `get_rollback_history` | **NO** | **NO** |

**Lines missing error handling:**
- `get_snapshot()`: Lines 303-318 - no try/except
- `get_snapshots_by_node()`: Lines 396-424 - no try/except
- `save_rollback_history()`: Lines 426-447 - no try/except
- `get_rollback_history()`: Lines 449-481 - no try/except

**Risk:** Redis connection failures or timeouts will propagate as unhandled exceptions, potentially crashing the async event loop or causing unpredictable behavior.

**Contrast with RedisSnapshotStore:** All methods have proper try/except blocks.

**Recommendation:** Add try/except to all methods in `DeploymentSnapshotStore` for consistency and robustness.

### Issue 3: Missing Deep Copy in DeploymentSnapshotStore

`InMemorySnapshotStore.get_snapshot()` (line 156-160) returns a deep copy:
```python
return copy.deepcopy(snapshot)
```

`DeploymentSnapshotStore.get_snapshot()` (line 303-318) returns the object directly:
```python
return DeploymentSnapshot.from_dict(json.loads(data))
```

**Risk:** External code could modify the returned snapshot and affect stored data.

**Recommendation:** Return a deep copy or document that callers should not modify returned objects.

---

## 3. test_tasks_sse.py - Test Engineering Review

**File:** `tests/unit/api/routes/test_tasks_sse.py`

### Assessment: GOOD STRUCTURE, NEEDS COVERAGE

### Strengths:
1. Well-organized test classes by concern (endpoint, format, disconnect handling)
2. Good use of fixtures in conftest.py - 6 shared fixtures
3. Proper async test patterns with `@pytest.mark.asyncio`
4. MockTask class provides flexible test doubles
5. Authentication header generation is comprehensive

### Issue 1: Limited Actual SSE Streaming Tests

Most tests are format/structure validation, not actual SSE streaming behavior:
- `TestSSEProgressEndpoint` - Tests route existence and 404, not streaming
- `TestSSEProgressGenerator` - Tests generator creation, not iteration
- `TestSSEEventFormat` - Only validates JSON structure, not SSE format

**Missing test scenarios:**
- Actual iteration over SSE events
- Multiple progress updates during streaming
- Heartbeat behavior at 30-event intervals
- Race condition when task completes during streaming

**Recommendation:** Add integration tests that actually iterate the SSE generator and validate events.

### Issue 2: Test Isolation Concern

The `MockTask` class (lines 84-112) uses `MagicMock` for `task_type` and `status`:

```python
@property
def task_type(self):
    return MagicMock(value=self._task_type)

@property
def status(self):
    return MagicMock(value=self._status)
```

**Problem:** The `MockTask` doesn't properly emulate the real task interface. Real tasks likely use `TaskType` and `TaskStatus` enums, not MagicMock wrappers.

**Risk:** Tests pass but real code using enum comparisons fails.

**Recommendation:** Make MockTask use actual TaskType/TaskStatus enum values.

### Issue 3: Cleanup Fixture Overwrites

`test_tasks_sse.py` defines its own `cleanup_sse_state` fixture (lines 60-69), while `conftest.py` in routes has `clean_app_state` (lines 91-103).

The local fixture only clears `TaskManager._instances`, while the shared fixture does the same. This is redundant but not harmful.

---

## Summary

| Deliverable | Status | Priority Issues |
|-------------|--------|-----------------|
| Sentinel Config | PARTIAL CONCERN | Quorum/replica configuration gaps |
| DeploymentSnapshotStore | NEEDS IMPROVEMENT | Missing error handling, no interface verification |
| test_tasks_sse.py | GOOD STRUCTURE | Needs actual SSE streaming tests |

### Action Items for Round 2:

1. **@devops-engineer:** Fix Sentinel quorum/replica configuration
2. **@backend-engineer:**
   - Add error handling to `DeploymentSnapshotStore` methods (get_snapshot, get_snapshots_by_node, save_rollback_history, get_rollback_history)
   - Add interface implementation verification
3. **@test-engineer:** Add actual SSE streaming iteration tests

---

## Phase 2 Architecture Completeness Assessment

Overall Phase 2 architecture is solid with the following gaps:

1. **Interface consistency** - RedisSnapshotStore is properly implemented with error handling; DeploymentSnapshotStore is not
2. **Dependency injection** - Uses runtime registration which works but lacks verification
3. **Error handling** - Inconsistent across implementations

**Recommendation:** Consider adding an abstract base class verification at module load time to catch interface mismatches early.
