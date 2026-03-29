# Investigation Task: Task Auto-Dispatch Issue (P2)

**From:** Coordinator
**To:** @ai-scheduling-engineer
**Date:** 2026-03-29
**Priority:** P2

---

## Task

Investigate Bug 2 in `docs/superpowers/test/ISSUE_BUGS_2026-03-29.md`

### Problem
Pending tasks are not being automatically assigned to nodes.

### Analysis So Far
- Manual dispatch via `POST /api/tasks/{taskId}/dispatch` works correctly
- Scheduler and Ray cluster are functioning
- Task runs normally after manual dispatch on node `admin10-System-Product-Name`

### Possible Causes
1. Auto-dispatch is not enabled
2. Scheduler polling interval is too long
3. Internal scheduler issue

### Investigation Required
1. Check `src/algo_studio/core/task.py` - TaskManager auto-dispatch logic
2. Check `src/algo_studio/core/scheduler/wfq_scheduler.py` - scheduler dispatch logic
3. Confirm expected behavior: should pending tasks be auto-dispatched?
4. If yes, what is the polling interval?

### Files to Investigate
- `src/algo_studio/core/task.py` (TaskManager)
- `src/algo_studio/core/scheduler/wfq_scheduler.py`
- `src/algo_studio/api/routes/tasks.py`

### Expected Output
1. Root cause identification
2. If it's a bug: fix implementation
3. If behavior is correct: explain why tasks don't auto-dispatch

---

Please investigate and report findings.
