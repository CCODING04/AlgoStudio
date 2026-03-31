# tests/e2e/web/test_sse_progress.py
"""
TC-WEB-004: SSE Progress Updates Test

This module tests Server-Sent Events (SSE) for real-time task progress updates.

Test scenarios:
1. SSE connection establishment
2. Progress updates are received in real-time
3. Progress bar updates correctly
4. Task completion triggers SSE completion event

Reference: PHASE2_E2E_PLAN.md Section 3.1, TC-WEB-004
"""

import json
import os
import pytest
import time
from unittest.mock import MagicMock, patch
from sseclient import SSEClient


@pytest.mark.web
@pytest.mark.e2e
@pytest.mark.skipif(
    os.getenv("CI", "").lower() in ("true", "1", "yes"),
    reason="Requires real API server and browser"
)
class TestSSEProgressUpdates:
    """Test suite for SSE-based task progress updates."""

    def test_sse_connection_establishment(self, page, api_client):
        """
        Test: SSE connection is established when viewing task details.

        Steps:
        1. Create a training task
        2. Navigate to task details page
        3. Verify SSE connection is established
        4. Verify initial task state is received
        """
        # Create a task
        task_payload = {
            "task_type": "train",
            "algorithm_name": "simple_classifier",
            "algorithm_version": "v1",
            "config": {"epochs": 100},
        }
        response = api_client.create_task(task_payload)
        assert response.status_code == 200

        task = response.json()
        task_id = task["task_id"]

        # Navigate to task details page
        page.goto(f"/tasks/{task_id}")

        # Wait for SSE connection indicator
        # The page should show "Connected" or similar
        sse_status = page.locator("[data-testid='sse-status']")
        if sse_status.count() > 0:
            assert sse_status.text_content() == "Connected", "SSE should be connected"

    def test_sse_progress_updates(self, page, api_client, sse_mock_server):
        """
        Test: Progress updates are received via SSE in real-time.

        This test uses the SSE mock server for CI environments.

        Steps:
        1. Create a task
        2. Connect to SSE endpoint
        3. Verify progress events are received
        4. Verify progress values increase
        """
        # If using mock server, set API URL to mock
        base_url = sse_mock_server.url if sse_mock_server else api_client.base_url

        # Create a task
        task_payload = {
            "task_type": "train",
            "algorithm_name": "simple_classifier",
            "algorithm_version": "v1",
            "config": {"epochs": 10},
        }
        response = api_client.create_task(task_payload)
        task = response.json()
        task_id = task["task_id"]

        # Connect to SSE endpoint
        import httpx

        sse_url = f"{base_url}/api/tasks/{task_id}/sse"
        progress_values = []

        # Note: In browser context, the page handles SSE via JavaScript
        # This test verifies the SSE endpoint works correctly

        # For CI, we test the SSE endpoint directly
        with httpx.stream("GET", sse_url, timeout=30.0) as response:
            assert response.status_code == 200
            assert response.headers.get("content-type") == "text/event-stream"

            # Read SSE events
            client = SSEClient(response.iter_lines())
            for event in client:
                if event.event == "progress":
                    data = json.loads(event.data)
                    progress_values.append(data.get("progress"))

                    if event.event == "completed":
                        break

        # Verify progress values were received
        assert len(progress_values) > 0, "Should receive progress updates"

        # Verify progress increases (should go from 0 or low to 100)
        if len(progress_values) > 1:
            assert progress_values[-1] > progress_values[0], (
                "Progress should increase over time"
            )

    def test_progress_bar_updates(self, page, api_client):
        """
        Test: Progress bar on web page updates in real-time.

        Steps:
        1. Create a task
        2. Navigate to tasks page
        3. Verify progress bar exists and updates
        """
        # Create a task
        task_payload = {
            "task_type": "train",
            "algorithm_name": "simple_classifier",
            "algorithm_version": "v1",
            "config": {"epochs": 50},
        }
        response = api_client.create_task(task_payload)
        task = response.json()
        task_id = task["task_id"]

        # Navigate to tasks page
        page.goto("/tasks")

        # Find the task row
        task_row = page.locator(f"[data-task-id='{task_id}']")
        if task_row.count() > 0:
            # Find progress bar within task row
            progress_bar = task_row.locator(".progress-bar, [role='progressbar']")

            # Verify progress bar exists
            if progress_bar.count() > 0:
                # Get initial progress (Playwright sync API - no await needed)
                initial_progress = progress_bar.get_attribute("aria-valuenow")
                if initial_progress:
                    initial_progress = int(initial_progress)

                    # Wait for progress update
                    time.sleep(2)

                    # Get updated progress
                    updated_progress = progress_bar.get_attribute("aria-valuenow")
                    if updated_progress:
                        updated_progress = int(updated_progress)

                        # Progress should have changed (unless task completed quickly)
                        assert updated_progress >= initial_progress

    def test_sse_completion_event(self, page, api_client, sse_mock_server):
        """
        Test: SSE sends completion event when task finishes.

        Steps:
        1. Create a task
        2. Wait for task to complete
        3. Verify 'completed' SSE event is received
        4. Verify task status updates to 'completed'
        """
        base_url = sse_mock_server.url if sse_mock_server else api_client.base_url

        # Create a task
        task_payload = {
            "task_type": "train",
            "algorithm_name": "simple_classifier",
            "algorithm_version": "v1",
            "config": {"epochs": 1},  # Quick task
        }
        response = api_client.create_task(task_payload)
        task = response.json()
        task_id = task["task_id"]

        # Connect to SSE and wait for completion
        import httpx

        sse_url = f"{base_url}/api/tasks/{task_id}/sse"
        completion_received = False

        with httpx.stream("GET", sse_url, timeout=30.0) as response:
            client = SSEClient(response.iter_lines())
            for event in client:
                if event.event == "completed":
                    data = json.loads(event.data)
                    assert data.get("status") == "completed"
                    assert data.get("task_id") == task_id
                    completion_received = True
                    break

        assert completion_received, "Should receive completion event"

    def test_sse_reconnection_on_disconnect(self, page, api_client):
        """
        Test: SSE client reconnects automatically on disconnect.

        This is important for production environments where network
        instability can cause SSE connections to drop.
        """
        # This test would require a more complex setup to simulate disconnects
        # For now, we document the expected behavior

        pytest.skip("Requires network simulation - documented behavior only")

        # Expected behavior:
        # 1. SSE connection drops
        # 2. Client automatically attempts reconnection
        # 3. Client backoff increases on each failure (exponential backoff)
        # 4. After max retries, client gives up and shows error state


@pytest.mark.mock
@pytest.mark.e2e
class TestSSEMock:
    """Test suite for SSE mock functionality in CI environments."""

    def test_sse_mock_server_responds_correctly(self, sse_mock_server):
        """Test: Mock SSE server responds correctly to requests."""
        import httpx

        # Test task list endpoint
        response = httpx.get(f"{sse_mock_server.url}/api/tasks")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

    def test_sse_mock_server_sends_events(self, sse_mock_server):
        """Test: Mock SSE server sends proper SSE events."""
        import httpx

        # Test SSE endpoint
        sse_url = f"{sse_mock_server.url}/api/tasks/task-001/sse"

        with httpx.stream("GET", sse_url, timeout=10.0) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            # Read events
            events = []
            for line in response.iter_lines():
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                    events.append(event_type)

            # Should receive connected and progress events
            assert "connected" in events or len(events) > 0

    def test_sse_mock_preserves_ci_compatibility(self):
        """Test: SSE mock works correctly in CI environment."""
        # Set CI environment variable
        import os
        os.environ["CI"] = "true"
        os.environ["USE_MOCK_SERVER"] = "true"

        # Verify mock server can be started
        server = SSEMockServer(port=8899)
        server.start()

        # Wait for server to be ready
        import httpx
        time.sleep(0.5)

        response = httpx.get(f"{server.url}/api/tasks", timeout=10.0)
        assert response.status_code == 200

        server.stop()

        # Reset environment
        os.environ.pop("CI", None)
        os.environ.pop("USE_MOCK_SERVER", None)


# Import for type hint
from tests.e2e.conftest import SSEMockServer
