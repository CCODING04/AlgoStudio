# Test Engineer Feedback: Phase 2.3 Plan Review

**Date:** 2026-03-27
**From:** @test-engineer
**To:** @coordinator

---

## 1. Test Infrastructure Needs for Phase 2.3

### 1.1 RBAC Permission System Tests

**Required Test Files:**
- `tests/unit/api/test_rbac_extended.py` - New Organization/Team/User hierarchy tests
- `tests/unit/core/test_permission_checker.py` - PermissionChecker class unit tests
- `tests/unit/api/test_audit_logging.py` - AuditLog API tests

**New Fixtures Needed:**
```python
# Organization/Team fixtures
@pytest.fixture
def org_factory():
    """Factory for creating Organization test data."""

@pytest.fixture
def team_factory():
    """Factory for creating Team test data."""

@pytest.fixture
def team_membership_factory():
    """Factory for creating TeamMembership test data."""

@pytest.fixture
def audit_log_factory():
    """Factory for creating AuditLog test data."""

# Mock for PermissionChecker
@pytest.fixture
def mock_permission_checker():
    """Provide a mocked PermissionChecker."""
```

**Test Cases Required:**
| Category | Test Cases |
|----------|------------|
| Organization CRUD | Create, Read, List, Delete organizations |
| Team CRUD | Create, Read, List, Delete teams |
| Team Membership | Add member, Remove member, Role changes |
| Permission Inheritance | org -> team -> user permission flow |
| Resource-level Permissions | Task owner, team member, org member, public access |
| Audit Logging | Permission grant/revoke logging, IP tracking |

### 1.2 Task Progress API Tests

**Required Test Files:**
- `tests/unit/api/test_task_cancellation.py` - Task cancellation endpoint tests
- `tests/unit/api/test_task_history.py` - Task history endpoint tests
- `tests/unit/api/test_task_resources.py` - Task resources endpoint tests
- `tests/integration/test_task_lifecycle.py` - Full task lifecycle integration

**Test Cases Required:**
| Category | Test Cases |
|----------|------------|
| Task Cancel - Success | Cancel pending task, Cancel running task |
| Task Cancel - Forbidden | Viewer cannot cancel, Non-member cannot cancel |
| Task Cancel - Invalid State | Cannot cancel completed task |
| Task History | Create history, Read history, Empty history |
| Task Resources | Get resources for running task, Resource aggregation |

### 1.3 Fair Scheduling Algorithm Tests

**Required Test Files:**
- `tests/unit/scheduler/test_wfq_scheduler.py` - WFQ core algorithm tests
- `tests/unit/scheduler/test_reservation_manager.py` - Reservation system tests
- `tests/unit/scheduler/test_priority_override.py` - Priority override tests
- `tests/unit/scheduler/test_fair_scheduler_integration.py` - Integration tests

**Test Cases Required:**
| Category | Test Cases |
|----------|------------|
| WFQ Selection | VFT calculation, Task selection order |
| Tenant Queue | Enqueue, Dequeue, Priority ordering |
| Global Queue | Multi-tenant scheduling, Round-robin |
| Reservation | Create reservation, Release, Guaranteed minimums |
| Priority Override | Urgent flag, High priority (>=90), Team bypass |
| Starvation Prevention | Long-waiting task gets scheduled |
| Quota Integration | Weight-based scheduling, Fair share calculation |

---

## 2. Testing Concerns

### 2.1 Complex Permission Inheritance

**Concern:** The PermissionChecker implements hierarchical inheritance (org -> team -> user) which is complex and error-prone.

**Risk:** Incorrect permission checks could allow unauthorized access or block legitimate access.

**Mitigation:**
- Unit test every permission check method with all combinations of roles and relationships
- Integration test with real database to verify cascade behavior
- Edge cases: user in multiple teams, org with no teams, suspended users

### 2.2 Fair Scheduling Mathematical Correctness

**Concern:** WFQ Virtual Finish Time (VFT) formula involves floating-point math and cumulative state.

**Risk:** Rounding errors or state tracking bugs could cause unfair scheduling.

**Mitigation:**
- Deterministic unit tests with fixed inputs
- Property-based testing for VFT formula
- Stress test with many tenants and tasks

### 2.3 Task Cancellation State Machine

**Concern:** Task cancellation involves multiple state transitions and external Ray cancellation.

**Risk:** Race conditions between API cancel request and Ray task completion.

**Mitigation:**
- Test state machine with all valid/invalid transitions
- Integration test with mock Ray client
- Verify audit log entries for all cancellation paths

### 2.4 Database Migration Testing

**Concern:** Phase 2.3 adds 6 new tables and modifies the tasks table.

**Risk:** Migration failures or data loss in production.

**Mitigation:**
- Unit test migration scripts independently
- Integration test with test database
- Verify rollback works correctly

---

## 3. Parallel vs. Sequential Testing Recommendation

### Recommendation: **Hybrid Approach**

**Test Implementation in Parallel with Feature Development:**

| Week | Implementation | Test Development |
|------|---------------|------------------|
| W5 D1-2 | DB Migration + Models | Test DB migration, model fixtures |
| W5 D3-4 | TeamMembership API | API endpoint tests |
| W5 D5 | Task Cancellation Backend | Cancellation unit tests |
| W6 D1-2 | Task History + AuditLog | History/Audit tests |
| W6 D3-4 | Task Resources API | Resource API tests |
| W6 D5 | Fair Scheduling | WFQ algorithm tests |

**Rationale:**
1. Unit tests can be written once interfaces are defined (design doc is sufficient)
2. API integration tests need implementation but can use mock fixtures
3. E2E tests require full implementation but can start after Week 5

**Key Dependencies:**
- RBAC tests depend on PermissionChecker implementation
- Fair scheduling tests depend on WFQScheduler implementation
- Task cancellation tests depend on TaskManager.cancel_task()

---

## 4. Estimated Test Count

| Phase 2.3 Feature | Unit Tests | Integration Tests | Total |
|-------------------|------------|-------------------|-------|
| RBAC Hierarchy | 35 | 15 | 50 |
| PermissionChecker | 25 | 10 | 35 |
| Task Cancellation | 15 | 10 | 25 |
| Task History | 10 | 8 | 18 |
| Task Resources | 12 | 8 | 20 |
| Fair Scheduling | 40 | 15 | 55 |
| **Total** | **137** | **66** | **203** |

---

## 5. Existing Test Infrastructure Compatibility

**Good News:**
- Existing `conftest.py` provides factory pattern and mock fixtures
- RBAC tests already have `make_auth_headers()` helper
- Async test support via `pytest-asyncio`

**Gaps to Fill:**
- No Organization/Team model fixtures
- No AuditLog fixtures
- No `mock_quota_manager` fixture for scheduler tests
- No `mock_reservation_manager` fixture

---

## 6. Questions/Decisions Needed

1. **Database for tests:** SQLite (faster, no external deps) or Redis-backed test DB?
2. **Fair scheduling toggle:** Should tests cover both enabled/disabled states?
3. **Real Ray cluster for integration:** Requires cluster access - acceptable for E2E only?
4. **AuditLog retention:** Tests need to verify old logs are not queryable?

---

**Status:** Ready to begin test development once Phase 2.3 implementation starts
