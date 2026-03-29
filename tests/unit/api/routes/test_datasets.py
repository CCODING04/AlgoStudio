# tests/unit/api/routes/test_datasets.py
"""Unit tests for datasets API endpoints."""

import hashlib
import hmac
import os
import time
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

# Set secret key for RBAC middleware BEFORE importing app
os.environ["RBAC_SECRET_KEY"] = "test-secret-key-12345"

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

# Import the datasets router
import importlib.util
from pathlib import Path

datasets_module_path = Path(__file__).parent.parent.parent.parent.parent / "src" / "algo_studio" / "api" / "routes" / "datasets.py"
spec = importlib.util.spec_from_file_location("datasets", datasets_module_path)
datasets_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(datasets_module)

router = datasets_module.router


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


class MockUser:
    """Mock User for testing."""
    def __init__(self, user_id="test-user", role="developer", is_superuser=False):
        self.user_id = user_id
        self.username = user_id
        self.role = role
        self.is_superuser = is_superuser


class MockDataset:
    """Mock Dataset for testing."""
    def __init__(
        self,
        dataset_id="ds-test123",
        name="test-dataset",
        description="A test dataset",
        path="/nas/datasets/test",
        storage_type="dvc",
        size_gb=10.5,
        file_count=100,
        version="v1.0",
        extra_metadata=None,
        tags=None,
        is_public=False,
        owner_id="test-user",
        team_id=None,
        is_active=True,
        last_accessed_at=None,
        created_at=None,
        updated_at=None,
    ):
        self.dataset_id = dataset_id
        self.name = name
        self.description = description
        self.path = path
        self.storage_type = storage_type
        self.size_gb = size_gb
        self.file_count = file_count
        self.version = version
        self.extra_metadata = extra_metadata or {"key": "value"}
        self.tags = tags or ["test", "demo"]
        self.is_public = is_public
        self.owner_id = owner_id
        self.team_id = team_id
        self.is_active = is_active
        self.last_accessed_at = last_accessed_at or datetime.now()
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()


class MockDatasetAccess:
    """Mock DatasetAccess for testing."""
    def __init__(
        self,
        id=1,
        dataset_id="ds-test123",
        user_id="test-user",
        team_id=None,
        access_level="read",
        granted_at=None,
        granted_by="admin-user",
    ):
        self.id = id
        self.dataset_id = dataset_id
        self.user_id = user_id
        self.team_id = team_id
        self.access_level = access_level
        self.granted_at = granted_at or datetime.now()
        self.granted_by = granted_by


class MockSession:
    """Mock AsyncSession for testing.

    Provides a simple mock that tracks calls and returns configured results.
    """

    def __init__(self, mock_results=None):
        self._results = mock_results or []
        self._result_index = 0
        self.added = []
        self.deleted = []
        self.committed = False
        self.refreshed = None

    def set_results(self, results):
        """Set results to return sequentially on execute calls."""
        self._results = results
        self._result_index = 0

    async def execute(self, *args, **kwargs):
        if self._result_index < len(self._results):
            result = self._results[self._result_index]
            self._result_index += 1
            return result
        return MagicMock()

    async def commit(self):
        self.committed = True

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def refresh(self, obj):
        # Simulate what the database would do - populate fields with defaults
        if hasattr(obj, 'is_active') and obj.is_active is None:
            obj.is_active = True
        if hasattr(obj, 'created_at') and obj.created_at is None:
            obj.created_at = datetime.now()
        if hasattr(obj, 'updated_at') and obj.updated_at is None:
            obj.updated_at = datetime.now()
        if hasattr(obj, 'last_accessed_at') and obj.last_accessed_at is None:
            obj.last_accessed_at = datetime.now()
        if hasattr(obj, 'dataset_id') and obj.dataset_id is None:
            obj.dataset_id = f"ds-test123"
        if hasattr(obj, 'size_gb') and obj.size_gb is None:
            obj.size_gb = 0.0
        if hasattr(obj, 'file_count') and obj.file_count is None:
            obj.file_count = 0
        # DatasetAccess specific fields
        if hasattr(obj, 'id') and obj.id is None:
            obj.id = 1
        if hasattr(obj, 'granted_at') and obj.granted_at is None:
            obj.granted_at = datetime.now()
        self.refreshed = obj

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def make_mock_result(scalar_one_or_none=None, scalars_all=None, scalar_count=None):
    """Create a mock SQLAlchemy result with configurable returns.

    Args:
        scalar_one_or_none: Value to return from scalar_one_or_none() - use actual value, not MagicMock
        scalars_all: List to return from scalars().all()
        scalar_count: Integer to return from scalar()

    Returns:
        Mock result object with properly configured return values
    """
    result = MagicMock()

    # Use spec to make it behave more like a real result
    # For scalar_one_or_none, we need to return the actual value, not create a new MagicMock
    if scalar_one_or_none is not None:
        result.scalar_one_or_none.return_value = scalar_one_or_none
    else:
        # Explicitly return None, not a MagicMock
        result.scalar_one_or_none.return_value = None

    if scalars_all is not None:
        result.scalars.return_value.all.return_value = scalars_all

    if scalar_count is not None:
        result.scalar.return_value = scalar_count

    return result


class TestDatasetsRouter:
    """Unit tests for datasets router endpoints."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app with the datasets router."""
        app = FastAPI()
        app.include_router(router)

        # Add user to request state via middleware
        @app.middleware("http")
        async def add_user_state(request, call_next):
            if "X-User-ID" in request.headers:
                role = request.headers.get("X-User-Role", "viewer")
                user = MockUser(
                    user_id=request.headers.get("X-User-ID"),
                    role=role,
                    is_superuser=(role == "admin")
                )
                request.state.user = user
            else:
                request.state.user = None
            response = await call_next(request)
            return response

        return app

    @pytest.fixture
    def client(self, test_app):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")

    @pytest.fixture
    def auth_headers(self):
        """Provide valid authentication headers for developer role."""
        return make_auth_headers(user_id="test-user", role="developer")

    @pytest.fixture
    def admin_auth_headers(self):
        """Provide valid authentication headers for admin role."""
        return make_auth_headers(user_id="admin-user", role="admin")

    # ==================== Create Dataset Tests ====================

    @pytest.mark.asyncio
    async def test_create_dataset_success(self, client, auth_headers, test_app):
        """Test creating a new dataset successfully."""
        mock_dataset = MockDataset()

        # For create: first check if name exists (returns None), then create succeeds
        mock_results = [
            make_mock_result(scalar_one_or_none=None),  # No existing dataset
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        try:
            response = await client.post(
                "/api/datasets",
                headers=auth_headers,
                json={
                    "name": "test-dataset",
                    "description": "A test dataset",
                    "path": "/nas/datasets/test",
                    "storage_type": "dvc",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "test-dataset"
            assert data["description"] == "A test dataset"
            assert data["storage_type"] == "dvc"
        finally:
            test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_dataset_without_auth(self, client):
        """Test creating dataset without authentication returns 401."""
        response = await client.post(
            "/api/datasets",
            json={
                "name": "test-dataset",
                "path": "/nas/datasets/test",
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_dataset_duplicate_name(self, client, auth_headers, test_app):
        """Test creating dataset with duplicate name returns 400."""
        existing_dataset = MockDataset()

        mock_results = [
            make_mock_result(scalar_one_or_none=existing_dataset),  # Found existing
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        try:
            response = await client.post(
                "/api/datasets",
                headers=auth_headers,
                json={
                    "name": "test-dataset",
                    "path": "/nas/datasets/test",
                },
            )

            assert response.status_code == 400
            assert "already exists" in response.json()["detail"]
        finally:
            test_app.dependency_overrides.clear()

    # ==================== List Datasets Tests ====================

    @pytest.mark.asyncio
    async def test_list_datasets_success(self, client, auth_headers, test_app):
        """Test listing datasets successfully."""
        mock_datasets = [
            MockDataset(dataset_id="ds-1", name="dataset-1"),
            MockDataset(dataset_id="ds-2", name="dataset-2"),
        ]

        # List datasets: datasets query, count query
        # List datasets: count query is executed FIRST, then datasets query
        mock_results = [
            make_mock_result(scalar_count=2),  # Count query - executed first
            make_mock_result(scalars_all=mock_datasets),  # Datasets query - executed second
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        try:
            response = await client.get("/api/datasets", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page" in data
            assert "page_size" in data
            assert "has_more" in data
            assert len(data["items"]) == 2
        finally:
            test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_datasets_with_search(self, client, auth_headers, test_app):
        """Test listing datasets with search filter."""
        # List datasets: count query is executed FIRST, then datasets query
        mock_results = [
            make_mock_result(scalar_count=0),  # Count query - executed first
            make_mock_result(scalars_all=[]),  # Datasets query - executed second
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        try:
            response = await client.get("/api/datasets?search=test", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert "items" in data
        finally:
            test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_datasets_with_active_filter(self, client, auth_headers, test_app):
        """Test listing datasets with active status filter."""
        # Count query is executed FIRST, then datasets query
        mock_results = [
            make_mock_result(scalar_count=0),  # Count query - first
            make_mock_result(scalars_all=[]),  # Datasets query - second
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        try:
            response = await client.get("/api/datasets?is_active=true", headers=auth_headers)

            assert response.status_code == 200
        finally:
            test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_datasets_without_auth(self, client):
        """Test listing datasets without authentication returns 401."""
        response = await client.get("/api/datasets")
        assert response.status_code == 401

    # ==================== Get Dataset Tests ====================

    @pytest.mark.asyncio
    async def test_get_dataset_success(self, client, auth_headers, test_app):
        """Test getting a specific dataset by ID."""
        mock_dataset = MockDataset()

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        try:
            response = await client.get(
                f"/api/datasets/{mock_dataset.dataset_id}",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["dataset_id"] == mock_dataset.dataset_id
            assert data["name"] == mock_dataset.name
        finally:
            test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_dataset_not_found(self, client, auth_headers, test_app):
        """Test getting a non-existent dataset returns 404."""
        mock_results = [
            make_mock_result(scalar_one_or_none=None),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        try:
            response = await client.get(
                "/api/datasets/non-existent-id",
                headers=auth_headers,
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            test_app.dependency_overrides.clear()

    # ==================== Update Dataset Tests ====================

    @pytest.mark.asyncio
    async def test_update_dataset_success(self, client, auth_headers, test_app):
        """Test updating a dataset successfully."""
        mock_dataset = MockDataset()

        # Update: find dataset, check access, update name (no conflict)
        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),  # Find dataset
            make_mock_result(scalar_one_or_none=None),  # No name conflict
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        with patch.object(datasets_module, 'check_dataset_access', return_value=True):
            try:
                response = await client.put(
                    f"/api/datasets/{mock_dataset.dataset_id}",
                    headers=auth_headers,
                    json={
                        "description": "Updated description",
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["description"] == "Updated description"
            finally:
                test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_dataset_permission_denied(self, client, auth_headers, test_app):
        """Test updating a dataset without permission returns 403."""
        mock_dataset = MockDataset()

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        with patch.object(datasets_module, 'check_dataset_access', return_value=False):
            try:
                response = await client.put(
                    f"/api/datasets/{mock_dataset.dataset_id}",
                    headers=auth_headers,
                    json={"description": "New description"},
                )

                assert response.status_code == 403
            finally:
                test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_dataset_duplicate_name(self, client, auth_headers, test_app):
        """Test updating dataset with duplicate name returns 400."""
        mock_dataset = MockDataset()
        existing_dataset = MockDataset(dataset_id="ds-other", name="existing-name")

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),  # Find dataset
            make_mock_result(scalar_one_or_none=existing_dataset),  # Name conflict
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        with patch.object(datasets_module, 'check_dataset_access', return_value=True):
            try:
                response = await client.put(
                    f"/api/datasets/{mock_dataset.dataset_id}",
                    headers=auth_headers,
                    json={"name": "existing-name"},
                )

                assert response.status_code == 400
                assert "already exists" in response.json()["detail"]
            finally:
                test_app.dependency_overrides.clear()

    # ==================== Delete Dataset Tests ====================

    @pytest.mark.asyncio
    async def test_delete_dataset_success(self, client, auth_headers, test_app):
        """Test soft deleting a dataset successfully."""
        mock_dataset = MockDataset()

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        with patch.object(datasets_module, 'check_dataset_access', return_value=True):
            try:
                response = await client.delete(
                    f"/api/datasets/{mock_dataset.dataset_id}",
                    headers=auth_headers,
                )

                assert response.status_code == 200
                data = response.json()
                assert data["dataset_id"] == mock_dataset.dataset_id
                assert "deleted" in data["message"].lower()
            finally:
                test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_dataset_not_found(self, client, auth_headers, test_app):
        """Test deleting a non-existent dataset returns 404."""
        mock_results = [
            make_mock_result(scalar_one_or_none=None),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        try:
            response = await client.delete(
                "/api/datasets/non-existent-id",
                headers=auth_headers,
            )

            assert response.status_code == 404
        finally:
            test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_dataset_permission_denied(self, client, auth_headers, test_app):
        """Test deleting a dataset without permission returns 403."""
        mock_dataset = MockDataset()

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        with patch.object(datasets_module, 'check_dataset_access', return_value=False):
            try:
                response = await client.delete(
                    f"/api/datasets/{mock_dataset.dataset_id}",
                    headers=auth_headers,
                )

                assert response.status_code == 403
            finally:
                test_app.dependency_overrides.clear()

    # ==================== Restore Dataset Tests ====================

    @pytest.mark.asyncio
    async def test_restore_dataset_success(self, client, auth_headers, test_app):
        """Test restoring a soft-deleted dataset successfully."""
        mock_dataset = MockDataset(is_active=False)

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        try:
            response = await client.post(
                f"/api/datasets/{mock_dataset.dataset_id}/restore",
                headers=auth_headers,
            )

            assert response.status_code == 200
        finally:
            test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_restore_dataset_not_owner(self, client, auth_headers, test_app):
        """Test restoring dataset by non-owner returns 403."""
        mock_dataset = MockDataset(is_active=False, owner_id="other-user")

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        try:
            response = await client.post(
                f"/api/datasets/{mock_dataset.dataset_id}/restore",
                headers=auth_headers,
            )

            assert response.status_code == 403
        finally:
            test_app.dependency_overrides.clear()

    # ==================== Upload Endpoint Tests ====================

    @pytest.mark.asyncio
    async def test_initiate_upload_success(self, client, auth_headers, test_app):
        """Test initiating dataset upload successfully."""
        mock_dataset = MockDataset()

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        with patch.object(datasets_module, 'check_dataset_access', return_value=True):
            try:
                response = await client.post(
                    f"/api/datasets/{mock_dataset.dataset_id}/upload",
                    headers=auth_headers,
                    json={
                        "filename": "test.csv",
                        "size_bytes": 1024 * 1024 * 100,  # 100MB
                        "storage_type": "nas",
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert "upload_id" in data
                assert "upload_url" in data
                assert "expires_at" in data
            finally:
                test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_initiate_upload_file_too_large(self, client, auth_headers, test_app):
        """Test initiating upload for file > 5GB returns 400."""
        mock_dataset = MockDataset()

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        with patch.object(datasets_module, 'check_dataset_access', return_value=True):
            try:
                response = await client.post(
                    f"/api/datasets/{mock_dataset.dataset_id}/upload",
                    headers=auth_headers,
                    json={
                        "filename": "huge_file.tar",
                        "size_bytes": 6 * 1024 * 1024 * 1024,  # 6GB
                        "storage_type": "nas",
                    },
                )

                assert response.status_code == 400
                assert "5GB" in response.json()["detail"]
            finally:
                test_app.dependency_overrides.clear()

    # ==================== Access Control Tests ====================

    @pytest.mark.asyncio
    async def test_list_dataset_access_success(self, client, admin_auth_headers, test_app):
        """Test listing dataset access permissions by admin."""
        mock_dataset = MockDataset()
        mock_access = MockDatasetAccess()

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
            make_mock_result(scalars_all=[mock_access]),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        with patch.object(datasets_module, 'check_dataset_access', return_value=True):
            try:
                response = await client.get(
                    f"/api/datasets/{mock_dataset.dataset_id}/access",
                    headers=admin_auth_headers,
                )

                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, list)
                assert len(data) == 1
            finally:
                test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_dataset_access_permission_denied(self, client, auth_headers, test_app):
        """Test listing dataset access without admin permission returns 403."""
        mock_dataset = MockDataset()

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        with patch.object(datasets_module, 'check_dataset_access', return_value=False):
            try:
                response = await client.get(
                    f"/api/datasets/{mock_dataset.dataset_id}/access",
                    headers=auth_headers,
                )

                assert response.status_code == 403
            finally:
                test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_grant_dataset_access_success(self, client, admin_auth_headers, test_app):
        """Test granting dataset access successfully."""
        mock_dataset = MockDataset()

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        with patch.object(datasets_module, 'check_dataset_access', return_value=True):
            try:
                response = await client.post(
                    f"/api/datasets/{mock_dataset.dataset_id}/access",
                    headers=admin_auth_headers,
                    json={
                        "user_id": "new-user",
                        "access_level": "read",
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["user_id"] == "new-user"
                assert data["access_level"] == "read"
            finally:
                test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_grant_dataset_access_no_user_or_team(self, client, admin_auth_headers, test_app):
        """Test granting access without user_id or team_id returns 400."""
        mock_dataset = MockDataset()

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        with patch.object(datasets_module, 'check_dataset_access', return_value=True):
            try:
                response = await client.post(
                    f"/api/datasets/{mock_dataset.dataset_id}/access",
                    headers=admin_auth_headers,
                    json={
                        "access_level": "read",
                    },
                )

                assert response.status_code == 400
                assert "user_id or team_id" in response.json()["detail"]
            finally:
                test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_revoke_dataset_access_success(self, client, admin_auth_headers, test_app):
        """Test revoking dataset access successfully."""
        mock_dataset = MockDataset()
        mock_access = MockDatasetAccess()

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_access),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        with patch.object(datasets_module, 'check_dataset_access', return_value=True):
            try:
                response = await client.delete(
                    f"/api/datasets/{mock_dataset.dataset_id}/access/1",
                    headers=admin_auth_headers,
                )

                assert response.status_code == 200
                assert "revoked" in response.json()["message"].lower()
            finally:
                test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_revoke_dataset_access_not_found(self, client, admin_auth_headers, test_app):
        """Test revoking non-existent access record returns 404."""
        mock_dataset = MockDataset()

        mock_results = [
            make_mock_result(scalar_one_or_none=None),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        with patch.object(datasets_module, 'check_dataset_access', return_value=True):
            try:
                response = await client.delete(
                    f"/api/datasets/{mock_dataset.dataset_id}/access/999",
                    headers=admin_auth_headers,
                )

                assert response.status_code == 404
            finally:
                test_app.dependency_overrides.clear()

    # ==================== Dataset Tasks Tests ====================

    @pytest.mark.asyncio
    async def test_list_dataset_tasks_success(self, client, auth_headers, test_app):
        """Test listing tasks associated with a dataset."""
        mock_dataset = MockDataset()

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        with patch.object(datasets_module, 'check_dataset_access', return_value=True):
            try:
                response = await client.get(
                    f"/api/datasets/{mock_dataset.dataset_id}/tasks",
                    headers=auth_headers,
                )

                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, list)
            finally:
                test_app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_dataset_tasks_permission_denied(self, client, auth_headers, test_app):
        """Test listing dataset tasks without read permission returns 403."""
        mock_dataset = MockDataset()

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        mock_session = MockSession(mock_results)

        async def override_get_session():
            yield mock_session

        test_app.dependency_overrides[datasets_module.get_session] = override_get_session

        with patch.object(datasets_module, 'check_dataset_access', return_value=False):
            try:
                response = await client.get(
                    f"/api/datasets/{mock_dataset.dataset_id}/tasks",
                    headers=auth_headers,
                )

                assert response.status_code == 403
            finally:
                test_app.dependency_overrides.clear()


class TestCheckDatasetAccess:
    """Unit tests for check_dataset_access helper function."""

    @pytest.mark.asyncio
    async def test_superuser_has_all_permissions(self):
        """Test that superuser has access to all datasets."""
        from algo_studio.api.routes.datasets import check_dataset_access

        mock_dataset = MockDataset()

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        session = MockSession(mock_results)
        mock_user = MockUser(is_superuser=True)

        result = await check_dataset_access(session, mock_user, "ds-123", "admin")
        assert result is True

    @pytest.mark.asyncio
    async def test_public_dataset_read_access(self):
        """Test that public datasets can be read by anyone."""
        from algo_studio.api.routes.datasets import check_dataset_access

        mock_dataset = MockDataset(is_public=True)

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        session = MockSession(mock_results)
        mock_user = MockUser(is_superuser=False)

        result = await check_dataset_access(session, mock_user, "ds-123", "read")
        assert result is True

    @pytest.mark.asyncio
    async def test_owner_has_all_permissions(self):
        """Test that dataset owner has access."""
        from algo_studio.api.routes.datasets import check_dataset_access

        mock_dataset = MockDataset(owner_id="owner-user", is_public=False)

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
        ]

        session = MockSession(mock_results)
        mock_user = MockUser(user_id="owner-user", is_superuser=False)

        result = await check_dataset_access(session, mock_user, "ds-123", "write")
        assert result is True

    @pytest.mark.asyncio
    async def test_explicit_access_grants_permission(self):
        """Test that explicit access in dataset_access table grants permission."""
        from algo_studio.api.routes.datasets import check_dataset_access

        mock_dataset = MockDataset(owner_id="other-user", is_public=False)
        mock_access = MockDatasetAccess(access_level="read")

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
            make_mock_result(scalar_one_or_none=mock_access),
        ]

        session = MockSession(mock_results)
        mock_user = MockUser(user_id="reader-user", is_superuser=False)

        result = await check_dataset_access(session, mock_user, "ds-123", "read")
        assert result is True

    @pytest.mark.asyncio
    async def test_insufficient_access_level(self):
        """Test that read-only access doesn't grant write permission."""
        from algo_studio.api.routes.datasets import check_dataset_access

        mock_dataset = MockDataset(owner_id="other-user", is_public=False)
        mock_access = MockDatasetAccess(access_level="read")

        mock_results = [
            make_mock_result(scalar_one_or_none=mock_dataset),
            make_mock_result(scalar_one_or_none=mock_access),
        ]

        session = MockSession(mock_results)
        mock_user = MockUser(user_id="reader-user", is_superuser=False)

        result = await check_dataset_access(session, mock_user, "ds-123", "write")
        assert result is False

    @pytest.mark.asyncio
    async def test_dataset_not_found(self):
        """Test that non-existent dataset returns False."""
        from algo_studio.api.routes.datasets import check_dataset_access

        mock_results = [
            make_mock_result(scalar_one_or_none=None),
        ]

        session = MockSession(mock_results)
        mock_user = MockUser(is_superuser=False)

        result = await check_dataset_access(session, mock_user, "non-existent", "read")
        assert result is False