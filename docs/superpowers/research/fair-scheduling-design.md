# Phase 2.3 Fair Scheduling Algorithm Architecture

**Task:** Phase 2.3 - Fair Scheduling Algorithm Design
**Owner:** @ai-scheduling-engineer
**Date:** 2026-03-27
**Version:** v1.0

---

## 1. Design Objectives

### 1.1 Problem Statement

Current scheduling limitations:
1. **No multi-tenant fairness**: Tasks are scheduled purely on priority/arrival, ignoring per-tenant usage
2. **No bandwidth allocation**: High-volume tenants can monopolize cluster resources
3. **No reservation guarantees**: Critical workloads cannot guarantee resources
4. **Potential starvation**: Low-priority tenants may wait indefinitely

### 1.2 Design Goals

- Implement **Weighted Fair Queuing (WFQ)** for bandwidth allocation across tenants
- Support **guaranteed minimum resources** per tenant (reservation)
- Provide **priority overrides** for urgent tasks
- Integrate seamlessly with existing **QuotaManager** (RedisQuotaStore)

---

## 2. Algorithm Specification

### 2.1 Weighted Fair Queuing (WFQ) Core

```python
class WFQScheduler:
    """Weighted Fair Queuing Scheduler for multi-tenant resource allocation."""

    def __init__(self, quota_manager: QuotaManager):
        self.quota_manager = quota_manager
        self.tenant_queues: Dict[str, TenantQueue] = {}
        self.reservation_manager = ReservationManager(quota_manager)

    def schedule_next(self, available_resources: ResourceQuota) -> Optional[SchedulingDecision]:
        """
        Select next task using WFQ algorithm.

        WFQ Selection Formula:
        1. Calculate virtual finish time for each eligible task
        2. Select task with smallest virtual finish time
        3. Apply priority override if urgent task exists
        """
        eligible_tasks = self._get_eligible_tasks(available_resources)
        if not eligible_tasks:
            return None

        # Check for priority override (urgent tasks)
        urgent_task = self._get_highest_priority_urgent(eligible_tasks)
        if urgent_task:
            return self._create_decision(urgent_task, "priority_override")

        # WFQ selection based on virtual finish time
        scored_tasks = []
        for task in eligible_tasks:
            vft = self._calculate_virtual_finish_time(task)
            scored_tasks.append((vft, task))

        scored_tasks.sort(key=lambda x: x[0])
        selected_task = scored_tasks[0][1]

        return self._create_decision(selected_task, "wfq")
```

### 2.2 Virtual Finish Time Calculation

```python
def _calculate_virtual_finish_time(self, task: Task) -> float:
    """
    Calculate virtual finish time (VFT) for WFQ.

    VFT Formula:
    VFT = (weight_sum_so_far / tenant_weight) + (task_resources / tenant_allocation_share)

    Where:
    - weight_sum_so_far: cumulative weight of tasks already scheduled for tenant
    - tenant_weight: tenant's weight from quota configuration
    - task_resources: resource units required by task
    - tenant_allocation_share: tenant's fair share of cluster resources
    """
    tenant_id = task.tenant_id
    quota = self.quota_manager._get_effective_quota(task.user_id, task.team_id)

    if not quota:
        # No quota = default weight of 1.0
        weight = 1.0
        allocation_share = 1.0 / len(self.tenant_queues) if self.tenant_queues else 1.0
    else:
        weight = quota.get("weight", 1.0)
        # Allocation share based on guaranteed resources vs total cluster
        guaranteed_gpu = quota.get("gpu_count", 0)
        total_cluster_gpu = self._get_total_cluster_gpu()
        allocation_share = guaranteed_gpu / total_cluster_gpu if total_cluster_gpu > 0 else 0.0

    # Get cumulative weight for this tenant
    weight_sum = self.tenant_queues.get(tenant_id, TenantQueue()).cumulative_weight

    # Calculate resource units (normalized)
    task_resources = self._normalize_resources(task.requested_resources)

    # Virtual finish time
    vft = (weight_sum / weight) + (task_resources / max(allocation_share, 0.01))

    return vft

def _normalize_resources(self, resources: ResourceQuota) -> float:
    """Normalize resources to a single comparable unit."""
    return (
        resources.gpu_count * 10.0 +
        resources.cpu_cores * 1.0 +
        resources.gpu_memory_gb * 0.5 +
        resources.memory_gb * 0.1
    )
```

### 2.3 Reservation System

```python
class ReservationManager:
    """Manages resource reservations for guaranteed minimum allocation."""

    def __init__(self, quota_manager: QuotaManager):
        self.quota_manager = quota_manager
        self.reservations: Dict[str, ResourceReservation] = {}
        self.guaranteed_minimums: Dict[str, ResourceQuota] = {}

    def reserve(
        self,
        task_id: str,
        tenant_id: str,
        resources: ResourceQuota,
        duration_minutes: int
    ) -> Optional[ResourceReservation]:
        """
        Create a resource reservation for guaranteed allocation.

        Returns reservation if successful, None if resources unavailable.
        """
        quota = self._get_tenant_quota(tenant_id)
        if not quota:
            return None

        # Check if reservation would violate guaranteed minimums of other tenants
        if not self._can_reserve(tenant_id, resources):
            return None

        # Create reservation
        reservation = ResourceReservation(
            reservation_id=str(uuid.uuid4()),
            task_id=task_id,
            tenant_id=tenant_id,
            resources=resources,
            start_time=datetime.now(),
            duration_minutes=duration_minutes,
            status="active"
        )

        self.reservations[task_id] = reservation
        self.guaranteed_minimums[tenant_id] = resources

        # Allocate resources immediately
        self.quota_manager.allocate_resources(
            quota["quota_id"],
            resources
        )

        return reservation

    def release(self, task_id: str) -> bool:
        """Release a reservation and return resources."""
        reservation = self.reservations.pop(task_id, None)
        if not reservation:
            return False

        quota = self._get_tenant_quota(reservation.tenant_id)
        if quota:
            self.quota_manager.release_resources(
                quota["quota_id"],
                reservation.resources
            )

        return True

    def _can_reserve(self, tenant_id: str, resources: ResourceQuota) -> bool:
        """Check if reservation doesn't violate other tenants' guaranteed minimums."""
        # Get current guaranteed minimum allocations
        for tid, min_res in self.guaranteed_minimums.items():
            if tid == tenant_id:
                continue

            # Check cluster has enough after this reservation
            cluster_available = self._get_cluster_available_resources()
            if resources.gpu_count > cluster_available.gpu_count:
                return False

        return True
```

### 2.4 Priority Override Mechanism

```python
class PriorityOverrideHandler:
    """Handles priority overrides for urgent/critical tasks."""

    URGENT_PRIORITY_THRESHOLD = 90  # Priority >= 90 triggers override
    CRITICAL_DURATION_MINUTES = 30  # Override lasts for 30 minutes

    def __init__(self, quota_manager: QuotaManager):
        self.quota_manager = quota_manager
        self.active_overrides: Dict[str, PriorityOverride] = {}

    def check_override(self, task: Task) -> Optional[OverrideDecision]:
        """
        Check if task qualifies for priority override.

        Override Conditions (any met):
        1. Task priority >= URGENT_PRIORITY_THRESHOLD
        2. Task has explicit 'urgent' flag
        3. Team has 'bypass_fairness' permission
        4. System in maintenance mode (all tasks urgent)
        """
        # Check explicit urgent flag
        if getattr(task, 'is_urgent', False):
            return self._create_override(task, "explicit_urgent_flag")

        # Check priority threshold
        if task.priority >= self.URGENT_PRIORITY_THRESHOLD:
            return self._create_override(task, "high_priority")

        # Check team bypass permission
        quota = self.quota_manager._get_effective_quota(
            task.user_id, task.team_id
        )
        if quota and quota.get("bypass_fairness", False):
            return self._create_override(task, "team_bypass_permission")

        return None

    def _create_override(self, task: Task, reason: str) -> OverrideDecision:
        """Create an override decision for the task."""
        override = PriorityOverride(
            task_id=task.task_id,
            reason=reason,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=self.CRITICAL_DURATION_MINUTES)
        )
        self.active_overrides[task.task_id] = override

        return OverrideDecision(
            should_override=True,
            reason=reason,
            override_expires_at=override.expires_at
        )
```

---

## 3. Queue Management Data Structures

### 3.1 Tenant Queue

```python
@dataclass
class TenantQueue:
    """Per-tenant queue with WFQ state tracking."""

    tenant_id: str
    quota_id: str
    weight: float = 1.0
    guaranteed_minimum: ResourceQuota = None

    # Queue of pending tasks
    pending_tasks: List[Task] = field(default_factory=list)

    # WFQ state
    cumulative_weight: float = 0.0
    tasks_scheduled: int = 0

    # Usage tracking
    current_usage: ResourceQuota = field(default_factory=ResourceQuota)
    usage_history: List[UsageSnapshot] = field(default_factory=list)

    def enqueue(self, task: Task):
        """Add task to tenant queue."""
        self.pending_tasks.append(task)

    def dequeue(self) -> Optional[Task]:
        """Remove and return next task based on internal ordering."""
        if not self.pending_tasks:
            return None

        # Sort by priority within tenant queue
        self.pending_tasks.sort(key=lambda t: t.priority, reverse=True)
        return self.pending_tasks.pop(0)

    def get_wait_time(self, task: Task) -> float:
        """Calculate how long task has been waiting."""
        if task.created_at:
            return (datetime.now() - task.created_at).total_seconds() / 3600
        return 0.0

    def update_wfq_state(self, task_weight: float):
        """Update WFQ cumulative state after scheduling."""
        self.cumulative_weight += task_weight
        self.tasks_scheduled += 1
```

### 3.2 Global Scheduler Queue

```python
class GlobalSchedulerQueue:
    """
    Global scheduling queue with multi-level hierarchy.

    Structure:
    GLOBAL -> TENANT_QUEUES -> USER_TASKS
    """

    def __init__(self, quota_manager: QuotaManager):
        self.quota_manager = quota_manager
        self.tenant_queues: Dict[str, TenantQueue] = {}
        self.global_pending: List[Task] = []
        self.scheduled_count = 0

    def enqueue(self, task: Task) -> str:
        """
        Add task to appropriate queue.

        Returns:
            queue_path: "global", "tenant:{id}", or "user:{id}"
        """
        if not task.tenant_id:
            self.global_pending.append(task)
            return "global"

        if task.tenant_id not in self.tenant_queues:
            self._create_tenant_queue(task.tenant_id)

        self.tenant_queues[task.tenant_id].enqueue(task)
        return f"tenant:{task.tenant_id}"

    def dequeue(self, available_resources: ResourceQuota) -> Optional[Tuple[Task, str]]:
        """
        Select next task using WFQ.

        Returns:
            (task, queue_path) or None if no tasks
        """
        # Get all eligible tenant queues
        eligible_tenants = self._get_eligible_tenants(available_resources)

        if not eligible_tenants:
            # Fall back to global queue
            if self.global_pending:
                return (self.global_pending.pop(0), "global")
            return None

        # Select tenant using weighted round-robin
        selected_tenant = self._select_tenant_wrr(eligible_tenants)
        if not selected_tenant:
            return None

        # Get next task from selected tenant
        task = selected_tenant.dequeue()
        if task:
            return (task, f"tenant:{selected_tenant.tenant_id}")

        return None

    def _select_tenant_wrr(self, tenants: List[TenantQueue]) -> Optional[TenantQueue]:
        """
        Select tenant using Weighted Round-Robin.

        Selection based on ratio: tasks_scheduled / weight
        Lower ratio = more underserved = select this tenant
        """
        if not tenants:
            return None

        # Calculate (tasks_scheduled / weight) for each tenant
        tenant_ratios = []
        for tenant in tenants:
            ratio = tenant.tasks_scheduled / max(tenant.weight, 0.1)
            tenant_ratios.append((ratio, tenant))

        # Select tenant with lowest ratio (most underserved)
        tenant_ratios.sort(key=lambda x: x[0])
        return tenant_ratios[0][1]
```

### 3.3 Task Ordering Within Queue

```python
class TaskOrderer:
    """Determines task ordering within a single queue."""

    @staticmethod
    def order_tasks(tasks: List[Task]) -> List[Task]:
        """
        Order tasks by composite score.

        Score Components:
        1. Priority (40% weight) - explicit task priority
        2. Wait time (30% weight) - longer waiting = higher score
        3. Resource efficiency (20% weight) - smaller tasks first
        4. Age (10% weight) - older tasks get slight boost
        """
        now = datetime.now()
        scored_tasks = []

        for task in tasks:
            # Priority score (0-100 -> normalized)
            priority_score = task.priority * 0.4

            # Wait time score (0-1 per hour, capped at 10 hours)
            wait_hours = 0.0
            if task.created_at:
                wait_hours = min((now - task.created_at).total_seconds() / 3600, 10.0)
            wait_score = min(wait_hours * 0.1, 1.0) * 0.3

            # Resource efficiency score (smaller = better)
            resource_units = TaskOrderer._calc_resource_units(task)
            efficiency_score = max(0, 1.0 - resource_units / 100.0) * 0.2

            # Age score (slight boost for older tasks)
            age_score = min(wait_hours * 0.01, 0.1) * 0.1

            total_score = priority_score + wait_score + efficiency_score + age_score
            scored_tasks.append((total_score, task))

        scored_tasks.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored_tasks]

    @staticmethod
    def _calc_resource_units(task: Task) -> float:
        """Calculate total resource units for a task."""
        req = task.requested_resources
        return (
            req.gpu_count * 10 +
            req.cpu_cores * 1 +
            req.gpu_memory_gb * 0.5 +
            req.memory_gb * 0.1
        )
```

---

## 4. Integration with QuotaManager

### 4.1 Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      FairScheduler                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  WFQScheduler                                            │    │
│  │  - Manages global/task queues                           │    │
│  │  - Calculates virtual finish times                      │    │
│  │  - Selects next task via WFQ                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ReservationManager                                      │    │
│  │  - Creates/releases resource reservations                │    │
│  │  - Enforces guaranteed minimums                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  PriorityOverrideHandler                                 │    │
│  │  - Checks urgent task flags                              │    │
│  │  - Evaluates team bypass permissions                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
└──────────────────────────────┼──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      QuotaManager                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  check_quota() - Validate task against tenant quota     │    │
│  │  allocate_resources() - Reserve resources for task       │    │
│  │  release_resources() - Release when task completes       │    │
│  │  _get_effective_quota() - Get tenant's effective quota   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  QuotaStore (RedisQuotaStore)                           │    │
│  │  - Stores quota definitions and usage                   │    │
│  │  - Provides inheritance hierarchy                        │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Quota Extensions for Fair Scheduling

```python
# New quota fields for fair scheduling support
FAIR_SCHEDULING_QUOTA_FIELDS = {
    # Weight for WFQ algorithm (default: 1.0)
    "weight": 1.0,

    # Guaranteed minimum resources (reserved even when cluster is busy)
    "guaranteed_gpu_count": 0,
    "guaranteed_cpu_cores": 0,
    "guaranteed_memory_gb": 0.0,

    # Burst allowance (max resources when cluster is underutilized)
    "burst_gpu_count": 0,
    "burst_multiplier": 1.0,

    # Fairness bypass (team can bypass WFQ in emergencies)
    "bypass_fairness": False,

    # Priority boost for this tenant
    "priority_boost": 0,
}

# Example quota configuration
example_quota = {
    "quota_id": "team-ml-001",
    "scope": "team",
    "scope_id": "ml-platform-team",
    "name": "ML Platform Team",

    # Standard quota fields
    "cpu_cores": 16,
    "gpu_count": 4,
    "gpu_memory_gb": 64.0,
    "memory_gb": 128.0,
    "concurrent_tasks": 8,

    # Fair scheduling extensions
    "weight": 2.0,  # Higher weight = more bandwidth in WFQ
    "guaranteed_gpu_count": 2,  # Always available
    "guaranteed_memory_gb": 32.0,
    "burst_gpu_count": 4,  # Can use all 4 when available
    "bypass_fairness": False,
    "priority_boost": 0,
}
```

### 4.3 QuotaManager Integration Points

```python
class FairScheduler:
    """Fair scheduler with QuotaManager integration."""

    def __init__(self, quota_manager: QuotaManager):
        self.quota_manager = quota_manager
        self.queue = GlobalSchedulerQueue(quota_manager)
        self.reservation_manager = ReservationManager(quota_manager)
        self.priority_handler = PriorityOverrideHandler(quota_manager)

    def submit_task(self, task: Task) -> bool:
        """
        Submit task to fair scheduling queue.

        Integrates with QuotaManager for:
        1. Checking if task is allowed (quota check)
        2. Reserving resources if reservation requested
        """
        # Get effective quota for task
        quota = self.quota_manager._get_effective_quota(
            task.user_id, task.team_id
        )

        if not quota:
            # No quota defined - use default limits
            quota = self._get_default_quota()

        # Check if task can be submitted
        requested = self._task_to_resource_quota(task)
        allowed, effective_quota, usage, reasons = self.quota_manager.check_quota(
            task.user_id, task.team_id, requested
        )

        if not allowed:
            task.status = TaskStatus.REJECTED
            task.error_message = f"Quota exceeded: {'; '.join(reasons)}"
            return False

        # Enqueue task
        queue_path = self.queue.enqueue(task)
        task.scheduling_path = queue_path

        return True

    def schedule_next(self, available_resources: ResourceQuota) -> Optional[SchedulingDecision]:
        """
        Get next scheduling decision using WFQ.

        Flow:
        1. Check for priority overrides
        2. Apply WFQ selection
        3. Validate with QuotaManager
        4. Create reservation if needed
        """
        # Get next task from queue
        result = self.queue.dequeue(available_resources)
        if not result:
            return None

        task, queue_path = result

        # Check for priority override
        override = self.priority_handler.check_override(task)
        if override:
            decision = self._create_decision(task, queue_path, "priority_override")
            decision.override_reason = override.reason
            return decision

        # Validate with QuotaManager
        quota = self.quota_manager._get_effective_quota(task.user_id, task.team_id)
        if quota:
            requested = self._task_to_resource_quota(task)
            allowed, _, _, reasons = self.quota_manager.check_quota(
                task.user_id, task.team_id, requested
            )

            if not allowed:
                # Re-queue and try next task
                self.queue.enqueue(task)
                return self.schedule_next(available_resources)

            # Allocate resources
            self.quota_manager.allocate_resources(quota["quota_id"], requested)

        # Create scheduling decision
        decision = self._create_decision(task, queue_path, "wfq")
        decision.fair_share_applied = True
        decision.tenant_weight = quota.get("weight", 1.0) if quota else 1.0

        return decision

    def task_completed(self, task: Task):
        """Handle task completion - release resources."""
        quota = self.quota_manager._get_effective_quota(task.user_id, task.team_id)
        if quota:
            requested = self._task_to_resource_quota(task)
            self.quota_manager.release_resources(quota["quota_id"], requested)

        # Release reservation if any
        self.reservation_manager.release(task.task_id)
```

---

## 5. API for Scheduling Decisions

### 5.1 Scheduling API Endpoints

```python
# src/algo_studio/api/routes/scheduler.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/api/scheduler/fair", tags=["fair-scheduling"])

class FairSchedulingStatus(BaseModel):
    """Fair scheduling status response."""
    enabled: bool
    total_tenants: int
    total_pending_tasks: int
    active_reservations: int
    queue_stats: Dict[str, QueueStats]

class QueueStats(BaseModel):
    """Per-queue statistics."""
    tenant_id: str
    queue_length: int
    avg_wait_time_minutes: float
    current_usage_ratio: float

@router.get("/status", response_model=FairSchedulingStatus)
async def get_fair_scheduling_status():
    """
    Get current fair scheduling status.

    Returns:
        - Enabled status
        - Number of active tenants
        - Pending task counts
        - Active reservations
        - Per-queue statistics
    """
    return FairSchedulingStatus(
        enabled=True,
        total_tenants=len(scheduler.queue.tenant_queues),
        total_pending_tasks=sum(
            len(q.pending_tasks) for q in scheduler.queue.tenant_queues.values()
        ),
        active_reservations=len(scheduler.reservation_manager.reservations),
        queue_stats={...}
    )

@router.post("/tasks/{task_id}/priority-override")
async def request_priority_override(
    task_id: str,
    reason: str,
    duration_minutes: int = 30
):
    """
    Request priority override for a task.

    Requires:
    - Task exists and is pending
    - Caller has admin role or team bypass_fairness=True

    Returns:
        - Override decision
        - Expiration time
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.PENDING:
        raise HTTPException(status_code=400, detail="Task is not pending")

    override = scheduler.priority_handler.check_override(task)
    if not override:
        raise HTTPException(status_code=403, detail="Task does not qualify for override")

    return {
        "task_id": task_id,
        "override_granted": True,
        "reason": override.reason,
        "expires_at": override.override_expires_at.isoformat()
    }

@router.post("/reservations")
async def create_reservation(
    tenant_id: str,
    resources: ResourceQuota,
    duration_minutes: int
):
    """
    Create a resource reservation for guaranteed allocation.

    Args:
        tenant_id: Tenant requiring reservation
        resources: Resources to reserve
        duration_minutes: How long reservation should last

    Returns:
        - Reservation ID
        - Status
        - Resource details
    """
    reservation = scheduler.reservation_manager.reserve(
        task_id=None,  # No specific task yet
        tenant_id=tenant_id,
        resources=resources,
        duration_minutes=duration_minutes
    )

    if not reservation:
        raise HTTPException(status_code=409, detail="Insufficient resources for reservation")

    return {
        "reservation_id": reservation.reservation_id,
        "tenant_id": tenant_id,
        "resources": resources,
        "status": reservation.status,
        "expires_at": reservation.expires_at.isoformat()
    }

@router.delete("/reservations/{reservation_id}")
async def release_reservation(reservation_id: str):
    """Release a resource reservation."""
    success = scheduler.reservation_manager.release_by_id(reservation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return {"status": "released"}

@router.get("/queue/{tenant_id}")
async def get_tenant_queue(tenant_id: str):
    """
    Get detailed queue status for a tenant.

    Returns:
        - Queue length
        - Waiting tasks with details
        - Usage statistics
        - WFQ state
    """
    tenant_queue = scheduler.queue.tenant_queues.get(tenant_id)
    if not tenant_queue:
        raise HTTPException(status_code=404, detail="Tenant queue not found")

    return {
        "tenant_id": tenant_id,
        "queue_length": len(tenant_queue.pending_tasks),
        "tasks": [
            {
                "task_id": t.task_id,
                "priority": t.priority,
                "wait_time_hours": tenant_queue.get_wait_time(t),
                "requested_resources": t.requested_resources
            }
            for t in tenant_queue.pending_tasks
        ],
        "wfq_state": {
            "cumulative_weight": tenant_queue.cumulative_weight,
            "tasks_scheduled": tenant_queue.tasks_scheduled,
            "weight": tenant_queue.weight
        }
    }

@router.post("/config")
async def update_fair_scheduling_config(config: FairSchedulingConfig):
    """
    Update fair scheduling configuration.

    Args:
        - enabled: Toggle fair scheduling on/off
        - default_weight: Default tenant weight
        - wait_compensation_rate: Priority boost per hour of waiting
        - urgent_priority_threshold: Priority level for urgent tasks
    """
    scheduler.config.update(config.dict())
    return {"status": "updated", "config": scheduler.config}
```

### 5.2 Scheduling Decision Response

```python
@dataclass
class FairSchedulingDecision(SchedulingDecision):
    """Extended scheduling decision with fair scheduling details."""

    # Fair scheduling specific fields
    selection_method: str = "wfq"  # "wfq", "priority_override", "reservation"
    tenant_id: Optional[str] = None
    tenant_weight: float = 1.0
    virtual_finish_time: Optional[float] = None

    # Queue position info
    queue_position: Optional[int] = None
    estimated_wait_minutes: Optional[float] = None

    # Override info
    override_reason: Optional[str] = None

    # Fairness metrics
    fair_share_applied: bool = False
    usage_at_selection: Dict[str, float] = field(default_factory=dict)  # quota usage ratios
```

---

## 6. Configuration

### 6.1 Fair Scheduling Configuration

```python
# src/algo_studio/core/scheduler/config.py

FAIR_SCHEDULING_CONFIG = {
    # Enable/disable fair scheduling
    "enabled": True,

    # Default WFQ weight for new tenants
    "default_weight": 1.0,

    # Wait time compensation (priority boost per hour)
    "wait_compensation_rate": 0.05,  # 5% priority boost per hour
    "wait_compensation_cap": 0.5,     # Cap at 50% boost

    # Resource normalization weights
    "resource_weights": {
        "gpu": 10.0,
        "cpu": 1.0,
        "gpu_memory": 0.5,
        "memory": 0.1,
    },

    # Priority override settings
    "urgent_priority_threshold": 90,
    "override_duration_minutes": 30,

    # Reservation settings
    "reservation_timeout_minutes": 60,
    "guaranteed_minimum_enforcement": True,

    # Queue limits
    "max_queue_length_per_tenant": 1000,
    "max_global_queue_length": 5000,
    "queue_timeout_minutes": 120,

    # Starvation prevention
    "starvation_threshold_hours": 2,
    "min_tasks_per_tenant_after_starvation": 1,
}

@dataclass
class FairSchedulingConfig:
    """Configuration for fair scheduling."""
    enabled: bool = True
    default_weight: float = 1.0
    wait_compensation_rate: float = 0.05
    wait_compensation_cap: float = 0.5
    urgent_priority_threshold: int = 90
    override_duration_minutes: int = 30
    reservation_timeout_minutes: int = 60
    starvation_threshold_hours: float = 2.0
```

---

## 7. Implementation Tasks (Week 5-6)

| Task | Days | Deliverable | Acceptance Criteria |
|------|------|-------------|---------------------|
| Implement TenantQueue and GlobalSchedulerQueue | 1.5 | `tenant_queue.py` | Queue operations correct, WFQ state tracking |
| Implement WFQScheduler core algorithm | 1.5 | `wfq_scheduler.py` | VFT calculation correct, selection works |
| Implement ReservationManager | 1.0 | `reservation_manager.py` | Reservations create/release correctly |
| Implement PriorityOverrideHandler | 0.5 | `priority_handler.py` | Override detection works |
| Integrate with QuotaManager | 1.0 | `fair_scheduler.py` | Quota checks/enforcement in scheduling |
| Add fair scheduling endpoints to API | 0.5 | `routes/scheduler.py` | API returns correct status |
| Unit tests | 1.0 | `test_fair_scheduler.py` | >80% coverage |
| Integration test | 0.5 | `test_fair_scheduler_integration.py` | End-to-end test passes |

---

## 8. Acceptance Criteria

- [ ] WFQ selects tasks based on virtual finish time
- [ ] Priority override triggers for urgent tasks (priority >= 90)
- [ ] Reservations guarantee minimum resources for tenants
- [ ] QuotaManager integration validates resource allocation
- [ ] Per-tenant queues track WFQ state correctly
- [ ] Starvation prevention ensures no task waits > 2 hours
- [ ] API returns accurate fair scheduling status
- [ ] Unit test coverage > 80%

---

## 10. Implementation Notes (2026-03-27 Review)

### 已确认点
- ✅ VFT 公式已确认: `VFT = (weight_sum_so_far / tenant_weight) + (task_resources / tenant_allocation_share)`
- ✅ QuotaManager 集成点已验证可用
- ✅ 无阻塞依赖

### 需验证项 (Implementation 时验证)
1. **VFT 公式行为**: 当 `allocation_share` 很小时 VFT 会很大，需在实现时确认是否符合预期
2. **资源归一化权重**: GPU=10.0, CPU=1.0 应提取到配置中便于调优
3. **饥饿预防**: 当前 2 小时阈值可考虑渐进式优先级提升
4. **并发安全**: `GlobalSchedulerQueue.enqueue/dequeue` 需使用 `asyncio.Lock` 保护
5. **reservation_timeout**: `ReservationManager` 需实现定期清理超时 reservation 的机制

### 建议验收测试场景
1. 多 tenant 并发提交时，WFQ 正确分配带宽
2. 高优先级任务到达时，立即抢占低优先级任务

---

## 9. Related Documents

| Document | Location |
|----------|----------|
| QuotaManager Design | `docs/superpowers/design/quota-manager-design.md` |
| Fair Scheduling v1 | `docs/superpowers/design/fair-scheduling-design.md` |
| Platform Agentic Report | `docs/superpowers/research/platform-agentic-report.md` |
| Phase 2 Schedule | `docs/superpowers/schedule/phase2-schedule.md` |

---

**Status:** Phase 2.3 Design Complete
**Next:** Implementation Week 5-6
