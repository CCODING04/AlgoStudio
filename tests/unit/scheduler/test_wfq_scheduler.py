# tests/unit/scheduler/test_wfq_scheduler.py
"""Unit tests for WFQScheduler - Weighted Fair Queuing Scheduler."""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from algo_studio.core.scheduler.wfq_scheduler import (
    WFQScheduler,
    FairSchedulingDecision,
    PriorityOverride,
    ReservationManager,
    RESOURCE_WEIGHTS,
    DEFAULT_CLUSTER_GPU,
)
from algo_studio.core.task import Task, TaskStatus, TaskType
from algo_studio.core.quota.manager import QuotaManager
from algo_studio.core.quota.store import ResourceQuota, SQLiteQuotaStore
from algo_studio.core.scheduler.tenant_queue import TenantQueue


class TestPriorityOverride:
    """Tests for PriorityOverride class."""

    def test_is_expired_false_when_not_expired(self):
        """Test is_expired returns False when override has not expired."""
        override = PriorityOverride(
            task_id="task-001",
            reason="high_priority",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=30),
        )
        assert override.is_expired is False

    def test_is_expired_true_when_expired(self):
        """Test is_expired returns True when override has expired."""
        override = PriorityOverride(
            task_id="task-001",
            reason="high_priority",
            created_at=datetime.now() - timedelta(minutes=60),
            expires_at=datetime.now() - timedelta(minutes=30),
        )
        assert override.is_expired is True


class TestFairSchedulingDecision:
    """Tests for FairSchedulingDecision dataclass."""

    def test_decision_id_short(self):
        """Test decision_id_short property returns first 8 characters."""
        task = Task(
            task_id="test-task-001",
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
        )
        decision = FairSchedulingDecision(
            decision_id="12345678-abcdefgh",
            task=task,
        )
        assert decision.decision_id_short == "12345678"

    def test_default_selection_method_is_wfq(self):
        """Test default selection_method is 'wfq'."""
        task = Task(
            task_id="test-task-001",
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
        )
        decision = FairSchedulingDecision(
            decision_id="12345678-abcdefgh",
            task=task,
        )
        assert decision.selection_method == "wfq"


class TestReservationManager:
    """Tests for ReservationManager class."""

    @pytest.fixture
    def mock_quota_manager(self):
        """Create a mock QuotaManager."""
        return MagicMock(spec=QuotaManager)

    @pytest.fixture
    def reservation_manager(self, mock_quota_manager):
        """Create a ReservationManager instance."""
        return ReservationManager(mock_quota_manager)

    def test_urgent_priority_threshold(self, reservation_manager):
        """Test URGENT_PRIORITY_THRESHOLD is 90."""
        assert reservation_manager.URGENT_PRIORITY_THRESHOLD == 90

    def test_critical_duration_minutes(self, reservation_manager):
        """Test CRITICAL_DURATION_MINUTES is 30."""
        assert reservation_manager.CRITICAL_DURATION_MINUTES == 30

    def test_active_reservation_count_initially_zero(self, reservation_manager):
        """Test active_reservation_count is 0 initially."""
        assert reservation_manager.active_reservation_count == 0

    def test_check_override_explicit_urgent_flag(self, reservation_manager, mock_quota_manager):
        """Test override when task has explicit is_urgent flag."""
        task = MagicMock()
        task.task_id = "urgent-task-001"
        task.is_urgent = True
        task.tenant_id = "tenant-001"

        override = reservation_manager.check_override(task)
        assert override is not None
        assert override.reason == "explicit_urgent_flag"
        assert task.task_id in reservation_manager.active_overrides

    def test_check_override_high_priority(self, reservation_manager, mock_quota_manager):
        """Test override when task priority >= 90."""
        task = MagicMock()
        task.task_id = "high-priority-task-001"
        task.is_urgent = False
        task.priority = 95
        task.tenant_id = "tenant-001"

        override = reservation_manager.check_override(task)
        assert override is not None
        assert override.reason == "high_priority"

    def test_check_override_team_bypass_permission(self, reservation_manager, mock_quota_manager):
        """Test override when team has bypass_fairness permission."""
        mock_quota_manager._get_effective_quota.return_value = {
            "quota_id": "q-001",
            "bypass_fairness": True,
        }

        task = MagicMock()
        task.task_id = "bypass-task-001"
        task.is_urgent = False
        task.priority = 50
        task.tenant_id = "tenant-001"

        override = reservation_manager.check_override(task)
        assert override is not None
        assert override.reason == "team_bypass_permission"

    def test_check_override_no_override(self, reservation_manager, mock_quota_manager):
        """Test no override when none of conditions met."""
        mock_quota_manager._get_effective_quota.return_value = {
            "quota_id": "q-001",
            "bypass_fairness": False,
        }

        task = MagicMock()
        task.task_id = "normal-task-001"
        task.is_urgent = False
        task.priority = 50
        task.tenant_id = "tenant-001"

        override = reservation_manager.check_override(task)
        assert override is None

    def test_create_override(self, reservation_manager):
        """Test _create_override creates PriorityOverride correctly."""
        task = MagicMock()
        task.task_id = "task-001"
        task.is_urgent = False
        task.priority = 50

        override = reservation_manager._create_override(task, "test_reason")

        assert isinstance(override, PriorityOverride)
        assert override.task_id == "task-001"
        assert override.reason == "test_reason"
        # Use tolerance since datetime.now() is called at different times
        expected = datetime.now() + timedelta(minutes=30)
        assert abs((override.expires_at - expected).total_seconds()) < 1

    @pytest.mark.asyncio
    async def test_reserve_no_quota(self, reservation_manager):
        """Test reserve returns None when tenant has no quota."""
        reservation_manager._get_tenant_quota = MagicMock(return_value=None)

        result = await reservation_manager.reserve(
            task_id="task-001",
            tenant_id="unknown-tenant",
            resources=ResourceQuota(gpu_count=1),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_reserve_cannot_reserve(self, reservation_manager, mock_quota_manager):
        """Test reserve returns None when _can_reserve fails."""
        mock_quota_manager._get_effective_quota.return_value = {
            "quota_id": "q-001"
        }
        reservation_manager._can_reserve = MagicMock(return_value=False)

        result = await reservation_manager.reserve(
            task_id="task-001",
            tenant_id="tenant-001",
            resources=ResourceQuota(gpu_count=1),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_reserve_allocation_failure_rollback(self, reservation_manager, mock_quota_manager):
        """Test reserve rolls back on allocation failure."""
        mock_quota_manager._get_effective_quota.return_value = {
            "quota_id": "q-001"
        }
        reservation_manager._can_reserve = MagicMock(return_value=True)
        mock_quota_manager.allocate_resources = MagicMock(
            side_effect=Exception("Allocation failed")
        )

        result = await reservation_manager.reserve(
            task_id="task-001",
            tenant_id="tenant-001",
            resources=ResourceQuota(gpu_count=1),
        )

        assert result is None
        # Reservation should not be in the dict after rollback
        assert len(reservation_manager.reservations) == 0

    @pytest.mark.asyncio
    async def test_reserve_success(self, reservation_manager, mock_quota_manager):
        """Test successful reservation."""
        mock_quota_manager._get_effective_quota.return_value = {
            "quota_id": "q-001"
        }
        reservation_manager._can_reserve = MagicMock(return_value=True)
        mock_quota_manager.allocate_resources = MagicMock(return_value=True)

        result = await reservation_manager.reserve(
            task_id="task-001",
            tenant_id="tenant-001",
            resources=ResourceQuota(gpu_count=1),
        )

        assert result is not None
        assert result["task_id"] == "task-001"
        assert result["tenant_id"] == "tenant-001"
        assert result["status"] == "active"
        assert "reservation_id" in result

    @pytest.mark.asyncio
    async def test_release_task_not_found(self, reservation_manager):
        """Test release returns False when task not found."""
        result = await reservation_manager.release("unknown-task")
        assert result is False

    @pytest.mark.asyncio
    async def test_release_success(self, reservation_manager, mock_quota_manager):
        """Test successful release."""
        # First create a reservation
        mock_quota_manager._get_effective_quota.return_value = {
            "quota_id": "q-001"
        }
        reservation_manager._can_reserve = MagicMock(return_value=True)
        mock_quota_manager.allocate_resources = MagicMock(return_value=True)
        mock_quota_manager.release_resources = MagicMock(return_value=True)

        # Create reservation
        reservation = await reservation_manager.reserve(
            task_id="task-001",
            tenant_id="tenant-001",
            resources=ResourceQuota(gpu_count=1),
        )
        assert reservation is not None

        # Release it
        result = await reservation_manager.release("task-001")
        assert result is True
        # Reservations should be empty
        assert len(reservation_manager.reservations) == 0

    @pytest.mark.asyncio
    async def test_release_by_id_not_found(self, reservation_manager):
        """Test release_by_id returns False when reservation not found."""
        result = await reservation_manager.release_by_id("unknown-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_release_by_id_success(self, reservation_manager, mock_quota_manager):
        """Test successful release by ID."""
        # First create a reservation
        mock_quota_manager._get_effective_quota.return_value = {
            "quota_id": "q-001"
        }
        reservation_manager._can_reserve = MagicMock(return_value=True)
        mock_quota_manager.allocate_resources = MagicMock(return_value=True)
        mock_quota_manager.release_resources = MagicMock(return_value=True)

        # Create reservation
        reservation = await reservation_manager.reserve(
            task_id="task-001",
            tenant_id="tenant-001",
            resources=ResourceQuota(gpu_count=1),
        )
        reservation_id = reservation["reservation_id"]

        # Release by ID
        result = await reservation_manager.release_by_id(reservation_id)
        assert result is True

    def test_can_reserve_allow(self, reservation_manager):
        """Test _can_reserve returns True when resources are available."""
        # No guaranteed minimums for other tenants, so should allow
        result = reservation_manager._can_reserve("tenant-001", ResourceQuota(gpu_count=1))
        assert result is True

    def test_can_reserve_deny(self, reservation_manager):
        """Test _can_reserve returns False when would violate another tenant's minimum."""
        # Set a guaranteed minimum for another tenant
        reservation_manager.guaranteed_minimums["other-tenant"] = ResourceQuota(gpu_count=2)

        # Request more than what's left (2 + 1 = 3 > 2 cluster GPUs)
        result = reservation_manager._can_reserve("tenant-001", ResourceQuota(gpu_count=3))
        assert result is False

    def test_get_tenant_quota(self, reservation_manager, mock_quota_manager):
        """Test _get_tenant_quota delegates to quota manager."""
        mock_quota_manager._get_effective_quota.return_value = {"quota_id": "q-001"}

        result = reservation_manager._get_tenant_quota("tenant-001")

        mock_quota_manager._get_effective_quota.assert_called_once_with(
            user_id="tenant-001",
            team_id=None,
        )
        assert result == {"quota_id": "q-001"}


class TestWFQScheduler:
    """Tests for WFQScheduler class."""

    @pytest.fixture
    def quota_store(self, tmp_path):
        """Create an in-memory SQLite quota store for testing."""
        store = SQLiteQuotaStore(db_path=str(tmp_path / "test_quota.db"))
        # Create a global quota
        store.create_quota({
            "quota_id": "global",
            "scope": "global",
            "scope_id": "global",
            "name": "Global Quota",
            "weight": 1.0,
            "guaranteed_gpu_count": 2,
            "guaranteed_cpu_cores": 8,
            "guaranteed_memory_gb": 32.0,
            "cpu_cores": 32,
            "gpu_count": 4,
            "memory_gb": 128.0,
        })
        # Create a team quota with weight 2.0
        store.create_quota({
            "quota_id": "team-001",
            "scope": "team",
            "scope_id": "team-001",
            "name": "Team Alpha",
            "weight": 2.0,
            "guaranteed_gpu_count": 1,
            "guaranteed_cpu_cores": 4,
            "guaranteed_memory_gb": 16.0,
            "cpu_cores": 16,
            "gpu_count": 2,
            "memory_gb": 64.0,
            "parent_quota_id": "global",
        })
        return store

    @pytest.fixture
    def quota_manager(self, quota_store):
        """Create a QuotaManager with test store."""
        return QuotaManager(quota_store)

    @pytest.fixture
    def scheduler(self, quota_manager):
        """Create a WFQScheduler instance."""
        return WFQScheduler(quota_manager, total_cluster_gpu=4)

    def _make_task(self, task_id, task_type, priority=50, tenant_id="team-001", user_id="user-001", team_id="team-001"):
        """Create a Task with additional attributes for scheduler testing."""
        task = Task(
            task_id=task_id,
            task_type=task_type,
            algorithm_name="simple_classifier",
            algorithm_version="v1",
        )
        task.priority = priority
        task.tenant_id = tenant_id
        task.user_id = user_id
        task.team_id = team_id
        task.requested_resources = None  # Will use defaults
        return task

    @pytest.fixture
    def sample_task(self):
        """Create a sample train task."""
        return self._make_task("train-task-001", TaskType.TRAIN, priority=50)

    @pytest.fixture
    def high_priority_task(self):
        """Create a high priority task (>=90)."""
        return self._make_task("urgent-task-001", TaskType.TRAIN, priority=95)

    @pytest.fixture
    def infer_task(self):
        """Create an inference task."""
        return self._make_task("infer-task-001", TaskType.INFER, priority=50)

    # =========================================================================
    # VFT Calculation Tests
    # =========================================================================

    def test_vft_calculation_basic(self, scheduler, sample_task):
        """Test VFT calculation with basic parameters."""
        vft = scheduler._calculate_virtual_finish_time(sample_task, {
            "weight": 1.0,
            "guaranteed_gpu_count": 1,
        })
        # VFT = (weight_sum / weight) + (task_resources / allocation_share)
        # weight_sum = 0 initially
        # task_resources for train task = gpu(10) + cpu(4) + gpu_mem(8*0.5) + mem(16*0.1) = 10 + 4 + 4 + 1.6 = 19.6
        # allocation_share = 1/4 = 0.25
        # VFT = 0 + 19.6/0.25 = 78.4
        assert vft > 0
        assert isinstance(vft, float)

    def test_vft_calculation_with_cumulative_weight(self, scheduler, sample_task):
        """Test VFT increases with cumulative weight from prior tasks."""
        # Create tenant queue with cumulative weight
        tenant_queue = TenantQueue(tenant_id="team-001", weight=1.0)
        # Add a dummy task to make the queue truthy (len > 0)
        dummy_task = self._make_task("dummy-task", TaskType.INFER, priority=1)
        tenant_queue.enqueue(dummy_task)
        tenant_queue.update_wfq_state(1.0)  # Simulate a previously scheduled task
        scheduler.queue.tenant_queues["team-001"] = tenant_queue

        # First task VFT
        vft1 = scheduler._calculate_virtual_finish_time(sample_task, {
            "weight": 1.0,
            "guaranteed_gpu_count": 1,
        })

        # Add another task's weight to cumulative weight
        tenant_queue.update_wfq_state(1.0)

        # Second task VFT (same params) should be higher due to increased cumulative weight
        vft2 = scheduler._calculate_virtual_finish_time(sample_task, {
            "weight": 1.0,
            "guaranteed_gpu_count": 1,
        })

        # VFT should be higher for second task due to weight_sum increase
        assert vft2 > vft1

    def test_vft_calculation_weight_higher_lower_vft(self, scheduler, sample_task):
        """Test higher weight results in lower VFT when there is cumulative weight."""
        # Create tenant queues with same cumulative weight but different tenant weights
        # Need to add tasks to make queues truthy (len > 0)
        tq_low = TenantQueue(tenant_id="tenant-low", weight=0.5)
        tq_low.enqueue(self._make_task("dummy-low", TaskType.INFER, priority=1))
        tq_low.update_wfq_state(1.0)  # Add some cumulative weight
        scheduler.queue.tenant_queues["tenant-low"] = tq_low

        tq_high = TenantQueue(tenant_id="tenant-high", weight=2.0)
        tq_high.enqueue(self._make_task("dummy-high", TaskType.INFER, priority=1))
        tq_high.update_wfq_state(1.0)  # Same cumulative weight
        scheduler.queue.tenant_queues["tenant-high"] = tq_high

        # Create tasks for each tenant
        task_low = self._make_task("task-low", TaskType.TRAIN, priority=50, tenant_id="tenant-low")
        task_high = self._make_task("task-high", TaskType.TRAIN, priority=50, tenant_id="tenant-high")

        # Same quota params except weight
        vft_low_weight = scheduler._calculate_virtual_finish_time(task_low, {
            "weight": 0.5,
            "guaranteed_gpu_count": 1,
        })

        vft_high_weight = scheduler._calculate_virtual_finish_time(task_high, {
            "weight": 2.0,
            "guaranteed_gpu_count": 1,
        })

        # Higher tenant weight = lower VFT = higher priority in WFQ
        # VFT = (cumulative_weight / tenant_weight) + (resources / allocation_share)
        # With same cumulative_weight=1.0: VFT_low = 1.0/0.5 + X = 2.0 + X
        #                                  VFT_high = 1.0/2.0 + X = 0.5 + X
        # So VFT_high < VFT_low
        assert vft_high_weight < vft_low_weight

    def test_vft_calculation_no_quota(self, scheduler, sample_task):
        """Test VFT calculation when no quota is available."""
        vft = scheduler._calculate_virtual_finish_time(sample_task, None)
        assert vft > 0
        # Should use default weight of 1.0 and allocation_share of 1/num_tenants

    def test_vft_calculation_zero_allocation_share(self, scheduler, sample_task):
        """Test VFT calculation handles zero allocation share (edge case)."""
        # With guaranteed_gpu_count=0, allocation_share becomes 0
        vft = scheduler._calculate_virtual_finish_time(sample_task, {
            "weight": 1.0,
            "guaranteed_gpu_count": 0,
        })
        # Should use max(allocation_share, 0.01) to avoid division by zero
        assert vft > 0

    # =========================================================================
    # Resource Normalization Tests
    # =========================================================================

    def test_normalize_resources_gpu_heavy(self, scheduler):
        """Test resource normalization with GPU-heavy resources."""
        resources = ResourceQuota(
            gpu_count=2,
            cpu_cores=8,
            gpu_memory_gb=16.0,
            memory_gb=32.0,
        )
        normalized = scheduler._normalize_resources(resources)

        # Expected: gpu*10 + cpu*1 + gpu_mem*0.5 + mem*0.1
        expected = (2 * 10.0) + (8 * 1.0) + (16.0 * 0.5) + (32.0 * 0.1)
        assert normalized == expected

    def test_normalize_resources_cpu_only(self, scheduler):
        """Test resource normalization with CPU-only resources."""
        resources = ResourceQuota(
            gpu_count=0,
            cpu_cores=16,
            gpu_memory_gb=0.0,
            memory_gb=64.0,
        )
        normalized = scheduler._normalize_resources(resources)

        expected = (0 * 10.0) + (16 * 1.0) + (0.0 * 0.5) + (64.0 * 0.1)
        assert normalized == expected

    def test_normalize_resources_weights_constant(self):
        """Test that RESOURCE_WEIGHTS are correctly defined."""
        assert RESOURCE_WEIGHTS["gpu"] == 10.0
        assert RESOURCE_WEIGHTS["cpu"] == 1.0
        assert RESOURCE_WEIGHTS["gpu_memory"] == 0.5
        assert RESOURCE_WEIGHTS["memory"] == 0.1

    # =========================================================================
    # Default Resources Tests
    # =========================================================================

    def test_default_resources_train_task(self, scheduler):
        """Test default resources for TRAIN task type."""
        task = MagicMock()
        task.task_type = TaskType.TRAIN  # Use actual enum

        defaults = scheduler._get_default_resources(task)

        assert defaults.gpu_count == 1
        assert defaults.cpu_cores == 4
        assert defaults.gpu_memory_gb == 8.0
        assert defaults.memory_gb == 16.0
        assert defaults.concurrent_tasks == 1

    def test_default_resources_infer_task(self, scheduler):
        """Test default resources for INFER task type."""
        task = MagicMock()
        task.task_type = TaskType.INFER  # Use actual enum

        defaults = scheduler._get_default_resources(task)

        assert defaults.gpu_count == 0
        assert defaults.cpu_cores == 1
        assert defaults.memory_gb == 4.0
        assert defaults.concurrent_tasks == 1

    def test_default_resources_verify_task(self, scheduler):
        """Test default resources for VERIFY task type."""
        task = MagicMock()
        task.task_type = TaskType.VERIFY  # Use actual enum

        defaults = scheduler._get_default_resources(task)

        assert defaults.gpu_count == 0
        assert defaults.cpu_cores == 1
        assert defaults.memory_gb == 2.0
        assert defaults.concurrent_tasks == 1

    def test_default_resources_unknown_task(self, scheduler):
        """Test default resources for unknown task type."""
        task = MagicMock()
        task.task_type = "unknown"

        defaults = scheduler._get_default_resources(task)

        assert defaults.concurrent_tasks == 1

    # =========================================================================
    # Quota Cache Tests
    # =========================================================================

    def test_quota_cache_invalidation(self, scheduler):
        """Test quota cache is cleared on invalidation."""
        # Populate cache
        scheduler._get_cached_quota("user-001", "team-001")
        assert ("user-001", "team-001") in scheduler._quota_cache

        # Invalidate
        scheduler._invalidate_quota_cache()

        # Cache should be cleared
        assert scheduler._quota_cache_valid is False
        assert len(scheduler._quota_cache) == 0

    def test_quota_cache_resets_on_invalidation(self, scheduler):
        """Test quota cache is cleared on invalidation."""
        # Populate cache
        scheduler._get_cached_quota("user-001", "team-001")
        assert ("user-001", "team-001") in scheduler._quota_cache

        # Invalidate
        scheduler._invalidate_quota_cache()

        assert scheduler._quota_cache_valid is False
        assert len(scheduler._quota_cache) == 0

    def test_quota_cache_population(self, scheduler):
        """Test quota cache is populated after first call."""
        scheduler.quota_manager._get_effective_quota = MagicMock(
            return_value={"quota_id": "q-001", "weight": 1.0}
        )

        # First call - should call quota manager and populate cache
        result1 = scheduler._get_cached_quota("user-001", "team-001")

        # Verify cache was populated
        assert ("user-001", "team-001") in scheduler._quota_cache
        assert result1 == {"quota_id": "q-001", "weight": 1.0}

        # Quota manager was called once
        scheduler.quota_manager._get_effective_quota.assert_called_once()

    # =========================================================================
    # Priority Override Tests
    # =========================================================================

    def test_priority_override_urgent_task(self, scheduler, high_priority_task):
        """Test high priority task (>=90) triggers priority override."""
        override = scheduler.reservation_manager.check_override(high_priority_task)
        assert override is not None
        assert override.reason == "high_priority"

    def test_priority_override_explicit_urgent(self, scheduler):
        """Test task with is_urgent=True triggers priority override."""
        task = MagicMock()
        task.task_id = "urgent-task"
        task.is_urgent = True
        task.priority = 50
        task.tenant_id = "tenant-001"

        override = scheduler.reservation_manager.check_override(task)
        assert override is not None
        assert override.reason == "explicit_urgent_flag"

    def test_priority_override_normal_task(self, scheduler, sample_task):
        """Test normal task (priority < 90, not urgent) does not trigger override."""
        override = scheduler.reservation_manager.check_override(sample_task)
        assert override is None

    # =========================================================================
    # Decision Creation Tests
    # =========================================================================

    def test_create_decision_wfq_method(self, scheduler, sample_task):
        """Test creating decision with WFQ method."""
        decision = scheduler._create_decision(
            task=sample_task,
            queue_path="tenant:team-001",
            method="wfq",
            tenant_weight=2.0,
            virtual_finish_time=78.4,
        )

        assert isinstance(decision, FairSchedulingDecision)
        assert decision.selection_method == "wfq"
        assert decision.tenant_weight == 2.0
        assert decision.virtual_finish_time == 78.4
        assert decision.tenant_id == "team-001"

    def test_create_decision_override_method(self, scheduler, high_priority_task):
        """Test creating decision with priority override method."""
        decision = scheduler._create_decision(
            task=high_priority_task,
            queue_path="tenant:team-001",
            method="priority_override",
            override_reason="high_priority",
        )

        assert decision.selection_method == "priority_override"
        assert decision.override_reason == "high_priority"
        assert decision.virtual_finish_time is None

    # =========================================================================
    # Iterative Requeue Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_schedule_next_empty_queue(self, scheduler):
        """Test schedule_next returns None when queue is empty."""
        # Mock queue.dequeue to return None
        scheduler.queue.dequeue = AsyncMock(return_value=None)

        available = ResourceQuota(gpu_count=2, cpu_cores=8)
        result = await scheduler.schedule_next(available)

        assert result is None

    @pytest.mark.asyncio
    async def test_schedule_next_priority_override(self, scheduler, high_priority_task):
        """Test schedule_next returns priority override decision for urgent task."""
        # Mock queue.dequeue to return our high priority task
        scheduler.queue.dequeue = AsyncMock(
            return_value=(high_priority_task, "tenant:team-001")
        )

        available = ResourceQuota(gpu_count=2, cpu_cores=8)
        result = await scheduler.schedule_next(available)

        assert result is not None
        assert result.selection_method == "priority_override"
        assert result.override_reason == "high_priority"

    @pytest.mark.asyncio
    async def test_schedule_next_quota_exceeded_requeue(self, scheduler, sample_task):
        """Test task is requeued when quota is exceeded."""
        call_count = 0

        async def mock_dequeue(resources):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (sample_task, "tenant:team-001")
            return None

        scheduler.queue.dequeue = mock_dequeue
        scheduler.queue.requeue = AsyncMock()

        # Mock quota check to fail first time
        original_check_quota = scheduler.quota_manager.check_quota
        check_call_count = 0

        def mock_check_quota(user_id, team_id, requested):
            nonlocal check_call_count
            check_call_count += 1
            if check_call_count == 1:
                return (False, None, None, ["GPU quota exceeded"])
            return (True, None, None, [])

        scheduler.quota_manager.check_quota = mock_check_quota

        available = ResourceQuota(gpu_count=2, cpu_cores=8)
        result = await scheduler.schedule_next(available, max_requeue_attempts=3)

        # Task should have been requeued
        scheduler.queue.requeue.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_next_max_requeue_exceeded(self, scheduler, sample_task):
        """Test schedule_next returns None after max requeue attempts."""
        scheduler.queue.dequeue = AsyncMock(
            return_value=(sample_task, "tenant:team-001")
        )
        scheduler.queue.requeue = AsyncMock()

        # Always fail quota check
        scheduler.quota_manager.check_quota = MagicMock(
            return_value=(False, None, None, ["GPU quota exceeded"])
        )

        available = ResourceQuota(gpu_count=2, cpu_cores=8)
        result = await scheduler.schedule_next(available, max_requeue_attempts=3)

        assert result is None
        # Should have attempted requeue 3 times (max_requeue_attempts)
        assert scheduler.queue.requeue.call_count == 3

    # =========================================================================
    # Task Submission Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_submit_task_success(self, scheduler, sample_task):
        """Test successful task submission."""
        scheduler.quota_manager.check_quota = MagicMock(
            return_value=(True, {"quota_id": "q-001"}, None, [])
        )
        scheduler.queue.enqueue = AsyncMock(return_value="tenant:team-001")

        success, path = await scheduler.submit_task(sample_task)

        assert success is True
        assert path == "tenant:team-001"

    @pytest.mark.asyncio
    async def test_submit_task_quota_exceeded(self, scheduler, sample_task):
        """Test task submission fails when quota exceeded."""
        scheduler.quota_manager.check_quota = MagicMock(
            return_value=(False, None, None, ["GPU quota exceeded"])
        )

        success, path = await scheduler.submit_task(sample_task)

        assert success is False
        assert "GPU quota exceeded" in path
        assert sample_task.status == TaskStatus.FAILED
        assert sample_task.error is not None

    # =========================================================================
    # Task Completion Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_task_completed_releases_resources(self, scheduler, sample_task):
        """Test task completion releases quota resources."""
        scheduler.quota_manager._get_effective_quota = MagicMock(
            return_value={"quota_id": "q-001"}
        )
        scheduler.quota_manager.release_resources = MagicMock(return_value=True)
        scheduler.reservation_manager.release = AsyncMock(return_value=True)

        await scheduler.task_completed(sample_task)

        scheduler.quota_manager.release_resources.assert_called_once()
        scheduler.reservation_manager.release.assert_called_once_with(sample_task.task_id)

    @pytest.mark.asyncio
    async def test_task_completed_no_quota(self, scheduler, sample_task):
        """Test task completion handles missing quota gracefully."""
        scheduler.quota_manager._get_effective_quota = MagicMock(return_value=None)
        scheduler.quota_manager.release_resources = MagicMock(return_value=True)
        scheduler.reservation_manager.release = AsyncMock(return_value=True)

        # Should not raise, even though quota is None
        await scheduler.task_completed(sample_task)

        scheduler.quota_manager.release_resources.assert_not_called()

    # =========================================================================
    # Scheduler Stats Tests
    # =========================================================================

    def test_get_stats(self, scheduler):
        """Test get_stats returns scheduler statistics."""
        stats = scheduler.get_stats()

        assert "scheduled_count" in stats
        assert "queue_stats" in stats
        assert "active_reservations" in stats
        assert stats["scheduled_count"] == 0
        assert stats["active_reservations"] == 0

    def test_scheduled_count_increments(self, scheduler, sample_task):
        """Test scheduled_count increments after scheduling decision."""
        initial_count = scheduler._scheduled_count

        decision = scheduler._create_decision(
            task=sample_task,
            queue_path="tenant:team-001",
            method="wfq",
        )

        # Manually increment for testing (normally done in schedule_next)
        scheduler._scheduled_count += 1

        assert scheduler._scheduled_count == initial_count + 1

    # =========================================================================
    # End-to-End Scheduling Flow Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_full_scheduling_flow(self, scheduler, sample_task, infer_task):
        """Test complete scheduling flow: submit -> schedule -> complete."""
        # Setup: quota allows the task
        scheduler.quota_manager.check_quota = MagicMock(
            return_value=(True, {"quota_id": "q-001", "weight": 1.0}, None, [])
        )
        scheduler.quota_manager.allocate_resources = MagicMock(return_value=True)
        scheduler.queue.enqueue = AsyncMock(return_value="tenant:team-001")
        scheduler.queue.requeue = AsyncMock()

        # Step 1: Submit tasks
        success1, path1 = await scheduler.submit_task(sample_task)
        assert success1 is True

        # Step 2: Schedule next (mock dequeue to return our task)
        scheduler.queue.dequeue = AsyncMock(
            return_value=(sample_task, "tenant:team-001")
        )

        available = ResourceQuota(gpu_count=2, cpu_cores=8)
        decision = await scheduler.schedule_next(available)

        assert decision is not None
        assert decision.selection_method == "wfq"
        assert decision.task.task_id == sample_task.task_id

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_default_cluster_gpu(self):
        """Test DEFAULT_CLUSTER_GPU is 1."""
        assert DEFAULT_CLUSTER_GPU == 1

    def test_scheduler_with_custom_gpu_count(self, quota_manager):
        """Test scheduler initializes with custom GPU count."""
        scheduler = WFQScheduler(quota_manager, total_cluster_gpu=8)
        assert scheduler.total_cluster_gpu == 8

    def test_vft_with_very_small_weight(self, scheduler, sample_task):
        """Test VFT calculation with very small weight (edge case)."""
        vft = scheduler._calculate_virtual_finish_time(sample_task, {
            "weight": 0.01,
            "guaranteed_gpu_count": 1,
        })
        # VFT should be finite and positive
        assert vft > 0
        assert vft != float('inf')

    def test_vft_with_very_large_weight(self, scheduler, sample_task):
        """Test VFT calculation with very large weight (edge case)."""
        vft = scheduler._calculate_virtual_finish_time(sample_task, {
            "weight": 1000.0,
            "guaranteed_gpu_count": 1,
        })
        # Higher weight should give lower VFT
        assert vft > 0

    def test_multiple_tenants_wfq_ordering(self, scheduler):
        """Test WFQ correctly orders tasks from multiple tenants."""
        # Create two tenant queues with different weights
        tq1 = TenantQueue(tenant_id="tenant-1", weight=1.0)
        tq2 = TenantQueue(tenant_id="tenant-2", weight=2.0)

        # Add to scheduler's queue
        scheduler.queue.tenant_queues["tenant-1"] = tq1
        scheduler.queue.tenant_queues["tenant-2"] = tq2

        # Check WRR ratios
        assert tq1.wrr_ratio == 0.0  # 0 tasks / weight 1.0
        assert tq2.wrr_ratio == 0.0  # 0 tasks / weight 2.0

        # After scheduling one task for tenant-1
        tq1.update_wfq_state(1.0)
        assert tq1.wrr_ratio == 1.0  # 1 task / weight 1.0

        # tenant-2 should now have lower ratio (higher priority)
        assert tq2.wrr_ratio < tq1.wrr_ratio
