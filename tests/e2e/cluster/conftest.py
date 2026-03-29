# tests/e2e/cluster/conftest.py
"""
Pytest configuration and fixtures for AlgoStudio E2E Cluster tests.

This module provides fixtures for cluster testing without requiring
web/browser infrastructure.
"""

import os
from typing import Optional
from unittest.mock import MagicMock

import pytest


# =============================================================================
# Mock API Client for Cluster Tests
# =============================================================================

class MockAPIClient:
    """Mock API client for cluster E2E tests without web dependencies."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.headers = {
            "X-User-ID": "test-user",
            "X-User-Role": "admin",
        }
        self._tasks = {}
        self._nodes = {}

    def get_tasks(self, status: Optional[str] = None):
        """Get tasks, optionally filtered by status."""
        mock_response = MagicMock()
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        mock_response.json.return_value = tasks
        mock_response.status_code = 200
        return mock_response

    def get_task(self, task_id: str):
        """Get a specific task by ID."""
        mock_response = MagicMock()
        task = self._tasks.get(task_id, {})
        mock_response.json.return_value = task
        mock_response.status_code = 200 if task else 404
        return mock_response

    def create_task(self, task_data: dict):
        """Create a new task."""
        import uuid
        mock_response = MagicMock()
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = {
            "task_id": task_id,
            "task_type": task_data.get("task_type", "train"),
            "algorithm_name": task_data.get("algorithm_name", "simple_classifier"),
            "algorithm_version": task_data.get("algorithm_version", "v1"),
            "status": "pending",
            "progress": 0,
            "config": task_data.get("config", {}),
        }
        self._tasks[task_id] = task
        mock_response.json.return_value = task
        mock_response.status_code = 200
        return mock_response

    def cancel_task(self, task_id: str):
        """Cancel a task."""
        mock_response = MagicMock()
        if task_id in self._tasks:
            self._tasks[task_id]["status"] = "cancelled"
        mock_response.status_code = 200
        return mock_response

    def get_hosts(self):
        """Get cluster hosts."""
        mock_response = MagicMock()
        mock_response.json.return_value = list(self._nodes.values())
        mock_response.status_code = 200
        return mock_response

    def get_host(self, node_id: str):
        """Get a specific host."""
        mock_response = MagicMock()
        node = self._nodes.get(node_id, {})
        mock_response.json.return_value = node
        mock_response.status_code = 200 if node else 404
        return mock_response


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def page():
    """
    Provide a mock page fixture for cluster tests.

    This is a stub fixture that provides minimal page-like behavior
    for tests that reference it but don't actually need browser automation.
    """
    mock_page = MagicMock()
    mock_page.goto = MagicMock(return_value=None)
    mock_page.wait_for_selector = MagicMock(return_value=None)
    mock_page.query_selector = MagicMock(return_value=None)
    mock_page.inner_text = MagicMock(return_value="")
    mock_page.inner_html = MagicMock(return_value="")
    mock_page.click = MagicMock(return_value=None)
    mock_page.fill = MagicMock(return_value=None)
    mock_page.select_option = MagicMock(return_value=None)
    return mock_page


@pytest.fixture
def api_client():
    """
    Provide a mock API client for cluster tests.

    This provides a mock client that doesn't require a running server.
    """
    return MockAPIClient(base_url=os.getenv("API_BASE_URL", "http://localhost:8000"))


@pytest.fixture
def multi_node_cluster():
    """
    Provide mock multi-node cluster configuration.

    This fixture is already defined in test_scheduling_e2e.py but we
    provide it here as well for consistency.
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

    This fixture is already defined in test_scheduling_e2e.py but we
    provide it here as well for consistency.
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
                "gpu_available": 0,
                "gpu_total": 1,
                "gpu_utilization": 80,
            },
            {
                "node_id": "worker-2",
                "hostname": "worker-120",
                "ip": "192.168.0.120",
                "status": "alive",
                "gpu_available": 1,
                "gpu_total": 1,
                "gpu_utilization": 20,
            },
        ],
        "head_node": "192.168.0.126",
        "worker_nodes": ["192.168.0.115", "192.168.0.120"],
    }