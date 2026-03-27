# src/algo_studio/db/models/audit.py
"""AuditLog model for tracking permission and system changes."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from algo_studio.db.models.base import Base


class AuditAction(str, Enum):
    """Audit action types for permission and system changes."""

    # Permission changes
    PERMISSION_GRANT = "permission.grant"
    PERMISSION_REVOKE = "permission.revoke"
    ROLE_CHANGED = "role.changed"

    # Team management
    TEAM_CREATED = "team.created"
    TEAM_UPDATED = "team.updated"
    TEAM_DELETED = "team.deleted"
    MEMBER_ADDED = "member.added"
    MEMBER_REMOVED = "member.removed"
    MEMBER_ROLE_CHANGED = "member.role_changed"

    # Organization management
    ORG_CREATED = "org.created"
    ORG_UPDATED = "org.updated"
    ORG_DELETED = "org.deleted"

    # Task operations
    TASK_CREATED = "task.created"
    TASK_CANCELLED = "task.cancelled"
    TASK_DELETED = "task.deleted"
    TASK_PUBLIC_SET = "task.public_set"

    # Authentication events
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"

    # Generic events
    SETTINGS_CHANGED = "settings.changed"

    # Deployment rollback events
    DEPLOY_ROLLBACK_INITIATED = "deploy.rollback.initiated"
    DEPLOY_ROLLBACK_COMPLETED = "deploy.rollback.completed"
    DEPLOY_ROLLBACK_FAILED = "deploy.rollback.failed"
    DEPLOY_SNAPSHOT_CREATED = "deploy.snapshot.created"


class AuditLog(Base):
    """AuditLog model for tracking security and permission changes.

    Stores all auditable actions including permission grants/revokes,
    team/organization changes, and task operations.

    Retention: 180 days (per GDPR compliance decision)
    """

    __tablename__ = "audit_logs"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)  # User who performed the action
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # Action type from AuditAction
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # task, team, user, org, etc.
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)  # ID of the affected resource

    # Change tracking
    old_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Request context
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 compatible
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Timestamps (no updated_at - audit logs are immutable)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_audit_created_at", "created_at"),
        Index("idx_audit_actor_id", "actor_id"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_action", "action"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(audit_id={self.audit_id}, action={self.action}, resource_type={self.resource_type}, resource_id={self.resource_id})>"
