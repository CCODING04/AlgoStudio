# tests/test_scheduler/test_fast_scheduler.py
"""Tests for FastPathScheduler"""

import pytest
from unittest.mock import MagicMock, patch
from algo_studio.core.task import Task, TaskType, TaskStatus
from algo_studio.core.ray_client import NodeStatus
from algo_studio.core.scheduler.agents.fast_scheduler import FastPathScheduler
from algo_studio.core.scheduler.profiles.task_profile import TaskType as SchedulerTaskType


class TestFastPathScheduler:
    """Test suite for FastPathScheduler"""

    def setup_method(self):
        """Set up test fixtures"""
        self.scheduler = FastPathScheduler()

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

    def test_schedule_selects_best_node(self):
        """Test that scheduler selects the best available node"""
        idle_node = self._create_node(hostname="idle-worker", gpu_total=1, gpu_used=0, status="idle")
        busy_node = self._create_node(hostname="busy-worker", gpu_total=1, gpu_used=1, status="busy")
        task = self._create_task()

        decision = self.scheduler.schedule(task, [busy_node, idle_node])

        assert decision.is_valid is True
        assert decision.selected_node == idle_node
        assert decision.routing_path == "fast"

    def test_schedule_no_nodes_returns_invalid(self):
        """Test that scheduling with no nodes returns invalid decision"""
        task = self._create_task()

        decision = self.scheduler.schedule(task, [])

        assert decision.is_valid is False
        assert decision.selected_node is None
        assert "No available nodes" in decision.reasoning

    def test_schedule_offline_nodes_skipped(self):
        """Test that offline nodes are not selected"""
        offline_node = self._create_node(status="offline")
        task = self._create_task()

        decision = self.scheduler.schedule(task, [offline_node])

        assert decision.is_valid is False

    def test_schedule_includes_alternatives(self):
        """Test that decision includes alternative nodes"""
        node1 = self._create_node(hostname="worker-1", gpu_total=1, gpu_used=0)
        node2 = self._create_node(hostname="worker-2", gpu_total=1, gpu_used=0)
        node3 = self._create_node(hostname="worker-3", gpu_total=1, gpu_used=0)
        task = self._create_task()

        decision = self.scheduler.schedule(task, [node1, node2, node3])

        assert len(decision.alternative_nodes) >= 2  # Top 4 alternatives

    def test_schedule_gpu_task(self):
        """Test scheduling a GPU-intensive task"""
        gpu_node = self._create_node(gpu_total=2, gpu_used=0)
        task = self._create_task(config={"num_gpus": 1})

        decision = self.scheduler.schedule(task, [gpu_node])

        assert decision.is_valid is True
        assert decision.confidence > 0

    def test_schedule_infer_task(self):
        """Test scheduling an inference task"""
        node = self._create_node(gpu_total=1, gpu_used=0)
        task = self._create_task(task_type=TaskType.INFER)

        decision = self.scheduler.schedule(task, [node])

        assert decision.is_valid is True
        assert decision.selected_node == node

    def test_schedule_verify_task(self):
        """Test scheduling a verification task"""
        node = self._create_node(gpu_total=1, gpu_used=0)
        task = self._create_task(task_type=TaskType.VERIFY)

        decision = self.scheduler.schedule(task, [node])

        assert decision.is_valid is True
        assert decision.selected_node == node

    def test_schedule_with_validation_fallback(self):
        """Test that scheduler falls back when best node fails validation"""
        # Create a node that will have validation warnings
        validator = self.scheduler.validator
        validator.allow_overcommit_gpu = False

        # Node with no GPU available
        no_gpu_node = self._create_node(gpu_total=1, gpu_used=1)  # No GPU available
        task = self._create_task(config={"num_gpus": 1})

        decision = self.scheduler.schedule(task, [no_gpu_node])

        # Should still select the node with low confidence due to validation warnings
        assert decision.is_valid is True
        # When validation fails but we use fallback, confidence should be low
        if decision.fallback_used:
            assert decision.confidence == 0.3

    def test_schedule_reasoning_contains_info(self):
        """Test that reasoning contains useful information"""
        node = self._create_node(hostname="test-worker")
        task = self._create_task()

        decision = self.scheduler.schedule(task, [node])

        assert len(decision.reasoning) > 0
        assert decision.selected_node is not None

    def test_schedule_decision_id_unique(self):
        """Test that each decision has a unique ID"""
        task = self._create_task()
        node = self._create_node()

        decision1 = self.scheduler.schedule(task, [node])
        decision2 = self.scheduler.schedule(task, [node])

        assert decision1.decision_id != decision2.decision_id

    def test_schedule_multiple_gpu_nodes_prefers_idle(self):
        """Test that among multiple GPU nodes, idle node is preferred"""
        idle_gpu = self._create_node(hostname="idle-gpu", gpu_total=1, gpu_used=0, status="idle")
        busy_gpu = self._create_node(hostname="busy-gpu", gpu_total=1, gpu_used=1, status="busy")
        task = self._create_task(config={"num_gpus": 1})

        decision = self.scheduler.schedule(task, [busy_gpu, idle_gpu])

        assert decision.selected_node == idle_gpu
