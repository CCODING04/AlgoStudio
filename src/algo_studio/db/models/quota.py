# src/algo_studio/db/models/quota.py
"""Quota models for resource management."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from algo_studio.db.models.base import Base, TimestampMixin


class Quota(Base, TimestampMixin):
    """Quota model for resource quota management.

    Supports hierarchical quotas: GLOBAL -> TEAM -> USER
    """

    __tablename__ = "quotas"

    quota_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)  # user/team/global
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False)  # user_id or team_id
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Resource limits
    cpu_cores: Mapped[int] = mapped_column(Integer, default=0)
    gpu_count: Mapped[int] = mapped_column(Integer, default=0)
    gpu_memory_gb: Mapped[float] = mapped_column(Float, default=0.0)
    memory_gb: Mapped[float] = mapped_column(Float, default=0.0)
    disk_gb: Mapped[float] = mapped_column(Float, default=0.0)
    concurrent_tasks: Mapped[int] = mapped_column(Integer, default=0)
    tasks_per_day: Mapped[int] = mapped_column(Integer, default=50)
    gpu_hours_per_day: Mapped[float] = mapped_column(Float, default=24.0)

    # Alert settings
    alert_threshold: Mapped[int] = mapped_column(Integer, default=80)  # 80%

    # Inheritance
    parent_quota_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def is_unlimited(self) -> bool:
        """Check if all resource dimensions are unlimited (0 = unlimited)."""
        return (
            self.cpu_cores == 0
            and self.gpu_count == 0
            and self.gpu_memory_gb == 0.0
            and self.memory_gb == 0.0
            and self.disk_gb == 0.0
            and self.concurrent_tasks == 0
        )

    def __repr__(self) -> str:
        return f"<Quota(quota_id={self.quota_id}, scope={self.scope}, scope_id={self.scope_id})>"


class QuotaUsage(Base):
    """Current resource usage for a quota."""

    __tablename__ = "quota_usages"

    quota_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("quotas.quota_id", ondelete="CASCADE"), primary_key=True
    )

    # Resource usage
    cpu_cores_used: Mapped[float] = mapped_column(Float, default=0.0)
    gpu_count_used: Mapped[int] = mapped_column(Integer, default=0)
    gpu_memory_gb_used: Mapped[float] = mapped_column(Float, default=0.0)
    memory_gb_used: Mapped[float] = mapped_column(Float, default=0.0)
    disk_gb_used: Mapped[float] = mapped_column(Float, default=0.0)
    concurrent_tasks_used: Mapped[int] = mapped_column(Integer, default=0)

    # Daily counters
    tasks_today: Mapped[int] = mapped_column(Integer, default=0)
    gpu_minutes_today: Mapped[float] = mapped_column(Float, default=0.0)

    # Optimistic locking version
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert usage to dictionary."""
        return {
            "cpu_cores_used": self.cpu_cores_used,
            "gpu_count_used": self.gpu_count_used,
            "gpu_memory_gb_used": self.gpu_memory_gb_used,
            "memory_gb_used": self.memory_gb_used,
            "disk_gb_used": self.disk_gb_used,
            "concurrent_tasks_used": self.concurrent_tasks_used,
            "tasks_today": self.tasks_today,
            "gpu_minutes_today": self.gpu_minutes_today,
        }

    def __repr__(self) -> str:
        return f"<QuotaUsage(quota_id={self.quota_id}, concurrent_tasks={self.concurrent_tasks_used})>"


class QuotaUsageHistory(Base):
    """Historical record of quota usage for statistics."""

    __tablename__ = "quota_usage_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quota_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("quotas.quota_id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<QuotaUsageHistory(quota_id={self.quota_id}, metric={self.metric}, value={self.value})>"


class QuotaAlert(Base):
    """Quota alert records."""

    __tablename__ = "quota_alerts"

    alert_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    quota_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("quotas.quota_id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)  # info/warning/critical
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    usage_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Associated task (for queue wait alerts)
    task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Acknowledgement
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<QuotaAlert(alert_id={self.alert_id}, level={self.level}, metric={self.metric})>"
