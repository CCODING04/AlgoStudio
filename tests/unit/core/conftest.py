# tests/unit/core/conftest.py
"""
Pytest configuration and shared fixtures for core module tests.

This module provides:
- Mock fixtures for Ray client and actors
- Task and Node factory fixtures
- Test helpers for task.py and ray_client.py testing
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from typing import Any, Dict, List

from algo_studio.core.task import (
    Task, TaskStatus, TaskType, TaskManager,
    ProgressStore, ProgressReporter, RayProgressCallback,
)
from algo_studio.core.ray_client import RayClient, NodeStatus


# =============================================================================
# Fixtures: Task Factories
# =============================================================================

class TaskFactory:
    """Factory for creating Task test data."""

    @staticmethod
    def create(
        task_id: str = None,
        task_type: TaskType = TaskType.TRAIN,
        algorithm_name: str = "simple_classifier",
        algorithm_version: str = "v1",
        status: TaskStatus = TaskStatus.PENDING,
        config: Dict[str, Any] = None,
        progress: int = 0,
        assigned_node: str = None,
        error: str = None,
    ) -> Task:
        """Create a Task instance."""
        return Task(
            task_id=task_id or f"task-{datetime.now().timestamp()}",
            task_type=task_type,
            algorithm_name=algorithm_name,
            algorithm_version=algorithm_version,
            status=status,
            config=config or {"epochs": 100},
            progress=progress,
            assigned_node=assigned_node,
            error=error,
        )

    @staticmethod
    def create_dict(
        task_id: str = None,
        task_type: str = "train",
        algorithm_name: str = "simple_classifier",
        algorithm_version: str = "v1",
        status: str = "pending",
        config: Dict[str, Any] = None,
        progress: int = 0,
    ) -> Dict[str, Any]:
        """Create a task dictionary (for API-style tests)."""
        return {
            "task_id": task_id or f"task-{datetime.now().timestamp()}",
            "task_type": task_type,
            "algorithm_name": algorithm_name,
            "algorithm_version": algorithm_version,
            "status": status,
            "config": config or {"epochs": 100},
            "progress": progress,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "assigned_node": None,
            "error": None,
        }


# =============================================================================
# Fixtures: NodeStatus Factories
# =============================================================================

class NodeStatusFactory:
    """Factory for creating NodeStatus test data."""

    @staticmethod
    def create(
        node_id: str = None,
        ip: str = "192.168.0.115",
        hostname: str = "worker-1",
        status: str = "idle",
        cpu_used: int = 4,
        cpu_total: int = 16,
        gpu_used: int = 0,
        gpu_total: int = 1,
        memory_used_gb: float = 8.0,
        memory_total_gb: float = 32.0,
        disk_used_gb: float = 200.0,
        disk_total_gb: float = 500.0,
        gpu_name: str = "NVIDIA RTX 4090",
        gpu_utilization: int = 0,
    ) -> NodeStatus:
        """Create a NodeStatus instance."""
        return NodeStatus(
            node_id=node_id or f"node-{datetime.now().timestamp()}",
            ip=ip,
            hostname=hostname,
            status=status,
            cpu_used=cpu_used,
            cpu_total=cpu_total,
            gpu_used=gpu_used,
            gpu_total=gpu_total,
            memory_used_gb=memory_used_gb,
            memory_total_gb=memory_total_gb,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
            gpu_name=gpu_name,
            gpu_utilization=gpu_utilization,
        )

    @staticmethod
    def create_idle_node(
        node_id: str = "node-001",
        ip: str = "192.168.0.115",
        hostname: str = "worker-1",
    ) -> NodeStatus:
        """Create an idle node with GPU available."""
        return NodeStatusFactory.create(
            node_id=node_id,
            ip=ip,
            hostname=hostname,
            status="idle",
            gpu_used=0,
            gpu_total=1,
            gpu_utilization=0,
        )

    @staticmethod
    def create_busy_node(
        node_id: str = "node-002",
        ip: str = "192.168.0.116",
        hostname: str = "worker-2",
    ) -> NodeStatus:
        """Create a busy node with GPU in use."""
        return NodeStatusFactory.create(
            node_id=node_id,
            ip=ip,
            hostname=hostname,
            status="busy",
            cpu_used=14,
            cpu_total=16,
            gpu_used=1,
            gpu_total=1,
            gpu_utilization=85,
        )


# =============================================================================
# Fixtures: Ray Client Mocks
# =============================================================================

@pytest.fixture
def mock_ray_client():
    """Provide a mocked RayClient with basic node methods."""
    mock_client = MagicMock(spec=RayClient)
    mock_client.get_nodes.return_value = []
    mock_client.submit_task.return_value = MagicMock()
    mock_client._ray_available = False
    return mock_client


@pytest.fixture
def mock_ray_client_with_nodes(mock_node_status):
    """Provide a mocked RayClient with sample nodes."""
    mock_client = MagicMock(spec=RayClient)
    mock_client.get_nodes.return_value = [mock_node_status]
    mock_client.submit_task.return_value = MagicMock()
    mock_client._ray_available = True
    return mock_client


@pytest.fixture
def mock_ray_client_with_idle_gpu_node():
    """Provide a mocked RayClient with an idle GPU node."""
    mock_client = MagicMock(spec=RayClient)
    idle_node = NodeStatusFactory.create_idle_node()
    mock_client.get_nodes.return_value = [idle_node]
    mock_client.submit_task.return_value = MagicMock()
    mock_client._ray_available = True
    return mock_client


# =============================================================================
# Fixtures: Progress Store Mocks
# =============================================================================

@pytest.fixture
def mock_progress_store():
    """Provide a mocked ProgressStore actor."""
    mock_store = MagicMock(spec=ProgressStore)
    mock_store.update.remote.return_value = None
    mock_store.get.remote.return_value = 50
    return mock_store


@pytest.fixture
def mock_progress_reporter():
    """Provide a mocked ProgressReporter actor."""
    mock_reporter = MagicMock(spec=ProgressReporter)
    mock_reporter.update_progress.remote.return_value = None
    mock_reporter.get_progress.remote.return_value = 50
    return mock_reporter


# =============================================================================
# Fixtures: TaskManager
# =============================================================================

@pytest.fixture
def task_manager():
    """Provide a fresh TaskManager instance."""
    return TaskManager()


@pytest.fixture
def task_manager_with_tasks(task_manager):
    """Provide a TaskManager with sample tasks."""
    task1 = task_manager.create_task(
        task_type=TaskType.TRAIN,
        algorithm_name="simple_classifier",
        algorithm_version="v1",
        config={"epochs": 100},
    )
    task2 = task_manager.create_task(
        task_type=TaskType.INFER,
        algorithm_name="simple_classifier",
        algorithm_version="v1",
        config={"inputs": [1, 2, 3]},
    )
    task3 = task_manager.create_task(
        task_type=TaskType.VERIFY,
        algorithm_name="simple_classifier",
        algorithm_version="v1",
        config={"test_data": "/data/test.jpg"},
    )
    # Mark first task as running
    task_manager.update_status(task1.task_id, TaskStatus.RUNNING)
    return task_manager


# =============================================================================
# Fixtures: NodeStatus
# =============================================================================

@pytest.fixture
def mock_node_status():
    """Provide a sample NodeStatus instance."""
    return NodeStatusFactory.create()


@pytest.fixture
def mock_idle_gpu_node():
    """Provide an idle GPU node."""
    return NodeStatusFactory.create_idle_node()


@pytest.fixture
def mock_busy_gpu_node():
    """Provide a busy GPU node."""
    return NodeStatusFactory.create_busy_node()


@pytest.fixture
def mock_nodes_list():
    """Provide a list of sample nodes."""
    return [
        NodeStatusFactory.create_idle_node(
            node_id="node-001",
            ip="192.168.0.115",
            hostname="worker-1",
        ),
        NodeStatusFactory.create_busy_node(
            node_id="node-002",
            ip="192.168.0.116",
            hostname="worker-2",
        ),
        NodeStatusFactory.create(
            node_id="node-003",
            ip="192.168.0.117",
            hostname="worker-3",
            status="offline",
            cpu_used=0,
            cpu_total=0,
            gpu_used=0,
            gpu_total=0,
        ),
    ]


# =============================================================================
# Fixtures: Ray Progress Callback
# =============================================================================

@pytest.fixture
def ray_progress_callback(mock_progress_reporter):
    """Provide a RayProgressCallback with mocked reporter."""
    return RayProgressCallback("task-001", mock_progress_reporter)


# =============================================================================
# Fixtures: Task Factory Access
# =============================================================================

@pytest.fixture
def task_factory():
    """Provide TaskFactory for creating task test data."""
    return TaskFactory


@pytest.fixture
def node_status_factory():
    """Provide NodeStatusFactory for creating node test data."""
    return NodeStatusFactory
