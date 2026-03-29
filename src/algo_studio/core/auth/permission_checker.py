# src/algo_studio/core/auth/permission_checker.py
"""Permission checker for task-level authorization.

Implements Org -> Team -> User permission inheritance flow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from algo_studio.db.models.organization import Organization
from algo_studio.db.models.task import Task
from algo_studio.db.models.team import Team
from algo_studio.db.models.team_membership import TeamMembership
from algo_studio.db.models.user import User
from algo_studio.db.models.dataset import Dataset, DatasetAccess

if TYPE_CHECKING:
    pass


class PermissionChecker:
    """Permission checker with Org -> Team -> User inheritance.

    Permission flow:
    - Owner: full access (read/write/delete/cancel)
    - Team Member: read + write/delete/cancel (if lead/admin role)
    - Org Member: read only (same organization)
    - Public: read (only completed tasks)
    - Superuser: full access

    Attributes:
        user: The user to check permissions for
        team_memberships: Pre-loaded team memberships for the user
        db_session: Database session for queries (optional)
    """

    def __init__(
        self,
        user: User,
        db_session: Optional[Session] = None,
        team_memberships: Optional[list[TeamMembership]] = None,
    ):
        """Initialize PermissionChecker.

        Args:
            user: The user to check permissions for
            db_session: Optional database session for queries
            team_memberships: Pre-loaded team memberships (if not provided,
                             will be loaded from db_session)
        """
        self.user = user
        self.db_session = db_session
        self._team_memberships = team_memberships
        self._user_org_ids: Optional[Set[str]] = None
        self._user_team_ids: Optional[Set[str]] = None

    @property
    def team_memberships(self) -> list[TeamMembership]:
        """Get user's team memberships, loading from DB if needed."""
        if self._team_memberships is None:
            if self.db_session is None:
                return []
            self._team_memberships = (
                self.db_session.query(TeamMembership)
                .filter(TeamMembership.user_id == self.user.user_id)
                .all()
            )
        return self._team_memberships

    def can_read_task(self, task_id: str) -> bool:
        """Check if user can read a task.

        Allows access if:
        - User is the task owner
        - User is a superuser
        - Task is public and completed
        - User shares a team with the task owner
        - User shares an organization with the task owner

        Args:
            task_id: ID of the task to check

        Returns:
            True if user can read the task
        """
        task = self._get_task(task_id)
        if not task:
            return False

        # Owner always can
        if task.user_id == self.user.user_id:
            return True

        # Superuser always can
        if self.user.is_superuser:
            return True

        # Public completed tasks can be read by anyone
        is_public = getattr(task, "is_public", False)
        if is_public and task.status == "completed":
            return True

        # Same team member
        if task.user_id and self._is_same_team(task.user_id):
            return True

        # Same organization member
        if task.user_id and self._is_same_org(task.user_id):
            return True

        return False

    def can_write_task(self, task_id: str) -> bool:
        """Check if user can write (modify) a task.

        Allows access if:
        - User is the task owner
        - User is a superuser
        - User is a team lead or admin for the task owner's team

        Args:
            task_id: ID of the task to check

        Returns:
            True if user can write the task
        """
        task = self._get_task(task_id)
        if not task:
            return False

        # Owner always can
        if task.user_id == self.user.user_id:
            return True

        # Superuser always can
        if self.user.is_superuser:
            return True

        # Team lead or admin can write tasks in their team
        if task.user_id and self._has_team_role(task.user_id, ["lead", "admin"]):
            return True

        return False

    def can_delete_task(self, task_id: str) -> bool:
        """Check if user can delete a task.

        Same permissions as write (owner, superuser, team lead/admin).

        Args:
            task_id: ID of the task to check

        Returns:
            True if user can delete the task
        """
        return self.can_write_task(task_id)

    def can_cancel_task(self, task_id: str) -> bool:
        """Check if user can cancel a running task.

        Same permissions as write, but task must be in PENDING or RUNNING status.

        Args:
            task_id: ID of the task to check

        Returns:
            True if user can cancel the task
        """
        task = self._get_task(task_id)
        if not task:
            return False

        # Can only cancel pending or running tasks
        if task.status not in ("pending", "running"):
            return False

        return self.can_write_task(task_id)

    # Dataset permission methods

    def can_read_dataset(self, dataset_id: str) -> bool:
        """Check if user can read a dataset.

        Allows access if:
        - User is superuser
        - Dataset is public
        - User is the dataset owner
        - User has explicit read/write/admin access

        Args:
            dataset_id: ID of the dataset to check

        Returns:
            True if user can read the dataset
        """
        return self._check_dataset_access(dataset_id, "read")

    def can_write_dataset(self, dataset_id: str) -> bool:
        """Check if user can write (modify) a dataset.

        Allows access if:
        - User is superuser
        - User is the dataset owner
        - User has write/admin access

        Args:
            dataset_id: ID of the dataset to check

        Returns:
            True if user can write the dataset
        """
        return self._check_dataset_access(dataset_id, "write")

    def can_delete_dataset(self, dataset_id: str) -> bool:
        """Check if user can delete a dataset.

        Same permissions as write (owner, superuser, team lead/admin).

        Args:
            dataset_id: ID of the dataset to check

        Returns:
            True if user can delete the dataset
        """
        return self.can_write_dataset(dataset_id)

    def can_admin_dataset(self, dataset_id: str) -> bool:
        """Check if user can admin (manage access to) a dataset.

        Allows access if:
        - User is superuser
        - User is the dataset owner
        - User has admin access

        Args:
            dataset_id: ID of the dataset to check

        Returns:
            True if user can admin the dataset
        """
        return self._check_dataset_access(dataset_id, "admin")

    def _check_dataset_access(self, dataset_id: str, required_level: str) -> bool:
        """Check if user has required access level to dataset.

        Args:
            dataset_id: ID of the dataset
            required_level: Required access level (read/write/admin)

        Returns:
            True if user has the required access level
        """
        dataset = self._get_dataset(dataset_id)
        if not dataset:
            return False

        # Superuser has all permissions
        if self.user.is_superuser:
            return True

        # Public datasets - anyone can read
        if dataset.is_public and required_level == "read":
            return True

        # Owner has all permissions
        if dataset.owner_id == self.user.user_id:
            return True

        # Check dataset_access table
        if not self.db_session:
            return False

        access = (
            self.db_session.query(DatasetAccess)
            .filter(
                DatasetAccess.dataset_id == dataset_id,
                DatasetAccess.user_id == self.user.user_id
            )
            .first()
        )

        if not access:
            return False

        level_hierarchy = {"read": 0, "write": 1, "admin": 2}
        return level_hierarchy.get(access.access_level, -1) >= level_hierarchy.get(required_level, 99)

    def _get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Get dataset by ID.

        Args:
            dataset_id: ID of the dataset

        Returns:
            Dataset object or None if not found
        """
        if self.db_session:
            return self.db_session.get(Dataset, dataset_id)
        return None

    def _get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID.

        Args:
            task_id: ID of the task

        Returns:
            Task object or None if not found
        """
        if self.db_session:
            return self.db_session.get(Task, task_id)
        return None

    def _is_same_team(self, target_user_id: str) -> bool:
        """Check if user shares a team with the target user.

        Args:
            target_user_id: User ID to check against

        Returns:
            True if users share at least one team
        """
        if not target_user_id or target_user_id == self.user.user_id:
            return target_user_id == self.user.user_id

        target_team_ids = self._get_user_team_ids(target_user_id)
        user_team_ids = self._get_user_team_ids(self.user.user_id)

        return bool(target_team_ids & user_team_ids)

    def _is_same_org(self, target_user_id: str) -> bool:
        """Check if user shares an organization with the target user.

        Args:
            target_user_id: User ID to check against

        Returns:
            True if users share at least one organization
        """
        if not target_user_id or target_user_id == self.user.user_id:
            return target_user_id == self.user.user_id

        target_org_ids = self._get_user_org_ids(target_user_id)
        user_org_ids = self._get_user_org_ids(self.user.user_id)

        return bool(target_org_ids & user_org_ids)

    def _has_team_role(self, target_user_id: str, roles: list[str]) -> bool:
        """Check if user has one of the specified roles in a shared team.

        Args:
            target_user_id: User ID of the task owner
            roles: List of allowed roles (e.g., ['lead', 'admin'])

        Returns:
            True if user has one of the roles in a team shared with target user
        """
        if not target_user_id:
            return False

        # Get teams that the target user belongs to
        target_team_ids = self._get_user_team_ids(target_user_id)

        # Check user's memberships in those teams
        for membership in self.team_memberships:
            if membership.team_id in target_team_ids and membership.role in roles:
                return True

        return False

    def _get_user_team_ids(self, user_id: str) -> Set[str]:
        """Get all team IDs a user belongs to.

        Args:
            user_id: User ID to look up

        Returns:
            Set of team IDs
        """
        if not self.db_session:
            return set()

        memberships = (
            self.db_session.query(TeamMembership.team_id)
            .filter(TeamMembership.user_id == user_id)
            .all()
        )
        return {m.team_id for m in memberships}

    def _get_user_org_ids(self, user_id: str) -> Set[str]:
        """Get all organization IDs a user belongs to.

        Args:
            user_id: User ID to look up

        Returns:
            Set of organization IDs
        """
        if not self.db_session:
            return set()

        # Get org IDs through team memberships
        org_ids: Set[str] = set()

        # Query teams through memberships and get their org_ids
        result = (
            self.db_session.query(Team.org_id)
            .join(TeamMembership, TeamMembership.team_id == Team.team_id)
            .filter(TeamMembership.user_id == user_id)
            .distinct()
            .all()
        )
        org_ids.update(r.org_id for r in result)

        return org_ids


def get_permission_checker(
    user: User,
    db_session: Optional[Session] = None,
) -> PermissionChecker:
    """Factory function to create a PermissionChecker with user data loaded.

    Args:
        user: The user to check permissions for
        db_session: Database session

    Returns:
        Configured PermissionChecker instance
    """
    team_memberships = None
    if db_session:
        team_memberships = (
            db_session.query(TeamMembership)
            .filter(TeamMembership.user_id == user.user_id)
            .all()
        )

    return PermissionChecker(
        user=user,
        db_session=db_session,
        team_memberships=team_memberships,
    )
