"""
RBAC Middleware Performance Benchmark

Tests the overhead of RBAC middleware for permission checking.
Target: < 10ms per request

Benchmark scenarios:
1. Public route access (no auth overhead)
2. Protected route with valid auth (HMAC signature verification)
3. Permission checking overhead
4. Role hierarchy validation
"""

import hashlib
import hmac
import os
import time
import statistics
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

# Add src to path
import sys
from pathlib import Path
_project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_project_root / "src"))

from algo_studio.api.middleware.rbac import (
    RBACMiddleware,
    Permission,
    Role,
    ROLE_PERMISSIONS,
    require_permission,
    require_role,
)
from algo_studio.db.models.user import User


# Test configuration
TEST_SECRET_KEY = "test-secret-key-for-benchmark"
os.environ["RBAC_SECRET_KEY"] = TEST_SECRET_KEY


def generate_signature(user_id: str, timestamp: str) -> str:
    """Generate HMAC signature for testing."""
    message = f"{user_id}:{timestamp}"
    return hmac.new(
        TEST_SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()


class TestRBACMiddlewareBenchmark:
    """RBAC Middleware Performance Tests"""

    @pytest.fixture
    def middleware(self):
        """Create RBAC middleware instance."""
        return RBACMiddleware(app=Mock())

    @pytest.fixture
    def valid_headers(self):
        """Generate valid auth headers."""
        timestamp = str(int(time.time()))
        return {
            "X-User-ID": "test-user",
            "X-User-Role": "developer",
            "X-Timestamp": timestamp,
            "X-Signature": generate_signature("test-user", timestamp),
        }

    def test_public_route_no_auth_overhead(self, middleware):
        """Test that public routes have no auth overhead.

        Public routes: /health, /, /docs, /openapi.json, /redoc
        Target: < 1ms (near-zero overhead)
        """
        public_routes = ["/health", "/", "/docs", "/openapi.json", "/redoc"]
        latencies = []

        for _ in range(100):
            request = Mock()
            request.url.path = "/health"
            request.headers = {}

            start = time.perf_counter()
            result = middleware._is_public_route(request.url.path)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nPublic Route Check: avg={avg:.4f}ms, p50={p50:.4f}ms, p95={p95:.4f}ms")
        assert p95 < 1.0, f"Public route check p95 {p95:.4f}ms exceeds 1ms"

    def test_signature_verification_overhead(self, middleware):
        """Test HMAC signature verification overhead.

        Target: < 5ms per verification
        """
        # Patch the global secret key before testing
        import algo_studio.api.middleware.rbac as rbac_module
        rbac_module._rbac_secret_key = TEST_SECRET_KEY

        latencies = []
        timestamp = str(int(time.time()))

        for i in range(100):
            user_id = f"user-{i % 10}"
            message = f"{user_id}:{timestamp}"
            signature = hmac.new(
                TEST_SECRET_KEY.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()

            start = time.perf_counter()
            result = middleware._verify_signature(user_id, timestamp, signature)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nSignature Verification: avg={avg:.4f}ms, p50={p50:.4f}ms, p95={p95:.4f}ms")
        assert result is True, "Signature verification should succeed with valid signature"
        assert p95 < 5.0, f"Signature verification p95 {p95:.4f}ms exceeds 5ms"

    def test_signature_verification_reject_invalid(self, middleware):
        """Test that invalid signatures are properly rejected.

        Target: < 5ms per verification
        """
        latencies = []
        timestamp = str(int(time.time()))

        for _ in range(100):
            start = time.perf_counter()
            result = middleware._verify_signature("user", timestamp, "invalid-signature")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]

        print(f"\nInvalid Signature Rejection: p95={p95:.4f}ms")
        assert result is False, "Invalid signature should be rejected"
        assert p95 < 5.0, f"Invalid signature rejection p95 {p95:.4f}ms exceeds 5ms"

    def test_permission_check_overhead(self):
        """Test permission checking overhead.

        Target: < 2ms per check
        """
        user = User(
            user_id="test-user",
            username="testuser",
            role="developer",
            is_active=True,
            is_superuser=False,
        )

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            has_perm = user.has_permission("task.read")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nPermission Check: avg={avg:.4f}ms, p50={p50:.4f}ms, p95={p95:.4f}ms")
        assert has_perm is True, "Developer should have task.read permission"
        assert p95 < 2.0, f"Permission check p95 {p95:.4f}ms exceeds 2ms"

    def test_role_permission_mapping_lookup(self):
        """Test role to permission mapping lookup.

        Target: < 1ms
        """
        latencies = []

        for _ in range(100):
            start = time.perf_counter()
            perms = ROLE_PERMISSIONS.get(Role.DEVELOPER, [])
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]

        print(f"\nRole Permission Mapping: p95={p95:.4f}ms")
        assert Permission.TASK_READ in perms
        assert Permission.TASK_CREATE in perms
        assert Permission.TASK_DELETE in perms
        assert p95 < 1.0, f"Role permission lookup p95 {p95:.4f}ms exceeds 1ms"

    def test_get_required_permissions_lookup(self, middleware):
        """Test route permission lookup.

        Target: < 1ms
        """
        latencies = []

        test_cases = [
            ("/api/tasks", "GET", Permission.TASK_READ),
            ("/api/tasks", "POST", Permission.TASK_CREATE),
            ("/api/tasks/abc123", "GET", Permission.TASK_READ),
            ("/api/tasks/abc123", "DELETE", Permission.TASK_DELETE),
        ]

        for _ in range(100):
            for path, method, expected_perm in test_cases:
                start = time.perf_counter()
                perms = middleware._get_required_permissions(path, method)
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nRoute Permission Lookup: avg={avg:.4f}ms, p50={p50:.4f}ms, p95={p95:.4f}ms")
        assert p95 < 1.0, f"Permission lookup p95 {p95:.4f}ms exceeds 1ms"

    def test_full_middleware_request_overhead(self, middleware, valid_headers):
        """Test full middleware request processing overhead.

        Target: < 10ms per request
        """
        import asyncio

        async def run_test():
            latencies = []

            for _ in range(100):
                request = Mock()
                request.url.path = "/api/tasks"
                request.method = "GET"
                request.headers = valid_headers
                request.state = Mock()

                async def call_next(req):
                    return Mock(status_code=200)

                start = time.perf_counter()
                response = await middleware.dispatch(request, call_next)
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)

            return latencies

        latencies = asyncio.get_event_loop().run_until_complete(run_test())

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)

        print(f"\nFull Middleware Overhead: avg={avg:.4f}ms, p50={p50:.4f}ms, p95={p95:.4f}ms, p99={p99:.4f}ms")
        assert p95 < 10.0, f"Full middleware overhead p95 {p95:.4f}ms exceeds 10ms target"

    def test_unauthorized_request_quick_reject(self, middleware):
        """Test unauthorized request rejection speed.

        Target: < 5ms (fast rejection without full processing)
        """
        import asyncio

        async def run_test():
            latencies = []

            # Missing user_id
            for _ in range(100):
                request = Mock()
                request.url.path = "/api/tasks"
                request.method = "GET"
                request.headers = {}  # No auth headers

                async def call_next(req):
                    return Mock(status_code=200)

                start = time.perf_counter()
                response = await middleware.dispatch(request, call_next)
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)

            return latencies

        latencies = asyncio.get_event_loop().run_until_complete(run_test())

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nUnauthorized Rejection: avg={avg:.4f}ms, p50={p50:.4f}ms, p95={p95:.4f}ms")
        assert p95 < 5.0, f"Unauthorized rejection p95 {p95:.4f}ms exceeds 5ms"


class TestRBACPermissionHierarchy:
    """Test role hierarchy and permission inheritance."""

    def test_admin_has_all_permissions(self):
        """Admin role should have all permissions."""
        admin = User(
            user_id="admin",
            username="admin",
            role="admin",
            is_active=True,
            is_superuser=True,
        )

        permissions_to_check = [
            "task.read", "task.create", "task.delete",
            "admin.user", "admin.quota", "admin.alert"
        ]

        for perm in permissions_to_check:
            assert admin.has_permission(perm) is True, f"Admin should have {perm}"

    def test_developer_permissions(self):
        """Developer role should have task permissions only."""
        developer = User(
            user_id="dev",
            username="developer",
            role="developer",
            is_active=True,
            is_superuser=False,
        )

        assert developer.has_permission("task.read") is True
        assert developer.has_permission("task.create") is True
        assert developer.has_permission("task.delete") is True
        assert developer.has_permission("admin.user") is False

    def test_viewer_permissions(self):
        """Viewer role should have read-only permissions."""
        viewer = User(
            user_id="viewer",
            username="viewer",
            role="viewer",
            is_active=True,
            is_superuser=False,
        )

        assert viewer.has_permission("task.read") is True
        assert viewer.has_permission("task.create") is False
        assert viewer.has_permission("task.delete") is False


class TestRBACSignatureEdgeCases:
    """Test signature verification edge cases."""

    @pytest.fixture
    def middleware(self):
        return RBACMiddleware(app=Mock())

    def test_expired_timestamp_rejected(self, middleware):
        """Test that expired timestamps are rejected."""
        # Timestamp from 10 minutes ago
        old_timestamp = str(int(time.time()) - 600)
        signature = generate_signature("user", old_timestamp)

        result = middleware._verify_signature("user", old_timestamp, signature)

        assert result is False, "Expired timestamp should be rejected"

    def test_future_timestamp_rejected(self, middleware):
        """Test that future timestamps are rejected."""
        # Timestamp 10 minutes in the future
        future_timestamp = str(int(time.time()) + 600)
        signature = generate_signature("user", future_timestamp)

        result = middleware._verify_signature("user", future_timestamp, signature)

        assert result is False, "Future timestamp should be rejected"

    def test_empty_signature_rejected(self, middleware):
        """Test that empty signatures are rejected."""
        timestamp = str(int(time.time()))

        result = middleware._verify_signature("user", timestamp, "")

        assert result is False, "Empty signature should be rejected"

    def test_missing_secret_key_rejects_all(self, middleware):
        """Test that missing secret key rejects all requests."""
        original_key = os.environ.get("RBAC_SECRET_KEY")
        try:
            os.environ.pop("RBAC_SECRET_KEY", None)

            # Reload module to pick up new secret
            import importlib
            import algo_studio.api.middleware.rbac as rbac_module
            rbac_module._rbac_secret_key = ""

            result = middleware._verify_signature("user", str(int(time.time())), "any")

            assert result is False, "Missing secret key should reject all signatures"
        finally:
            if original_key:
                os.environ["RBAC_SECRET_KEY"] = original_key
                rbac_module._rbac_secret_key = original_key


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
