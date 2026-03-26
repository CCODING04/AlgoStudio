"""
ComplexityEvaluator - Evaluates task complexity for routing decisions
"""

from typing import Dict

from algo_studio.core.scheduler.profiles.task_profile import TaskProfile


class ComplexityEvaluator:
    """
    Evaluates task complexity on a scale of 1-10.

    Higher complexity tasks benefit from Deep Path (LLM-based) scheduling.
    """

    # Weight factors for complexity calculation
    DEFAULT_FACTORS = {
        "gpu_weight": 2,          # GPU requirement adds complexity
        "memory_weight": 1,       # Memory requirement adds complexity
        "affinity_weight": 2,     # Node affinity adds complexity
        "data_locality_weight": 1,  # Data locality adds complexity
        "priority_weight": 1,      # High priority adds complexity
        "duration_weight": 1,     # Long duration adds complexity
        "retry_weight": 1,       # Retry task adds complexity
    }

    def __init__(self, factors: Dict[str, int] = None):
        """
        Initialize complexity evaluator.

        Args:
            factors: Custom weight factors. If None, uses DEFAULT_FACTORS.
        """
        self.factors = factors or self.DEFAULT_FACTORS.copy()

    def evaluate(self, task_profile: TaskProfile) -> int:
        """
        Evaluate task complexity.

        Args:
            task_profile: Task profile to evaluate

        Returns:
            int: Complexity score (1-10)
        """
        score = 1  # Base score

        # GPU complexity
        if task_profile.num_gpus > 0:
            score += self.factors["gpu_weight"]

        # High memory complexity
        if task_profile.memory_gb > 16:
            score += self.factors["memory_weight"]

        # Affinity complexity
        if task_profile.preferred_nodes:
            score += self.factors["affinity_weight"]

        # Data locality complexity
        if task_profile.data_locality:
            score += self.factors["data_locality_weight"]

        # High priority complexity
        if task_profile.priority >= 8:
            score += self.factors["priority_weight"]

        # Long-running task complexity
        if task_profile.estimated_duration_minutes > 60:
            score += self.factors["duration_weight"]

        # Retry complexity
        if task_profile.is_retry:
            score += self.factors["retry_weight"]

        return min(score, 10)  # Cap at 10

    def get_complexity_breakdown(self, task_profile: TaskProfile) -> Dict[str, any]:
        """
        Get detailed breakdown of complexity factors.

        Args:
            task_profile: Task profile to evaluate

        Returns:
            dict: Breakdown of complexity factors
        """
        factors = {}

        factors["base"] = 1

        if task_profile.num_gpus > 0:
            factors["gpu"] = self.factors["gpu_weight"]
        else:
            factors["gpu"] = 0

        if task_profile.memory_gb > 16:
            factors["memory"] = self.factors["memory_weight"]
        else:
            factors["memory"] = 0

        if task_profile.preferred_nodes:
            factors["affinity"] = self.factors["affinity_weight"]
        else:
            factors["affinity"] = 0

        if task_profile.data_locality:
            factors["data_locality"] = self.factors["data_locality_weight"]
        else:
            factors["data_locality"] = 0

        if task_profile.priority >= 8:
            factors["priority"] = self.factors["priority_weight"]
        else:
            factors["priority"] = 0

        if task_profile.estimated_duration_minutes > 60:
            factors["duration"] = self.factors["duration_weight"]
        else:
            factors["duration"] = 0

        if task_profile.is_retry:
            factors["retry"] = self.factors["retry_weight"]
        else:
            factors["retry"] = 0

        factors["total"] = min(sum(factors.values()), 10)

        return factors
