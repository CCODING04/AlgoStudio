# src/algo_studio/api/routes/deploy.py
"""Deploy REST API endpoints for SSH worker deployment management.

This module provides REST API endpoints for:
- Listing all deployment records
- Getting specific deployment details
- Triggering new worker deployments
- SSE progress streaming for deployment tasks

All endpoints are protected with HMAC signature authentication.
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, SecretStr, field_validator
from sse_starlette.sse import EventSourceResponse

# IP address regex pattern (IPv4 only, no CIDR support)
_IPV4_PATTERN = re.compile(
    r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
    r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
)

from algo_studio.api.middleware.rbac import Permission, require_permission
from algo_studio.db.models.user import User
from algo_studio.core.deploy.rollback import (
    DeploymentSnapshotStore,
    RollbackService,
    RollbackStatus,
    RollbackHistoryEntry,
)
from scripts.ssh_deploy import (
    DeployProgressStore,
    SSHDeployer,
    DeployWorkerRequest,
    DeployStatus,
    DeployProgress,
    validate_command,
    DeployError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deploy", tags=["deploy"])

# Global instances
_progress_store = DeployProgressStore()
_deployer = SSHDeployer()
_snapshot_store = DeploymentSnapshotStore()
_rollback_service = RollbackService(_snapshot_store)


# ==============================================================================
# Pydantic Models for API Responses
# ==============================================================================

class DeployProgressResponse(BaseModel):
    """Deployment progress response model."""
    task_id: str
    status: str
    step: str
    step_index: int
    total_steps: int
    progress: int
    message: Optional[str] = None
    error: Optional[str] = None
    node_ip: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class DeployWorkerResponse(BaseModel):
    """Deployment worker response model."""
    task_id: str
    status: str
    node_ip: Optional[str] = None
    step: str
    step_index: int
    total_steps: int
    progress: int
    message: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class DeployListResponse(BaseModel):
    """List of deployments response."""
    items: List[dict]
    total: int


class RollbackResponse(BaseModel):
    """Rollback operation response model."""
    rollback_id: str
    deployment_id: str
    status: str
    snapshot_id: Optional[str] = None
    message: str
    verification_result: Optional[dict] = None
    initiated_by: str
    initiated_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


class RollbackHistoryResponse(BaseModel):
    """Rollback history response model."""
    deployment_id: str
    entries: List[dict]
    total: int


class SnapshotResponse(BaseModel):
    """Deployment snapshot response model."""
    snapshot_id: str
    deployment_id: str
    node_ip: str
    version: str
    config: dict
    steps_completed: List[str]
    created_at: str
    ray_head_ip: str
    ray_port: int
    artifacts: List[str]
    metadata: dict


class DeployWorkerRequestInternal(BaseModel):
    """Internal request model with secure password handling.

    This model uses SecretStr for password to prevent accidental logging
    and validates IP address format.
    """
    node_ip: str
    username: str = "admin02"
    password: SecretStr
    head_ip: str
    ray_port: int = 6379
    proxy_url: Optional[str] = None

    @field_validator("node_ip", "head_ip")
    @classmethod
    def validate_ip_address(cls, v: str) -> str:
        """Validate IP address format (IPv4 only, no CIDR)."""
        if not _IPV4_PATTERN.match(v):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid IP address format: {v}. Must be valid IPv4 (e.g., 192.168.1.1)"
            )
        return v

    @field_validator("ray_port")
    @classmethod
    def validate_ray_port(cls, v: int) -> int:
        """Validate Ray port range."""
        if v < 1 or v > 65535:
            raise HTTPException(
                status_code=400,
                detail="ray_port must be between 1 and 65535"
            )
        return v

    def to_deploy_request(self) -> DeployWorkerRequest:
        """Convert to the original DeployWorkerRequest with plain password."""
        return DeployWorkerRequest(
            node_ip=self.node_ip,
            username=self.username,
            password=self.password.get_secret_value(),  # Extract plain password
            head_ip=self.head_ip,
            ray_port=self.ray_port,
            proxy_url=self.proxy_url,
        )


# ==============================================================================
# API Endpoints
# ==============================================================================

@router.get("/workers")
async def list_workers(
    status: str | None = Query(default=None, description="Filter by deployment status"),
    node_ip: str | None = Query(default=None, description="Filter by node IP"),
):
    """List all deployment records.

    Returns a list of all deployment records with optional filtering
    by status or node IP address.

    Args:
        status: Optional status filter (pending, connecting, deploying,
                verifying, completed, failed, cancelled)
        node_ip: Optional node IP filter

    Returns:
        List of deployment records

    Raises:
        401: Unauthorized - missing or invalid authentication
        400: Bad Request - invalid status value
    """
    # Validate status if provided
    filter_status = None
    if status:
        try:
            filter_status = DeployStatus(status)
        except ValueError:
            valid_statuses = [s.value for s in DeployStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid values: {valid_statuses}"
            )

    # Get all deployments from Redis
    try:
        r = await _progress_store._get_redis()
        keys = []
        async for key in r.scan_iter(f"{DeployProgressStore.REDIS_KEY_PREFIX}*"):
            keys.append(key)
    except Exception:
        # Log internal error but return generic message to client
        logger.exception("Failed to connect to Redis")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve deployment records"
        )

    deployments = []
    for key in keys:
        try:
            data = await r.get(key)
            if data:
                progress = DeployProgress.model_validate_json(data)

                # Apply filters
                if filter_status and progress.status != filter_status:
                    continue
                if node_ip and progress.node_ip != node_ip:
                    continue

                deployments.append(progress)
        except Exception:
            continue

    return DeployListResponse(
        items=[DeployWorkerResponse(
            task_id=d.task_id,
            status=d.status.value,
            node_ip=d.node_ip,
            step=d.step,
            step_index=d.step_index,
            total_steps=d.total_steps,
            progress=d.progress,
            message=d.message,
            error=d.error,
            started_at=d.started_at.isoformat() if d.started_at else None,
            completed_at=d.completed_at.isoformat() if d.completed_at else None,
        ).model_dump() for d in deployments],
        total=len(deployments),
    )


@router.get("/worker/{task_id}")
async def get_worker(task_id: str):
    """Get specific deployment details.

    Retrieves detailed information about a specific deployment
    by its task ID.

    Args:
        task_id: The deployment task ID

    Returns:
        Deployment details including current step and progress

    Raises:
        401: Unauthorized - missing or invalid authentication
        404: Not Found - deployment task not found
    """
    progress = await _progress_store.get(task_id)

    if not progress:
        raise HTTPException(
            status_code=404,
            detail=f"Deployment not found: {task_id}"
        )

    return DeployWorkerResponse(
        task_id=progress.task_id,
        status=progress.status.value,
        node_ip=progress.node_ip,
        step=progress.step,
        step_index=progress.step_index,
        total_steps=progress.total_steps,
        progress=progress.progress,
        message=progress.message,
        error=progress.error,
        started_at=progress.started_at.isoformat() if progress.started_at else None,
        completed_at=progress.completed_at.isoformat() if progress.completed_at else None,
    )


@router.post("/worker")
async def create_worker(request: DeployWorkerRequestInternal):
    """Trigger new worker deployment.

    Initiates a new SSH deployment to a worker node. The deployment
    runs asynchronously - this endpoint returns immediately with
    the task ID. Use GET /api/deploy/worker/{task_id} to track progress.

    The deployment process includes:
    1. SSH connection establishment
    2. sudo configuration
    3. uv virtual environment creation
    4. Dependency installation
    5. Code synchronization
    6. Ray worker startup
    7. Deployment verification

    Args:
        request: Deployment request containing node_ip, username,
                 password (SecretStr), and head_ip

    Returns:
        Task ID for the new deployment

    Raises:
        401: Unauthorized - missing or invalid authentication
        400: Bad Request - invalid request parameters or validation error
    """
    # Check if there's already a deployment in progress for this node
    existing = await _progress_store.get_by_node(request.node_ip)
    if existing and existing.status in (
        DeployStatus.PENDING,
        DeployStatus.CONNECTING,
        DeployStatus.DEPLOYING,
        DeployStatus.VERIFYING,
    ):
        # Return existing task ID - deployment is already in progress
        return {
            "task_id": existing.task_id,
            "message": "Deployment already in progress for this node",
            "status": existing.status.value,
        }

    try:
        # Convert to original request (with plain password) and trigger deployment
        deploy_request = request.to_deploy_request()
        task_id = await _deployer.deploy_worker(deploy_request)

        return {
            "task_id": task_id,
            "message": "Deployment initiated successfully",
            "node_ip": request.node_ip,
        }

    except DeployError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "step": e.step,
                    "details": e.details,
                }
            }
        )
    except Exception as e:
        # Log the actual error internally but return generic message to client
        logger.error(f"Deployment failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Deployment failed due to internal error"
        )


# ==============================================================================
# SSE Progress Endpoint
# ==============================================================================

@router.get("/worker/{task_id}/progress")
async def get_worker_progress(task_id: str, request: Request):
    """SSE progress stream for deployment task.

    Provides Server-Sent Events (SSE) streaming for real-time deployment
    progress updates. The stream continues until the deployment completes,
    fails, or the client disconnects.

    The SSE connection supports reconnection - clients can reconnect and
    receive the current state immediately upon reconnect.

    Event types:
    - progress: Regular progress update with current step and percentage
    - completed: Deployment finished successfully (progress = 100)
    - failed: Deployment failed with error message
    - heartbeat: Periodic ping to keep connection alive

    Args:
        task_id: The deployment task ID
        request: FastAPI request object

    Returns:
        EventSourceResponse with SSE stream

    Raises:
        404: Deployment task not found
    """
    # Check if task exists
    progress = await _progress_store.get(task_id)
    if not progress:
        raise HTTPException(
            status_code=404,
            detail=f"Deployment not found: {task_id}"
        )

    # If already terminal state, send final state and complete
    if progress.status in (DeployStatus.COMPLETED, DeployStatus.FAILED, DeployStatus.CANCELLED):
        async def terminal_state_generator():
            """Send final state and close"""
            event_type = "completed" if progress.status == DeployStatus.COMPLETED else "failed"
            if progress.status == DeployStatus.CANCELLED:
                event_type = "cancelled"
            yield {
                "event": event_type,
                "data": _format_progress_event(progress)
            }
        return EventSourceResponse(terminal_state_generator())

    async def progress_generator():
        """SSE generator for deployment progress updates.

        Polls the progress store every second and yields events
        when progress changes or at regular intervals for heartbeat.
        """
        last_progress = progress.progress
        last_step = progress.step
        last_status = progress.status
        consecutive_empty = 0
        max_empty_count = 30  # 30 seconds of no updates before heartbeat

        while True:
            try:
                # Poll current progress
                current = await _progress_store.get(task_id)

                if current is None:
                    # Task was deleted
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": "Deployment task not found"})
                    }
                    break

                # Check for terminal state
                if current.status in (DeployStatus.COMPLETED, DeployStatus.FAILED, DeployStatus.CANCELLED):
                    event_type = "completed"
                    if current.status == DeployStatus.FAILED:
                        event_type = "failed"
                    elif current.status == DeployStatus.CANCELLED:
                        event_type = "cancelled"

                    yield {
                        "event": event_type,
                        "data": _format_progress_event(current)
                    }
                    break

                # Send update if progress changed or heartbeat interval reached
                if (current.progress != last_progress or
                    current.step != last_step or
                    current.status != last_status or
                    consecutive_empty >= max_empty_count):

                    yield {
                        "event": "progress",
                        "data": _format_progress_event(current)
                    }

                    last_progress = current.progress
                    last_step = current.step
                    last_status = current.status
                    consecutive_empty = 0
                else:
                    consecutive_empty += 1

                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"Client disconnected from deploy progress stream: {task_id}")
                    break

            except Exception as e:
                logger.error(f"Error in deploy progress stream: {e}")
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(e)})
                }
                break

            # Poll interval - 1 second
            await asyncio.sleep(1)

    return EventSourceResponse(progress_generator())


def _format_progress_event(progress: DeployProgress) -> str:
    """Format DeployProgress as JSON for SSE event."""
    return json.dumps({
        "task_id": progress.task_id,
        "status": progress.status.value,
        "step": progress.step,
        "step_index": progress.step_index,
        "total_steps": progress.total_steps,
        "progress": progress.progress,
        "message": progress.message,
        "error": progress.error,
        "node_ip": progress.node_ip,
        "started_at": progress.started_at.isoformat() if progress.started_at else None,
        "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
    })


# ==============================================================================
# Rollback API Endpoints
# ==============================================================================

@router.post("/rollback/{deployment_id}")
async def rollback_deployment(
    deployment_id: str,
    request: Request,
    user: User = Depends(require_permission(Permission.DEPLOY_WRITE)),
):
    """Execute rollback for a deployment.

    Rolls back a deployment to its previous state using a stored snapshot.
    The rollback process:
    1. Retrieves the deployment snapshot
    2. Executes rollback steps in reverse order
    3. Verifies the rollback was successful
    4. Records the rollback in audit log

    Args:
        deployment_id: The deployment ID to rollback
        request: FastAPI request object
        user: Authenticated user (from RBAC middleware)

    Returns:
        RollbackResponse with rollback status and verification results

    Raises:
        401: Unauthorized - missing or invalid authentication
        403: Forbidden - user lacks deploy.write permission
        404: No snapshot found for deployment
        500: Internal error during rollback
    """
    # Get initiated_by from authenticated user context, not from request parameter
    initiated_by = user.username if user else "system"

    try:
        # Check if snapshot exists for this deployment (validates deployment_id is correct)
        snapshot = await _snapshot_store.get_snapshot(deployment_id)
        if not snapshot:
            raise HTTPException(
                status_code=404,
                detail=f"Deployment not found: {deployment_id}"
            )

        # Execute rollback - task_id from snapshot metadata or empty if not available
        task_id = snapshot.metadata.get("task_id", "")
        result = await _rollback_service.rollback(
            deployment_id=deployment_id,
            task_id=task_id,
            initiated_by=initiated_by,
        )

        return RollbackResponse(
            rollback_id=result.rollback_id,
            deployment_id=result.deployment_id,
            status=result.status.value,
            snapshot_id=result.snapshot_id if result.snapshot_id else None,
            message="Rollback completed successfully" if result.status == RollbackStatus.COMPLETED else result.error or "Rollback failed",
            verification_result=result.verification_result,
            initiated_by=result.initiated_by,
            initiated_at=result.initiated_at.isoformat(),
            completed_at=result.completed_at.isoformat() if result.completed_at else None,
            error=result.error,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Rollback failed for deployment {deployment_id}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "ROLLBACK_FAILED",
                    "message": f"Rollback failed: {str(e)}",
                    "details": {},
                }
            }
        )


@router.get("/rollback/{deployment_id}/history")
async def get_rollback_history(deployment_id: str):
    """Get rollback history for a deployment.

    Retrieves the complete rollback history for a specific deployment,
    including all rollback attempts and their results.

    Args:
        deployment_id: The deployment ID to get history for

    Returns:
        RollbackHistoryResponse with list of rollback entries

    Raises:
        404: No rollback history found for deployment
    """
    try:
        history = await _snapshot_store.get_rollback_history(deployment_id)

        if not history:
            return RollbackHistoryResponse(
                deployment_id=deployment_id,
                entries=[],
                total=0,
            )

        return RollbackHistoryResponse(
            deployment_id=deployment_id,
            entries=[entry.to_dict() for entry in history],
            total=len(history),
        )

    except Exception as e:
        logger.exception(f"Failed to get rollback history for {deployment_id}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve rollback history: {str(e)}"
        )


@router.get("/snapshot/{deployment_id}")
async def get_deployment_snapshot(deployment_id: str):
    """Get the current snapshot for a deployment.

    Retrieves the stored snapshot for a deployment, which contains
    the version information and configuration at the time of last deployment.

    Args:
        deployment_id: The deployment ID to get snapshot for

    Returns:
        SnapshotResponse with snapshot details

    Raises:
        404: No snapshot found for deployment
    """
    snapshot = await _snapshot_store.get_snapshot(deployment_id)

    if not snapshot:
        raise HTTPException(
            status_code=404,
            detail=f"No snapshot found for deployment: {deployment_id}"
        )

    return SnapshotResponse(
        snapshot_id=snapshot.snapshot_id,
        deployment_id=snapshot.deployment_id,
        node_ip=snapshot.node_ip,
        version=snapshot.version,
        config=snapshot.config,
        steps_completed=snapshot.steps_completed,
        created_at=snapshot.created_at.isoformat(),
        ray_head_ip=snapshot.ray_head_ip,
        ray_port=snapshot.ray_port,
        artifacts=snapshot.artifacts,
        metadata=snapshot.metadata,
    )


@router.get("/snapshots/node/{node_ip}")
async def get_node_snapshots(node_ip: str):
    """Get all snapshots for a node.

    Retrieves all deployment snapshots stored for a specific node,
    ordered by creation time (most recent first).

    Args:
        node_ip: The node IP address to get snapshots for

    Returns:
        List of SnapshotResponse for the node
    """
    snapshots = await _snapshot_store.get_snapshots_by_node(node_ip)

    return [
        SnapshotResponse(
            snapshot_id=s.snapshot_id,
            deployment_id=s.deployment_id,
            node_ip=s.node_ip,
            version=s.version,
            config=s.config,
            steps_completed=s.steps_completed,
            created_at=s.created_at.isoformat(),
            ray_head_ip=s.ray_head_ip,
            ray_port=s.ray_port,
            artifacts=s.artifacts,
            metadata=s.metadata,
        )
        for s in snapshots
    ]
