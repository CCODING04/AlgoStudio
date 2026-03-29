"""
Unit tests for TenantQueue.

Covers:
- Heap ordering (priority + FIFO tiebreak)
- WFQ ratio caching (_ratio_dirty flag)
- Usage snapshot recording
- Enqueue/dequeue operations
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from algo_studio.core.scheduler.tenant_queue import (
    TenantQueue,
    UsageSnapshot,
    _TaskEntry,
)
from algo_studio.core.task import Task, TaskType, TaskStatus


def make_task(task_id: str, priority: int = 50, created_at: datetime = None) -> Task:
    """Helper to create a Task with optional priority attribute."""
    task = Task(
        task_id=task_id,
        task_type=TaskType.TRAIN,
        algorithm_name="test_algo",
        algorithm_version="v1",
        created_at=created_at or datetime.now(),
    )
    # Manually set priority if needed (Tasks don't have priority by default)
    if priority != 50:
        task.priority = priority
    return task


class TestTaskEntryOrdering:
    """Tests for _TaskEntry.__lt__ heap ordering."""

    def test_higher_priority_dequeued_first(self):
        """Higher priority tasks should come out before lower priority."""
        now = time.time()
        low = _TaskEntry(priority=10, task=make_task("low"), enqueue_time=now)
        mid = _TaskEntry(priority=50, task=make_task("mid"), enqueue_time=now)
        high = _TaskEntry(priority=100, task=make_task("high"), enqueue_time=now)

        entries = [low, mid, high]
        sorted_entries = sorted(entries)
        # Due to max-heap via __lt__, higher priority should be first
        assert sorted_entries[0] is high
        assert sorted_entries[1] is mid
        assert sorted_entries[2] is low

    def test_fifo_tiebreak_same_priority(self):
        """Tasks with same priority respect FIFO ordering via enqueue_time."""
        now = time.time()
        first = _TaskEntry(priority=50, task=make_task("first"), enqueue_time=now)
        second = _TaskEntry(priority=50, task=make_task("second"), enqueue_time=now + 0.001)
        third = _TaskEntry(priority=50, task=make_task("third"), enqueue_time=now + 0.002)

        entries = [third, first, second]
        sorted_entries = sorted(entries)
        # FIFO means earlier enqueue_time first
        assert sorted_entries[0] is first
        assert sorted_entries[1] is second
        assert sorted_entries[2] is third

    def test_priority_outranks_fifo(self):
        """Lower priority task enqueued earlier should still come after higher priority."""
        now = time.time()
        low_early = _TaskEntry(priority=10, task=make_task("low_early"), enqueue_time=now)
        high_late = _TaskEntry(priority=100, task=make_task("high_late"), enqueue_time=now + 10)

        entries = [low_early, high_late]
        sorted_entries = sorted(entries)
        # High priority should win even if enqueued later
        assert sorted_entries[0] is high_late
        assert sorted_entries[1] is low_early


class TestTenantQueueEnqueueDequeue:
    """Tests for enqueue/dequeue operations."""

    def test_enqueue_increases_length(self):
        """Enqueueing a task increases queue length."""
        q = TenantQueue(tenant_id="test-tenant")
        assert q.queue_length == 0
        q.enqueue(make_task("task-1"))
        assert q.queue_length == 1
        q.enqueue(make_task("task-2"))
        assert q.queue_length == 2

    def test_dequeue_returns_highest_priority(self):
        """Dequeue returns task with highest priority."""
        q = TenantQueue(tenant_id="test-tenant")
        q.enqueue(make_task("low", priority=10))
        q.enqueue(make_task("high", priority=100))
        q.enqueue(make_task("mid", priority=50))

        first = q.dequeue()
        assert first.task_id == "high"

    def test_dequeue_respects_fifo_tiebreak(self):
        """Same priority tasks are dequeued in FIFO order."""
        q = TenantQueue(tenant_id="test-tenant")
        q.enqueue(make_task("first", priority=50))
        time.sleep(0.01)
        q.enqueue(make_task("second", priority=50))

        first = q.dequeue()
        second = q.dequeue()
        assert first.task_id == "first"
        assert second.task_id == "second"

    def test_dequeue_empty_returns_none(self):
        """Dequeue from empty queue returns None."""
        q = TenantQueue(tenant_id="test-tenant")
        assert q.dequeue() is None

    def test_dequeue_decreases_length(self):
        """Dequeuing reduces queue length."""
        q = TenantQueue(tenant_id="test-tenant")
        q.enqueue(make_task("task-1"))
        q.enqueue(make_task("task-2"))
        assert q.queue_length == 2
        q.dequeue()
        assert q.queue_length == 1
        q.dequeue()
        assert q.queue_length == 0

    def test_peek_returns_without_removing(self):
        """Peek returns next task without removing it."""
        q = TenantQueue(tenant_id="test-tenant")
        q.enqueue(make_task("task-1"))
        q.enqueue(make_task("task-2", priority=100))

        peeked = q.peek()
        assert peeked.task_id == "task-2"
        assert q.queue_length == 2  # Still 2

    def test_peek_empty_returns_none(self):
        """Peek on empty queue returns None."""
        q = TenantQueue(tenant_id="test-tenant")
        assert q.peek() is None

    def test_contains_returns_true_for_enqueued_task(self):
        """contains() returns True for enqueued task."""
        q = TenantQueue(tenant_id="test-tenant")
        task = make_task("task-1")
        q.enqueue(task)
        assert q.contains("task-1") is True

    def test_contains_returns_false_for_nonexistent(self):
        """contains() returns False for non-enqueued task."""
        q = TenantQueue(tenant_id="test-tenant")
        assert q.contains("nonexistent") is False

    def test_contains_after_dequeue(self):
        """Task no longer in contains() after dequeue."""
        q = TenantQueue(tenant_id="test-tenant")
        task = make_task("task-1")
        q.enqueue(task)
        assert q.contains("task-1") is True
        q.dequeue()
        assert q.contains("task-1") is False

    def test_is_empty_initially(self):
        """is_empty() returns True for new queue."""
        q = TenantQueue(tenant_id="test-tenant")
        assert q.is_empty() is True

    def test_is_empty_false_after_enqueue(self):
        """is_empty() returns False after enqueue."""
        q = TenantQueue(tenant_id="test-tenant")
        q.enqueue(make_task("task-1"))
        assert q.is_empty() is False

    def test_is_empty_true_after_dequeue_all(self):
        """is_empty() returns True after all tasks dequeued."""
        q = TenantQueue(tenant_id="test-tenant")
        q.enqueue(make_task("task-1"))
        q.dequeue()
        assert q.is_empty() is True


class TestWfqRatioCaching:
    """Tests for WFQ ratio caching and _ratio_dirty flag."""

    def test_wrr_ratio_initially_zero(self):
        """WRR ratio starts at 0 for new tenant."""
        q = TenantQueue(tenant_id="test-tenant", weight=1.0)
        assert q.wrr_ratio == 0.0

    def test_wrr_ratio_updates_after_wfq_state(self):
        """WRR ratio reflects tasks_scheduled / weight after update."""
        q = TenantQueue(tenant_id="test-tenant", weight=2.0)
        q.update_wfq_state(task_weight=1.0)
        q.update_wfq_state(task_weight=1.0)
        # 2 tasks scheduled / weight 2 = 1.0
        assert q.wrr_ratio == 1.0

    def test_ratio_dirty_flag_set_on_update(self):
        """_ratio_dirty is set True after update_wfq_state."""
        q = TenantQueue(tenant_id="test-tenant", weight=1.0)
        assert q._ratio_dirty is False
        q.update_wfq_state(task_weight=1.0)
        assert q._ratio_dirty is True

    def test_ratio_dirty_false_after_wrr_access(self):
        """_ratio_dirty set to False after wrr_ratio is accessed."""
        q = TenantQueue(tenant_id="test-tenant", weight=1.0)
        q.update_wfq_state(task_weight=1.0)
        # Access ratio to trigger recalculation
        _ = q.wrr_ratio
        assert q._ratio_dirty is False

    def test_cached_ratio_reused_without_recalc(self):
        """Cached ratio is reused when not dirty."""
        q = TenantQueue(tenant_id="test-tenant", weight=1.0)
        q.update_wfq_state(task_weight=1.0)
        first_access = q.wrr_ratio
        second_access = q.wrr_ratio
        assert first_access == second_access

    def test_invalidate_ratio_cache_sets_dirty(self):
        """invalidate_ratio_cache() sets _ratio_dirty True."""
        q = TenantQueue(tenant_id="test-tenant", weight=1.0)
        q.update_wfq_state(task_weight=1.0)
        _ = q.wrr_ratio  # Clear dirty
        assert q._ratio_dirty is False
        q.invalidate_ratio_cache()
        assert q._ratio_dirty is True

    def test_wrr_ratio_with_low_weight_uses_minimum(self):
        """WRR ratio uses max(weight, 0.1) to avoid division issues."""
        q = TenantQueue(tenant_id="test-tenant", weight=0.0)
        q.update_wfq_state(task_weight=1.0)
        # Uses max(0.0, 0.1) = 0.1 as denominator
        assert q.wrr_ratio == 10.0


class TestUsageSnapshotRecording:
    """Tests for usage snapshot recording."""

    def test_update_usage_changes_current_usage(self):
        """update_usage() modifies current_usage dict."""
        q = TenantQueue(tenant_id="test-tenant")
        assert q.current_usage["gpu_count"] == 0
        q.update_usage({"gpu_count": 2, "cpu_cores": 4})
        assert q.current_usage["gpu_count"] == 2
        assert q.current_usage["cpu_cores"] == 4

    def test_update_usage_appends_snapshot(self):
        """update_usage() appends a UsageSnapshot to usage_history."""
        q = TenantQueue(tenant_id="test-tenant")
        before_count = len(q.usage_history)
        q.update_usage({"gpu_count": 1})
        assert len(q.usage_history) == before_count + 1
        assert isinstance(q.usage_history[-1], UsageSnapshot)

    def test_update_usage_snapshot_records_correct_values(self):
        """Snapshot captures current_usage values at time of update."""
        q = TenantQueue(tenant_id="test-tenant")
        q.update_usage({"gpu_count": 3, "cpu_cores": 6, "gpu_memory_gb": 10.0, "memory_gb": 20.0})
        snapshot = q.usage_history[-1]
        assert snapshot.gpu_count == 3
        assert snapshot.cpu_cores == 6
        assert snapshot.gpu_memory_gb == 10.0
        assert snapshot.memory_gb == 20.0

    def test_update_usage_accumulates(self):
        """Multiple update_usage() calls accumulate values."""
        q = TenantQueue(tenant_id="test-tenant")
        q.update_usage({"gpu_count": 1})
        q.update_usage({"gpu_count": 2})
        assert q.current_usage["gpu_count"] == 3

    def test_update_usage_snapshot_timestamps(self):
        """Snapshot timestamp is set to datetime.now()."""
        q = TenantQueue(tenant_id="test-tenant")
        before = datetime.now()
        q.update_usage({"gpu_count": 1})
        after = datetime.now()
        snapshot = q.usage_history[-1]
        assert before <= snapshot.timestamp <= after

    def test_release_usage_reduces_current_usage(self):
        """release_usage() subtracts from current_usage."""
        q = TenantQueue(tenant_id="test-tenant")
        q.update_usage({"gpu_count": 5, "cpu_cores": 10})
        q.release_usage({"gpu_count": 2, "cpu_cores": 3})
        assert q.current_usage["gpu_count"] == 3
        assert q.current_usage["cpu_cores"] == 7

    def test_release_usage_does_not_go_negative(self):
        """release_usage() values cannot go below zero."""
        q = TenantQueue(tenant_id="test-tenant")
        q.update_usage({"gpu_count": 2})
        q.release_usage({"gpu_count": 5})
        assert q.current_usage["gpu_count"] == 0

    def test_usage_history_max_100_snapshots(self):
        """usage_history keeps only the last 100 snapshots."""
        q = TenantQueue(tenant_id="test-tenant")
        # Add 150 snapshots
        for i in range(150):
            q.update_usage({"gpu_count": 1})  # Each adds 1, accumulating in current_usage
        # Should be capped at 100
        assert len(q.usage_history) == 100
        # First snapshot should be from the 51st iteration (index 50), with gpu_count=51
        # (since we keep history[-100:] which starts at iteration 50)
        assert q.usage_history[0].gpu_count == 51
        # Last snapshot should be from the 150th iteration (index 149), with gpu_count=150
        assert q.usage_history[-1].gpu_count == 150


class TestTenantQueueMisc:
    """Miscellaneous TenantQueue tests."""

    def test_len_returns_queue_length(self):
        """__len__ returns same as queue_length."""
        q = TenantQueue(tenant_id="test-tenant")
        q.enqueue(make_task("t1"))
        q.enqueue(make_task("t2"))
        assert len(q) == 2

    def test_pending_tasks_returns_sorted_list(self):
        """pending_tasks property returns tasks sorted by priority descending."""
        q = TenantQueue(tenant_id="test-tenant")
        q.enqueue(make_task("low", priority=10))
        q.enqueue(make_task("high", priority=100))
        q.enqueue(make_task("mid", priority=50))
        pending = q.pending_tasks
        assert pending[0].task_id == "high"
        assert pending[1].task_id == "mid"
        assert pending[2].task_id == "low"

    def test_get_task_weights_returns_weights(self):
        """get_task_weights returns list of calculated weights."""
        q = TenantQueue(tenant_id="test-tenant")
        q.enqueue(make_task("t1", priority=100))
        q.enqueue(make_task("t2", priority=50))
        weights = q.get_task_weights()
        # weight = 0.5 + (priority / 100)
        assert 1.5 in weights  # 0.5 + 100/100
        assert 1.0 in weights  # 0.5 + 50/100

    def test_average_wait_time_hours_empty_queue(self):
        """average_wait_time_hours returns 0.0 for empty queue."""
        q = TenantQueue(tenant_id="test-tenant")
        assert q.average_wait_time_hours == 0.0

    def test_average_wait_time_hours_calculates_correctly(self):
        """average_wait_time_hours calculates average wait time."""
        q = TenantQueue(tenant_id="test-tenant")
        old_time = datetime.now() - timedelta(hours=2)
        q.enqueue(make_task("t1", created_at=old_time))
        new_time = datetime.now() - timedelta(hours=1)
        q.enqueue(make_task("t2", created_at=new_time))
        avg = q.average_wait_time_hours
        # Should be between 1 and 2 hours (avg of 1hr and 2hr wait)
        assert 1.0 <= avg <= 2.0

    def test_update_wfq_state_increments_counters(self):
        """update_wfq_state increments cumulative_weight and tasks_scheduled."""
        q = TenantQueue(tenant_id="test-tenant")
        assert q.cumulative_weight == 0.0
        assert q.tasks_scheduled == 0
        q.update_wfq_state(task_weight=2.5)
        assert q.cumulative_weight == 2.5
        assert q.tasks_scheduled == 1
        q.update_wfq_state(task_weight=1.5)
        assert q.cumulative_weight == 4.0
        assert q.tasks_scheduled == 2

    def test_get_wait_time_returns_zero_if_no_created_at(self, monkeypatch):
        """get_wait_time returns 0.0 for task with no created_at."""
        q = TenantQueue(tenant_id="test-tenant")
        task = make_task("t1")
        task.created_at = None
        assert q.get_wait_time(task) == 0.0


class TestUsageSnapshot:
    """Tests for UsageSnapshot dataclass."""

    def test_usage_snapshot_defaults(self):
        """UsageSnapshot has expected default values."""
        snap = UsageSnapshot(timestamp=datetime.now())
        assert snap.gpu_count == 0
        assert snap.cpu_cores == 0
        assert snap.gpu_memory_gb == 0.0
        assert snap.memory_gb == 0.0

    def test_usage_snapshot_explicit_values(self):
        """UsageSnapshot accepts explicit resource values."""
        snap = UsageSnapshot(
            timestamp=datetime.now(),
            gpu_count=4,
            cpu_cores=16,
            gpu_memory_gb=20.0,
            memory_gb=64.0,
        )
        assert snap.gpu_count == 4
        assert snap.cpu_cores == 16
        assert snap.gpu_memory_gb == 20.0
        assert snap.memory_gb == 64.0
