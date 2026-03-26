"""
TaskAnalyzer interface definition
"""

from abc import ABC, abstractmethod
from typing import Protocol

from algo_studio.core.task import Task
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile
from algo_studio.core.scheduler.exceptions import AnalysisError


class TaskAnalyzerInterface(ABC):
    """
    Task analyzer interface.

    Analyzes tasks and generates task profiles for scheduling decisions.
    """

    @abstractmethod
    def analyze(self, task: Task) -> TaskProfile:
        """
        Analyze task and generate task profile.

        Args:
            task: Raw task object

        Returns:
            TaskProfile: Task profile

        Raises:
            AnalysisError: When analysis fails
        """
        pass

    @abstractmethod
    def get_resource_requirements(self, task: Task) -> dict:
        """
        Extract resource requirements from task.

        Args:
            task: Raw task object

        Returns:
            dict: Resource requirements (num_gpus, num_cpus, memory_gb)
        """
        pass


# For Python 3.8 compatibility, use ABC instead of Protocol
class TaskAnalyzerProtocol(Protocol):
    """Protocol for task analyzers (Python 3.8+ compatible)"""

    def analyze(self, task: Task) -> TaskProfile:
        """Analyze task and generate task profile"""
        ...

    def get_resource_requirements(self, task: Task) -> dict:
        """Extract resource requirements from task"""
        ...
