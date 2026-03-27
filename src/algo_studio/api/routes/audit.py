# src/algo_studio/api/routes/audit.py
"""Audit log query API routes.

Provides endpoints for querying audit logs with filtering support.

Query Parameters:
    - user_id: Filter by actor/user ID
    - action: Filter by action pattern (e.g., "GET /api/tasks")
    - resource_type: Filter by resource type (task, host, etc.)
    - resource_id: Filter by specific resource ID
    - start_date: Filter logs from this date (ISO format)
    - end_date: Filter logs until this date (ISO format)
    - limit: Maximum number of results (default 100, max 1000)
    - offset: Pagination offset (default 0)

Retention: 180 days (automatic cleanup handled externally)
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from algo_studio.api.middleware.rbac import Permission, require_permission
from algo_studio.db.models.audit import AuditLog
from algo_studio.db.models.user import User
from algo_studio.db.session import get_session


router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditLogResponse(BaseModel):
    """Response model for a single audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    audit_id: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: str


class AuditLogListResponse(BaseModel):
    """Response model for audit log list with pagination."""

    items: list[AuditLogResponse]
    total: int
    limit: int
    offset: int


@router.get("/logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    user_id: Optional[str] = Query(None, description="Filter by actor/user ID"),
    action: Optional[str] = Query(None, description="Filter by action pattern"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by specific resource ID"),
    start_date: Optional[datetime] = Query(None, description="Filter logs from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter logs until this date"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission(Permission.ADMIN_USER)),
) -> AuditLogListResponse:
    """Query audit logs with filtering.

    Supports filtering by:
    - user_id (actor who performed the action)
    - action (HTTP method + path pattern)
    - resource_type (task, host, team, etc.)
    - resource_id (specific resource identifier)
    - date range (start_date, end_date)

    Results are ordered by timestamp descending (newest first).
    """
    # Build filter conditions
    conditions = []

    if user_id:
        conditions.append(AuditLog.actor_id == user_id)

    if action:
        if "%" not in action and "_" not in action:
            conditions.append(AuditLog.action.like(f"{action}%"))
        else:
            conditions.append(AuditLog.action.like(f"%{action}%"))

    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)

    if resource_id:
        conditions.append(AuditLog.resource_id == resource_id)

    if start_date:
        conditions.append(AuditLog.created_at >= start_date)

    if end_date:
        conditions.append(AuditLog.created_at <= end_date)

    # Build the query
    where_clause = and_(*conditions) if conditions else None

    # Get total count using COUNT query instead of loading all rows
    count_query = select(func.count()).select_from(AuditLog)
    if where_clause is not None:
        count_query = count_query.where(where_clause)
    count_result = await session.execute(count_query)
    total = count_result.scalar() or 0

    # Get paginated results
    query = select(AuditLog)
    if where_clause is not None:
        query = query.where(where_clause)
    query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)

    result = await session.execute(query)
    logs = result.scalars().all()

    # Convert to response model
    items = [
        AuditLogResponse(
            audit_id=log.audit_id,
            actor_id=log.actor_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.new_value,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            timestamp=log.created_at.isoformat() if log.created_at else None,
        )
        for log in logs
    ]

    return AuditLogListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/logs/{audit_id}", response_model=AuditLogResponse)
async def get_audit_log(
    audit_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission(Permission.ADMIN_USER)),
) -> AuditLogResponse:
    """Get a specific audit log entry by ID.

    Args:
        audit_id: The unique audit log ID

    Returns:
        The audit log entry

    Raises:
        404: If audit log not found
    """
    query = select(AuditLog).where(AuditLog.audit_id == audit_id)
    result = await session.execute(query)
    log = result.scalar_one_or_none()

    if not log:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit log not found: {audit_id}",
        )

    return AuditLogResponse(
        audit_id=log.audit_id,
        actor_id=log.actor_id,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        details=log.new_value,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        timestamp=log.created_at.isoformat() if log.created_at else None,
    )
