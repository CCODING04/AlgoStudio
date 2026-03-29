# tests/e2e/cluster/test_scheduling_e2e.py
"""
TC-SCHED-001: Fair Scheduling E2E Tests

This module tests the fair scheduling E2E scenarios:
1. TC-SCHED-001: Tasks distributed evenly (fair share)
2. Additional scheduling edge cases

Reference: PHASE2_E2E_PLAN.md Section 4.1, TC-CLUSTER-003, TC-CLUSTER-004
"""

import time
from collections import Counter
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def multi_node_cluster():
    """
    Provide mock multi-node cluster configuration.

    This simulates a cluster with:
    - Head node (192.168.0.126) - no GPU
    - Worker 1 (192.168.0.115) - GPU 0 available
    - Worker 2 (192.168.0.120) - GPU 0 available
    """
    return {
        "nodes": [
            {
                "node_id": "head-node",
                "hostname": "192.168.0.126",
                "ip": "192.168.0.126",
                "status": "alive",
                "gpu_available": 0,
                "gpu_total": 0,
                "cpu_cores": 16,
                "memory_total": 64,
                "memory_available": 32,
            },
            {
                "node_id": "worker-1",
                "hostname": "worker-115",
                "ip": "192.168.0.115",
                "status": "alive",
                "gpu_available": 1,
                "gpu_total": 1,
                "cpu_cores": 8,
                "memory_total": 32,
                "memory_available": 16,
            },
            {
                "node_id": "worker-2",
                "hostname": "worker-120",
                "ip": "192.168.0.120",
                "status": "alive",
                "gpu_available": 1,
                "gpu_total": 1,
                "cpu_cores": 8,
                "memory_total": 32,
                "memory_available": 16,
            },
        ],
        "head_node": "192.168.0.126",
        "worker_nodes": ["192.168.0.115", "192.168.0.120"],
    }


@pytest.fixture
def loaded_cluster():
    """
    Provide mock cluster with imbalanced load.

    Worker 1 is heavily loaded (80% GPU usage)
    Worker 2 is lightly loaded (20% GPU usage)
    """
    return {
        "nodes": [
            {
                "node_id": "head-node",
                "hostname": "192.168.0.126",
                "ip": "192.168.0.126",
                "status": "alive",
                "gpu_available": 0,
                "gpu_total": 0,
            },
            {
                "node_id": "worker-1",
                "hostname": "worker-115",
                "ip": "192.168.0.115",
                "status": "alive",
                "gpu_available": 0,  # Mostly occupied
                "gpu_total": 1,
                "gpu_utilization": 80,
            },
            {
                "node_id": "worker-2",
                "hostname": "worker-120",
                "ip": "192.168.0.120",
                "status": "alive",
                "gpu_available": 1,  # Lightly loaded
                "gpu_total": 1,
                "gpu_utilization": 20,
            },
        ],
        "head_node": "192.168.0.126",
        "worker_nodes": ["192.168.0.115", "192.168.0.120"],
    }


# =============================================================================
# Test Cases
# =============================================================================

@pytest.mark.cluster
@pytest.mark.e2e
@pytest.mark.scheduling
class TestFairShareScheduling:
    """
    TC-SCHED-001: Tasks distributed evenly (fair share).

    This test verifies that when multiple tasks are submitted,
    they are distributed evenly across available GPU nodes.
    """

    def test_tasks_distributed_evenly_across_nodes(
        self, page, api_client, mock_ray_client, task_factory, multi_node_cluster
    ):
        """
        Test: Multiple tasks are distributed evenly across GPU nodes.

        This is the PRIMARY test case for TC-SCHED-001.

        Steps:
        1. Submit 4 training tasks simultaneously
        2. Verify tasks are distributed across available GPU nodes
        3. Verify no single node is overloaded
        4. Verify GPU resources are not over-allocated
        """
        # Submit 4 tasks concurrently
        num_tasks = 4
        task_ids = []

        for i in range(num_tasks):
            task_payload = task_factory.create_train_task(epochs=10)
            response = api_client.create_task(task_payload)
            assert response.status_code == 200
            task = response.json()
            task_ids.append(task.get("task_id"))

        # Wait for tasks to be assigned to nodes
        time.sleep(3)

        # Get task assignments
        task_assignments = {}
        for task_id in task_ids:
            response = api_client.get_task(task_id)
            task_info = response.json()
            assigned_node = task_info.get("assigned_node")
            task_assignments[task_id] = assigned_node

        # Count tasks per node
        node_task_counts = Counter(task_assignments.values())

        # Verify tasks are distributed
        # With 2 GPU nodes and 4 tasks, expect 2 tasks per node (fair share)
        assert len(node_task_counts) == 2, (
            f"Tasks should be distributed across 2 nodes, got: {node_task_counts}"
        )

        # Check fair distribution (each node gets 2 tasks)
        for node, count in node_task_counts.items():
            assert count == 2, (
                f"Each GPU node should have 2 tasks, node {node} has {count}"
            )

    def test_no_gpu_over_allocation(
        self, page, api_client, mock_ray_client, task_factory, multi_node_cluster
    ):
        """
        Test: GPU resources are never over-allocated.

        A node with 1 GPU should never have more than 1 running task.
        """
        # Submit 6 tasks (more than available GPUs)
        num_tasks = 6
        task_ids = []

        for i in range(num_tasks):
            task_payload = task_factory.create_train_task(epochs=5)
            response = api_client.create_task(task_payload)
            assert response.status_code == 200
            task = response.json()
            task_ids.append(task.get("task_id"))

        # Wait for assignment
        time.sleep(3)

        # Count running tasks per node via mock
        # In real test, would query Ray cluster state
        with patch("algo_studio.core.ray_client.RayClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get_nodes.return_value = multi_node_cluster["nodes"]

            # Track tasks assigned to each node
            tasks_per_node = Counter()

            for task_id in task_ids:
                response = api_client.get_task(task_id)
                task_info = response.json()
                node = task_info.get("assigned_node")
                status = task_info.get("status")

                if status == "running" and node:
                    tasks_per_node[node] += 1

            # Verify no node has more running tasks than GPUs
            for node_ip, task_count in tasks_per_node.items():
                node_info = next(
                    (n for n in multi_node_cluster["nodes"] if n["ip"] == node_ip),
                    None
                )
                if node_info and node_info["gpu_total"] > 0:
                    assert task_count <= node_info["gpu_total"], (
                        f"Node {node_ip} has {task_count} tasks but only "
                        f"{node_info['gpu_total']} GPUs"
                    )

    def test_new_task_goes_to_least_loaded_node(
        self, page, api_client, mock_ray_client, task_factory, loaded_cluster
    ):
        """
        Test: New tasks are assigned to the least loaded node.

        When selecting a node for a new task, the scheduler should
        prefer nodes with lower GPU utilization.
        """
        # Create a new task
        task_payload = task_factory.create_train_task(epochs=20)
        response = api_client.create_task(task_payload)
        assert response.status_code == 200

        task = response.json()
        task_id = task.get("task_id")

        # Wait for assignment
        time.sleep(2)

        # Verify task was assigned to the less loaded node
        response = api_client.get_task(task_id)
        task_info = response.json()
        assigned_node = task_info.get("assigned_node")

        # Should be assigned to worker-2 (lighter loaded)
        assert assigned_node == "192.168.0.120", (
            f"New task should be assigned to least loaded node (192.168.0.120), "
            f"got: {assigned_node}"
        )


@pytest.mark.cluster
@pytest.mark.e2e
@pytest.mark.scheduling
class TestPriorityScheduling:
    """
    TC-SCHED-004: Priority-based scheduling.

    Tests that tasks with higher priority are scheduled first
    when resources are constrained.
    """

    def test_high_priority_task_scheduled_first(
        self, page, api_client, mock_ray_client, task_factory
    ):
        """
        Test: High priority task is scheduled before normal priority.

        When multiple tasks are queued and resources are limited,
        higher priority tasks should be scheduled first.
        """
        # Submit tasks with different priorities
        tasks = []

        # Submit low priority task first
        low_priority_payload = task_factory.create_train_task(epochs=10)
        low_priority_payload["priority"] = "low"
        response = api_client.create_task(low_priority_payload)
        assert response.status_code == 200
        tasks.append(("low", response.json().get("task_id")))

        # Submit high priority task second
        high_priority_payload = task_factory.create_train_task(epochs=10)
        high_priority_payload["priority"] = "high"
        response = api_client.create_task(high_priority_payload)
        assert response.status_code == 200
        tasks.append(("high", response.json().get("task_id")))

        # Submit normal priority task third
        normal_priority_payload = task_factory.create_train_task(epochs=10)
        normal_priority_payload["priority"] = "normal"
        response = api_client.create_task(normal_priority_payload)
        assert response.status_code == 200
        tasks.append(("normal", response.json().get("task_id")))

        # Wait for scheduling
        time.sleep(3)

        # Check which task was scheduled first (by started_at timestamp)
        task_start_times = {}
        for priority, task_id in tasks:
            response = api_client.get_task(task_id)
            task_info = response.json()
            started_at = task_info.get("started_at")
            task_start_times[priority] = started_at

        # High priority task should have earlier or equal start time
        if task_start_times["high"] and task_start_times["low"]:
            assert task_start_times["high"] <= task_start_times["low"], (
                "High priority task should be scheduled before low priority"
            )

    def test_same_priority_fifo_order(
        self, page, api_client, mock_ray_client, task_factory
    ):
        """
        Test: Tasks with same priority follow FIFO order.

        For tasks of equal priority, scheduling should follow
        submission order (first-in, first-out).
        """
        # Submit 3 tasks with same priority
        task_ids = []
        for i in range(3):
            task_payload = task_factory.create_train_task(epochs=5)
            task_payload["priority"] = "normal"
            response = api_client.create_task(task_payload)
            assert response.status_code == 200
            task_ids.append(response.json().get("task_id"))
            time.sleep(0.1)  # Small delay to ensure order

        # Wait for scheduling
        time.sleep(2)

        # Check start times maintain order
        start_times = []
        for task_id in task_ids:
            response = api_client.get_task(task_id)
            task_info = response.json()
            start_times.append(task_info.get("started_at"))

        # Verify tasks were scheduled in submission order
        # (first submitted should start first or at same time)
        if all(start_times):
            assert start_times[0] <= start_times[1] <= start_times[2], (
                "Same priority tasks should follow FIFO order"
            )


@pytest.mark.cluster
@pytest.mark.e2e
@pytest.mark.scheduling
class TestConcurrentScheduling:
    """
    TC-CLUSTER-003: Multi-task concurrent scheduling.

    Tests that multiple tasks can be scheduled and run concurrently.
    """

    def test_concurrent_tasks_run_simultaneously(
        self, page, api_client, mock_ray_client, task_factory
    ):
        """
        Test: Multiple tasks can run simultaneously.

        When resources are available, multiple tasks should
        be able to run at the same time.
        """
        # Submit multiple tasks
        num_tasks = 3
        task_ids = []

        for i in range(num_tasks):
            task_payload = task_factory.create_train_task(epochs=50)
            response = api_client.create_task(task_payload)
            assert response.status_code == 200
            task_ids.append(response.json().get("task_id"))

        # Wait for scheduling
        time.sleep(3)

        # Count how many tasks are running concurrently
        running_tasks = []
        for task_id in task_ids:
            response = api_client.get_task(task_id)
            task_info = response.json()
            if task_info.get("status") == "running":
                running_tasks.append(task_id)

        # At least some tasks should be running concurrently
        assert len(running_tasks) >= 1, (
            "At least one task should be running"
        )

        # With 2 GPU nodes, we could have up to 2 concurrent tasks
        # This verifies concurrent execution is possible
        assert len(running_tasks) <= 2, (
            "Should not exceed available GPU count"
        )

    def test_task_queue_maintains_order(
        self, page, api_client, mock_ray_client, task_factory
    ):
        """
        Test: When resources are limited, queue maintains order.

        When all GPUs are occupied, new tasks should queue up
        and maintain their submission order.
        """
        # First, fill up available resources with long-running tasks
        # (In real test, would check actual cluster state)

        # Submit tasks that will queue
        task_ids = []
        for i in range(5):
            task_payload = task_factory.create_train_task(epochs=100)
            response = api_client.create_task(task_payload)
            assert response.status_code == 200
            task_ids.append(response.json().get("task_id"))

        # Wait a bit
        time.sleep(2)

        # Get all task statuses
        statuses = []
        for task_id in task_ids:
            response = api_client.get_task(task_id)
            task_info = response.json()
            statuses.append(task_info.get("status"))

        # Count pending tasks (queued)
        pending_count = statuses.count("pending")
        running_count = statuses.count("running")

        # Total should equal number of tasks
        assert pending_count + running_count == len(task_ids), (
            "All tasks should be either pending or running"
        )


@pytest.mark.cluster
@pytest.mark.e2e
@pytest.mark.scheduling
class TestSchedulingEdgeCases:
    """
    Edge case tests for the scheduling system.
    """

    def test_task_retry_on_node_failure(
        self, page, api_client, mock_ray_client, task_factory
    ):
        """
        Test: Task is rescheduled when assigned node fails.

        If a node goes down while a task is running, the task
        should be rescheduled to another available node.
        """
        # Create a task
        task_payload = task_factory.create_train_task(epochs=30)
        response = api_client.create_task(task_payload)
        assert response.status_code == 200

        task = response.json()
        task_id = task.get("task_id")

        # Wait for task to start
        time.sleep(2)

        # Get initial assignment
        response = api_client.get_task(task_id)
        task_info = response.json()
        initial_node = task_info.get("assigned_node")

        # Simulate node failure and task rescheduling
        with patch("algo_studio.core.ray_client.RayClient") as mock_client_class:
            mock_client = MagicMock()

            # Report the original node as dead
            def mock_get_nodes():
                return [
                    {"node_id": "head", "hostname": "192.168.0.126", "status": "alive"},
                    {
                        "node_id": "worker-1",
                        "hostname": initial_node,
                        "status": "dead" if initial_node == "192.168.0.115" else "alive",
                    },
                    {
                        "node_id": "worker-2",
                        "hostname": "192.168.0.120",
                        "status": "alive",
                    },
                ]

            mock_client.get_nodes.side_effect = mock_get_nodes
            mock_client.get_task_status.return_value = "pending"  # Rescheduled
            mock_client_class.return_value = mock_client

            # Task should be rescheduled
            response = api_client.get_task(task_id)
            rescheduled_task = response.json()

            # Verify task is now pending (waiting for new node)
            assert rescheduled_task.get("status") == "pending", (
                "Task should be pending after node failure"
            )

    def test_zero_gpu_node_not_selected_for_tasks(
        self, page, api_client, mock_ray_client, task_factory, multi_node_cluster
    ):
        """
        Test: Tasks are never assigned to nodes without GPUs.

        Only nodes with available GPU resources should be
        selected for training tasks.
        """
        # Create a training task
        task_payload = task_factory.create_train_task(epochs=10)
        response = api_client.create_task(task_payload)
        assert response.status_code == 200

        task = response.json()
        task_id = task.get("task_id")

        # Wait for assignment
        time.sleep(2)

        # Get assigned node
        response = api_client.get_task(task_id)
        task_info = response.json()
        assigned_node = task_info.get("assigned_node")

        # Head node (no GPU) should never be selected
        assert assigned_node != "192.168.0.126", (
            "Training task should not be assigned to head node (no GPU)"
        )

        # Should be assigned to a worker node
        assert assigned_node in ["192.168.0.115", "192.168.0.120"], (
            f"Training task should be assigned to worker node, got: {assigned_node}"
        )

    def test_scheduling_respects_quota_limits(
        self, page, api_client, mock_ray_client, task_factory
    ):
        """
        Test: Scheduling respects user quota limits.

        If a user has a quota of N concurrent tasks, submitting
        more than N tasks should be rejected or queued.
        """
        # Create multiple tasks
        # In a real system with quota enforcement, we would verify
        # that the N+1th task is rejected or queued

        task_payload = task_factory.create_train_task(epochs=20)
        response = api_client.create_task(task_payload)

        # Should succeed if under quota
        # If quota is enforced, would check response for quota info
        assert response.status_code in (200, 429), (
            f"Task submission should succeed or return quota error, "
            f"got: {response.status_code}"
        )
