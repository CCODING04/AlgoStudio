# src/algo_studio/db/models/team_membership.py
"""TeamMembership model for RBAC hierarchy."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from algo_studio.db.models.base import Base, TimestampMixin


class TeamMembership(Base, TimestampMixin):
    """TeamMembership model - links users to teams with roles.

    Represents the membership relationship between users and teams.
    Each user can belong to multiple teams with different roles.
    """

    __tablename__ = "team_memberships"

    membership_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    team_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("teams.team_id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), default="member")  # member, lead, admin

    # Relationships (using string references to avoid circular imports)
    user: Mapped["User"] = relationship(
        "User",
        back_populates="team_memberships",
    )
    team: Mapped["Team"] = relationship(
        "Team",
        back_populates="memberships",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "team_id", name="uq_user_team"),
        Index("idx_membership_user_id", "user_id"),
        Index("idx_membership_team_id", "team_id"),
        Index("idx_membership_role", "role"),
    )

    def __repr__(self) -> str:
        return f"<TeamMembership(membership_id={self.membership_id}, user_id={self.user_id}, team_id={self.team_id}, role={self.role})>"
