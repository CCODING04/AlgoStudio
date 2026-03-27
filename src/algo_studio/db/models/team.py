# src/algo_studio/db/models/team.py
"""Team model for RBAC hierarchy."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from algo_studio.db.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from algo_studio.db.models.organization import Organization
    from algo_studio.db.models.team_membership import TeamMembership


class Team(Base, TimestampMixin):
    """Team model - second level of RBAC hierarchy.

    Teams belong to organizations and contain user members.
    Supports quota inheritance from parent organization.
    """

    __tablename__ = "teams"

    team_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("organizations.org_id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Quota settings (None = inherit from organization)
    max_members: Mapped[int] = mapped_column(Integer, default=20)
    max_gpu_hours_per_day: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="teams",
    )
    memberships: Mapped[List["TeamMembership"]] = relationship(
        "TeamMembership",
        back_populates="team",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_team_org_id", "org_id"),
        Index("idx_team_slug", "org_id", "slug"),
        Index("idx_team_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Team(team_id={self.team_id}, name={self.name}, org_id={self.org_id})>"
