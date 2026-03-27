"""
GlobalSchedulerQueue - Global scheduling queue with multi-level hierarchy.

Structure:
    GLOBAL -> TENANT_QUEUES -> USER_TASKS

Part of the fair scheduling algorithm implementation.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from algo_studio.core.task import Task
from algo_studio.core.quota.manager import QuotaManager
from algo_studio.core.quota.store import ResourceQuota
from algo_studio.core.scheduler.tenant_queue import TenantQueue


class GlobalSchedulerQueue:
    """
    Global scheduling queue with multi-level hierarchy.

    Structure:
        GLOBAL -> TENANT_QUEUES -> USER_TASKS

    This queue implements WFQ (Weighted Fair Queuing) at the tenant level
    and priority ordering within each tenant queue.
    """

    def __init__(self, quota_manager: QuotaManager):
        """Initialize global scheduler queue.

        Args:
            quota_manager: QuotaManager instance for quota lookups
        """
        self.quota_manager = quota_manager
        self.tenant_queues: Dict[str, TenantQueue] = {}
        self.global_pending: List[Task] = []  # Tasks without tenant_id
        self.scheduled_count: int = 0

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def enqueue(self, task: Task) -> str:
        """Add task to appropriate queue.

        Tasks are routed to:
        - Global queue if no tenant_id
        - Tenant-specific queue if tenant_id exists

        Args:
            task: Task to enqueue

        Returns:
            Queue path: "global", "tenant:{tenant_id}", or "user:{user_id}"
        """
        async with self._lock:
            if not task.tenant_id:
                self.global_pending.append(task)
                return "global"

            if task.tenant_id not in self.tenant_queues:
                self._create_tenant_queue(task.tenant_id)

            self.tenant_queues[task.tenant_id].enqueue(task)
            return f"tenant:{task.tenant_id}"

    def _create_tenant_queue(self, tenant_id: str) -> TenantQueue:
        """Create a new tenant queue.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Created TenantQueue
        """
        # Try to get quota to set initial weight
        # Use tenant_id as team_id since quotas are created with scope=TEAM
        quota = self.quota_manager._get_effective_quota(
            user_id=tenant_id,
            team_id=tenant_id
        )

        weight = 1.0
        quota_id = ""
        guaranteed_minimum = None

        if quota:
            weight = quota.get("weight", 1.0)
            quota_id = quota.get("quota_id", "")
            guaranteed_minimum = {
                "gpu_count": quota.get("guaranteed_gpu_count", 0),
                "cpu_cores": quota.get("guaranteed_cpu_cores", 0),
                "memory_gb": quota.get("guaranteed_memory_gb", 0.0),
            }

        tenant_queue = TenantQueue(
            tenant_id=tenant_id,
            quota_id=quota_id,
            weight=weight,
            guaranteed_minimum=guaranteed_minimum,
        )
        self.tenant_queues[tenant_id] = tenant_queue
        return tenant_queue

    async def dequeue(self, available_resources: ResourceQuota) -> Optional[Tuple[Task, str]]:
        """Select next task using WFQ (Weighted Fair Queuing).

        Selection flow:
        1. Get all eligible tenant queues
        2. Select tenant using Weighted Round-Robin (lowest ratio = most underserved)
        3. Get next task from selected tenant (ordered by priority)

        Args:
            available_resources: Available cluster resources

        Returns:
            (task, queue_path) tuple, or None if no tasks available
        """
        async with self._lock:
            # Get all eligible tenant queues
            eligible_tenants = self._get_eligible_tenants(available_resources)

            if not eligible_tenants:
                # Fall back to global queue
                if self.global_pending:
                    return (self.global_pending.pop(0), "global")
                return None

            # Select tenant using Weighted Round-Robin
            selected_tenant = self._select_tenant_wrr(eligible_tenants)
            if not selected_tenant:
                return None

            # Get next task from selected tenant
            task = selected_tenant.dequeue()
            if task:
                # Update WFQ state with task weight based on priority
                task_weight = 0.5 + (task.priority / 100)
                selected_tenant.update_wfq_state(task_weight)
                self.scheduled_count += 1
                return (task, f"tenant:{selected_tenant.tenant_id}")

            return None

    def _get_eligible_tenants(self, available_resources: ResourceQuota) -> List[TenantQueue]:
        """Get list of tenant queues that are eligible for scheduling.

        A tenant is eligible if:
        1. Their queue is not empty
        2. Their guaranteed minimums can be satisfied (if defined)

        Args:
            available_resources: Available cluster resources

        Returns:
            List of eligible TenantQueue instances
        """
        eligible = []

        for tenant_queue in self.tenant_queues.values():
            if tenant_queue.is_empty():
                continue

            # Check if guaranteed minimums can be satisfied
            if tenant_queue.guaranteed_minimum:
                min_gpu = tenant_queue.guaranteed_minimum.get("gpu_count", 0)
                if available_resources.gpu_count < min_gpu:
                    continue

            eligible.append(tenant_queue)

        return eligible

    def _select_tenant_wrr(self, tenants: List[TenantQueue]) -> Optional[TenantQueue]:
        """Select tenant using Weighted Round-Robin.

        Selection based on ratio: tasks_scheduled / weight
        Lower ratio = more underserved = select this tenant

        Uses cached ratios from TenantQueue for O(1) lookup instead of recalculating.

        Args:
            tenants: List of eligible TenantQueue instances

        Returns:
            Selected TenantQueue, or None if list is empty
        """
        if not tenants:
            return None

        # Find tenant with lowest ratio using cached ratios (O(n) instead of recalculating)
        # Lower ratio means more underserved
        selected = None
        lowest_ratio = float('inf')

        for tenant in tenants:
            ratio = tenant.wrr_ratio  # Uses cached value from TenantQueue
            if ratio < lowest_ratio:
                lowest_ratio = ratio
                selected = tenant

        return selected

    async def requeue(self, task: Task) -> None:
        """Re-add a task to the queue (e.g., when it couldn't be scheduled).

        Args:
            task: Task to requeue
        """
        await self.enqueue(task)

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics for all queues.

        Returns:
            Dict with queue statistics
        """
        stats = {
            "total_pending": len(self.global_pending) + sum(
                len(q.pending_tasks) for q in self.tenant_queues.values()
            ),
            "global_pending": len(self.global_pending),
            "tenants": {},
        }

        for tenant_id, tenant_queue in self.tenant_queues.items():
            stats["tenants"][tenant_id] = {
                "queue_length": tenant_queue.queue_length,
                "weight": tenant_queue.weight,
                "tasks_scheduled": tenant_queue.tasks_scheduled,
                "cumulative_weight": tenant_queue.cumulative_weight,
                "avg_wait_hours": tenant_queue.average_wait_time_hours,
                "current_usage": tenant_queue.current_usage.copy(),
            }

        return stats

    def get_tenant_queue(self, tenant_id: str) -> Optional[TenantQueue]:
        """Get tenant queue by ID.

        Args:
            tenant_id: Tenant identifier

        Returns:
            TenantQueue if exists, None otherwise
        """
        return self.tenant_queues.get(tenant_id)

    def remove_tenant(self, tenant_id: str) -> bool:
        """Remove a tenant queue.

        Args:
            tenant_id: Tenant identifier

        Returns:
            True if removed, False if not found
        """
        if tenant_id in self.tenant_queues:
            del self.tenant_queues[tenant_id]
            return True
        return False

    def clear_global_queue(self) -> int:
        """Clear all tasks from global queue.

        Returns:
            Number of tasks removed
        """
        count = len(self.global_pending)
        self.global_pending.clear()
        return count

    @property
    def total_pending_tasks(self) -> int:
        """Get total number of pending tasks across all queues."""
        return (
            len(self.global_pending) +
            sum(q.queue_length for q in self.tenant_queues.values())
        )

    @property
    def active_tenant_count(self) -> int:
        """Get number of active tenants (with non-empty queues)."""
        return sum(1 for q in self.tenant_queues.values() if not q.is_empty())
