# tests/test_scheduler/test_node_scorer.py
"""Tests for MultiDimNodeScorer"""

import pytest
from algo_studio.core.ray_client import NodeStatus
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile, TaskType
from algo_studio.core.scheduler.scorers.multi_dim_scorer import MultiDimNodeScorer


class TestMultiDimNodeScorer:
    """Test suite for MultiDimNodeScorer"""

    def setup_method(self):
        """Set up test fixtures"""
        self.scorer = MultiDimNodeScorer()

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

    def _create_profile(
        self,
        num_gpus=0,
        num_cpus=1,
        memory_gb=0.0,
        preferred_nodes=None,
        data_locality=None,
    ):
        """Helper to create TaskProfile"""
        return TaskProfile(
            task_id="test-task",
            task_type=TaskType.INFER,
            num_gpus=num_gpus,
            num_cpus=num_cpus,
            memory_gb=memory_gb,
            preferred_nodes=preferred_nodes or [],
            data_locality=data_locality,
        )

    def test_score_single_idle_gpu_node(self):
        """Test scoring an idle GPU node for GPU task"""
        node = self._create_node(
            gpu_used=0,
            gpu_total=1,
            status="idle",
        )
        profile = self._create_profile(num_gpus=1)

        scores = self.scorer.score(profile, [node])

        assert len(scores) == 1
        assert scores[0].gpu_score == 100.0  # Low utilization
        assert scores[0].total_score > 0

    def test_score_cpu_task_on_gpu_node(self):
        """Test scoring a GPU node for CPU-only task (should prefer it)"""
        node = self._create_node(
            gpu_used=0,
            gpu_total=1,
            status="idle",
        )
        profile = self._create_profile(num_gpus=0)  # CPU-only task

        scores = self.scorer.score(profile, [node])

        assert len(scores) == 1
        assert scores[0].gpu_score == 80.0  # CPU task on GPU node, slightly preferred

    def test_score_node_with_insufficient_gpu(self):
        """Test scoring node with fewer GPUs than required"""
        node = self._create_node(
            gpu_used=1,
            gpu_total=1,  # No available GPU
            status="busy",
        )
        profile = self._create_profile(num_gpus=1)

        scores = self.scorer.score(profile, [node])

        assert len(scores) == 1
        assert scores[0].gpu_score == 0.0
        assert any("GPU" in c for c in scores[0].concerns)

    def test_score_busy_node(self):
        """Test scoring a busy node (lower health score)"""
        node = self._create_node(status="busy", cpu_used=20, cpu_total=24)
        profile = self._create_profile()

        scores = self.scorer.score(profile, [node])

        assert len(scores) == 1
        assert scores[0].health_score == 60.0  # Busy
        assert any("busy" in c.lower() for c in scores[0].concerns)

    def test_score_offline_node(self):
        """Test that offline nodes are skipped"""
        node = self._create_node(status="offline")
        profile = self._create_profile()

        scores = self.scorer.score(profile, [node])

        assert len(scores) == 0  # Offline nodes skipped

    def test_score_preferred_node_match(self):
        """Test that preferred nodes get high affinity score"""
        node = self._create_node(hostname="worker-1")
        profile = self._create_profile(preferred_nodes=["worker-1"])

        scores = self.scorer.score(profile, [node])

        assert len(scores) == 1
        assert scores[0].affinity_score == 100.0
        assert any("preferred" in r.lower() for r in scores[0].reasons)

    def test_score_preferred_node_no_match(self):
        """Test that non-preferred nodes get lower affinity score"""
        node = self._create_node(hostname="worker-2")
        profile = self._create_profile(preferred_nodes=["worker-1"])

        scores = self.scorer.score(profile, [node])

        assert len(scores) == 1
        assert scores[0].affinity_score == 30.0
        assert "not match" in scores[0].concerns[0].lower()

    def test_score_data_locality_match(self):
        """Test that data locality is considered"""
        node = self._create_node(hostname="data-node")
        profile = self._create_profile(data_locality="data-node")

        scores = self.scorer.score(profile, [node])

        assert len(scores) == 1
        assert scores[0].affinity_score == 100.0
        assert any("data locality" in r.lower() for r in scores[0].reasons)

    def test_score_multiple_nodes_sorted_by_score(self):
        """Test that nodes are sorted by total score descending"""
        node1 = self._create_node(hostname="gpu-node", gpu_total=1, gpu_used=1, status="busy")
        node2 = self._create_node(hostname="idle-node", gpu_total=1, gpu_used=0, status="idle")
        profile = self._create_profile(num_gpus=1)

        scores = self.scorer.score(profile, [node1, node2])

        assert len(scores) == 2
        # Idle node should score higher
        assert scores[0].total_score >= scores[1].total_score

    def test_score_low_load_node(self):
        """Test that low load nodes score higher"""
        low_load = self._create_node(cpu_used=4, cpu_total=24)  # ~17% load
        high_load = self._create_node(cpu_used=20, cpu_total=24)  # ~83% load
        profile = self._create_profile()

        low_scores = self.scorer.score(profile, [low_load])
        high_scores = self.scorer.score(profile, [high_load])

        assert low_scores[0].load_score > high_scores[0].load_score

    def test_explain_score(self):
        """Test score explanation generation"""
        node = self._create_node(
            hostname="worker-1",
            gpu_total=1,
            gpu_used=0,
            status="idle",
        )
        profile = self._create_profile(num_gpus=1)

        scores = self.scorer.score(profile, [node])
        explanation = self.scorer.explain_score(scores[0])

        assert "worker-1" in explanation
        assert "100.0" in explanation  # Total score
        assert "GPU" in explanation

    def test_default_weights(self):
        """Test that default weights are applied"""
        scorer = MultiDimNodeScorer()

        assert scorer.weights["gpu_score"] == 0.35
        assert scorer.weights["memory_score"] == 0.25
        assert scorer.weights["load_score"] == 0.20
        assert scorer.weights["health_score"] == 0.10
        assert scorer.weights["affinity_score"] == 0.10

    def test_custom_weights(self):
        """Test that custom weights can be applied"""
        custom_weights = {
            "gpu_score": 0.50,
            "memory_score": 0.20,
            "load_score": 0.15,
            "health_score": 0.10,
            "affinity_score": 0.05,
        }
        scorer = MultiDimNodeScorer(weights=custom_weights)

        assert scorer.weights["gpu_score"] == 0.50
        assert scorer.weights["affinity_score"] == 0.05
