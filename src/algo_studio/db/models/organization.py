# src/algo_studio/db/models/organization.py
"""Organization model for RBAC hierarchy."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from algo_studio.db.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from algo_studio.db.models.team import Team


class Organization(Base, TimestampMixin):
    """Organization model - top level of RBAC hierarchy.

    Represents organizations like companies or divisions within a company.
    Each organization can contain multiple teams.
    """

    __tablename__ = "organizations"

    org_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Quota settings
    max_teams: Mapped[int] = mapped_column(Integer, default=10)
    max_users: Mapped[int] = mapped_column(Integer, default=100)
    max_gpu_hours_per_day: Mapped[float] = mapped_column(Float, default=1000.0)

    # Relationships
    teams: Mapped[List["Team"]] = relationship(
        "Team",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_organization_slug", "slug"),
        Index("idx_organization_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Organization(org_id={self.org_id}, name={self.name}, slug={self.slug})>"
