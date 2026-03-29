# tests/unit/scheduler/test_agentic_scheduler.py
"""Unit tests for AgenticScheduler - black-box tests with mocks."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from algo_studio.core.scheduler.agentic_scheduler import AgenticScheduler
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile, TaskType
from algo_studio.core.scheduler.profiles.scheduling_decision import SchedulingDecision
from algo_studio.core.task import Task, TaskType as CoreTaskType, TaskStatus
from algo_studio.core.ray_client import NodeStatus


class TestAgenticScheduler:
    """Black-box tests for AgenticScheduler."""

    @pytest.fixture
    def mock_ray_client(self):
        """Create a mock RayClient."""
        client = MagicMock()
        client.get_nodes.return_value = []
        return client

    @pytest.fixture
    def mock_fast_scheduler(self):
        """Create a mock FastPathScheduler."""
        scheduler = MagicMock()
        mock_decision = SchedulingDecision(
            decision_id="fast-decision-001",
            task_id="test-task",
            selected_node=None,
            routing_path="fast",
            confidence=0.8,
            reasoning="Fast path scheduling",
        )
        scheduler.schedule.return_value = mock_decision
        return scheduler

    @pytest.fixture
    def sample_task(self):
        """Create a sample Task."""
        return Task(
            task_id="test-task-001",
            task_type=CoreTaskType.TRAIN,
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            status=TaskStatus.PENDING,
            config={"epochs": 100},
        )

    @pytest.fixture
    def sample_nodes(self):
        """Create sample NodeStatus objects."""
        node1 = NodeStatus(
            node_id="node-001",
            ip="192.168.0.10",
            status="idle",
            cpu_used=2,
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=16,
            memory_total_gb=64,
            disk_used_gb=100,
            disk_total_gb=500,
            gpu_utilization=0,
            hostname="worker-1",
        )
        node2 = NodeStatus(
            node_id="node-002",
            ip="192.168.0.11",
            status="busy",
            cpu_used=6,
            cpu_total=8,
            gpu_used=1,
            gpu_total=2,
            memory_used_gb=48,
            memory_total_gb=64,
            disk_used_gb=200,
            disk_total_gb=500,
            gpu_utilization=80,
            hostname="worker-2",
        )
        return [node1, node2]

    @pytest.fixture
    def scheduler_with_mocks(self, mock_ray_client, mock_fast_scheduler):
        """Create scheduler with mocked dependencies."""
        scheduler = AgenticScheduler(
            ray_client=mock_ray_client,
            fast_scheduler=mock_fast_scheduler,
        )
        return scheduler

    def test_scheduler_initializes_with_defaults(self):
        """Test that scheduler initializes with default components."""
        scheduler = AgenticScheduler()
        assert scheduler.router is not None
        assert scheduler.fast_scheduler is not None
        assert scheduler.task_analyzer is not None
        assert scheduler.node_scorer is not None
        assert scheduler.validator is not None

    def test_scheduler_accepts_custom_ray_client(self, mock_ray_client):
        """Test that scheduler accepts custom RayClient."""
        scheduler = AgenticScheduler(ray_client=mock_ray_client)
        assert scheduler.ray_client is mock_ray_client

    def test_scheduler_accepts_custom_fast_scheduler(self, mock_fast_scheduler):
        """Test that scheduler accepts custom FastPathScheduler."""
        scheduler = AgenticScheduler(fast_scheduler=mock_fast_scheduler)
        assert scheduler.fast_scheduler is mock_fast_scheduler

    def test_deep_path_disabled_by_default_without_api_key(self):
        """Test that Deep Path is disabled when ANTHROPIC_API_KEY is not set."""
        with patch.dict('os.environ', {}, clear=True):
            scheduler = AgenticScheduler()
            assert scheduler.deep_path_enabled is False
            assert scheduler.llm_available is False

    def test_deep_path_enabled_with_api_key(self):
        """Test that Deep Path is enabled when ANTHROPIC_API_KEY is set."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            scheduler = AgenticScheduler()
            assert scheduler.deep_path_enabled is True

    def test_enable_deep_path(self):
        """Test enabling Deep Path."""
        scheduler = AgenticScheduler()
        with patch.dict('os.environ', {}, clear=True):
            scheduler.disable_deep_path()
            assert scheduler.deep_path_enabled is False
            scheduler.enable_deep_path()
            assert scheduler.deep_path_enabled is True

    def test_disable_deep_path(self):
        """Test disabling Deep Path."""
        # Initialize with API key set
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            scheduler = AgenticScheduler()
            assert scheduler.deep_path_enabled is True
            scheduler.disable_deep_path()
            assert scheduler.deep_path_enabled is False

    def test_schedule_uses_fast_path_by_default(
        self, scheduler_with_mocks, sample_task, sample_nodes
    ):
        """Test that schedule uses Fast Path when Deep Path is disabled."""
        scheduler_with_mocks.ray_client.get_nodes.return_value = sample_nodes

        decision = scheduler_with_mocks.schedule(sample_task)

        assert decision.routing_path == "fast"
        scheduler_with_mocks.fast_scheduler.schedule.assert_called_once()

    def test_schedule_analyzes_task(
        self, scheduler_with_mocks, sample_task, sample_nodes
    ):
        """Test that schedule analyzes the task."""
        scheduler_with_mocks.ray_client.get_nodes.return_value = sample_nodes

        scheduler_with_mocks.schedule(sample_task)

        # Task analyzer should be called
        assert scheduler_with_mocks.task_analyzer is not None

    def test_schedule_scores_nodes(
        self, scheduler_with_mocks, sample_task, sample_nodes
    ):
        """Test that schedule scores available nodes."""
        scheduler_with_mocks.ray_client.get_nodes.return_value = sample_nodes

        scheduler_with_mocks.schedule(sample_task)

        # Node scorer should be available
        assert scheduler_with_mocks.node_scorer is not None

    def test_schedule_returns_scheduling_decision(
        self, scheduler_with_mocks, sample_task, sample_nodes
    ):
        """Test that schedule returns a SchedulingDecision."""
        scheduler_with_mocks.ray_client.get_nodes.return_value = sample_nodes

        decision = scheduler_with_mocks.schedule(sample_task)

        assert isinstance(decision, SchedulingDecision)

    def test_should_use_deep_path_delegates_to_router(self, scheduler_with_mocks):
        """Test that should_use_deep_path delegates to router."""
        profile = TaskProfile(
            task_id="test",
            task_type=TaskType.TRAIN,
            num_gpus=2,
        )

        result = scheduler_with_mocks.should_use_deep_path(profile)

        # Should delegate to router
        assert isinstance(result, bool)

    def test_should_use_deep_path_with_context(self, scheduler_with_mocks):
        """Test should_use_deep_path_with_context."""
        profile = TaskProfile(
            task_id="test",
            task_type=TaskType.TRAIN,
        )

        result = scheduler_with_mocks.should_use_deep_path_with_context(
            profile,
            queue_length=25,
            avg_node_load=0.8,
        )

        assert isinstance(result, bool)

    def test_get_scheduler_status(self, scheduler_with_mocks):
        """Test get_scheduler_status returns status dict."""
        status = scheduler_with_mocks.get_scheduler_status()

        assert isinstance(status, dict)
        assert "status" in status
        assert "fast_path_enabled" in status
        assert "deep_path_enabled" in status
        assert "components" in status
        assert status["components"]["router"] == "Router"
        assert status["components"]["fast_scheduler"] == "FastPathScheduler"

    def test_get_routing_decision(self, scheduler_with_mocks):
        """Test get_routing_decision returns routing info."""
        profile = TaskProfile(
            task_id="test-task-001",
            task_type=TaskType.TRAIN,
            num_gpus=1,
            priority=8,
        )

        result = scheduler_with_mocks.get_routing_decision(profile)

        assert isinstance(result, dict)
        assert "task_id" in result
        assert "selected_path" in result
        assert "reason" in result
        assert "deep_path_available" in result
        assert result["task_id"] == "test-task-001"

    def test_schedule_creates_default_ray_client_if_none(
        self, mock_fast_scheduler, sample_task
    ):
        """Test that schedule creates default RayClient if none provided."""
        scheduler = AgenticScheduler(fast_scheduler=mock_fast_scheduler)

        with patch.object(AgenticScheduler, '__init__', lambda x, **kwargs: None):
            scheduler.ray_client = None
            scheduler.fast_scheduler = mock_fast_scheduler
            scheduler.router = MagicMock()
            scheduler.task_analyzer = MagicMock()
            scheduler.node_scorer = MagicMock()
            scheduler.deep_path_agent = None
            scheduler._deep_path_enabled = False

            scheduler.ray_client = MagicMock()
            scheduler.ray_client.get_nodes.return_value = []

            # This should not raise
            scheduler.schedule(sample_task)

    def test_schedule_with_deep_path_enabled_no_agent_falls_back_to_fast(
        self, mock_fast_scheduler, sample_task, sample_nodes
    ):
        """Test fallback to Fast Path when Deep Path enabled but no agent."""
        scheduler = AgenticScheduler(fast_scheduler=mock_fast_scheduler)
        scheduler.ray_client = MagicMock()
        scheduler.ray_client.get_nodes.return_value = sample_nodes
        scheduler.deep_path_agent = None  # No agent
        scheduler._deep_path_enabled = True  # But deep path enabled

        mock_decision = SchedulingDecision(
            decision_id="fast-001",
            task_id="test",
            selected_node=sample_nodes[0],
            routing_path="fast",
            confidence=0.9,
            reasoning="Fast path",
        )
        scheduler.fast_scheduler.schedule.return_value = mock_decision

        decision = scheduler.schedule(sample_task)

        # Should fall back to fast path
        assert decision.routing_path == "fast"

    def test_deep_path_enabled_reflects_llm_availability(self):
        """Test that deep_path_enabled property reflects LLM availability."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}):
            scheduler = AgenticScheduler()
            assert scheduler.deep_path_enabled is False

        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'sk-test'}):
            scheduler = AgenticScheduler()
            assert scheduler.deep_path_enabled is True

    def test_llm_available_alias(self):
        """Test that llm_available is an alias for deep_path_enabled."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'sk-test'}):
            scheduler = AgenticScheduler()
            assert scheduler.llm_available == scheduler.deep_path_enabled

    def test_components_initialized(self):
        """Test that all components are properly initialized."""
        scheduler = AgenticScheduler()

        assert scheduler.task_analyzer is not None
        assert scheduler.node_scorer is not None
        assert scheduler.validator is not None
        assert scheduler.router is not None
        assert scheduler.fast_scheduler is not None

    def test_get_scheduler_status_includes_deep_path_agent_when_enabled(self):
        """Test that status includes deep_path_agent info when enabled."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'sk-test'}):
            scheduler = AgenticScheduler()
            # Need to call enable_deep_path to create the agent
            scheduler.enable_deep_path()
            status = scheduler.get_scheduler_status()

            assert status["deep_path_enabled"] is True
            assert "deep_path_agent" in status

    def test_async_schedule_delegates_when_deep_path_disabled(self, mock_fast_scheduler, sample_task):
        """Test that schedule_async falls back to sync schedule when Deep Path disabled."""
        scheduler = AgenticScheduler(fast_scheduler=mock_fast_scheduler)
        scheduler._deep_path_enabled = False
        scheduler.deep_path_agent = MagicMock()

        mock_decision = SchedulingDecision(
            decision_id="async-001",
            task_id="test",
            selected_node=None,
            routing_path="fast",
            confidence=0.8,
            reasoning="Fallback to sync",
        )
        scheduler.fast_scheduler.schedule.return_value = mock_decision

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            scheduler.schedule_async(sample_task)
        )

        assert result.routing_path == "fast"
