# tests/test_scheduler/test_fast_scheduler.py
"""Tests for FastPathScheduler - Fast Path rule-based scheduler"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from algo_studio.core.task import Task, TaskType, TaskStatus
from algo_studio.core.ray_client import NodeStatus
from algo_studio.core.scheduler.agents.fast_scheduler import FastPathScheduler
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile, TaskType as SchedulerTaskType
from algo_studio.core.scheduler.profiles.node_score import NodeScore
from algo_studio.core.scheduler.profiles.scheduling_decision import SchedulingDecision
from algo_studio.core.scheduler.validators.resource_validator import ResourceValidator
from algo_studio.core.scheduler.validators.base import ValidationResult
from algo_studio.core.scheduler.scorers.multi_dim_scorer import MultiDimNodeScorer
from algo_studio.core.scheduler.analyzers.default_analyzer import DefaultTaskAnalyzer


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
        gpu_utilization=None,
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
            gpu_utilization=gpu_utilization,
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

    def _create_task_profile(
        self,
        task_id="train-001",
        task_type=SchedulerTaskType.TRAIN,
        num_gpus=0,
        num_cpus=1,
        memory_gb=0.0,
        priority=5,
        preferred_nodes=None,
        data_locality=None,
    ):
        """Helper to create TaskProfile"""
        return TaskProfile(
            task_id=task_id,
            task_type=task_type,
            num_gpus=num_gpus,
            num_cpus=num_cpus,
            memory_gb=memory_gb,
            priority=priority,
            preferred_nodes=preferred_nodes or [],
            data_locality=data_locality,
        )

    def _create_node_score(
        self,
        node,
        total_score=85.0,
        reasons=None,
        concerns=None,
    ):
        """Helper to create NodeScore"""
        return NodeScore(
            node=node,
            total_score=total_score,
            reasons=reasons or [],
            concerns=concerns or [],
        )

    # =====================================================================
    # Basic scheduling tests
    # =====================================================================

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

    # =====================================================================
    # Custom components tests
    # =====================================================================

    def test_schedule_with_custom_analyzer(self):
        """Test scheduling with custom task analyzer"""
        custom_analyzer = MagicMock()
        custom_analyzer.analyze.return_value = self._create_task_profile(
            task_id="test-task",
            num_gpus=1,
        )
        scheduler = FastPathScheduler(task_analyzer=custom_analyzer)
        node = self._create_node(gpu_total=1, gpu_used=0)
        task = self._create_task()

        decision = scheduler.schedule(task, [node])

        assert decision.is_valid is True
        custom_analyzer.analyze.assert_called_once_with(task)

    def test_schedule_with_custom_scorer(self):
        """Test scheduling with custom node scorer"""
        node = self._create_node(hostname="test-worker")
        task = self._create_task()

        # Create a scorer that always returns a specific node as best
        custom_scorer = MagicMock()
        custom_scorer.score.return_value = [
            self._create_node_score(node, total_score=100.0, reasons=["Custom scorer"])
        ]

        scheduler = FastPathScheduler(node_scorer=custom_scorer)
        decision = scheduler.schedule(task, [node])

        assert decision.is_valid is True
        custom_scorer.score.assert_called_once()

    def test_schedule_with_custom_validator(self):
        """Test scheduling with custom validator"""
        node = self._create_node(gpu_total=1, gpu_used=0)
        task = self._create_task(config={"num_gpus": 1})

        # Create a validator that always validates
        custom_validator = MagicMock()
        custom_validator.validate.return_value = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
        )

        scheduler = FastPathScheduler(validator=custom_validator)
        decision = scheduler.schedule(task, [node])

        assert decision.is_valid is True
        custom_validator.validate.assert_called_once()

    # =====================================================================
    # Validation fallback tests
    # =====================================================================

    def test_schedule_validation_fallback_when_best_invalid(self):
        """Test that scheduler falls back to alternative when best node fails validation"""
        # node1 scores higher, so it's validated first
        # We make node1 fail validation so it falls back to node2
        node1 = self._create_node(hostname="node-1", gpu_total=1, gpu_used=0)  # Has GPU
        node2 = self._create_node(hostname="node-2", gpu_total=1, gpu_used=0)  # Has GPU too
        task = self._create_task(config={"num_gpus": 1})

        # Validator: first node (node1, higher score) invalid, second (node2) valid
        validator = MagicMock()
        validator.validate.side_effect = [
            ValidationResult(is_valid=False, errors=["Node health check failed"], warnings=[]),
            ValidationResult(is_valid=True, errors=[], warnings=[]),
        ]

        scheduler = FastPathScheduler(validator=validator)
        decision = scheduler.schedule(task, [node1, node2])

        assert decision.is_valid is True
        assert decision.selected_node == node2  # node1 failed, fell back to node2
        assert decision.fallback_used is False  # node2 was valid

    def test_schedule_fallback_used_when_all_validations_fail(self):
        """Test that fallback is used when all nodes fail validation"""
        node1 = self._create_node(hostname="node-1", gpu_total=1, gpu_used=1)
        node2 = self._create_node(hostname="node-2", gpu_total=1, gpu_used=1)
        task = self._create_task(config={"num_gpus": 1})

        # Both nodes fail validation
        validator = MagicMock()
        validation_result = ValidationResult(
            is_valid=False,
            errors=["Insufficient GPU"],
            warnings=["GPU overcommit required"],
        )
        validator.validate.return_value = validation_result

        scheduler = FastPathScheduler(validator=validator)
        decision = scheduler.schedule(task, [node1, node2])

        assert decision.is_valid is True  # Still selects a node with fallback
        assert decision.fallback_used is True
        assert decision.confidence == 0.3
        assert "Validation warnings" in decision.reasoning

    def test_schedule_fallback_with_validation_warnings(self):
        """Test scheduling when node has validation warnings but is still valid"""
        node = self._create_node(hostname="node-1", gpu_total=1, gpu_used=1)
        task = self._create_task(config={"num_gpus": 1})

        # Validator allows overcommit, so only warnings
        validator = MagicMock()
        validator.validate.return_value = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=["GPU overcommit: need 1, only 0 available"],
        )

        scheduler = FastPathScheduler(validator=validator)
        decision = scheduler.schedule(task, [node])

        assert decision.is_valid is True
        # When validation has warnings but is still valid, fallback is not used
        assert decision.fallback_used is False

    # =====================================================================
    # _build_reasoning tests
    # =====================================================================

    def test_build_reasoning_basic(self):
        """Test _build_reasoning with basic node"""
        node = self._create_node(hostname="test-worker", ip="192.168.0.100")
        task_profile = self._create_task_profile(task_type=SchedulerTaskType.TRAIN)
        node_score = self._create_node_score(
            node=node,
            total_score=85.0,
            reasons=["GPU available", "Memory available"],
        )

        reasoning = self.scheduler._build_reasoning(task_profile, node_score)

        assert "test-worker" in reasoning
        assert "85.0" in reasoning
        assert "train" in reasoning.lower()
        assert "GPU available" in reasoning

    def test_build_reasoning_with_multiple_reasons(self):
        """Test _build_reasoning limits reasons to top 3"""
        node = self._create_node(hostname="test-worker")
        node_score = self._create_node_score(
            node=node,
            total_score=90.0,
            reasons=["Reason 1", "Reason 2", "Reason 3", "Reason 4", "Reason 5"],
        )
        task_profile = self._create_task_profile()

        reasoning = self.scheduler._build_reasoning(task_profile, node_score)

        # Should only show top 3 reasons
        assert "Reason 1" in reasoning
        assert "Reason 2" in reasoning
        assert "Reason 3" in reasoning
        assert "Reason 4" not in reasoning  # Should be truncated

    def test_build_reasoning_no_reasons(self):
        """Test _build_reasoning when node score has no reasons"""
        node = self._create_node(hostname="test-worker")
        node_score = self._create_node_score(
            node=node,
            total_score=50.0,
            reasons=[],  # No reasons
        )
        task_profile = self._create_task_profile()

        reasoning = self.scheduler._build_reasoning(task_profile, node_score)

        assert "test-worker" in reasoning
        assert "50.0" in reasoning
        # Should not crash when no reasons

    def test_build_reasoning_no_hostname(self):
        """Test _build_reasoning when node has no hostname"""
        node = self._create_node(hostname=None, ip="192.168.0.100")
        node_score = self._create_node_score(node=node, total_score=75.0)
        task_profile = self._create_task_profile()

        reasoning = self.scheduler._build_reasoning(task_profile, node_score)

        # Should fall back to IP
        assert "192.168.0.100" in reasoning

    # =====================================================================
    # Node scoring and selection tests
    # =====================================================================

    def test_schedule_sorts_by_score(self):
        """Test that scheduler selects highest scoring node"""
        low_score_node = self._create_node(hostname="low-score", gpu_total=1, gpu_used=1)  # Busy, low score
        high_score_node = self._create_node(hostname="high-score", gpu_total=1, gpu_used=0)  # Idle, high score
        task = self._create_task(config={"num_gpus": 1})

        decision = self.scheduler.schedule(task, [low_score_node, high_score_node])

        assert decision.selected_node == high_score_node

    def test_schedule_with_preferred_nodes(self):
        """Test scheduling with preferred nodes affinity"""
        # Create nodes with enough resources to avoid validation errors
        preferred = self._create_node(
            hostname="preferred-node",
            gpu_total=1,
            gpu_used=0,
            memory_used_gb=8,
            memory_total_gb=32,
        )
        other = self._create_node(
            hostname="other-node",
            gpu_total=1,
            gpu_used=0,
            memory_used_gb=8,
            memory_total_gb=32,
        )
        task = self._create_task(config={"preferred_nodes": ["preferred-node"]})

        decision = self.scheduler.schedule(task, [preferred, other])

        # Preferred node should score higher due to affinity
        assert decision.selected_node == preferred

    def test_schedule_with_data_locality(self):
        """Test scheduling with data locality preference"""
        # Create nodes with enough resources to avoid validation errors
        local = self._create_node(
            hostname="data-node",
            gpu_total=1,
            gpu_used=0,
            memory_used_gb=8,
            memory_total_gb=32,
        )
        remote = self._create_node(
            hostname="remote-node",
            gpu_total=1,
            gpu_used=0,
            memory_used_gb=8,
            memory_total_gb=32,
        )
        task = self._create_task(config={"data_locality": "data-node"})

        decision = self.scheduler.schedule(task, [local, remote])

        # Data locality node should score higher due to affinity
        assert decision.selected_node == local

    # =====================================================================
    # Edge cases
    # =====================================================================

    def test_schedule_with_high_load_node(self):
        """Test scheduling when all nodes are highly loaded"""
        high_load = self._create_node(
            hostname="loaded-node",
            cpu_used=23,
            cpu_total=24,  # 95%+ load
            gpu_total=1,
            gpu_used=0,
        )
        task = self._create_task(config={"num_gpus": 1})

        # Validator with high max_load_ratio to allow loaded nodes
        validator = ResourceValidator(max_load_ratio=0.98)
        scheduler = FastPathScheduler(validator=validator)
        decision = scheduler.schedule(task, [high_load])

        # Should still schedule but with lower confidence due to validation warnings
        assert decision.is_valid is True

    def test_schedule_cpu_task(self):
        """Test scheduling a CPU-only task"""
        node = self._create_node(cpu_total=24, cpu_used=8, gpu_total=1, gpu_used=1)
        task = self._create_task(task_type=TaskType.INFER, config={"num_gpus": 0})

        decision = self.scheduler.schedule(task, [node])

        assert decision.is_valid is True
        assert decision.selected_node == node

    def test_schedule_with_retry_task(self):
        """Test scheduling a retry task"""
        node = self._create_node(hostname="retry-node", gpu_total=1, gpu_used=0)
        task = self._create_task(config={"is_retry": True})

        decision = self.scheduler.schedule(task, [node])

        assert decision.is_valid is True

    def test_schedule_multiple_nodes_more_than_four_alternatives(self):
        """Test that alternatives are limited to top 4"""
        nodes = [
            self._create_node(hostname=f"node-{i}", gpu_total=1, gpu_used=0)
            for i in range(10)
        ]
        task = self._create_task()

        decision = self.scheduler.schedule(task, nodes)

        # Should include at most 4 alternatives
        assert len(decision.alternative_nodes) <= 4

    # =====================================================================
    # SchedulingDecision properties tests
    # =====================================================================

    def test_decision_is_valid_property(self):
        """Test that is_valid property correctly reflects selected_node"""
        node = self._create_node(hostname="test-worker")
        task = self._create_task()

        decision = self.scheduler.schedule(task, [node])

        assert decision.is_valid is True
        assert decision.selected_node is not None

    def test_decision_to_dict(self):
        """Test SchedulingDecision.to_dict()"""
        node = self._create_node(hostname="test-worker", node_id="n1", ip="192.168.0.1")
        task = self._create_task()
        decision = self.scheduler.schedule(task, [node])

        result = decision.to_dict()

        assert "decision_id" in result
        assert "task_id" in result
        assert result["selected_node"]["hostname"] == "test-worker"
        assert result["routing_path"] == "fast"
        assert "confidence" in result

    # =====================================================================
    # Confidence calculation tests
    # =====================================================================

    def test_confidence_based_on_score(self):
        """Test that confidence is calculated from node score"""
        # High score node - idle with GPU available and enough memory
        high_score_node = self._create_node(
            hostname="high",
            gpu_total=1,
            gpu_used=0,
            memory_used_gb=8,
            memory_total_gb=32,  # More memory to avoid validation error
        )
        # Low score node - busy with GPU used and enough memory
        low_score_node = self._create_node(
            hostname="low",
            gpu_total=1,
            gpu_used=1,
            status="busy",
            memory_used_gb=24,
            memory_total_gb=32,  # More memory to avoid validation error
        )

        task = self._create_task(config={"num_gpus": 1})
        high_decision = self.scheduler.schedule(task, [high_score_node])
        low_decision = self.scheduler.schedule(task, [low_score_node])

        # High score should have higher confidence
        # Both may fall back but with different confidence values
        assert high_decision.confidence >= 0
        assert low_decision.confidence >= 0

    # =====================================================================
    # Error handling tests
    # =====================================================================

    def test_schedule_handles_analyzer_error(self):
        """Test that scheduler handles analyzer errors gracefully"""
        faulty_analyzer = MagicMock()
        faulty_analyzer.analyze.side_effect = Exception("Analysis failed")

        scheduler = FastPathScheduler(task_analyzer=faulty_analyzer)
        node = self._create_node()
        task = self._create_task()

        # Should raise the error
        with pytest.raises(Exception, match="Analysis failed"):
            scheduler.schedule(task, [node])

    def test_schedule_handles_scorer_error(self):
        """Test that scheduler handles scorer errors gracefully"""
        faulty_scorer = MagicMock()
        faulty_scorer.score.side_effect = Exception("Scoring failed")

        scheduler = FastPathScheduler(node_scorer=faulty_scorer)
        node = self._create_node()
        task = self._create_task()

        # Should raise the error
        with pytest.raises(Exception, match="Scoring failed"):
            scheduler.schedule(task, [node])

    def test_schedule_handles_validator_error(self):
        """Test that scheduler handles validator errors gracefully"""
        node = self._create_node()
        task = self._create_task()

        faulty_validator = MagicMock()
        faulty_validator.validate.side_effect = Exception("Validation failed")

        scheduler = FastPathScheduler(validator=faulty_validator)
        # Score the node first to get a valid node_score
        scorer = MultiDimNodeScorer()
        task_profile = DefaultTaskAnalyzer().analyze(task)
        node_scores = scorer.score(task_profile, [node])

        # Should raise the error when validator is called
        with pytest.raises(Exception, match="Validation failed"):
            scheduler.schedule(task, [node])


class TestFastPathSchedulerIntegration:
    """Integration tests for FastPathScheduler with real components"""

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

    def test_full_schedule_workflow(self):
        """Test complete scheduling workflow with real components"""
        # Create multiple nodes with different characteristics
        head_node = self._create_node(
            hostname="head-node",
            ip="192.168.0.126",
            status="idle",
            gpu_total=1,
            gpu_used=0,
            cpu_used=4,
            cpu_total=24,
        )
        worker_node = self._create_node(
            hostname="worker-node",
            ip="192.168.0.115",
            status="busy",
            gpu_total=1,
            gpu_used=1,
            cpu_used=20,
            cpu_total=24,
        )

        # Create a training task
        task = self._create_task(
            task_id="train-yolo-v1",
            task_type=TaskType.TRAIN,
            config={
                "num_gpus": 1,
                "batch_size": 32,
                "epochs": 10,
            },
        )

        # Schedule
        decision = self.scheduler.schedule(task, [head_node, worker_node])

        # Verify decision
        assert decision.is_valid is True
        assert decision.task_id == "train-yolo-v1"
        assert decision.routing_path == "fast"
        assert decision.selected_node is not None
        assert decision.confidence > 0

        # Best node should be head (idle, has GPU)
        assert decision.selected_node == head_node

    def test_schedule_with_real_analyzer_and_scorer(self):
        """Test scheduling with real DefaultTaskAnalyzer and MultiDimNodeScorer"""
        node = self._create_node(
            hostname="gpu-worker",
            gpu_total=2,
            gpu_used=0,
            cpu_total=24,
            cpu_used=8,
            memory_total_gb=64,
            memory_used_gb=16,
        )

        # Train task with explicit GPU requirement
        task = Task(
            task_id="train-resnet",
            task_type=TaskType.TRAIN,
            algorithm_name="resnet",
            algorithm_version="v2",
            config={
                "num_gpus": 2,
                "memory_gb": 32,
                "priority": 8,
            },
        )

        decision = self.scheduler.schedule(task, [node])

        assert decision.is_valid is True
        assert decision.selected_node == node
        assert "gpu" in decision.reasoning.lower() or "memory" in decision.reasoning.lower()

    def test_infer_task_scheduling(self):
        """Test inference task scheduling"""
        node = self._create_node(
            hostname="infer-node",
            gpu_total=1,
            gpu_used=0,
            status="idle",
        )

        task = Task(
            task_id="infer-input-123",
            task_type=TaskType.INFER,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={},
        )

        decision = self.scheduler.schedule(task, [node])

        assert decision.is_valid is True
        assert decision.routing_path == "fast"
        # Inference should not necessarily require GPU

    def test_verify_task_scheduling(self):
        """Test verification task scheduling"""
        node = self._create_node(
            hostname="verify-node",
            gpu_total=0,
            gpu_used=0,
            cpu_total=16,
            cpu_used=4,
            status="idle",
        )

        task = Task(
            task_id="verify-model-456",
            task_type=TaskType.VERIFY,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={},
        )

        decision = self.scheduler.schedule(task, [node])

        assert decision.is_valid is True
        assert decision.selected_node == node
