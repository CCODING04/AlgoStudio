# Performance Feedback: Phase 2.3

**From:** @performance-engineer
**To:** @coordinator
**Date:** 2026-03-27
**Subject:** Phase 2.3 API Performance Benchmark Review

---

## 1. Performance Benchmarks Needed for Phase 2.3

Phase 2.3 introduces three features with performance implications:

| Feature | Benchmark | Target | Priority |
|---------|-----------|--------|----------|
| **RBAC 权限系统** | Permission check overhead | < 10ms per request | P1 |
| **Fair Scheduling** | `AgenticScheduler.schedule()` latency | p95 < 100ms | P0 |
| **部署状态监控** | Polling impact on API | API p95 < 100ms | P0 |

Additional benchmarks from test plan:
- `GET /api/tasks` p95 < 100ms
- `GET /api/hosts` p95 < 100ms
- SSE 100 concurrent connections (>= 95% survival)

---

## 2. Performance Concerns

### Concern 1: RBAC Middleware Latency
Every API call will now go through RBAC validation. If not cached, this adds 5-15ms per request. The plan does not specify RBAC cache strategy.

**Recommendation:** Add benchmark for RBAC middleware overhead specifically.

### Concern 2: Fair Scheduling Complexity
Multi-tenant fairness algorithm may increase scheduling latency beyond 100ms target as tenant count grows.

**Recommendation:** Test with simulated multi-tenant load (10+ concurrent tasks from different users).

### Concern 3: Status Polling Cascade
If deployment status polling is implemented with short intervals (< 5s), it could create cascading load on `/api/hosts` and Ray API.

**Recommendation:** Benchmark status polling under 10 concurrentpolling clients.

---

## 3. Testing Strategy: Parallel with Implementation

**Recommendation:** Run performance tests **in parallel** with implementation, not after.

### Rationale:
1. Performance issues found late are expensive to fix
2. Test infrastructure (fixtures, baseline data) can be built before features are ready
3. Quick smoke tests (does it boot? does basic path work?) catch integration bugs early

### Proposed Schedule for Phase 2.3:

| Week | Activity |
|------|----------|
| **W5 early** | Build test fixtures for RBAC, Fair Scheduling benchmarks |
| **W5 mid** | Run smoke tests as each feature completes |
| **W5 late** | Full benchmark suite for RBAC + Scheduling |
| **W6** | Integration benchmarks (E2E + Performance combined) |

### Pre-requisites from other roles:
- Need `@backend-engineer` to expose RBAC decision as standalone function for isolated benchmarking
- Need `@ai-scheduling-engineer` to provide mock scheduling scenarios for latency testing

---

## 4. Action Items

| Item | Owner | Status | Notes |
|------|-------|--------|-------|
| RBAC middleware benchmark | @performance-engineer | Pending | Requires RBAC implementation |
| Fair scheduling latency test | @performance-engineer | Pending | Requires algorithm implementation |
| Status polling load test | @performance-engineer | Pending | Requires monitoring implementation |
| Baseline benchmarks storage | @performance-engineer | Ready | `tests/performance/benchmarks/` structure exists |

---

## 5. Risk Summary

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| RBAC adds > 10ms per request | Medium | High | Cache permissions; benchmark early |
| Fair scheduling > 100ms under load | Medium | Medium | Optimize algorithm; pre-compute scores |
| Polling overloads API | Low | High | Use SSE push instead of polling |

---

**Status:** Ready to start test infrastructure build in Week 5
