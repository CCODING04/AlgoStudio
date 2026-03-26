# tests/test_scheduler/test_resource_validator.py
"""Tests for ResourceValidator"""

import pytest
from algo_studio.core.ray_client import NodeStatus
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile, TaskType
from algo_studio.core.scheduler.scorers.multi_dim_scorer import MultiDimNodeScorer
from algo_studio.core.scheduler.validators.resource_validator import ResourceValidator


class TestResourceValidator:
    """Test suite for ResourceValidator"""

    def setup_method(self):
        """Set up test fixtures"""
        self.validator = ResourceValidator()
        self.scorer = MultiDimNodeScorer()

    def _create_node(
        self,
        cpu_used=8,
        cpu_total=24,
        gpu_available=1,
        memory_used_gb=16,
        memory_total_gb=31,
        status="idle",
        disk_used_gb=100,
        disk_total_gb=500,
    ):
        """Helper to create NodeStatus"""
        return NodeStatus(
            node_id="node-1",
            ip="192.168.0.101",
            hostname="worker-1",
            status=status,
            cpu_used=cpu_used,
            cpu_total=cpu_total,
            gpu_used=0,
            gpu_total=gpu_available,
            memory_used_gb=memory_used_gb,
            memory_total_gb=memory_total_gb,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
        )

    def _create_profile(
        self,
        num_gpus=0,
        num_cpus=1,
        memory_gb=0.0,
    ):
        """Helper to create TaskProfile"""
        return TaskProfile(
            task_id="test-task",
            task_type=TaskType.TRAIN,
            num_gpus=num_gpus,
            num_cpus=num_cpus,
            memory_gb=memory_gb,
        )

    def _score_node(self, node, profile):
        """Helper to score a node for validation tests"""
        scores = self.scorer.score(profile, [node])
        return scores[0]

    def test_validate_sufficient_gpu(self):
        """Test validation passes with sufficient GPU"""
        node = self._create_node(gpu_available=2)
        profile = self._create_profile(num_gpus=1)
        node_score = self._score_node(node, profile)

        result = self.validator.validate(node_score, profile)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_insufficient_gpu(self):
        """Test validation fails with insufficient GPU"""
        node = self._create_node(gpu_available=0)
        profile = self._create_profile(num_gpus=1)
        node_score = self._score_node(node, profile)

        result = self.validator.validate(node_score, profile)

        assert result.is_valid is False
        assert any("GPU" in err or "Insufficient" in err for err in result.errors)

    def test_validate_gpu_overcommit_allowed(self):
        """Test GPU overcommit is allowed when configured"""
        validator = ResourceValidator(allow_overcommit_gpu=True)
        node = self._create_node(gpu_available=0)
        profile = self._create_profile(num_gpus=1)
        node_score = self._score_node(node, profile)

        result = validator.validate(node_score, profile)

        assert result.is_valid is True
        assert len(result.warnings) >= 1
        assert any("overcommit" in w.lower() for w in result.warnings)

    def test_validate_sufficient_memory(self):
        """Test validation passes with sufficient memory"""
        node = self._create_node(memory_total_gb=32, memory_used_gb=8)  # 24GB available
        profile = self._create_profile(memory_gb=16)
        node_score = self._score_node(node, profile)

        result = self.validator.validate(node_score, profile)

        assert result.is_valid is True

    def test_validate_insufficient_memory(self):
        """Test validation fails with insufficient memory"""
        node = self._create_node(memory_total_gb=16, memory_used_gb=14)  # 2GB available
        profile = self._create_profile(memory_gb=8)
        node_score = self._score_node(node, profile)

        result = self.validator.validate(node_score, profile)

        assert result.is_valid is False
        assert any("memory" in err.lower() for err in result.errors)

    def test_validate_memory_overcommit_allowed(self):
        """Test memory overcommit is allowed when configured"""
        validator = ResourceValidator(allow_overcommit_memory=True)
        node = self._create_node(memory_total_gb=16, memory_used_gb=14)  # 2GB available
        profile = self._create_profile(memory_gb=8)
        node_score = self._score_node(node, profile)

        result = validator.validate(node_score, profile)

        assert result.is_valid is True
        assert len(result.warnings) >= 1

    def test_validate_high_load_rejected(self):
        """Test that high load is rejected"""
        validator = ResourceValidator(max_load_ratio=0.8)
        node = self._create_node(cpu_used=22, cpu_total=24)  # ~92% load
        profile = self._create_profile()
        node_score = self._score_node(node, profile)

        result = validator.validate(node_score, profile)

        assert result.is_valid is False
        assert any("overload" in err.lower() for err in result.errors)

    def test_validate_offline_node_rejected(self):
        """Test that offline nodes are rejected via can_schedule"""
        node = self._create_node(status="offline")
        profile = self._create_profile()

        # can_schedule should return False for offline nodes
        result = self.validator.can_schedule(profile, node)

        assert result is False

    def test_can_schedule_sufficient_resources(self):
        """Test can_schedule returns True for sufficient resources"""
        node = self._create_node(gpu_available=1, memory_total_gb=32, memory_used_gb=8)
        profile = self._create_profile(num_gpus=1, memory_gb=16)

        result = self.validator.can_schedule(profile, node)

        assert result is True

    def test_can_schedule_insufficient_gpu(self):
        """Test can_schedule returns False for insufficient GPU"""
        validator = ResourceValidator(allow_overcommit_gpu=False)
        node = self._create_node(gpu_available=0)
        profile = self._create_profile(num_gpus=1)

        result = validator.can_schedule(profile, node)

        assert result is False

    def test_can_schedule_overcommit_allowed(self):
        """Test can_schedule returns True if overcommit allowed"""
        validator = ResourceValidator(allow_overcommit_gpu=True)
        node = self._create_node(gpu_available=0)
        profile = self._create_profile(num_gpus=1)

        result = validator.can_schedule(profile, node)

        assert result is True

    def test_validate_cpu_shortage_warning(self):
        """Test that CPU shortage generates warning not error"""
        # Use a node with moderate load (not 100%) so it doesn't trigger overload
        validator = ResourceValidator(max_load_ratio=0.95)  # Higher threshold
        node = self._create_node(cpu_total=10, cpu_used=5)  # 50% load, 5 available
        profile = self._create_profile(num_cpus=8)  # Need 8, only 5 available
        node_score = self._score_node(node, profile)

        result = validator.validate(node_score, profile)

        # CPU shortage is a warning, not an error
        assert result.is_valid is True
        assert len(result.warnings) >= 1
        assert any("CPU" in w for w in result.warnings)
