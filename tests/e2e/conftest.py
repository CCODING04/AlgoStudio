# tests/e2e/conftest.py
"""
Pytest configuration and shared fixtures for AlgoStudio E2E tests.

This module provides:
- Playwright browser/page fixtures
- API client fixtures
- SSE mock server for CI environments
- Ray cluster mocks
"""

import json
import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Callable, Optional
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# SSE Mock Server for CI Environments
# =============================================================================

class SSEEvent:
    """Represents a Server-Sent Event."""

    def __init__(self, event_type: str, data: dict):
        self.event_type = event_type
        self.data = data

    def format(self) -> str:
        """Format the event as SSE data."""
        json_data = json.dumps(self.data)
        return f"event: {self.event_type}\ndata: {json_data}\n\n"


class SSEMockRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler that serves mock SSE events."""

    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path.startswith("/api/tasks/"):
            # Extract task_id from path
            parts = self.path.split("/")
            if len(parts) >= 4:
                task_id = parts[3]
                # Check if it's SSE endpoint
                if self.path.endswith("/sse"):
                    self._handle_task_sse(task_id)
                else:
                    self._handle_task_get(task_id)
            else:
                self._send_error(404)
        elif self.path == "/api/tasks":
            self._handle_tasks_list()
        else:
            self._send_error(404)

    def _handle_task_sse(self, task_id: str):
        """Handle SSE connection for task progress."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # Send initial connection event
        self.wfile.write(self._make_event("connected", {"task_id": task_id}))

        # Send progress events
        for progress in [10, 30, 50, 70, 90, 100]:
            event_data = {
                "task_id": task_id,
                "status": "running" if progress < 100 else "completed",
                "progress": progress,
                "message": f"Training progress: {progress}%",
            }
            self.wfile.write(self._make_event("progress", event_data))
            time.sleep(0.1)

        # Send completion event
        self.wfile.write(self._make_event("completed", {
            "task_id": task_id,
            "status": "completed",
            "progress": 100,
        }))

    def _handle_task_get(self, task_id: str):
        """Handle GET request for task status."""
        task_data = {
            "task_id": task_id,
            "task_type": "train",
            "algorithm_name": "simple_classifier",
            "algorithm_version": "v1",
            "status": "completed",
            "progress": 100,
            "created_at": "2026-03-26T10:00:00Z",
            "started_at": "2026-03-26T10:00:05Z",
            "completed_at": "2026-03-26T10:05:00Z",
            "assigned_node": "192.168.0.115",
        }
        self._send_json(task_data)

    def _handle_tasks_list(self):
        """Handle GET request for tasks list."""
        tasks = [
            {
                "task_id": "task-001",
                "task_type": "train",
                "status": "completed",
                "progress": 100,
            },
            {
                "task_id": "task-002",
                "task_type": "train",
                "status": "running",
                "progress": 50,
            },
        ]
        self._send_json(tasks)

    def _make_event(self, event_type: str, data: dict) -> bytes:
        """Create a formatted SSE event."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n".encode()

    def _send_json(self, data):
        """Send JSON response."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_error(self, code: int):
        """Send error response."""
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(f"Error {code}".encode())

    def log_message(self, format, *args):
        """Suppress log messages."""
        pass


class SSEMockServer:
    """
    Mock SSE server for CI environments that cannot access real Ray clusters.

    Usage:
        server = SSEMockServer(port=8888)
        server.start()
        # Use http://localhost:8888 as API_BASE_URL
        server.stop()
    """

    def __init__(self, port: int = 8888):
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self._running = False

    def start(self):
        """Start the mock SSE server."""
        if self._running:
            return

        self.server = HTTPServer(("localhost", self.port), SSEMockRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self._running = True

    def stop(self):
        """Stop the mock SSE server."""
        if not self._running:
            return

        self._running = False
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=5)

    @property
    def url(self) -> str:
        """Return the server URL."""
        return f"http://localhost:{self.port}"


@pytest.fixture(scope="session")
def sse_mock_server():
    """
    Provide an SSE mock server for CI environments.

    This fixture starts a mock server that provides:
    - Mock task status API
    - Mock SSE progress streaming

    Only active when CI environment is detected or RAY_ADDRESS is not accessible.
    """
    # Check if we should use mock server
    use_mock = os.getenv("USE_MOCK_SERVER", "").lower() in ("true", "1", "yes")
    ray_accessible = os.getenv("CI", "").lower() in ("true", "1", "yes")

    if not use_mock and not ray_accessible:
        # In local dev, skip the mock server
        pytest.skip("Skipping mock server - running against real cluster")

    server = SSEMockServer(port=8888)
    server.start()
    yield server
    server.stop()


# =============================================================================
# Mock Ray Client for CI
# =============================================================================

@pytest.fixture
def mock_ray_client():
    """
    Provide a mock Ray client for CI environments.

    This fixture mocks the RayClient to avoid requiring a real Ray cluster.
    """
    mock_client = MagicMock()

    # Mock node data
    mock_nodes = [
        {
            "node_id": "worker-1",
            "hostname": "192.168.0.115",
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
            "hostname": "192.168.0.120",
            "ip": "192.168.0.120",
            "status": "alive",
            "gpu_available": 0,
            "gpu_total": 1,
            "cpu_cores": 8,
            "memory_total": 32,
            "memory_available": 8,
        },
    ]

    mock_client.get_nodes.return_value = mock_nodes
    mock_client.get_node.return_value = mock_nodes[0]
    mock_client.submit_task.return_value = "task-mock-001"
    mock_client.get_task_status.return_value = "running"
    mock_client.get_task_progress.return_value = 50

    return mock_client


# =============================================================================
# Mock Progress Reporter
# =============================================================================

@pytest.fixture
def mock_progress_reporter():
    """
    Provide a mock progress reporter for CI environments.

    This mocks the SSE streaming to avoid requiring real Ray actors.
    """
    mock_reporter = MagicMock()
    mock_reporter.update_progress.return_value = None
    mock_reporter.get_progress.return_value = 50
    mock_reporter.get_status.return_value = "running"
    return mock_reporter


# =============================================================================
# Fixture for CI Environment Detection
# =============================================================================

@pytest.fixture
def is_ci_environment():
    """Detect if running in CI environment."""
    return os.getenv("CI", "").lower() in ("true", "1", "yes")


# =============================================================================
# Test Data Factories
# =============================================================================

class E2ETaskFactory:
    """Factory for creating task test data for E2E tests."""

    @staticmethod
    def create_train_task(
        algorithm_name: str = "simple_classifier",
        algorithm_version: str = "v1",
        epochs: int = 10,
        batch_size: int = 32,
    ) -> dict:
        """Create a training task payload."""
        return {
            "task_type": "train",
            "algorithm_name": algorithm_name,
            "algorithm_version": algorithm_version,
            "config": {
                "epochs": epochs,
                "batch_size": batch_size,
            },
        }

    @staticmethod
    def create_infer_task(
        algorithm_name: str = "simple_classifier",
        algorithm_version: str = "v1",
    ) -> dict:
        """Create an inference task payload."""
        return {
            "task_type": "infer",
            "algorithm_name": algorithm_name,
            "algorithm_version": algorithm_version,
            "inputs": [[1, 2, 3], [4, 5, 6]],
        }

    @staticmethod
    def create_verify_task(
        algorithm_name: str = "simple_classifier",
        algorithm_version: str = "v1",
    ) -> dict:
        """Create a verification task payload."""
        return {
            "task_type": "verify",
            "algorithm_name": algorithm_name,
            "algorithm_version": algorithm_version,
            "test_data": "/data/test_set",
        }


@pytest.fixture
def task_factory():
    """Provide E2ETaskFactory."""
    return E2ETaskFactory
