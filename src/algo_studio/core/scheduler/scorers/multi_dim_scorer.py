"""
MultiDimNodeScorer - Multi-dimensional node scorer implementation
"""

from typing import Dict, List

from algo_studio.core.ray_client import NodeStatus
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile
from algo_studio.core.scheduler.profiles.node_score import NodeScore
from algo_studio.core.scheduler.scorers.base import NodeScorerInterface


class MultiDimNodeScorer(NodeScorerInterface):
    """
    Multi-dimensional node scorer.

    Scores nodes based on:
    - GPU match (GPU availability for GPU tasks)
    - Memory match (memory availability)
    - Load score (current node load - lower is better)
    - Health score (node health status)
    - Affinity score (preferred node matching)
    """

    # Default weights for scoring dimensions
    DEFAULT_WEIGHTS = {
        "gpu_score": 0.35,
        "memory_score": 0.25,
        "load_score": 0.20,
        "health_score": 0.10,
        "affinity_score": 0.10,
    }

    def __init__(self, weights: Dict[str, float] = None):
        """
        Initialize scorer with optional custom weights.

        Args:
            weights: Custom weights for scoring dimensions.
                    If None, uses DEFAULT_WEIGHTS.
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()

    def score(self, task_profile: TaskProfile, nodes: List[NodeStatus]) -> List[NodeScore]:
        """
        Score available nodes based on task profile.

        Args:
            task_profile: Task profile with requirements
            nodes: Available nodes to score

        Returns:
            List[NodeScore]: Node scores sorted by total_score descending
        """
        scored_nodes = []

        for node in nodes:
            if node.status == "offline":
                # Skip offline nodes
                continue

            score = self._score_node(task_profile, node)
            scored_nodes.append(score)

        # Sort by total score descending
        scored_nodes.sort(key=lambda x: x.total_score, reverse=True)
        return scored_nodes

    def _score_node(self, task_profile: TaskProfile, node: NodeStatus) -> NodeScore:
        """
        Score a single node for the given task profile.

        Args:
            task_profile: Task profile with requirements
            node: Node to score

        Returns:
            NodeScore: Calculated node score
        """
        reasons = []
        concerns = []

        # GPU Score (0-100)
        gpu_score = self._calculate_gpu_score(task_profile, node, reasons, concerns)

        # Memory Score (0-100)
        memory_score = self._calculate_memory_score(task_profile, node, reasons, concerns)

        # Load Score (0-100, lower load = higher score)
        load_score = self._calculate_load_score(task_profile, node, reasons, concerns)

        # Health Score (0-100)
        health_score = self._calculate_health_score(node, reasons, concerns)

        # Affinity Score (0-100)
        affinity_score = self._calculate_affinity_score(task_profile, node, reasons, concerns)

        # Calculate total score
        total_score = (
            gpu_score * self.weights["gpu_score"] +
            memory_score * self.weights["memory_score"] +
            load_score * self.weights["load_score"] +
            health_score * self.weights["health_score"] +
            affinity_score * self.weights["affinity_score"]
        ) * 100

        return NodeScore(
            node=node,
            gpu_score=gpu_score,
            memory_score=memory_score,
            load_score=load_score,
            health_score=health_score,
            affinity_score=affinity_score,
            total_score=total_score,
            reasons=reasons,
            concerns=concerns,
        )

    def _calculate_gpu_score(
        self,
        task_profile: TaskProfile,
        node: NodeStatus,
        reasons: List[str],
        concerns: List[str],
    ) -> float:
        """Calculate GPU matching score (0-100)"""
        required_gpus = task_profile.num_gpus
        available_gpus = node.gpu_available

        if required_gpus == 0:
            # CPU-only task, any node is fine
            if node.gpu_total > 0:
                return 80.0  # Prefer nodes without GPU for CPU tasks
            return 100.0

        if available_gpus >= required_gpus:
            # Node has enough GPUs
            utilization = node.gpu_utilization or 0
            if utilization < 30:
                reasons.append(f"Node has {available_gpus} GPUs with low utilization ({utilization}%)")
                return 100.0
            elif utilization < 70:
                reasons.append(f"Node has {available_gpus} GPUs with moderate utilization ({utilization}%)")
                return 85.0
            else:
                reasons.append(f"Node has {available_gpus} GPUs but high utilization ({utilization}%)")
                return 70.0
        elif available_gpus > 0:
            # Node has some GPUs but not enough
            concerns.append(f"Node has only {available_gpus} GPUs, need {required_gpus}")
            return 40.0
        else:
            # No GPU available
            concerns.append("Node has no GPU available")
            return 0.0

    def _calculate_memory_score(
        self,
        task_profile: TaskProfile,
        node: NodeStatus,
        reasons: List[str],
        concerns: List[str],
    ) -> float:
        """Calculate memory matching score (0-100)"""
        required_memory = task_profile.memory_gb
        available_memory = node.memory_available_gb

        if required_memory == 0:
            return 100.0

        if available_memory >= required_memory:
            # Calculate utilization ratio
            utilization_ratio = (node.memory_total_gb - available_memory) / node.memory_total_gb
            if utilization_ratio < 0.5:
                reasons.append(f"Node has {available_memory:.1f}GB memory available")
                return 100.0
            elif utilization_ratio < 0.8:
                reasons.append(f"Node has moderate memory available ({available_memory:.1f}GB)")
                return 80.0
            else:
                return 60.0
        else:
            # Not enough memory
            shortfall = required_memory - available_memory
            concerns.append(f"Memory shortfall: need {required_memory:.1f}GB, only {available_memory:.1f}GB available")
            return max(0.0, 100 - (shortfall / required_memory * 100))

    def _calculate_load_score(
        self,
        task_profile: TaskProfile,
        node: NodeStatus,
        reasons: List[str],
        concerns: List[str],
    ) -> float:
        """Calculate load score (0-100, lower load = higher score)"""
        if node.cpu_total == 0:
            return 50.0  # Unknown

        load_ratio = node.cpu_used / node.cpu_total

        if load_ratio < 0.3:
            reasons.append(f"Node has low CPU load ({load_ratio * 100:.0f}%)")
            return 100.0
        elif load_ratio < 0.6:
            reasons.append(f"Node has moderate CPU load ({load_ratio * 100:.0f}%)")
            return 80.0
        elif load_ratio < 0.85:
            concerns.append(f"Node has high CPU load ({load_ratio * 100:.0f}%)")
            return 50.0
        else:
            concerns.append(f"Node is heavily loaded ({load_ratio * 100:.0f}%)")
            return 25.0

    def _calculate_health_score(
        self,
        node: NodeStatus,
        reasons: List[str],
        concerns: List[str],
    ) -> float:
        """Calculate health score based on node status"""
        if node.status == "idle":
            reasons.append("Node is idle and healthy")
            return 100.0
        elif node.status == "busy":
            concerns.append("Node is busy with other tasks")
            return 60.0
        else:
            concerns.append("Node is offline")
            return 0.0

    def _calculate_affinity_score(
        self,
        task_profile: TaskProfile,
        node: NodeStatus,
        reasons: List[str],
        concerns: List[str],
    ) -> float:
        """Calculate affinity score based on preferred nodes and data locality"""
        hostname = node.hostname or ""
        ip = node.ip or ""

        # Check preferred nodes
        if task_profile.preferred_nodes:
            if hostname in task_profile.preferred_nodes or ip in task_profile.preferred_nodes:
                reasons.append("Node matches preferred nodes")
                return 100.0
            else:
                concerns.append("Node does not match preferred nodes")
                return 30.0

        # Check data locality
        if task_profile.data_locality:
            if hostname == task_profile.data_locality or ip == task_profile.data_locality:
                reasons.append("Node has data locality")
                return 100.0
            else:
                concerns.append("Node lacks data locality")
                return 30.0

        # No affinity preferences
        return 50.0

    def explain_score(self, node_score: NodeScore) -> str:
        """
        Generate human-readable explanation of the score.

        Args:
            node_score: Node score to explain

        Returns:
            str: Human-readable explanation
        """
        return node_score.explain_score()
