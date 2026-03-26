"""
MemoryLayer interface definition
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from algo_studio.core.scheduler.profiles.task_profile import TaskType
from algo_studio.core.scheduler.profiles.scheduling_decision import SchedulingDecision


@dataclass
class NodeCharacteristics:
    """Node characteristics learned from scheduling history"""

    node_id: str
    hostname: str
    ip: str

    # Reliability metrics
    total_tasks: int = 0
    success_tasks: int = 0
    failure_tasks: int = 0

    # Performance metrics
    avg_gpu_utilization: float = 0.0
    avg_memory_usage: float = 0.0
    avg_task_duration_minutes: float = 0.0

    # Task type success rates
    train_success_rate: float = 0.0
    infer_success_rate: float = 0.0
    verify_success_rate: float = 0.0

    # Health status
    last_heartbeat: Optional[datetime] = None
    consecutive_failures: int = 0
    is_healthy: bool = True

    @property
    def success_rate(self) -> float:
        """Overall success rate"""
        if self.total_tasks == 0:
            return 0.0
        return self.success_tasks / self.total_tasks


@dataclass
class TaskOutcome:
    """Task execution outcome"""

    task_id: str
    success: bool
    duration_minutes: float
    error: Optional[str] = None
    gpu_utilization: Optional[float] = None
    memory_used_gb: Optional[float] = None


class MemoryLayerInterface(ABC):
    """
    Memory layer interface.

    Records scheduling decisions and outcomes for learning.
    """

    @abstractmethod
    def record_decision(
        self,
        decision: SchedulingDecision,
        outcome: TaskOutcome,
    ) -> None:
        """
        Record scheduling decision and outcome.

        Args:
            decision: Scheduling decision
            outcome: Task execution outcome
        """
        pass

    @abstractmethod
    def get_node_characteristics(self, node_id: str) -> Optional[NodeCharacteristics]:
        """
        Get node characteristics.

        Args:
            node_id: Node ID

        Returns:
            NodeCharacteristics if found, None otherwise
        """
        pass

    @abstractmethod
    def get_success_rate(self, task_type: TaskType, node_id: str) -> float:
        """
        Get success rate for task type on node.

        Args:
            task_type: Task type
            node_id: Node ID

        Returns:
            Success rate (0.0 - 1.0)
        """
        pass

    @abstractmethod
    def get_cached_decision(self, task_profile_hash: str) -> Optional[SchedulingDecision]:
        """
        Get cached scheduling decision.

        Args:
            task_profile_hash: Hash of task profile

        Returns:
            Cached decision if found, None otherwise
        """
        pass

    @abstractmethod
    def cache_decision(
        self,
        task_profile_hash: str,
        decision: SchedulingDecision,
    ) -> None:
        """
        Cache scheduling decision.

        Args:
            task_profile_hash: Hash of task profile
            decision: Decision to cache
        """
        pass
