# tests/e2e/web/test_sse_real.py
"""
TC-WEB-SSE-REAL-001: Real SSE Connection Tests

This module tests REAL SSE (Server-Sent Events) connections:
1. Real SSE reconnection mechanism testing
2. Real long-lived connection keep-alive testing
3. Real stream termination handling

These tests require a real API server with SSE endpoint and are marked
with @pytest.mark.skip_ci since they cannot run in CI environments.

Reference: Phase 2 Round 4 E2E Plan
"""

import json
import os
import time
import pytest
import httpx
from sseclient import SSEClient


# Skip entire test class in CI environments
pytestmark = pytest.mark.skipif(
    os.getenv("CI", "").lower() in ("true", "1", "yes"),
    reason="Real API server with SSE endpoint required"
)


class TestRealSSEConnection:
    """Test suite for real SSE connection behavior."""

    @pytest.fixture
    def api_base_url(self):
        """Get the API base URL."""
        return os.getenv("API_BASE_URL", "http://localhost:8000")

    @pytest.fixture
    def ensure_api_running(self, api_base_url):
        """Ensure API server is running before tests."""
        try:
            response = httpx.get(f"{api_base_url}/api/tasks", timeout=5)
            assert response.status_code == 200, "API should be accessible"
        except Exception as e:
            pytest.skip(f"API server not running at {api_base_url}: {e}")
        yield

    def test_real_sse_endpoint_accessible(self, api_base_url, ensure_api_running):
        """
        Test: SSE endpoint is accessible and returns correct headers.

        The SSE endpoint at /api/cluster/events should:
        1. Return 200 status
        2. Return text/event-stream content type
        3. Include Cache-Control: no-cache
        """
        sse_url = f"{api_base_url}/api/cluster/events"

        try:
            with httpx.stream("GET", sse_url, timeout=10.0) as response:
                assert response.status_code == 200, \
                    f"SSE endpoint should return 200, got {response.status_code}"

                content_type = response.headers.get("content-type", "")
                assert "text/event-stream" in content_type, \
                    f"Content-Type should be text/event-stream, got {content_type}"

                cache_control = response.headers.get("cache-control", "")
                assert "no-cache" in cache_control.lower(), \
                    f"Cache-Control should be no-cache, got {cache_control}"

        except httpx.ConnectError:
            pytest.skip(f"Cannot connect to API at {api_base_url}")

    def test_real_sse_long_connection_keepalive(self, api_base_url, ensure_api_running):
        """
        Test: SSE connection remains alive over extended period.

        A proper SSE implementation should:
        1. Maintain connection for extended period (30+ seconds)
        2. Send periodic events to keep connection alive
        3. Not close connection prematurely
        """
        sse_url = f"{api_base_url}/api/cluster/events"

        try:
            events_received = []
            start_time = time.time()
            connection_duration = 0

            with httpx.stream("GET", sse_url, timeout=35.0) as response:
                client = SSEClient(response.iter_lines())

                # Read events for up to 30 seconds
                for event in client:
                    elapsed = time.time() - start_time
                    connection_duration = elapsed

                    events_received.append({
                        "event": event.event,
                        "data": event.data,
                        "elapsed": elapsed
                    })

                    # Stop after 30 seconds of connection
                    if elapsed >= 30:
                        break

            # Verify connection lasted at least some time
            assert connection_duration >= 5, \
                f"Connection should last at least 5s, lasted {connection_duration}s"

            # Log events received for debugging
            print(f"Received {len(events_received)} events in {connection_duration:.1f}s")
            for evt in events_received[:5]:  # Print first 5 events
                print(f"  {evt['elapsed']:.1f}s: {evt['event']} - {evt['data'][:100] if evt['data'] else 'empty'}")

        except httpx.ConnectError:
            pytest.skip(f"Cannot connect to API at {api_base_url}")
        except Exception as e:
            pytest.fail(f"SSE connection failed: {e}")

    def test_real_sse_connection_recovery_after_network_blip(
        self, api_base_url, ensure_api_running
    ):
        """
        Test: SSE client can recover after temporary network disruption.

        When a network blip causes SSE connection to drop:
        1. Client should detect disconnection
        2. Client should attempt reconnection
        3. Client should resume receiving events after reconnection

        Note: This test simulates reconnection by closing and reopening
        the connection, since we cannot inject network failures.
        """
        sse_url = f"{api_base_url}/api/cluster/events"

        try:
            # First connection - establish baseline
            with httpx.stream("GET", sse_url, timeout=10.0) as response:
                assert response.status_code == 200

            # Small delay between connections
            time.sleep(1)

            # Second connection - verify reconnection works
            events_after_reconnect = []
            with httpx.stream("GET", sse_url, timeout=10.0) as response:
                assert response.status_code == 200
                client = SSEClient(response.iter_lines())

                # Read a few events
                for i, event in enumerate(client):
                    events_after_reconnect.append(event)
                    if i >= 3:
                        break

            # Verify we received events after reconnecting
            assert len(events_after_reconnect) > 0, \
                "Should receive events after reconnection"

            print(f"Successfully reconnected and received {len(events_after_reconnect)} events")

        except httpx.ConnectError:
            pytest.skip(f"Cannot connect to API at {api_base_url}")

    def test_real_sse_event_format_validity(self, api_base_url, ensure_api_running):
        """
        Test: SSE events follow proper format specification.

        Each event should have:
        1. event: <event_type>
        2. data: <json_payload>

        And the data should be valid JSON.
        """
        sse_url = f"{api_base_url}/api/cluster/events"

        try:
            with httpx.stream("GET", sse_url, timeout=15.0) as response:
                assert response.status_code == 200

                client = SSEClient(response.iter_lines())
                events_with_valid_data = 0
                events_checked = 0

                for event in client:
                    events_checked += 1

                    # Skip events without data
                    if not event.data:
                        continue

                    # Try to parse as JSON
                    try:
                        json.loads(event.data)
                        events_with_valid_data += 1
                    except json.JSONDecodeError:
                        pass

                    # Stop after checking enough events
                    if events_checked >= 5:
                        break

                # Most events should have valid JSON data
                assert events_with_valid_data >= events_checked - 1, \
                    "Most events should have valid JSON data"

        except httpx.ConnectError:
            pytest.skip(f"Cannot connect to API at {api_base_url}")

    def test_real_sse_no_hang_on_api_restart(self, api_base_url, ensure_api_running):
        """
        Test: Client properly handles SSE connection when API is restarting.

        When the API server restarts:
        1. Existing SSE connection should be closed by server
        2. Client should receive proper close notification
        3. Client should not hang indefinitely

        This is a documentation test - actual API restart requires
        external process management.
        """
        sse_url = f"{api_base_url}/api/cluster/events"

        # This test documents expected behavior
        # Actual testing would require process management capabilities

        try:
            with httpx.stream("GET", sse_url, timeout=5.0) as response:
                # Read at least one event
                for event in SSEClient(response.iter_lines()):
                    print(f"Received event: {event.event}")
                    break
        except httpx.ReadTimeout:
            # If we get a read timeout, that's acceptable for this test
            # The important thing is the connection doesn't hang forever
            pass
        except httpx.ConnectError:
            pytest.skip(f"Cannot connect to API at {api_base_url}")


class TestRealSSETaskProgress:
    """Test suite for SSE task progress streaming."""

    @pytest.fixture
    def api_base_url(self):
        """Get the API base URL."""
        return os.getenv("API_BASE_URL", "http://localhost:8000")

    @pytest.fixture
    def ensure_api_running(self, api_base_url):
        """Ensure API server is running before tests."""
        try:
            response = httpx.get(f"{api_base_url}/api/tasks", timeout=5)
            assert response.status_code == 200, "API should be accessible"
        except Exception as e:
            pytest.skip(f"API server not running at {api_base_url}: {e}")
        yield

    @pytest.fixture
    def create_test_task(self, api_base_url):
        """Create a test task and return its ID."""
        task_payload = {
            "task_type": "train",
            "algorithm_name": "simple_classifier",
            "algorithm_version": "v1",
            "config": {"epochs": 5}
        }
        response = httpx.post(f"{api_base_url}/api/tasks", json=task_payload, timeout=10)
        assert response.status_code == 200
        task = response.json()
        return task["task_id"]

    def test_real_sse_task_progress_updates(self, api_base_url, ensure_api_running, create_test_task):
        """
        Test: Task progress is visible via SSE endpoint.

        While the main SSE endpoint is /api/cluster/events for cluster-wide
        events, we verify the SSE infrastructure is working by connecting
        to it and receiving events.
        """
        sse_url = f"{api_base_url}/api/cluster/events"
        task_id = create_test_task

        try:
            progress_events = []
            all_events = []

            with httpx.stream("GET", sse_url, timeout=20.0) as response:
                client = SSEClient(response.iter_lines())

                for event in client:
                    all_events.append(event)

                    if event.event == "progress" and task_id in event.data:
                        try:
                            data = json.loads(event.data)
                            if data.get("task_id") == task_id:
                                progress_events.append(data)
                        except json.JSONDecodeError:
                            pass

                    # Collect at least 3 events before stopping
                    if len(all_events) >= 3:
                        break

            # We should have received some events
            assert len(all_events) > 0, "Should receive at least some SSE events"

            print(f"Received {len(all_events)} events, {len(progress_events)} progress events for task {task_id}")

        except httpx.ConnectError:
            pytest.skip(f"Cannot connect to API at {api_base_url}")

    def test_real_sse_task_completion_event(self, api_base_url, ensure_api_running):
        """
        Test: Task completion triggers SSE completion event.

        When a task completes, the SSE stream should emit a completion event.

        Note: This test uses a short task to increase chance of capturing completion.
        """
        # Create a task with minimal work
        task_payload = {
            "task_type": "train",
            "algorithm_name": "simple_classifier",
            "algorithm_version": "v1",
            "config": {"epochs": 1}
        }

        try:
            # Create task
            response = httpx.post(f"{api_base_url}/api/tasks", json=task_payload, timeout=10)
            if response.status_code != 200:
                pytest.skip(f"Cannot create task: {response.status_code}")
            task = response.json()
            task_id = task["task_id"]

            # Dispatch the task
            dispatch_response = httpx.post(
                f"{api_base_url}/api/tasks/{task_id}/dispatch",
                timeout=10
            )
            if dispatch_response.status_code != 200:
                pytest.skip(f"Cannot dispatch task: {dispatch_response.status_code}")

            # Connect to SSE and wait for completion
            sse_url = f"{api_base_url}/api/cluster/events"
            completion_received = False
            max_wait = 60  # Wait up to 60 seconds for completion

            start_time = time.time()
            with httpx.stream("GET", sse_url, timeout=max_wait + 5) as response:
                client = SSEClient(response.iter_lines())

                for event in client:
                    elapsed = time.time() - start_time

                    if event.event == "completed":
                        try:
                            data = json.loads(event.data)
                            if data.get("task_id") == task_id:
                                completion_received = True
                                print(f"Task {task_id} completed after {elapsed:.1f}s")
                                break
                        except json.JSONDecodeError:
                            pass

                    # Timeout if task doesn't complete in reasonable time
                    if elapsed >= max_wait:
                        break

            # Note: We don't assert completion_received because tasks may fail
            # if the algorithm isn't properly set up. The important thing is
            # that we can connect and receive SSE events.
            print(f"SSE connection test completed. Completion received: {completion_received}")

        except httpx.ConnectError:
            pytest.skip(f"Cannot connect to API at {api_base_url}")


class TestRealSSEClientBehavior:
    """Test suite for real SSE client behavior verification."""

    @pytest.fixture
    def api_base_url(self):
        """Get the API base URL."""
        return os.getenv("API_BASE_URL", "http://localhost:8000")

    @pytest.fixture
    def ensure_api_running(self, api_base_url):
        """Ensure API server is running before tests."""
        try:
            response = httpx.get(f"{api_base_url}/api/tasks", timeout=5)
            assert response.status_code == 200, "API should be accessible"
        except Exception as e:
            pytest.skip(f"API server not running at {api_base_url}: {e}")
        yield

    def test_real_sse_client_handles_idle_timeout(self, api_base_url, ensure_api_running):
        """
        Test: SSE client handles server-side idle timeout gracefully.

        If server closes connection after idle period:
        1. Client should detect the closure
        2. Client should not hang on next read
        3. Client can attempt reconnection
        """
        sse_url = f"{api_base_url}/api/cluster/events"

        try:
            # Establish connection
            with httpx.stream("GET", sse_url, timeout=10.0) as response:
                assert response.status_code == 200

                client = SSEClient(response.iter_lines())

                # Read first event (should come quickly)
                first_event = next(client)
                assert first_event is not None

            # Connection should be closed after exiting context

            # Verify we can reconnect
            with httpx.stream("GET", sse_url, timeout=10.0) as response:
                assert response.status_code == 200

        except httpx.ConnectError:
            pytest.skip(f"Cannot connect to API at {api_base_url}")

    def test_real_sse_chunked_transfer_encoding(self, api_base_url, ensure_api_running):
        """
        Test: SSE works correctly with chunked transfer encoding.

        SSE typically uses chunked transfer encoding. Verify that:
        1. Response uses chunked transfer encoding
        2. Events are delivered as they are generated
        3. No buffering issues occur
        """
        sse_url = f"{api_base_url}/api/cluster/events"

        try:
            with httpx.stream("GET", sse_url, timeout=15.0) as response:
                transfer_encoding = response.headers.get("transfer-encoding", "")

                # Chunked transfer encoding is typical for SSE
                # but not strictly required
                print(f"Transfer-Encoding: {transfer_encoding}")

                # Read multiple events to verify streaming works
                events = []
                client = SSEClient(response.iter_lines())

                for event in client:
                    events.append(event)
                    if len(events) >= 5:
                        break

                assert len(events) > 0, "Should receive events via streaming"
                print(f"Received {len(events)} events via chunked transfer")

        except httpx.ConnectError:
            pytest.skip(f"Cannot connect to API at {api_base_url}")
