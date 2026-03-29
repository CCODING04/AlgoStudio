"""
WFQScheduler - Weighted Fair Queuing Scheduler for multi-tenant resource allocation.

Part of the fair scheduling algorithm implementation.

VFT Formula: VFT = (weight_sum_so_far / tenant_weight) + (task_resources / tenant_allocation_share)
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import uuid

from algo_studio.core.task import Task, TaskStatus
from algo_studio.core.quota.manager import QuotaManager
from algo_studio.core.quota.store import ResourceQuota
from algo_studio.core.scheduler.tenant_queue import TenantQueue
from algo_studio.core.scheduler.global_queue import GlobalSchedulerQueue


# Resource normalization weights
RESOURCE_WEIGHTS = {
    "gpu": 10.0,
    "cpu": 1.0,
    "gpu_memory": 0.5,
    "memory": 0.1,
}

# Default cluster GPU count (used when not specified)
DEFAULT_CLUSTER_GPU = 1


@dataclass
class FairSchedulingDecision:
    """Scheduling decision with fair scheduling details."""

    decision_id: str
    task: Task
    selection_method: str = "wfq"  # "wfq", "priority_override", "reservation"

    # Queue info
    queue_path: str = ""
    queue_position: Optional[int] = None
    estimated_wait_minutes: Optional[float] = None

    # Tenant info
    tenant_id: Optional[str] = None
    tenant_weight: float = 1.0
    virtual_finish_time: Optional[float] = None

    # Override info
    override_reason: Optional[str] = None

    # Role-aware scheduling
    target_role: Optional[str] = None  # "head" | "worker" | None (any)
    target_labels: List[str] = field(default_factory=list)  # Required labels

    # Fairness metrics
    fair_share_applied: bool = False
    usage_at_selection: Dict[str, float] = field(default_factory=dict)

    # Timestamp
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def decision_id_short(self) -> str:
        """Get shortened decision ID."""
        return self.decision_id[:8]

    def requires_head_node(self) -> bool:
        """Check if this decision requires a head node."""
        return self.target_role == "head"

    def requires_worker_node(self) -> bool:
        """Check if this decision requires a worker node."""
        return self.target_role == "worker"

    def has_label_requirements(self) -> bool:
        """Check if this decision has label requirements."""
        return len(self.target_labels) > 0

    def matches_node(self, node_role: str, node_labels: List[str]) -> bool:
        """Check if a node matches this scheduling decision's requirements.

        Args:
            node_role: Role of the node ("head" or "worker")
            node_labels: Labels of the node

        Returns:
            True if node matches requirements, False otherwise
        """
        # Check role requirement
        if self.target_role is not None and self.target_role != node_role:
            return False

        # Check label requirements (all required labels must be present)
        if self.target_labels:
            node_labels_set = set(node_labels)
            for label in self.target_labels:
                if label not in node_labels_set:
                    return False

        return True


class PriorityOverride:
    """Represents an active priority override."""

    def __init__(
        self,
        task_id: str,
        reason: str,
        created_at: datetime,
        expires_at: datetime,
    ):
        self.task_id = task_id
        self.reason = reason
        self.created_at = created_at
        self.expires_at = expires_at

    @property
    def is_expired(self) -> bool:
        """Check if override has expired."""
        return datetime.now() > self.expires_at


class ReservationManager:
    """Manages resource reservations for guaranteed minimum allocation."""

    URGENT_PRIORITY_THRESHOLD = 90
    CRITICAL_DURATION_MINUTES = 30

    def __init__(self, quota_manager: QuotaManager):
        """Initialize reservation manager.

        Args:
            quota_manager: QuotaManager instance
        """
        self.quota_manager = quota_manager
        self.reservations: Dict[str, Dict[str, Any]] = {}
        self.guaranteed_minimums: Dict[str, Dict[str, Any]] = {}
        self.active_overrides: Dict[str, PriorityOverride] = {}
        self._lock = asyncio.Lock()

    async def reserve(
        self,
        task_id: str,
        tenant_id: str,
        resources: ResourceQuota,
        duration_minutes: int = 60,
    ) -> Optional[Dict[str, Any]]:
        """Create a resource reservation for guaranteed allocation.

        Args:
            task_id: Task ID (or None for general reservation)
            tenant_id: Tenant requiring reservation
            resources: Resources to reserve
            duration_minutes: Reservation duration

        Returns:
            Reservation dict if successful, None if resources unavailable
        """
        async with self._lock:
            quota = self._get_tenant_quota(tenant_id)
            if not quota:
                return None

            # Check if reservation would violate guaranteed minimums
            if not self._can_reserve(tenant_id, resources):
                return None

            # Create reservation
            reservation = {
                "reservation_id": str(uuid.uuid4()),
                "task_id": task_id,
                "tenant_id": tenant_id,
                "resources": {
                    "gpu_count": resources.gpu_count,
                    "cpu_cores": resources.cpu_cores,
                    "gpu_memory_gb": resources.gpu_memory_gb,
                    "memory_gb": resources.memory_gb,
                },
                "start_time": datetime.now(),
                "duration_minutes": duration_minutes,
                "expires_at": datetime.now() + timedelta(minutes=duration_minutes),
                "status": "active",
            }

            self.reservations[reservation["reservation_id"]] = reservation
            self.guaranteed_minimums[tenant_id] = resources

            # Allocate resources
            try:
                self.quota_manager.allocate_resources(
                    quota["quota_id"],
                    resources,
                )
            except Exception:
                # Rollback on failure
                del self.reservations[reservation["reservation_id"]]
                return None

            return reservation

    async def release(self, task_id: str) -> bool:
        """Release a reservation and return resources.

        Args:
            task_id: Task ID to release reservation for

        Returns:
            True if release succeeded
        """
        async with self._lock:
            # Find reservation by task_id
            reservation = None
            reservation_id = None
            for rid, res in self.reservations.items():
                if res["task_id"] == task_id:
                    reservation = res
                    reservation_id = rid
                    break

            if not reservation:
                return False

            # Release resources
            quota = self._get_tenant_quota(reservation["tenant_id"])
            if quota:
                resources = ResourceQuota(
                    gpu_count=reservation["resources"]["gpu_count"],
                    cpu_cores=reservation["resources"]["cpu_cores"],
                    gpu_memory_gb=reservation["resources"]["gpu_memory_gb"],
                    memory_gb=reservation["resources"]["memory_gb"],
                )
                try:
                    self.quota_manager.release_resources(quota["quota_id"], resources)
                except Exception:
                    pass

            del self.reservations[reservation_id]
            return True

    async def release_by_id(self, reservation_id: str) -> bool:
        """Release a reservation by ID.

        Args:
            reservation_id: Reservation ID

        Returns:
            True if release succeeded
        """
        async with self._lock:
            reservation = self.reservations.get(reservation_id)
            if not reservation:
                return False

            # Release resources
            quota = self._get_tenant_quota(reservation["tenant_id"])
            if quota:
                resources = ResourceQuota(
                    gpu_count=reservation["resources"]["gpu_count"],
                    cpu_cores=reservation["resources"]["cpu_cores"],
                    gpu_memory_gb=reservation["resources"]["gpu_memory_gb"],
                    memory_gb=reservation["resources"]["memory_gb"],
                )
                try:
                    self.quota_manager.release_resources(quota["quota_id"], resources)
                except Exception:
                    pass

            del self.reservations[reservation_id]
            return True

    def _can_reserve(self, tenant_id: str, resources: ResourceQuota) -> bool:
        """Check if reservation doesn't violate other tenants' guaranteed minimums.

        Args:
            tenant_id: Tenant requesting reservation
            resources: Resources to reserve

        Returns:
            True if reservation is allowed
        """
        # Check cluster has enough after this reservation
        # This is a simplified check - in production would check actual cluster capacity
        for tid, min_res in self.guaranteed_minimums.items():
            if tid == tenant_id:
                continue
            if resources.gpu_count > min_res.gpu_count:
                return False
        return True

    def _get_tenant_quota(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get quota for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Quota dict or None
        """
        return self.quota_manager._get_effective_quota(
            user_id=tenant_id,
            team_id=None,
        )

    def check_override(self, task: Task) -> Optional[PriorityOverride]:
        """Check if task qualifies for priority override.

        Override Conditions (any met):
        1. Task priority >= URGENT_PRIORITY_THRESHOLD
        2. Task has explicit 'is_urgent' flag
        3. Team has 'bypass_fairness' permission

        Args:
            task: Task to check

        Returns:
            PriorityOverride if qualified, None otherwise
        """
        # Check explicit urgent flag
        if getattr(task, 'is_urgent', False):
            return self._create_override(task, "explicit_urgent_flag")

        # Check priority threshold
        priority = getattr(task, 'priority', 0)
        if priority >= self.URGENT_PRIORITY_THRESHOLD:
            return self._create_override(task, "high_priority")

        # Check team bypass permission
        quota = self._get_tenant_quota(task.tenant_id or "")
        if quota and quota.get("bypass_fairness", False):
            return self._create_override(task, "team_bypass_permission")

        return None

    def _create_override(self, task: Task, reason: str) -> PriorityOverride:
        """Create an override for the task.

        Args:
            task: Task to override
            reason: Override reason

        Returns:
            PriorityOverride instance
        """
        override = PriorityOverride(
            task_id=task.task_id,
            reason=reason,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=self.CRITICAL_DURATION_MINUTES),
        )
        self.active_overrides[task.task_id] = override
        return override

    @property
    def active_reservation_count(self) -> int:
        """Get count of active reservations."""
        return len(self.reservations)


class WFQScheduler:
    """
    Weighted Fair Queuing Scheduler for multi-tenant resource allocation.

    Implements fair bandwidth allocation across tenants using virtual finish time (VFT).

    VFT Formula: VFT = (weight_sum_so_far / tenant_weight) + (task_resources / tenant_allocation_share)

    Performance optimizations:
    - Caches effective quota lookups within a scheduling cycle to avoid redundant DB queries
    - Uses heap-based priority queue for O(log n) task dequeue instead of O(n log n) sort
    - Caches WFQ ratios per tenant, invalidated only on scheduling events
    """

    def __init__(
        self,
        quota_manager: QuotaManager,
        total_cluster_gpu: int = DEFAULT_CLUSTER_GPU,
    ):
        """Initialize WFQ Scheduler.

        Args:
            quota_manager: QuotaManager instance for quota lookups
            total_cluster_gpu: Total GPUs in cluster for allocation share calculation
        """
        self.quota_manager = quota_manager
        self.total_cluster_gpu = total_cluster_gpu

        # Queue management
        self.queue = GlobalSchedulerQueue(quota_manager)

        # Support components
        self.reservation_manager = ReservationManager(quota_manager)

        # Scheduling config
        self._lock = asyncio.Lock()
        self._scheduled_count = 0

        # Per-scheduling-cycle cache to avoid redundant quota lookups
        # Key: (user_id, team_id) -> quota dict
        self._quota_cache: Dict[Tuple[str, Optional[str]], Dict[str, Any]] = {}
        # Cache validity flag (reset each scheduling cycle)
        self._quota_cache_valid = False

    def _get_cached_quota(self, user_id: str, team_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """Get effective quota with caching to avoid redundant lookups.

        Args:
            user_id: User identifier
            team_id: Optional team identifier

        Returns:
            Effective quota dict or None
        """
        cache_key = (user_id, team_id)
        if self._quota_cache_valid and cache_key in self._quota_cache:
            return self._quota_cache[cache_key]

        quota = self.quota_manager._get_effective_quota(user_id, team_id)
        self._quota_cache[cache_key] = quota
        return quota

    def _invalidate_quota_cache(self) -> None:
        """Invalidate quota cache at the start of each scheduling cycle."""
        self._quota_cache.clear()
        self._quota_cache_valid = False

    async def submit_task(self, task: Task) -> Tuple[bool, str]:
        """Submit task to fair scheduling queue.

        Args:
            task: Task to submit

        Returns:
            (success, queue_path) tuple
        """
        user_id = task.user_id if hasattr(task, 'user_id') else ""
        team_id = task.team_id if hasattr(task, 'team_id') else None

        # Get effective quota for task (use cache if available)
        quota = self._get_cached_quota(user_id, team_id)

        if not quota:
            # No quota defined - use default limits
            pass

        # Check if task can be submitted (quota check)
        requested = getattr(task, 'requested_resources', None)
        if requested is None:
            # Default resources based on task type
            requested = self._get_default_resources(task)

        allowed, effective_quota, usage, reasons = self.quota_manager.check_quota(
            user_id,
            team_id,
            requested,
        )

        if not allowed:
            # Task rejected
            if hasattr(task, 'status'):
                task.status = TaskStatus.FAILED
            if hasattr(task, 'error'):
                task.error = f"Quota exceeded: {'; '.join(reasons)}"
            return False, f"rejected: {'; '.join(reasons)}"

        # Enqueue task
        queue_path = await self.queue.enqueue(task)
        return True, queue_path

    async def schedule_next(
        self, available_resources: ResourceQuota,
        max_requeue_attempts: int = 10
    ) -> Optional[FairSchedulingDecision]:
        """Select next task using WFQ algorithm.

        Flow:
        1. Invalidate quota cache (new scheduling cycle)
        2. Check for priority overrides
        3. Apply WFQ selection
        4. Validate with QuotaManager
        5. Create reservation if needed

        Performance optimizations:
        - Single lock acquisition for queue operations
        - Cached quota lookups avoid redundant DB queries
        - Uses cached WFQ ratios from TenantQueue
        - Iterative requeue pattern (instead of recursive) to avoid stack overflow

        Args:
            available_resources: Available cluster resources
            max_requeue_attempts: Maximum number of requeue attempts before giving up

        Returns:
            FairSchedulingDecision if a task was selected, None otherwise
        """
        # Iterative requeue handling (replaces recursive pattern to avoid stack overflow)
        requeue_count = 0
        while requeue_count < max_requeue_attempts:
            # Get next task from queue (lock held for queue operation and cache invalidation)
            async with self._lock:
                # Start new scheduling cycle - invalidate caches under lock
                self._invalidate_quota_cache()

                result = await self.queue.dequeue(available_resources)
                if not result:
                    return None

                task, queue_path = result

            # Now do quota operations outside the lock (no lock needed for read-only quota checks)
            user_id = task.user_id if hasattr(task, 'user_id') else ""
            team_id = task.team_id if hasattr(task, 'team_id') else None

            # Check for priority override (uses cached quota internally)
            override = self.reservation_manager.check_override(task)
            if override:
                decision = self._create_decision(
                    task=task,
                    queue_path=queue_path,
                    method="priority_override",
                    override_reason=override.reason,
                )
                async with self._lock:
                    self._scheduled_count += 1
                return decision

            # Get quota using cache
            quota = self._get_cached_quota(user_id, team_id)

            if quota:
                requested = getattr(task, 'requested_resources', None)
                if requested is None:
                    requested = self._get_default_resources(task)

                allowed, _, _, reasons = self.quota_manager.check_quota(
                    user_id,
                    team_id,
                    requested,
                )

                if not allowed:
                    # Re-queue and try next task (need lock again)
                    async with self._lock:
                        await self.queue.requeue(task)
                    requeue_count += 1
                    continue  # Iterative loop instead of recursion

                # Allocate resources
                try:
                    self.quota_manager.allocate_resources(quota["quota_id"], requested)
                except Exception:
                    async with self._lock:
                        await self.queue.requeue(task)
                    requeue_count += 1
                    continue  # Iterative loop instead of recursion

            # Calculate VFT for the decision
            vft = self._calculate_virtual_finish_time(task, quota)

            # Create decision
            decision = self._create_decision(
                task=task,
                queue_path=queue_path,
                method="wfq",
                tenant_weight=quota.get("weight", 1.0) if quota else 1.0,
                virtual_finish_time=vft,
            )
            decision.fair_share_applied = True

            async with self._lock:
                self._scheduled_count += 1

            return decision

        # Exceeded max requeue attempts - no viable task found
        return None

    def _calculate_virtual_finish_time(
        self, task: Task, quota: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate virtual finish time (VFT) for WFQ.

        VFT Formula:
            VFT = (weight_sum_so_far / tenant_weight) + (task_resources / tenant_allocation_share)

        Where:
            - weight_sum_so_far: cumulative weight of tasks already scheduled for tenant
            - tenant_weight: tenant's weight from quota configuration
            - task_resources: resource units required by task
            - tenant_allocation_share: tenant's fair share of cluster resources

        Args:
            task: Task to calculate VFT for
            quota: Effective quota for the task's tenant

        Returns:
            Virtual finish time (lower = scheduled sooner)
        """
        tenant_id = task.tenant_id or "global"

        # Get tenant weight
        if quota:
            weight = quota.get("weight", 1.0)
            # Allocation share based on guaranteed resources vs total cluster
            guaranteed_gpu = quota.get("guaranteed_gpu_count", 0) or quota.get("gpu_count", 0)
            allocation_share = guaranteed_gpu / max(self.total_cluster_gpu, 1)
        else:
            weight = 1.0
            allocation_share = 1.0 / max(len(self.queue.tenant_queues), 1)

        # Get cumulative weight for this tenant
        tenant_queue = self.queue.get_tenant_queue(tenant_id)
        weight_sum = tenant_queue.cumulative_weight if tenant_queue else 0.0

        # Calculate resource units
        if hasattr(task, 'requested_resources') and task.requested_resources is not None:
            task_resources = self._normalize_resources(task.requested_resources)
        else:
            task_resources = self._normalize_resources(self._get_default_resources(task))

        # Virtual finish time
        # Avoid division by zero by using max(allocation_share, 0.01)
        vft = (weight_sum / max(weight, 0.1)) + (task_resources / max(allocation_share, 0.01))

        return vft

    def _normalize_resources(self, resources: ResourceQuota) -> float:
        """Normalize resources to a single comparable unit.

        Uses weighted sum:
            gpu * 10.0 + cpu * 1.0 + gpu_memory * 0.5 + memory * 0.1

        Args:
            resources: ResourceQuota to normalize

        Returns:
            Normalized resource value
        """
        return (
            resources.gpu_count * RESOURCE_WEIGHTS["gpu"] +
            resources.cpu_cores * RESOURCE_WEIGHTS["cpu"] +
            resources.gpu_memory_gb * RESOURCE_WEIGHTS["gpu_memory"] +
            resources.memory_gb * RESOURCE_WEIGHTS["memory"]
        )

    def _get_default_resources(self, task: Task) -> ResourceQuota:
        """Get default resource requirements for a task type.

        Args:
            task: Task to get defaults for

        Returns:
            ResourceQuota with default values
        """
        task_type = getattr(task, 'task_type', None)

        if task_type and hasattr(task_type, 'value'):
            task_type = task_type.value

        if task_type == "train":
            return ResourceQuota(
                cpu_cores=4,
                gpu_count=1,
                gpu_memory_gb=8.0,
                memory_gb=16.0,
                concurrent_tasks=1,
            )
        elif task_type == "infer":
            return ResourceQuota(
                cpu_cores=1,
                gpu_count=0,
                memory_gb=4.0,
                concurrent_tasks=1,
            )
        elif task_type == "verify":
            return ResourceQuota(
                cpu_cores=1,
                gpu_count=0,
                memory_gb=2.0,
                concurrent_tasks=1,
            )
        else:
            return ResourceQuota(concurrent_tasks=1)

    def _create_decision(
        self,
        task: Task,
        queue_path: str,
        method: str,
        tenant_weight: float = 1.0,
        virtual_finish_time: Optional[float] = None,
        override_reason: Optional[str] = None,
        target_role: Optional[str] = None,
        target_labels: Optional[List[str]] = None,
    ) -> FairSchedulingDecision:
        """Create a fair scheduling decision.

        Args:
            task: Selected task
            queue_path: Queue path (global/tenant:{id})
            method: Selection method (wfq/priority_override/reservation)
            tenant_weight: Tenant weight
            virtual_finish_time: Calculated VFT
            override_reason: Reason for override (if priority_override)
            target_role: Required node role ("head" or "worker"), None for any
            target_labels: Required node labels, None or empty for no requirements

        Returns:
            FairSchedulingDecision instance
        """
        # Extract role/labels from task if not explicitly provided
        if target_role is None:
            target_role = getattr(task, 'target_role', None)
        if target_labels is None:
            target_labels = getattr(task, 'target_labels', []) or []

        decision = FairSchedulingDecision(
            decision_id=str(uuid.uuid4()),
            task=task,
            selection_method=method,
            queue_path=queue_path,
            tenant_id=task.tenant_id,
            tenant_weight=tenant_weight,
            virtual_finish_time=virtual_finish_time,
            override_reason=override_reason,
            target_role=target_role,
            target_labels=target_labels,
        )

        return decision

    async def task_completed(self, task: Task) -> None:
        """Handle task completion - release resources.

        Args:
            task: Completed task
        """
        # Release quota resources
        quota = self.quota_manager._get_effective_quota(
            task.user_id if hasattr(task, 'user_id') else "",
            task.team_id if hasattr(task, 'team_id') else None,
        )

        if quota:
            requested = getattr(task, 'requested_resources', None)
            if requested is None:
                requested = self._get_default_resources(task)

            try:
                self.quota_manager.release_resources(quota["quota_id"], requested)
            except Exception:
                pass

        # Release reservation if any
        await self.reservation_manager.release(task.task_id)

    def filter_nodes_by_role(
        self,
        nodes: List[Any],
        target_role: Optional[str] = None,
        target_labels: Optional[List[str]] = None,
    ) -> List[Any]:
        """Filter nodes by role requirements from scheduling decision.

        This helper method can be used by dispatch logic to filter nodes
        based on role/labels requirements from the scheduling decision.

        Args:
            nodes: List of NodeStatus or similar node objects with role/labels attributes
            target_role: Required role ("head" or "worker"), None for any
            target_labels: Required labels, None or empty for no requirements

        Returns:
            Filtered list of nodes matching the requirements
        """
        if not nodes:
            return []

        # If no role or label requirements, return all nodes
        if target_role is None and (not target_labels or len(target_labels) == 0):
            return nodes

        filtered = []
        for node in nodes:
            # Check role requirement
            node_role = getattr(node, 'role', None) or "worker"
            if target_role is not None and node_role != target_role:
                continue

            # Check label requirements
            if target_labels:
                node_labels = set(getattr(node, 'labels', []) or [])
                labels_match = all(label in node_labels for label in target_labels)
                if not labels_match:
                    continue

            filtered.append(node)

        return filtered

    def select_best_node_for_decision(
        self,
        nodes: List[Any],
        decision: FairSchedulingDecision,
    ) -> Optional[Any]:
        """Select the best matching node for a scheduling decision.

        Args:
            nodes: List of available NodeStatus objects
            decision: FairSchedulingDecision with role/labels requirements

        Returns:
            Best matching node, or None if no suitable node found
        """
        # Filter nodes by decision requirements
        matching_nodes = self.filter_nodes_by_role(
            nodes,
            target_role=decision.target_role,
            target_labels=decision.target_labels,
        )

        if not matching_nodes:
            return None

        # Prefer head nodes for head-required tasks (head can run tasks when explicitly requested)
        # Otherwise, select based on availability (idle nodes first)
        idle_nodes = [n for n in matching_nodes if getattr(n, 'status', None) == "idle"]
        if idle_nodes:
            return idle_nodes[0]

        return matching_nodes[0] if matching_nodes else None

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics.

        Returns:
            Dict with scheduler stats
        """
        return {
            "scheduled_count": self._scheduled_count,
            "queue_stats": self.queue.get_queue_stats(),
            "active_reservations": self.reservation_manager.active_reservation_count,
        }
