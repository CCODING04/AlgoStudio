# tests/unit/api/test_hosts_api.py
"""Unit tests for hosts API endpoints."""

import hashlib
import hmac
import os
import socket
import time
from dataclasses import dataclass
from typing import Optional
from unittest.mock import patch, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

# Set secret key for RBAC middleware BEFORE importing app
os.environ["RBAC_SECRET_KEY"] = "test-secret-key-12345"

from algo_studio.api.main import app
from algo_studio.core.ray_client import NodeStatus


def generate_valid_signature(user_id: str, timestamp: str, secret_key: str) -> str:
    """Generate a valid HMAC-SHA256 signature for testing."""
    message = f"{user_id}:{timestamp}"
    return hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()


def make_auth_headers(
    user_id: str = "test-user",
    role: str = "developer",
    secret_key: str = "test-secret-key-12345",
    timestamp: int = None,
) -> dict:
    """Generate authentication headers with valid signature."""
    if timestamp is None:
        timestamp = int(time.time())
    timestamp_str = str(timestamp)
    signature = generate_valid_signature(user_id, timestamp_str, secret_key)
    return {
        "X-User-ID": user_id,
        "X-User-Role": role,
        "X-Timestamp": timestamp_str,
        "X-Signature": signature,
    }


@dataclass
class MockHostInfo:
    """Mock HostInfo for testing."""
    hostname: str
    ip: str
    cpu_count: int = 8
    cpu_physical_cores: int = 4
    cpu_used: int = 2
    cpu_model: str = "Intel(R) Xeon(R) CPU"
    cpu_freq_current_mhz: float = 3600.0
    memory_total_gb: float = 32.0
    memory_used_gb: float = 16.0
    gpu_name: Optional[str] = "NVIDIA RTX 4090"
    gpu_count: int = 1
    gpu_utilization: int = 50
    gpu_memory_used_gb: float = 8.0
    gpu_memory_total_gb: float = 24.0
    disk_total_gb: float = 500.0
    disk_used_gb: float = 200.0
    swap_total_gb: float = 8.0
    swap_used_gb: float = 1.0


class TestHostsAPI:
    """Test suite for hosts API endpoints."""

    @pytest.fixture
    def client(self):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.fixture
    def auth_headers(self):
        """Provide valid authentication headers for developer role."""
        return make_auth_headers(user_id="test-user", role="developer")

    @pytest.mark.asyncio
    async def test_hosts_status_redirect(self, client, auth_headers):
        """Test that /api/hosts/status returns 307 redirect to /api/hosts/."""
        response = await client.get("/api/hosts/status", headers=auth_headers)
        assert response.status_code == 307
        assert response.headers["location"] == "/api/hosts/"

    @pytest.mark.asyncio
    async def test_hosts_status_redirect_follow(self, client, auth_headers):
        """Test that following the redirect from /api/hosts/status works."""
        mock_local_info = MockHostInfo(
            hostname=socket.gethostname(),
            ip="192.168.0.126",
        )

        with patch("algo_studio.api.routes.hosts.get_ray_client") as mock_get_client, \
             patch("algo_studio.api.routes.hosts.local_monitor") as mock_monitor:

            mock_client = MagicMock()
            mock_client.get_nodes.return_value = []
            mock_get_client.return_value = mock_client
            mock_monitor.get_host_info.return_value = mock_local_info

            response = await client.get("/api/hosts/status", headers=auth_headers, follow_redirects=True)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hosts_endpoint_returns_cluster_nodes(self, client, auth_headers):
        """Test that /api/hosts/ returns cluster nodes data when Ray is available."""
        mock_nodes = [
            NodeStatus(
                node_id="worker-1",
                ip="192.168.0.115",
                status="idle",
                cpu_used=2,
                cpu_total=8,
                gpu_used=0,
                gpu_total=1,
                memory_used_gb=16.0,
                memory_total_gb=32.0,
                disk_used_gb=200.0,
                disk_total_gb=500.0,
                swap_used_gb=1.0,
                swap_total_gb=8.0,
                cpu_model="Intel Xeon",
                cpu_physical_cores=4,
                cpu_freq_current_mhz=3600.0,
                gpu_utilization=0,
                gpu_memory_used_gb=0.0,
                gpu_memory_total_gb=24.0,
                gpu_name="NVIDIA RTX 4090",
                hostname="worker-node",
            ),
        ]

        mock_local_info = MockHostInfo(
            hostname=socket.gethostname(),
            ip="192.168.0.126",
        )

        with patch("algo_studio.api.routes.hosts.get_ray_client") as mock_get_client, \
             patch("algo_studio.api.routes.hosts.local_monitor") as mock_monitor:

            mock_client = MagicMock()
            mock_client.get_nodes.return_value = mock_nodes
            mock_get_client.return_value = mock_client
            mock_monitor.get_host_info.return_value = mock_local_info

            response = await client.get("/api/hosts/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "cluster_nodes" in data
        assert isinstance(data["cluster_nodes"], list)

    @pytest.mark.asyncio
    async def test_hosts_endpoint_with_multiple_nodes(self, client, auth_headers):
        """Test /api/hosts/ with multiple cluster nodes."""
        mock_nodes = [
            NodeStatus(
                node_id="head-node",
                ip="192.168.0.126",
                status="idle",
                cpu_used=1,
                cpu_total=8,
                gpu_used=0,
                gpu_total=1,
                memory_used_gb=8.0,
                memory_total_gb=32.0,
                disk_used_gb=100.0,
                disk_total_gb=500.0,
                swap_used_gb=0.5,
                swap_total_gb=8.0,
                hostname="head-node",
                cpu_model="Intel Xeon",
                cpu_physical_cores=4,
                cpu_freq_current_mhz=3600.0,
                gpu_utilization=10,
                gpu_memory_used_gb=2.0,
                gpu_memory_total_gb=24.0,
                gpu_name="NVIDIA RTX 4090",
            ),
            NodeStatus(
                node_id="worker-1",
                ip="192.168.0.115",
                status="busy",
                cpu_used=6,
                cpu_total=8,
                gpu_used=1,
                gpu_total=1,
                memory_used_gb=28.0,
                memory_total_gb=32.0,
                disk_used_gb=400.0,
                disk_total_gb=500.0,
                swap_used_gb=2.0,
                swap_total_gb=8.0,
                hostname="worker-node",
                cpu_model="AMD Ryzen",
                cpu_physical_cores=8,
                cpu_freq_current_mhz=4000.0,
                gpu_utilization=90,
                gpu_memory_used_gb=20.0,
                gpu_memory_total_gb=24.0,
                gpu_name="NVIDIA RTX 4090",
            ),
        ]

        mock_local_info = MockHostInfo(
            hostname="head-node",
            ip="192.168.0.126",
        )

        with patch("algo_studio.api.routes.hosts.get_ray_client") as mock_get_client, \
             patch("algo_studio.api.routes.hosts.local_monitor") as mock_monitor:

            mock_client = MagicMock()
            mock_client.get_nodes.return_value = mock_nodes
            mock_get_client.return_value = mock_client
            mock_monitor.get_host_info.return_value = mock_local_info

            response = await client.get("/api/hosts/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["cluster_nodes"]) == 2

    @pytest.mark.asyncio
    async def test_hosts_endpoint_ray_unavailable_fallback(self, client, auth_headers):
        """Test /api/hosts/ returns local-only data when Ray is not initialized."""
        mock_local_info = MockHostInfo(
            hostname=socket.gethostname(),
            ip="192.168.0.126",
        )

        with patch("algo_studio.api.routes.hosts.get_ray_client") as mock_get_client, \
             patch("algo_studio.api.routes.hosts.local_monitor") as mock_monitor:

            mock_client = MagicMock()
            # Simulate Ray not being available
            mock_client.get_nodes.side_effect = RuntimeError("Ray is not available")
            mock_get_client.return_value = mock_client
            mock_monitor.get_host_info.return_value = mock_local_info
            mock_monitor.to_dict.return_value = mock_monitor.get_host_info.return_value

            response = await client.get("/api/hosts/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "cluster_nodes" in data
        # Should have error field when Ray is unavailable
        assert "error" in data
        # Should have only local node
        assert len(data["cluster_nodes"]) == 1
        assert data["cluster_nodes"][0]["node_id"] == "local"
        assert data["cluster_nodes"][0]["is_local"] is True

    @pytest.mark.asyncio
    async def test_hosts_endpoint_node_ip_matching(self, client, auth_headers):
        """Test that local node is correctly identified by IP matching."""
        local_ip = "192.168.0.126"
        mock_nodes = [
            NodeStatus(
                node_id="head-node",
                ip=local_ip,
                status="idle",
                cpu_used=1,
                cpu_total=8,
                gpu_used=0,
                gpu_total=1,
                memory_used_gb=8.0,
                memory_total_gb=32.0,
                disk_used_gb=100.0,
                disk_total_gb=500.0,
                swap_used_gb=0.5,
                swap_total_gb=8.0,
                hostname="head-node",
                cpu_model="Intel Xeon",
                cpu_physical_cores=4,
                cpu_freq_current_mhz=3600.0,
                gpu_utilization=10,
                gpu_memory_used_gb=2.0,
                gpu_memory_total_gb=24.0,
                gpu_name="NVIDIA RTX 4090",
            ),
            NodeStatus(
                node_id="worker-1",
                ip="192.168.0.115",
                status="idle",
                cpu_used=1,
                cpu_total=8,
                gpu_used=0,
                gpu_total=1,
                memory_used_gb=8.0,
                memory_total_gb=32.0,
                disk_used_gb=100.0,
                disk_total_gb=500.0,
                swap_used_gb=0.5,
                swap_total_gb=8.0,
                hostname="worker-node",
                cpu_model="AMD Ryzen",
                cpu_physical_cores=4,
                cpu_freq_current_mhz=4000.0,
                gpu_utilization=10,
                gpu_memory_used_gb=2.0,
                gpu_memory_total_gb=24.0,
                gpu_name="NVIDIA RTX 4090",
            ),
        ]

        mock_local_info = MockHostInfo(
            hostname="head-node",
            ip=local_ip,
        )

        with patch("algo_studio.api.routes.hosts.get_ray_client") as mock_get_client, \
             patch("algo_studio.api.routes.hosts.local_monitor") as mock_monitor:

            mock_client = MagicMock()
            mock_client.get_nodes.return_value = mock_nodes
            mock_get_client.return_value = mock_client
            mock_monitor.get_host_info.return_value = mock_local_info

            response = await client.get("/api/hosts/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        nodes = data["cluster_nodes"]

        # Find head node (matching IP)
        head_node = next(n for n in nodes if n["ip"] == local_ip)
        assert head_node["is_local"] is True
        assert head_node["hostname"] == "head-node"

        # Find worker node (different IP)
        worker_node = next(n for n in nodes if n["ip"] == "192.168.0.115")
        assert worker_node["is_local"] is False

    @pytest.mark.asyncio
    async def test_hosts_endpoint_node_deduplication(self, client, auth_headers):
        """Test that duplicate IP nodes are deduplicated, preferring alive nodes."""
        local_ip = "192.168.0.126"
        mock_nodes = [
            # First registration (alive)
            NodeStatus(
                node_id="head-node-1",
                ip=local_ip,
                status="idle",
                cpu_used=1,
                cpu_total=8,
                gpu_used=0,
                gpu_total=1,
                memory_used_gb=8.0,
                memory_total_gb=32.0,
                disk_used_gb=100.0,
                disk_total_gb=500.0,
                swap_used_gb=0.5,
                swap_total_gb=8.0,
                hostname="head-node",
            ),
            # Second registration (offline) - should be dropped
            NodeStatus(
                node_id="head-node-2",
                ip=local_ip,
                status="offline",
                cpu_used=0,
                cpu_total=8,
                gpu_used=0,
                gpu_total=1,
                memory_used_gb=0.0,
                memory_total_gb=32.0,
                disk_used_gb=0.0,
                disk_total_gb=500.0,
                swap_used_gb=0.0,
                swap_total_gb=8.0,
                hostname="head-node-old",
            ),
        ]

        mock_local_info = MockHostInfo(
            hostname="head-node",
            ip=local_ip,
        )

        with patch("algo_studio.api.routes.hosts.get_ray_client") as mock_get_client, \
             patch("algo_studio.api.routes.hosts.local_monitor") as mock_monitor:

            mock_client = MagicMock()
            mock_client.get_nodes.return_value = mock_nodes
            mock_get_client.return_value = mock_client
            mock_monitor.get_host_info.return_value = mock_local_info

            response = await client.get("/api/hosts/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Should only have one node (offline duplicate dropped)
        assert len(data["cluster_nodes"]) == 1
        assert data["cluster_nodes"][0]["status"] == "idle"

    @pytest.mark.asyncio
    async def test_hosts_endpoint_offline_node_retained_if_no_alive(self, client, auth_headers):
        """Test that if only offline node exists for an IP, it is retained."""
        mock_nodes = [
            NodeStatus(
                node_id="dead-node",
                ip="192.168.0.200",
                status="offline",
                cpu_used=0,
                cpu_total=8,
                gpu_used=0,
                gpu_total=1,
                memory_used_gb=0.0,
                memory_total_gb=32.0,
                disk_used_gb=0.0,
                disk_total_gb=500.0,
                swap_used_gb=0.0,
                swap_total_gb=8.0,
                hostname="dead-node",
            ),
        ]

        mock_local_info = MockHostInfo(
            hostname=socket.gethostname(),
            ip="192.168.0.126",
        )

        with patch("algo_studio.api.routes.hosts.get_ray_client") as mock_get_client, \
             patch("algo_studio.api.routes.hosts.local_monitor") as mock_monitor:

            mock_client = MagicMock()
            mock_client.get_nodes.return_value = mock_nodes
            mock_get_client.return_value = mock_client
            mock_monitor.get_host_info.return_value = mock_local_info

            response = await client.get("/api/hosts/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Offline node should be retained since no alive node exists for that IP
        assert len(data["cluster_nodes"]) == 1


class TestHostsAPIResponseFormat:
    """Tests for API response format validation."""

    @pytest.fixture
    def client(self):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.fixture
    def auth_headers(self):
        """Provide valid authentication headers for developer role."""
        return make_auth_headers(user_id="test-user", role="developer")

    @pytest.mark.asyncio
    async def test_response_has_required_fields(self, client, auth_headers):
        """Test that response contains all required fields."""
        mock_local_info = MockHostInfo(
            hostname=socket.gethostname(),
            ip="192.168.0.126",
        )

        with patch("algo_studio.api.routes.hosts.get_ray_client") as mock_get_client, \
             patch("algo_studio.api.routes.hosts.local_monitor") as mock_monitor:

            mock_client = MagicMock()
            mock_client.get_nodes.side_effect = RuntimeError("Ray not available")
            mock_get_client.return_value = mock_client
            mock_monitor.get_host_info.return_value = mock_local_info
            mock_monitor.to_dict.return_value = mock_monitor.get_host_info.return_value

            response = await client.get("/api/hosts/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "cluster_nodes" in data
        assert isinstance(data["cluster_nodes"], list)
        assert len(data["cluster_nodes"]) == 1

        node = data["cluster_nodes"][0]
        required_fields = ["node_id", "ip", "status", "is_local", "hostname", "resources"]
        for field in required_fields:
            assert field in node, f"Missing field: {field}"

        resources = node["resources"]
        resource_fields = ["cpu", "gpu", "memory", "disk", "swap"]
        for field in resource_fields:
            assert field in resources, f"Missing resource field: {field}"

    @pytest.mark.asyncio
    async def test_cpu_resource_fields(self, client, auth_headers):
        """Test that CPU resource contains expected fields."""
        mock_local_info = MockHostInfo(
            hostname=socket.gethostname(),
            ip="192.168.0.126",
        )

        with patch("algo_studio.api.routes.hosts.get_ray_client") as mock_get_client, \
             patch("algo_studio.api.routes.hosts.local_monitor") as mock_monitor:

            mock_client = MagicMock()
            mock_client.get_nodes.side_effect = RuntimeError("Ray not available")
            mock_get_client.return_value = mock_client
            mock_monitor.get_host_info.return_value = mock_local_info
            mock_monitor.to_dict.return_value = mock_monitor.get_host_info.return_value

            response = await client.get("/api/hosts/", headers=auth_headers)

        data = response.json()
        cpu = data["cluster_nodes"][0]["resources"]["cpu"]
        cpu_fields = ["total", "used", "physical_cores", "model", "freq_mhz"]
        for field in cpu_fields:
            assert field in cpu, f"Missing CPU field: {field}"

    @pytest.mark.asyncio
    async def test_gpu_resource_fields(self, client, auth_headers):
        """Test that GPU resource contains expected fields."""
        mock_local_info = MockHostInfo(
            hostname=socket.gethostname(),
            ip="192.168.0.126",
        )

        with patch("algo_studio.api.routes.hosts.get_ray_client") as mock_get_client, \
             patch("algo_studio.api.routes.hosts.local_monitor") as mock_monitor:

            mock_client = MagicMock()
            mock_client.get_nodes.side_effect = RuntimeError("Ray not available")
            mock_get_client.return_value = mock_client
            mock_monitor.get_host_info.return_value = mock_local_info
            mock_monitor.to_dict.return_value = mock_monitor.get_host_info.return_value

            response = await client.get("/api/hosts/", headers=auth_headers)

        data = response.json()
        gpu = data["cluster_nodes"][0]["resources"]["gpu"]
        gpu_fields = ["total", "utilization", "memory_used", "memory_total", "name"]
        for field in gpu_fields:
            assert field in gpu, f"Missing GPU field: {field}"


class TestHostsAPIRBAC:
    """Tests for RBAC authentication on Hosts API.

    Note: /api/hosts and /api/hosts/status are public routes (no auth required).
    This is intentional as host status information is considered non-sensitive.
    """

    @pytest.fixture
    def client(self):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.asyncio
    async def test_hosts_api_allows_request_without_auth_header(self, client):
        """Test that /api/hosts/ allows requests without X-User-ID header (public route)."""
        mock_local_info = MockHostInfo(
            hostname=socket.gethostname(),
            ip="192.168.0.126",
        )

        with patch("algo_studio.api.routes.hosts.get_ray_client") as mock_get_client, \
             patch("algo_studio.api.routes.hosts.local_monitor") as mock_monitor:

            mock_client = MagicMock()
            mock_client.get_nodes.side_effect = RuntimeError("Ray not available")
            mock_get_client.return_value = mock_client
            mock_monitor.get_host_info.return_value = mock_local_info
            mock_monitor.to_dict.return_value = mock_monitor.get_host_info.return_value

            response = await client.get("/api/hosts/")

        # Public route - should not require auth
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hosts_api_works_with_auth_header(self, client):
        """Test that /api/hosts/ works with valid authentication headers."""
        auth_headers = make_auth_headers(user_id="test-user", role="developer")

        mock_local_info = MockHostInfo(
            hostname=socket.gethostname(),
            ip="192.168.0.126",
        )

        with patch("algo_studio.api.routes.hosts.get_ray_client") as mock_get_client, \
             patch("algo_studio.api.routes.hosts.local_monitor") as mock_monitor:

            mock_client = MagicMock()
            mock_client.get_nodes.side_effect = RuntimeError("Ray not available")
            mock_get_client.return_value = mock_client
            mock_monitor.get_host_info.return_value = mock_local_info
            mock_monitor.to_dict.return_value = mock_monitor.get_host_info.return_value

            response = await client.get("/api/hosts/", headers=auth_headers)

        # Should work with auth too
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hosts_status_endpoint_allows_without_auth(self, client):
        """Test that /api/hosts/status allows requests without auth (public route)."""
        response = await client.get("/api/hosts/status")
        # Public route - returns redirect, not 401
        assert response.status_code == 307


class TestHostsAPIViewerAccess:
    """Tests for viewer role access to hosts API."""

    @pytest.fixture
    def client(self):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.asyncio
    async def test_viewer_can_read_hosts(self, client):
        """Test that viewer role can read hosts API (has task.read permission)."""
        viewer_headers = make_auth_headers(user_id="viewer-user", role="viewer")

        mock_local_info = MockHostInfo(
            hostname=socket.gethostname(),
            ip="192.168.0.126",
        )

        with patch("algo_studio.api.routes.hosts.get_ray_client") as mock_get_client, \
             patch("algo_studio.api.routes.hosts.local_monitor") as mock_monitor:

            mock_client = MagicMock()
            mock_client.get_nodes.side_effect = RuntimeError("Ray not available")
            mock_get_client.return_value = mock_client
            mock_monitor.get_host_info.return_value = mock_local_info
            mock_monitor.to_dict.return_value = mock_monitor.get_host_info.return_value

            response = await client.get("/api/hosts/", headers=viewer_headers)

        # Viewer can read (task.read permission)
        assert response.status_code == 200
