# System Architecture Review Report
**From:** @architect-alpha (Chief Architect)
**Date:** 2026-03-29
**Topic:** Phase 3.5 R9 Sprint 4 - System Architecture Review
**Review Scope:**
1. Dataset Model Design
2. Node Role Determination Logic
3. WFQScheduler Role-Aware Scheduling

---

## 1. Dataset Model Design

### Assessment: ACCEPTABLE WITH MINOR ISSUES

#### Strengths
- Clean separation between DB model (`Dataset`) and API model (`DatasetResponse`)
- Proper use of SQLAlchemy 2.0 Mapped types with relationships
- `TimestampMixin` for automatic created_at/updated_at tracking
- `DatasetAccess` model for fine-grained per-user/team permissions
- JSON fields for `extra_metadata` and `tags` provide extensibility
- Proper foreign key constraints with `ondelete="SET NULL"` for owner/team

#### Issues Found

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|-----------------|
| **Minor** | Header comment mismatch: file says `# src/algo_studio/api/models/dataset.py` but actual path is `dataset_models.py` | `src/algo_studio/api/dataset_models.py:1` | Fix comment or rename file for consistency |
| **Minor** | No validation on `path` field format | `Dataset.path` | Add regex validation (e.g., must start with `/nas/` or `/data/`) |
| **Minor** | `DatasetResponse` lacks relationship data (owner_name, team_name) | API model | Consider denormalizing for API responses to avoid N+1 queries |
| **Minor** | `size_gb` and `file_count` nullable but likely always populated | `Dataset` model | Consider defaulting to 0 instead of NULL for numeric fields |

#### Verdict
The Dataset model design is sound and follows SQLAlchemy best practices. The issues are minor and do not affect functionality or data integrity.

---

## 2. Node Role Determination Logic

### Assessment: NEEDS IMPROVEMENT

#### Current Implementation
```python
def determine_node_role(node_ip: str, ray_head_ip: str) -> str:
    if not node_ip or not ray_head_ip:
        return "worker"
    return "head" if node_ip == ray_head_ip else "worker"
```

#### Strengths
- Simple and fast logic with no external dependencies
- `get_default_node_labels()` provides sensible defaults per role
- `NodeStatus` dataclass is well-structured with proper typing
- Fallback behavior in `hosts.py` correctly identifies local node as head

#### Issues Found

| Severity | Issue | Location | Impact |
|----------|-------|----------|--------|
| **Important** | Role determination is purely IP-based | `ray_client.py:16-31` | Fragile in multi-NIC environments; a worker with same IP as head would be misidentified |
| **Important** | No persistent node role configuration | `ray_client.py` | Role can only be determined at runtime from Ray cluster state |
| **Important** | Labels are hardcoded defaults | `get_default_node_labels()` | Cannot customize labels per node (e.g., "gpu-tier-2", "high-memory") |
| **Minor** | `get_default_node_labels` not used in hosts.py fallback | `hosts.py:113-114` | Local node fallback hardcodes labels instead of using utility function |
| **Minor** | Labels stored as Set but serialized to List | `NodeStatus.labels` | Potential ordering inconsistency in API responses |

#### Specific Concerns

1. **Multi-homed node problem**: If a worker node has multiple network interfaces and one matches the head IP, it will be incorrectly labeled as "head"

2. **No label extensibility**: The system cannot represent nodes with different capabilities (e.g., nodes with more GPU memory, specific hardware)

3. **Role is runtime-derived**: If Ray head changes, node roles could change unexpectedly

#### Recommendations
1. Consider storing node role configuration in database rather than deriving from Ray state
2. Add custom labels support in node configuration
3. Use `get_default_node_labels()` consistently in all code paths

---

## 3. WFQScheduler Role-Aware Scheduling

### Assessment: WELL-DESIGNED

#### Strengths
- `FairSchedulingDecision` is a clean dataclass with clear role/labels requirements
- `matches_node()` method provides clear matching logic with proper docstring
- `filter_nodes_by_role()` and `select_best_node_for_decision()` are well-separated concerns
- Task attribute extraction with `getattr(task, 'target_role', None)` is a good duck-typing pattern
- Test coverage is comprehensive (18 test cases)

#### Issues Found

| Severity | Issue | Location | Impact |
|----------|-------|----------|--------|
| **Minor** | `select_best_node_for_decision` selects first idle node arbitrarily | `wfq_scheduler.py:831-833` | No load balancing across equivalent idle nodes |
| **Minor** | When `target_role=None`, tasks could be scheduled on head node | Scheduler decision flow | Head node may become overloaded with "any role" tasks |
| **Minor** | Reservation allocation failure could cause task requeue loop | `schedule_next()` line 555-559 | Max 10 attempts prevents infinite loop, but tasks are lost after exhaustion |

#### Design Observation
The WFQScheduler correctly separates scheduling decision from dispatch:
- Scheduler produces a `FairSchedulingDecision` with role/labels requirements
- Dispatch logic (external) must use `select_best_node_for_decision()` to find actual node

This is a good architectural choice as it keeps the scheduler focused on resource fairness while allowing dispatch flexibility.

#### Verdict
The role-aware scheduling implementation is well-architected. The `FairSchedulingDecision` class and related methods provide a solid foundation. The minor issues noted do not affect correctness but could be improved for better load distribution.

---

## Summary

| Component | Assessment | Risk Level |
|-----------|------------|------------|
| Dataset Model | Acceptable with minor issues | LOW |
| Node Role Determination | Needs improvement | MEDIUM |
| WFQScheduler Role-Aware | Well-designed | LOW |

### Critical Findings
None. No architectural flaws that would prevent Phase 3.5 from functioning correctly.

### Priority Recommendations
1. **Node Role**: Consider adding a persistent node configuration store (even a simple config file or DB table) to complement IP-based detection
2. **Labels**: Add support for custom node labels beyond the hardcoded defaults
3. **Scheduling**: When `target_role=None`, consider defaulting to "worker" only to avoid head node overload

### Files Reviewed
- `src/algo_studio/db/models/dataset.py` - Dataset DB model
- `src/algo_studio/api/dataset_models.py` - Dataset API models
- `src/algo_studio/core/ray_client.py` - Node role determination
- `src/algo_studio/core/scheduler/wfq_scheduler.py` - WFQScheduler with role-aware scheduling
- `src/algo_studio/api/routes/hosts.py` - Hosts API with node role display
- `tests/unit/scheduler/test_role_aware_scheduling.py` - Test coverage

---

**Review Complete. Ready for Phase 3.5 sign-off.**
