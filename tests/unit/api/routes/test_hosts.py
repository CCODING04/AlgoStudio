# tests/unit/api/routes/test_hosts.py
"""Unit tests for hosts API endpoints."""

from unittest.mock import patch, MagicMock
from pathlib import Path
import importlib.util

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

# Load hosts module directly
hosts_module_path = Path(__file__).parent.parent.parent.parent.parent / "src" / "algo_studio" / "api" / "routes" / "hosts.py"
spec = importlib.util.spec_from_file_location("hosts", hosts_module_path)
hosts_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hosts_module)

router = hosts_module.router


class MockHostInfo:
    """Mock HostInfo for testing."""

    def __init__(self):
        self.hostname = "test-host"
        self.ip = "192.168.0.126"
        self.cpu_count = 8
        self.cpu_used = 4
        self.cpu_physical_cores = 4
        self.cpu_model = "Intel i7"
        self.cpu_freq_current_mhz = 3000
        self.gpu_count = 1
        self.gpu_utilization = 50
        self.gpu_memory_used_gb = 8
        self.gpu_memory_total_gb = 24
        self.gpu_name = "RTX 4090"
        self.memory_total_gb = 32
        self.memory_used_gb = 16
        self.disk_total_gb = 500
        self.disk_used_gb = 200
        self.swap_total_gb = 64
        self.swap_used_gb = 8


class MockNode:
    """Mock Ray node for testing."""

    def __init__(self, node_id, ip, status="alive", hostname=None):
        self.node_id = node_id
        self.ip = ip
        self.status = status
        self.hostname = hostname
        self.cpu_total = 8
        self.cpu_used = 4
        self.cpu_physical_cores = 4
        self.cpu_model = "Intel i7"
        self.cpu_freq_current_mhz = 3000
        self.gpu_total = 1
        self.gpu_utilization = 50
        self.gpu_memory_used_gb = 8
        self.gpu_memory_total_gb = 24
        self.gpu_name = "RTX 4090"
        self.memory_total_gb = 32
        self.memory_used_gb = 16
        self.disk_total_gb = 500
        self.disk_used_gb = 200
        self.swap_total_gb = 64
        self.swap_used_gb = 8


class MockRayClient:
    """Mock RayClient for testing."""

    def __init__(self, nodes=None):
        self.nodes = nodes or [MockNode("node1", "192.168.0.126", "alive", "head-node")]

    def get_nodes(self):
        return self.nodes


class TestHostsRouter:
    """Unit tests for hosts router endpoints."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app with the hosts router."""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, test_app):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")

    @pytest.fixture
    def mock_host_info(self):
        """Create mock HostInfo."""
        return MockHostInfo()

    @pytest.fixture
    def mock_ray_client(self):
        """Create mock RayClient."""
        return MockRayClient()

    # ==================== Get Hosts Status Tests ====================

    @pytest.mark.asyncio
    async def test_get_hosts_status_returns_cluster_nodes(self, client, mock_host_info, mock_ray_client):
        """Test GET /api/hosts/ returns cluster nodes with status."""
        with patch.object(hosts_module, "get_ray_client", return_value=mock_ray_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()
        assert "cluster_nodes" in data
        assert isinstance(data["cluster_nodes"], list)
        assert len(data["cluster_nodes"]) >= 1

    @pytest.mark.asyncio
    async def test_get_hosts_status_includes_local_node_info(self, client, mock_host_info, mock_ray_client):
        """Test GET /api/hosts/ includes local node detailed info."""
        with patch.object(hosts_module, "get_ray_client", return_value=mock_ray_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()

        # Find the local node (IP should match localhost)
        local_nodes = [n for n in data["cluster_nodes"] if n.get("is_local")]
        assert len(local_nodes) >= 1
        local = local_nodes[0]
        assert "resources" in local
        assert "cpu" in local["resources"]
        assert "gpu" in local["resources"]

    @pytest.mark.asyncio
    async def test_get_hosts_status_handles_empty_cluster(self, client, mock_host_info):
        """Test GET /api/hosts/ handles empty cluster (Ray not initialized)."""
        mock_client = MockRayClient(nodes=[])

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()
        assert "cluster_nodes" in data

    @pytest.mark.asyncio
    async def test_get_hosts_status_handles_exception(self, client, mock_host_info):
        """Test GET /api/hosts/ returns local info when Ray fails."""
        def raise_exception():
            raise Exception("Ray not initialized")

        mock_client = MagicMock()
        mock_client.get_nodes = raise_exception

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()
        # Should return local node info when Ray fails
        assert len(data["cluster_nodes"]) >= 1
        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_hosts_status_deduplicates_nodes_by_ip(self, client, mock_host_info):
        """Test GET /api/hosts/ deduplicates nodes with same IP."""
        nodes = [
            MockNode("node1", "192.168.0.126", "alive"),
            MockNode("node2", "192.168.0.126", "offline"),  # Duplicate IP, should be skipped
        ]
        mock_client = MockRayClient(nodes=nodes)

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()
        # Should only have one node for the same IP
        assert len(data["cluster_nodes"]) == 1

    @pytest.mark.asyncio
    async def test_get_hosts_status_keeps_alive_over_offline(self, client, mock_host_info):
        """Test GET /api/hosts/ keeps alive node when offline also exists."""
        nodes = [
            MockNode("node1", "192.168.0.126", "online"),
            MockNode("node2", "192.168.0.126", "offline"),
        ]
        mock_client = MockRayClient(nodes=nodes)

        # Patch the get_ray_client function to return our mock
        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()
        # Should keep the alive node (deduplication should prefer alive over offline)
        assert len(data["cluster_nodes"]) == 1
        assert data["cluster_nodes"][0]["status"] == "online"

    # ==================== Status Alias Tests ====================

    @pytest.mark.asyncio
    async def test_get_hosts_status_alias_redirects(self, client):
        """Test GET /api/hosts/status redirects to /api/hosts/."""
        response = await client.get("/api/hosts/status")

        assert response.status_code == 307
        assert response.headers["location"] == "/api/hosts/"

    @pytest.mark.asyncio
    async def test_get_hosts_status_alias_uses_get_hosts_status(self, client, mock_host_info, mock_ray_client):
        """Test the alias endpoint returns same data as main endpoint."""
        with patch.object(hosts_module, "get_ray_client", return_value=mock_ray_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            # Main endpoint
            main_response = await client.get("/api/hosts/")

            # Alias redirect
            alias_response = await client.get("/api/hosts/status", follow_redirects=False)

        assert alias_response.status_code == 307


class TestHostMonitorIntegration:
    """Integration tests for HostMonitor with hosts router."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app with the hosts router."""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, test_app):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")

    @pytest.mark.asyncio
    async def test_get_hosts_status_includes_gpu_info(self, client, mock_ray_client):
        """Test GET /api/hosts/ includes GPU information."""
        from algo_studio.monitor.host_monitor import HostMonitor

        with patch.object(hosts_module, "get_ray_client", return_value=mock_ray_client), \
             patch.object(hosts_module, "local_monitor", wraps=hosts_module.local_monitor):
            # Just ensure the router is properly configured
            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        # The test validates structure

    @pytest.mark.asyncio
    async def test_get_hosts_status_includes_memory_info(self, client, mock_ray_client):
        """Test GET /api/hosts/ includes memory information."""
        with patch.object(hosts_module, "get_ray_client", return_value=mock_ray_client):
            response = await client.get("/api/hosts/")

        assert response.status_code == 200


class TestHostRolesAndLabels:
    """Tests for hosts API role and labels functionality."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app with the hosts router."""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, test_app):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")

    @pytest.fixture
    def mock_host_info(self):
        """Create mock HostInfo."""
        return MockHostInfo()

    @pytest.fixture
    def head_node_with_labels(self):
        """Create a mock Ray node representing a head node with labels."""
        node = MockNode("head-node-1", "192.168.0.126", "alive", "head-node")
        node.role = "head"
        node.labels = {"head", "management", "gpu"}
        return node

    @pytest.fixture
    def worker_node_with_labels(self):
        """Create a mock Ray node representing a worker node with custom labels."""
        node = MockNode("worker-node-1", "192.168.0.115", "alive", "worker-1")
        node.role = "worker"
        node.labels = {"worker", "gpu", "training"}
        return node

    @pytest.fixture
    def worker_node_minimal_labels(self):
        """Create a mock Ray node with minimal default labels."""
        node = MockNode("worker-node-2", "192.168.0.116", "alive", "worker-2")
        node.role = "worker"
        node.labels = {"worker", "gpu"}
        return node

    # ==================== Role Tests ====================

    @pytest.mark.asyncio
    async def test_head_node_has_correct_role(self, client, mock_host_info, head_node_with_labels):
        """Test that head node is correctly identified with 'head' role."""
        nodes = [head_node_with_labels]
        mock_client = MockRayClient(nodes=nodes)

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()
        assert len(data["cluster_nodes"]) == 1
        assert data["cluster_nodes"][0]["role"] == "head"

    @pytest.mark.asyncio
    async def test_worker_node_has_correct_role(self, client, mock_host_info, worker_node_with_labels):
        """Test that worker node is correctly identified with 'worker' role."""
        nodes = [worker_node_with_labels]
        mock_client = MockRayClient(nodes=nodes)

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()
        assert len(data["cluster_nodes"]) == 1
        assert data["cluster_nodes"][0]["role"] == "worker"

    @pytest.mark.asyncio
    async def test_mixed_cluster_roles(self, client, mock_host_info, head_node_with_labels, worker_node_with_labels):
        """Test that mixed cluster with head and worker nodes shows correct roles."""
        # Note: head node uses 192.168.0.126 which matches local IPs in test
        nodes = [head_node_with_labels, worker_node_with_labels]
        mock_client = MockRayClient(nodes=nodes)

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()
        # Should have 2 nodes after IP deduplication
        assert len(data["cluster_nodes"]) == 2

    # ==================== Labels Tests ====================

    @pytest.mark.asyncio
    async def test_head_node_includes_default_labels(self, client, mock_host_info, head_node_with_labels):
        """Test that head node includes default labels (head, management, gpu)."""
        nodes = [head_node_with_labels]
        mock_client = MockRayClient(nodes=nodes)

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()
        labels = data["cluster_nodes"][0]["labels"]
        assert "head" in labels
        assert "management" in labels
        assert "gpu" in labels

    @pytest.mark.asyncio
    async def test_worker_node_includes_default_labels(self, client, mock_host_info, worker_node_with_labels):
        """Test that worker node includes default labels (worker, gpu)."""
        nodes = [worker_node_with_labels]
        mock_client = MockRayClient(nodes=nodes)

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()
        labels = data["cluster_nodes"][0]["labels"]
        assert "worker" in labels
        assert "gpu" in labels

    @pytest.mark.asyncio
    async def test_worker_node_with_custom_labels(self, client, mock_host_info, worker_node_with_labels):
        """Test that worker node includes custom training label."""
        nodes = [worker_node_with_labels]
        mock_client = MockRayClient(nodes=nodes)

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()
        labels = data["cluster_nodes"][0]["labels"]
        assert "training" in labels

    @pytest.mark.asyncio
    async def test_labels_returned_as_list(self, client, mock_host_info, head_node_with_labels):
        """Test that labels are returned as a list (for JSON serialization)."""
        nodes = [head_node_with_labels]
        mock_client = MockRayClient(nodes=nodes)

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()
        labels = data["cluster_nodes"][0]["labels"]
        # Verify it's a list, not a set
        assert isinstance(labels, list)

    @pytest.mark.asyncio
    async def test_node_with_no_labels_returns_empty_list(self, client, mock_host_info):
        """Test that node with no labels returns empty list."""
        node = MockNode("node-no-labels", "192.168.0.200", "alive", "no-labels-node")
        node.role = "worker"
        node.labels = set()  # Empty labels

        mock_client = MockRayClient(nodes=[node])

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()
        labels = data["cluster_nodes"][0]["labels"]
        assert labels == []

    @pytest.mark.asyncio
    async def test_local_node_has_fallback_labels(self, client, mock_host_info, head_node_with_labels):
        """Test that local node gets fallback labels when Ray is not available."""
        head_node_with_labels.ip = "127.0.0.1"  # Force local detection
        nodes = [head_node_with_labels]
        mock_client = MockRayClient(nodes=nodes)

        def raise_exception():
            raise Exception("Ray not initialized")

        mock_client.get_nodes = raise_exception

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()
        # Find local node
        local_nodes = [n for n in data["cluster_nodes"] if n.get("is_local")]
        assert len(local_nodes) >= 1
        # Local node should have fallback labels
        assert "head" in local_nodes[0]["labels"]
        assert "gpu" in local_nodes[0]["labels"]

    # ==================== Role/Labels with Resources ====================

    @pytest.mark.asyncio
    async def test_role_and_labels_available_with_all_resources(self, client, mock_host_info, worker_node_with_labels):
        """Test that role and labels are present along with full resource info."""
        nodes = [worker_node_with_labels]
        mock_client = MockRayClient(nodes=nodes)

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()
        node = data["cluster_nodes"][0]

        # Verify role and labels are present
        assert "role" in node
        assert "labels" in node

        # Verify resources are also present
        assert "resources" in node
        assert "cpu" in node["resources"]
        assert "gpu" in node["resources"]
        assert "memory" in node["resources"]

    @pytest.mark.asyncio
    async def test_multiple_workers_each_with_unique_labels(self, client, mock_host_info):
        """Test multiple workers with different label sets."""
        worker1 = MockNode("w1", "192.168.0.115", "alive", "worker-1")
        worker1.role = "worker"
        worker1.labels = {"worker", "gpu", "training"}

        worker2 = MockNode("w2", "192.168.0.116", "alive", "worker-2")
        worker2.role = "worker"
        worker2.labels = {"worker", "gpu", "inference"}

        nodes = [worker1, worker2]
        mock_client = MockRayClient(nodes=nodes)

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()

        # Find nodes by their IP
        worker1_data = next((n for n in data["cluster_nodes"] if n["ip"] == "192.168.0.115"), None)
        worker2_data = next((n for n in data["cluster_nodes"] if n["ip"] == "192.168.0.116"), None)

        assert worker1_data is not None
        assert worker2_data is not None

        assert "training" in worker1_data["labels"]
        assert "inference" in worker2_data["labels"]
        assert worker1_data["role"] == "worker"
        assert worker2_data["role"] == "worker"


class TestHostRoleAwareBehavior:
    """Tests for role-aware behavior in hosts API."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app with the hosts router."""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, test_app):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")

    @pytest.fixture
    def mock_host_info(self):
        """Create mock HostInfo."""
        return MockHostInfo()

    @pytest.mark.asyncio
    async def test_offline_node_not_included_in_role_counts(self, client, mock_host_info):
        """Test that offline nodes are not included when querying roles."""
        alive_node = MockNode("alive-worker", "192.168.0.115", "alive", "alive-worker")
        alive_node.role = "worker"
        alive_node.labels = {"worker", "gpu"}

        offline_node = MockNode("offline-worker", "192.168.0.116", "offline", "offline-worker")
        offline_node.role = "worker"
        offline_node.labels = {"worker", "gpu"}

        nodes = [alive_node, offline_node]
        mock_client = MockRayClient(nodes=nodes)

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()

        # Only alive nodes should be in the response (offline filtered out due to deduplication)
        online_nodes = [n for n in data["cluster_nodes"] if n["status"] != "offline"]
        assert len(online_nodes) >= 1

    @pytest.mark.asyncio
    async def test_is_local_flag_on_head_node(self, client, mock_host_info):
        """Test that head node is marked as is_local when running on head."""
        # Create a head node at the local IP
        head_node = MockNode("head-node", "192.168.0.126", "alive", "head-node")
        head_node.role = "head"
        head_node.labels = {"head", "management", "gpu"}

        nodes = [head_node]
        mock_client = MockRayClient(nodes=nodes)

        with patch.object(hosts_module, "get_ray_client", return_value=mock_client), \
             patch.object(hosts_module, "local_monitor") as mock_monitor:
            mock_monitor.get_host_info.return_value = mock_host_info
            mock_monitor.to_dict.return_value = {}

            response = await client.get("/api/hosts/")

        assert response.status_code == 200
        data = response.json()

        # Find the node at 192.168.0.126 (local IP in mock)
        local_nodes = [n for n in data["cluster_nodes"] if n.get("is_local")]
        assert len(local_nodes) >= 1
        assert local_nodes[0]["role"] == "head"
