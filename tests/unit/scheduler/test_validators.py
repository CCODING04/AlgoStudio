# tests/unit/scheduler/test_validators.py
"""Unit tests for scheduler validators."""

import pytest
from unittest.mock import MagicMock
from algo_studio.core.scheduler.validators.base import SafetyValidatorInterface, ValidationResult
from algo_studio.core.scheduler.validators.resource_validator import ResourceValidator
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile, TaskType
from algo_studio.core.scheduler.profiles.node_score import NodeScore
from algo_studio.core.ray_client import NodeStatus


class TestSafetyValidatorInterface:
    """Tests for SafetyValidatorInterface."""

    def test_interface_is_abc(self):
        """Test SafetyValidatorInterface is an abstract base class."""
        from abc import ABC
        assert issubclass(SafetyValidatorInterface, ABC)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self):
        """Test creating a valid result."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        assert result.is_valid is True
        assert result.has_errors is False
        assert result.has_warnings is False

    def test_result_with_errors(self):
        """Test result with errors."""
        result = ValidationResult(
            is_valid=False,
            errors=["Insufficient GPU"],
            warnings=[]
        )
        assert result.is_valid is False
        assert result.has_errors is True
        assert result.has_warnings is False

    def test_result_with_warnings(self):
        """Test result with warnings."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=["GPU overcommit"]
        )
        assert result.is_valid is True
        assert result.has_errors is False
        assert result.has_warnings is True


class TestResourceValidator:
    """Tests for ResourceValidator."""

    @pytest.fixture
    def validator(self):
        """Create a ResourceValidator instance."""
        return ResourceValidator()

    @pytest.fixture
    def sample_task_profile(self):
        """Create a sample task profile."""
        return TaskProfile(
            task_id="test-task-001",
            task_type=TaskType.TRAIN,
            num_gpus=1,
            num_cpus=4,
            memory_gb=16.0,
            priority=5,
            preferred_nodes=[],
            data_locality=None,
            estimated_duration_minutes=60,
            is_retry=False,
            retry_count=0,
            timeout_minutes=120,
        )

    @pytest.fixture
    def idle_node(self):
        """Create an idle node with available resources."""
        return NodeStatus(
            node_id="node-001",
            ip="192.168.0.115",
            status="idle",
            cpu_used=1,
            cpu_total=32,
            gpu_used=0,
            gpu_total=4,
            memory_used_gb=16.0,
            memory_total_gb=64.0,
            disk_used_gb=100.0,
            disk_total_gb=500.0,
            hostname="worker-1",
        )

    @pytest.fixture
    def busy_node(self):
        """Create a busy node with no GPU available."""
        return NodeStatus(
            node_id="node-002",
            ip="192.168.0.116",
            status="busy",
            cpu_used=28,
            cpu_total=32,
            gpu_used=4,
            gpu_total=4,
            memory_used_gb=60.0,
            memory_total_gb=64.0,
            disk_used_gb=200.0,
            disk_total_gb=500.0,
            hostname="worker-2",
        )

    def test_validator_inherits_from_interface(self, validator):
        """Test ResourceValidator inherits from SafetyValidatorInterface."""
        assert isinstance(validator, SafetyValidatorInterface)

    def test_validate_sufficient_resources(self, validator, sample_task_profile, idle_node):
        """Test validation passes when resources are sufficient."""
        node_score = NodeScore(node=idle_node, total_score=95.0)
        result = validator.validate(node_score, sample_task_profile)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_insufficient_gpu(self, validator, sample_task_profile, busy_node):
        """Test validation fails when GPU is insufficient."""
        node_score = NodeScore(node=busy_node, total_score=50.0)
        result = validator.validate(node_score, sample_task_profile)
        assert result.is_valid is False
        assert any("GPU" in err for err in result.errors)

    def test_can_schedule_sufficient(self, validator, sample_task_profile, idle_node):
        """Test can_schedule returns True when resources are sufficient."""
        assert validator.can_schedule(sample_task_profile, idle_node) is True

    def test_can_schedule_insufficient(self, validator, sample_task_profile, busy_node):
        """Test can_schedule returns False when GPU insufficient."""
        assert validator.can_schedule(sample_task_profile, busy_node) is False

    def test_allow_overcommit_gpu(self, sample_task_profile, idle_node):
        """Test GPU overcommit is allowed when configured."""
        # Use idle_node but with no GPU available (to test GPU overcommit)
        busy_gpu_node = NodeStatus(
            node_id="node-gpu-busy",
            ip="192.168.0.120",
            status="busy",
            cpu_used=4,
            cpu_total=32,
            gpu_used=4,  # All GPUs used
            gpu_total=4,
            memory_used_gb=16.0,  # Has memory available
            memory_total_gb=64.0,
            disk_used_gb=100.0,
            disk_total_gb=500.0,
            hostname="gpu-busy-worker",
        )
        validator = ResourceValidator(allow_overcommit_gpu=True)
        node_score = NodeScore(node=busy_gpu_node, total_score=50.0)
        result = validator.validate(node_score, sample_task_profile)
        # With overcommit, validation passes but warning is added
        assert result.is_valid is True
        assert len(result.warnings) > 0

    def test_offline_node_invalid(self, validator, sample_task_profile, idle_node):
        """Test that offline nodes are always invalid."""
        offline_node = NodeStatus(
            node_id="node-offline",
            ip="192.168.0.200",
            status="offline",
            cpu_used=1,
            cpu_total=32,
            gpu_used=0,
            gpu_total=4,
            memory_used_gb=16.0,
            memory_total_gb=64.0,
            disk_used_gb=100.0,
            disk_total_gb=500.0,
            hostname="offline-worker",
        )
        node_score = NodeScore(node=offline_node, total_score=95.0)
        result = validator.validate(node_score, sample_task_profile)
        assert result.is_valid is False
        assert any("offline" in err.lower() for err in result.errors)

    def test_infer_task_no_gpu_required(self, validator, idle_node):
        """Test inference task doesn't require GPU."""
        infer_profile = TaskProfile(
            task_id="test-infer-001",
            task_type=TaskType.INFER,
            num_gpus=0,
            num_cpus=2,
            memory_gb=4.0,
            priority=5,
            preferred_nodes=[],
            data_locality=None,
            estimated_duration_minutes=10,
            is_retry=False,
            retry_count=0,
            timeout_minutes=60,
        )
        node_score = NodeScore(node=idle_node, total_score=90.0)
        result = validator.validate(node_score, infer_profile)
        assert result.is_valid is True

    def test_high_load_node_invalid(self, validator, sample_task_profile, idle_node):
        """Test node with high CPU load is invalid."""
        high_load_node = NodeStatus(
            node_id="node-003",
            ip="192.168.0.117",
            status="idle",
            cpu_used=31,  # High load (31/32)
            cpu_total=32,
            gpu_used=0,
            gpu_total=4,
            memory_used_gb=16.0,
            memory_total_gb=64.0,
            disk_used_gb=100.0,
            disk_total_gb=500.0,
            hostname="loaded-worker",
        )
        node_score = NodeScore(node=high_load_node, total_score=30.0)
        result = validator.validate(node_score, sample_task_profile)
        assert result.is_valid is False
