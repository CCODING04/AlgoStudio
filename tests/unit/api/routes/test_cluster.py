# tests/unit/api/routes/test_cluster.py
"""Unit tests for cluster API endpoints."""

from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
import importlib.util

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

# Load cluster module directly
cluster_module_path = Path(__file__).parent.parent.parent.parent.parent / "src" / "algo_studio" / "api" / "routes" / "cluster.py"
spec = importlib.util.spec_from_file_location("cluster", cluster_module_path)
cluster_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cluster_module)

router = cluster_module.router
get_ray_client = cluster_module.get_ray_client


class MockRayAPIClient:
    """Mock RayAPIClient for testing."""

    def __init__(self, **kwargs):
        self.health_resp = MagicMock()
        self.health_resp.success = True
        self.health_resp.error = None

    def health_check(self):
        return self.health_resp

    def get_cluster_status(self):
        mock_resp = MagicMock()
        mock_resp.success = True
        mock_resp.data = {"cluster_name": "test"}
        return mock_resp

    def list_nodes(self):
        mock_resp = MagicMock()
        mock_resp.success = True
        mock_resp.data = {
            "nodes": [
                {
                    "node_id": "node1",
                    "ip": "192.168.0.126",
                    "hostname": "head-node",
                    "status": "alive",
                    "resources": {"CPU": 8, "GPU": 1}
                }
            ]
        }
        return mock_resp

    def get_node(self, node_id):
        mock_resp = MagicMock()
        mock_resp.success = True
        mock_resp.data = {
            "node_id": node_id,
            "ip": "192.168.0.126",
            "hostname": "head-node",
            "status": "alive",
            "resources": {"CPU": 8, "GPU": 1}
        }
        return mock_resp

    def list_actors(self, limit=100):
        mock_resp = MagicMock()
        mock_resp.success = True
        mock_resp.data = {"actors": [{"actor_id": "a1", "class_name": "Test"}]}
        return mock_resp

    def get_actor(self, actor_id):
        mock_resp = MagicMock()
        mock_resp.success = True
        mock_resp.data = {
            "actor_id": actor_id,
            "class_name": "TestActor",
            "state": "ALIVE"
        }
        return mock_resp

    def list_tasks(self, limit=100):
        mock_resp = MagicMock()
        mock_resp.success = True
        mock_resp.data = {"tasks": [{"task_id": "t1", "func_name": "test"}]}
        return mock_resp

    def list_jobs(self):
        mock_resp = MagicMock()
        mock_resp.success = True
        mock_resp.data = {"jobs": []}
        return mock_resp

    def get_circuit_state(self):
        return "closed"

    def get_cache_stats(self):
        return {"hits": 10, "misses": 5}

    def invalidate_cache(self, endpoint=None):
        pass


class TestClusterRouter:
    """Unit tests for cluster router endpoints."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app with the cluster router."""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, test_app):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")

    @pytest.fixture
    def mock_client(self):
        """Create mock RayAPIClient."""
        return MockRayAPIClient()

    # ==================== Cluster Status Tests ====================

    @pytest.mark.asyncio
    async def test_get_cluster_status_returns_connected_state(self, client, mock_client):
        """Test GET /api/cluster/status returns connected cluster state."""
        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert "nodes" in data
        assert "actors_count" in data
        assert "tasks_count" in data
        assert data["ray_version"] is not None

    @pytest.mark.asyncio
    async def test_get_cluster_status_handles_health_exception(self, client, mock_client):
        """Test GET /api/cluster/status handles health check exception."""
        mock_client.health_resp.success = False
        mock_client.health_resp.error = "Connection refused"

        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_cluster_status_handles_exception_as_error(self, client, mock_client):
        """Test GET /api/cluster/status returns error when health throws exception."""
        mock_client.health_resp = Exception("Connection refused")

        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert "Failed to connect" in data["error"]

    @pytest.mark.asyncio
    async def test_get_cluster_status_parses_nodes_correctly(self, client, mock_client):
        """Test GET /api/cluster/status correctly parses node data."""
        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/status")

        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) == 1
        node = data["nodes"][0]
        assert node["node_id"] == "node1"
        assert node["ip"] == "192.168.0.126"
        assert node["gpu_count"] == 1

    # ==================== List Nodes Tests ====================

    @pytest.mark.asyncio
    async def test_list_nodes_returns_node_list(self, client, mock_client):
        """Test GET /api/cluster/nodes returns node list."""
        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/nodes")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["node_id"] == "node1"

    @pytest.mark.asyncio
    async def test_list_nodes_handles_failure(self, client, mock_client):
        """Test GET /api/cluster/nodes handles client failure."""
        mock_client.list_nodes = MagicMock(return_value=MagicMock(success=False, error="Failed"))

        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/nodes")

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_list_nodes_returns_empty_on_invalid_data(self, client, mock_client):
        """Test GET /api/cluster/nodes handles invalid data format."""
        mock_client.list_nodes = MagicMock(return_value=MagicMock(success=True, data={}))

        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/nodes")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    # ==================== Node Detail Tests ====================

    @pytest.mark.asyncio
    async def test_get_node_detail_returns_node_info(self, client, mock_client):
        """Test GET /api/cluster/nodes/{node_id} returns node detail."""
        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/nodes/node1")

        assert response.status_code == 200
        data = response.json()
        assert data["node_id"] == "node1"
        assert data["ip"] == "192.168.0.126"
        assert "resources" in data

    @pytest.mark.asyncio
    async def test_get_node_detail_handles_not_found(self, client, mock_client):
        """Test GET /api/cluster/nodes/{node_id} returns 404 when not found."""
        mock_client.get_node = MagicMock(return_value=MagicMock(success=False, error="Not found"))

        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/nodes/nonexistent")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_node_detail_handles_invalid_response(self, client, mock_client):
        """Test GET /api/cluster/nodes/{node_id} handles invalid response."""
        mock_client.get_node = MagicMock(return_value=MagicMock(success=True, data="invalid"))

        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/nodes/node1")

        assert response.status_code == 500

    # ==================== List Actors Tests ====================

    @pytest.mark.asyncio
    async def test_list_actors_returns_actor_list(self, client, mock_client):
        """Test GET /api/cluster/actors returns actor list."""
        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/actors")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["actor_id"] == "a1"

    @pytest.mark.asyncio
    async def test_list_actors_respects_limit(self, client, mock_client):
        """Test GET /api/cluster/actors respects limit parameter."""
        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/actors?limit=50")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_actors_handles_failure(self, client, mock_client):
        """Test GET /api/cluster/actors handles client failure."""
        mock_client.list_actors = MagicMock(return_value=MagicMock(success=False, error="Failed"))

        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/actors")

        assert response.status_code == 503

    # ==================== Actor Detail Tests ====================

    @pytest.mark.asyncio
    async def test_get_actor_detail_returns_actor_info(self, client, mock_client):
        """Test GET /api/cluster/actors/{actor_id} returns actor detail."""
        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/actors/a1")

        assert response.status_code == 200
        data = response.json()
        assert data["actor_id"] == "a1"
        assert data["class_name"] == "TestActor"

    @pytest.mark.asyncio
    async def test_get_actor_detail_handles_not_found(self, client, mock_client):
        """Test GET /api/cluster/actors/{actor_id} returns 404 when not found."""
        mock_client.get_actor = MagicMock(return_value=MagicMock(success=False, error="Not found"))

        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/actors/nonexistent")

        assert response.status_code == 404

    # ==================== List Tasks Tests ====================

    @pytest.mark.asyncio
    async def test_list_tasks_returns_task_list(self, client, mock_client):
        """Test GET /api/cluster/tasks returns task list."""
        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/tasks")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_list_tasks_handles_failure(self, client, mock_client):
        """Test GET /api/cluster/tasks handles client failure."""
        mock_client.list_tasks = MagicMock(return_value=MagicMock(success=False, error="Failed"))

        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/tasks")

        assert response.status_code == 503

    # ==================== List Jobs Tests ====================

    @pytest.mark.asyncio
    async def test_list_jobs_returns_job_list(self, client, mock_client):
        """Test GET /api/cluster/jobs returns job list."""
        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/jobs")

        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data

    @pytest.mark.asyncio
    async def test_list_jobs_handles_failure(self, client, mock_client):
        """Test GET /api/cluster/jobs handles client failure."""
        mock_client.list_jobs = MagicMock(return_value=MagicMock(success=False, error="Failed"))

        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/jobs")

        assert response.status_code == 503

    # ==================== Health Check Tests ====================

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy_status(self, client, mock_client):
        """Test GET /api/cluster/health returns healthy status."""
        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["ray_dashboard"] is True
        assert data["gcs"] is True
        assert data["circuit_breaker"] == "closed"
        assert "cache_stats" in data

    @pytest.mark.asyncio
    async def test_health_check_returns_unhealthy_on_exception(self, client, mock_client):
        """Test GET /api/cluster/health returns unhealthy when health check throws."""
        mock_client.health_check = MagicMock(side_effect=Exception("Connection refused"))

        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_check_returns_degraded_on_cluster_exception(self, client, mock_client):
        """Test GET /api/cluster/health returns degraded when cluster check throws."""
        mock_client.get_cluster_status = MagicMock(side_effect=Exception("Failed"))

        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_health_check_returns_degraded_on_failed_responses(self, client, mock_client):
        """Test GET /api/cluster/health returns degraded on failed responses."""
        mock_client.health_resp.success = False

        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"

    # ==================== Cache Invalidate Tests ====================

    @pytest.mark.asyncio
    async def test_invalidate_cache_calls_client_invalidate(self, client, mock_client):
        """Test POST /api/cluster/cache/invalidate calls client invalidate."""
        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.post("/api/cluster/cache/invalidate")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Cache invalidated"

    @pytest.mark.asyncio
    async def test_invalidate_cache_with_endpoint(self, client, mock_client):
        """Test POST /api/cluster/cache/invalidate with specific endpoint."""
        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.post("/api/cluster/cache/invalidate?endpoint=nodes")

        assert response.status_code == 200
        data = response.json()
        assert data["endpoint"] == "nodes"

    # ==================== Circuit Breaker Tests ====================

    @pytest.mark.asyncio
    async def test_get_circuit_breaker_status(self, client, mock_client):
        """Test GET /api/cluster/circuit-breaker returns circuit state."""
        with patch.object(cluster_module, "get_ray_client", return_value=mock_client):
            response = await client.get("/api/cluster/circuit-breaker")

        assert response.status_code == 200
        data = response.json()
        assert "state" in data
        assert data["state"] == "closed"
        assert "cache_stats" in data

    # ==================== Response Model Tests ====================

    def test_node_info_model_validation(self):
        """Test NodeInfo model can be instantiated with valid data."""
        from algo_studio.api.routes.cluster import NodeInfo

        node = NodeInfo(
            node_id="test",
            ip="192.168.0.1",
            status="alive",
            cpu_count=8,
            gpu_count=1
        )
        assert node.node_id == "test"
        assert node.gpu_count == 1

    def test_actor_info_model_validation(self):
        """Test ActorInfo model can be instantiated with valid data."""
        from algo_studio.api.routes.cluster import ActorInfo

        actor = ActorInfo(
            actor_id="a1",
            class_name="TestClass",
            state="ALIVE"
        )
        assert actor.actor_id == "a1"
        assert actor.state == "ALIVE"

    def test_task_info_model_validation(self):
        """Test TaskInfo model can be instantiated with valid data."""
        from algo_studio.api.routes.cluster import TaskInfo

        task = TaskInfo(
            task_id="t1",
            func_name="test_func",
            state="RUNNING"
        )
        assert task.task_id == "t1"

    def test_cluster_status_response_model(self):
        """Test ClusterStatusResponse model can be instantiated."""
        from algo_studio.api.routes.cluster import ClusterStatusResponse

        resp = ClusterStatusResponse(
            connected=True,
            nodes=[]
        )
        assert resp.connected is True
        assert resp.nodes == []

    def test_health_check_response_model(self):
        """Test HealthCheckResponse model can be instantiated."""
        from algo_studio.api.routes.cluster import HealthCheckResponse

        resp = HealthCheckResponse(
            status="healthy",
            ray_dashboard=True,
            gcs=True,
            circuit_breaker="closed",
            cache_stats={"hits": 0, "misses": 0}
        )
        assert resp.status == "healthy"

    def test_node_detail_response_model(self):
        """Test NodeDetailResponse model can be instantiated."""
        from algo_studio.api.routes.cluster import NodeDetailResponse

        resp = NodeDetailResponse(
            node_id="test",
            ip="192.168.0.1",
            status="alive",
            resources={"CPU": 8}
        )
        assert resp.node_id == "test"
