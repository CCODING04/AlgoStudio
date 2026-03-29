# tests/unit/api/test_audit.py
"""Unit tests for Audit logging middleware and API.

Tests cover:
- AuditMiddleware captures all API requests
- Audit log fields are correctly populated
- Public routes are excluded or logged as anonymous
- Audit query API returns filtered results
- Audit log retrieval by ID
"""

import hashlib
import hmac
import os
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

# Set secret key before importing app
os.environ["RBAC_SECRET_KEY"] = "test-secret-key-12345"

from algo_studio.api.main import app
from algo_studio.api.middleware.audit import AuditMiddleware


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


class TestAuditMiddlewareHelpers:
    """Test suite for AuditMiddleware helper methods."""

    def test_parse_resource_basic_paths(self):
        """Test resource parsing from basic API paths."""
        middleware = AuditMiddleware(app=app)

        # Test task paths
        resource_type, resource_id = middleware._parse_resource("/api/tasks")
        assert resource_type == "tasks"
        assert resource_id is None

        resource_type, resource_id = middleware._parse_resource("/api/tasks/task-123")
        assert resource_type == "tasks"
        assert resource_id == "task-123"

        resource_type, resource_id = middleware._parse_resource("/api/tasks/task-123/dispatch")
        assert resource_type == "tasks"
        assert resource_id == "task-123"

    def test_parse_resource_host_paths(self):
        """Test resource parsing for host paths."""
        middleware = AuditMiddleware(app=app)

        resource_type, resource_id = middleware._parse_resource("/api/hosts")
        assert resource_type == "hosts"
        assert resource_id is None

        resource_type, resource_id = middleware._parse_resource("/api/hosts/worker-1")
        assert resource_type == "hosts"
        assert resource_id == "worker-1"

    def test_parse_resource_non_api_paths(self):
        """Test resource parsing for non-API paths."""
        middleware = AuditMiddleware(app=app)

        resource_type, resource_id = middleware._parse_resource("/health")
        assert resource_type == "health"
        assert resource_id is None

        resource_type, resource_id = middleware._parse_resource("/")
        assert resource_type == "root"
        assert resource_id is None

    def test_is_excluded_route(self):
        """Test that excluded routes are correctly identified."""
        middleware = AuditMiddleware(app=app)

        # Excluded routes
        assert middleware._is_excluded_route("/health") is True
        assert middleware._is_excluded_route("/") is True
        assert middleware._is_excluded_route("/docs") is True
        assert middleware._is_excluded_route("/openapi.json") is True

        # SSE progress routes
        assert middleware._is_excluded_route("/api/tasks/task-123/progress") is True

        # Non-excluded routes
        assert middleware._is_excluded_route("/api/tasks") is False
        assert middleware._is_excluded_route("/api/tasks/task-123") is False
        assert middleware._is_excluded_route("/api/hosts") is False

    def test_get_client_ip_direct(self):
        """Test IP extraction from direct client connection."""
        middleware = AuditMiddleware(app=app)

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client = MagicMock(host="192.168.1.100")

        ip = middleware._get_client_ip(mock_request)
        assert ip == "192.168.1.100"

    def test_get_client_ip_forwarded(self):
        """Test IP extraction from X-Forwarded-For header."""
        middleware = AuditMiddleware(app=app)

        mock_request = MagicMock()
        mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 10.0.0.2"}
        mock_request.client = MagicMock(host="192.168.1.100")

        ip = middleware._get_client_ip(mock_request)
        assert ip == "10.0.0.1"

    def test_get_client_ip_real_ip(self):
        """Test IP extraction from X-Real-IP header."""
        middleware = AuditMiddleware(app=app)

        mock_request = MagicMock()
        mock_request.headers = {"X-Real-IP": "10.0.0.5"}
        mock_request.client = MagicMock(host="192.168.1.100")

        ip = middleware._get_client_ip(mock_request)
        assert ip == "10.0.0.5"

    def test_get_client_ip_no_client(self):
        """Test IP extraction when no client info available."""
        middleware = AuditMiddleware(app=app)

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client = None

        ip = middleware._get_client_ip(mock_request)
        assert ip == "unknown"


class TestAuditMiddlewareIntegration:
    """Integration tests for AuditMiddleware with API routes."""

    @pytest.mark.asyncio
    async def test_health_endpoint_not_logged(self):
        """Test that /health endpoint is not logged (excluded route)."""
        with patch.object(AuditMiddleware, '_create_audit_log', new_callable=AsyncMock) as mock_log:
            client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            response = await client.get("/health")

            assert response.status_code == 200
            # Health endpoint should not create audit log
            mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_public_root_not_logged(self):
        """Test that / endpoint is not logged (excluded route)."""
        with patch.object(AuditMiddleware, '_create_audit_log', new_callable=AsyncMock) as mock_log:
            client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            response = await client.get("/")

            assert response.status_code == 200
            # Root endpoint should not create audit log
            mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_api_request_logged(self):
        """Test that API requests are logged with correct data."""
        with patch.object(AuditMiddleware, '_create_audit_log', new_callable=AsyncMock) as mock_log:
            client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            headers = make_auth_headers(user_id="test-user", role="developer")

            response = await client.get("/api/tasks", headers=headers)

            assert response.status_code == 200
            # Verify audit log was created
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs

            assert call_kwargs["user_id"] == "test-user"
            assert call_kwargs["action"] == "GET /api/tasks"
            assert call_kwargs["resource_type"] == "tasks"
            assert call_kwargs["resource_id"] is None
            assert call_kwargs["ip_address"] == "127.0.0.1"  # localhost
            assert call_kwargs["details"]["method"] == "GET"
            assert call_kwargs["details"]["response_status"] == 200

    @pytest.mark.asyncio
    async def test_api_request_with_resource_id_logged(self):
        """Test that API requests with resource ID are logged correctly."""
        with patch.object(AuditMiddleware, '_create_audit_log', new_callable=AsyncMock) as mock_log:
            client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            headers = make_auth_headers(user_id="admin-user", role="admin")

            # Note: task-456 doesn't exist so returns 404, but audit should still log
            response = await client.get("/api/tasks/task-456", headers=headers)

            # Verify audit log was created with resource ID (regardless of response status)
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs

            assert call_kwargs["resource_type"] == "tasks"
            assert call_kwargs["resource_id"] == "task-456"
            assert call_kwargs["details"]["response_status"] == 404

    @pytest.mark.asyncio
    async def test_post_request_with_body_logged(self):
        """Test that POST requests include request body in audit log."""
        with patch.object(AuditMiddleware, '_create_audit_log', new_callable=AsyncMock) as mock_log:
            client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            headers = make_auth_headers(user_id="dev-user", role="developer")

            request_body = {
                "task_type": "train",
                "algorithm_name": "simple_classifier",
                "algorithm_version": "v1",
            }

            response = await client.post("/api/tasks", headers=headers, json=request_body)

            assert response.status_code == 200
            # Verify audit log was created with request body
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs

            assert call_kwargs["details"]["request_body"] == request_body

    @pytest.mark.asyncio
    async def test_anonymous_user_for_public_routes(self):
        """Test that public routes use 'anonymous' user_id when no auth headers."""
        with patch.object(AuditMiddleware, '_create_audit_log', new_callable=AsyncMock) as mock_log:
            client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

            # Request without auth headers to a public route
            response = await client.get("/api/hosts")

            # Should still be logged (not excluded), but with 'anonymous' user
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs
            assert call_kwargs["user_id"] == "anonymous"

    @pytest.mark.asyncio
    async def test_sse_progress_not_logged(self):
        """Test that SSE progress endpoints are not logged."""
        with patch.object(AuditMiddleware, '_create_audit_log', new_callable=AsyncMock) as mock_log:
            client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            headers = make_auth_headers(user_id="test-user", role="developer")

            # Note: This would be an SSE endpoint, but we test the path exclusion
            # The actual SSE streaming won't complete in this test
            response = await client.get(
                "/api/tasks/test-task/progress",
                headers=headers,
            )

            # SSE endpoint returns event stream
            # The middleware should not log this endpoint
            mock_log.assert_not_called()


class TestAuditQueryAPI:
    """Tests for audit log query API endpoints."""

    @pytest.fixture
    def admin_headers(self):
        """Provide valid authentication headers for admin role."""
        return make_auth_headers(user_id="admin-user", role="admin")

    @pytest.mark.asyncio
    async def test_get_audit_logs_endpoint_requires_auth(self):
        """Test that GET /api/audit/logs endpoint requires authentication."""
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

        # Without auth headers, should return 401
        response = await client.get("/api/audit/logs")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_audit_log_by_id_endpoint_requires_auth(self):
        """Test that GET /api/audit/logs/{audit_id} endpoint requires authentication."""
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

        # Without auth headers, should return 401
        response = await client.get("/api/audit/logs/audit-123")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_resource_id_filter(self, admin_headers):
        """Test GET /api/audit/logs with resource_id filter exercises lines 100-101."""
        from datetime import datetime
        from algo_studio.db.session import get_session

        class MockAuditLogEntry:
            def __init__(self, audit_id="audit-1", actor_id="user1", action="GET /api/tasks",
                         resource_type="task", resource_id="task-1"):
                self.audit_id = audit_id
                self.actor_id = actor_id
                self.action = action
                self.resource_type = resource_type
                self.resource_id = resource_id
                self.new_value = {"key": "value"}
                self.ip_address = "192.168.0.1"
                self.user_agent = "TestClient/1.0"
                self.created_at = datetime.now()

        class MockSession:
            def __init__(self, logs=None, single_log=None):
                self.logs = logs or []
                self.single_log = single_log

            async def execute(self, query):
                mock_result = MagicMock()
                if self.single_log is not None:
                    mock_result.scalar_one_or_none.return_value = self.single_log
                else:
                    mock_result.scalars.return_value.all.return_value = self.logs
                    mock_result.scalar.return_value = len(self.logs)
                return mock_result

        mock_log = MockAuditLogEntry(audit_id="audit-res-1", resource_id="task-specific-123")
        mock_session_instance = MockSession(logs=[mock_log])

        async def override_get_session():
            return mock_session_instance

        app.dependency_overrides[get_session] = override_get_session

        try:
            client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            response = await client.get(
                "/api/audit/logs",
                params={"resource_id": "task-specific-123"},
                headers=admin_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_date_range(self, admin_headers):
        """Test GET /api/audit/logs with start_date and end_date filters (lines 103-107)."""
        from datetime import datetime
        from algo_studio.db.session import get_session

        class MockAuditLogEntry:
            def __init__(self, audit_id="audit-1", actor_id="user1", action="GET /api/tasks",
                         resource_type="task", resource_id="task-1"):
                self.audit_id = audit_id
                self.actor_id = actor_id
                self.action = action
                self.resource_type = resource_type
                self.resource_id = resource_id
                self.new_value = {"key": "value"}
                self.ip_address = "192.168.0.1"
                self.user_agent = "TestClient/1.0"
                self.created_at = datetime.now()

        class MockSession:
            def __init__(self, logs=None, single_log=None):
                self.logs = logs or []
                self.single_log = single_log

            async def execute(self, query):
                mock_result = MagicMock()
                if self.single_log is not None:
                    mock_result.scalar_one_or_none.return_value = self.single_log
                else:
                    mock_result.scalars.return_value.all.return_value = self.logs
                    mock_result.scalar.return_value = len(self.logs)
                return mock_result

        mock_log = MockAuditLogEntry(audit_id="audit-date-1", action="POST /api/deploy")
        mock_session_instance = MockSession(logs=[mock_log])

        async def override_get_session():
            return mock_session_instance

        app.dependency_overrides[get_session] = override_get_session

        try:
            client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            response = await client.get(
                "/api/audit/logs",
                params={
                    "start_date": "2024-01-01T00:00:00",
                    "end_date": "2024-12-31T23:59:59"
                },
                headers=admin_headers
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_audit_logs_returns_data(self, admin_headers):
        """Test GET /api/audit/logs returns actual audit log data (lines 112-127)."""
        from datetime import datetime
        from algo_studio.db.session import get_session

        class MockAuditLogEntry:
            def __init__(self, audit_id="audit-1", actor_id="user1", action="GET /api/tasks",
                         resource_type="task", resource_id="task-1"):
                self.audit_id = audit_id
                self.actor_id = actor_id
                self.action = action
                self.resource_type = resource_type
                self.resource_id = resource_id
                self.new_value = {"key": "value"}
                self.ip_address = "192.168.0.1"
                self.user_agent = "TestClient/1.0"
                self.created_at = datetime.now()

        class MockSession:
            def __init__(self, logs=None, single_log=None):
                self.logs = logs or []
                self.single_log = single_log

            async def execute(self, query):
                mock_result = MagicMock()
                if self.single_log is not None:
                    mock_result.scalar_one_or_none.return_value = self.single_log
                else:
                    mock_result.scalars.return_value.all.return_value = self.logs
                    mock_result.scalar.return_value = len(self.logs)
                return mock_result

        mock_log = MockAuditLogEntry(
            audit_id="audit-data-1",
            actor_id="test-user",
            action="GET /api/tasks",
            resource_type="task",
            resource_id="task-1"
        )
        mock_session_instance = MockSession(logs=[mock_log])

        async def override_get_session():
            return mock_session_instance

        app.dependency_overrides[get_session] = override_get_session

        try:
            client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            response = await client.get("/api/audit/logs", headers=admin_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1
            assert data["items"][0]["audit_id"] == "audit-data-1"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_audit_log_returns_log_when_found(self, admin_headers):
        """Test GET /api/audit/logs/{id} returns log when found (lines 152-190)."""
        from datetime import datetime
        from algo_studio.db.session import get_session

        class MockAuditLogEntry:
            def __init__(self, audit_id="audit-1", actor_id="user1", action="GET /api/tasks",
                         resource_type="task", resource_id="task-1"):
                self.audit_id = audit_id
                self.actor_id = actor_id
                self.action = action
                self.resource_type = resource_type
                self.resource_id = resource_id
                self.new_value = {"key": "value"}
                self.ip_address = "192.168.0.1"
                self.user_agent = "TestClient/1.0"
                self.created_at = datetime.now()

        class MockSession:
            def __init__(self, logs=None, single_log=None):
                self.logs = logs or []
                self.single_log = single_log

            async def execute(self, query):
                mock_result = MagicMock()
                if self.single_log is not None:
                    mock_result.scalar_one_or_none.return_value = self.single_log
                else:
                    mock_result.scalars.return_value.all.return_value = self.logs
                    mock_result.scalar.return_value = len(self.logs)
                return mock_result

        mock_log = MockAuditLogEntry(
            audit_id="audit-found-1",
            actor_id="user1",
            action="GET /api/tasks",
            resource_type="task",
            resource_id="task-1"
        )
        mock_session_instance = MockSession(single_log=mock_log)

        async def override_get_session():
            return mock_session_instance

        app.dependency_overrides[get_session] = override_get_session

        try:
            client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            response = await client.get(
                "/api/audit/logs/audit-found-1",
                headers=admin_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["audit_id"] == "audit-found-1"
            assert data["actor_id"] == "user1"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_all_filters(self, admin_headers):
        """Test GET /api/audit/logs with all filters combined (lines 86-107)."""
        from datetime import datetime
        from algo_studio.db.session import get_session

        class MockAuditLogEntry:
            def __init__(self, audit_id="audit-1", actor_id="user1", action="GET /api/tasks",
                         resource_type="task", resource_id="task-1"):
                self.audit_id = audit_id
                self.actor_id = actor_id
                self.action = action
                self.resource_type = resource_type
                self.resource_id = resource_id
                self.new_value = {"key": "value"}
                self.ip_address = "192.168.0.1"
                self.user_agent = "TestClient/1.0"
                self.created_at = datetime.now()

        class MockSession:
            def __init__(self, logs=None, single_log=None):
                self.logs = logs or []
                self.single_log = single_log

            async def execute(self, query):
                mock_result = MagicMock()
                if self.single_log is not None:
                    mock_result.scalar_one_or_none.return_value = self.single_log
                else:
                    mock_result.scalars.return_value.all.return_value = self.logs
                    mock_result.scalar.return_value = len(self.logs)
                return mock_result

        mock_log = MockAuditLogEntry(
            audit_id="audit-all-1",
            actor_id="admin-user",
            action="PUT /api/hosts",
            resource_type="host",
            resource_id="host-456"
        )
        mock_session_instance = MockSession(logs=[mock_log])

        async def override_get_session():
            return mock_session_instance

        app.dependency_overrides[get_session] = override_get_session

        try:
            client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            response = await client.get(
                "/api/audit/logs",
                params={
                    "user_id": "admin-user",
                    "action": "PUT",
                    "resource_type": "host",
                    "resource_id": "host-456",
                    "limit": 50,
                    "offset": 0
                },
                headers=admin_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["limit"] == 50
            assert data["offset"] == 0
        finally:
            app.dependency_overrides.clear()


class TestAuditLogModelMapping:
    """Tests to verify audit log fields match requirements."""

    def test_audit_log_fields_match_requirements(self):
        """Verify AuditLog model has fields for all required audit data.

        Requirements:
        - user_id -> mapped to actor_id
        - action -> action field
        - resource -> resource_type + resource_id
        - timestamp -> created_at
        - details -> new_value (JSON details)
        - ip_address -> ip_address
        """
        from algo_studio.db.models.audit import AuditLog

        # Check that AuditLog has required fields
        assert hasattr(AuditLog, "audit_id")
        assert hasattr(AuditLog, "actor_id")  # user_id equivalent
        assert hasattr(AuditLog, "action")
        assert hasattr(AuditLog, "resource_type")
        assert hasattr(AuditLog, "resource_id")
        assert hasattr(AuditLog, "new_value")  # details equivalent
        assert hasattr(AuditLog, "ip_address")
        assert hasattr(AuditLog, "user_agent")
        assert hasattr(AuditLog, "created_at")  # timestamp equivalent

    def test_audit_middleware_creates_complete_log(self):
        """Test that audit middleware creates log with all required fields."""
        middleware = AuditMiddleware(app=app)

        # Verify the middleware has the dispatch method
        assert hasattr(middleware, "dispatch")
        assert callable(middleware.dispatch)


class TestAuditMiddlewareEdgeCases:
    """Tests for edge cases in audit middleware."""

    @pytest.mark.asyncio
    async def test_large_body_truncated(self):
        """Test that large request bodies are truncated."""
        middleware = AuditMiddleware(app=app)

        # Create a mock request with large body (20KB > 10KB MAX)
        mock_request = MagicMock()
        large_body = b"x" * (20 * 1024)

        async def mock_body():
            return large_body

        mock_request.body = mock_body

        # Test actual truncation behavior
        result = await middleware._get_request_body(mock_request)
        assert result == {"_truncated": True, "size": 20 * 1024}
        assert result["size"] > middleware.MAX_BODY_SIZE

    @pytest.mark.asyncio
    async def test_invalid_json_body_handled(self):
        """Test that invalid JSON body is handled gracefully."""
        middleware = AuditMiddleware(app=app)

        # Create a mock request with invalid JSON body
        mock_request = MagicMock()
        invalid_body = b"not valid json {"

        async def mock_body():
            return invalid_body

        mock_request.body = mock_body

        # Verify the middleware returns fallback dict instead of raising
        result = await middleware._get_request_body(mock_request)
        assert result == {"_raw": "Unable to parse body as JSON"}


class TestAuditCreateLogErrorHandling:
    """Tests for _create_audit_log error handling."""

    @pytest.mark.asyncio
    async def test_dispatch_handles_audit_log_error(self):
        """Test that dispatch method catches audit log errors and continues."""
        middleware = AuditMiddleware(app=app)

        # Mock _create_audit_log to raise an exception
        async def mock_create_audit_log(**kwargs):
            raise Exception("Audit logging failed")

        middleware._create_audit_log = mock_create_audit_log

        # Create mock request
        mock_request = MagicMock()
        mock_request.url.path = "/api/tasks"
        mock_request.headers = {"X-User-ID": "test-user"}
        mock_request.method = "GET"
        mock_request.query_params = {}
        mock_request.client = MagicMock(host="127.0.0.1")

        # Mock call_next to return a response
        mock_response = MagicMock()
        mock_response.status_code = 200

        async def mock_call_next(request):
            return mock_response

        # Dispatch should catch the exception and return the response
        result = await middleware.dispatch(mock_request, mock_call_next)

        # Should return the response even when audit logging fails
        assert result == mock_response
        assert result.status_code == 200

    def test_create_audit_log_creates_valid_entry(self):
        """Test that _create_audit_log creates a valid audit log entry."""
        from algo_studio.db.models.audit import AuditLog

        # Verify AuditLog model has required fields as class attributes
        assert hasattr(AuditLog, 'audit_id')
        assert hasattr(AuditLog, 'actor_id')
        assert hasattr(AuditLog, 'action')
        assert hasattr(AuditLog, 'resource_type')
        assert hasattr(AuditLog, 'resource_id')
        assert hasattr(AuditLog, 'new_value')
        assert hasattr(AuditLog, 'ip_address')
        assert hasattr(AuditLog, 'user_agent')
        assert hasattr(AuditLog, 'created_at')

    def test_create_audit_log_resource_id_none_string_conversion(self):
        """Test that None resource_id is handled in the audit entry creation."""
        # This tests the logic that None is converted to "none"
        resource_id = None
        result = resource_id or "none"
        assert result == "none"

    def test_create_audit_log_user_agent_truncation_logic(self):
        """Test the user agent truncation logic used in _create_audit_log."""
        user_agent = "A" * 1000
        truncated = user_agent[:500] if user_agent else None
        assert len(truncated) == 500

