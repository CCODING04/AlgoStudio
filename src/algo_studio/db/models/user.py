# src/algo_studio/db/models/user.py
"""User model for RBAC (Role-Based Access Control)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from algo_studio.db.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from algo_studio.db.models.team_membership import TeamMembership


class User(Base, TimestampMixin):
    """User model for authentication and authorization.

    Supports RBAC with roles: viewer, developer, admin.
    """

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # RBAC fields
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    team_memberships: Mapped[List["TeamMembership"]] = relationship(
        "TeamMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission.

        Args:
            permission: Permission string like 'task.create', 'admin.quota'

        Returns:
            True if user has the permission
        """
        # Admin has all permissions
        if self.is_superuser:
            return True

        # Role-based permissions (must match RBACMiddleware.ROLE_PERMISSIONS)
        role_permissions = {
            "viewer": ["task.read", "dataset.read", "deploy.read"],
            "developer": [
                "task.read", "task.create", "task.delete",
                "dataset.read", "dataset.create", "dataset.write",
                "deploy.read", "deploy.write",
            ],
            "admin": [
                "task.read", "task.create", "task.delete",
                "admin.user", "admin.quota", "admin.alert",
                "dataset.read", "dataset.create", "dataset.write", "dataset.delete", "dataset.admin",
                "deploy.read", "deploy.write",
            ],
        }

        return permission in role_permissions.get(self.role, [])

    def __repr__(self) -> str:
        return f"<User(user_id={self.user_id}, username={self.username}, role={self.role})>"
