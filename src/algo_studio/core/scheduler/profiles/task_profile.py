"""
TaskProfile - Task characteristics profile for scheduling decisions
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class TaskType(Enum):
    """Task type enumeration - mirrors TaskType in task.py"""
    TRAIN = "train"
    INFER = "infer"
    VERIFY = "verify"


@dataclass
class TaskProfile:
    """
    Task characteristics profile for the scheduler.

    This is the input format for the AI scheduling module.
    """

    task_id: str
    task_type: TaskType

    # Resource requirements
    num_gpus: int = 0
    num_cpus: int = 1
    memory_gb: float = 0.0

    # Priority (1-10, 10 highest)
    priority: int = 5

    # Affinity preferences
    preferred_nodes: List[str] = field(default_factory=list)  # hostname list
    data_locality: Optional[str] = None  # Data location node hostname

    # Task characteristics
    estimated_duration_minutes: int = 30
    is_retry: bool = False
    retry_count: int = 0

    # Timeout settings
    timeout_minutes: int = 120

    @property
    def requires_gpu(self) -> bool:
        """Check if task requires GPU"""
        return self.num_gpus > 0

    @property
    def complexity(self) -> int:
        """
        Calculate task complexity score (1-10).

        Higher complexity tasks may benefit from Deep Path.
        """
        score = 1

        # GPU requirement adds complexity
        if self.num_gpus > 0:
            score += 2

        # High memory requirement
        if self.memory_gb > 16:
            score += 1

        # Specific node affinity
        if self.preferred_nodes:
            score += 2

        # Data locality requirement
        if self.data_locality:
            score += 1

        # High priority
        if self.priority >= 8:
            score += 1

        # Long running task
        if self.estimated_duration_minutes > 60:
            score += 1

        # Retry task
        if self.is_retry:
            score += 1

        return min(score, 10)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "num_gpus": self.num_gpus,
            "num_cpus": self.num_cpus,
            "memory_gb": self.memory_gb,
            "priority": self.priority,
            "preferred_nodes": self.preferred_nodes,
            "data_locality": self.data_locality,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "is_retry": self.is_retry,
            "retry_count": self.retry_count,
            "timeout_minutes": self.timeout_minutes,
            "complexity": self.complexity,
        }
