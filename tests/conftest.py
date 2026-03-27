# tests/conftest.py
"""
Pytest configuration and shared fixtures for AlgoStudio tests.

This module provides:
- pytest configuration
- Shared fixtures for API, core, and scheduler tests
- Factory fixtures for test data generation
- Mock fixtures for Ray and external dependencies
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from typing import Any, Dict, List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# =============================================================================
# Fixtures: Test Data Factories (using factory-boy pattern)
# =============================================================================

class TaskFactory:
    """Factory for creating Task test data."""

    @staticmethod
    def create(
        task_id: str = None,
        task_type: str = "train",
        algorithm_name: str = "simple_classifier",
        algorithm_version: str = "v1",
        status: str = "pending",
        config: Dict[str, Any] = None,
        progress: int = 0,
    ) -> Dict[str, Any]:
        """Create a task dictionary."""
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


class NodeFactory:
    """Factory for creating Node test data."""

    @staticmethod
    def create(
        node_id: str = None,
        hostname: str = "worker-1",
        ip: str = "192.168.0.115",
        status: str = "idle",
        gpu_available: int = 1,
        gpu_total: int = 1,
        cpu_cores: int = 8,
        memory_total: int = 32,
        memory_available: int = 16,
    ) -> Dict[str, Any]:
        """Create a node dictionary."""
        return {
            "node_id": node_id or f"node-{datetime.now().timestamp()}",
            "hostname": hostname,
            "ip": ip,
            "status": status,
            "gpu_available": gpu_available,
            "gpu_total": gpu_total,
            "cpu_cores": cpu_cores,
            "memory_total": memory_total,
            "memory_available": memory_available,
        }


class AlgorithmMetadataFactory:
    """Factory for creating AlgorithmMetadata test data."""

    @staticmethod
    def create(
        name: str = "simple_classifier",
        version: str = "v1",
        description: str = "A simple classifier",
        supported_task_types: List[str] = None,
        input_schema: Dict[str, Any] = None,
        output_schema: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Create algorithm metadata dictionary."""
        return {
            "name": name,
            "version": version,
            "description": description,
            "supported_task_types": supported_task_types or ["train", "infer", "verify"],
            "input_schema": input_schema or {"type": "object", "properties": {}},
            "output_schema": output_schema or {"type": "object", "properties": {}},
        }


class TrainResultFactory:
    """Factory for creating TrainResult test data."""

    @staticmethod
    def create(
        success: bool = True,
        model_path: str = "/models/test_model.pth",
        metrics: Dict[str, float] = None,
        error: str = None,
    ) -> Dict[str, Any]:
        """Create a training result dictionary."""
        return {
            "success": success,
            "model_path": model_path,
            "metrics": metrics or {"accuracy": 0.95, "loss": 0.05},
            "error": error,
        }


class InferenceResultFactory:
    """Factory for creating InferenceResult test data."""

    @staticmethod
    def create(
        success: bool = True,
        outputs: List[Any] = None,
        latency_ms: float = 10.5,
        error: str = None,
    ) -> Dict[str, Any]:
        """Create an inference result dictionary."""
        return {
            "success": success,
            "outputs": outputs or [[1, 0], [0, 1]],
            "latency_ms": latency_ms,
            "error": error,
        }


# =============================================================================
# Fixtures: Core Components
# =============================================================================

@pytest.fixture
def task_factory():
    """Provide TaskFactory for creating task test data."""
    return TaskFactory


@pytest.fixture
def node_factory():
    """Provide NodeFactory for creating node test data."""
    return NodeFactory


@pytest.fixture
def algorithm_metadata_factory():
    """Provide AlgorithmMetadataFactory."""
    return AlgorithmMetadataFactory


@pytest.fixture
def train_result_factory():
    """Provide TrainResultFactory."""
    return TrainResultFactory


@pytest.fixture
def inference_result_factory():
    """Provide InferenceResultFactory."""
    return InferenceResultFactory


@pytest.fixture
def mock_ray_client():
    """Provide a mocked RayClient."""
    mock_client = MagicMock()
    mock_client.get_nodes.return_value = []
    mock_client.get_node.return_value = None
    mock_client.submit_task.return_value = None
    mock_client.get_task_status.return_value = "pending"
    return mock_client


@pytest.fixture
def mock_task_manager():
    """Provide a mocked TaskManager."""
    from algo_studio.core.task import TaskManager, TaskType, TaskStatus

    mock_manager = MagicMock(spec=TaskManager)
    mock_manager._tasks = {}

    # Create actual TaskManager with mocked dependencies
    real_manager = TaskManager()

    # Override create_task to use our factory
    def create_task(task_type, algorithm_name, algorithm_version, config):
        return real_manager.create_task(task_type, algorithm_name, algorithm_version, config)

    mock_manager.create_task.side_effect = create_task
    mock_manager.get_task.side_effect = lambda tid: real_manager.get_task(tid)
    mock_manager.list_tasks.side_effect = lambda status=None: real_manager.list_tasks(status)
    mock_manager.update_status.side_effect = lambda tid, status, **kw: real_manager.update_status(tid, status, **kw)

    return mock_manager


@pytest.fixture
def sample_task_data():
    """Provide sample task data for tests."""
    return TaskFactory.create(
        task_id="test-task-001",
        task_type="train",
        algorithm_name="simple_classifier",
        algorithm_version="v1",
        status="pending",
        config={"epochs": 100, "batch_size": 32},
    )


@pytest.fixture
def sample_tasks_list():
    """Provide a list of sample tasks for tests."""
    return [
        TaskFactory.create(task_id="test-task-001", status="completed"),
        TaskFactory.create(task_id="test-task-002", status="running"),
        TaskFactory.create(task_id="test-task-003", status="pending"),
    ]


@pytest.fixture
def sample_node_data():
    """Provide sample node data for tests."""
    return NodeFactory.create(
        node_id="node-001",
        hostname="worker-1",
        ip="192.168.0.115",
        status="idle",
        gpu_available=1,
        gpu_total=1,
    )


@pytest.fixture
def sample_nodes_list():
    """Provide a list of sample nodes for tests."""
    return [
        NodeFactory.create(node_id="node-001", hostname="worker-1", ip="192.168.0.115", status="idle", gpu_available=1),
        NodeFactory.create(node_id="node-002", hostname="worker-2", ip="192.168.0.116", status="busy", gpu_available=0),
    ]


# =============================================================================
# Fixtures: API Tests
# =============================================================================

@pytest.fixture
def async_client():
    """Provide an async HTTP client for API testing."""
    from httpx import AsyncClient, ASGITransport
    from algo_studio.api.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# =============================================================================
# Fixtures: Scheduler Tests
# =============================================================================

@pytest.fixture
def mock_scheduler_agent():
    """Provide a mocked scheduler agent."""
    mock_agent = MagicMock()
    mock_agent.schedule.return_value = {
        "decision": "fast_path",
        "selected_node": "worker-1",
        "score": 0.95,
    }
    return mock_agent


@pytest.fixture
def mock_node_scorer():
    """Provide a mocked node scorer."""
    mock_scorer = MagicMock()
    mock_scorer.score.return_value = 0.85
    return mock_scorer


@pytest.fixture
def mock_resource_validator():
    """Provide a mocked resource validator."""
    mock_validator = MagicMock()
    mock_validator.validate.return_value = (True, None)
    return mock_validator


# =============================================================================
# Fixtures: SSH Deployment Tests
# =============================================================================

@pytest.fixture
def mock_ssh_client():
    """Provide a mocked SSH client for deployment tests."""
    mock_client = AsyncMock()
    mock_client.connect.return_value = True
    mock_client.run.return_value = MagicMock(stdout="success", stderr="", exit_code=0)
    mock_client.close.return_value = None
    return mock_client


@pytest.fixture
def mock_ssh_deploy_result():
    """Provide a mock SSH deployment result."""
    return {
        "success": True,
        "node": "192.168.0.115",
        "message": "Deployment successful",
        "artifacts": ["/opt/algo_studio/bin/start.sh"],
    }


# =============================================================================
# Fixtures: Ray Actor Mocks
# =============================================================================

@pytest.fixture
def mock_progress_store():
    """Provide a mocked ProgressStore actor."""
    mock_store = MagicMock()
    mock_store.update.remote.return_value = None
    mock_store.get.remote.return_value = 50
    return mock_store


@pytest.fixture
def mock_progress_reporter():
    """Provide a mocked ProgressReporter actor."""
    mock_reporter = MagicMock()
    mock_reporter.update_progress.remote.return_value = None
    mock_reporter.get_progress.remote.return_value = 50
    return mock_reporter


# =============================================================================
# Fixtures: Configuration
# =============================================================================

@pytest.fixture
def test_config():
    """Provide test configuration."""
    return {
        "ray_head_address": "192.168.0.126:6379",
        "object_store_memory": 5368709120,
        "algorithm_base_path": "/tmp/test_algorithms",
        "redis_host": "localhost",
        "redis_port": 6380,
    }


# =============================================================================
# Fixtures: Cleanup
# =============================================================================

@pytest.fixture(autouse=True)
def reset_task_manager_singletons():
    """Reset task manager singletons between tests."""
    yield
    # Cleanup after test
    import algo_studio.core.task as task_module
    task_module._progress_store_actor = None
