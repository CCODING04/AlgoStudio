"""Unit tests for PermissionChecker."""

import pytest
from unittest.mock import MagicMock, patch
from typing import Optional

from algo_studio.core.auth.permission_checker import (
    PermissionChecker,
    get_permission_checker,
)
from algo_studio.db.models.user import User
from algo_studio.db.models.task import Task
from algo_studio.db.models.team import Team
from algo_studio.db.models.team_membership import TeamMembership


class MockUser:
    """Mock user for testing."""
    def __init__(
        self,
        user_id: str = "user-1",
        is_superuser: bool = False,
        role: str = "viewer",
    ):
        self.user_id = user_id
        self.is_superuser = is_superuser
        self.role = role


class MockTask:
    """Mock task for testing."""
    def __init__(
        self,
        task_id: str = "task-1",
        user_id: str = "owner-1",
        status: str = "pending",
        is_public: bool = False,
    ):
        self.task_id = task_id
        self.user_id = user_id
        self.status = status
        self.is_public = is_public


class MockTeamMembership:
    """Mock team membership for testing."""
    def __init__(
        self,
        team_id: str = "team-1",
        role: str = "member",
    ):
        self.team_id = team_id
        self.role = role


# =============================================================================
# PermissionChecker Initialization Tests
# =============================================================================

class TestPermissionCheckerInit:
    """Tests for PermissionChecker initialization."""

    def test_init_with_user(self):
        """Test initialization with user."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        assert checker.user.user_id == "user-1"
        assert checker.db_session is None
        assert checker._team_memberships is None

    def test_init_with_db_session(self):
        """Test initialization with db session."""
        user = MockUser(user_id="user-1")
        mock_session = MagicMock()
        checker = PermissionChecker(user=user, db_session=mock_session)

        assert checker.db_session == mock_session

    def test_init_with_team_memberships(self):
        """Test initialization with pre-loaded team memberships."""
        user = MockUser(user_id="user-1")
        memberships = [
            MockTeamMembership(team_id="team-1", role="admin"),
            MockTeamMembership(team_id="team-2", role="member"),
        ]
        checker = PermissionChecker(user=user, team_memberships=memberships)

        assert len(checker.team_memberships) == 2
        assert checker.team_memberships[0].team_id == "team-1"

    def test_init_caches_org_and_team_ids(self):
        """Test that org and team ID caches are initialized."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        assert checker._user_org_ids is None
        assert checker._user_team_ids is None


# =============================================================================
# Team Memberships Property Tests
# =============================================================================

class TestTeamMembershipsProperty:
    """Tests for team_memberships property."""

    def test_team_memberships_from_preloaded(self):
        """Test team memberships returned when pre-loaded."""
        user = MockUser(user_id="user-1")
        memberships = [MockTeamMembership(team_id="team-1")]
        checker = PermissionChecker(user=user, team_memberships=memberships)

        # Should return pre-loaded memberships without DB query
        assert checker.team_memberships == memberships

    def test_team_memberships_loads_from_db(self):
        """Test team memberships loaded from DB when not pre-loaded."""
        user = MockUser(user_id="user-1")
        mock_session = MagicMock()
        mock_membership = MagicMock()
        mock_membership.team_id = "team-1"
        mock_membership.role = "member"

        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_membership]
        mock_session.query.return_value = mock_query

        checker = PermissionChecker(user=user, db_session=mock_session)

        memberships = checker.team_memberships
        assert len(memberships) == 1
        assert memberships[0].team_id == "team-1"

    def test_team_memberships_returns_empty_without_db(self):
        """Test team memberships returns empty list without DB session."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)  # No db_session

        memberships = checker.team_memberships
        assert memberships == []


# =============================================================================
# can_read_task Tests
# =============================================================================

class TestCanReadTask:
    """Tests for can_read_task method."""

    def test_owner_can_read_own_task(self):
        """Test that task owner can read their task."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="user-1")

        # Mock _get_task to return our task
        checker._get_task = MagicMock(return_value=task)

        assert checker.can_read_task("task-1") is True

    def test_superuser_can_read_any_task(self):
        """Test that superuser can read any task."""
        user = MockUser(user_id="user-1", is_superuser=True)
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="other-user")
        checker._get_task = MagicMock(return_value=task)

        assert checker.can_read_task("task-1") is True

    def test_public_completed_task_can_be_read_by_anyone(self):
        """Test that public completed tasks can be read by anyone."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="other-user", status="completed", is_public=True)
        checker._get_task = MagicMock(return_value=task)

        assert checker.can_read_task("task-1") is True

    def test_public_non_completed_task_cannot_be_read(self):
        """Test that public non-completed tasks cannot be read by non-members."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        # Public but running (not completed)
        task = MockTask(task_id="task-1", user_id="other-user", status="running", is_public=True)
        checker._get_task = MagicMock(return_value=task)

        assert checker.can_read_task("task-1") is False

    def test_same_team_member_can_read(self):
        """Test that same team member can read task."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="other-user")
        checker._get_task = MagicMock(return_value=task)

        # Mock _is_same_team to return True
        checker._is_same_team = MagicMock(return_value=True)

        assert checker.can_read_task("task-1") is True

    def test_same_org_member_can_read(self):
        """Test that same organization member can read task."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="other-user")
        checker._get_task = MagicMock(return_value=task)

        # Mock _is_same_team to return False but _is_same_org to return True
        checker._is_same_team = MagicMock(return_value=False)
        checker._is_same_org = MagicMock(return_value=True)

        assert checker.can_read_task("task-1") is True

    def test_task_not_found_returns_false(self):
        """Test that task not found returns False."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        checker._get_task = MagicMock(return_value=None)

        assert checker.can_read_task("nonexistent") is False

    def test_no_permission_returns_false(self):
        """Test that user without permission cannot read task."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="other-user")
        checker._get_task = MagicMock(return_value=task)
        checker._is_same_team = MagicMock(return_value=False)
        checker._is_same_org = MagicMock(return_value=False)

        assert checker.can_read_task("task-1") is False


# =============================================================================
# can_write_task Tests
# =============================================================================

class TestCanWriteTask:
    """Tests for can_write_task method."""

    def test_owner_can_write_own_task(self):
        """Test that task owner can write their task."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="user-1")
        checker._get_task = MagicMock(return_value=task)

        assert checker.can_write_task("task-1") is True

    def test_superuser_can_write_any_task(self):
        """Test that superuser can write any task."""
        user = MockUser(user_id="user-1", is_superuser=True)
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="other-user")
        checker._get_task = MagicMock(return_value=task)

        assert checker.can_write_task("task-1") is True

    def test_team_lead_can_write_task(self):
        """Test that team lead can write task in their team."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="other-user")
        checker._get_task = MagicMock(return_value=task)

        # Mock _has_team_role to return True for lead role
        checker._has_team_role = MagicMock(return_value=True)

        assert checker.can_write_task("task-1") is True

    def test_team_admin_can_write_task(self):
        """Test that team admin can write task in their team."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="other-user")
        checker._get_task = MagicMock(return_value=task)

        # Mock _has_team_role to return True for admin role
        checker._has_team_role = MagicMock(return_value=True)

        assert checker.can_write_task("task-1") is True

    def test_regular_member_cannot_write_task(self):
        """Test that regular team member cannot write task."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="other-user")
        checker._get_task = MagicMock(return_value=task)
        checker._has_team_role = MagicMock(return_value=False)

        assert checker.can_write_task("task-1") is False

    def test_task_not_found_returns_false(self):
        """Test that task not found returns False."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        checker._get_task = MagicMock(return_value=None)

        assert checker.can_write_task("nonexistent") is False


# =============================================================================
# can_delete_task Tests
# =============================================================================

class TestCanDeleteTask:
    """Tests for can_delete_task method."""

    def test_delete_has_same_permission_as_write(self):
        """Test that can_delete_task delegates to can_write_task."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="user-1")
        checker._get_task = MagicMock(return_value=task)

        # If can_write_task returns True, can_delete_task should also return True
        assert checker.can_delete_task("task-1") is True


# =============================================================================
# can_cancel_task Tests
# =============================================================================

class TestCanCancelTask:
    """Tests for can_cancel_task method."""

    def test_cancel_pending_task_allowed(self):
        """Test that cancel is allowed for pending tasks."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="user-1", status="pending")
        checker._get_task = MagicMock(return_value=task)

        assert checker.can_cancel_task("task-1") is True

    def test_cancel_running_task_allowed(self):
        """Test that cancel is allowed for running tasks."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="user-1", status="running")
        checker._get_task = MagicMock(return_value=task)

        assert checker.can_cancel_task("task-1") is True

    def test_cancel_completed_task_not_allowed(self):
        """Test that cancel is not allowed for completed tasks."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="user-1", status="completed")
        checker._get_task = MagicMock(return_value=task)

        # Should check status first and return False
        assert checker.can_cancel_task("task-1") is False

    def test_cancel_failed_task_not_allowed(self):
        """Test that cancel is not allowed for failed tasks."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        task = MockTask(task_id="task-1", user_id="user-1", status="failed")
        checker._get_task = MagicMock(return_value=task)

        assert checker.can_cancel_task("task-1") is False

    def test_cancel_task_not_found(self):
        """Test that cancel returns False for non-existent task."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        checker._get_task = MagicMock(return_value=None)

        assert checker.can_cancel_task("nonexistent") is False


# =============================================================================
# _get_task Tests
# =============================================================================

class TestGetTask:
    """Tests for _get_task method."""

    def test_get_task_with_db_session(self):
        """Test getting task with database session."""
        user = MockUser(user_id="user-1")
        mock_session = MagicMock()
        mock_task = MockTask(task_id="task-1")

        mock_session.get.return_value = mock_task

        checker = PermissionChecker(user=user, db_session=mock_session)
        result = checker._get_task("task-1")

        mock_session.get.assert_called_once_with(Task, "task-1")
        assert result == mock_task

    def test_get_task_without_db_session(self):
        """Test getting task without database session returns None."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        result = checker._get_task("task-1")

        assert result is None


# =============================================================================
# _is_same_team Tests
# =============================================================================

class TestIsSameTeam:
    """Tests for _is_same_team method."""

    def test_same_user_id_returns_true(self):
        """Test that same user ID returns True."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        assert checker._is_same_team("user-1") is True

    def test_same_team_shared(self):
        """Test that users sharing a team return True."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        # Mock _get_user_team_ids to return overlapping teams
        checker._get_user_team_ids = MagicMock(side_effect=[
            {"team-1", "team-2"},  # user-1's teams
            {"team-1", "team-3"},  # target user's teams
        ])

        assert checker._is_same_team("user-2") is True

    def test_no_shared_team_returns_false(self):
        """Test that users without shared team return False."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        checker._get_user_team_ids = MagicMock(side_effect=[
            {"team-1"},  # user-1's teams
            {"team-2"},  # target user's teams
        ])

        assert checker._is_same_team("user-2") is False

    def test_empty_target_user_id_returns_false(self):
        """Test that empty target user ID returns False."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        assert checker._is_same_team("") is False

    def test_none_target_user_id_returns_false(self):
        """Test that None target user ID returns False."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        assert checker._is_same_team(None) is False


# =============================================================================
# _is_same_org Tests
# =============================================================================

class TestIsSameOrg:
    """Tests for _is_same_org method."""

    def test_same_user_id_returns_true(self):
        """Test that same user ID returns True."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        assert checker._is_same_org("user-1") is True

    def test_same_org_shared(self):
        """Test that users sharing an organization return True."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        # Mock _get_user_org_ids to return overlapping orgs
        checker._get_user_org_ids = MagicMock(side_effect=[
            {"org-1", "org-2"},  # user-1's orgs
            {"org-1", "org-3"},  # target user's orgs
        ])

        assert checker._is_same_org("user-2") is True

    def test_no_shared_org_returns_false(self):
        """Test that users without shared organization return False."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        checker._get_user_org_ids = MagicMock(side_effect=[
            {"org-1"},  # user-1's orgs
            {"org-2"},  # target user's orgs
        ])

        assert checker._is_same_org("user-2") is False


# =============================================================================
# _has_team_role Tests
# =============================================================================

class TestHasTeamRole:
    """Tests for _has_team_role method."""

    def test_empty_target_user_id_returns_false(self):
        """Test that empty target user ID returns False."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        assert checker._has_team_role("", ["lead", "admin"]) is False

    def test_user_has_required_role(self):
        """Test that user with required role returns True."""
        user = MockUser(user_id="user-1")
        memberships = [
            MockTeamMembership(team_id="team-1", role="lead"),
        ]
        checker = PermissionChecker(user=user, team_memberships=memberships)

        # Mock _get_user_team_ids to return teams that include team-1
        checker._get_user_team_ids = MagicMock(return_value={"team-1", "team-2"})

        assert checker._has_team_role("user-2", ["lead", "admin"]) is True

    def test_user_does_not_have_required_role(self):
        """Test that user without required role returns False."""
        user = MockUser(user_id="user-1")
        memberships = [
            MockTeamMembership(team_id="team-1", role="member"),
        ]
        checker = PermissionChecker(user=user, team_memberships=memberships)

        checker._get_user_team_ids = MagicMock(return_value={"team-1"})

        assert checker._has_team_role("user-2", ["lead", "admin"]) is False

    def test_user_in_shared_team_without_role(self):
        """Test that user in shared team without correct role returns False."""
        user = MockUser(user_id="user-1")
        memberships = [
            MockTeamMembership(team_id="team-1", role="member"),
        ]
        checker = PermissionChecker(user=user, team_memberships=memberships)

        # target user is in team-2, which user-1 is not in
        checker._get_user_team_ids = MagicMock(side_effect=[
            {"team-2"},  # target user's teams
            {"team-1"},  # user-1's teams
        ])

        assert checker._has_team_role("user-2", ["lead", "admin"]) is False


# =============================================================================
# _get_user_team_ids Tests
# =============================================================================

class TestGetUserTeamIds:
    """Tests for _get_user_team_ids method."""

    def test_get_team_ids_without_db_session(self):
        """Test that returns empty set without DB session."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        result = checker._get_user_team_ids("user-2")

        assert result == set()

    def test_get_team_ids_with_db_session(self):
        """Test getting team IDs from database."""
        user = MockUser(user_id="user-1")
        mock_session = MagicMock()

        mock_membership1 = MagicMock()
        mock_membership1.team_id = "team-1"
        mock_membership2 = MagicMock()
        mock_membership2.team_id = "team-2"

        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_membership1, mock_membership2]
        mock_session.query.return_value = mock_query

        checker = PermissionChecker(user=user, db_session=mock_session)

        result = checker._get_user_team_ids("user-2")

        assert result == {"team-1", "team-2"}


# =============================================================================
# _get_user_org_ids Tests
# =============================================================================

class TestGetUserOrgIds:
    """Tests for _get_user_org_ids method."""

    def test_get_org_ids_without_db_session(self):
        """Test that returns empty set without DB session."""
        user = MockUser(user_id="user-1")
        checker = PermissionChecker(user=user)

        result = checker._get_user_org_ids("user-2")

        assert result == set()

    def test_get_org_ids_with_db_session(self):
        """Test getting org IDs through team memberships."""
        user = MockUser(user_id="user-1")
        mock_session = MagicMock()

        # Mock query result for org IDs
        mock_result = [MagicMock(org_id="org-1"), MagicMock(org_id="org-2")]

        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.distinct.return_value.all.return_value = mock_result
        mock_session.query.return_value = mock_query

        checker = PermissionChecker(user=user, db_session=mock_session)

        result = checker._get_user_org_ids("user-2")

        assert result == {"org-1", "org-2"}


# =============================================================================
# get_permission_checker Factory Tests
# =============================================================================

class TestGetPermissionChecker:
    """Tests for get_permission_checker factory function."""

    def test_factory_without_db_session(self):
        """Test factory creates checker without DB session."""
        user = MockUser(user_id="user-1")

        checker = get_permission_checker(user)

        assert checker.user.user_id == "user-1"
        assert checker.db_session is None
        assert checker._team_memberships is None

    def test_factory_with_db_session(self):
        """Test factory loads team memberships from DB."""
        user = MockUser(user_id="user-1")
        mock_session = MagicMock()

        mock_membership = MagicMock()
        mock_membership.team_id = "team-1"
        mock_membership.role = "member"

        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_membership]
        mock_session.query.return_value = mock_query

        checker = get_permission_checker(user, db_session=mock_session)

        assert checker.user.user_id == "user-1"
        assert checker.db_session == mock_session
        assert len(checker.team_memberships) == 1
