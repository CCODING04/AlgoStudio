# Task: Fix test_rollback_generates_unique_id Failure

## Context

Phase 3 Testing Improvement - Round 1/8

The test `test_rollback_generates_unique_id` is failing because when two rollbacks are called in the same second, they get the same ID due to second-level precision in the rollback_id generation.

## Source Issue

File: `/home/admin02/Code/Dev/AlgoStudio/src/algo_studio/core/deploy/rollback.py`
Line 424:
```python
rollback_id = f"rollback-{deployment_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
```

The format `%Y%m%d%H%M%S` only has second precision. When two rollbacks happen in the same second, they get identical IDs.

## The Fix

Change line 424 to use microseconds (like the snapshot_id does on line 248):
```python
rollback_id = f"rollback-{deployment_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
```

This matches the snapshot_id format which already uses `%f` for microseconds and is proven to work.

## Task

1. Apply the fix to rollback.py line 424
2. Run the test to verify it passes:
   ```bash
   cd /home/admin02/Code/Dev/AlgoStudio && PYTHONPATH=src pytest tests/unit/core/test_rollback.py::TestRollbackServiceRollback::test_rollback_generates_unique_id -v
   ```
3. Run all rollback tests to ensure no regressions:
   ```bash
   cd /home/admin02/Code/Dev/AlgoStudio && PYTHONPATH=src pytest tests/unit/core/test_rollback.py -v
   ```

## Expected Outcome

- Test passes
- All 43 tests pass (was 42 passed, 1 failed)
