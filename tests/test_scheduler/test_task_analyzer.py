# tests/test_scheduler/test_task_analyzer.py
"""Tests for DefaultTaskAnalyzer"""

import pytest
from algo_studio.core.task import Task, TaskType, TaskStatus
from algo_studio.core.scheduler.analyzers.default_analyzer import DefaultTaskAnalyzer
from algo_studio.core.scheduler.profiles.task_profile import TaskType as SchedulerTaskType


class TestDefaultTaskAnalyzer:
    """Test suite for DefaultTaskAnalyzer"""

    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = DefaultTaskAnalyzer()

    def test_analyze_train_task_defaults(self):
        """Test analyzing a train task with default requirements"""
        task = Task(
            task_id="train-001",
            task_type=TaskType.TRAIN,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={}
        )

        profile = self.analyzer.analyze(task)

        assert profile.task_id == "train-001"
        assert profile.task_type == SchedulerTaskType.TRAIN
        assert profile.num_gpus == 1  # Default for TRAIN
        assert profile.num_cpus == 4   # Default for TRAIN
        assert profile.memory_gb == 16.0  # Default for TRAIN
        assert profile.priority == 5  # Default priority
        assert profile.timeout_minutes == 120  # Default timeout

    def test_analyze_infer_task_defaults(self):
        """Test analyzing an inference task with default requirements"""
        task = Task(
            task_id="infer-001",
            task_type=TaskType.INFER,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={}
        )

        profile = self.analyzer.analyze(task)

        assert profile.task_type == SchedulerTaskType.INFER
        assert profile.num_gpus == 0  # Default for INFER
        assert profile.num_cpus == 2   # Default for INFER

    def test_analyze_verify_task_defaults(self):
        """Test analyzing a verify task with default requirements"""
        task = Task(
            task_id="verify-001",
            task_type=TaskType.VERIFY,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={}
        )

        profile = self.analyzer.analyze(task)

        assert profile.task_type == SchedulerTaskType.VERIFY
        assert profile.num_gpus == 0  # Default for VERIFY

    def test_analyze_with_explicit_gpu_config(self):
        """Test analyzing task with explicit GPU config"""
        task = Task(
            task_id="train-002",
            task_type=TaskType.TRAIN,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={"num_gpus": 2}
        )

        profile = self.analyzer.analyze(task)

        assert profile.num_gpus == 2

    def test_analyze_with_explicit_gpu_config_gpus_key(self):
        """Test analyzing task with 'gpus' key in config"""
        task = Task(
            task_id="train-003",
            task_type=TaskType.TRAIN,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={"gpus": 4}
        )

        profile = self.analyzer.analyze(task)

        assert profile.num_gpus == 4

    def test_analyze_with_batch_size_memory_scaling(self):
        """Test that large batch size scales memory requirements"""
        task = Task(
            task_id="train-004",
            task_type=TaskType.TRAIN,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={"batch_size": 128}  # 4x default (32)
        )

        profile = self.analyzer.analyze(task)

        # Memory should be scaled: 16GB * (128/32) = 64GB
        assert profile.memory_gb == 64.0

    def test_analyze_with_priority(self):
        """Test extracting priority from config"""
        task = Task(
            task_id="train-005",
            task_type=TaskType.TRAIN,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={"priority": 9}
        )

        profile = self.analyzer.analyze(task)

        assert profile.priority == 9

    def test_analyze_with_priority_clamping(self):
        """Test that priority is clamped to 1-10 range"""
        task = Task(
            task_id="train-006",
            task_type=TaskType.TRAIN,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={"priority": 15}  # Over max
        )

        profile = self.analyzer.analyze(task)

        assert profile.priority == 10  # Clamped to max

    def test_analyze_with_preferred_nodes(self):
        """Test extracting preferred nodes from config"""
        task = Task(
            task_id="train-007",
            task_type=TaskType.TRAIN,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={"preferred_node": "worker-1"}
        )

        profile = self.analyzer.analyze(task)

        assert profile.preferred_nodes == ["worker-1"]

    def test_analyze_with_preferred_nodes_list(self):
        """Test extracting preferred nodes as list"""
        task = Task(
            task_id="train-008",
            task_type=TaskType.TRAIN,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={"preferred_nodes": ["worker-1", "worker-2"]}
        )

        profile = self.analyzer.analyze(task)

        assert profile.preferred_nodes == ["worker-1", "worker-2"]

    def test_analyze_with_data_locality(self):
        """Test extracting data locality hint"""
        task = Task(
            task_id="train-009",
            task_type=TaskType.TRAIN,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={"data_path": "/mnt/data/dataset1"}
        )

        profile = self.analyzer.analyze(task)

        assert profile.data_locality == "/mnt/data/dataset1"

    def test_analyze_with_timeout(self):
        """Test extracting timeout from config"""
        task = Task(
            task_id="train-010",
            task_type=TaskType.TRAIN,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={"timeout_minutes": 240}
        )

        profile = self.analyzer.analyze(task)

        assert profile.timeout_minutes == 240

    def test_analyze_estimated_duration_with_epochs(self):
        """Test that epochs affect estimated duration for training"""
        task = Task(
            task_id="train-011",
            task_type=TaskType.TRAIN,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={"epochs": 50}
        )

        profile = self.analyzer.analyze(task)

        # Base duration for TRAIN is 60 min, with 50 epochs = 3000 min
        assert profile.estimated_duration_minutes == 3000

    def test_complexity_calculation_simple_task(self):
        """Test complexity calculation for simple task"""
        task = Task(
            task_id="infer-001",
            task_type=TaskType.INFER,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={}
        )

        profile = self.analyzer.analyze(task)

        # Simple INFER task: base=1, no GPU, no affinity
        assert profile.complexity == 1

    def test_complexity_calculation_gpu_task(self):
        """Test complexity calculation for GPU task"""
        task = Task(
            task_id="train-001",
            task_type=TaskType.TRAIN,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={"num_gpus": 1}
        )

        profile = self.analyzer.analyze(task)

        # TRAIN with GPU: base=1 + 2 (GPU) = 3
        assert profile.complexity == 3

    def test_complexity_calculation_complex_task(self):
        """Test complexity calculation for complex task with multiple factors"""
        task = Task(
            task_id="train-001",
            task_type=TaskType.TRAIN,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={
                "num_gpus": 2,
                "memory_gb": 32,
                "preferred_node": "worker-1",
                "data_path": "/mnt/data",
                "priority": 9,
                "epochs": 100,
            }
        )

        profile = self.analyzer.analyze(task)

        # Base 1 + GPU 2 + memory 1 + affinity 2 + locality 1 + high priority 1 + long running 1 = 9
        assert profile.complexity == 9

    def test_get_resource_requirements(self):
        """Test resource requirements extraction"""
        task = Task(
            task_id="train-001",
            task_type=TaskType.TRAIN,
            algorithm_name="yolo",
            algorithm_version="v1",
            config={"num_gpus": 2, "memory_gb": 32}
        )

        resources = self.analyzer.get_resource_requirements(task)

        assert resources["num_gpus"] == 2
        assert resources["memory_gb"] == 32
        assert resources["num_cpus"] == 4  # Default
