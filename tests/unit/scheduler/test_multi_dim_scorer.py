# tests/unit/scheduler/test_multi_dim_scorer.py
"""Unit tests for MultiDimNodeScorer."""

import pytest
from unittest.mock import MagicMock
from algo_studio.core.scheduler.scorers.multi_dim_scorer import MultiDimNodeScorer
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile, TaskType
from algo_studio.core.ray_client import NodeStatus


class TestMultiDimNodeScorer:
    """Tests for MultiDimNodeScorer."""

    @pytest.fixture
    def scorer(self):
        """Create a MultiDimNodeScorer with default weights."""
        return MultiDimNodeScorer()

    @pytest.fixture
    def scorer_custom_weights(self):
        """Create a scorer with custom weights."""
        custom_weights = {
            "gpu_score": 0.40,
            "memory_score": 0.30,
            "load_score": 0.15,
            "health_score": 0.10,
            "affinity_score": 0.05,
        }
        return MultiDimNodeScorer(weights=custom_weights)

    @pytest.fixture
    def gpu_task_profile(self):
        """Create a GPU-requiring task profile."""
        return TaskProfile(
            task_id="gpu-task-001",
            task_type=TaskType.TRAIN,
            num_gpus=1,
            memory_gb=16,
            priority=5,
        )

    @pytest.fixture
    def cpu_task_profile(self):
        """Create a CPU-only task profile."""
        return TaskProfile(
            task_id="cpu-task-001",
            task_type=TaskType.INFER,
            num_gpus=0,
            memory_gb=8,
            priority=5,
        )

    @pytest.fixture
    def node_idle_with_gpu(self):
        """Create an idle node with GPU available."""
        return NodeStatus(
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

    @pytest.fixture
    def node_busy_with_gpu(self):
        """Create a busy node with GPU in use."""
        return NodeStatus(
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

    @pytest.fixture
    def node_cpu_only(self):
        """Create a CPU-only node."""
        return NodeStatus(
            node_id="node-003",
            ip="192.168.0.12",
            status="idle",
            cpu_used=1,
            cpu_total=8,
            gpu_used=0,
            gpu_total=0,  # No GPU
            memory_used_gb=8,
            memory_total_gb=32,
            disk_used_gb=50,
            disk_total_gb=200,
            hostname="cpu-worker",
        )

    def test_scorer_has_default_weights(self, scorer):
        """Test that scorer has expected default weights."""
        assert scorer.weights["gpu_score"] == 0.35
        assert scorer.weights["memory_score"] == 0.25
        assert scorer.weights["load_score"] == 0.20
        assert scorer.weights["health_score"] == 0.10
        assert scorer.weights["affinity_score"] == 0.10

    def test_scorer_accepts_custom_weights(self, scorer_custom_weights):
        """Test that scorer accepts custom weights."""
        assert scorer_custom_weights.weights["gpu_score"] == 0.40
        assert scorer_custom_weights.weights["memory_score"] == 0.30

    def test_score_returns_list(self, scorer, gpu_task_profile, node_idle_with_gpu):
        """Test that score returns a list of NodeScore."""
        result = scorer.score(gpu_task_profile, [node_idle_with_gpu])
        assert isinstance(result, list)
        assert len(result) == 1

    def test_score_sorts_by_total_score_descending(self, scorer, gpu_task_profile):
        """Test that nodes are sorted by total score descending."""
        node_low = NodeStatus(
            node_id="low",
            ip="10.0.0.1",
            status="busy",
            cpu_used=7,
            cpu_total=8,
            gpu_used=2,
            gpu_total=2,
            memory_used_gb=60,
            memory_total_gb=64,
            disk_used_gb=400,
            disk_total_gb=500,
            gpu_utilization=95,
            hostname="low-node",
        )
        node_high = NodeStatus(
            node_id="high",
            ip="10.0.0.2",
            status="idle",
            cpu_used=1,
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=8,
            memory_total_gb=64,
            disk_used_gb=50,
            disk_total_gb=500,
            gpu_utilization=0,
            hostname="high-node",
        )
        nodes = [node_low, node_high]
        result = scorer.score(gpu_task_profile, nodes)
        assert result[0].node.node_id == "high"
        assert result[1].node.node_id == "low"

    def test_score_skips_offline_nodes(self, scorer, gpu_task_profile):
        """Test that offline nodes are skipped."""
        offline_node = NodeStatus(
            node_id="offline",
            ip="10.0.0.99",
            status="offline",
            cpu_used=0,
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=0,
            memory_total_gb=64,
            disk_used_gb=0,
            disk_total_gb=500,
            hostname="offline-node",
        )
        result = scorer.score(gpu_task_profile, [offline_node])
        assert len(result) == 0

    def test_gpu_score_sufficient_gpus_low_utilization(self, scorer, gpu_task_profile, node_idle_with_gpu):
        """Test GPU score for node with sufficient GPUs and low utilization."""
        result = scorer.score(gpu_task_profile, [node_idle_with_gpu])
        assert len(result) == 1
        assert result[0].gpu_score == 100.0
        assert "low utilization" in result[0].reasons[0]

    def test_gpu_score_sufficient_gpus_moderate_utilization(self, scorer, gpu_task_profile):
        """Test GPU score for node with moderate utilization."""
        node = NodeStatus(
            node_id="mod",
            ip="10.0.0.1",
            status="idle",
            cpu_used=2,
            cpu_total=8,
            gpu_used=1,
            gpu_total=2,
            memory_used_gb=32,
            memory_total_gb=64,
            disk_used_gb=100,
            disk_total_gb=500,
            gpu_utilization=50,  # Moderate
            hostname="mod-node",
        )
        result = scorer.score(gpu_task_profile, [node])
        assert result[0].gpu_score == 85.0

    def test_gpu_score_sufficient_gpus_high_utilization(self, scorer, gpu_task_profile, node_busy_with_gpu):
        """Test GPU score for node with high utilization."""
        result = scorer.score(gpu_task_profile, [node_busy_with_gpu])
        assert result[0].gpu_score == 70.0

    def test_gpu_score_insufficient_gpus(self, scorer, gpu_task_profile):
        """Test GPU score when node has some but not enough GPUs."""
        # Task requires 2 GPUs, node has 1 available (2 total - 1 used = 1 available)
        node = NodeStatus(
            node_id="partial",
            ip="10.0.0.1",
            status="idle",
            cpu_used=2,
            cpu_total=8,
            gpu_used=1,
            gpu_total=2,
            memory_used_gb=32,
            memory_total_gb=64,
            disk_used_gb=100,
            disk_total_gb=500,
            gpu_utilization=50,
            hostname="partial-node",
        )
        # Override task to require 2 GPUs
        gpu_task_profile.num_gpus = 2
        result = scorer.score(gpu_task_profile, [node])
        assert result[0].gpu_score == 40.0
        assert any("need 2" in c for c in result[0].concerns)

    def test_gpu_score_no_gpu_available(self, scorer, gpu_task_profile, node_cpu_only):
        """Test GPU score when task requires GPU but node has none."""
        result = scorer.score(gpu_task_profile, [node_cpu_only])
        assert result[0].gpu_score == 0.0
        assert any("no GPU" in c for c in result[0].concerns)

    def test_gpu_score_cpu_task_prefers_no_gpu(self, scorer, cpu_task_profile, node_idle_with_gpu):
        """Test that CPU-only task prefers nodes without GPU."""
        result = scorer.score(cpu_task_profile, [node_idle_with_gpu])
        assert result[0].gpu_score == 80.0  # CPU task on GPU node

    def test_gpu_score_cpu_task_no_gpu_is_optimal(self, scorer, cpu_task_profile, node_cpu_only):
        """Test that CPU-only task gets best score on CPU-only node."""
        result = scorer.score(cpu_task_profile, [node_cpu_only])
        assert result[0].gpu_score == 100.0

    def test_memory_score_sufficient_memory(self, scorer, gpu_task_profile, node_idle_with_gpu):
        """Test memory score when node has sufficient memory."""
        result = scorer.score(gpu_task_profile, [node_idle_with_gpu])
        # Node has 48GB available (64-16), task needs 16GB
        # Utilization ratio = (64-48)/64 = 0.25 < 0.5
        assert result[0].memory_score == 100.0

    def test_memory_score_moderate_utilization(self, scorer):
        """Test memory score with moderate utilization."""
        node = NodeStatus(
            node_id="mod-mem",
            ip="10.0.0.1",
            status="idle",
            cpu_used=2,
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=48,  # 16GB available out of 64GB
            memory_total_gb=64,
            disk_used_gb=100,
            disk_total_gb=500,
            hostname="mod-mem-node",
        )
        profile = TaskProfile(task_id="t", task_type=TaskType.TRAIN, memory_gb=16)
        result = scorer.score(profile, [node])
        # Utilization ratio = (64-16)/64 = 0.75, which is >= 0.5 but < 0.8
        assert result[0].memory_score == 80.0

    def test_memory_score_insufficient_memory(self, scorer, gpu_task_profile):
        """Test memory score when node doesn't have enough memory."""
        node = NodeStatus(
            node_id="low-mem",
            ip="10.0.0.1",
            status="idle",
            cpu_used=2,
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=60,  # Only 4GB available
            memory_total_gb=64,
            disk_used_gb=100,
            disk_total_gb=500,
            hostname="low-mem-node",
        )
        result = scorer.score(gpu_task_profile, [node])
        assert result[0].memory_score < 100.0
        assert any("shortfall" in c.lower() for c in result[0].concerns)

    def test_load_score_low_load(self, scorer, gpu_task_profile, node_idle_with_gpu):
        """Test load score for low load node."""
        result = scorer.score(gpu_task_profile, [node_idle_with_gpu])
        # Load = 2/8 = 0.25 < 0.3
        assert result[0].load_score == 100.0

    def test_load_score_moderate_load(self, scorer):
        """Test load score for moderate load node."""
        node = NodeStatus(
            node_id="mod-load",
            ip="10.0.0.1",
            status="idle",
            cpu_used=4,  # 4/8 = 0.5
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=16,
            memory_total_gb=64,
            disk_used_gb=100,
            disk_total_gb=500,
            hostname="mod-load-node",
        )
        profile = TaskProfile(task_id="t", task_type=TaskType.TRAIN)
        result = scorer.score(profile, [node])
        assert result[0].load_score == 80.0

    def test_load_score_high_load(self, scorer):
        """Test load score for high load node."""
        node = NodeStatus(
            node_id="high-load",
            ip="10.0.0.1",
            status="idle",
            cpu_used=7,  # 7/8 = 0.875 which is >= 0.85, so heavy (25.0)
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=16,
            memory_total_gb=64,
            disk_used_gb=100,
            disk_total_gb=500,
            hostname="high-load-node",
        )
        profile = TaskProfile(task_id="t", task_type=TaskType.TRAIN)
        result = scorer.score(profile, [node])
        # 7/8 = 0.875 >= 0.85, so returns 25.0 (heavily loaded)
        assert result[0].load_score == 25.0

    def test_load_score_heavy_load(self, scorer):
        """Test load score for heavily loaded node."""
        node = NodeStatus(
            node_id="heavy-load",
            ip="10.0.0.1",
            status="idle",
            cpu_used=8,  # 8/8 = 1.0
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=16,
            memory_total_gb=64,
            disk_used_gb=100,
            disk_total_gb=500,
            hostname="heavy-load-node",
        )
        profile = TaskProfile(task_id="t", task_type=TaskType.TRAIN)
        result = scorer.score(profile, [node])
        assert result[0].load_score == 25.0

    def test_health_score_idle(self, scorer, gpu_task_profile, node_idle_with_gpu):
        """Test health score for idle node."""
        result = scorer.score(gpu_task_profile, [node_idle_with_gpu])
        assert result[0].health_score == 100.0
        # Check that "idle" appears in reasons (may not be first due to GPU reasons)
        assert any("idle" in r.lower() for r in result[0].reasons)

    def test_health_score_busy(self, scorer, gpu_task_profile, node_busy_with_gpu):
        """Test health score for busy node."""
        result = scorer.score(gpu_task_profile, [node_busy_with_gpu])
        assert result[0].health_score == 60.0
        assert any("busy" in c.lower() for c in result[0].concerns)

    def test_health_score_offline(self, scorer):
        """Test health score for offline node (should be skipped)."""
        node = NodeStatus(
            node_id="offline",
            ip="10.0.0.1",
            status="offline",
            cpu_used=0,
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=0,
            memory_total_gb=64,
            disk_used_gb=0,
            disk_total_gb=500,
            hostname="offline-node",
        )
        profile = TaskProfile(task_id="t", task_type=TaskType.TRAIN)
        result = scorer.score(profile, [node])
        assert len(result) == 0  # Offline nodes skipped

    def test_affinity_score_preferred_node_match(self, scorer):
        """Test affinity score when node matches preferred nodes."""
        node = NodeStatus(
            node_id="pref",
            ip="192.168.0.100",
            status="idle",
            cpu_used=2,
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=16,
            memory_total_gb=64,
            disk_used_gb=100,
            disk_total_gb=500,
            hostname="preferred-worker",
        )
        profile = TaskProfile(
            task_id="t",
            task_type=TaskType.TRAIN,
            preferred_nodes=["preferred-worker"],
        )
        result = scorer.score(profile, [node])
        assert result[0].affinity_score == 100.0
        assert any("preferred nodes" in r.lower() for r in result[0].reasons)

    def test_affinity_score_preferred_node_no_match(self, scorer):
        """Test affinity score when node doesn't match preferred nodes."""
        node = NodeStatus(
            node_id="other",
            ip="192.168.0.200",
            status="idle",
            cpu_used=2,
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=16,
            memory_total_gb=64,
            disk_used_gb=100,
            disk_total_gb=500,
            hostname="other-worker",
        )
        profile = TaskProfile(
            task_id="t",
            task_type=TaskType.TRAIN,
            preferred_nodes=["preferred-worker"],
        )
        result = scorer.score(profile, [node])
        assert result[0].affinity_score == 30.0
        assert any("preferred" in c.lower() for c in result[0].concerns)

    def test_affinity_score_data_locality_match(self, scorer):
        """Test affinity score when node has data locality."""
        node = NodeStatus(
            node_id="data-node",
            ip="192.168.0.50",
            status="idle",
            cpu_used=2,
            cpu_total=8,
            gpu_used=0,
            gpu_total=2,
            memory_used_gb=16,
            memory_total_gb=64,
            disk_used_gb=100,
            disk_total_gb=500,
            hostname="storage-node",
        )
        profile = TaskProfile(
            task_id="t",
            task_type=TaskType.TRAIN,
            data_locality="storage-node",
        )
        result = scorer.score(profile, [node])
        assert result[0].affinity_score == 100.0
        assert any("data locality" in r.lower() for r in result[0].reasons)

    def test_affinity_score_no_preference(self, scorer, gpu_task_profile, node_idle_with_gpu):
        """Test affinity score when task has no affinity preference."""
        result = scorer.score(gpu_task_profile, [node_idle_with_gpu])
        assert result[0].affinity_score == 50.0  # Neutral score

    def test_total_score_calculation(self, scorer, gpu_task_profile, node_idle_with_gpu):
        """Test that total score is calculated correctly with weights."""
        result = scorer.score(gpu_task_profile, [node_idle_with_gpu])
        expected = (
            result[0].gpu_score * 0.35 +
            result[0].memory_score * 0.25 +
            result[0].load_score * 0.20 +
            result[0].health_score * 0.10 +
            result[0].affinity_score * 0.10
        ) * 100
        assert abs(result[0].total_score - expected) < 0.01

    def test_explain_score(self, scorer, gpu_task_profile, node_idle_with_gpu):
        """Test that explain_score returns human-readable string."""
        result = scorer.score(gpu_task_profile, [node_idle_with_gpu])
        explanation = scorer.explain_score(result[0])
        assert "worker-1" in explanation
        assert "Total Score" in explanation
        assert "GPU Match" in explanation

    def test_empty_node_list(self, scorer, gpu_task_profile):
        """Test scoring with empty node list."""
        result = scorer.score(gpu_task_profile, [])
        assert result == []

    def test_uses_custom_weights(self, scorer_custom_weights, gpu_task_profile, node_idle_with_gpu):
        """Test that custom weights affect scoring."""
        result = scorer_custom_weights.score(gpu_task_profile, [node_idle_with_gpu])
        # With custom weights, total should be different from default
        # GPU has more weight (0.40 vs 0.35), so idle GPU node should score higher
        expected = (
            result[0].gpu_score * 0.40 +
            result[0].memory_score * 0.30 +
            result[0].load_score * 0.15 +
            result[0].health_score * 0.10 +
            result[0].affinity_score * 0.05
        ) * 100
        assert abs(result[0].total_score - expected) < 0.01
