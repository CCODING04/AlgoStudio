# tests/test_ray_dashboard_client.py
"""Tests for RayAPIClient - Ray Dashboard API封装类"""

import pytest
from unittest.mock import patch, MagicMock
from algo_studio.core.ray_dashboard_client import RayAPIClient, RayAPIResponse, CircuitState


class TestRayAPIClient:
    """Test suite for RayAPIClient"""

    def setup_method(self):
        """Set up test fixtures"""
        self.client = RayAPIClient(
            head_address="localhost",
            dashboard_port=8265,
            enable_cache=True,
            enable_circuit_breaker=True
        )

    def test_initialization(self):
        """Test client initialization"""
        client = RayAPIClient(
            head_address="192.168.0.100",
            dashboard_port=9000
        )

        assert client.base_url == "http://192.168.0.100:9000"
        assert client.timeout == 10
        assert client.enable_cache is True
        assert client.enable_circuit_breaker is True

    def test_initialization_defaults(self):
        """Test client with default values"""
        client = RayAPIClient()

        assert client.base_url == "http://localhost:8265"
        assert client.enable_cache is True
        assert client.enable_circuit_breaker is True

    def test_cache_key_generation(self):
        """Test cache key generation"""
        key1 = self.client._get_cache_key("/api/nodes")
        key2 = self.client._get_cache_key("/api/nodes", {"view": "summary"})
        key3 = self.client._get_cache_key("/api/nodes", {"view": "detail"})

        assert key1 == "/api/nodes"
        assert "view" in key2
        assert key2 != key3  # Different params should give different keys

    def test_cache_key_params_sorted(self):
        """Test that cache key params are sorted"""
        key1 = self.client._get_cache_key("/api/nodes", {"a": 1, "b": 2})
        key2 = self.client._get_cache_key("/api/nodes", {"b": 2, "a": 1})

        assert key1 == key2  # Should be same regardless of param order

    def test_cache_hit(self):
        """Test cache hit returns cached data"""
        self.client._set_cache("/test", {"data": "cached"})

        result = self.client._get_cached("/test")

        assert result == {"data": "cached"}

    def test_cache_miss(self):
        """Test cache miss returns None"""
        result = self.client._get_cached("/nonexistent")

        assert result is None

    def test_cache_expiration(self):
        """Test that cache expires after TTL"""
        # Manually set cache with old timestamp
        self.client._cache["/old"] = ({"data": "old"}, 0)  # 0 = epoch time
        self.client._cache_timestamps["/old"] = 0

        result = self.client._get_cached("/old")

        assert result is None  # Expired

    def test_set_cache_respects_max_size(self):
        """Test that cache respects max size limit"""
        client = RayAPIClient(enable_cache=True)
        client.CACHE_MAX_SIZE = 5

        # Fill cache
        for i in range(10):
            client._set_cache(f"/key{i}", {"data": i})

        # Should only have 5 entries
        assert len(client._cache) <= 5

    def test_circuit_state_closed_initially(self):
        """Test circuit breaker is closed initially"""
        assert self.client._circuit_state == CircuitState.CLOSED
        assert self.client.get_circuit_state() == "closed"

    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after failure threshold"""
        client = RayAPIClient(enable_circuit_breaker=True)
        client.CIRCUIT_FAILURE_THRESHOLD = 3

        # Simulate failures
        for _ in range(3):
            client._update_circuit_state(success=False)

        assert client._circuit_state == CircuitState.OPEN

    def test_circuit_breaker_resets_on_success(self):
        """Test circuit breaker resets failure count on success"""
        self.client._failure_count = 2

        self.client._update_circuit_state(success=True)

        assert self.client._failure_count == 0

    def test_circuit_breaker_half_open_after_timeout(self):
        """Test circuit breaker goes to half-open after recovery timeout"""
        client = RayAPIClient(enable_circuit_breaker=True)
        client.CIRCUIT_FAILURE_THRESHOLD = 1
        client.CIRCUIT_RECOVERY_TIMEOUT = 0.1  # 100ms

        # Open circuit
        client._update_circuit_state(success=False)
        assert client._circuit_state == CircuitState.OPEN

        # Wait for recovery timeout
        import time
        time.sleep(0.15)

        # Should allow request (will transition to half-open)
        can_request = client._should_allow_request()
        assert can_request is True
        assert client._circuit_state == CircuitState.HALF_OPEN

    def test_should_allow_request_when_closed(self):
        """Test requests are allowed when circuit is closed"""
        assert self.client._should_allow_request() is True

    def test_should_not_allow_request_when_open(self):
        """Test requests are blocked when circuit is open"""
        self.client._circuit_state = CircuitState.OPEN
        self.client._last_failure_time = 9999999999  # Far in future

        assert self.client._should_allow_request() is False

    def test_invalidate_cache_endpoint(self):
        """Test invalidating cache for specific endpoint"""
        self.client._set_cache("/api/nodes", {"data": "nodes"})
        self.client._set_cache("/api/actors", {"data": "actors"})
        self.client._set_cache("/other", {"data": "other"})

        self.client.invalidate_cache("/api/")

        assert "/api/nodes" not in self.client._cache
        assert "/api/actors" not in self.client._cache
        assert "/other" in self.client._cache  # Different endpoint preserved

    def test_invalidate_all_cache(self):
        """Test invalidating all cache"""
        self.client._set_cache("/api/nodes", {"data": "nodes"})
        self.client._set_cache("/api/actors", {"data": "actors"})

        self.client.invalidate_cache()

        assert len(self.client._cache) == 0

    def test_get_cache_stats(self):
        """Test getting cache statistics"""
        self.client._set_cache("/key1", {"data": 1})
        self.client._set_cache("/key2", {"data": 2})

        stats = self.client.get_cache_stats()

        assert stats["size"] == 2
        assert stats["max_size"] == 100

    def test_make_request_returns_circuit_breaker_error(self):
        """Test that requests return error when circuit is open"""
        self.client._circuit_state = CircuitState.OPEN
        self.client._last_failure_time = 9999999999

        response = self.client._make_request("GET", "/api/nodes")

        assert response.success is False
        assert "Circuit breaker" in response.error

    @patch('requests.request')
    def test_make_request_success(self, mock_request):
        """Test successful request"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"nodes": []}
        mock_request.return_value = mock_response

        response = self.client._make_request("GET", "/api/nodes")

        assert response.success is True
        assert response.data == {"nodes": []}
        assert response.cached is False

    @patch('requests.request')
    def test_make_request_caches_result(self, mock_request):
        """Test that successful requests are cached"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"nodes": []}
        mock_request.return_value = mock_response

        # First request
        self.client._make_request("GET", "/api/nodes")

        # Second request should hit cache
        cached_response = self.client._make_request("GET", "/api/nodes")

        assert cached_response.cached is True
        # mock_request should only be called once
        assert mock_request.call_count == 1

    @patch('requests.request')
    def test_make_request_retries_on_timeout(self, mock_request):
        """Test that requests retry on timeout"""
        import requests
        mock_request.side_effect = [
            requests.exceptions.Timeout("timeout"),
            requests.exceptions.Timeout("timeout"),
            MagicMock(status_code=200, json=lambda: {"data": "ok"})
        ]

        response = self.client._make_request("GET", "/api/nodes")

        assert response.success is True
        assert mock_request.call_count == 3

    @patch('requests.request')
    def test_make_request_returns_error_on_connection_error(self, mock_request):
        """Test that connection errors are handled"""
        import requests
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection refused")

        response = self.client._make_request("GET", "/api/nodes")

        assert response.success is False
        assert "Connection error" in response.error

    @patch('requests.request')
    def test_health_check(self, mock_request):
        """Test health check method"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_request.return_value = mock_response

        response = self.client.health_check()

        assert response.success is True
        mock_request.assert_called_once()

    @patch('requests.request')
    def test_list_nodes(self, mock_request):
        """Test list nodes method"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"nodes": [{"node_id": "1"}]}
        mock_request.return_value = mock_response

        response = self.client.list_nodes()

        assert response.success is True
        assert len(response.data["nodes"]) == 1

    @patch('requests.request')
    def test_list_actors(self, mock_request):
        """Test list actors method"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"actors": []}
        mock_request.return_value = mock_response

        response = self.client.list_actors(limit=50)

        assert response.success is True
        mock_request.assert_called_once()

    def test_close_clears_cache(self):
        """Test close method clears cache"""
        self.client._set_cache("/key", {"data": "value"})
        assert len(self.client._cache) > 0

        self.client.close()

        assert len(self.client._cache) == 0


class TestRayAPIResponse:
    """Test suite for RayAPIResponse dataclass"""

    def test_success_response(self):
        """Test successful response"""
        response = RayAPIResponse(
            success=True,
            data={"key": "value"}
        )

        assert response.success is True
        assert response.data == {"key": "value"}
        assert response.error is None
        assert response.cached is False

    def test_error_response(self):
        """Test error response"""
        response = RayAPIResponse(
            success=False,
            data=None,
            error="Something went wrong"
        )

        assert response.success is False
        assert response.data is None
        assert response.error == "Something went wrong"

    def test_cached_response(self):
        """Test cached response"""
        response = RayAPIResponse(
            success=True,
            data={"cached": True},
            cached=True
        )

        assert response.cached is True
