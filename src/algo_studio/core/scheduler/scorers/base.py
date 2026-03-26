"""
NodeScorer interface definition
"""

from abc import ABC, abstractmethod
from typing import List

from algo_studio.core.ray_client import NodeStatus
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile
from algo_studio.core.scheduler.profiles.node_score import NodeScore


class NodeScorerInterface(ABC):
    """
    Node scorer interface.

    Scores available nodes based on task requirements.
    """

    @abstractmethod
    def score(self, task_profile: TaskProfile, nodes: List[NodeStatus]) -> List[NodeScore]:
        """
        Score available nodes based on task profile.

        Args:
            task_profile: Task profile with requirements
            nodes: Available nodes to score

        Returns:
            List[NodeScore]: Node scores sorted by total_score descending
        """
        pass

    @abstractmethod
    def explain_score(self, node_score: NodeScore) -> str:
        """
        Explain node score in human-readable format.

        Args:
            node_score: Node score to explain

        Returns:
            str: Human-readable explanation
        """
        pass
