"""
Router - Fast/Deep path routing decision maker
"""

from typing import Optional

from algo_studio.core.scheduler.profiles.task_profile import TaskProfile


class Router:
    """
    Router decides whether to use Fast Path or Deep Path for a task.

    Fast Path: Rule-based scheduling (< 10ms latency)
    Deep Path: LLM-based scheduling (500ms - 2s latency)
    """

    # Fast Path decision rules
    DEFAULT_RULES = {
        "complexity_threshold": 7,
        "retry_count_threshold": 2,
        "queue_length_threshold": 20,
        "load_threshold": 0.7,
        "timeout_threshold_minutes": 120,
    }

    def __init__(self, rules: dict = None):
        """
        Initialize router with optional custom rules.

        Args:
            rules: Custom routing rules. If None, uses DEFAULT_RULES.
        """
        self.rules = rules or self.DEFAULT_RULES.copy()

    def should_use_deep_path(self, task_profile: TaskProfile) -> bool:
        """
        Determine if task should use Deep Path (basic version).

        Uses only task profile information.

        Args:
            task_profile: Task profile

        Returns:
            bool: True if should use Deep Path, False for Fast Path
        """
        return self._evaluate_rules(task_profile, queue_length=0, avg_node_load=0.0)

    def should_use_deep_path_with_context(
        self,
        task_profile: TaskProfile,
        queue_length: int,
        avg_node_load: float,
    ) -> bool:
        """
        Determine if task should use Deep Path (full context version).

        Uses task profile and cluster context.

        Decision rules (any condition triggers Deep Path):
        1. Task complexity >= 7 (multi-dimensional resource needs, affinity constraints)
        2. Retry task with retry_count >= 2
        3. Queue length > 20 AND avg_node_load > 0.7 (high load scenario)
        4. Task requires specific node affinity (preferred_nodes non-empty)
        5. Task timeout > 120 minutes (long-running task)
        6. Previous Fast Path failed (is_retry=True AND fallback_used=True)

        Args:
            task_profile: Task profile
            queue_length: Number of tasks waiting to be scheduled
            avg_node_load: Average node load across cluster (0.0-1.0)

        Returns:
            bool: True if should use Deep Path, False for Fast Path
        """
        return self._evaluate_rules(task_profile, queue_length, avg_node_load)

    def _evaluate_rules(
        self,
        task_profile: TaskProfile,
        queue_length: int,
        avg_node_load: float,
    ) -> bool:
        """
        Evaluate routing rules.

        Args:
            task_profile: Task profile
            queue_length: Current queue length
            avg_node_load: Average node load

        Returns:
            bool: True if Deep Path should be used
        """
        # Rule 1: Task complexity
        if task_profile.complexity >= self.rules["complexity_threshold"]:
            return True

        # Rule 2: Retry count
        if task_profile.is_retry and task_profile.retry_count >= self.rules["retry_count_threshold"]:
            return True

        # Rule 3: High load scenario
        if (
            queue_length > self.rules["queue_length_threshold"] and
            avg_node_load > self.rules["load_threshold"]
        ):
            return True

        # Rule 4: Node affinity required
        if task_profile.preferred_nodes:
            return True

        # Rule 5: Long-running task
        if task_profile.timeout_minutes > self.rules["timeout_threshold_minutes"]:
            return True

        # Rule 6: Previous Fast Path failed
        if task_profile.is_retry:
            # This would need to track fallback_used in the task profile
            # For now, we treat retry as potential Fast Path failure
            return True

        return False

    def get_routing_reason(
        self,
        task_profile: TaskProfile,
        queue_length: int = 0,
        avg_node_load: float = 0.0,
    ) -> str:
        """
        Get human-readable reason for routing decision.

        Args:
            task_profile: Task profile
            queue_length: Current queue length
            avg_node_load: Average node load

        Returns:
            str: Human-readable reason
        """
        reasons = []

        if task_profile.complexity >= self.rules["complexity_threshold"]:
            reasons.append(f"High complexity ({task_profile.complexity} >= {self.rules['complexity_threshold']})")

        if task_profile.is_retry and task_profile.retry_count >= self.rules["retry_count_threshold"]:
            reasons.append(f"Multiple retries (count={task_profile.retry_count})")

        if queue_length > self.rules["queue_length_threshold"] and avg_node_load > self.rules["load_threshold"]:
            reasons.append(f"High cluster load (queue={queue_length}, load={avg_node_load:.1%})")

        if task_profile.preferred_nodes:
            reasons.append(f"Node affinity required ({task_profile.preferred_nodes})")

        if task_profile.timeout_minutes > self.rules["timeout_threshold_minutes"]:
            reasons.append(f"Long-running task ({task_profile.timeout_minutes} min)")

        if task_profile.is_retry:
            reasons.append("Retry task (potential Fast Path failure)")

        if reasons:
            return "Deep Path selected: " + "; ".join(reasons)
        else:
            return "Fast Path selected: Simple task"
