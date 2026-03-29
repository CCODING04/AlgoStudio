# Round 2 Completion - WFQ State Update Fix

**From:** ai-scheduling-engineer
**To:** coordinator
**Date:** 2026-03-27
**Subject:** Phase 2.3 Round 2 Task Completed

## Task Completed

Fixed the WFQ state update issue identified in Round 1 review.

## Issue Fixed

**Location:** `src/algo_studio/core/scheduler/global_queue.py` line 137

**Problem:** `TenantQueue.cumulative_weight` was never updated after task scheduling. `update_wfq_state()` existed but was never called from `GlobalSchedulerQueue.dequeue()`.

**Fix Applied:**
Added call to `selected_tenant.update_wfq_state(task_weight)` after `task = selected_tenant.dequeue()`, with task weight calculated as `0.5 + (task.priority / 100)` matching the formula in `get_task_weights()`.

```python
# Get next task from selected tenant
task = selected_tenant.dequeue()
if task:
    # Update WFQ state with task weight based on priority
    task_weight = 0.5 + (task.priority / 100)
    selected_tenant.update_wfq_state(task_weight)
    self.scheduled_count += 1
    return (task, f"tenant:{selected_tenant.tenant_id}")
```

## Verification

All 27 scheduler unit tests pass:
```
PYTHONPATH=src pytest tests/unit/scheduler/ -v
======================== 27 passed, 1 warning in 1.54s =========================
```

## Status

Ready for Round 3 or next task assignment.
