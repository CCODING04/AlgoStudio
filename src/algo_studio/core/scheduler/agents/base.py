"""
AgenticScheduler interface definition
"""

from abc import ABC, abstractmethod
from typing import List

from algo_studio.core.task import Task
from algo_studio.core.ray_client import NodeStatus
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile
from algo_studio.core.scheduler.profiles.scheduling_decision import SchedulingDecision


class AgenticSchedulerInterface(ABC):
    """
    Agentic scheduler interface.

    Main interface for the AI scheduling module.
    """

    @abstractmethod
    def schedule(self, task: Task) -> SchedulingDecision:
        """
        Synchronous scheduling decision (Fast Path).

        Args:
            task: Task to schedule

        Returns:
            SchedulingDecision: Scheduling decision
        """
        pass

    @abstractmethod
    async def schedule_async(self, task: Task) -> SchedulingDecision:
        """
        Asynchronous scheduling decision (supports Deep Path).

        Args:
            task: Task to schedule

        Returns:
            SchedulingDecision: Scheduling decision
        """
        pass

    @abstractmethod
    def should_use_deep_path(self, task_profile: TaskProfile) -> bool:
        """
        Determine if task should use Deep Path.

        Args:
            task_profile: Task profile

        Returns:
            bool: True if should use Deep Path
        """
        pass

    @abstractmethod
    def should_use_deep_path_with_context(
        self,
        task_profile: TaskProfile,
        queue_length: int,
        avg_node_load: float,
    ) -> bool:
        """
        Determine if task should use Deep Path with full context.

        Args:
            task_profile: Task profile
            queue_length: Current queue length
            avg_node_load: Average node load

        Returns:
            bool: True if should use Deep Path
        """
        pass
