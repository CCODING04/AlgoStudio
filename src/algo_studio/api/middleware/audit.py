# src/algo_studio/api/middleware/audit.py
"""Audit logging middleware for tracking all API operations.

This module provides FastAPI middleware that logs all API requests
including user_id, action, resource, timestamp, details, and ip_address.

Retention: 180 days (per GDPR compliance decision)

Audit Log Fields:
    - user_id: The user who performed the action (from X-User-ID header)
    - action: HTTP method + API path (e.g., "GET /api/tasks")
    - resource: The resource type and ID accessed (e.g., "task:task-123")
    - timestamp: When the action occurred
    - details: Additional context (request body, query params, response status)
    - ip_address: Client IP address
"""

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from algo_studio.db.models.audit import AuditLog
from algo_studio.db.session import db

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all API operations to the audit trail.

    This middleware captures:
    - User ID (from X-User-ID header, or "anonymous" for public routes)
    - Action (HTTP method + path)
    - Resource (parsed from path, e.g., "task:task-123")
    - Timestamp (UTC)
    - Request details (method, path, query params, body for POST/PUT/PATCH)
    - Response status code
    - Client IP address
    - User agent

    Public routes (defined in RBACMiddleware) are logged with user_id="anonymous"
    unless they are health check endpoints.

    Note: SSE progress endpoints are excluded from audit logging to reduce noise.
    """

    # Routes to exclude from audit logging (health checks, SSE streams)
    EXCLUDED_ROUTES = {
        "/health",
        "/",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    # SSE progress routes to exclude
    SSE_PROGRESS_PATTERNS = [
        re.compile(r"^/api/tasks/[^/]+/progress$"),
    ]

    # Routes where we capture request body
    BODY_CAPTURE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    # Maximum body size to capture (10KB)
    MAX_BODY_SIZE = 10 * 1024

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and log audit information."""
        path = request.url.path

        # Skip excluded routes
        if self._is_excluded_route(path):
            return await call_next(request)

        # Extract request metadata before processing
        user_id = request.headers.get("X-User-ID", "anonymous")
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")
        method = request.method
        query_params = dict(request.query_params)

        # Parse resource from path
        resource_type, resource_id = self._parse_resource(path)

        # Capture request body for relevant methods
        details = {
            "method": method,
            "path": path,
            "query_params": query_params if query_params else None,
        }

        # Read body if applicable (store for later use)
        body = None
        if method in self.BODY_CAPTURE_METHODS:
            body = await self._get_request_body(request)
            if body:
                details["request_body"] = body

        # Process the request
        response = await call_next(request)

        # Add response status to details
        details["response_status"] = response.status_code

        # Create audit log entry
        try:
            await self._create_audit_log(
                user_id=user_id,
                action=f"{method} {path}",
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception as e:
            # Audit logging should not break the request
            # Log the error but continue
            logger.error(f"Audit logging failed: {e}", exc_info=True)

        return response

    def _is_excluded_route(self, path: str) -> bool:
        """Check if the route should be excluded from audit logging."""
        # Check exact match exclusions
        if path in self.EXCLUDED_ROUTES:
            return True

        # Check SSE progress patterns
        for pattern in self.SSE_PROGRESS_PATTERNS:
            if pattern.match(path):
                return True

        return False

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request.

        Handles X-Forwarded-For header for proxy setups.
        """
        # Check X-Forwarded-For header first (for proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    def _parse_resource(self, path: str) -> tuple[str, Optional[str]]:
        """Parse resource type and ID from the API path.

        Examples:
            /api/tasks -> ("tasks", None)
            /api/tasks/task-123 -> ("tasks", "task-123")
            /api/tasks/task-123/dispatch -> ("tasks", "task-123")
            /api/hosts -> ("hosts", None)
            /health -> ("health", None)
            / -> ("root", None)
        """
        # Normalize path - remove leading/trailing slashes
        path = path.strip("/")

        # Handle empty path
        if not path:
            return ("root", None)

        # Remove API prefix if present
        if path.startswith("api/"):
            path = path[4:]

        parts = path.split("/")

        resource_type = parts[0] if parts else "unknown"
        resource_id = None

        # Check if we have a resource ID (second part)
        if len(parts) > 1 and parts[1]:
            resource_id = parts[1]

            # For actions like /tasks/{id}/dispatch, the resource is still {id}
            # We capture the action in the "action" field instead

        return (resource_type, resource_id)

    async def _get_request_body(self, request: Request) -> Optional[dict[str, Any]]:
        """Capture request body for audit logging.

        Limits body size to MAX_BODY_SIZE to prevent large payloads.
        """
        try:
            body = await request.body()
            if not body:
                return None

            # Limit body size
            if len(body) > self.MAX_BODY_SIZE:
                return {"_truncated": True, "size": len(body)}

            # Try to parse as JSON
            try:
                return json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {"_raw": "Unable to parse body as JSON"}

        except Exception:
            return None

    async def _create_audit_log(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str],
        details: dict[str, Any],
        ip_address: str,
        user_agent: str,
    ) -> None:
        """Create an audit log entry in the database.

        Uses the global db instance for session management.
        """
        audit_id = f"audit-{uuid.uuid4().hex[:16]}"

        audit_entry = AuditLog(
            audit_id=audit_id,
            actor_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id or "none",
            new_value=details,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            created_at=datetime.now(timezone.utc),
        )

        async with db.session() as session:
            session.add(audit_entry)
            await session.commit()
