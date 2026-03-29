# tests/unit/core/test_ray_dashboard_client.py
"""Unit tests for core/ray_dashboard_client.py module."""

import time
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from algo_studio.core.ray_dashboard_client import (
    RayAPIClient,
    RayAPIResponse,
    CircuitState,
)


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_circuit_state_values(self):
        """Test CircuitState enum values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_circuit_state_is_enum(self):
        """Test CircuitState is a proper Enum."""
        assert hasattr(CircuitState, 'CLOSED')
        assert hasattr(CircuitState, 'OPEN')
        assert hasattr(CircuitState, 'HALF_OPEN')


class TestRayAPIResponse:
    """Tests for RayAPIResponse dataclass."""

    def test_ray_api_response_success(self):
        """Test RayAPIResponse with successful response."""
        response = RayAPIResponse(success=True, data={"key": "value"})
        assert response.success is True
        assert response.data == {"key": "value"}
        assert response.error is None
        assert response.cached is False

    def test_ray_api_response_with_error(self):
        """Test RayAPIResponse with error."""
        response = RayAPIResponse(success=False, data=None, error="Connection failed")
        assert response.success is False
        assert response.data is None
        assert response.error == "Connection failed"

    def test_ray_api_response_cached(self):
        """Test RayAPIResponse with cached flag."""
        response = RayAPIResponse(success=True, data={"cached": True}, cached=True)
        assert response.cached is True

    def test_ray_api_response_default_values(self):
        """Test RayAPIResponse default values."""
        response = RayAPIResponse(success=True, data={})
        assert response.error is None
        assert response.cached is False


class TestRayAPIClientInit:
    """Tests for RayAPIClient initialization."""

    def test_init_default_values(self):
        """Test RayAPIClient initialization with defaults."""
        client = RayAPIClient()
        assert client.base_url == "http://localhost:8265"
        assert client.timeout == 10
        assert client.enable_cache is True
        assert client.enable_circuit_breaker is True
        assert client._circuit_state == CircuitState.CLOSED
        assert client._failure_count == 0
        assert client._half_open_success == 0

    def test_init_custom_address(self):
        """Test RayAPIClient with custom head address."""
        client = RayAPIClient(head_address="192.168.0.126")
        assert client.base_url == "http://192.168.0.126:8265"

    def test_init_custom_port(self):
        """Test RayAPIClient with custom dashboard port."""
        client = RayAPIClient(dashboard_port=9090)
        assert client.base_url == "http://localhost:9090"

    def test_init_custom_timeout(self):
        """Test RayAPIClient with custom timeout."""
        client = RayAPIClient(timeout=30)
        assert client.timeout == 30

    def test_init_cache_disabled(self):
        """Test RayAPIClient with cache disabled."""
        client = RayAPIClient(enable_cache=False)
        assert client.enable_cache is False

    def test_init_circuit_breaker_disabled(self):
        """Test RayAPIClient with circuit breaker disabled."""
        client = RayAPIClient(enable_circuit_breaker=False)
        assert client.enable_circuit_breaker is False

    def test_init_with_all_custom_params(self):
        """Test RayAPIClient with all custom parameters."""
        client = RayAPIClient(
            head_address="192.168.0.100",
            dashboard_port=9000,
            timeout=60,
            enable_cache=False,
            enable_circuit_breaker=False,
        )
        assert client.base_url == "http://192.168.0.100:9000"
        assert client.timeout == 60
        assert client.enable_cache is False
        assert client.enable_circuit_breaker is False


class TestRayAPIClientCacheMethods:
    """Tests for RayAPIClient cache methods."""

    def test_get_cache_key_without_params(self):
        """Test _get_cache_key without params."""
        client = RayAPIClient()
        key = client._get_cache_key("/api/cluster_status")
        assert key == "/api/cluster_status"

    def test_get_cache_key_with_params(self):
        """Test _get_cache_key with params."""
        client = RayAPIClient()
        key = client._get_cache_key("/nodes", {"view": "summary"})
        # Key contains endpoint and sorted params
        assert "/nodes" in key
        assert "summary" in key

    def test_get_cache_key_with_multiple_params(self):
        """Test _get_cache_key with multiple params."""
        client = RayAPIClient()
        key = client._get_cache_key("/api/test", {"b": 2, "a": 1, "c": 3})
        # Should be sorted alphabetically; format is str(sorted(params.items()))
        assert key == "/api/test?[('a', 1), ('b', 2), ('c', 3)]"

    def test_is_cache_valid_missing_key(self):
        """Test _is_cache_valid returns False for missing key."""
        client = RayAPIClient()
        assert client._is_cache_valid("/nonexistent") is False

    def test_is_cache_valid_expired(self):
        """Test _is_cache_valid returns False for expired entry."""
        client = RayAPIClient()
        client._cache["/test"] = ({"data": "value"}, time.time() - 10)  # TTL is 5 seconds
        assert client._is_cache_valid("/test") is False

    def test_is_cache_valid_valid(self):
        """Test _is_cache_valid returns True for valid entry."""
        client = RayAPIClient()
        client._cache["/test"] = ({"data": "value"}, time.time())
        assert client._is_cache_valid("/test") is True

    def test_get_cached_when_disabled(self):
        """Test _get_cached returns None when cache disabled."""
        client = RayAPIClient(enable_cache=False)
        client._cache["/test"] = ({"data": "value"}, time.time())
        assert client._get_cached("/test") is None

    def test_get_cached_missing_key(self):
        """Test _get_cached returns None for missing key."""
        client = RayAPIClient()
        assert client._get_cached("/nonexistent") is None

    def test_get_cached_valid(self):
        """Test _get_cached returns cached data."""
        client = RayAPIClient()
        client._cache["/test"] = ({"data": "value"}, time.time())
        result = client._get_cached("/test")
        assert result == {"data": "value"}

    def test_set_cache_when_disabled(self):
        """Test _set_cache does nothing when cache disabled."""
        client = RayAPIClient(enable_cache=False)
        client._set_cache("/test", {"data": "value"})
        assert "/test" not in client._cache

    def test_set_cache_basic(self):
        """Test _set_cache stores data."""
        client = RayAPIClient()
        client._set_cache("/test", {"data": "value"})
        assert "/test" in client._cache
        assert client._cache["/test"][0] == {"data": "value"}

    def test_set_cache_eviction(self):
        """Test _set_cache evicts oldest entries when max size reached."""
        client = RayAPIClient()
        client.CACHE_MAX_SIZE = 5

        # Fill cache to max
        for i in range(5):
            client._set_cache(f"/test{i}", {"data": i})

        assert len(client._cache) == 5

        # Add one more - should evict oldest 10 (all current entries) then add new
        client._set_cache("/test_new", {"data": "new"})
        # All old entries evicted, only new one remains
        assert "/test0" not in client._cache
        assert "/test4" not in client._cache
        assert "/test_new" in client._cache


class TestRayAPIClientCircuitBreaker:
    """Tests for RayAPIClient circuit breaker methods."""

    def test_update_circuit_state_when_disabled(self):
        """Test _update_circuit_state does nothing when circuit breaker disabled."""
        client = RayAPIClient(enable_circuit_breaker=False)
        client._update_circuit_state(success=True)
        assert client._circuit_state == CircuitState.CLOSED

    def test_update_circuit_state_success_closed(self):
        """Test _update_circuit_state success when closed resets failure count."""
        client = RayAPIClient()
        client._failure_count = 3
        client._update_circuit_state(success=True)
        assert client._failure_count == 0

    def test_update_circuit_state_failure_closed(self):
        """Test _update_circuit_state failure increments count and opens circuit."""
        client = RayAPIClient()
        for _ in range(5):
            client._update_circuit_state(success=False)
        assert client._circuit_state == CircuitState.OPEN
        assert client._failure_count == 5

    def test_update_circuit_state_half_open_success(self):
        """Test _update_circuit_state half-open success counter."""
        client = RayAPIClient()
        client._circuit_state = CircuitState.HALF_OPEN
        client._half_open_success = 0
        client._update_circuit_state(success=True)
        assert client._half_open_success == 1

    def test_update_circuit_state_half_open_recovery(self):
        """Test _update_circuit_state half-open recovers after enough successes."""
        client = RayAPIClient()
        client._circuit_state = CircuitState.HALF_OPEN
        client._failure_count = 5

        for _ in range(3):
            client._update_circuit_state(success=True)

        assert client._circuit_state == CircuitState.CLOSED
        assert client._failure_count == 0

    def test_update_circuit_state_half_open_failure(self):
        """Test _update_circuit_state half-open failure reopens circuit."""
        client = RayAPIClient()
        client._circuit_state = CircuitState.HALF_OPEN
        client._update_circuit_state(success=False)
        assert client._circuit_state == CircuitState.OPEN

    def test_should_allow_request_when_disabled(self):
        """Test _should_allow_request returns True when circuit breaker disabled."""
        client = RayAPIClient(enable_circuit_breaker=False)
        assert client._should_allow_request() is True

    def test_should_allow_request_closed(self):
        """Test _should_allow_request returns True when closed."""
        client = RayAPIClient()
        client._circuit_state = CircuitState.CLOSED
        assert client._should_allow_request() is True

    def test_should_allow_request_open_timeout_not_reached(self):
        """Test _should_allow_request returns False when open and timeout not reached."""
        client = RayAPIClient()
        client._circuit_state = CircuitState.OPEN
        client._last_failure_time = time.time()
        assert client._should_allow_request() is False

    def test_should_allow_request_open_timeout_reached(self):
        """Test _should_allow_request transitions to half-open when timeout reached."""
        client = RayAPIClient()
        client._circuit_state = CircuitState.OPEN
        client._last_failure_time = time.time() - 31  # 30 second timeout

        result = client._should_allow_request()

        assert result is True
        assert client._circuit_state == CircuitState.HALF_OPEN

    def test_should_allow_request_half_open(self):
        """Test _should_allow_request returns True when half-open."""
        client = RayAPIClient()
        client._circuit_state = CircuitState.HALF_OPEN
        assert client._should_allow_request() is True

    def test_get_circuit_state(self):
        """Test get_circuit_state returns current state."""
        client = RayAPIClient()
        assert client.get_circuit_state() == "closed"

        client._circuit_state = CircuitState.OPEN
        assert client.get_circuit_state() == "open"


class TestRayAPIClientMakeRequest:
    """Tests for RayAPIClient _make_request method."""

    def test_make_request_returns_cached(self):
        """Test _make_request returns cached response."""
        client = RayAPIClient()
        client._cache["/api/test"] = ({"cached": True}, time.time())

        with patch('requests.request') as mock_request:
            response = client._make_request("GET", "/api/test")

        assert response.success is True
        assert response.cached is True
        assert response.data == {"cached": True}
        mock_request.assert_not_called()

    def test_make_request_circuit_open(self):
        """Test _make_request returns error when circuit open."""
        client = RayAPIClient()
        client._circuit_state = CircuitState.OPEN
        client._last_failure_time = time.time()

        response = client._make_request("GET", "/api/test")

        assert response.success is False
        assert "Circuit breaker is OPEN" in response.error

    @patch('requests.request')
    def test_make_request_success_200(self, mock_request):
        """Test _make_request with successful 200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "value"}
        mock_request.return_value = mock_response

        client = RayAPIClient()
        response = client._make_request("GET", "/api/test")

        assert response.success is True
        assert response.data == {"data": "value"}
        assert response.cached is False
        mock_request.assert_called_once()

    @patch('requests.request')
    def test_make_request_non_200(self, mock_request):
        """Test _make_request with non-200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_request.return_value = mock_response

        client = RayAPIClient()
        response = client._make_request("GET", "/api/test")

        assert response.success is False
        assert "404" in response.error

    @patch('requests.request')
    def test_make_request_timeout_retry(self, mock_request):
        """Test _make_request retries on timeout."""
        import requests as req

        mock_request.side_effect = [
            req.exceptions.Timeout("timeout"),
            req.exceptions.Timeout("timeout"),
            MagicMock(status_code=200, json=lambda: {"data": "value"}),
        ]

        client = RayAPIClient()
        response = client._make_request("GET", "/api/test")

        assert response.success is True
        assert response.data == {"data": "value"}
        # Should have retried (3 attempts)
        assert mock_request.call_count == 3

    @patch('requests.request')
    def test_make_request_timeout_max_retries_exceeded(self, mock_request):
        """Test _make_request returns error after max retries."""
        import requests as req

        mock_request.side_effect = req.exceptions.Timeout("timeout")

        client = RayAPIClient()
        response = client._make_request("GET", "/api/test")

        assert response.success is False
        assert "timeout" in response.error.lower()
        assert mock_request.call_count == 4  # Initial + 3 retries

    @patch('requests.request')
    def test_make_request_connection_error(self, mock_request):
        """Test _make_request handles connection error."""
        import requests as req

        mock_request.side_effect = req.exceptions.ConnectionError("Connection refused")

        client = RayAPIClient()
        response = client._make_request("GET", "/api/test")

        assert response.success is False
        assert "Connection error" in response.error

    @patch('requests.request')
    def test_make_request_unexpected_error(self, mock_request):
        """Test _make_request handles unexpected errors."""
        mock_request.side_effect = ValueError("Unexpected error")

        client = RayAPIClient()
        response = client._make_request("GET", "/api/test")

        assert response.success is False
        assert "Unexpected error" in response.error


class TestRayAPIClientPublicAPI:
    """Tests for RayAPIClient public API methods."""

    @patch('requests.request')
    def test_health_check(self, mock_request):
        """Test health_check method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_request.return_value = mock_response

        client = RayAPIClient()
        response = client.health_check()

        assert response.success is True
        mock_request.assert_called_with(
            method="GET",
            url="http://localhost:8265/api/gcs_healthz",
            params=None,
            json=None,
            timeout=10,
        )

    @patch('requests.request')
    def test_get_cluster_status(self, mock_request):
        """Test get_cluster_status method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"cluster": "alive"}
        mock_request.return_value = mock_response

        client = RayAPIClient()
        response = client.get_cluster_status()

        assert response.success is True
        assert response.data == {"cluster": "alive"}

    @patch('requests.request')
    def test_list_nodes(self, mock_request):
        """Test list_nodes method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"nodes": []}
        mock_request.return_value = mock_response

        client = RayAPIClient()
        response = client.list_nodes(view="summary")

        assert response.success is True
        mock_request.assert_called_with(
            method="GET",
            url="http://localhost:8265/nodes",
            params={"view": "summary"},
            json=None,
            timeout=10,
        )

    @patch('requests.request')
    def test_get_node(self, mock_request):
        """Test get_node method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"node_id": "abc123"}
        mock_request.return_value = mock_response

        client = RayAPIClient()
        response = client.get_node("abc123")

        assert response.success is True
        mock_request.assert_called_with(
            method="GET",
            url="http://localhost:8265/nodes/abc123",
            params=None,
            json=None,
            timeout=10,
        )

    @patch('requests.request')
    def test_list_actors(self, mock_request):
        """Test list_actors method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"actors": []}
        mock_request.return_value = mock_response

        client = RayAPIClient()
        response = client.list_actors(limit=50)

        assert response.success is True
        mock_request.assert_called_with(
            method="GET",
            url="http://localhost:8265/api/v0/actors",
            params={"limit": 50},
            json=None,
            timeout=10,
        )

    @patch('requests.request')
    def test_get_actor(self, mock_request):
        """Test get_actor method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"actor_id": "xyz"}
        mock_request.return_value = mock_response

        client = RayAPIClient()
        response = client.get_actor("xyz")

        assert response.success is True

    @patch('requests.request')
    def test_list_tasks(self, mock_request):
        """Test list_tasks method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tasks": []}
        mock_request.return_value = mock_response

        client = RayAPIClient()
        response = client.list_tasks(limit=100)

        assert response.success is True

    @patch('requests.request')
    def test_list_jobs(self, mock_request):
        """Test list_jobs method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"jobs": []}
        mock_request.return_value = mock_response

        client = RayAPIClient()
        response = client.list_jobs()

        assert response.success is True

    @patch('requests.request')
    def test_get_cluster_metadata(self, mock_request):
        """Test get_cluster_metadata method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"version": "2.5.0"}
        mock_request.return_value = mock_response

        client = RayAPIClient()
        response = client.get_cluster_metadata()

        assert response.success is True

    @patch('requests.request')
    def test_get_metrics(self, mock_request):
        """Test get_metrics method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"metrics": []}
        mock_request.return_value = mock_response

        client = RayAPIClient()
        response = client.get_metrics()

        assert response.success is True

    @patch('requests.request')
    def test_summarize_actors(self, mock_request):
        """Test summarize_actors method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"summary": {}}
        mock_request.return_value = mock_response

        client = RayAPIClient()
        response = client.summarize_actors()

        assert response.success is True

    @patch('requests.request')
    def test_summarize_tasks(self, mock_request):
        """Test summarize_tasks method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"summary": {}}
        mock_request.return_value = mock_response

        client = RayAPIClient()
        response = client.summarize_tasks()

        assert response.success is True


class TestRayAPIClientUtilityMethods:
    """Tests for RayAPIClient utility methods."""

    def test_invalidate_cache_all(self):
        """Test invalidate_cache clears all cache."""
        client = RayAPIClient()
        client._set_cache("/test1", {"data": 1})
        client._set_cache("/test2", {"data": 2})

        client.invalidate_cache()

        assert len(client._cache) == 0
        assert len(client._cache_timestamps) == 0

    def test_invalidate_cache_specific_endpoint(self):
        """Test invalidate_cache clears specific endpoint."""
        client = RayAPIClient()
        client._set_cache("/api/test1", {"data": 1})
        client._set_cache("/api/test2", {"data": 2})
        client._set_cache("/other/test", {"data": 3})

        client.invalidate_cache("/api/")

        assert "/api/test1" not in client._cache
        assert "/api/test2" not in client._cache
        assert "/other/test" in client._cache

    def test_get_cache_stats(self):
        """Test get_cache_stats returns correct stats."""
        client = RayAPIClient()
        client._set_cache("/test1", {"data": 1})
        client._set_cache("/test2", {"data": 2})

        stats = client.get_cache_stats()

        assert stats["size"] == 2
        assert stats["max_size"] == 100

    def test_close(self):
        """Test close clears cache."""
        client = RayAPIClient()
        client._set_cache("/test1", {"data": 1})
        client._set_cache("/test2", {"data": 2})

        client.close()

        assert len(client._cache) == 0
        assert len(client._cache_timestamps) == 0


class TestRayAPIClientIntegration:
    """Integration tests for RayAPIClient with circuit breaker and cache."""

    @patch('requests.request')
    def test_cache_then_failure(self, mock_request):
        """Test cache is used then circuit breaker opens after failures."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "cached"}
        mock_request.return_value = mock_response

        client = RayAPIClient()

        # First request - populates cache
        response1 = client.health_check()
        assert response1.success is True
        assert response1.cached is False

        # Second request - uses cache
        response2 = client.health_check()
        assert response2.success is True
        assert response2.cached is True

        # Now simulate failures to open circuit
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        for _ in range(5):
            client._update_circuit_state(success=False)

        assert client._circuit_state == CircuitState.OPEN

        # Clear cache so circuit state is checked (cache check happens before circuit check)
        client.invalidate_cache()

        # Request should be blocked
        response3 = client.health_check()
        assert response3.success is False
        assert "Circuit breaker is OPEN" in response3.error

    @patch('requests.request')
    def test_circuit_half_open_recovery_flow(self, mock_request):
        """Test circuit breaker half-open to closed recovery."""
        client = RayAPIClient()

        # Open the circuit
        for _ in range(5):
            client._update_circuit_state(success=False)
        assert client._circuit_state == CircuitState.OPEN

        # Wait for recovery timeout
        client._last_failure_time = time.time() - 31

        # Configure mock to succeed on the half-open probe request
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_request.return_value = mock_response

        # Next request should transition to half-open and succeed
        response = client.health_check()
        assert response.success is True
        assert client._circuit_state == CircuitState.HALF_OPEN

        # Additional successes should close the circuit
        for _ in range(3):
            client._update_circuit_state(success=True)

        assert client._circuit_state == CircuitState.CLOSED
