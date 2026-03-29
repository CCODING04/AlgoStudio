# tests/unit/scheduler/routing/test_complexity_evaluator.py
"""Unit tests for ComplexityEvaluator."""

import pytest
from algo_studio.core.scheduler.routing.complexity_evaluator import ComplexityEvaluator
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile, TaskType


class TestComplexityEvaluator:
    """Tests for ComplexityEvaluator."""

    @pytest.fixture
    def evaluator(self):
        """Create a ComplexityEvaluator instance with default factors."""
        return ComplexityEvaluator()

    @pytest.fixture
    def evaluator_custom(self):
        """Create a ComplexityEvaluator with custom factors."""
        custom_factors = {
            "gpu_weight": 3,
            "memory_weight": 2,
            "affinity_weight": 1,
            "data_locality_weight": 1,
            "priority_weight": 1,
            "duration_weight": 1,
            "retry_weight": 1,
        }
        return ComplexityEvaluator(factors=custom_factors)

    @pytest.fixture
    def simple_task_profile(self):
        """Create a simple task profile with minimal requirements."""
        return TaskProfile(
            task_id="simple-task-001",
            task_type=TaskType.TRAIN,
            num_gpus=0,
            memory_gb=8,
            priority=5,
            estimated_duration_minutes=30,
        )

    @pytest.fixture
    def gpu_task_profile(self):
        """Create a task profile that requires GPU."""
        return TaskProfile(
            task_id="gpu-task-001",
            task_type=TaskType.TRAIN,
            num_gpus=1,
            memory_gb=8,  # Not > 16, so only GPU weight applies
            priority=5,
            estimated_duration_minutes=30,
        )

    @pytest.fixture
    def complex_task_profile(self):
        """Create a complex task profile with multiple complexity factors."""
        return TaskProfile(
            task_id="complex-task-001",
            task_type=TaskType.TRAIN,
            num_gpus=2,
            memory_gb=32,
            priority=9,
            preferred_nodes=["worker-1", "worker-2"],
            data_locality="storage-node",
            estimated_duration_minutes=120,
            is_retry=True,
            retry_count=3,
        )

    def test_evaluator_has_default_factors(self, evaluator):
        """Test that evaluator has the expected default factors."""
        assert evaluator.factors["gpu_weight"] == 2
        assert evaluator.factors["memory_weight"] == 1
        assert evaluator.factors["affinity_weight"] == 2
        assert evaluator.factors["data_locality_weight"] == 1
        assert evaluator.factors["priority_weight"] == 1
        assert evaluator.factors["duration_weight"] == 1
        assert evaluator.factors["retry_weight"] == 1

    def test_evaluator_accepts_custom_factors(self, evaluator_custom):
        """Test that evaluator accepts custom weight factors."""
        assert evaluator_custom.factors["gpu_weight"] == 3
        assert evaluator_custom.factors["memory_weight"] == 2
        assert evaluator_custom.factors["affinity_weight"] == 1

    def test_evaluate_base_score(self, evaluator, simple_task_profile):
        """Test that base score is 1 for minimal task."""
        score = evaluator.evaluate(simple_task_profile)
        assert score == 1

    def test_evaluate_gpu_adds_complexity(self, evaluator, gpu_task_profile):
        """Test that GPU requirement adds complexity."""
        score = evaluator.evaluate(gpu_task_profile)
        # Base 1 + GPU weight 2 = 3
        assert score == 3

    def test_evaluate_high_memory_adds_complexity(self, evaluator, simple_task_profile):
        """Test that high memory (>16GB) adds complexity."""
        simple_task_profile.memory_gb = 32
        score = evaluator.evaluate(simple_task_profile)
        # Base 1 + memory weight 1 = 2
        assert score == 2

    def test_evaluate_affinity_adds_complexity(self, evaluator, simple_task_profile):
        """Test that preferred nodes adds complexity."""
        simple_task_profile.preferred_nodes = ["worker-1"]
        score = evaluator.evaluate(simple_task_profile)
        # Base 1 + affinity weight 2 = 3
        assert score == 3

    def test_evaluate_data_locality_adds_complexity(self, evaluator, simple_task_profile):
        """Test that data locality adds complexity."""
        simple_task_profile.data_locality = "storage-node"
        score = evaluator.evaluate(simple_task_profile)
        # Base 1 + data_locality weight 1 = 2
        assert score == 2

    def test_evaluate_high_priority_adds_complexity(self, evaluator, simple_task_profile):
        """Test that high priority (>=8) adds complexity."""
        simple_task_profile.priority = 8
        score = evaluator.evaluate(simple_task_profile)
        # Base 1 + priority weight 1 = 2
        assert score == 2

    def test_evaluate_long_duration_adds_complexity(self, evaluator, simple_task_profile):
        """Test that long duration (>60 min) adds complexity."""
        simple_task_profile.estimated_duration_minutes = 90
        score = evaluator.evaluate(simple_task_profile)
        # Base 1 + duration weight 1 = 2
        assert score == 2

    def test_evaluate_retry_adds_complexity(self, evaluator, simple_task_profile):
        """Test that retry task adds complexity."""
        simple_task_profile.is_retry = True
        score = evaluator.evaluate(simple_task_profile)
        # Base 1 + retry weight 1 = 2
        assert score == 2

    def test_evaluate_complex_task(self, evaluator, complex_task_profile):
        """Test evaluation of a complex task with multiple factors."""
        score = evaluator.evaluate(complex_task_profile)
        # Base 1 + GPU 2 + memory 1 + affinity 2 + data 1 + priority 1 + duration 1 + retry 1 = 10
        assert score == 10

    def test_evaluate_caps_at_10(self, evaluator):
        """Test that complexity score is capped at 10."""
        # Create a task with all complexity factors maxed out
        profile = TaskProfile(
            task_id="max-complexity-task",
            task_type=TaskType.TRAIN,
            num_gpus=4,
            memory_gb=64,
            priority=10,
            preferred_nodes=["node1", "node2", "node3"],
            data_locality="storage",
            estimated_duration_minutes=300,
            is_retry=True,
            retry_count=5,
        )
        score = evaluator.evaluate(profile)
        assert score == 10

    def test_get_complexity_breakdown_base(self, evaluator, simple_task_profile):
        """Test breakdown for base complexity."""
        breakdown = evaluator.get_complexity_breakdown(simple_task_profile)
        assert breakdown["base"] == 1
        assert breakdown["total"] == 1

    def test_get_complexity_breakdown_gpu(self, evaluator, gpu_task_profile):
        """Test breakdown includes GPU factor."""
        breakdown = evaluator.get_complexity_breakdown(gpu_task_profile)
        assert breakdown["gpu"] == evaluator.factors["gpu_weight"]
        # memory_gb=8 which is not > 16, so memory should be 0
        assert breakdown["memory"] == 0
        assert breakdown["total"] == 3  # base 1 + gpu 2

    def test_get_complexity_breakdown_complex(self, evaluator, complex_task_profile):
        """Test breakdown for complex task."""
        breakdown = evaluator.get_complexity_breakdown(complex_task_profile)
        assert breakdown["base"] == 1
        assert breakdown["gpu"] == evaluator.factors["gpu_weight"]
        assert breakdown["memory"] == evaluator.factors["memory_weight"]
        assert breakdown["affinity"] == evaluator.factors["affinity_weight"]
        assert breakdown["data_locality"] == evaluator.factors["data_locality_weight"]
        assert breakdown["priority"] == evaluator.factors["priority_weight"]
        assert breakdown["duration"] == evaluator.factors["duration_weight"]
        assert breakdown["retry"] == evaluator.factors["retry_weight"]
        assert breakdown["total"] == 10

    def test_get_complexity_breakdown_zeros_when_not_applicable(self, evaluator, simple_task_profile):
        """Test that unused factors are 0 in breakdown."""
        breakdown = evaluator.get_complexity_breakdown(simple_task_profile)
        assert breakdown["gpu"] == 0
        assert breakdown["memory"] == 0
        assert breakdown["affinity"] == 0
        assert breakdown["data_locality"] == 0
        assert breakdown["priority"] == 0
        assert breakdown["duration"] == 0
        assert breakdown["retry"] == 0

    def test_evaluate_with_custom_weights(self, evaluator_custom, gpu_task_profile):
        """Test evaluation with custom weight factors."""
        score = evaluator_custom.evaluate(gpu_task_profile)
        # gpu_task_profile has memory_gb=8 which is NOT > 16, so only GPU applies
        # Base 1 + GPU (custom weight 3) = 4
        assert score == 4

    def test_evaluate_threshold_edge_cases(self, evaluator):
        """Test edge cases around thresholds."""
        # Priority threshold is >= 8
        profile_7 = TaskProfile(task_id="p7", task_type=TaskType.TRAIN, priority=7)
        profile_8 = TaskProfile(task_id="p8", task_type=TaskType.TRAIN, priority=8)
        assert evaluator.evaluate(profile_7) == 1
        assert evaluator.evaluate(profile_8) == 2

        # Duration threshold is > 60
        profile_60 = TaskProfile(task_id="d60", task_type=TaskType.TRAIN, estimated_duration_minutes=60)
        profile_61 = TaskProfile(task_id="d61", task_type=TaskType.TRAIN, estimated_duration_minutes=61)
        assert evaluator.evaluate(profile_60) == 1
        assert evaluator.evaluate(profile_61) == 2

        # Memory threshold is > 16
        profile_16 = TaskProfile(task_id="m16", task_type=TaskType.TRAIN, memory_gb=16)
        profile_17 = TaskProfile(task_id="m17", task_type=TaskType.TRAIN, memory_gb=17)
        assert evaluator.evaluate(profile_16) == 1
        assert evaluator.evaluate(profile_17) == 2
