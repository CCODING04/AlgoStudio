"""
TenantQueue - Per-tenant queue with WFQ state tracking.

Part of the fair scheduling algorithm implementation.
"""

import asyncio
import heapq
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from algo_studio.core.task import Task


@dataclass
class UsageSnapshot:
    """Snapshot of resource usage at a point in time."""
    timestamp: datetime
    gpu_count: int = 0
    cpu_cores: int = 0
    gpu_memory_gb: float = 0.0
    memory_gb: float = 0.0


@dataclass(order=False)
class _TaskEntry:
    """Internal heap entry for priority queue - uses negative priority for max-heap behavior."""
    priority: float
    task: Task
    enqueue_time: float

    def __lt__(self, other: "_TaskEntry") -> bool:
        # Max-heap via negative priority; tie-break by enqueue_time (FIFO)
        if self.priority != other.priority:
            return self.priority > other.priority  # Higher priority first
        return self.enqueue_time < other.enqueue_time


@dataclass
class TenantQueue:
    """
    Per-tenant queue with WFQ (Weighted Fair Queuing) state tracking.

    Uses a heap-based priority queue for O(log n) enqueue/dequeue operations
    instead of sorting on every dequeue.

    Attributes:
        tenant_id: Unique tenant identifier
        quota_id: Associated quota ID in QuotaManager
        weight: Tenant weight for WFQ (higher = more bandwidth)
        guaranteed_minimum: Guaranteed minimum resources for this tenant
        pending_tasks: Queue of pending tasks for this tenant
        cumulative_weight: Sum of weights of scheduled tasks (WFQ state)
        tasks_scheduled: Number of tasks successfully scheduled
        current_usage: Current resource usage for this tenant
        usage_history: Historical usage snapshots
    """

    tenant_id: str
    quota_id: str = ""
    weight: float = 1.0
    guaranteed_minimum: Optional[Dict[str, Any]] = None

    # Priority queue using heap - stores (priority, task, enqueue_time) tuples
    _heap: List[_TaskEntry] = field(default_factory=list)
    # Set to track tasks for O(1) membership check (prevents duplicates)
    _task_set: set = field(default_factory=set)

    # WFQ state
    cumulative_weight: float = 0.0
    tasks_scheduled: int = 0
    # Cached WFQ ratio: tasks_scheduled / weight (recalculated only when needed)
    _cached_wrr_ratio: float = 0.0
    _ratio_dirty: bool = False

    # Usage tracking
    current_usage: Dict[str, Any] = field(default_factory=lambda: {
        "gpu_count": 0,
        "cpu_cores": 0,
        "gpu_memory_gb": 0.0,
        "memory_gb": 0.0,
    })
    usage_history: List[UsageSnapshot] = field(default_factory=list)

    # Lock for thread-safe operations
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def enqueue(self, task: Task) -> None:
        """Add task to tenant queue.

        Args:
            task: Task to add to the queue
        """
        priority = getattr(task, 'priority', 50)
        enqueue_time = datetime.now().timestamp()
        entry = _TaskEntry(priority=priority, task=task, enqueue_time=enqueue_time)

        heapq.heappush(self._heap, entry)
        self._task_set.add(task.task_id)

    def dequeue(self) -> Optional[Task]:
        """Remove and return the next task based on internal ordering.

        Within a tenant queue, tasks are ordered by priority (highest first),
        with FIFO tie-breaking.

        Returns:
            The next task, or None if queue is empty
        """
        if not self._heap:
            return None

        entry = heapq.heappop(self._heap)
        self._task_set.discard(entry.task.task_id)
        return entry.task

    def peek(self) -> Optional[Task]:
        """View the next task without removing it.

        Returns:
            The next task, or None if queue is empty
        """
        if not self._heap:
            return None
        # Heap[0] is the highest priority entry due to our __lt__ implementation
        return self._heap[0].task

    def get_wait_time(self, task: Task) -> float:
        """Calculate how long task has been waiting in hours.

        Args:
            task: Task to check

        Returns:
            Wait time in hours, 0.0 if task has no created_at
        """
        if task.created_at:
            return (datetime.now() - task.created_at).total_seconds() / 3600
        return 0.0

    def update_wfq_state(self, task_weight: float) -> None:
        """Update WFQ cumulative state after scheduling a task.

        Args:
            task_weight: Weight of the task that was scheduled
        """
        self.cumulative_weight += task_weight
        self.tasks_scheduled += 1
        # Invalidate cached ratio since tasks_scheduled changed
        self._ratio_dirty = True

    def update_usage(self, resources: Dict[str, Any]) -> None:
        """Update current resource usage.

        Args:
            resources: Resource dict with gpu_count, cpu_cores, etc.
        """
        for key, value in resources.items():
            if key in self.current_usage:
                self.current_usage[key] += value

        # Record snapshot
        self.usage_history.append(UsageSnapshot(
            timestamp=datetime.now(),
            gpu_count=self.current_usage.get("gpu_count", 0),
            cpu_cores=self.current_usage.get("cpu_cores", 0),
            gpu_memory_gb=self.current_usage.get("gpu_memory_gb", 0.0),
            memory_gb=self.current_usage.get("memory_gb", 0.0),
        ))

        # Keep only last 100 snapshots
        if len(self.usage_history) > 100:
            self.usage_history = self.usage_history[-100:]

    def release_usage(self, resources: Dict[str, Any]) -> None:
        """Release resources from current usage.

        Args:
            resources: Resource dict to subtract
        """
        for key, value in resources.items():
            if key in self.current_usage:
                self.current_usage[key] = max(0, self.current_usage[key] - value)

    @property
    def queue_length(self) -> int:
        """Get the number of pending tasks."""
        return len(self._heap)

    @property
    def pending_tasks(self) -> List[Task]:
        """Get list of pending tasks (for backward compatibility)."""
        return [entry.task for entry in sorted(self._heap, key=lambda e: e.priority, reverse=True)]

    @property
    def wrr_ratio(self) -> float:
        """Get WFQ ratio (tasks_scheduled / weight), cached for performance."""
        if self._ratio_dirty:
            self._cached_wrr_ratio = self.tasks_scheduled / max(self.weight, 0.1)
            self._ratio_dirty = False
        return self._cached_wrr_ratio

    def invalidate_ratio_cache(self) -> None:
        """Mark ratio cache as dirty so it recalculates on next access."""
        self._ratio_dirty = True

    @property
    def average_wait_time_hours(self) -> float:
        """Calculate average wait time for tasks in queue based on task.created_at."""
        if not self._heap:
            return 0.0

        total_wait = sum(self.get_wait_time(entry.task) for entry in self._heap)
        return total_wait / len(self._heap)

    def get_task_weights(self) -> List[float]:
        """Get list of task weights (for WFQ calculation).

        Returns task weights based on priority and resource requirements.
        """
        return [0.5 + (entry.priority / 100) for entry in self._heap]

    def __len__(self) -> int:
        """Return queue length."""
        return len(self._heap)

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._heap) == 0

    def contains(self, task_id: str) -> bool:
        """Check if a task is in this queue (O(1) instead of O(n))."""
        return task_id in self._task_set
