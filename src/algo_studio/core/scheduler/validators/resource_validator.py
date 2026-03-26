"""
ResourceValidator - Validates scheduling decisions against resource constraints
"""

from typing import List

from algo_studio.core.ray_client import NodeStatus
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile
from algo_studio.core.scheduler.profiles.node_score import NodeScore
from algo_studio.core.scheduler.validators.base import SafetyValidatorInterface, ValidationResult


class ResourceValidator(SafetyValidatorInterface):
    """
    Resource-based safety validator.

    Ensures that scheduling decisions satisfy resource constraints.
    """

    def __init__(
        self,
        allow_overcommit_gpu: bool = False,
        allow_overcommit_memory: bool = False,
        max_load_ratio: float = 0.95,
    ):
        """
        Initialize resource validator.

        Args:
            allow_overcommit_gpu: Allow GPU overcommitment
            allow_overcommit_memory: Allow memory overcommitment
            max_load_ratio: Maximum load ratio before rejecting (0.0-1.0)
        """
        self.allow_overcommit_gpu = allow_overcommit_gpu
        self.allow_overcommit_memory = allow_overcommit_memory
        self.max_load_ratio = max_load_ratio

    def validate(
        self,
        node_score: NodeScore,
        task_profile: TaskProfile,
    ) -> ValidationResult:
        """
        Validate a node score.

        Args:
            node_score: Node score to validate
            task_profile: Original task profile

        Returns:
            ValidationResult: Validation result
        """
        errors = []
        warnings = []

        node = node_score.node

        # Check GPU availability
        if task_profile.num_gpus > 0:
            if node.gpu_available < task_profile.num_gpus:
                if self.allow_overcommit_gpu:
                    warnings.append(
                        f"GPU overcommit: need {task_profile.num_gpus}, "
                        f"only {node.gpu_available} available"
                    )
                else:
                    errors.append(
                        f"Insufficient GPU: need {task_profile.num_gpus}, "
                        f"only {node.gpu_available} available"
                    )

        # Check CPU availability
        if task_profile.num_cpus > 0:
            if node.cpu_available < task_profile.num_cpus:
                warnings.append(
                    f"CPU shortage: need {task_profile.num_cpus}, "
                    f"only {node.cpu_available} available"
                )

        # Check memory availability
        if task_profile.memory_gb > 0:
            if node.memory_available_gb < task_profile.memory_gb:
                if self.allow_overcommit_memory:
                    warnings.append(
                        f"Memory overcommit: need {task_profile.memory_gb:.1f}GB, "
                        f"only {node.memory_available_gb:.1f}GB available"
                    )
                else:
                    errors.append(
                        f"Insufficient memory: need {task_profile.memory_gb:.1f}GB, "
                        f"only {node.memory_available_gb:.1f}GB available"
                    )

        # Check node load
        if node.cpu_total > 0:
            load_ratio = node.cpu_used / node.cpu_total
            if load_ratio >= self.max_load_ratio:
                errors.append(f"Node overload: CPU load {load_ratio * 100:.0f}% exceeds max {self.max_load_ratio * 100:.0f}%")

        # Check node status
        if node.status == "offline":
            errors.append("Node is offline")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def can_schedule(self, task_profile: TaskProfile, node: NodeStatus) -> bool:
        """
        Quick check if task can be scheduled on node.

        Args:
            task_profile: Task profile
            node: Target node

        Returns:
            bool: True if task can be scheduled
        """
        # Check GPU
        if task_profile.num_gpus > 0 and node.gpu_available < task_profile.num_gpus:
            if not self.allow_overcommit_gpu:
                return False

        # Check memory (with tolerance)
        if task_profile.memory_gb > 0 and node.memory_available_gb < task_profile.memory_gb * 0.8:
            if not self.allow_overcommit_memory:
                return False

        # Check load
        if node.cpu_total > 0:
            load_ratio = node.cpu_used / node.cpu_total
            if load_ratio >= self.max_load_ratio:
                return False

        # Check status
        if node.status == "offline":
            return False

        return True
