"""
SafetyValidator interface definition
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from algo_studio.core.ray_client import NodeStatus
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile
from algo_studio.core.scheduler.profiles.node_score import NodeScore


@dataclass
class ValidationResult:
    """Result of validation check"""

    is_valid: bool
    errors: List[str]
    warnings: List[str]

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


class SafetyValidatorInterface(ABC):
    """
    Safety validator interface.

    Validates node scores to ensure they are safe to execute.
    """

    @abstractmethod
    def validate(
        self,
        node_score: NodeScore,
        task_profile: TaskProfile,
    ) -> ValidationResult:
        """
        Validate a node score before making scheduling decision.

        Args:
            node_score: Node score to validate
            task_profile: Original task profile

        Returns:
            ValidationResult: Validation result
        """
        pass

    @abstractmethod
    def can_schedule(self, task_profile: TaskProfile, node: NodeStatus) -> bool:
        """
        Quick check if task can be scheduled on node.

        Args:
            task_profile: Task profile
            node: Target node

        Returns:
            bool: True if task can be scheduled
        """
        pass
