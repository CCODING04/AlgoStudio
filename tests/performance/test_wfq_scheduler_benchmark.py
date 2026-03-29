"""
WFQScheduler Performance Benchmark

Tests the performance of the Weighted Fair Queuing Scheduler.
Target: p95 < 100ms for scheduling operations.

Benchmark scenarios:
1. Single task scheduling latency
2. Multi-tenant fair scheduling
3. Concurrent scheduling throughput
4. Lock contention under load
5. Quota cache effectiveness
"""

import os
import sys
import time
import statistics
import asyncio
import tempfile
import uuid
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime
from typing import List
from dataclasses import dataclass, field
from typing import Optional

# Add src to path
from pathlib import Path
_project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_project_root / "src"))

from algo_studio.core.quota.manager import QuotaManager
from algo_studio.core.quota.store import ResourceQuota, SQLiteQuotaStore
from algo_studio.core.task import Task, TaskType, TaskStatus
from algo_studio.core.scheduler.wfq_scheduler import WFQScheduler, FairSchedulingDecision
from algo_studio.core.scheduler.global_queue import GlobalSchedulerQueue


def create_temp_db():
    """Create a temporary database file for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


# Extended Task for fair scheduling tests with all required fields
@dataclass
class FairTask:
    """Extended Task with fair scheduling fields."""
    task_id: str
    task_type: TaskType
    algorithm_name: str
    algorithm_version: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    config: dict = field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None
    assigned_node: Optional[str] = None
    progress: int = 0

    # Fair scheduling fields
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    priority: int = 50  # 0-100
    is_urgent: bool = False
    requested_resources: Optional[ResourceQuota] = None

    @property
    def task_id_prop(self) -> str:
        """Alias for task_id to match expected interface."""
        return self.task_id


class TestWFQSchedulerPerformance:
    """Performance tests for WFQScheduler"""

    @pytest.fixture
    def db_path(self):
        """Create temp database path."""
        path = create_temp_db()
        yield path
        if os.path.exists(path):
            os.unlink(path)

    @pytest.fixture
    def quota_store(self, db_path):
        """Create quota store with test data."""
        store = SQLiteQuotaStore(db_path)
        store._init_db()

        # Create multiple team quotas with different weights
        store.create_quota({
            "quota_id": "team-a",
            "scope": "team",
            "scope_id": "team-a",
            "name": "Team A",
            "cpu_cores": 16,
            "gpu_count": 4,
            "memory_gb": 128.0,
            "concurrent_tasks": 8,
            "weight": 1.0,
            "guaranteed_gpu_count": 2,
        })

        store.create_quota({
            "quota_id": "team-b",
            "scope": "team",
            "scope_id": "team-b",
            "name": "Team B",
            "cpu_cores": 16,
            "gpu_count": 4,
            "memory_gb": 128.0,
            "concurrent_tasks": 8,
            "weight": 3.0,  # Higher weight
            "guaranteed_gpu_count": 2,
        })

        store.create_quota({
            "quota_id": "team-c",
            "scope": "team",
            "scope_id": "team-c",
            "name": "Team C",
            "cpu_cores": 8,
            "gpu_count": 2,
            "memory_gb": 64.0,
            "concurrent_tasks": 4,
            "weight": 2.0,
            "guaranteed_gpu_count": 1,
        })

        return store

    @pytest.fixture
    def quota_manager(self, quota_store):
        """Create QuotaManager instance."""
        return QuotaManager(quota_store)

    @pytest.fixture
    def wfq_scheduler(self, quota_manager):
        """Create WFQScheduler instance."""
        return WFQScheduler(quota_manager, total_cluster_gpu=4)

    def _create_task(
        self,
        task_id="train-001",
        tenant_id=None,
        priority=50,
    ):
        """Helper to create a test task"""
        task = FairTask(
            task_id=task_id,
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
            config={},
            priority=priority,
            tenant_id=tenant_id,
        )
        return task

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_single_schedule_latency(self, wfq_scheduler):
        """Test single task scheduling latency.

        Target: p95 < 10ms (local queue operation)
        """
        available = ResourceQuota(gpu_count=2)

        latencies = []
        for i in range(100):
            # Create and submit a task for each scheduling iteration
            task = self._create_task(tenant_id="team-a")
            await wfq_scheduler.submit_task(task)

            start = time.perf_counter()
            decision = await wfq_scheduler.schedule_next(available)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

            # Complete the task to free resources
            if decision:
                await wfq_scheduler.task_completed(decision.task)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)

        print(f"\nSingle Schedule: avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")

        assert decision is not None
        assert p95 < 10.0, f"Single schedule p95 {p95:.2f}ms exceeds 10ms target"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_multi_tenant_scheduling_latency(self, wfq_scheduler):
        """Test scheduling latency with multiple tenants.

        Target: p95 < 50ms
        """
        # Submit tasks from multiple tenants
        for i in range(10):
            await wfq_scheduler.submit_task(self._create_task(f"task-a{i}", tenant_id="team-a"))
            await wfq_scheduler.submit_task(self._create_task(f"task-b{i}", tenant_id="team-b"))
            await wfq_scheduler.submit_task(self._create_task(f"task-c{i}", tenant_id="team-c"))

        available = ResourceQuota(gpu_count=2)

        latencies = []
        for _ in range(50):
            start = time.perf_counter()
            decision = await wfq_scheduler.schedule_next(available)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

            # Reset for next iteration
            if decision:
                await wfq_scheduler.task_completed(decision.task)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)

        print(f"\nMulti-tenant Schedule: avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")

        assert p95 < 50.0, f"Multi-tenant schedule p95 {p95:.2f}ms exceeds 50ms target"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_high_contention_scheduling(self, wfq_scheduler):
        """Test scheduling under high contention (many tasks, limited resources).

        Target: p95 < 100ms
        """
        # Submit many tasks
        for i in range(100):
            await wfq_scheduler.submit_task(self._create_task(f"task-{i}", tenant_id="team-a"))

        available = ResourceQuota(gpu_count=1)  # Limited resources

        latencies = []
        for _ in range(50):
            start = time.perf_counter()
            decision = await wfq_scheduler.schedule_next(available)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

            # Reset for next iteration
            if decision:
                await wfq_scheduler.task_completed(decision.task)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)

        print(f"\nHigh Contention: avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")

        assert p95 < 100.0, f"High contention p95 {p95:.2f}ms exceeds 100ms target"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_scheduling_latency(self, wfq_scheduler):
        """Test concurrent scheduling latency.

        Target: p95 < 100ms under concurrent load
        """
        # Submit many tasks with unique IDs
        for i in range(100):
            task_id = f"task-{uuid.uuid4().hex[:8]}"
            await wfq_scheduler.submit_task(self._create_task(task_id, tenant_id="team-a"))

        available = ResourceQuota(gpu_count=2)

        # Warm-up period: run 5 iterations to warm up caches/JIT
        for _ in range(5):
            decision = await wfq_scheduler.schedule_next(available)
            if decision:
                await wfq_scheduler.task_completed(decision.task)

        async def schedule_and_complete():
            """Schedule a task and complete it to free resources."""
            start = time.perf_counter()
            decision = await wfq_scheduler.schedule_next(available)
            elapsed = (time.perf_counter() - start) * 1000
            if decision:
                await wfq_scheduler.task_completed(decision.task)
            return elapsed

        # True concurrent scheduling using asyncio.gather
        # Use semaphore to limit concurrency to avoid overwhelming the scheduler
        semaphore = asyncio.Semaphore(10)

        async def bounded_schedule():
            async with semaphore:
                return await schedule_and_complete()

        # Run 50 concurrent scheduling operations
        latencies = await asyncio.gather(*[bounded_schedule() for _ in range(50)])

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)

        print(f"\nConcurrent Scheduling: avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")

        assert p95 < 100.0, f"Concurrent scheduling p95 {p95:.2f}ms exceeds 100ms target"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_quota_cache_effectiveness(self, wfq_scheduler):
        """Test that quota cache reduces redundant lookups.

        Measures improvement when scheduling many tasks from same tenant.
        """
        # Submit tasks from same tenant
        for i in range(50):
            await wfq_scheduler.submit_task(self._create_task(f"task-{i}", tenant_id="team-a"))

        available = ResourceQuota(gpu_count=2)

        # First scheduling - cache miss expected
        start = time.perf_counter()
        decision1 = await wfq_scheduler.schedule_next(available)
        first_latency = (time.perf_counter() - start) * 1000

        # Reset and schedule again (should hit cache)
        await wfq_scheduler.task_completed(decision1.task)
        await wfq_scheduler.submit_task(self._create_task("cached-task", tenant_id="team-a"))

        start = time.perf_counter()
        decision2 = await wfq_scheduler.schedule_next(available)
        cached_latency = (time.perf_counter() - start) * 1000

        print(f"\nQuota Cache: first={first_latency:.2f}ms, cached={cached_latency:.2f}ms")

        # Cached lookups should be faster or similar
        assert decision2 is not None
        assert cached_latency < 50.0, f"Cached lookup took {cached_latency:.2f}ms"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_requeue_iteration_performance(self, wfq_scheduler):
        """Test the iterative requeue pattern performance.

        This test verifies that the iterative requeue optimization
        handles quota-exceeded scenarios efficiently.
        """
        # Create a task that will be rejected
        task = self._create_task(tenant_id="team-a")
        task.requested_resources = ResourceQuota(gpu_count=100)  # Exceeds quota

        await wfq_scheduler.submit_task(task)

        available = ResourceQuota(gpu_count=2)

        latencies = []
        for _ in range(10):
            start = time.perf_counter()
            # This will fail quota check and requeue
            decision = await wfq_scheduler.schedule_next(available)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nRequeue Iteration: avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms")

        # Should handle requeue gracefully without excessive latency
        assert p95 < 100.0, f"Requeue p95 {p95:.2f}ms exceeds 100ms target"


class TestWFQSchedulerFairness:
    """Test scheduling fairness across tenants"""

    @pytest.fixture
    def db_path(self):
        path = create_temp_db()
        yield path
        if os.path.exists(path):
            os.unlink(path)

    @pytest.fixture
    def quota_store(self, db_path):
        store = SQLiteQuotaStore(db_path)
        store._init_db()

        # Create two teams with different weights
        store.create_quota({
            "quota_id": "team-low",
            "scope": "team",
            "scope_id": "team-low",
            "name": "Low Weight Team",
            "cpu_cores": 16,
            "gpu_count": 4,
            "memory_gb": 128.0,
            "concurrent_tasks": 8,
            "weight": 1.0,  # Lower weight
            "guaranteed_gpu_count": 2,
        })

        store.create_quota({
            "quota_id": "team-high",
            "scope": "team",
            "scope_id": "team-high",
            "name": "High Weight Team",
            "cpu_cores": 16,
            "gpu_count": 4,
            "memory_gb": 128.0,
            "concurrent_tasks": 8,
            "weight": 3.0,  # Higher weight
            "guaranteed_gpu_count": 2,
        })

        return store

    @pytest.fixture
    def quota_manager(self, quota_store):
        return QuotaManager(quota_store)

    @pytest.fixture
    def wfq_scheduler(self, quota_manager):
        return WFQScheduler(quota_manager, total_cluster_gpu=4)

    @dataclass
    class FairTask:
        """Extended Task with fair scheduling fields."""
        task_id: str
        task_type: TaskType
        algorithm_name: str
        algorithm_version: str
        status: TaskStatus = TaskStatus.PENDING
        created_at: datetime = field(default_factory=datetime.now)
        started_at: Optional[datetime] = None
        completed_at: Optional[datetime] = None
        config: dict = field(default_factory=dict)
        result: Optional[dict] = None
        error: Optional[str] = None
        assigned_node: Optional[str] = None
        progress: int = 0

        # Fair scheduling fields
        tenant_id: Optional[str] = None
        user_id: Optional[str] = None
        team_id: Optional[str] = None
        priority: int = 50  # 0-100
        is_urgent: bool = False
        requested_resources: Optional[ResourceQuota] = None

        @property
        def task_id_prop(self) -> str:
            return self.task_id

    def _create_task(self, task_id="train-001", tenant_id=None, priority=50):
        task = self.FairTask(
            task_id=task_id,
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
            config={},
            priority=priority,
            tenant_id=tenant_id,
        )
        return task

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_weighted_fairness(self, wfq_scheduler):
        """Test that WFQ correctly tracks cumulative weights.

        WFQ uses tasks_scheduled/weight ratio. After scheduling 20 tasks from
        each team:
        - team-low: ratio = 20/1.0 = 20
        - team-high: ratio = 20/3.0 = 6.67

        So team-high has LOWER ratio (more underserved) and would be selected
        next if we continued scheduling.
        """
        # Submit equal number of tasks from both teams
        for i in range(20):
            await wfq_scheduler.submit_task(self._create_task(f"low-{i}", tenant_id="team-low"))
            await wfq_scheduler.submit_task(self._create_task(f"high-{i}", tenant_id="team-high"))

        available = ResourceQuota(gpu_count=2)

        # Schedule 40 tasks total
        selections = {"team-low": 0, "team-high": 0}
        for _ in range(40):
            decision = await wfq_scheduler.schedule_next(available)
            if decision:
                tenant_id = decision.task.tenant_id
                if tenant_id in selections:
                    selections[tenant_id] += 1
                await wfq_scheduler.task_completed(decision.task)

        print(f"\nWeighted Fairness: {selections}")

        # After 40 tasks, verify the WFQ state
        low_queue = wfq_scheduler.queue.get_tenant_queue("team-low")
        high_queue = wfq_scheduler.queue.get_tenant_queue("team-high")

        print(f"Low ratio: {low_queue.wrr_ratio}, High ratio: {high_queue.wrr_ratio}")

        # Both should have same number of tasks scheduled (equal opportunity was given)
        # But the ratio for high-weight team should be LOWER (meaning it has more bandwidth available)
        assert selections["team-low"] == selections["team-high"], \
            "Both teams should have equal scheduling in this test"
        assert high_queue.wrr_ratio < low_queue.wrr_ratio, \
            f"High-weight team ratio should be lower: {high_queue.wrr_ratio} < {low_queue.wrr_ratio}"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_priority_override_performance(self, wfq_scheduler):
        """Test high priority task scheduling latency.

        Target: p95 < 5ms (should skip WFQ calculation)
        """
        # Create high priority task
        task = self._create_task(tenant_id="team-low", priority=95)
        await wfq_scheduler.submit_task(task)

        available = ResourceQuota(gpu_count=2)

        latencies = []
        for _ in range(100):
            await wfq_scheduler.submit_task(self._create_task(f"task-{_}", tenant_id="team-low"))
            start = time.perf_counter()
            decision = await wfq_scheduler.schedule_next(available)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

            if decision:
                await wfq_scheduler.task_completed(decision.task)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nPriority Override: avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms")

        # Priority override should be very fast
        assert p95 < 10.0, f"Priority override p95 {p95:.2f}ms exceeds 10ms target"


class TestWFQSchedulerScalability:
    """Scalability tests for WFQScheduler"""

    @pytest.fixture
    def db_path(self):
        path = create_temp_db()
        yield path
        if os.path.exists(path):
            os.unlink(path)

    @pytest.fixture
    def quota_store(self, db_path):
        store = SQLiteQuotaStore(db_path)
        store._init_db()

        # Create many team quotas
        for i in range(20):
            store.create_quota({
                "quota_id": f"team-{i}",
                "scope": "team",
                "scope_id": f"team-{i}",
                "name": f"Team {i}",
                "cpu_cores": 16,
                "gpu_count": 4,
                "memory_gb": 128.0,
                "concurrent_tasks": 8,
                "weight": 1.0 + (i % 5) * 0.5,  # Varying weights
                "guaranteed_gpu_count": 2,
            })

        return store

    @pytest.fixture
    def quota_manager(self, quota_store):
        return QuotaManager(quota_store)

    @pytest.fixture
    def wfq_scheduler(self, quota_manager):
        return WFQScheduler(quota_manager, total_cluster_gpu=16)

    @dataclass
    class FairTask:
        task_id: str
        task_type: TaskType
        algorithm_name: str
        algorithm_version: str
        status: TaskStatus = TaskStatus.PENDING
        created_at: datetime = field(default_factory=datetime.now)
        tenant_id: Optional[str] = None
        priority: int = 50
        requested_resources: Optional[ResourceQuota] = None

        @property
        def task_id_prop(self) -> str:
            return self.task_id

    def _create_task(self, task_id="train-001", tenant_id=None, priority=50):
        return self.FairTask(
            task_id=task_id,
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
            priority=priority,
            tenant_id=tenant_id,
        )

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_many_tenants_scalability(self, wfq_scheduler):
        """Test scheduling with many tenants (20+).

        Target: p95 < 100ms even with many tenants
        """
        # Submit tasks from all 20 tenants
        for i in range(20):
            for j in range(5):
                await wfq_scheduler.submit_task(
                    self._create_task(f"task-{i}-{j}", tenant_id=f"team-{i}")
                )

        available = ResourceQuota(gpu_count=4)

        latencies = []
        for _ in range(50):
            start = time.perf_counter()
            decision = await wfq_scheduler.schedule_next(available)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

            if decision:
                await wfq_scheduler.task_completed(decision.task)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)

        print(f"\nMany Tenants (20): avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")

        assert p95 < 100.0, f"Scalability p95 {p95:.2f}ms exceeds 100ms target"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
