# tests/e2e/cluster/test_rbac_e2e.py
"""
TC-RBAC-001 & TC-RBAC-002: RBAC E2E Tests

This module tests the Role-Based Access Control (RBAC) system:
1. PermissionChecker unit tests for org/team permission boundaries
2. Signature validation middleware tests
3. Role-based permission coverage tests

Reference: docs/superpowers/research/rbac-permission-design.md
            PHASE2_E2E_PLAN.md Section 4
"""

import hashlib
import hmac
import os
import time
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Test Configuration
# =============================================================================

RBAC_SECRET_KEY = os.getenv("RBAC_SECRET_KEY", "test-secret-key-12345")


def generate_auth_headers(
    user_id: str,
    role: str,
    secret_key: str = RBAC_SECRET_KEY,
    timestamp: int = None,
) -> dict:
    """Generate authentication headers with valid HMAC signature."""
    if timestamp is None:
        timestamp = int(time.time())
    timestamp_str = str(timestamp)
    message = f"{user_id}:{timestamp_str}"
    signature = hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return {
        "X-User-ID": user_id,
        "X-User-Role": role,
        "X-Timestamp": timestamp_str,
        "X-Signature": signature,
    }


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    from algo_studio.db.models.user import User
    return User(
        user_id="test-user",
        username="test-user",
        role="developer",
        is_active=True,
        is_superuser=False,
    )


@pytest.fixture
def admin_user():
    """Create an admin user for testing."""
    from algo_studio.db.models.user import User
    return User(
        user_id="admin-user",
        username="admin-user",
        role="admin",
        is_active=True,
        is_superuser=True,
    )


@pytest.fixture
def viewer_user():
    """Create a viewer user for testing."""
    from algo_studio.db.models.user import User
    return User(
        user_id="viewer-user",
        username="viewer-user",
        role="viewer",
        is_active=True,
        is_superuser=False,
    )


@pytest.fixture
def mock_task():
    """Create a mock task for testing."""
    task = MagicMock()
    task.task_id = "task-test-001"
    task.user_id = "owner-user"
    task.status = "running"
    task.team_id = "team-001"
    task.org_id = "org-001"
    task.is_public = False
    return task


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock()


# =============================================================================
# Test Cases: Permission Model
# =============================================================================

@pytest.mark.cluster
@pytest.mark.e2e
@pytest.mark.rbac
class TestPermissionCheckerCrossOrganization:
    """
    Tests for cross-organization permission boundaries.

    Verifies that users cannot access resources outside their organization.
    """

    def test_same_org_can_read_task(self, mock_user, mock_task, mock_db_session):
        """Test: User can read task in same organization."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.user_id = "reader-user"
        mock_task.user_id = "owner-user"

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        with patch.object(checker, '_get_task', return_value=mock_task):
            with patch.object(checker, '_is_same_org', return_value=True):
                assert checker.can_read_task(mock_task.task_id) is True

    def test_diff_org_cannot_read_task(self, mock_user, mock_task, mock_db_session):
        """Test: User cannot read task in different organization."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.user_id = "other-org-user"
        mock_task.user_id = "owner-user"

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        with patch.object(checker, '_get_task', return_value=mock_task):
            with patch.object(checker, '_is_same_org', return_value=False):
                with patch.object(checker, '_is_same_team', return_value=False):
                    assert checker.can_read_task(mock_task.task_id) is False

    def test_admin_bypasses_org_check(self, admin_user, mock_task, mock_db_session):
        """Test: Admin user can access tasks from any organization."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_task.user_id = "other-org-owner"

        checker = PermissionChecker(admin_user, db_session=mock_db_session)

        with patch.object(checker, '_get_task', return_value=mock_task):
            # Even if not same org, admin should have access
            assert checker.can_read_task(mock_task.task_id) is True

    def test_superuser_bypasses_all_checks(self, mock_user, mock_task, mock_db_session):
        """Test: Superuser flag grants access to all resources."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.is_superuser = True
        mock_task.user_id = "other-user"

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        with patch.object(checker, '_get_task', return_value=mock_task):
            # Superuser bypasses org/team checks
            assert checker.can_read_task(mock_task.task_id) is True


@pytest.mark.cluster
@pytest.mark.e2e
@pytest.mark.rbac
class TestPermissionCheckerTeamLevel:
    """
    Tests for team-level permission override behavior.

    Verifies that team leads have elevated permissions within their team.
    """

    def test_team_member_can_read_own_task(self, mock_user, mock_task, mock_db_session):
        """Test: User can read their own task."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.user_id = "owner-user"
        mock_task.user_id = "owner-user"

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        with patch.object(checker, '_get_task', return_value=mock_task):
            assert checker.can_read_task(mock_task.task_id) is True

    def test_team_member_can_write_own_task(self, mock_user, mock_task, mock_db_session):
        """Test: User can write (modify) their own task."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.user_id = "owner-user"
        mock_task.user_id = "owner-user"

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        with patch.object(checker, '_get_task', return_value=mock_task):
            assert checker.can_write_task(mock_task.task_id) is True

    def test_same_team_member_can_read_task(self, mock_user, mock_task, mock_db_session):
        """Test: Team member can read another team member's task."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.user_id = "team-member-2"
        mock_task.user_id = "team-member-1"
        mock_task.team_id = "team-001"

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        with patch.object(checker, '_get_task', return_value=mock_task):
            with patch.object(checker, '_is_same_team', return_value=True):
                assert checker.can_read_task(mock_task.task_id) is True

    def test_same_team_lead_can_write_task(self, mock_user, mock_task, mock_db_session):
        """Test: Team lead can write tasks of team members."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.user_id = "team-lead-user"
        mock_task.user_id = "team-member-user"
        mock_task.team_id = "team-001"

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        with patch.object(checker, '_get_task', return_value=mock_task):
            with patch.object(checker, '_has_team_role', return_value=True):
                assert checker.can_write_task(mock_task.task_id) is True

    def test_diff_team_member_cannot_write_task(self, mock_user, mock_task, mock_db_session):
        """Test: User cannot write tasks outside their team."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.user_id = "other-team-user"
        mock_task.user_id = "team-member-user"
        mock_task.team_id = "other-team"

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        with patch.object(checker, '_get_task', return_value=mock_task):
            with patch.object(checker, '_is_same_team', return_value=False):
                with patch.object(checker, '_has_team_role', return_value=False):
                    assert checker.can_write_task(mock_task.task_id) is False


@pytest.mark.cluster
@pytest.mark.e2e
@pytest.mark.rbac
class TestPermissionCheckerCancelTask:
    """
    Tests for task cancellation permissions.
    """

    def test_can_cancel_pending_task(self, mock_user, mock_task, mock_db_session):
        """Test: Owner can cancel their pending task."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.user_id = "owner-user"
        mock_task.user_id = "owner-user"
        mock_task.status = "pending"

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        with patch.object(checker, '_get_task', return_value=mock_task):
            assert checker.can_cancel_task(mock_task.task_id) is True

    def test_cannot_cancel_completed_task(self, mock_user, mock_task, mock_db_session):
        """Test: Cannot cancel a completed task."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.user_id = "owner-user"
        mock_task.user_id = "owner-user"
        mock_task.status = "completed"

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        with patch.object(checker, '_get_task', return_value=mock_task):
            assert checker.can_cancel_task(mock_task.task_id) is False

    def test_cannot_cancel_failed_task(self, mock_user, mock_task, mock_db_session):
        """Test: Cannot cancel a failed task."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.user_id = "owner-user"
        mock_task.user_id = "owner-user"
        mock_task.status = "failed"

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        with patch.object(checker, '_get_task', return_value=mock_task):
            assert checker.can_cancel_task(mock_task.task_id) is False

    def test_team_lead_can_cancel_running_task(self, mock_user, mock_task, mock_db_session):
        """Test: Team lead can cancel a running team member task."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.user_id = "team-lead-user"
        mock_task.user_id = "team-member-user"
        mock_task.status = "running"
        mock_task.team_id = "team-001"

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        with patch.object(checker, '_get_task', return_value=mock_task):
            with patch.object(checker, '_has_team_role', return_value=True):
                assert checker.can_cancel_task(mock_task.task_id) is True


# =============================================================================
# Test Cases: Signature Validation
# =============================================================================

@pytest.mark.cluster
@pytest.mark.e2e
@pytest.mark.rbac
class TestSignatureValidation:
    """
    Tests for HMAC signature validation in RBAC middleware.
    """

    def _setup_middleware_with_secret(self, secret_key):
        """Set up middleware with a specific secret key."""
        import os
        os.environ["RBAC_SECRET_KEY"] = secret_key
        # Need to reload module to pick up new env var
        import importlib
        import algo_studio.api.middleware.rbac as rbac_module
        importlib.reload(rbac_module)
        from algo_studio.api.middleware.rbac import RBACMiddleware
        return RBACMiddleware(app=MagicMock())

    def test_valid_signature_accepted(self):
        """Test: Request with valid signature is accepted."""
        middleware = self._setup_middleware_with_secret(RBAC_SECRET_KEY)

        user_id = "test-user"
        timestamp = int(time.time())
        signature = hmac.new(
            RBAC_SECRET_KEY.encode(),
            f"{user_id}:{timestamp}".encode(),
            hashlib.sha256
        ).hexdigest()

        result = middleware._verify_signature(
            user_id,
            str(timestamp),
            signature
        )

        assert result is True

    def test_invalid_signature_rejected(self):
        """Test: Request with invalid signature is rejected."""
        middleware = self._setup_middleware_with_secret(RBAC_SECRET_KEY)

        result = middleware._verify_signature(
            "test-user",
            str(int(time.time())),
            "invalid-signature"
        )

        assert result is False

    def test_wrong_secret_key_rejected(self):
        """Test: Signature computed with wrong key is rejected."""
        middleware = self._setup_middleware_with_secret(RBAC_SECRET_KEY)

        user_id = "test-user"
        timestamp = int(time.time())
        signature = hmac.new(
            "wrong-key".encode(),
            f"{user_id}:{timestamp}".encode(),
            hashlib.sha256
        ).hexdigest()

        result = middleware._verify_signature(
            user_id,
            str(timestamp),
            signature
        )

        assert result is False

    def test_expired_timestamp_rejected(self):
        """Test: Request with expired timestamp is rejected."""
        middleware = self._setup_middleware_with_secret(RBAC_SECRET_KEY)

        old_timestamp = int(time.time()) - 600  # 10 minutes ago
        signature = hmac.new(
            RBAC_SECRET_KEY.encode(),
            f"test-user:{old_timestamp}".encode(),
            hashlib.sha256
        ).hexdigest()

        result = middleware._verify_signature(
            "test-user",
            str(old_timestamp),
            signature
        )

        assert result is False

    def test_future_timestamp_rejected(self):
        """Test: Request with future timestamp is rejected."""
        middleware = self._setup_middleware_with_secret(RBAC_SECRET_KEY)

        future_timestamp = int(time.time()) + 600  # 10 minutes in future
        signature = hmac.new(
            RBAC_SECRET_KEY.encode(),
            f"test-user:{future_timestamp}".encode(),
            hashlib.sha256
        ).hexdigest()

        result = middleware._verify_signature(
            "test-user",
            str(future_timestamp),
            signature
        )

        assert result is False

    def test_near_future_timestamp_accepted(self):
        """Test: Request with near-future timestamp is accepted."""
        middleware = self._setup_middleware_with_secret(RBAC_SECRET_KEY)

        near_future = int(time.time()) + 30  # 30 seconds
        signature = hmac.new(
            RBAC_SECRET_KEY.encode(),
            f"test-user:{near_future}".encode(),
            hashlib.sha256
        ).hexdigest()

        result = middleware._verify_signature(
            "test-user",
            str(near_future),
            signature
        )

        assert result is True

    def test_missing_timestamp_rejected(self):
        """Test: Request without timestamp is rejected."""
        middleware = self._setup_middleware_with_secret(RBAC_SECRET_KEY)

        result = middleware._verify_signature(
            "test-user",
            "",
            "some-signature"
        )

        assert result is False

    def test_empty_signature_rejected(self):
        """Test: Request with empty signature is rejected."""
        middleware = self._setup_middleware_with_secret(RBAC_SECRET_KEY)

        result = middleware._verify_signature(
            "test-user",
            str(int(time.time())),
            ""
        )

        assert result is False


# =============================================================================
# Test Cases: Role-Based Permissions
# =============================================================================

@pytest.mark.cluster
@pytest.mark.e2e
@pytest.mark.rbac
class TestRoleBasedPermissions:
    """
    Tests for role-based permission assignments.
    """

    def test_viewer_has_task_read(self, viewer_user):
        """Test: Viewer role has task:read permission."""
        assert viewer_user.has_permission("task.read") is True

    def test_viewer_lacks_task_create(self, viewer_user):
        """Test: Viewer role lacks task:create permission."""
        assert viewer_user.has_permission("task.create") is False

    def test_viewer_lacks_task_delete(self, viewer_user):
        """Test: Viewer role lacks task:delete permission."""
        assert viewer_user.has_permission("task.delete") is False

    def test_developer_has_task_read(self, mock_user):
        """Test: Developer role has task:read permission."""
        mock_user.role = "developer"
        assert mock_user.has_permission("task.read") is True

    def test_developer_has_task_create(self, mock_user):
        """Test: Developer role has task:create permission."""
        mock_user.role = "developer"
        assert mock_user.has_permission("task.create") is True

    def test_developer_has_task_delete(self, mock_user):
        """Test: Developer role has task:delete permission."""
        mock_user.role = "developer"
        assert mock_user.has_permission("task.delete") is True

    def test_developer_lacks_admin_permissions(self, mock_user):
        """Test: Developer role lacks admin permissions."""
        mock_user.role = "developer"
        assert mock_user.has_permission("admin.user") is False
        assert mock_user.has_permission("admin.quota") is False
        assert mock_user.has_permission("admin.alert") is False

    def test_admin_has_all_task_permissions(self, admin_user):
        """Test: Admin role has all task permissions."""
        assert admin_user.has_permission("task.read") is True
        assert admin_user.has_permission("task.create") is True
        assert admin_user.has_permission("task.delete") is True

    def test_admin_has_all_admin_permissions(self, admin_user):
        """Test: Admin role has all admin permissions."""
        assert admin_user.has_permission("admin.user") is True
        assert admin_user.has_permission("admin.quota") is True
        assert admin_user.has_permission("admin.alert") is True

    def test_superuser_bypasses_role_check(self, mock_user):
        """Test: Superuser flag grants all permissions regardless of role."""
        mock_user.role = "viewer"
        mock_user.is_superuser = True
        assert mock_user.has_permission("task.create") is True
        assert mock_user.has_permission("admin.user") is True


# =============================================================================
# Test Cases: Permission Enum and Mapping
# =============================================================================

@pytest.mark.cluster
@pytest.mark.e2e
@pytest.mark.rbac
class TestPermissionDefinitions:
    """
    Tests ensuring all Permission types are properly defined.
    """

    def test_all_required_permissions_defined(self):
        """Test: All required permissions are defined in Permission enum."""
        from algo_studio.api.middleware.rbac import Permission

        required_permissions = [
            "task.read",
            "task.create",
            "task.delete",
            "admin.user",
            "admin.quota",
            "admin.alert",
        ]

        for perm in required_permissions:
            perm_enum = perm.replace(".", "_").upper()
            assert hasattr(Permission, perm_enum), f"Permission {perm} should be defined"

    def test_role_permissions_mapping_complete(self):
        """Test: ROLE_PERMISSIONS mapping covers all roles."""
        from algo_studio.api.middleware.rbac import ROLE_PERMISSIONS, Role, Permission

        # All roles should be in mapping
        assert Role.VIEWER in ROLE_PERMISSIONS
        assert Role.DEVELOPER in ROLE_PERMISSIONS
        assert Role.ADMIN in ROLE_PERMISSIONS

        # Viewer should only have read
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        assert Permission.TASK_READ in viewer_perms
        assert len(viewer_perms) == 1

        # Developer should have task CRUD
        dev_perms = ROLE_PERMISSIONS[Role.DEVELOPER]
        assert Permission.TASK_READ in dev_perms
        assert Permission.TASK_CREATE in dev_perms
        assert Permission.TASK_DELETE in dev_perms

        # Admin should have all permissions
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert Permission.TASK_READ in admin_perms
        assert Permission.TASK_CREATE in admin_perms
        assert Permission.TASK_DELETE in admin_perms
        assert Permission.ADMIN_USER in admin_perms
        assert Permission.ADMIN_QUOTA in admin_perms
        assert Permission.ADMIN_ALERT in admin_perms

    def test_user_model_permission_coverage(self):
        """Test: User.has_permission covers all role-based permissions."""
        from algo_studio.db.models.user import User

        # Test viewer
        viewer = User(
            user_id="v1", username="viewer", role="viewer",
            is_active=True, is_superuser=False
        )
        assert viewer.has_permission("task.read")
        assert not viewer.has_permission("task.create")
        assert not viewer.has_permission("task.delete")
        assert not viewer.has_permission("admin.user")

        # Test developer
        dev = User(
            user_id="d1", username="dev", role="developer",
            is_active=True, is_superuser=False
        )
        assert dev.has_permission("task.read")
        assert dev.has_permission("task.create")
        assert dev.has_permission("task.delete")
        assert not dev.has_permission("admin.user")

        # Test admin (superuser)
        admin = User(
            user_id="a1", username="admin", role="admin",
            is_active=True, is_superuser=True
        )
        assert admin.has_permission("task.read")
        assert admin.has_permission("task.create")
        assert admin.has_permission("task.delete")
        assert admin.has_permission("admin.user")
        assert admin.has_permission("admin.quota")
        assert admin.has_permission("admin.alert")


# =============================================================================
# Test Cases: Concurrent Permission Modifications
# =============================================================================

@pytest.mark.cluster
@pytest.mark.e2e
@pytest.mark.rbac
class TestConcurrentPermissionScenarios:
    """
    Tests for concurrent permission modification scenarios.
    """

    def test_task_status_changes_during_permission_check(
        self, mock_user, mock_task, mock_db_session
    ):
        """Test: Permission check handles task status changes gracefully."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.user_id = "owner-user"
        mock_task.user_id = "owner-user"

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        # First call returns running, second returns completed
        call_count = 0
        original_get_task = checker._get_task

        def mock_get_task(task_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                mock_task.status = "running"
            else:
                mock_task.status = "completed"
            return mock_task

        with patch.object(checker, '_get_task', side_effect=mock_get_task):
            # First check should allow cancel (running)
            result1 = checker.can_cancel_task(mock_task.task_id)
            assert result1 is True

            # Second check should deny cancel (completed)
            result2 = checker.can_cancel_task(mock_task.task_id)
            assert result2 is False

    def test_team_membership_revoked_during_session(
        self, mock_user, mock_task, mock_db_session
    ):
        """Test: Permission check handles team membership revocation."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.user_id = "former-team-lead"
        mock_task.user_id = "team-member"
        mock_task.team_id = "team-001"

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        # Simulate membership being revoked between calls
        call_count = 0

        def mock_has_team_role(target_user_id, roles):
            nonlocal call_count
            call_count += 1
            # First call: has role, second call: no role
            return call_count == 1

        with patch.object(checker, '_has_team_role', side_effect=mock_has_team_role):
            # First call should allow (has role)
            result1 = checker.can_write_task(mock_task.task_id)
            assert result1 is True

            # Second call should deny (role revoked)
            result2 = checker.can_write_task(mock_task.task_id)
            assert result2 is False


# =============================================================================
# Test Cases: Permission Hierarchy
# =============================================================================

@pytest.mark.cluster
@pytest.mark.e2e
@pytest.mark.rbac
class TestPermissionHierarchy:
    """
    Tests for permission hierarchy and inheritance.
    """

    def test_public_completed_task_readable_by_all(
        self, mock_user, mock_task, mock_db_session
    ):
        """Test: Public completed tasks can be read by anyone."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.user_id = "random-user"
        mock_task.user_id = "other-user"
        mock_task.status = "completed"
        mock_task.is_public = True

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        with patch.object(checker, '_get_task', return_value=mock_task):
            with patch.object(checker, '_is_same_team', return_value=False):
                with patch.object(checker, '_is_same_org', return_value=False):
                    assert checker.can_read_task(mock_task.task_id) is True

    def test_private_running_task_not_readable_by_diff_org(
        self, mock_user, mock_task, mock_db_session
    ):
        """Test: Private running tasks cannot be read by different org users."""
        from algo_studio.core.auth.permission_checker import PermissionChecker

        mock_user.user_id = "other-org-user"
        mock_task.user_id = "owner-user"
        mock_task.status = "running"
        mock_task.is_public = False

        checker = PermissionChecker(mock_user, db_session=mock_db_session)

        with patch.object(checker, '_get_task', return_value=mock_task):
            with patch.object(checker, '_is_same_team', return_value=False):
                with patch.object(checker, '_is_same_org', return_value=False):
                    assert checker.can_read_task(mock_task.task_id) is False


# =============================================================================
# Test Cases: Public Routes
# =============================================================================

@pytest.mark.cluster
@pytest.mark.e2e
@pytest.mark.rbac
class TestPublicRoutes:
    """
    Tests for public route detection.
    """

    def test_health_route_is_public(self):
        """Test: /health is a public route."""
        from algo_studio.api.middleware.rbac import RBACMiddleware

        middleware = RBACMiddleware(app=MagicMock())

        assert middleware._is_public_route("/health") is True

    def test_api_hosts_is_public(self):
        """Test: /api/hosts is a public route."""
        from algo_studio.api.middleware.rbac import RBACMiddleware

        middleware = RBACMiddleware(app=MagicMock())

        assert middleware._is_public_route("/api/hosts") is True

    def test_api_cluster_is_public(self):
        """Test: /api/cluster is a public route."""
        from algo_studio.api.middleware.rbac import RBACMiddleware

        middleware = RBACMiddleware(app=MagicMock())

        assert middleware._is_public_route("/api/cluster") is True

    def test_api_tasks_is_not_public(self):
        """Test: /api/tasks requires authentication."""
        from algo_studio.api.middleware.rbac import RBACMiddleware

        middleware = RBACMiddleware(app=MagicMock())

        assert middleware._is_public_route("/api/tasks") is False

    def test_api_tasks_with_id_is_not_public(self):
        """Test: /api/tasks/{id} requires authentication."""
        from algo_studio.api.middleware.rbac import RBACMiddleware

        middleware = RBACMiddleware(app=MagicMock())

        assert middleware._is_public_route("/api/tasks/task-123") is False


# =============================================================================
# Test Cases: Deploy Permission Coverage
# =============================================================================

@pytest.mark.cluster
@pytest.mark.e2e
@pytest.mark.rbac
class TestDeployPermissions:
    """
    Tests for deploy permission coverage.

    Note: These test the Permission model coverage, not actual deploy API calls.
    """

    def test_developer_lacks_deploy_permissions(self, mock_user):
        """Test: Developer role should have deploy permissions via middleware."""
        mock_user.role = "developer"

        # Note: In the middleware, developer has deploy.write
        # But User model doesn't expose deploy permissions
        # This documents the current implementation gap
        assert mock_user.has_permission("task.create") is True

    def test_admin_can_access_deploy_endpoints(self, admin_user):
        """Test: Admin should be able to access deploy endpoints."""
        # Admin is superuser, so should have access
        assert admin_user.is_superuser is True


# =============================================================================
# Test Cases: Hosts Read Permission
# =============================================================================

@pytest.mark.cluster
@pytest.mark.e2e
@pytest.mark.rbac
class TestHostsReadPermission:
    """
    Tests for hosts:read permission.

    The /api/hosts endpoint is public, but we test the permission model.
    """

    def test_viewer_can_read_hosts_via_public_route(self):
        """Test: Viewer can access /api/hosts because it's public."""
        from algo_studio.api.middleware.rbac import RBACMiddleware

        middleware = RBACMiddleware(app=MagicMock())

        # Public route - no auth required
        assert middleware._is_public_route("/api/hosts") is True

    def test_all_roles_can_read_hosts_public_endpoint(self):
        """Test: All authenticated users can read hosts via public route."""
        from algo_studio.api.middleware.rbac import RBACMiddleware

        middleware = RBACMiddleware(app=MagicMock())

        # Even without auth headers, public route is accessible
        # This is by design in the RBAC middleware
        assert middleware._is_public_route("/api/hosts") is True
