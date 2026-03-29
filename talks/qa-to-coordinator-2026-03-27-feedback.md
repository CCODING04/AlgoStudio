# QA Engineer Feedback - Phase 2.3 E2E Plan Review

**Date:** 2026-03-27
**From:** @qa-engineer
**Status:** Complete

---

## 1. E2E Tests Needed for Phase 2.3

Phase 2.3 includes three major features per `phase2-schedule.md`:
- RBAC 权限系统
- 公平调度算法
- Hosts/Deploy 页面

### 1.1 RBAC E2E Tests (Missing from E2E Plan)

The current E2E plan has **no RBAC E2E tests**. The Phase 2.3 design document (`rbac-permission-design.md`) specifies:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/organizations/{org_id}/teams` | GET | List teams |
| `/api/teams/{team_id}/members` | POST/DELETE | Manage members |
| `/api/tasks/{task_id}` | DELETE | Cancel task (with permission check) |
| `/api/tasks/{task_id}/history` | GET | Get task history |
| `/api/tasks/{task_id}/resources` | GET | Get resource usage |

**Required E2E tests:**
- TC-RBAC-001: Team lead can cancel team member's task (Owner/Team Lead/Admin)
- TC-RBAC-002: Regular user cannot cancel another user's task
- TC-RBAC-003: Admin can view all tasks in organization
- TC-RBAC-004: Team member can view other team member's tasks
- TC-RBAC-005: Cross-organization user cannot access resources

### 1.2 Task Lifecycle E2E Tests (Missing)

Phase 2.3 adds task cancellation, history, and resource APIs. Required tests:

- TC-TASK-001: Cancel pending task via DELETE /api/tasks/{id}
- TC-TASK-002: Cancel running task sends Ray cancel signal
- TC-TASK-003: Cancel completed task returns 400 error
- TC-TASK-004: Get task history returns all state transitions
- TC-TASK-005: Get task resources returns GPU/CPU/memory metrics

### 1.3 Fair Scheduling E2E Tests (Insufficient)

Current plan has TC-CLUSTER-001 and TC-CLUSTER-004 which touch on scheduling, but Phase 2.3's "公平调度算法" (fair scheduling algorithm) is not explicitly tested. Need:

- TC-SCHED-001: Tasks are distributed evenly across nodes (fair share)
- TC-SCHED-002: GPU memory is considered in scheduling decisions
- TC-SCHED-003: New node joining triggers rebalancing

---

## 2. Testing Concerns

### 2.1 Deploy/Hosts Page Testing Dependencies

TC-WEB-007 (Deploy page) and TC-WEB-005/006 (Hosts page) depend on `@frontend-engineer` completing Hosts/Deploy pages. If implementation is delayed, E2E tests cannot proceed.

**Recommendation:** Consider mocking the frontend for initial E2E testing of backend APIs.

### 2.2 RBAC Test Data Setup

RBAC E2E tests require complex test data setup:
- Multiple organizations
- Teams with different roles
- Cross-organization users

**Recommendation:** Add `tests/e2e/fixtures/rbac_test_data.py` for fixture setup.

### 2.3 SSE Progress Tests Reliability

TC-WEB-004 (SSE progress updates) has timing sensitivity. Tests may be flaky if:
- Network latency affects SSE delivery
- Ray task progress timing varies

**Recommendation:** Add timeout/retry logic and mark as P1 (not P0).

### 2.4 Node Failure Tests (TC-CLUSTER-002)

The Round 2 update added task migration verification, but simulating node failure reliably in E2E is challenging.

**Recommendation:** Consider integration tests with mock Ray actors for deterministic behavior.

---

## 3. E2E Testing Timeline Recommendation

**Start E2E testing during implementation, not after.**

Current plan has E2E starting Week 5 (Phase 2.3 Week 5-6). However:

| Phase 2.3 Feature | Backend Ready | Frontend Ready | E2E Can Start |
|-------------------|---------------|----------------|---------------|
| Task cancellation API | Week 5 Day 5 | N/A | Week 5 Day 5 |
| RBAC Team APIs | Week 5 Day 4 | N/A | Week 5 Day 4 |
| Hosts page | N/A | Week 5-6 | Week 6 |
| Deploy page | N/A | Week 5-6 | Week 6 |

**Recommended approach:**
- **Week 5**: Start API-level E2E tests for backend features (task cancellation, RBAC, history)
- **Week 6**: Integrate frontend E2E tests as pages become available

---

## 4. Summary of Gaps

| Gap | Severity | Action Required |
|-----|----------|-----------------|
| No RBAC E2E tests | High | Add TC-RBAC-001 to TC-RBAC-005 |
| No task lifecycle E2E tests | High | Add TC-TASK-001 to TC-TASK-005 |
| Fair scheduling not explicitly tested | Medium | Add TC-SCHED-001 to TC-SCHED-003 |
| Deploy page tests depend on frontend | Medium | Consider API-level testing first |

---

## 5. Next Steps for QA

1. Add RBAC E2E test cases to `PHASE2_E2E_PLAN.md`
2. Create `tests/e2e/cluster/test_scheduling.py` for fair scheduling
3. Create `tests/e2e/rbac/` directory structure
4. Coordinate with @backend-engineer for API completion timeline
5. Get @frontend-engineer schedule for Hosts/Deploy pages

---

**Approval needed from:** @coordinator
**Blocking:** None - can proceed with API-level tests while waiting for frontend
