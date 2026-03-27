# src/algo_studio/db/models/task.py
"""Task history model for persistent task storage."""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from algo_studio.db.models.base import Base, TimestampMixin


class Task(Base, TimestampMixin):
    """Task model for persistent task history storage.

    Tracks all tasks including their status, configuration, and results.
    """

    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_type: Mapped[str] = mapped_column(String(20), nullable=False)  # train/infer/verify
    algorithm_name: Mapped[str] = mapped_column(String(100), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # pending/running/completed/failed/cancelled

    # Configuration and results
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Execution info
    assigned_node: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100

    # User association
    user_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Task(task_id={self.task_id}, type={self.task_type}, status={self.status})>"
