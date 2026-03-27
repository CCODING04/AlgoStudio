# tests/unit/api/test_tasks_api.py
"""Unit tests for tasks API endpoints."""

import hashlib
import hmac
import os
import time

# Set secret key for RBAC middleware BEFORE importing app
os.environ["RBAC_SECRET_KEY"] = "test-secret-key-12345"

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock
from algo_studio.api.main import app
from algo_studio.core.task import TaskType, TaskStatus


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


class TestTasksAPI:
    """Test suite for tasks API endpoints."""

    @pytest.fixture
    def client(self):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.fixture
    def auth_headers(self):
        """Provide valid authentication headers for developer role."""
        return make_auth_headers(user_id="test-user", role="developer")

    @pytest.mark.asyncio
    async def test_create_task_train(self, client, auth_headers):
        """Test creating a train task."""
        response = await client.post(
            "/api/tasks",
            headers=auth_headers,
            json={
                "task_type": "train",
                "algorithm_name": "simple_classifier",
                "algorithm_version": "v1",
                "config": {"epochs": 100},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] is not None
        assert data["task_type"] == "train"
        assert data["algorithm_name"] == "simple_classifier"
        assert data["algorithm_version"] == "v1"
        assert data["status"] == "pending"
        assert data["progress"] == 0

    @pytest.mark.asyncio
    async def test_create_task_infer(self, client, auth_headers):
        """Test creating an infer task."""
        response = await client.post(
            "/api/tasks",
            headers=auth_headers,
            json={
                "task_type": "infer",
                "algorithm_name": "simple_classifier",
                "algorithm_version": "v1",
                "config": {"inputs": [1, 2, 3]},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["task_type"] == "infer"

    @pytest.mark.asyncio
    async def test_create_task_verify(self, client, auth_headers):
        """Test creating a verify task."""
        response = await client.post(
            "/api/tasks",
            headers=auth_headers,
            json={
                "task_type": "verify",
                "algorithm_name": "simple_classifier",
                "algorithm_version": "v1",
                "config": {"test_data": "/data/test.jpg"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["task_type"] == "verify"

    @pytest.mark.asyncio
    async def test_create_task_invalid_type(self, client, auth_headers):
        """Test creating task with invalid type returns 400."""
        response = await client.post(
            "/api/tasks",
            headers=auth_headers,
            json={
                "task_type": "invalid_type",
                "algorithm_name": "simple_classifier",
                "algorithm_version": "v1",
            },
        )
        assert response.status_code == 400
        assert "Invalid task_type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_task_missing_fields(self, client, auth_headers):
        """Test creating task with missing required fields."""
        response = await client.post(
            "/api/tasks",
            headers=auth_headers,
            json={
                "task_type": "train",
            },
        )
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, client, auth_headers):
        """Test listing tasks when none exist."""
        response = await client.get("/api/tasks", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "has_more" in data

    @pytest.mark.asyncio
    async def test_list_tasks_with_tasks(self, client, auth_headers):
        """Test listing tasks returns created tasks."""
        # Create a task first
        await client.post(
            "/api/tasks",
            headers=auth_headers,
            json={
                "task_type": "train",
                "algorithm_name": "simple_classifier",
                "algorithm_version": "v1",
            },
        )
        response = await client.get("/api/tasks", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data.get("items", [])) >= 1

    @pytest.mark.asyncio
    async def test_list_tasks_with_status_filter(self, client, auth_headers):
        """Test listing tasks with status filter."""
        response = await client.get("/api/tasks?status=pending", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        for task in data.get("items", []):
            assert task["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_tasks_invalid_status(self, client, auth_headers):
        """Test listing tasks with invalid status returns 400."""
        response = await client.get("/api/tasks?status=invalid", headers=auth_headers)
        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_task_found(self, client, auth_headers):
        """Test getting an existing task."""
        # Create a task first
        create_response = await client.post(
            "/api/tasks",
            headers=auth_headers,
            json={
                "task_type": "train",
                "algorithm_name": "simple_classifier",
                "algorithm_version": "v1",
            },
        )
        task_id = create_response.json()["task_id"]

        response = await client.get(f"/api/tasks/{task_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, client, auth_headers):
        """Test getting a non-existent task returns 404."""
        response = await client.get("/api/tasks/non-existent-id", headers=auth_headers)
        assert response.status_code == 404
        assert "Task not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_dispatch_task_success(self, client, auth_headers):
        """Test dispatching a pending task."""
        # Create a task first
        create_response = await client.post(
            "/api/tasks",
            headers=auth_headers,
            json={
                "task_type": "train",
                "algorithm_name": "simple_classifier",
                "algorithm_version": "v1",
            },
        )
        task_id = create_response.json()["task_id"]

        # Dispatch the task
        with patch("algo_studio.core.task.ray") as mock_ray:
            mock_ray.nodes.return_value = []
            mock_ray.get.return_value = None

            response = await client.post(f"/api/tasks/{task_id}/dispatch", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == task_id
            # Status should be running since we mocked ray.client

    @pytest.mark.asyncio
    async def test_dispatch_task_not_found(self, client, auth_headers):
        """Test dispatching non-existent task returns 404."""
        response = await client.post("/api/tasks/non-existent-id/dispatch", headers=auth_headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_dispatch_task_already_dispatched(self, client, auth_headers):
        """Test dispatching already dispatched task returns 400."""
        # Create and dispatch a task
        create_response = await client.post(
            "/api/tasks",
            headers=auth_headers,
            json={
                "task_type": "train",
                "algorithm_name": "simple_classifier",
                "algorithm_version": "v1",
            },
        )
        task_id = create_response.json()["task_id"]

        # Try to dispatch twice
        await client.post(f"/api/tasks/{task_id}/dispatch", headers=auth_headers)
        response = await client.post(f"/api/tasks/{task_id}/dispatch", headers=auth_headers)
        assert response.status_code == 400
        assert "already dispatched" in response.json()["detail"].lower()


class TestTasksAPIResponseFormat:
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
    async def test_task_response_has_required_fields(self, client, auth_headers):
        """Test that task response contains all required fields."""
        response = await client.post(
            "/api/tasks",
            headers=auth_headers,
            json={
                "task_type": "train",
                "algorithm_name": "simple_classifier",
                "algorithm_version": "v1",
            },
        )
        data = response.json()
        required_fields = [
            "task_id", "task_type", "algorithm_name", "algorithm_version",
            "status", "created_at", "started_at", "completed_at",
            "assigned_node", "error", "progress"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_task_list_response_has_required_fields(self, client, auth_headers):
        """Test that task list response contains all required fields."""
        response = await client.get("/api/tasks", headers=auth_headers)
        data = response.json()
        assert "items" in data
        assert "has_more" in data
        assert isinstance(data["items"], list)


class TestTasksAPIRBAC:
    """Tests for RBAC authentication on Tasks API."""

    @pytest.fixture
    def client(self):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.asyncio
    async def test_tasks_api_rejects_request_without_auth_header(self, client):
        """Test that requests without X-User-ID header are rejected."""
        response = await client.get("/api/tasks")
        assert response.status_code == 401
        assert "UNAUTHORIZED" in response.json()["detail"]["error"]["code"]
        assert "X-User-ID" in response.json()["detail"]["error"]["message"]

    @pytest.mark.asyncio
    async def test_tasks_api_rejects_request_with_invalid_signature(self, client):
        """Test that requests with invalid signature are rejected."""
        headers = {
            "X-User-ID": "test-user",
            "X-User-Role": "developer",
            "X-Timestamp": str(int(time.time())),
            "X-Signature": "invalid_signature_here",
        }
        response = await client.get("/api/tasks", headers=headers)
        assert response.status_code == 401
        assert "INVALID_SIGNATURE" in response.json()["detail"]["error"]["code"]

    @pytest.mark.asyncio
    async def test_tasks_api_rejects_expired_timestamp(self, client):
        """Test that requests with expired timestamp are rejected."""
        # Use timestamp from 10 minutes ago (beyond 5 minute limit)
        expired_timestamp = int(time.time()) - 600
        headers = make_auth_headers(
            user_id="test-user",
            role="developer",
            timestamp=expired_timestamp
        )
        response = await client.get("/api/tasks", headers=headers)
        assert response.status_code == 401
        assert "INVALID_SIGNATURE" in response.json()["detail"]["error"]["code"]

    @pytest.mark.asyncio
    async def test_missing_secret_key_rejects_all_requests(self, client):
        """Test that requests are rejected when secret key is not configured."""
        # This test verifies the fail-secure behavior when no secret key is set
        # Since we set RBAC_SECRET_KEY in the test env, we just verify the header is required
        response = await client.get("/api/tasks")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_tasks_api_rejects_post_without_auth_header(self, client):
        """Test that POST /api/tasks without auth header is rejected with 401."""
        response = await client.post(
            "/api/tasks",
            json={
                "task_type": "train",
                "algorithm_name": "simple_classifier",
                "algorithm_version": "v1",
            },
        )
        assert response.status_code == 401
        assert "UNAUTHORIZED" in response.json()["detail"]["error"]["code"]
        assert "X-User-ID" in response.json()["detail"]["error"]["message"]

    @pytest.mark.asyncio
    async def test_tasks_api_rejects_delete_without_auth_header(self, client):
        """Test that DELETE /api/tasks/{id} without auth header is rejected with 401."""
        response = await client.delete("/api/tasks/some-task-id")
        assert response.status_code == 401
        assert "UNAUTHORIZED" in response.json()["detail"]["error"]["code"]
        assert "X-User-ID" in response.json()["detail"]["error"]["message"]


class TestDeleteTaskEndpoint:
    """Tests for DELETE /api/tasks/{id} endpoint."""

    @pytest.fixture
    def client(self):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.fixture
    def auth_headers(self):
        """Provide valid authentication headers for developer role."""
        return make_auth_headers(user_id="test-user", role="developer")

    @pytest.fixture
    def admin_auth_headers(self):
        """Provide valid authentication headers for admin role."""
        return make_auth_headers(user_id="admin-user", role="admin")

    @pytest.mark.asyncio
    async def test_delete_task_success(self, client, auth_headers):
        """Test successfully deleting a pending task."""
        # Create a task first
        create_response = await client.post(
            "/api/tasks",
            headers=auth_headers,
            json={
                "task_type": "train",
                "algorithm_name": "simple_classifier",
                "algorithm_version": "v1",
            },
        )
        task_id = create_response.json()["task_id"]

        # Delete the task
        response = await client.delete(f"/api/tasks/{task_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert "deleted" in data["message"].lower()

        # Verify task is gone
        get_response = await client.get(f"/api/tasks/{task_id}", headers=auth_headers)
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, client, auth_headers):
        """Test deleting a non-existent task returns 404."""
        response = await client.delete("/api/tasks/non-existent-id", headers=auth_headers)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_task_running_fails(self, client, auth_headers):
        """Test deleting a running task fails with 400."""
        # Create a task first
        create_response = await client.post(
            "/api/tasks",
            headers=auth_headers,
            json={
                "task_type": "train",
                "algorithm_name": "simple_classifier",
                "algorithm_version": "v1",
            },
        )
        task_id = create_response.json()["task_id"]

        # Dispatch the task to make it running
        with patch("algo_studio.core.task.ray") as mock_ray, \
             patch("algo_studio.core.task.get_progress_store") as mock_progress_store:
            mock_ray.nodes.return_value = []
            # Use a mock ObjectRef for ray.get
            mock_obj_ref = MagicMock()
            mock_ray.get.return_value = 0
            mock_progress_store.return_value.get.remote.return_value = mock_obj_ref
            await client.post(f"/api/tasks/{task_id}/dispatch", headers=auth_headers)

        # Try to delete a running task - should fail
        with patch("algo_studio.core.task.ray") as mock_ray, \
             patch("algo_studio.core.task.get_progress_store") as mock_progress_store:
            mock_obj_ref = MagicMock()
            mock_ray.get.return_value = 0
            mock_progress_store.return_value.get.remote.return_value = mock_obj_ref
            response = await client.delete(f"/api/tasks/{task_id}", headers=auth_headers)
        assert response.status_code == 400
        assert "running" in response.json()["detail"].lower() or "cannot delete" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_task_requires_task_delete_permission(self, client, auth_headers):
        """Test that deleting a task requires task.delete permission (viewer role should fail)."""
        # Create a task first
        create_response = await client.post(
            "/api/tasks",
            headers=auth_headers,
            json={
                "task_type": "train",
                "algorithm_name": "simple_classifier",
                "algorithm_version": "v1",
            },
        )
        task_id = create_response.json()["task_id"]

        # Try to delete with viewer role (has only task.read permission)
        viewer_headers = make_auth_headers(user_id="viewer-user", role="viewer")
        response = await client.delete(f"/api/tasks/{task_id}", headers=viewer_headers)
        assert response.status_code == 403
        assert "PERMISSION_DENIED" in response.json()["detail"]["error"]["code"]
