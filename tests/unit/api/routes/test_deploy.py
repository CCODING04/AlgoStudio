# tests/unit/api/routes/test_deploy.py
"""Unit tests for deploy API endpoints."""

from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
import importlib.util
import json

import pytest
from fastapi import FastAPI, Request
from httpx import AsyncClient, ASGITransport
from pydantic import SecretStr

# Load deploy module directly
deploy_module_path = Path(__file__).parent.parent.parent.parent.parent / "src" / "algo_studio" / "api" / "routes" / "deploy.py"
spec = importlib.util.spec_from_file_location("deploy", deploy_module_path)
deploy_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy_module)

router = deploy_module.router


class MockRedis:
    """Mock Redis client for testing."""

    def __init__(self):
        self.data = {}

    async def scan_iter(self, pattern):
        """Return keys matching pattern."""
        prefix = pattern.replace("*", "")
        for key in self.data.keys():
            if key.startswith(prefix):
                yield key

    async def get(self, key):
        return self.data.get(key)


class MockDeployProgressStore:
    """Mock DeployProgressStore for testing."""

    def __init__(self):
        self.deployments = {}
        self._redis = MockRedis()

    async def _get_redis(self):
        return self._redis

    async def get(self, task_id):
        return self.deployments.get(task_id)

    async def get_by_node(self, node_ip):
        for d in self.deployments.values():
            if d.node_ip == node_ip:
                return d
        return None


class MockSSHDeployer:
    """Mock SSHDeployer for testing."""

    def __init__(self):
        self.deployed_nodes = {}

    async def deploy_worker(self, request):
        return f"task-{request.node_ip}"


class MockDeployProgress:
    """Mock DeployProgress for testing."""

    def __init__(self, task_id, status="pending", node_ip="192.168.0.115"):
        from scripts.ssh_deploy import DeployStatus
        self.task_id = task_id
        self.status = DeployStatus(status)
        self.node_ip = node_ip
        self.step = "connecting"
        self.step_index = 1
        self.total_steps = 7
        self.progress = 15
        self.message = "Connecting..."
        self.error = None
        self.started_at = datetime.now()
        self.completed_at = None

    def model_dump_json(self):
        return json.dumps({
            "task_id": self.task_id,
            "status": self.status.value,
            "node_ip": self.node_ip,
            "step": self.step,
            "step_index": self.step_index,
            "total_steps": self.total_steps,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        })


class TestDeployWorkerRequestInternal:
    """Unit tests for DeployWorkerRequestInternal validation."""

    def test_valid_ip_address(self):
        """Test DeployWorkerRequestInternal accepts valid IPv4."""
        from algo_studio.api.routes.deploy import DeployWorkerRequestInternal

        req = DeployWorkerRequestInternal(
            node_ip="192.168.0.115",
            username="admin02",
            password=SecretStr("password"),
            head_ip="192.168.0.126"
        )
        assert req.node_ip == "192.168.0.115"

    def test_invalid_ip_address_rejected(self):
        """Test DeployWorkerRequestInternal rejects invalid IP."""
        from algo_studio.api.routes.deploy import DeployWorkerRequestInternal
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            DeployWorkerRequestInternal(
                node_ip="invalid-ip",
                username="admin02",
                password=SecretStr("password"),
                head_ip="192.168.0.126"
            )
        assert exc_info.value.status_code == 400

    def test_invalid_head_ip_rejected(self):
        """Test DeployWorkerRequestInternal rejects invalid head IP."""
        from algo_studio.api.routes.deploy import DeployWorkerRequestInternal
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            DeployWorkerRequestInternal(
                node_ip="192.168.0.115",
                username="admin02",
                password=SecretStr("password"),
                head_ip="not-an-ip"
            )
        assert exc_info.value.status_code == 400

    def test_invalid_ray_port_rejected(self):
        """Test DeployWorkerRequestInternal rejects invalid ray port."""
        from algo_studio.api.routes.deploy import DeployWorkerRequestInternal
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            DeployWorkerRequestInternal(
                node_ip="192.168.0.115",
                username="admin02",
                password=SecretStr("password"),
                head_ip="192.168.0.126",
                ray_port=70000
            )
        assert exc_info.value.status_code == 400

    def test_to_deploy_request_converts_password(self):
        """Test to_deploy_request correctly extracts plain password."""
        from algo_studio.api.routes.deploy import DeployWorkerRequestInternal

        req = DeployWorkerRequestInternal(
            node_ip="192.168.0.115",
            username="admin02",
            password=SecretStr("secret"),
            head_ip="192.168.0.126"
        )
        deploy_req = req.to_deploy_request()
        assert deploy_req.password == "secret"
        assert deploy_req.node_ip == "192.168.0.115"


class TestDeployRouter:
    """Unit tests for deploy router endpoints."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app with the deploy router."""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, test_app):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")

    @pytest.fixture
    def mock_progress_store(self):
        """Create mock DeployProgressStore."""
        return MockDeployProgressStore()

    @pytest.fixture
    def mock_deployer(self):
        """Create mock SSHDeployer."""
        return MockSSHDeployer()

    # ==================== List Workers Tests ====================

    @pytest.mark.asyncio
    async def test_list_workers_returns_empty_list(self, client, mock_progress_store):
        """Test GET /api/deploy/workers returns empty list when no deployments."""
        with patch.object(deploy_module, "_progress_store", mock_progress_store):
            response = await client.get("/api/deploy/workers")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_workers_returns_deployments(self, client, mock_progress_store):
        """Test GET /api/deploy/workers returns deployment list."""
        from scripts.ssh_deploy import DeployProgressStore
        progress = MockDeployProgress("task-1", "completed", "192.168.0.115")
        # Use correct prefix
        key = f"{DeployProgressStore.REDIS_KEY_PREFIX}task-1"
        mock_progress_store.deployments[key] = progress
        # Add to Redis mock
        import json
        mock_progress_store._redis.data[key] = progress.model_dump_json()

        with patch.object(deploy_module, "_progress_store", mock_progress_store):
            response = await client.get("/api/deploy/workers")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_list_workers_filters_by_status(self, client, mock_progress_store):
        """Test GET /api/deploy/workers filters by status."""
        from scripts.ssh_deploy import DeployProgressStore
        progress1 = MockDeployProgress("task-1", "completed")
        progress2 = MockDeployProgress("task-2", "pending")
        key1 = f"{DeployProgressStore.REDIS_KEY_PREFIX}task-1"
        key2 = f"{DeployProgressStore.REDIS_KEY_PREFIX}task-2"
        mock_progress_store.deployments[key1] = progress1
        mock_progress_store.deployments[key2] = progress2
        import json
        mock_progress_store._redis.data[key1] = progress1.model_dump_json()
        mock_progress_store._redis.data[key2] = progress2.model_dump_json()

        with patch.object(deploy_module, "_progress_store", mock_progress_store):
            response = await client.get("/api/deploy/workers?status=completed")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_workers_filters_by_node_ip(self, client, mock_progress_store):
        """Test GET /api/deploy/workers filters by node IP."""
        from scripts.ssh_deploy import DeployProgressStore
        progress1 = MockDeployProgress("task-1", "completed", "192.168.0.115")
        progress2 = MockDeployProgress("task-2", "completed", "192.168.0.120")
        key1 = f"{DeployProgressStore.REDIS_KEY_PREFIX}task-1"
        key2 = f"{DeployProgressStore.REDIS_KEY_PREFIX}task-2"
        mock_progress_store.deployments[key1] = progress1
        mock_progress_store.deployments[key2] = progress2
        import json
        mock_progress_store._redis.data[key1] = progress1.model_dump_json()
        mock_progress_store._redis.data[key2] = progress2.model_dump_json()

        with patch.object(deploy_module, "_progress_store", mock_progress_store):
            response = await client.get("/api/deploy/workers?node_ip=192.168.0.115")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_workers_handles_invalid_status(self, client, mock_progress_store):
        """Test GET /api/deploy/workers returns 400 for invalid status."""
        with patch.object(deploy_module, "_progress_store", mock_progress_store):
            response = await client.get("/api/deploy/workers?status=invalid")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_workers_handles_redis_error(self, client, mock_progress_store):
        """Test GET /api/deploy/workers handles Redis error."""
        async def raise_error():
            raise Exception("Redis connection failed")

        mock_progress_store._get_redis = raise_error

        with patch.object(deploy_module, "_progress_store", mock_progress_store):
            response = await client.get("/api/deploy/workers")

        assert response.status_code == 500

    # ==================== Get Worker Tests ====================

    @pytest.mark.asyncio
    async def test_get_worker_returns_deployment(self, client, mock_progress_store):
        """Test GET /api/deploy/worker/{task_id} returns deployment details."""
        progress = MockDeployProgress("task-1")
        mock_progress_store.deployments["task-1"] = progress

        with patch.object(deploy_module, "_progress_store", mock_progress_store):
            response = await client.get("/api/deploy/worker/task-1")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-1"

    @pytest.mark.asyncio
    async def test_get_worker_returns_404_when_not_found(self, client, mock_progress_store):
        """Test GET /api/deploy/worker/{task_id} returns 404 when not found."""
        with patch.object(deploy_module, "_progress_store", mock_progress_store):
            response = await client.get("/api/deploy/worker/nonexistent")

        assert response.status_code == 404

    # ==================== Create Worker Tests ====================

    @pytest.mark.asyncio
    async def test_create_worker_initiates_deployment(self, client, mock_progress_store, mock_deployer):
        """Test POST /api/deploy/worker initiates new deployment."""
        with patch.object(deploy_module, "_progress_store", mock_progress_store), \
             patch.object(deploy_module, "_deployer", mock_deployer):
            response = await client.post(
                "/api/deploy/worker",
                json={
                    "node_ip": "192.168.0.115",
                    "username": "admin02",
                    "password": "secret",
                    "head_ip": "192.168.0.126"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["node_ip"] == "192.168.0.115"

    @pytest.mark.asyncio
    async def test_create_worker_returns_existing_when_in_progress(self, client, mock_progress_store, mock_deployer):
        """Test POST /api/deploy/worker returns existing task if deployment in progress."""
        progress = MockDeployProgress("existing-task", "deploying", "192.168.0.115")
        mock_progress_store.deployments["existing-task"] = progress

        with patch.object(deploy_module, "_progress_store", mock_progress_store), \
             patch.object(deploy_module, "_deployer", mock_deployer):
            response = await client.post(
                "/api/deploy/worker",
                json={
                    "node_ip": "192.168.0.115",
                    "username": "admin02",
                    "password": "secret",
                    "head_ip": "192.168.0.126"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "existing-task"
        assert "in progress" in data["message"]

    @pytest.mark.asyncio
    async def test_create_worker_validates_ip_format(self, client, mock_progress_store, mock_deployer):
        """Test POST /api/deploy/worker validates IP format."""
        with patch.object(deploy_module, "_progress_store", mock_progress_store), \
             patch.object(deploy_module, "_deployer", mock_deployer):
            response = await client.post(
                "/api/deploy/worker",
                json={
                    "node_ip": "invalid-ip",
                    "username": "admin02",
                    "password": "secret",
                    "head_ip": "192.168.0.126"
                }
            )

        # Validation error - either 400 (HTTPException from validator) or 422 (pydantic)
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_create_worker_handles_deploy_error(self, client, mock_progress_store, mock_deployer):
        """Test POST /api/deploy/worker handles DeployError."""
        from scripts.ssh_deploy import DeployError

        async def raise_deploy_error(*args):
            raise DeployError(code="SSH_FAILED", message="Connection refused", step="connect")

        mock_deployer.deploy_worker = raise_deploy_error

        with patch.object(deploy_module, "_progress_store", mock_progress_store), \
             patch.object(deploy_module, "_deployer", mock_deployer):
            response = await client.post(
                "/api/deploy/worker",
                json={
                    "node_ip": "192.168.0.115",
                    "username": "admin02",
                    "password": "secret",
                    "head_ip": "192.168.0.126"
                }
            )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data["detail"]

    # ==================== Deploy Progress SSE Tests ====================

    @pytest.mark.asyncio
    async def test_get_worker_progress_returns_404_when_not_found(self, client, mock_progress_store):
        """Test GET /api/deploy/worker/{task_id}/progress returns 404 when not found."""
        with patch.object(deploy_module, "_progress_store", mock_progress_store):
            response = await client.get("/api/deploy/worker/nonexistent/progress")

        assert response.status_code == 404

    # ==================== Format Progress Event Tests ====================

    def test_format_progress_event(self, mock_progress_store):
        """Test _format_progress_event formats DeployProgress correctly."""
        from scripts.ssh_deploy import DeployStatus
        from scripts.ssh_deploy import DeployProgress

        progress = DeployProgress(
            task_id="task-1",
            status=DeployStatus.DEPLOYING,
            step="installing",
            step_index=3,
            total_steps=7,
            progress=50,
            message="Installing packages...",
            error=None,
            node_ip="192.168.0.115",
            started_at=datetime.now(),
            completed_at=None
        )

        result = deploy_module._format_progress_event(progress)
        data = json.loads(result)

        assert data["task_id"] == "task-1"
        assert data["status"] == "deploying"
        assert data["progress"] == 50


class TestDeployProgressResponse:
    """Unit tests for DeployProgressResponse model."""

    def test_deploy_progress_response_validation(self):
        """Test DeployProgressResponse can be instantiated."""
        from algo_studio.api.routes.deploy import DeployProgressResponse

        resp = DeployProgressResponse(
            task_id="task-1",
            status="deploying",
            step="connecting",
            step_index=1,
            total_steps=7,
            progress=15
        )
        assert resp.task_id == "task-1"
        assert resp.progress == 15


class TestDeployWorkerResponse:
    """Unit tests for DeployWorkerResponse model."""

    def test_deploy_worker_response_validation(self):
        """Test DeployWorkerResponse can be instantiated."""
        from algo_studio.api.routes.deploy import DeployWorkerResponse

        resp = DeployWorkerResponse(
            task_id="task-1",
            status="completed",
            step="done",
            step_index=7,
            total_steps=7,
            progress=100
        )
        assert resp.task_id == "task-1"
        assert resp.status == "completed"


class TestSnapshotResponse:
    """Unit tests for SnapshotResponse model."""

    def test_snapshot_response_validation(self):
        """Test SnapshotResponse can be instantiated."""
        from algo_studio.api.routes.deploy import SnapshotResponse

        resp = SnapshotResponse(
            snapshot_id="snap-1",
            deployment_id="deploy-1",
            node_ip="192.168.0.115",
            version="v1",
            config={},
            steps_completed=["connect", "install"],
            created_at="2024-01-01T00:00:00",
            ray_head_ip="192.168.0.126",
            ray_port=6379,
            artifacts=[],
            metadata={}
        )
        assert resp.snapshot_id == "snap-1"
        assert resp.node_ip == "192.168.0.115"
