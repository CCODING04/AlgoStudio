# tests/unit/core/test_ray_client.py
"""Unit tests for core/ray_client.py module."""

import socket

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from algo_studio.core.ray_client import RayClient, NodeStatus


class TestNodeStatus:
    """Tests for NodeStatus dataclass."""

    def test_node_status_creation(self):
        """Test NodeStatus creation with required fields."""
        node = NodeStatus(
            node_id="node-001",
            ip="192.168.0.115",
            status="idle",
            cpu_used=2,
            cpu_total=8,
            gpu_used=0,
            gpu_total=1,
            memory_used_gb=16.0,
            memory_total_gb=32.0,
            disk_used_gb=100.0,
            disk_total_gb=500.0,
        )
        assert node.node_id == "node-001"
        assert node.ip == "192.168.0.115"
        assert node.status == "idle"
        assert node.cpu_available == 6
        assert node.gpu_available == 1
        assert node.memory_available_gb == 16.0

    def test_node_status_cpu_available(self):
        """Test cpu_available property calculation."""
        node = NodeStatus(
            node_id="node-001",
            ip="192.168.0.115",
            status="busy",
            cpu_used=4,
            cpu_total=8,
            gpu_used=1,
            gpu_total=1,
            memory_used_gb=24.0,
            memory_total_gb=32.0,
            disk_used_gb=200.0,
            disk_total_gb=500.0,
        )
        assert node.cpu_available == 4

    def test_node_status_gpu_available(self):
        """Test gpu_available property when all GPUs used."""
        node = NodeStatus(
            node_id="node-001",
            ip="192.168.0.115",
            status="busy",
            cpu_used=8,
            cpu_total=8,
            gpu_used=1,
            gpu_total=1,
            memory_used_gb=32.0,
            memory_total_gb=32.0,
            disk_used_gb=500.0,
            disk_total_gb=500.0,
        )
        assert node.gpu_available == 0

    def test_node_status_memory_available(self):
        """Test memory_available_gb property calculation."""
        node = NodeStatus(
            node_id="node-001",
            ip="192.168.0.115",
            status="idle",
            cpu_used=0,
            cpu_total=8,
            gpu_used=0,
            gpu_total=1,
            memory_used_gb=8.0,
            memory_total_gb=32.0,
            disk_used_gb=50.0,
            disk_total_gb=500.0,
        )
        assert node.memory_available_gb == 24.0

    def test_node_status_optional_fields(self):
        """Test NodeStatus with optional fields populated."""
        node = NodeStatus(
            node_id="node-001",
            ip="192.168.0.115",
            status="idle",
            cpu_used=2,
            cpu_total=8,
            gpu_used=0,
            gpu_total=1,
            memory_used_gb=16.0,
            memory_total_gb=32.0,
            disk_used_gb=100.0,
            disk_total_gb=500.0,
            swap_used_gb=1.0,
            swap_total_gb=8.0,
            cpu_model="Intel Xeon",
            cpu_physical_cores=4,
            cpu_freq_current_mhz=3500.0,
            gpu_utilization=45,
            gpu_memory_used_gb=8.0,
            gpu_memory_total_gb=24.0,
            gpu_name="NVIDIA RTX 4090",
            hostname="worker-1",
        )
        assert node.cpu_model == "Intel Xeon"
        assert node.gpu_utilization == 45
        assert node.gpu_name == "NVIDIA RTX 4090"
        assert node.hostname == "worker-1"


class TestRayClient:
    """Tests for RayClient class."""

    def test_ray_client_initialization_default(self):
        """Test RayClient initialization with defaults."""
        client = RayClient()
        assert client.head_address is None
        assert client._ray_initialized is False
        assert client._ray_available is False
        assert client._cache_ttl == 5.0
        assert client._nodes_cache is None

    def test_ray_client_initialization_with_address(self):
        """Test RayClient initialization with head address."""
        client = RayClient(head_address="192.168.0.126:6379", cache_ttl=10.0)
        assert client.head_address == "192.168.0.126:6379"
        assert client._cache_ttl == 10.0

    def test_ray_client_check_ray_available_socket_failure(self):
        """Test _check_ray_available returns False when socket fails."""
        client = RayClient(head_address="192.168.0.126:6379")

        with patch('socket.socket') as mock_socket:
            mock_sock_instance = MagicMock()
            mock_sock_instance.connect_ex.return_value = 1  # Connection refused
            mock_socket.return_value = mock_sock_instance

            result = client._check_ray_available()
            assert result is False
            mock_sock_instance.connect_ex.assert_called_once()
            mock_sock_instance.close.assert_called_once()

    def test_ray_client_check_ray_available_socket_success(self):
        """Test _check_ray_available returns True when socket connects."""
        client = RayClient(head_address="192.168.0.126:6379")

        with patch('socket.socket') as mock_socket:
            mock_sock_instance = MagicMock()
            mock_sock_instance.connect_ex.return_value = 0  # Success
            mock_socket.return_value = mock_sock_instance

            result = client._check_ray_available()
            assert result is True
            mock_sock_instance.connect_ex.assert_called_once()
            mock_sock_instance.close.assert_called_once()

    def test_ray_client_check_ray_available_socket_exception(self):
        """Test _check_ray_available returns False on socket exception."""
        client = RayClient(head_address="192.168.0.126:6379")

        with patch('socket.socket') as mock_socket:
            mock_socket.side_effect = socket.error("Network unreachable")

            result = client._check_ray_available()
            assert result is False

    def test_ray_client_ensure_ray_init_not_available(self):
        """Test _ensure_ray_init skips when head not reachable."""
        client = RayClient(head_address="192.168.0.126:6379")

        with patch.object(client, '_check_ray_available', return_value=False):
            client._ensure_ray_init()

            assert client._ray_initialized is True
            assert client._ray_available is False

    def test_ray_client_clear_cache(self):
        """Test clear_cache method."""
        client = RayClient()

        # Set up cache
        with client._cache_lock:
            client._nodes_cache = (12345.0, [])

        client.clear_cache()

        with client._cache_lock:
            assert client._nodes_cache is None

    def test_ray_client_shutdown(self):
        """Test shutdown method."""
        client = RayClient()
        client._ray_initialized = True

        with patch('ray.shutdown'):
            client.shutdown()

        assert client._ray_initialized is False


class TestRayClientSubmitTask:
    """Tests for RayClient.submit_task method."""

    def test_submit_task_without_ray_init(self):
        """Test submit_task works even when Ray is not initialized (lazy init)."""
        client = RayClient(head_address="192.168.0.126:6379")

        # Mock _ensure_ray_init to do nothing (simulates unavailable Ray)
        with patch.object(client, '_ensure_ray_init'):
            mock_func = MagicMock()
            mock_func.options.return_value.remote = MagicMock(return_value="task-ref")

            result = client.submit_task(mock_func, "arg1", num_gpus=1)

            # Result is what the mocked remote returns
            assert result == "task-ref"

    def test_submit_task_with_node_ip(self):
        """Test submit_task with node_ip adds node affinity."""
        client = RayClient(head_address="192.168.0.126:6379")

        with patch.object(client, '_ensure_ray_init'):
            mock_func = MagicMock()
            mock_options = MagicMock()
            mock_options.remote.return_value = "task-ref"
            mock_func.options.return_value = mock_options

            result = client.submit_task(mock_func, "arg1", node_ip="192.168.0.115")

            # Verify options was called with node affinity
            call_kwargs = mock_func.options.call_args.kwargs
            assert "resources" in call_kwargs
            assert "node:192.168.0.115" in call_kwargs["resources"]

    def test_submit_task_with_custom_resources(self):
        """Test submit_task with custom resources."""
        client = RayClient(head_address="192.168.0.126:6379")

        with patch.object(client, '_ensure_ray_init'):
            mock_func = MagicMock()
            mock_options = MagicMock()
            mock_options.remote.return_value = "task-ref"
            mock_func.options.return_value = mock_options

            custom_resources = {"custom-resource": 1.0}
            result = client.submit_task(mock_func, "arg1", resources=custom_resources)

            call_kwargs = mock_func.options.call_args.kwargs
            assert call_kwargs["resources"] == custom_resources


class TestRayClientGetNodes:
    """Tests for RayClient.get_nodes method behavior with caching."""

    def test_get_nodes_returns_cached(self):
        """Test get_nodes returns cached result within TTL."""
        client = RayClient(cache_ttl=10.0)

        cached_nodes = [
            NodeStatus(
                node_id="node-001",
                ip="192.168.0.115",
                status="idle",
                cpu_used=0,
                cpu_total=8,
                gpu_used=0,
                gpu_total=1,
                memory_used_gb=16.0,
                memory_total_gb=32.0,
                disk_used_gb=100.0,
                disk_total_gb=500.0,
            )
        ]

        import time
        with client._cache_lock:
            client._nodes_cache = (time.time() - 1, cached_nodes)  # 1 second ago

        with patch.object(client, '_ensure_ray_init'):
            with patch('ray.nodes', return_value=[]):
                result = client.get_nodes()

        assert result == cached_nodes

    def test_get_nodes_raises_when_ray_unavailable(self):
        """Test get_nodes raises RuntimeError when Ray is not available."""
        client = RayClient()
        client._ray_initialized = True
        client._ray_available = False

        with pytest.raises(RuntimeError, match="Ray is not available"):
            client.get_nodes()
