# tests/test_scheduler/test_agentic_scheduler.py
"""Tests for AgenticScheduler"""

import pytest
from unittest.mock import MagicMock, patch
from algo_studio.core.task import Task, TaskType
from algo_studio.core.ray_client import NodeStatus, RayClient
from algo_studio.core.scheduler.agentic_scheduler import AgenticScheduler


class TestAgenticScheduler:
    """Test suite for AgenticScheduler"""

    def setup_method(self):
        """Set up test fixtures"""
        self.scheduler = AgenticScheduler()

    def _create_node(
        self,
        node_id="node-1",
        ip="192.168.0.101",
        hostname="worker-1",
        status="idle",
        cpu_used=8,
        cpu_total=24,
        gpu_used=0,
        gpu_total=1,
        memory_used_gb=16,
        memory_total_gb=31,
        disk_used_gb=100,
        disk_total_gb=500,
    ):
        """Helper to create NodeStatus"""
        return NodeStatus(
            node_id=node_id,
            ip=ip,
            hostname=hostname,
            status=status,
            cpu_used=cpu_used,
            cpu_total=cpu_total,
            gpu_used=gpu_used,
            gpu_total=gpu_total,
            memory_used_gb=memory_used_gb,
            memory_total_gb=memory_total_gb,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
        )

    def _create_task(
        self,
        task_id="train-001",
        task_type=TaskType.TRAIN,
        config=None,
    ):
        """Helper to create Task"""
        return Task(
            task_id=task_id,
            task_type=task_type,
            algorithm_name="yolo",
            algorithm_version="v1",
            config=config or {},
        )

    def test_schedule_with_mock_ray_client(self):
        """Test scheduling with mocked Ray client"""
        mock_client = MagicMock(spec=RayClient)
        mock_client.get_nodes.return_value = [
            self._create_node(hostname="worker-1", gpu_total=1, gpu_used=0)
        ]

        scheduler = AgenticScheduler(ray_client=mock_client)
        task = self._create_task()

        decision = scheduler.schedule(task)

        assert decision.is_valid is True
        mock_client.get_nodes.assert_called_once()

    def test_schedule_without_ray_client_creates_default(self):
        """Test that scheduler creates default Ray client if not provided"""
        scheduler = AgenticScheduler()
        task = self._create_task()

        # This will try to connect to Ray - we patch to avoid that
        with patch.object(scheduler, 'ray_client', MagicMock(spec=RayClient)) as mock_client:
            mock_client.get_nodes.return_value = [self._create_node()]
            decision = scheduler.schedule(task)
            assert decision is not None

    def test_should_use_deep_path_delegates_to_router(self):
        """Test that should_use_deep_path delegates to router"""
        from algo_studio.core.scheduler.profiles.task_profile import TaskProfile, TaskType

        profile = TaskProfile(
            task_id="test",
            task_type=TaskType.TRAIN,
        )

        # Simple task should use Fast Path
        result = self.scheduler.should_use_deep_path(profile)

        assert result is False

    def test_should_use_deep_path_with_context(self):
        """Test should_use_deep_path_with_context"""
        from algo_studio.core.scheduler.profiles.task_profile import TaskProfile, TaskType

        profile = TaskProfile(
            task_id="test",
            task_type=TaskType.TRAIN,
            preferred_nodes=["worker-1"],
        )

        result = self.scheduler.should_use_deep_path_with_context(profile, 0, 0.0)

        assert result is True

    def test_get_scheduler_status(self):
        """Test getting scheduler status"""
        status = self.scheduler.get_scheduler_status()

        assert status["status"] == "healthy"
        assert status["fast_path_enabled"] is True
        assert "components" in status
        assert status["components"]["task_analyzer"] == "DefaultTaskAnalyzer"
        assert status["components"]["node_scorer"] == "MultiDimNodeScorer"

    def test_schedule_async_delegates_to_sync(self):
        """Test that async schedule delegates to sync schedule"""
        scheduler = AgenticScheduler()
        task = self._create_task()

        with patch.object(scheduler, 'schedule', wraps=scheduler.schedule) as mock_schedule:
            with patch.object(scheduler, 'ray_client', MagicMock(spec=RayClient)) as mock_client:
                mock_client.get_nodes.return_value = [self._create_node()]
                # Run async method
                import asyncio
                result = asyncio.get_event_loop().run_until_complete(scheduler.schedule_async(task))

                mock_schedule.assert_called_once_with(task)

    def test_deep_path_currently_falls_back_to_fast(self):
        """Test that Deep Path currently falls back to Fast Path"""
        mock_client = MagicMock(spec=RayClient)
        mock_client.get_nodes.return_value = [
            self._create_node(hostname="worker-1", gpu_total=1, gpu_used=0)
        ]

        scheduler = AgenticScheduler(ray_client=mock_client)
        task = self._create_task(config={"preferred_node": "worker-1"})  # Would trigger deep path

        # Currently Deep Path falls back to Fast Path
        decision = scheduler.schedule(task)

        assert decision.is_valid is True
        # Deep path currently just uses fast scheduler with different routing_path marker
        # The decision should still select a valid node
        assert decision.selected_node is not None or not decision.is_valid
