# src/algo_studio/db/models/dataset.py
"""Dataset model for persistent dataset metadata storage."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from algo_studio.db.models.base import Base, TimestampMixin


class Dataset(Base, TimestampMixin):
    """Dataset model for persistent storage.

    Stores dataset metadata including name, path, version, size, and access control.
    """

    __tablename__ = "datasets"

    # Primary key - UUID or name-based
    dataset_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Basic info
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Storage info
    path: Mapped[str] = mapped_column(String(512), nullable=False)  # /nas/datasets/xxx
    storage_type: Mapped[str] = mapped_column(String(20), default="dvc")  # dvc/nas/raw
    size_gb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    file_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Version control (DVC)
    version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # DVC commit hash
    dvc_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Metadata (renamed to avoid SQLAlchemy reserved name conflict)
    extra_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Access control
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    team_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("teams.team_id", ondelete="SET NULL"), nullable=True
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="dataset")

    def __repr__(self) -> str:
        return f"<Dataset(dataset_id={self.dataset_id}, name={self.name}, size_gb={self.size_gb})>"


class DatasetAccess(Base):
    """Dataset access control model for per-user permissions."""

    __tablename__ = "dataset_access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("datasets.dataset_id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True
    )
    team_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=True
    )

    # Permission level
    access_level: Mapped[str] = mapped_column(String(20), default="read")  # read/write/admin

    # Timestamps
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    granted_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return f"<DatasetAccess(dataset_id={self.dataset_id}, user_id={self.user_id}, level={self.access_level})>"