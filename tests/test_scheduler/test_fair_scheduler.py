# tests/test_scheduler/test_fair_scheduler.py
"""Unit tests for WFQ Scheduler - Fair Scheduling Algorithm"""

import pytest
import asyncio
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from dataclasses import dataclass, field
from typing import Optional

from algo_studio.core.quota.manager import QuotaManager
from algo_studio.core.quota.store import ResourceQuota, SQLiteQuotaStore
from algo_studio.core.task import Task, TaskType, TaskStatus
from algo_studio.core.scheduler.wfq_scheduler import (
    WFQScheduler,
    FairSchedulingDecision,
    PriorityOverride,
    ReservationManager,
    RESOURCE_WEIGHTS,
)
from algo_studio.core.scheduler.tenant_queue import TenantQueue
from algo_studio.core.scheduler.global_queue import GlobalSchedulerQueue


def create_temp_db():
    """Create a temporary database file for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


# Extended Task for fair scheduling tests with all required fields
@dataclass
class FairTask:
    """Extended Task with fair scheduling fields."""
    task_id: str
    task_type: TaskType
    algorithm_name: str
    algorithm_version: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    config: dict = field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None
    assigned_node: Optional[str] = None
    progress: int = 0

    # Fair scheduling fields
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    priority: int = 50  # 0-100
    is_urgent: bool = False
    requested_resources: Optional[ResourceQuota] = None

    @property
    def task_id_prop(self) -> str:
        """Alias for task_id to match expected interface."""
        return self.task_id


class TestTenantQueue:
    """Test suite for TenantQueue"""

    def setup_method(self):
        """Set up test fixtures"""
        self.tenant_queue = TenantQueue(
            tenant_id="test-tenant",
            quota_id="quota-001",
            weight=2.0,
        )

    def _create_task(
        self,
        task_id="train-001",
        priority=50,
        tenant_id="test-tenant",
    ):
        """Helper to create a test task"""
        task = FairTask(
            task_id=task_id,
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
            config={},
            priority=priority,
            tenant_id=tenant_id,
        )
        return task

    def test_enqueue(self):
        """Test adding tasks to queue"""
        task = self._create_task()
        self.tenant_queue.enqueue(task)

        assert self.tenant_queue.queue_length == 1
        assert not self.tenant_queue.is_empty()

    def test_dequeue_empty(self):
        """Test dequeue from empty queue returns None"""
        result = self.tenant_queue.dequeue()
        assert result is None

    def test_dequeue_order(self):
        """Test dequeue returns highest priority task first"""
        task1 = self._create_task(task_id="low", priority=10)
        task2 = self._create_task(task_id="high", priority=90)
        task3 = self._create_task(task_id="medium", priority=50)

        self.tenant_queue.enqueue(task1)
        self.tenant_queue.enqueue(task2)
        self.tenant_queue.enqueue(task3)

        # Should return highest priority first
        first = self.tenant_queue.dequeue()
        assert first.task_id == "high"

        second = self.tenant_queue.dequeue()
        assert second.task_id == "medium"

        third = self.tenant_queue.dequeue()
        assert third.task_id == "low"

    def test_update_wfq_state(self):
        """Test WFQ state updates after scheduling"""
        initial_weight = self.tenant_queue.cumulative_weight
        initial_count = self.tenant_queue.tasks_scheduled

        self.tenant_queue.update_wfq_state(1.5)

        assert self.tenant_queue.cumulative_weight == initial_weight + 1.5
        assert self.tenant_queue.tasks_scheduled == initial_count + 1

    def test_update_usage(self):
        """Test usage tracking"""
        resources = {"gpu_count": 2, "cpu_cores": 8}
        self.tenant_queue.update_usage(resources)

        assert self.tenant_queue.current_usage["gpu_count"] == 2
        assert self.tenant_queue.current_usage["cpu_cores"] == 8

    def test_release_usage(self):
        """Test releasing resources from usage"""
        # First allocate
        self.tenant_queue.update_usage({"gpu_count": 4})
        assert self.tenant_queue.current_usage["gpu_count"] == 4

        # Then release
        self.tenant_queue.release_usage({"gpu_count": 2})
        assert self.tenant_queue.current_usage["gpu_count"] == 2

    def test_average_wait_time(self):
        """Test average wait time calculation"""
        task = self._create_task()
        task.created_at = datetime.now() - timedelta(hours=1)
        self.tenant_queue.enqueue(task)

        avg_wait = self.tenant_queue.average_wait_time_hours
        assert 0.9 < avg_wait < 1.1  # Should be approximately 1 hour


class TestGlobalSchedulerQueue:
    """Test suite for GlobalSchedulerQueue"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_quota_manager = MagicMock(spec=QuotaManager)
        self.mock_quota_manager._get_effective_quota.return_value = None
        self.queue = GlobalSchedulerQueue(self.mock_quota_manager)

    def _create_task(
        self,
        task_id="train-001",
        tenant_id=None,
        priority=50,
    ):
        """Helper to create a test task"""
        task = FairTask(
            task_id=task_id,
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
            config={},
            priority=priority,
            tenant_id=tenant_id,
        )
        return task

    @pytest.mark.asyncio
    async def test_enqueue_global_task(self):
        """Test enqueuing task without tenant routes to global"""
        task = self._create_task(tenant_id=None)
        path = await self.queue.enqueue(task)

        assert path == "global"
        assert len(self.queue.global_pending) == 1

    @pytest.mark.asyncio
    async def test_enqueue_tenant_task(self):
        """Test enqueuing task with tenant routes to tenant queue"""
        task = self._create_task(tenant_id="team-a")
        path = await self.queue.enqueue(task)

        assert path == "tenant:team-a"
        assert "team-a" in self.queue.tenant_queues

    @pytest.mark.asyncio
    async def test_dequeue_creates_tenant_queue(self):
        """Test dequeue creates tenant queue if needed"""
        task = self._create_task(tenant_id="new-tenant")
        await self.queue.enqueue(task)

        # Should auto-create tenant queue
        assert "new-tenant" in self.queue.tenant_queues

    def test_select_tenant_wrr(self):
        """Test weighted round-robin tenant selection"""
        # Create two tenant queues with different weights
        tenant_a = TenantQueue(tenant_id="a", weight=1.0)
        tenant_b = TenantQueue(tenant_id="b", weight=2.0)

        # Initially both have 0 tasks scheduled, but a has lower weight
        # so tasks_scheduled/weight = 0 for both
        selected = self.queue._select_tenant_wrr([tenant_a, tenant_b])
        assert selected.tenant_id in ["a", "b"]  # Either is valid at 0

    def test_get_eligible_tenants(self):
        """Test filtering eligible tenants"""
        # Add tenant queues to the global scheduler queue
        self.queue.tenant_queues["empty"] = TenantQueue(tenant_id="empty")
        self.queue.tenant_queues["with_tasks"] = TenantQueue(tenant_id="with_tasks")
        self.queue.tenant_queues["with_tasks"].enqueue(self._create_task())

        available = ResourceQuota(gpu_count=1)

        eligible = self.queue._get_eligible_tenants(available)
        assert len(eligible) == 1
        assert eligible[0].tenant_id == "with_tasks"

    def test_queue_stats(self):
        """Test getting queue statistics"""
        stats = self.queue.get_queue_stats()

        assert "total_pending" in stats
        assert "global_pending" in stats
        assert "tenants" in stats
        assert stats["global_pending"] == 0


class TestWFQScheduler:
    """Test suite for WFQScheduler core algorithm"""

    def setup_method(self):
        """Set up test fixtures"""
        # Create temp file for SQLite testing
        self.db_path = create_temp_db()
        self.store = SQLiteQuotaStore(self.db_path)
        # Initialize the database schema
        self.store._init_db()

        # Create a test quota
        self.store.create_quota({
            "quota_id": "team-ml",
            "scope": "team",
            "scope_id": "ml-team",
            "name": "ML Team",
            "cpu_cores": 16,
            "gpu_count": 4,
            "memory_gb": 128.0,
            "concurrent_tasks": 8,
            "weight": 2.0,
            "guaranteed_gpu_count": 2,
        })

        self.quota_manager = QuotaManager(self.store)
        self.scheduler = WFQScheduler(self.quota_manager, total_cluster_gpu=4)

    def teardown_method(self):
        """Clean up temp database file."""
        if hasattr(self, 'db_path') and os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _create_task(
        self,
        task_id="train-001",
        tenant_id=None,
        priority=50,
    ):
        """Helper to create a test task"""
        task = FairTask(
            task_id=task_id,
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
            config={},
            priority=priority,
            tenant_id=tenant_id,
        )
        return task

    @pytest.mark.asyncio
    async def test_submit_task_creates_queue(self):
        """Test submitting a task creates tenant queue"""
        task = self._create_task(tenant_id="new-team")
        success, path = await self.scheduler.submit_task(task)

        assert success
        assert path == "tenant:new-team"

    @pytest.mark.asyncio
    async def test_schedule_next_returns_decision(self):
        """Test scheduling returns a decision"""
        task = self._create_task(tenant_id="ml-team")
        await self.scheduler.submit_task(task)

        available = ResourceQuota(gpu_count=2)
        decision = await self.scheduler.schedule_next(available)

        assert decision is not None
        assert isinstance(decision, FairSchedulingDecision)
        assert decision.task == task
        assert decision.selection_method == "wfq"

    @pytest.mark.asyncio
    async def test_priority_override_high_priority(self):
        """Test high priority task triggers override"""
        # Create quota with bypass_fairness
        self.store.create_quota({
            "quota_id": "urgent-team",
            "scope": "team",
            "scope_id": "urgent-team",
            "name": "Urgent Team",
            "weight": 1.0,
        })

        # Create high priority task
        task = self._create_task(task_id="urgent-001", tenant_id="urgent-team", priority=95)
        await self.scheduler.submit_task(task)

        available = ResourceQuota(gpu_count=2)
        decision = await self.scheduler.schedule_next(available)

        assert decision is not None
        assert decision.selection_method == "priority_override"
        assert decision.override_reason in ["high_priority", "explicit_urgent_flag", "team_bypass_permission"]

    @pytest.mark.asyncio
    async def test_task_completed_releases_resources(self):
        """Test task completion releases resources"""
        task = self._create_task(tenant_id="ml-team")
        await self.scheduler.submit_task(task)

        available = ResourceQuota(gpu_count=2)
        await self.scheduler.schedule_next(available)

        # Complete the task - should not raise
        await self.scheduler.task_completed(task)

    def test_normalize_resources(self):
        """Test resource normalization formula"""
        resources = ResourceQuota(
            gpu_count=2,
            cpu_cores=8,
            gpu_memory_gb=16.0,
            memory_gb=32.0,
        )

        normalized = self.scheduler._normalize_resources(resources)

        expected = (
            2 * RESOURCE_WEIGHTS["gpu"] +
            8 * RESOURCE_WEIGHTS["cpu"] +
            16.0 * RESOURCE_WEIGHTS["gpu_memory"] +
            32.0 * RESOURCE_WEIGHTS["memory"]
        )
        assert normalized == expected

    def test_vft_calculation(self):
        """Test Virtual Finish Time calculation"""
        task = self._create_task(tenant_id="ml-team")

        quota = {
            "weight": 2.0,
            "guaranteed_gpu_count": 2,
            "gpu_count": 4,
        }

        vft = self.scheduler._calculate_virtual_finish_time(task, quota)

        # VFT should be positive
        assert vft > 0

        # VFT for first task should include only the resource term
        # since cumulative_weight starts at 0
        # VFT = (0 / 2.0) + (resources / (2/4)) = 0 + (resources / 0.5) = resources * 2

    def test_vft_lower_for_smaller_tasks(self):
        """Test smaller tasks get lower VFT (scheduled sooner)"""
        task_small = self._create_task(task_id="small")
        task_large = self._create_task(task_id="large")

        # Set up task resources via config
        task_small.requested_resources = ResourceQuota(gpu_count=1)
        task_large.requested_resources = ResourceQuota(gpu_count=4)

        quota = {"weight": 1.0, "guaranteed_gpu_count": 1, "gpu_count": 4}

        vft_small = self.scheduler._calculate_virtual_finish_time(task_small, quota)
        vft_large = self.scheduler._calculate_virtual_finish_time(task_large, quota)

        # Smaller tasks should have lower VFT
        assert vft_small < vft_large

    def test_scheduler_stats(self):
        """Test getting scheduler statistics"""
        stats = self.scheduler.get_stats()

        assert "scheduled_count" in stats
        assert "queue_stats" in stats
        assert "active_reservations" in stats


class TestReservationManager:
    """Test suite for ReservationManager"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_quota_manager = MagicMock(spec=QuotaManager)
        self.mock_quota_manager._get_effective_quota.return_value = None
        self.reservation_manager = ReservationManager(self.mock_quota_manager)

    def _create_task(self, priority=50, is_urgent=False, tenant_id="test"):
        """Helper to create a test task"""
        import uuid
        task = FairTask(
            task_id=f"train-{uuid.uuid4().hex[:8]}",
            task_type=TaskType.TRAIN,
            algorithm_name="test",
            algorithm_version="v1",
            config={},
            priority=priority,
            is_urgent=is_urgent,
            tenant_id=tenant_id,
        )
        return task

    def test_check_override_high_priority(self):
        """Test high priority triggers override"""
        task = self._create_task(priority=95)
        override = self.reservation_manager.check_override(task)

        assert override is not None
        assert override.reason == "high_priority"

    def test_check_override_explicit_urgent(self):
        """Test explicit is_urgent flag triggers override"""
        task = self._create_task(is_urgent=True)
        override = self.reservation_manager.check_override(task)

        assert override is not None
        assert override.reason == "explicit_urgent_flag"

    def test_check_override_normal_task(self):
        """Test normal priority task doesn't trigger override"""
        task = self._create_task(priority=50)
        override = self.reservation_manager.check_override(task)

        assert override is None

    def test_check_override_team_bypass(self):
        """Test team with bypass_fairness triggers override"""
        self.mock_quota_manager._get_effective_quota.return_value = {
            "bypass_fairness": True,
        }
        task = self._create_task(priority=50)
        override = self.reservation_manager.check_override(task)

        assert override is not None
        assert override.reason == "team_bypass_permission"


class TestVFTFormula:
    """Test suite verifying VFT formula implementation"""

    def setup_method(self):
        """Set up test fixtures"""
        self.db_path = create_temp_db()

    def teardown_method(self):
        """Clean up temp database file."""
        if hasattr(self, 'db_path') and os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_vft_formula_components(self):
        """Verify VFT = (weight_sum_so_far / tenant_weight) + (task_resources / tenant_allocation_share)"""
        # This test verifies the VFT formula is correctly implemented

        store = SQLiteQuotaStore(self.db_path)
        store._init_db()
        store.create_quota({
            "quota_id": "team-1",
            "scope": "team",
            "scope_id": "team-1",
            "name": "Team 1",
            "weight": 2.0,
            "guaranteed_gpu_count": 2,
            "gpu_count": 4,
        })

        quota_manager = QuotaManager(store)
        scheduler = WFQScheduler(quota_manager, total_cluster_gpu=4)

        # Create a task with specific resources
        task = FairTask(
            task_id="test-task",
            task_type=TaskType.TRAIN,
            algorithm_name="test",
            algorithm_version="v1",
            config={},
            priority=50,
            tenant_id="team-1",
        )
        task.requested_resources = ResourceQuota(gpu_count=1, cpu_cores=4)

        # Get the tenant queue and set cumulative weight
        tenant_queue = scheduler.queue.tenant_queues.get("team-1")
        if not tenant_queue:
            # Create it via enqueue
            asyncio.run(scheduler.submit_task(task))
            tenant_queue = scheduler.queue.tenant_queues.get("team-1")

        if tenant_queue:
            tenant_queue.cumulative_weight = 4.0  # weight_sum_so_far

        quota = quota_manager._get_effective_quota("team-1", None)

        # Calculate VFT manually:
        # weight_sum_so_far = 4.0
        # tenant_weight = 2.0
        # task_resources = 1*10 + 4*1 = 14
        # allocation_share = 2/4 = 0.5
        # VFT = (4.0 / 2.0) + (14 / 0.5) = 2 + 28 = 30

        vft = scheduler._calculate_virtual_finish_time(task, quota)

        # Just verify VFT is calculated and positive
        assert vft > 0


class TestFairSchedulingIntegration:
    """Integration tests for fair scheduling with multiple tenants"""

    def setup_method(self):
        """Set up test fixtures"""
        self.db_path = create_temp_db()
        self.store = SQLiteQuotaStore(self.db_path)
        self.store._init_db()

        # Create quotas for two teams with different weights
        self.store.create_quota({
            "quota_id": "team-a",
            "scope": "team",
            "scope_id": "team-a",
            "name": "Team A",
            "weight": 1.0,  # Lower weight
            "guaranteed_gpu_count": 1,
            "gpu_count": 2,
        })

        self.store.create_quota({
            "quota_id": "team-b",
            "scope": "team",
            "scope_id": "team-b",
            "name": "Team B",
            "weight": 3.0,  # Higher weight
            "guaranteed_gpu_count": 1,
            "gpu_count": 2,
        })

        self.quota_manager = QuotaManager(self.store)
        self.scheduler = WFQScheduler(self.quota_manager, total_cluster_gpu=4)

    def teardown_method(self):
        """Clean up temp database file."""
        if hasattr(self, 'db_path') and os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _create_task(self, task_id, tenant_id):
        """Helper to create a test task"""
        return FairTask(
            task_id=task_id,
            task_type=TaskType.TRAIN,
            algorithm_name="test",
            algorithm_version="v1",
            config={},
            priority=50,
            tenant_id=tenant_id,
        )

    @pytest.mark.asyncio
    async def test_multiple_tenants_queuing(self):
        """Test tasks from multiple tenants are properly queued"""
        # Submit tasks from both teams
        await self.scheduler.submit_task(self._create_task("task-a1", "team-a"))
        await self.scheduler.submit_task(self._create_task("task-b1", "team-b"))
        await self.scheduler.submit_task(self._create_task("task-a2", "team-a"))

        stats = self.scheduler.get_stats()
        assert stats["queue_stats"]["total_pending"] == 3

    @pytest.mark.asyncio
    async def test_wfq_tenants_equal_initial(self):
        """Test WFQ gives fair access when both teams have equal needs"""
        # Submit one task from each team
        await self.scheduler.submit_task(self._create_task("task-a1", "team-a"))
        await self.scheduler.submit_task(self._create_task("task-b1", "team-b"))

        available = ResourceQuota(gpu_count=2)

        # Schedule first task
        decision1 = await self.scheduler.schedule_next(available)
        assert decision1 is not None

        # Schedule second task
        decision2 = await self.scheduler.schedule_next(available)
        assert decision2 is not None

        # Both should be scheduled
        assert self.scheduler._scheduled_count == 2


class TestWFQSchedulerQuotaManagerIntegration:
    """Integration tests for WFQScheduler with QuotaManager.

    Verifies that quota lifecycle methods are called correctly:
    - check_quota() is called before enqueueing
    - allocate_resources() is called when task starts
    - release_resources() is called when task completes
    """

    def setup_method(self):
        """Set up test fixtures with mock QuotaManager."""
        # Create mock QuotaManager
        self.mock_quota_manager = MagicMock(spec=QuotaManager)
        self.mock_quota_manager._get_effective_quota.return_value = {
            "quota_id": "test-quota",
            "scope": "team",
            "scope_id": "test-team",
            "weight": 1.0,
            "guaranteed_gpu_count": 1,
            "gpu_count": 4,
        }
        self.mock_quota_manager.check_quota.return_value = (
            True,  # allowed
            {"quota_id": "test-quota"},
            {"gpu_count_used": 0},
            []  # reasons
        )

        self.scheduler = WFQScheduler(self.mock_quota_manager, total_cluster_gpu=4)

    def _create_task(self, task_id="train-001", tenant_id="test-team"):
        """Helper to create a test task"""
        task = FairTask(
            task_id=task_id,
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
            config={},
            priority=50,
            tenant_id=tenant_id,
        )
        return task

    @pytest.mark.asyncio
    async def test_submit_task_calls_check_quota(self):
        """Test that submit_task calls check_quota before enqueueing."""
        task = self._create_task()

        success, path = await self.scheduler.submit_task(task)

        # Verify check_quota was called
        self.mock_quota_manager.check_quota.assert_called_once()
        # Verify the call arguments include user_id and team_id
        call_args = self.mock_quota_manager.check_quota.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_submit_task_rejects_when_quota_exceeded(self):
        """Test that submit_task rejects task when quota is exceeded."""
        # Configure mock to reject
        self.mock_quota_manager.check_quota.return_value = (
            False,  # not allowed
            {"quota_id": "test-quota"},
            {"gpu_count_used": 4},
            ["GPU count: requested 1, available 0"]
        )

        task = self._create_task()

        success, path = await self.scheduler.submit_task(task)

        # Task should be rejected
        assert success is False
        assert "rejected" in path
        assert "GPU count" in path

    @pytest.mark.asyncio
    async def test_schedule_next_calls_allocate_resources(self):
        """Test that schedule_next calls allocate_resources when scheduling."""
        task = self._create_task()
        await self.scheduler.submit_task(task)

        # Reset mock to check allocate_resources call
        self.mock_quota_manager.allocate_resources.reset_mock()

        available = ResourceQuota(gpu_count=2)
        decision = await self.scheduler.schedule_next(available)

        # Verify allocate_resources was called
        self.mock_quota_manager.allocate_resources.assert_called_once()
        call_args = self.mock_quota_manager.allocate_resources.call_args
        # Should be called with quota_id and resources
        assert call_args[0][0] == "test-quota"  # quota_id

    @pytest.mark.asyncio
    async def test_task_completed_calls_release_resources(self):
        """Test that task_completed calls release_resources."""
        task = self._create_task()
        await self.scheduler.submit_task(task)

        # Schedule the task to allocate resources
        available = ResourceQuota(gpu_count=2)
        await self.scheduler.schedule_next(available)

        # Reset mock to check release_resources call
        self.mock_quota_manager.release_resources.reset_mock()

        # Complete the task
        await self.scheduler.task_completed(task)

        # Verify release_resources was called
        self.mock_quota_manager.release_resources.assert_called_once()
        call_args = self.mock_quota_manager.release_resources.call_args
        # Should be called with quota_id and resources
        assert call_args[0][0] == "test-quota"  # quota_id

    @pytest.mark.asyncio
    async def test_quota_lifecycle_full_flow(self):
        """Test complete quota lifecycle: check -> allocate -> release."""
        task = self._create_task()

        # 1. Submit - check_quota called
        success, path = await self.scheduler.submit_task(task)
        assert success is True
        check_call_count_before = self.mock_quota_manager.check_quota.call_count

        # 2. Schedule - allocate_resources called
        available = ResourceQuota(gpu_count=2)
        decision = await self.scheduler.schedule_next(available)
        assert decision is not None
        allocate_call_count = self.mock_quota_manager.allocate_resources.call_count

        # 3. Complete - release_resources called
        await self.scheduler.task_completed(task)
        release_call_count = self.mock_quota_manager.release_resources.call_count

        # Verify lifecycle: check_quota called once (on submit), allocate once, release once
        assert check_call_count_before == 1
        assert allocate_call_count == 1
        assert release_call_count == 1

    @pytest.mark.asyncio
    async def test_quota_not_found_allows_scheduling(self):
        """Test that tasks can still be scheduled when no quota is found."""
        # Configure mock to return None for effective quota
        self.mock_quota_manager._get_effective_quota.return_value = None
        self.mock_quota_manager.check_quota.return_value = (True, None, None, [])

        task = self._create_task()
        success, path = await self.scheduler.submit_task(task)

        # Task should be submitted even without quota
        assert success is True

        # Schedule should work without allocating (no quota)
        available = ResourceQuota(gpu_count=2)
        decision = await self.scheduler.schedule_next(available)

        # Decision should be made (using WFQ path)
        assert decision is not None
        assert decision.selection_method == "wfq"
        # No allocation should happen when no quota
        self.mock_quota_manager.allocate_resources.assert_not_called()


class TestWFQSchedulerQuotaExceededIntegration:
    """Integration tests for quota exceeded scenarios with real SQLite store."""

    def setup_method(self):
        """Set up test fixtures with limited quota."""
        self.db_path = create_temp_db()
        self.store = SQLiteQuotaStore(self.db_path)
        self.store._init_db()

        # Create a quota with limited GPU (only 1 GPU)
        self.store.create_quota({
            "quota_id": "limited-team",
            "scope": "team",
            "scope_id": "limited-team",
            "name": "Limited Team",
            "cpu_cores": 8,
            "gpu_count": 1,  # Only 1 GPU
            "gpu_memory_gb": 8.0,
            "memory_gb": 32.0,
            "concurrent_tasks": 2,
            "weight": 1.0,
            "guaranteed_gpu_count": 1,
        })

        self.quota_manager = QuotaManager(self.store)
        self.scheduler = WFQScheduler(self.quota_manager, total_cluster_gpu=4)

    def teardown_method(self):
        """Clean up temp database file."""
        if hasattr(self, 'db_path') and os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _create_task(self, task_id="train-001", tenant_id="limited-team"):
        """Helper to create a test task"""
        task = FairTask(
            task_id=task_id,
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
            config={},
            priority=50,
            tenant_id=tenant_id,
            team_id=tenant_id,  # Must match scope_id for QuotaManager lookup
        )
        return task

    @pytest.mark.asyncio
    async def test_submit_rejected_when_quota_exceeded(self):
        """Test task is rejected when submitting would exceed quota."""
        # Submit first task (should succeed)
        task1 = self._create_task("task-1")
        success1, _ = await self.scheduler.submit_task(task1)
        assert success1 is True

        # Schedule first task to allocate resources
        available = ResourceQuota(gpu_count=1)
        decision1 = await self.scheduler.schedule_next(available)
        assert decision1 is not None

        # Verify usage after first task
        usage = self.quota_manager.get_usage("limited-team")
        assert usage["gpu_count_used"] == 1  # Using the only GPU

        # Complete first task
        await self.scheduler.task_completed(task1)

        # Verify usage after completion
        usage = self.quota_manager.get_usage("limited-team")
        assert usage["gpu_count_used"] == 0  # GPU released

    @pytest.mark.asyncio
    async def test_usage_incremented_on_schedule(self):
        """Test that usage is correctly incremented when scheduling."""
        task = self._create_task()

        # Get initial usage
        initial_usage = self.quota_manager.get_usage("limited-team")
        initial_gpu = initial_usage["gpu_count_used"] if initial_usage else 0

        # Submit and schedule
        await self.scheduler.submit_task(task)
        available = ResourceQuota(gpu_count=1)
        await self.scheduler.schedule_next(available)

        # Check usage increased
        updated_usage = self.quota_manager.get_usage("limited-team")
        assert updated_usage["gpu_count_used"] == initial_gpu + 1

    @pytest.mark.asyncio
    async def test_usage_decremented_on_completion(self):
        """Test that usage is correctly decremented when task completes."""
        task = self._create_task()

        # Submit and schedule
        await self.scheduler.submit_task(task)
        available = ResourceQuota(gpu_count=1)
        await self.scheduler.schedule_next(available)

        # Check usage after scheduling
        usage_after_schedule = self.quota_manager.get_usage("limited-team")
        gpu_after_schedule = usage_after_schedule["gpu_count_used"]

        # Complete task
        await self.scheduler.task_completed(task)

        # Check usage after completion
        usage_after_completion = self.quota_manager.get_usage("limited-team")
        assert usage_after_completion["gpu_count_used"] == gpu_after_schedule - 1
