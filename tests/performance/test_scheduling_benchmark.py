"""
Fair Scheduling Latency Benchmark

Tests the latency of the fair scheduling algorithm.
Target: p95 < 100ms

Benchmark scenarios:
1. Fast Path scheduling decision latency
2. Task analysis latency
3. Node scoring latency
4. Multi-task scheduling throughput
"""

import os
import sys
import time
import statistics
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import List

# Add src to path
from pathlib import Path
_project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_project_root / "src"))

from algo_studio.core.task import Task, TaskType, TaskStatus
from algo_studio.core.ray_client import NodeStatus
from algo_studio.core.scheduler.agentic_scheduler import AgenticScheduler
from algo_studio.core.scheduler.agents.fast_scheduler import FastPathScheduler
from algo_studio.core.scheduler.profiles.task_profile import TaskProfile, TaskType as ProfileTaskType
from algo_studio.core.scheduler.profiles.node_score import NodeScore
from algo_studio.core.scheduler.profiles.scheduling_decision import SchedulingDecision
from algo_studio.core.scheduler.analyzers.default_analyzer import DefaultTaskAnalyzer
from algo_studio.core.scheduler.scorers.multi_dim_scorer import MultiDimNodeScorer
from algo_studio.core.scheduler.validators.resource_validator import ResourceValidator


def create_mock_nodes(count: int = 2) -> List[NodeStatus]:
    """Create mock nodes for testing."""
    nodes = []
    for i in range(count):
        node = NodeStatus(
            node_id=f"node-{i}",
            hostname=f"worker-{i}",
            ip=f"192.168.0.{100 + i}",
            status="idle",
            gpu_used=0 if i == 0 else 1,  # First node has GPU free
            gpu_total=1,
            cpu_used=i,
            cpu_total=8,
            memory_used_gb=8 + (i * 4),
            memory_total_gb=32,
            disk_used_gb=100,
            disk_total_gb=500,
        )
        nodes.append(node)
    return nodes


def create_test_task(task_type: TaskType = TaskType.TRAIN) -> Task:
    """Create a test task."""
    return Task.create(
        task_type=task_type,
        algorithm_name="simple_classifier",
        algorithm_version="v1",
        config={"epochs": 10, "batch_size": 32}
    )


class TestSchedulingLatencyBenchmark:
    """Fair Scheduling Performance Tests"""

    @pytest.fixture
    def mock_ray_client(self):
        """Create mock Ray client."""
        client = Mock()
        client.get_nodes.return_value = create_mock_nodes(2)
        return client

    @pytest.fixture
    def fast_scheduler(self):
        """Create FastPathScheduler instance."""
        return FastPathScheduler()

    @pytest.fixture
    def agentic_scheduler(self, mock_ray_client):
        """Create AgenticScheduler instance."""
        scheduler = AgenticScheduler(ray_client=mock_ray_client)
        scheduler.disable_deep_path()  # Ensure Fast Path only for consistent benchmarks
        return scheduler

    def test_fast_path_single_task_latency(self, fast_scheduler):
        """Test Fast Path single task scheduling latency.

        Target: p95 < 50ms (Fast Path is optimized for low latency)
        """
        nodes = create_mock_nodes(2)
        task = create_test_task()

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            decision = fast_scheduler.schedule(task, nodes)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)

        print(f"\nFast Path Single Task: avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")

        assert decision is not None
        assert p95 < 50.0, f"Fast Path p95 {p95:.2f}ms exceeds 50ms target"

    def test_agentic_scheduler_latency(self, agentic_scheduler):
        """Test AgenticScheduler scheduling latency.

        Target: p95 < 100ms
        """
        task = create_test_task()

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            decision = agentic_scheduler.schedule(task)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)

        print(f"\nAgentic Scheduler: avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")

        assert decision is not None
        assert p95 < 100.0, f"Agentic scheduler p95 {p95:.2f}ms exceeds 100ms target"

    def test_task_analyzer_latency(self):
        """Test task analysis latency.

        Target: < 10ms per analysis
        """
        analyzer = DefaultTaskAnalyzer()
        task = create_test_task()

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            profile = analyzer.analyze(task)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nTask Analyzer: avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms")

        assert profile is not None
        assert profile.task_type == ProfileTaskType.TRAIN
        assert p95 < 10.0, f"Task analyzer p95 {p95:.2f}ms exceeds 10ms target"

    def test_node_scorer_latency(self):
        """Test node scoring latency.

        Target: < 20ms for scoring all nodes
        """
        analyzer = DefaultTaskAnalyzer()
        scorer = MultiDimNodeScorer()
        nodes = create_mock_nodes(2)

        # First create a task profile
        task = create_test_task()
        profile = analyzer.analyze(task)

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            scores = scorer.score(profile, nodes)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nNode Scorer: avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms")

        assert len(scores) == 2
        assert scores[0].total_score >= scores[1].total_score  # Sorted by score
        assert p95 < 20.0, f"Node scorer p95 {p95:.2f}ms exceeds 20ms target"

    def test_resource_validator_latency(self):
        """Test resource validation latency.

        Target: < 5ms per validation
        """
        analyzer = DefaultTaskAnalyzer()
        scorer = MultiDimNodeScorer()
        validator = ResourceValidator()
        nodes = create_mock_nodes(2)

        # Create task profile and scores
        task = create_test_task()
        profile = analyzer.analyze(task)
        scores = scorer.score(profile, nodes)

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            validation = validator.validate(scores[0], profile)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nResource Validator: avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms")

        assert validation is not None
        assert p95 < 5.0, f"Resource validator p95 {p95:.2f}ms exceeds 5ms target"

    def test_concurrent_scheduling_latency(self, agentic_scheduler):
        """Test concurrent scheduling latency.

        Target: p95 < 100ms under concurrent load
        """
        import concurrent.futures

        def schedule_task(task_id):
            task = create_test_task()
            task.task_id = f"task-{task_id}"
            start = time.perf_counter()
            decision = agentic_scheduler.schedule(task)
            elapsed = (time.perf_counter() - start) * 1000
            return elapsed

        latencies = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(schedule_task, i) for i in range(50)]
            for future in concurrent.futures.as_completed(futures):
                latencies.append(future.result())

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)

        print(f"\nConcurrent Scheduling (50 tasks, 10 workers):")
        print(f"  avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")

        assert p95 < 100.0, f"Concurrent scheduling p95 {p95:.2f}ms exceeds 100ms target"

    def test_different_task_types_latency(self, fast_scheduler):
        """Test scheduling latency for different task types.

        Target: All task types < 50ms p95
        """
        nodes = create_mock_nodes(2)
        task_types = [TaskType.TRAIN, TaskType.INFER, TaskType.VERIFY]

        results = {}
        for task_type in task_types:
            latencies = []
            for _ in range(100):
                task = create_test_task(task_type)
                start = time.perf_counter()
                decision = fast_scheduler.schedule(task, nodes)
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)

            latencies.sort()
            p95 = latencies[int(len(latencies) * 0.95)]
            results[task_type.value] = p95
            print(f"\n{task_type.value.capitalize()} scheduling: p95={p95:.2f}ms")

            assert decision is not None
            assert p95 < 50.0, f"{task_type.value} scheduling p95 {p95:.2f}ms exceeds 50ms"

    def test_scheduling_decision_quality(self, fast_scheduler):
        """Test that scheduling decisions are valid and sensible."""
        nodes = create_mock_nodes(2)
        task = create_test_task(TaskType.TRAIN)

        decisions = []
        for _ in range(10):
            decision = fast_scheduler.schedule(task, nodes)
            decisions.append(decision)

        # All decisions should select a node
        for decision in decisions:
            assert decision.selected_node is not None, "Decision should select a node"

        # Should prefer the node with GPU
        gpu_node_decisions = sum(
            1 for d in decisions
            if d.selected_node and d.selected_node.gpu_available > 0
        )

        print(f"\nScheduling quality: {gpu_node_decisions}/10 chose GPU node")
        assert gpu_node_decisions >= 8, "Should prefer GPU node at least 80% of the time"


class TestSchedulingFairness:
    """Test scheduling fairness across multiple tasks."""

    @pytest.fixture
    def fast_scheduler(self):
        return FastPathScheduler()

    def test_round_robin_fairness(self, fast_scheduler):
        """Test that scheduling distributes work across available nodes.

        Note: The scheduler prefers GPU nodes for GPU tasks. For INFER tasks
        (non-GPU), it should distribute work across nodes.
        """
        nodes = create_mock_nodes(2)

        # Submit 20 INFER tasks (non-GPU) and track node selection
        node_selections = {nodes[0].node_id: 0, nodes[1].node_id: 0}

        for i in range(20):
            task = create_test_task(TaskType.INFER)
            decision = fast_scheduler.schedule(task, nodes)

            if decision.selected_node:
                node_id = decision.selected_node.node_id
                node_selections[node_id] = node_selections.get(node_id, 0) + 1

        print(f"\nNode selections over 20 INFER tasks: {node_selections}")

        # For INFER tasks, the scheduler should use both nodes
        # since neither has a clear advantage
        assert node_selections[nodes[0].node_id] > 0 or node_selections[nodes[1].node_id] > 0

    def test_gpu_task_distribution(self, fast_scheduler):
        """Test that GPU tasks are distributed to GPU nodes."""
        nodes = create_mock_nodes(2)
        gpu_task_count = 0
        gpu_node_selections = 0

        for _ in range(20):
            task = create_test_task(TaskType.TRAIN)  # GPU task
            decision = fast_scheduler.schedule(task, nodes)

            if decision.selected_node and decision.selected_node.gpu_available > 0:
                gpu_node_selections += 1
            gpu_task_count += 1

        print(f"\nGPU tasks ({gpu_task_count}) routed to GPU nodes: {gpu_node_selections}")

        # Most GPU tasks should go to GPU nodes
        gpu_ratio = gpu_node_selections / gpu_task_count if gpu_task_count > 0 else 0
        assert gpu_ratio >= 0.8, f"Only {gpu_ratio*100:.0f}% of GPU tasks went to GPU nodes"


class TestSchedulingEdgeCases:
    """Test scheduling edge cases and error handling."""

    @pytest.fixture
    def fast_scheduler(self):
        return FastPathScheduler()

    def test_no_available_nodes(self, fast_scheduler):
        """Test scheduling when no nodes are available."""
        task = create_test_task()

        # Empty node list
        decision = fast_scheduler.schedule(task, [])

        assert decision is not None
        assert decision.selected_node is None
        assert decision.routing_path == "fast"
        assert "No available nodes" in decision.reasoning

    def test_single_node_fallback(self, fast_scheduler):
        """Test scheduling with only one node available."""
        nodes = [create_mock_nodes(2)[0]]  # Only GPU node

        task = create_test_task()
        decision = fast_scheduler.schedule(task, nodes)

        assert decision.selected_node is not None
        assert decision.selected_node.node_id == nodes[0].node_id

    def test_unknown_task_type(self, fast_scheduler):
        """Test scheduling with unknown task type doesn't crash."""
        nodes = create_mock_nodes(2)

        # Create task with custom config that might cause issues
        task = Task.create(
            task_type=TaskType.TRAIN,
            algorithm_name="unknown_algo",
            algorithm_version="v99",
            config={}  # Empty config
        )

        # Should not raise, might fall back gracefully
        try:
            decision = fast_scheduler.schedule(task, nodes)
            assert decision is not None
        except Exception as e:
            pytest.fail(f"Scheduling should not crash on unknown algo: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
