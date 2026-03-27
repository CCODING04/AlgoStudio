"""Unit tests for GlobalSchedulerQueue."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from typing import Optional

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
):
    """Create a mock task for testing."""
    task = MagicMock(spec=Task)
    task.task_id = task_id
    task.tenant_id = tenant_id
    task.priority = priority
    task.status = status
    task.created_at = datetime.now()
    return task


class MockQuotaManager:
    """Mock QuotaManager for testing."""

    def __init__(self):
        self.quotas = {}

    def _get_effective_quota(self, user_id: str = None, team_id: str = None):
        """Return mock quota based on tenant_id."""
        if team_id and team_id in self.quotas:
            return self.quotas[team_id]
        return None

    def get_quota(self, quota_id: str):
        """Get quota by ID."""
        return self.quotas.get(quota_id)


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
    """Create a mock resource quota."""
    return ResourceQuota(
        cpu_cores=10,
        gpu_count=2,
        gpu_memory_gb=16.0,
        memory_gb=32.0,
        concurrent_tasks=5,
    )


# =============================================================================
# GlobalSchedulerQueue Initialization Tests
# =============================================================================

class TestGlobalSchedulerQueueInit:
    """Tests for GlobalSchedulerQueue initialization."""

    def test_init_sets_quota_manager(self, mock_quota_manager):
        """Test initialization sets quota manager."""
        queue = GlobalSchedulerQueue(quota_manager=mock_quota_manager)

        assert queue.quota_manager == mock_quota_manager

    def test_init_starts_empty(self, mock_quota_manager):
        """Test initialization starts with empty queues."""
        queue = GlobalSchedulerQueue(quota_manager=mock_quota_manager)

        assert queue.tenant_queues == {}
        assert queue.global_pending == []
        assert queue.scheduled_count == 0

    def test_init_has_lock(self, mock_quota_manager):
        """Test initialization creates asyncio lock."""
        queue = GlobalSchedulerQueue(quota_manager=mock_quota_manager)

        assert isinstance(queue._lock, asyncio.Lock)


# =============================================================================
# Enqueue Tests
# =============================================================================

class TestEnqueue:
    """Tests for enqueue method."""

    @pytest.mark.asyncio
    async def test_enqueue_global_task(self, global_queue):
        """Test enqueueing a task without tenant_id goes to global queue."""
        task = create_mock_task(task_id="task-1", tenant_id=None)

        result = await global_queue.enqueue(task)

        assert result == "global"
        assert len(global_queue.global_pending) == 1
        assert global_queue.global_pending[0] == task

    @pytest.mark.asyncio
    async def test_enqueue_tenant_task(self, global_queue):
        """Test enqueueing a task with tenant_id goes to tenant queue."""
        task = create_mock_task(task_id="task-1", tenant_id="tenant-1")

        result = await global_queue.enqueue(task)

        assert result == "tenant:tenant-1"
        assert "tenant-1" in global_queue.tenant_queues

    @pytest.mark.asyncio
    async def test_enqueue_creates_tenant_queue(self, global_queue):
        """Test enqueueing first task for tenant creates tenant queue."""
        task = create_mock_task(task_id="task-1", tenant_id="tenant-1")

        await global_queue.enqueue(task)

        assert "tenant-1" in global_queue.tenant_queues
        assert isinstance(global_queue.tenant_queues["tenant-1"], TenantQueue)

    @pytest.mark.asyncio
    async def test_enqueue_multiple_tasks_same_tenant(self, global_queue):
        """Test enqueueing multiple tasks for same tenant."""
        task1 = create_mock_task(task_id="task-1", tenant_id="tenant-1")
        task2 = create_mock_task(task_id="task-2", tenant_id="tenant-1")

        await global_queue.enqueue(task1)
        await global_queue.enqueue(task2)

        tenant_queue = global_queue.tenant_queues["tenant-1"]
        assert tenant_queue.queue_length == 2


# =============================================================================
# _create_tenant_queue Tests
# =============================================================================

class TestCreateTenantQueue:
    """Tests for _create_tenant_queue method."""

    def test_creates_tenant_queue_with_defaults(self, global_queue):
        """Test creating tenant queue with default values."""
        # Set up quota manager to return None
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        tenant_queue = global_queue._create_tenant_queue("tenant-1")

        assert tenant_queue.tenant_id == "tenant-1"
        assert tenant_queue.weight == 1.0
        assert tenant_queue.quota_id == ""
        assert tenant_queue.guaranteed_minimum is None

    def test_creates_tenant_queue_with_quota(self, global_queue):
        """Test creating tenant queue with quota settings."""
        quota_data = {
            "quota_id": "quota-1",
            "weight": 2.5,
            "guaranteed_gpu_count": 1,
            "guaranteed_cpu_cores": 4,
            "guaranteed_memory_gb": 16.0,
        }
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=quota_data)

        tenant_queue = global_queue._create_tenant_queue("tenant-1")

        assert tenant_queue.tenant_id == "tenant-1"
        assert tenant_queue.weight == 2.5
        assert tenant_queue.quota_id == "quota-1"
        assert tenant_queue.guaranteed_minimum == {
            "gpu_count": 1,
            "cpu_cores": 4,
            "memory_gb": 16.0,
        }

    def test_tenant_queue_stored(self, global_queue):
        """Test created tenant queue is stored."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        global_queue._create_tenant_queue("tenant-1")

        assert "tenant-1" in global_queue.tenant_queues


# =============================================================================
# Dequeue Tests
# =============================================================================

class TestDequeue:
    """Tests for dequeue method."""

    @pytest.mark.asyncio
    async def test_dequeue_empty_returns_none(self, global_queue, mock_resource_quota):
        """Test dequeue returns None when all queues are empty."""
        result = await global_queue.dequeue(mock_resource_quota)

        assert result is None

    @pytest.mark.asyncio
    async def test_dequeue_global_task(self, global_queue, mock_resource_quota):
        """Test dequeuing from global queue."""
        task = create_mock_task(task_id="task-1")
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
    async def test_dequeue_updates_wfq_state(self, global_queue, mock_resource_quota):
        """Test dequeue updates WFQ state for tenant queue."""
        task = create_mock_task(task_id="task-1", tenant_id="tenant-1", priority=75)
        await global_queue.enqueue(task)

        await global_queue.dequeue(mock_resource_quota)

        tenant_queue = global_queue.tenant_queues["tenant-1"]
        assert tenant_queue.tasks_scheduled == 1
        assert tenant_queue.cumulative_weight > 0

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
        # Add a tenant queue but with guaranteed minimums that can't be satisfied
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value={
            "guaranteed_gpu_count": 100,  # More than available
            "guaranteed_cpu_cores": 0,
            "guaranteed_memory_gb": 0,
        })

        task_global = create_mock_task(task_id="task-global")
        task_tenant = create_mock_task(task_id="task-tenant", tenant_id="tenant-1")
        await global_queue.enqueue(task_global)
        await global_queue.enqueue(task_tenant)

        # Only global task should be returned since tenant can't be satisfied
        result = await global_queue.dequeue(mock_resource_quota)

        # Tenant queue should be empty (task was not dequeued from tenant)
        # Global queue task should be dequeued
        assert len(global_queue.global_pending) == 0


# =============================================================================
# _get_eligible_tenants Tests
# =============================================================================

class TestGetEligibleTenants:
    """Tests for _get_eligible_tenants method."""

    def test_empty_queues_returns_empty(self, global_queue, mock_resource_quota):
        """Test empty tenant queues returns empty list."""
        result = global_queue._get_eligible_tenants(mock_resource_quota)

        assert result == []

    def test_non_empty_queue_is_eligible(self, global_queue, mock_resource_quota):
        """Test non-empty tenant queue is eligible."""
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

    def test_guaranteed_minimum_gpu_check(self, global_queue):
        """Test guaranteed minimum GPU count check."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value={
            "guaranteed_gpu_count": 5,
            "guaranteed_cpu_cores": 0,
            "guaranteed_memory_gb": 0,
        })

        global_queue._create_tenant_queue("tenant-1")
        task = create_mock_task(task_id="task-1", tenant_id="tenant-1")
        global_queue.tenant_queues["tenant-1"].enqueue(task)

        # Available GPU is less than guaranteed minimum
        low_resource_quota = ResourceQuota(gpu_count=2)
        result = global_queue._get_eligible_tenants(low_resource_quota)

        assert len(result) == 0

        # Available GPU meets guaranteed minimum
        high_resource_quota = ResourceQuota(gpu_count=10)
        result = global_queue._get_eligible_tenants(high_resource_quota)

        assert len(result) == 1


# =============================================================================
# _select_tenant_wrr Tests
# =============================================================================

class TestSelectTenantWrr:
    """Tests for _select_tenant_wrr method."""

    def test_empty_list_returns_none(self, global_queue):
        """Test empty tenant list returns None."""
        result = global_queue._select_tenant_wrr([])

        assert result is None

    def test_selects_lowest_ratio_tenant(self, global_queue):
        """Test selects tenant with lowest WRR ratio."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        # Create two tenant queues
        tq1 = global_queue._create_tenant_queue("tenant-1")
        tq2 = global_queue._create_tenant_queue("tenant-2")

        # Add tasks to both
        tq1.enqueue(create_mock_task(task_id="task-1", tenant_id="tenant-1"))
        tq2.enqueue(create_mock_task(task_id="task-2", tenant_id="tenant-2"))

        # Make tenant-1 more underserved (lower ratio means more underserved)
        # Default weight is 1.0 for both, but tasks_scheduled affects ratio
        tq1.tasks_scheduled = 0
        tq2.tasks_scheduled = 5  # More scheduled = higher ratio = less underserved

        tenants = [tq1, tq2]
        result = global_queue._select_tenant_wrr(tenants)

        assert result == tq1

    def test_all_same_ratio_selects_first(self, global_queue):
        """Test that with same ratio, first tenant is selected."""
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

        # Should select tenant-1 (first in list)
        assert result == tq1


# =============================================================================
# Requeue Tests
# =============================================================================

class TestRequeue:
    """Tests for requeue method."""

    @pytest.mark.asyncio
    async def test_requeue_calls_enqueue(self, global_queue):
        """Test requeue delegates to enqueue."""
        task = create_mock_task(task_id="task-1", tenant_id=None)

        await global_queue.requeue(task)

        assert len(global_queue.global_pending) == 1


# =============================================================================
# Get Queue Stats Tests
# =============================================================================

class TestGetQueueStats:
    """Tests for get_queue_stats method."""

    def test_empty_queue_stats(self, global_queue):
        """Test stats for empty queue."""
        stats = global_queue.get_queue_stats()

        assert stats["total_pending"] == 0
        assert stats["global_pending"] == 0
        assert stats["tenants"] == {}

    def test_global_pending_counted(self, global_queue):
        """Test global pending tasks are counted."""
        global_queue.global_pending = [
            create_mock_task(task_id="task-1"),
            create_mock_task(task_id="task-2"),
        ]

        stats = global_queue.get_queue_stats()

        assert stats["total_pending"] == 2
        assert stats["global_pending"] == 2

    def test_tenant_stats_included(self, global_queue):
        """Test tenant stats are included."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        global_queue._create_tenant_queue("tenant-1")
        global_queue.tenant_queues["tenant-1"].enqueue(create_mock_task(task_id="task-1", tenant_id="tenant-1"))

        stats = global_queue.get_queue_stats()

        assert "tenant-1" in stats["tenants"]
        assert stats["tenants"]["tenant-1"]["queue_length"] == 1


# =============================================================================
# Get Tenant Queue Tests
# =============================================================================

class TestGetTenantQueue:
    """Tests for get_tenant_queue method."""

    def test_get_existing_tenant(self, global_queue):
        """Test getting existing tenant queue."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        global_queue._create_tenant_queue("tenant-1")

        result = global_queue.get_tenant_queue("tenant-1")

        assert result is not None
        assert result.tenant_id == "tenant-1"

    def test_get_nonexistent_tenant(self, global_queue):
        """Test getting non-existent tenant returns None."""
        result = global_queue.get_tenant_queue("nonexistent")

        assert result is None


# =============================================================================
# Remove Tenant Tests
# =============================================================================

class TestRemoveTenant:
    """Tests for remove_tenant method."""

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


# =============================================================================
# Clear Global Queue Tests
# =============================================================================

class TestClearGlobalQueue:
    """Tests for clear_global_queue method."""

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


# =============================================================================
# Property Tests
# =============================================================================

class TestTotalPendingTasks:
    """Tests for total_pending_tasks property."""

    def test_total_with_no_tasks(self, global_queue):
        """Test total pending with no tasks."""
        assert global_queue.total_pending_tasks == 0

    def test_total_with_global_tasks(self, global_queue):
        """Test total pending with global tasks only."""
        global_queue.global_pending = [
            create_mock_task(task_id="task-1"),
            create_mock_task(task_id="task-2"),
        ]

        assert global_queue.total_pending_tasks == 2

    def test_total_with_tenant_tasks(self, global_queue):
        """Test total pending with tenant tasks only."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        global_queue._create_tenant_queue("tenant-1")
        global_queue.tenant_queues["tenant-1"].enqueue(create_mock_task(task_id="task-1", tenant_id="tenant-1"))
        global_queue.tenant_queues["tenant-1"].enqueue(create_mock_task(task_id="task-2", tenant_id="tenant-1"))

        assert global_queue.total_pending_tasks == 2

    def test_total_with_mixed_tasks(self, global_queue):
        """Test total pending with both global and tenant tasks."""
        global_queue.global_pending = [create_mock_task(task_id="task-1")]
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        global_queue._create_tenant_queue("tenant-1")
        global_queue.tenant_queues["tenant-1"].enqueue(create_mock_task(task_id="task-2", tenant_id="tenant-1"))

        assert global_queue.total_pending_tasks == 2


class TestActiveTenantCount:
    """Tests for active_tenant_count property."""

    def test_active_with_no_tenants(self, global_queue):
        """Test active tenant count with no tenants."""
        assert global_queue.active_tenant_count == 0

    def test_active_with_empty_tenant(self, global_queue):
        """Test active tenant count with empty tenant queue."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        global_queue._create_tenant_queue("tenant-1")

        assert global_queue.active_tenant_count == 0

    def test_active_with_non_empty_tenant(self, global_queue):
        """Test active tenant count with non-empty tenant queue."""
        global_queue.quota_manager._get_effective_quota = MagicMock(return_value=None)

        global_queue._create_tenant_queue("tenant-1")
        global_queue.tenant_queues["tenant-1"].enqueue(create_mock_task(task_id="task-1", tenant_id="tenant-1"))

        assert global_queue.active_tenant_count == 1
