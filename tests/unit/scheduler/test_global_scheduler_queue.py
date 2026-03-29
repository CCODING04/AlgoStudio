"""Unit tests for GlobalSchedulerQueue - WFQ-based global scheduling queue.

Tests cover:
1. _get_eligible_tenants() - filters by guaranteed minimums
2. _select_tenant_wrr() - WRR selection algorithm
3. dequeue() - full WFQ selection flow
4. requeue(), remove_tenant(), clear_global_queue()
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from typing import Optional, Dict, Any

from algo_studio.core.scheduler.global_queue import GlobalSchedulerQueue
from algo_studio.core.scheduler.tenant_queue import TenantQueue
from algo_studio.core.quota.manager import QuotaManager
from algo_studio.core.quota.store import ResourceQuota, QuotaScope
from algo_studio.core.task import Task, TaskType, TaskStatus


# =============================================================================
# Fixtures
# =============================================================================

def create_mock_task(
    task_id: str = "task-1",
    tenant_id: Optional[str] = None,
    priority: int = 50,
    status: str = "pending",
    task_type: str = "train",
):
    """Create a mock task for testing.

    Args:
        task_id: Unique task identifier
        tenant_id: Tenant identifier (None for global)
        priority: Task priority (0-100, higher = more priority)
        status: Task status string
        task_type: Type of task (train/infer/verify)

    Returns:
        Mock Task with required attributes
    """
    task = MagicMock(spec=Task)
    task.task_id = task_id
    task.tenant_id = tenant_id
    task.priority = priority
    task.status = status
    task.created_at = datetime.now()
    task.task_type = task_type
    return task


class MockQuotaManager:
    """Mock QuotaManager for testing.

    Provides configurable quota responses for tenant weight and
    guaranteed minimum testing.
    """

    def __init__(self):
        self.quotas: Dict[str, Dict[str, Any]] = {}

    def _get_effective_quota(self, user_id: str = None, team_id: str = None) -> Optional[Dict[str, Any]]:
        """Return mock quota based on tenant_id.

        Args:
            user_id: User identifier
            team_id: Team/Tenant identifier

        Returns:
            Quota dict or None if not found
        """
        key = team_id or user_id
        if key and key in self.quotas:
            return self.quotas[key]
        return None

    def get_quota(self, quota_id: str) -> Optional[Dict[str, Any]]:
        """Get quota by ID."""
        for quota in self.quotas.values():
            if quota.get("quota_id") == quota_id:
                return quota
        return None


@pytest.fixture
def mock_quota_manager():
    """Create a mock QuotaManager."""
    return MockQuotaManager()


@pytest.fixture
def global_queue(mock_quota_manager):
    """Create a GlobalSchedulerQueue with mock quota manager."""
    return GlobalSchedulerQueue(quota_manager=mock_quota_manager)


@pytest.fixture
def mock_resource_quota():
    """Create a mock resource quota with ample resources."""
    return ResourceQuota(
        cpu_cores=10,
        gpu_count=4,
        gpu_memory_gb=32.0,
        memory_gb=64.0,
        concurrent_tasks=5,
    )


# =============================================================================
# _get_eligible_tenants() Tests - Guaranteed Minimum Filtering
# =============================================================================

class TestGetEligibleTenants:
    """Tests for _get_eligible_tenants() method.

    This method filters tenant queues based on:
    1. Queue must be non-empty
    2. Guaranteed minimums must be satisfiable with available resources
    """

    def test_empty_queues_returns_empty_list(self, global_queue, mock_resource_quota):
        """Test empty tenant queues returns empty list."""
        result = global_queue._get_eligible_tenants(mock_resource_quota)
        assert result == []

    def test_non_empty_queue_is_eligible(self, global_queue, mock_resource_quota):
        """Test non-empty tenant queue is eligible when no guaranteed mins set."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        # Create tenant queue and add a task
        global_queue._create_tenant_queue("tenant-1")
        task = create_mock_task(task_id="task-1", tenant_id="tenant-1")
        global_queue.tenant_queues["tenant-1"].enqueue(task)

        result = global_queue._get_eligible_tenants(mock_resource_quota)

        assert len(result) == 1
        assert result[0].tenant_id == "tenant-1"

    def test_empty_queue_is_not_eligible(self, global_queue, mock_resource_quota):
        """Test empty tenant queue is not eligible."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        # Create empty tenant queue
        global_queue._create_tenant_queue("tenant-1")

        result = global_queue._get_eligible_tenants(mock_resource_quota)

        assert len(result) == 0

    def test_guaranteed_minimum_gpu_insufficient(self, global_queue):
        """Test tenant with guaranteed GPU minimum not met is ineligible."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value={
            "guaranteed_gpu_count": 5,  # Requires 5 GPUs
            "guaranteed_cpu_cores": 0,
            "guaranteed_memory_gb": 0,
        })

        global_queue._create_tenant_queue("tenant-1")
        task = create_mock_task(task_id="task-1", tenant_id="tenant-1")
        global_queue.tenant_queues["tenant-1"].enqueue(task)

        # Available GPU (2) is less than guaranteed minimum (5)
        low_resource_quota = ResourceQuota(gpu_count=2)
        result = global_queue._get_eligible_tenants(low_resource_quota)

        assert len(result) == 0

    def test_guaranteed_minimum_gpu_sufficient(self, global_queue):
        """Test tenant with guaranteed GPU minimum met is eligible."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value={
            "guaranteed_gpu_count": 2,  # Requires 2 GPUs
            "guaranteed_cpu_cores": 0,
            "guaranteed_memory_gb": 0,
        })

        global_queue._create_tenant_queue("tenant-1")
        task = create_mock_task(task_id="task-1", tenant_id="tenant-1")
        global_queue.tenant_queues["tenant-1"].enqueue(task)

        # Available GPU (4) meets guaranteed minimum (2)
        high_resource_quota = ResourceQuota(gpu_count=4)
        result = global_queue._get_eligible_tenants(high_resource_quota)

        assert len(result) == 1
        assert result[0].tenant_id == "tenant-1"

    def test_multiple_tenants_mixed_eligibility(self, global_queue):
        """Test multiple tenants with mixed eligibility."""
        # Tenant 1: needs 3 GPUs
        global_queue.quota_manager.quotas = {
            "tenant-1": {
                "guaranteed_gpu_count": 3,
                "guaranteed_cpu_cores": 0,
                "guaranteed_memory_gb": 0,
            },
            "tenant-2": {
                "guaranteed_gpu_count": 0,  # No minimum
                "guaranteed_cpu_cores": 0,
                "guaranteed_memory_gb": 0,
            },
        }

        global_queue._create_tenant_queue("tenant-1")
        global_queue._create_tenant_queue("tenant-2")
        global_queue.tenant_queues["tenant-1"].enqueue(
            create_mock_task(task_id="task-1", tenant_id="tenant-1")
        )
        global_queue.tenant_queues["tenant-2"].enqueue(
            create_mock_task(task_id="task-2", tenant_id="tenant-2")
        )

        # Only 2 GPUs available - tenant-1 ineligible, tenant-2 eligible
        limited_resource_quota = ResourceQuota(gpu_count=2)
        result = global_queue._get_eligible_tenants(limited_resource_quota)

        assert len(result) == 1
        assert result[0].tenant_id == "tenant-2"

    def test_guaranteed_minimum_none_is_always_eligible(self, global_queue, mock_resource_quota):
        """Test tenant with no guaranteed_minimum is always eligible if non-empty."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        global_queue._create_tenant_queue("tenant-1")
        global_queue.tenant_queues["tenant-1"].enqueue(
            create_mock_task(task_id="task-1", tenant_id="tenant-1")
        )

        result = global_queue._get_eligible_tenants(mock_resource_quota)

        assert len(result) == 1


# =============================================================================
# _select_tenant_wrr() Tests - Weighted Round-Robin Selection
# =============================================================================

class TestSelectTenantWrr:
    """Tests for _select_tenant_wrr() method.

    Weighted Round-Robin selection: tenant with lowest ratio
    (tasks_scheduled / weight) is selected as most underserved.
    """

    def test_empty_list_returns_none(self, global_queue):
        """Test empty tenant list returns None."""
        result = global_queue._select_tenant_wrr([])
        assert result is None

    def test_single_tenant_selected(self, global_queue):
        """Test single tenant in list is selected."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        tq1 = global_queue._create_tenant_queue("tenant-1")
        tq1.enqueue(create_mock_task(task_id="task-1", tenant_id="tenant-1"))

        tenants = [tq1]
        result = global_queue._select_tenant_wrr(tenants)

        assert result == tq1

    def test_lowest_ratio_selected(self, global_queue):
        """Test tenant with lowest WRR ratio (most underserved) is selected."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        tq1 = global_queue._create_tenant_queue("tenant-1")
        tq2 = global_queue._create_tenant_queue("tenant-2")

        tq1.enqueue(create_mock_task(task_id="task-1", tenant_id="tenant-1"))
        tq2.enqueue(create_mock_task(task_id="task-2", tenant_id="tenant-2"))

        # tq1: 0 tasks scheduled, ratio = 0/1.0 = 0 (most underserved)
        # tq2: 5 tasks scheduled, ratio = 5/1.0 = 5
        tq1.tasks_scheduled = 0
        tq2.tasks_scheduled = 5

        tenants = [tq1, tq2]
        result = global_queue._select_tenant_wrr(tenants)

        assert result == tq1

    def test_weight_affects_ratio(self, global_queue):
        """Test that tenant weight affects WRR ratio calculation."""
        global_queue.quota_manager.quotas = {
            "tenant-1": {"weight": 1.0},  # ratio = 0/1.0 = 0
            "tenant-2": {"weight": 2.0},  # ratio = 0/2.0 = 0 (same as tenant-1)
        }

        tq1 = global_queue._create_tenant_queue("tenant-1")
        tq2 = global_queue._create_tenant_queue("tenant-2")

        tq1.enqueue(create_mock_task(task_id="task-1", tenant_id="tenant-1"))
        tq2.enqueue(create_mock_task(task_id="task-2", tenant_id="tenant-2"))

        # Both have 0 scheduled, tenant-1 has lower weight so lower ratio
        tenants = [tq1, tq2]
        result = global_queue._select_tenant_wrr(tenants)

        assert result == tq1

    def test_higher_weight_tolerates_more_tasks(self, global_queue):
        """Test tenant with higher weight can have more tasks but still be selected."""
        global_queue.quota_manager.quotas = {
            "tenant-1": {"weight": 1.0},  # ratio = 10/1.0 = 10
            "tenant-2": {"weight": 5.0},  # ratio = 10/5.0 = 2 (more underserved)
        }

        tq1 = global_queue._create_tenant_queue("tenant-1")
        tq2 = global_queue._create_tenant_queue("tenant-2")

        tq1.enqueue(create_mock_task(task_id="task-1", tenant_id="tenant-1"))
        tq2.enqueue(create_mock_task(task_id="task-2", tenant_id="tenant-2"))

        # tq1 scheduled 10 tasks, tq2 scheduled 10 tasks but with higher weight
        tq1.tasks_scheduled = 10
        tq1.invalidate_ratio_cache()
        tq2.tasks_scheduled = 10
        tq2.invalidate_ratio_cache()

        tenants = [tq1, tq2]
        result = global_queue._select_tenant_wrr(tenants)

        # tq2 should win because despite same scheduled count, its ratio is lower
        # due to higher weight (2 < 10)
        assert result == tq2

    def test_same_ratio_selects_first_in_list(self, global_queue):
        """Test that with same ratio, first tenant in list is selected."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        tq1 = global_queue._create_tenant_queue("tenant-1")
        tq2 = global_queue._create_tenant_queue("tenant-2")

        tq1.enqueue(create_mock_task(task_id="task-1", tenant_id="tenant-1"))
        tq2.enqueue(create_mock_task(task_id="task-2", tenant_id="tenant-2"))

        # Same tasks_scheduled and weight = same ratio
        tq1.tasks_scheduled = 2
        tq2.tasks_scheduled = 2

        tenants = [tq1, tq2]
        result = global_queue._select_tenant_wrr(tenants)

        assert result == tq1

    def test_three_tenants_选most_underserved(self, global_queue):
        """Test three-way selection selects most underserved."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        tq1 = global_queue._create_tenant_queue("tenant-1")
        tq2 = global_queue._create_tenant_queue("tenant-2")
        tq3 = global_queue._create_tenant_queue("tenant-3")

        tq1.enqueue(create_mock_task(task_id="task-1", tenant_id="tenant-1"))
        tq2.enqueue(create_mock_task(task_id="task-2", tenant_id="tenant-2"))
        tq3.enqueue(create_mock_task(task_id="task-3", tenant_id="tenant-3"))

        # tq1: ratio 0/1.0 = 0 (most underserved)
        # tq2: ratio 3/1.0 = 3
        # tq3: ratio 6/1.0 = 6
        tq1.tasks_scheduled = 0
        tq2.tasks_scheduled = 3
        tq3.tasks_scheduled = 6

        tenants = [tq1, tq2, tq3]
        result = global_queue._select_tenant_wrr(tenants)

        assert result == tq1


# =============================================================================
# dequeue() Tests - Full WFQ Selection Flow
# =============================================================================

class TestDequeue:
    """Tests for dequeue() method.

    Full WFQ selection flow:
    1. Get eligible tenants (filter by guaranteed mins)
    2. Select tenant via WRR (lowest ratio = most underserved)
    3. Get next task from tenant (priority order)
    4. Update WFQ state
    """

    @pytest.mark.asyncio
    async def test_dequeue_empty_returns_none(self, global_queue, mock_resource_quota):
        """Test dequeue returns None when all queues are empty."""
        result = await global_queue.dequeue(mock_resource_quota)
        assert result is None

    @pytest.mark.asyncio
    async def test_dequeue_global_task(self, global_queue, mock_resource_quota):
        """Test dequeuing from global queue when no eligible tenants."""
        task = create_mock_task(task_id="task-1", tenant_id=None)
        await global_queue.enqueue(task)

        result = await global_queue.dequeue(mock_resource_quota)

        assert result is not None
        task_dequeued, queue_path = result
        assert queue_path == "global"
        assert len(global_queue.global_pending) == 0

    @pytest.mark.asyncio
    async def test_dequeue_tenant_task(self, global_queue, mock_resource_quota):
        """Test dequeuing from tenant queue."""
        task = create_mock_task(task_id="task-1", tenant_id="tenant-1")
        await global_queue.enqueue(task)

        result = await global_queue.dequeue(mock_resource_quota)

        assert result is not None
        task_dequeued, queue_path = result
        assert queue_path == "tenant:tenant-1"

    @pytest.mark.asyncio
    async def test_dequeue_priority_order(self, global_queue, mock_resource_quota):
        """Test dequeuing returns highest priority task first within tenant."""
        # Enqueue tasks with different priorities
        task_low = create_mock_task(task_id="task-low", tenant_id="tenant-1", priority=20)
        task_high = create_mock_task(task_id="task-high", tenant_id="tenant-1", priority=80)
        task_medium = create_mock_task(task_id="task-medium", tenant_id="tenant-1", priority=50)

        await global_queue.enqueue(task_low)
        await global_queue.enqueue(task_high)
        await global_queue.enqueue(task_medium)

        result = await global_queue.dequeue(mock_resource_quota)
        assert result is not None
        dequeued_task, _ = result
        assert dequeued_task.task_id == "task-high"

    @pytest.mark.asyncio
    async def test_dequeue_updates_wfq_state(self, global_queue, mock_resource_quota):
        """Test dequeue updates WFQ state for tenant queue."""
        task = create_mock_task(task_id="task-1", tenant_id="tenant-1", priority=75)
        await global_queue.enqueue(task)

        await global_queue.dequeue(mock_resource_quota)

        tenant_queue = global_queue.tenant_queues["tenant-1"]
        assert tenant_queue.tasks_scheduled == 1
        assert tenant_queue.cumulative_weight > 0

    @pytest.mark.asyncio
    async def test_dequeue_task_weight_based_on_priority(self, global_queue, mock_resource_quota):
        """Test task weight in WFQ state is based on priority."""
        task_low = create_mock_task(task_id="task-low", tenant_id="tenant-1", priority=20)
        task_high = create_mock_task(task_id="task-high", tenant_id="tenant-1", priority=80)

        await global_queue.enqueue(task_low)
        await global_queue.dequeue(mock_resource_quota)

        await global_queue.enqueue(task_high)
        await global_queue.dequeue(mock_resource_quota)

        tenant_queue = global_queue.tenant_queues["tenant-1"]
        # weight = 0.5 + (priority / 100)
        # low: 0.5 + (20/100) = 0.7
        # high: 0.5 + (80/100) = 1.3
        # cumulative should be 0.7 + 1.3 = 2.0
        assert tenant_queue.cumulative_weight == pytest.approx(2.0, rel=0.1)

    @pytest.mark.asyncio
    async def test_dequeue_increments_scheduled_count(self, global_queue, mock_resource_quota):
        """Test dequeue increments global scheduled count."""
        task = create_mock_task(task_id="task-1", tenant_id="tenant-1")
        await global_queue.enqueue(task)

        assert global_queue.scheduled_count == 0
        await global_queue.dequeue(mock_resource_quota)
        assert global_queue.scheduled_count == 1

    @pytest.mark.asyncio
    async def test_dequeue_no_eligible_tenants_falls_back_to_global(self, global_queue, mock_resource_quota):
        """Test fallback to global queue when no eligible tenants."""
        # Set guaranteed minimum that can't be satisfied
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value={
            "guaranteed_gpu_count": 100,  # More than available
            "guaranteed_cpu_cores": 0,
            "guaranteed_memory_gb": 0,
        })

        task_global = create_mock_task(task_id="task-global")
        task_tenant = create_mock_task(task_id="task-tenant", tenant_id="tenant-1")
        await global_queue.enqueue(task_global)
        await global_queue.enqueue(task_tenant)

        # Only global task should be returned
        result = await global_queue.dequeue(mock_resource_quota)

        # Tenant queue should still have task (not dequeued)
        assert len(global_queue.tenant_queues["tenant-1"].pending_tasks) == 1
        # Global queue should be empty
        assert len(global_queue.global_pending) == 0

    @pytest.mark.asyncio
    async def test_dequeue_multiple_tenants_wrr_selection(self, global_queue, mock_resource_quota):
        """Test dequeue selects from multiple tenants using WRR."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        # Create two tenants
        tq1 = global_queue._create_tenant_queue("tenant-1")
        tq2 = global_queue._create_tenant_queue("tenant-2")

        tq1.enqueue(create_mock_task(task_id="task-1", tenant_id="tenant-1"))
        tq2.enqueue(create_mock_task(task_id="task-2", tenant_id="tenant-2"))

        # Make tenant-1 more underserved
        tq1.tasks_scheduled = 0
        tq2.tasks_scheduled = 5

        result = await global_queue.dequeue(mock_resource_quota)

        assert result is not None
        _, queue_path = result
        assert queue_path == "tenant:tenant-1"

    @pytest.mark.asyncio
    async def test_dequeue_returns_none_when_tenant_queue_empty_after_filter(self, global_queue):
        """Test dequeue returns None when all tenant queues fail guaranteed check."""
        global_queue.quota_manager.quotas = {
            "tenant-1": {"guaranteed_gpu_count": 100},
        }

        global_queue._create_tenant_queue("tenant-1")
        global_queue.tenant_queues["tenant-1"].enqueue(
            create_mock_task(task_id="task-1", tenant_id="tenant-1")
        )

        # Only 1 GPU available, tenant needs 100
        limited_quota = ResourceQuota(gpu_count=1)
        result = await global_queue.dequeue(limited_quota)

        assert result is None


# =============================================================================
# requeue() Tests
# =============================================================================

class TestRequeue:
    """Tests for requeue() method.

    requeue() delegates to enqueue() to re-add tasks that couldn't be scheduled.
    """

    @pytest.mark.asyncio
    async def test_requeue_global_task(self, global_queue):
        """Test requeue adds task back to global queue."""
        task = create_mock_task(task_id="task-1", tenant_id=None)

        await global_queue.requeue(task)

        assert len(global_queue.global_pending) == 1
        assert global_queue.global_pending[0] == task

    @pytest.mark.asyncio
    async def test_requeue_tenant_task(self, global_queue):
        """Test requeue adds task back to tenant queue."""
        task = create_mock_task(task_id="task-1", tenant_id="tenant-1")

        await global_queue.requeue(task)

        assert "tenant-1" in global_queue.tenant_queues
        assert global_queue.tenant_queues["tenant-1"].queue_length == 1


# =============================================================================
# remove_tenant() Tests
# =============================================================================

class TestRemoveTenant:
    """Tests for remove_tenant() method.

    Removes a tenant queue from the global scheduler.
    """

    def test_remove_existing_tenant(self, global_queue):
        """Test removing existing tenant returns True."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        global_queue._create_tenant_queue("tenant-1")

        result = global_queue.remove_tenant("tenant-1")

        assert result is True
        assert "tenant-1" not in global_queue.tenant_queues

    def test_remove_nonexistent_tenant(self, global_queue):
        """Test removing non-existent tenant returns False."""
        result = global_queue.remove_tenant("nonexistent")

        assert result is False

    def test_remove_tenant_with_tasks(self, global_queue):
        """Test removing tenant with pending tasks removes all tasks."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        global_queue._create_tenant_queue("tenant-1")
        global_queue.tenant_queues["tenant-1"].enqueue(
            create_mock_task(task_id="task-1", tenant_id="tenant-1")
        )
        global_queue.tenant_queues["tenant-1"].enqueue(
            create_mock_task(task_id="task-2", tenant_id="tenant-1")
        )

        global_queue.remove_tenant("tenant-1")

        assert "tenant-1" not in global_queue.tenant_queues
        assert global_queue.total_pending_tasks == 0


# =============================================================================
# clear_global_queue() Tests
# =============================================================================

class TestClearGlobalQueue:
    """Tests for clear_global_queue() method.

    Clears all tasks from the global (non-tenant) queue.
    """

    def test_clear_empty_queue_returns_zero(self, global_queue):
        """Test clearing empty global queue returns 0."""
        result = global_queue.clear_global_queue()

        assert result == 0

    def test_clear_queue_returns_count(self, global_queue):
        """Test clearing queue returns number of tasks removed."""
        global_queue.global_pending = [
            create_mock_task(task_id="task-1"),
            create_mock_task(task_id="task-2"),
            create_mock_task(task_id="task-3"),
        ]

        result = global_queue.clear_global_queue()

        assert result == 3
        assert len(global_queue.global_pending) == 0

    def test_clear_does_not_affect_tenant_queues(self, global_queue):
        """Test clear global queue does not affect tenant queues."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        global_queue.global_pending = [create_mock_task(task_id="task-global")]
        global_queue._create_tenant_queue("tenant-1")
        global_queue.tenant_queues["tenant-1"].enqueue(
            create_mock_task(task_id="task-tenant", tenant_id="tenant-1")
        )

        global_queue.clear_global_queue()

        assert global_queue.total_pending_tasks == 1
        assert global_queue.tenant_queues["tenant-1"].queue_length == 1


# =============================================================================
# Integration Tests - Full WFQ Flow
# =============================================================================

class TestWFQFlowIntegration:
    """Integration tests for complete WFQ scheduling flow."""

    @pytest.mark.asyncio
    async def test_wfq_fairness_over_multiple_schedules(self, global_queue, mock_resource_quota):
        """Test WFQ provides fairness over multiple schedule cycles."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        # Create two tenants with equal weight
        for tenant_id in ["tenant-1", "tenant-2"]:
            global_queue._create_tenant_queue(tenant_id)
            for i in range(3):
                global_queue.tenant_queues[tenant_id].enqueue(
                    create_mock_task(task_id=f"{tenant_id}-task-{i}", tenant_id=tenant_id)
                )

        # Schedule 6 tasks alternating between tenants
        schedule_order = []
        for _ in range(6):
            result = await global_queue.dequeue(mock_resource_quota)
            if result:
                _, queue_path = result
                schedule_order.append(queue_path)

        # Both tenants should have equal representation (3 each ideally)
        # due to WFQ balancing
        tenant1_count = schedule_order.count("tenant:tenant-1")
        tenant2_count = schedule_order.count("tenant:tenant-2")
        assert tenant1_count == 3
        assert tenant2_count == 3

    @pytest.mark.asyncio
    async def test_wfq_respects_weight_differences(self, global_queue, mock_resource_quota):
        """Test WFQ respects different tenant weights."""
        global_queue.quota_manager.quotas = {
            "low-priority": {"weight": 1.0},
            "high-priority": {"weight": 3.0},
        }

        global_queue._create_tenant_queue("low-priority")
        global_queue._create_tenant_queue("high-priority")

        # Each tenant has 3 tasks
        for tenant_id in ["low-priority", "high-priority"]:
            for i in range(3):
                global_queue.tenant_queues[tenant_id].enqueue(
                    create_mock_task(task_id=f"{tenant_id}-task-{i}", tenant_id=tenant_id)
                )

        # With weight 3:1, high-priority should get 3 tasks for every 1 low-priority
        schedule_order = []
        for _ in range(4):  # Schedule 4 tasks
            result = await global_queue.dequeue(mock_resource_quota)
            if result:
                _, queue_path = result
                schedule_order.append(queue_path)

        # high-priority should dominate due to 3x weight
        high_count = schedule_order.count("tenant:high-priority")
        low_count = schedule_order.count("tenant:low-priority")
        assert high_count == 3
        assert low_count == 1

    @pytest.mark.asyncio
    async def test_empty_tenant_removed_from_wrr_selection(self, global_queue, mock_resource_quota):
        """Test tenant queue becoming empty doesn't break scheduling."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        tq1 = global_queue._create_tenant_queue("tenant-1")
        tq2 = global_queue._create_tenant_queue("tenant-2")

        # tq1 has 1 task, tq2 has 2 tasks
        tq1.enqueue(create_mock_task(task_id="task-1", tenant_id="tenant-1"))
        tq2.enqueue(create_mock_task(task_id="task-2", tenant_id="tenant-2"))
        tq2.enqueue(create_mock_task(task_id="task-3", tenant_id="tenant-2"))

        # Schedule all 3 tasks
        results = []
        for _ in range(3):
            result = await global_queue.dequeue(mock_resource_quota)
            if result:
                results.append(result)

        assert len(results) == 3
        # Verify we can continue scheduling without error
        more_result = await global_queue.dequeue(mock_resource_quota)
        assert more_result is None  # All queues empty
