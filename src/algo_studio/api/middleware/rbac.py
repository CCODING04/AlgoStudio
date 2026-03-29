# src/algo_studio/api/middleware/rbac.py
"""RBAC (Role-Based Access Control) middleware for permission checking.

This module provides FastAPI middleware and dependencies for checking
user permissions based on their role.

RBAC Roles:
    - viewer: Can read tasks
    - developer: Can create, read, and delete tasks
    - admin: Full access including user, quota, and alert management

Permissions:
    - task.read: Read tasks
    - task.create: Create new tasks
    - task.delete: Delete tasks
    - admin.user: Manage users
    - admin.quota: Manage quotas
    - admin.alert: Manage alerts

Security:
    - All protected routes require valid signature verification
    - Signatures use HMAC-SHA256 with a shared secret key
    - Timestamp is included to prevent replay attacks
"""

import hashlib
import hmac
import os
import time
from enum import Enum
from functools import wraps
from typing import Callable, Optional

from fastapi import HTTPException, Request, status
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from algo_studio.db.models.user import User

# Secret key for signature verification - must be set via environment variable
_rbac_secret_key = os.environ.get("RBAC_SECRET_KEY", "")

# Maximum age of request timestamp in seconds (5 minutes) to prevent replay attacks
MAX_TIMESTAMP_AGE = 300


class Permission(str, Enum):
    """Available permissions in the system."""

    TASK_READ = "task.read"
    TASK_CREATE = "task.create"
    TASK_DELETE = "task.delete"
    ADMIN_USER = "admin.user"
    ADMIN_QUOTA = "admin.quota"
    ADMIN_ALERT = "admin.alert"
    DEPLOY_READ = "deploy.read"
    DEPLOY_WRITE = "deploy.write"
    DATASET_READ = "dataset.read"
    DATASET_CREATE = "dataset.create"
    DATASET_WRITE = "dataset.write"
    DATASET_DELETE = "dataset.delete"
    DATASET_ADMIN = "dataset.admin"


class Role(str, Enum):
    """Available roles in the system."""

    VIEWER = "viewer"
    DEVELOPER = "developer"
    ADMIN = "admin"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.VIEWER: [Permission.TASK_READ, Permission.DATASET_READ, Permission.DEPLOY_READ],
    Role.DEVELOPER: [
        Permission.TASK_READ, Permission.TASK_CREATE, Permission.TASK_DELETE,
        Permission.DATASET_READ, Permission.DATASET_CREATE, Permission.DATASET_WRITE,
        Permission.DEPLOY_READ, Permission.DEPLOY_WRITE,
    ],
    Role.ADMIN: [
        Permission.TASK_READ,
        Permission.TASK_CREATE,
        Permission.TASK_DELETE,
        Permission.ADMIN_USER,
        Permission.ADMIN_QUOTA,
        Permission.ADMIN_ALERT,
        Permission.DATASET_READ,
        Permission.DATASET_CREATE,
        Permission.DATASET_WRITE,
        Permission.DATASET_DELETE,
        Permission.DATASET_ADMIN,
        Permission.DEPLOY_READ,
        Permission.DEPLOY_WRITE,
    ],
}


class RBACMiddleware(BaseHTTPMiddleware):
    """Middleware for checking user permissions on requests.

    This middleware extracts user information from the request and
    attaches it to the request state for use in route handlers.

    Security:
    - All protected routes require valid signature verification via X-Signature header
    - Signatures are computed as HMAC-SHA256(user_id:timestamp, secret_key)
    - X-Timestamp header prevents replay attacks (max 5 minutes age)
    """

    # Routes that don't require authentication
    PUBLIC_ROUTES = [
        "/health",
        "/",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/hosts",
        "/api/hosts/status",
        "/api/cluster/",
        "/api/algorithms",
    ]

    # SSE progress endpoints - these require auth headers but skip signature verification
    # and permission checks because progress streaming should be accessible for monitoring
    # Format: routes that start with prefix and end with /progress
    SSE_PROGRESS_ROUTES = [
        "/api/tasks/",  # /api/tasks/{task_id}/progress
    ]

    # Routes that require specific permissions
    PROTECTED_ROUTES = {
        "/api/tasks": [Permission.TASK_READ],
        "/api/tasks/": [Permission.TASK_READ],  # GET single task
        "/api/datasets": [Permission.DATASET_READ],
        "/api/datasets/": [Permission.DATASET_READ],
    }

    async def dispatch(self, request: Request, call_next):
        """Process the request and check permissions."""
        # Skip auth for public routes
        if self._is_public_route(request.url.path):
            return await call_next(request)

        # Check if this is an SSE progress route (auth required but skip signature verification)
        is_sse_route = self._is_sse_progress_route(request.url.path)

        # Extract user info from headers
        user_id = request.headers.get("X-User-ID")
        user_role = request.headers.get("X-User-Role", "viewer")
        signature = request.headers.get("X-Signature")
        timestamp_str = request.headers.get("X-Timestamp")

        # Require user_id - no bypass allowed
        if not user_id:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": {
                        "error": {
                            "code": "UNAUTHORIZED",
                            "message": "X-User-ID header is required",
                            "details": {},
                        }
                    }
                },
            )

        # Verify signature to prevent header forgery
        # Skip signature verification for SSE routes (internal monitoring endpoints)
        if not is_sse_route:
            if not self._verify_signature(user_id, timestamp_str or "", signature or ""):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": {
                            "error": {
                                "code": "INVALID_SIGNATURE",
                                "message": "Invalid or missing X-Signature header",
                                "details": {},
                            }
                        }
                    },
                )

        # Validate role
        try:
            role = Role(user_role.lower())
        except ValueError:
            role = Role.VIEWER

        # Create a minimal user object for permission checking
        user = User(
            user_id=user_id,
            username=user_id,
            role=role.value,
            is_active=True,
            is_superuser=(role == Role.ADMIN),
        )

        # Attach user to request state
        request.state.user = user
        request.state.user_role = role

        # Check permissions for protected routes (skip for SSE progress endpoints)
        if not is_sse_route:
            required_permissions = self._get_required_permissions(request.url.path, request.method)
            if required_permissions:
                for perm in required_permissions:
                    if not user.has_permission(perm.value):
                        return JSONResponse(
                            status_code=status.HTTP_403_FORBIDDEN,
                            content={
                                "detail": {
                                    "error": {
                                        "code": "PERMISSION_DENIED",
                                        "message": f"Permission '{perm.value}' required for this operation",
                                        "details": {"required_permission": perm.value},
                                    }
                                }
                            },
                        )

        return await call_next(request)

    def _verify_signature(self, user_id: str, timestamp_str: str, signature: str) -> bool:
        """Verify the HMAC signature for request authentication.

        Signature is computed as: HMAC-SHA256(f"{user_id}:{timestamp}", secret_key)

        Args:
            user_id: The user ID from X-User-ID header
            timestamp_str: The timestamp from X-Timestamp header
            signature: The signature from X-Signature header

        Returns:
            True if signature is valid, False otherwise
        """
        global _rbac_secret_key

        # If no secret key is configured, reject all requests (fail secure)
        if not _rbac_secret_key:
            return False

        # Verify timestamp is present and within acceptable range
        if not timestamp_str:
            return False

        try:
            timestamp = int(timestamp_str)
        except ValueError:
            return False

        current_time = int(time.time())
        if abs(current_time - timestamp) > MAX_TIMESTAMP_AGE:
            return False

        # Compute expected signature
        message = f"{user_id}:{timestamp_str}"
        expected_signature = hmac.new(
            _rbac_secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(signature, expected_signature)

    def _is_public_route(self, path: str) -> bool:
        """Check if the route is public (no auth required).

        Supports both exact matching and prefix matching for routes ending with '/'.
        For example, '/api/tasks/' will match '/api/tasks/abc123/progress'.
        """
        # Normalize path by removing trailing slash (but keep "/" as special case)
        normalized_path = path.rstrip("/") or "/"

        # Check exact match routes and prefix match routes
        for public_route in self.PUBLIC_ROUTES:
            if public_route == "/":
                if normalized_path == "/":
                    return True
            elif public_route.endswith("/"):
                # Prefix match for routes ending with '/'
                if normalized_path.startswith(public_route.rstrip("/")):
                    return True
            elif normalized_path == public_route:
                return True

        return False

    def _is_sse_progress_route(self, path: str) -> bool:
        """Check if the route is an SSE progress endpoint (auth required, no permission check)."""
        for sse_route in self.SSE_PROGRESS_ROUTES:
            if path.startswith(sse_route) and path.endswith("/progress"):
                return True
        return False

    def _get_required_permissions(self, path: str, method: str) -> Optional[list[Permission]]:
        """Get required permissions for a route and method.

        Returns None if the route is not protected, otherwise returns
        the list of required permissions.
        """
        # POST /api/tasks requires task.create
        if path == "/api/tasks" and method == "POST":
            return [Permission.TASK_CREATE]

        # DELETE /api/tasks/{id} requires task.delete
        if path.startswith("/api/tasks/") and method == "DELETE":
            return [Permission.TASK_DELETE]

        # POST /api/tasks/{id}/dispatch requires task.create
        if path.startswith("/api/tasks/") and path.endswith("/dispatch") and method == "POST":
            return [Permission.TASK_CREATE]

        # GET /api/tasks requires task.read
        if path == "/api/tasks" and method == "GET":
            return [Permission.TASK_READ]

        # GET /api/tasks/{id} requires task.read
        if path.startswith("/api/tasks/") and method == "GET":
            return [Permission.TASK_READ]

        # Dataset routes
        # POST /api/datasets requires dataset.create
        if path == "/api/datasets" and method == "POST":
            return [Permission.DATASET_CREATE]

        # GET /api/datasets requires dataset.read
        if path == "/api/datasets" and method == "GET":
            return [Permission.DATASET_READ]

        # PUT /api/datasets/{id} requires dataset.write
        if path.startswith("/api/datasets/") and method == "PUT":
            return [Permission.DATASET_WRITE]

        # DELETE /api/datasets/{id} requires dataset.delete
        if path.startswith("/api/datasets/") and method == "DELETE":
            return [Permission.DATASET_DELETE]

        # GET /api/datasets/{id} requires dataset.read
        if path.startswith("/api/datasets/") and method == "GET":
            return [Permission.DATASET_READ]

        return None


def require_permission(permission: Permission) -> Callable:
    """Dependency that checks if the current user has the required permission.

    Usage:
        @router.get("/tasks")
        async def list_tasks(user: User = Depends(require_permission(Permission.TASK_READ))):
            ...
    """

    async def permission_check(request: Request) -> User:
        """Check if user has the required permission."""
        user: Optional[User] = getattr(request.state, "user", None)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Authentication required",
                        "details": {},
                    }
                },
            )

        if not user.has_permission(permission.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "PERMISSION_DENIED",
                        "message": f"Permission '{permission.value}' required for this operation",
                        "details": {"required_permission": permission.value},
                    }
                },
            )

        return user

    return permission_check


def require_role(role: Role) -> Callable:
    """Dependency that checks if the current user has the required role.

    Usage:
        @router.get("/admin")
        async def admin_endpoint(user: User = Depends(require_role(Role.ADMIN))):
            ...
    """

    async def role_check(request: Request) -> User:
        """Check if user has the required role."""
        user: Optional[User] = getattr(request.state, "user", None)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Authentication required",
                        "details": {},
                    }
                },
            )

        if user.is_superuser:
            return user

        # Check if user's role is >= required role (admin > developer > viewer)
        role_hierarchy = {Role.VIEWER: 0, Role.DEVELOPER: 1, Role.ADMIN: 2}

        if role_hierarchy.get(Role(user.role.lower()), 0) < role_hierarchy.get(role, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "PERMISSION_DENIED",
                        "message": f"Role '{role.value}' or higher required for this operation",
                        "details": {"required_role": role.value},
                    }
                },
            )

        return user

    return role_check
