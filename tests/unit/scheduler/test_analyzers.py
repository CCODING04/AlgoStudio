# tests/unit/scheduler/test_analyzers.py
"""Unit tests for scheduler analyzers."""

import pytest
from unittest.mock import MagicMock, patch
from algo_studio.core.scheduler.analyzers.base import TaskAnalyzerInterface
from algo_studio.core.scheduler.analyzers.default_analyzer import DefaultTaskAnalyzer
from algo_studio.core.task import Task, TaskType, TaskStatus


class TestTaskAnalyzerInterface:
    """Tests for TaskAnalyzerInterface."""

    def test_interface_is_abc(self):
        """Test TaskAnalyzerInterface is an abstract base class."""
        from abc import ABC
        assert issubclass(TaskAnalyzerInterface, ABC)


class TestDefaultTaskAnalyzer:
    """Tests for DefaultTaskAnalyzer implementation."""

    @pytest.fixture
    def analyzer(self):
        """Create a DefaultTaskAnalyzer instance."""
        return DefaultTaskAnalyzer()

    @pytest.fixture
    def sample_task(self):
        """Create a sample train task."""
        return Task(
            task_id="test-task-001",
            task_type=TaskType.TRAIN,
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            status=TaskStatus.PENDING,
            config={"epochs": 100},
        )

    def test_analyzer_inherits_from_interface(self, analyzer):
        """Test DefaultTaskAnalyzer inherits from TaskAnalyzerInterface."""
        assert isinstance(analyzer, TaskAnalyzerInterface)

    def test_analyze_train_task(self, analyzer, sample_task):
        """Test analyzing a training task."""
        profile = analyzer.analyze(sample_task)
        assert profile is not None
        assert profile.task_id == "test-task-001"
        assert profile.task_type.value == "train"
        assert profile.num_gpus == 1  # Default for TRAIN
        assert profile.priority == 5  # Default priority

    def test_analyze_infer_task(self, analyzer):
        """Test analyzing an inference task."""
        infer_task = Task(
            task_id="test-infer-001",
            task_type=TaskType.INFER,
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            status=TaskStatus.PENDING,
            config={"batch_size": 32},
        )
        profile = analyzer.analyze(infer_task)
        assert profile.num_gpus == 0  # Default for INFER
        assert profile.num_cpus == 2

    def test_analyze_verify_task(self, analyzer):
        """Test analyzing a verification task."""
        verify_task = Task(
            task_id="test-verify-001",
            task_type=TaskType.VERIFY,
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            status=TaskStatus.PENDING,
            config={},
        )
        profile = analyzer.analyze(verify_task)
        assert profile.task_type.value == "verify"

    def test_get_resource_requirements_train(self, analyzer, sample_task):
        """Test extracting resource requirements for train task."""
        resources = analyzer.get_resource_requirements(sample_task)
        assert resources["num_gpus"] == 1
        assert resources["num_cpus"] == 4
        assert resources["memory_gb"] == 16.0

    def test_get_resource_requirements_with_config_override(self, analyzer):
        """Test resource requirements with config override."""
        task = Task(
            task_id="test-001",
            task_type=TaskType.TRAIN,
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            config={"num_gpus": 2, "memory_gb": 32.0},
        )
        resources = analyzer.get_resource_requirements(task)
        assert resources["num_gpus"] == 2
        assert resources["memory_gb"] == 32.0

    def test_priority_extraction(self, analyzer):
        """Test priority extraction from config."""
        task = Task(
            task_id="test-001",
            task_type=TaskType.TRAIN,
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            config={"priority": 8},
        )
        profile = analyzer.analyze(task)
        assert profile.priority == 8

    def test_priority_clamping(self, analyzer):
        """Test priority is clamped to 1-10 range."""
        task = Task(
            task_id="test-001",
            task_type=TaskType.TRAIN,
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            config={"priority": 15},  # Above max
        )
        profile = analyzer.analyze(task)
        assert profile.priority == 10

    def test_estimated_duration_for_train(self, analyzer, sample_task):
        """Test duration estimation for training tasks."""
        profile = analyzer.analyze(sample_task)
        # Should be scaled by epochs (100)
        assert profile.estimated_duration_minutes > 60

    def test_estimated_duration_with_explicit_value(self, analyzer):
        """Test duration estimation with explicit value in config."""
        task = Task(
            task_id="test-001",
            task_type=TaskType.TRAIN,
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            config={"estimated_duration_minutes": 30},
        )
        profile = analyzer.analyze(task)
        assert profile.estimated_duration_minutes == 30

    def test_preferred_nodes_extraction(self, analyzer):
        """Test preferred nodes extraction."""
        task = Task(
            task_id="test-001",
            task_type=TaskType.TRAIN,
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            config={"preferred_node": "worker-1"},
        )
        profile = analyzer.analyze(task)
        assert "worker-1" in profile.preferred_nodes

    def test_data_locality_extraction(self, analyzer):
        """Test data locality hint extraction."""
        task = Task(
            task_id="test-001",
            task_type=TaskType.TRAIN,
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            config={"data_path": "/data/train"},
        )
        profile = analyzer.analyze(task)
        assert profile.data_locality == "/data/train"

    def test_batch_size_affects_memory(self, analyzer):
        """Test that large batch size increases memory estimate."""
        task_small = Task(
            task_id="test-001",
            task_type=TaskType.TRAIN,
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            config={"batch_size": 32},
        )
        task_large = Task(
            task_id="test-002",
            task_type=TaskType.TRAIN,
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            config={"batch_size": 128},
        )
        resources_small = analyzer.get_resource_requirements(task_small)
        resources_large = analyzer.get_resource_requirements(task_large)
        # Large batch should have higher memory
        assert resources_large["memory_gb"] > resources_small["memory_gb"]
