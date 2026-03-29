# tests/unit/api/routes/conftest.py
"""Shared pytest fixtures for API routes tests.

This module provides common fixtures for testing API routes including:
- Authentication mocking
- App state cleanup
- Mock session handling
"""

import pytest
import os
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

# Set secret key before importing app modules
os.environ["RBAC_SECRET_KEY"] = "test-secret-key-12345"


@pytest.fixture
def mock_rbac_auth(mocker):
    """Mock RBAC authentication for API routes tests.

    Patches the RBAC middleware's verify_signature to always return True,
    allowing tests to bypass authentication checks.
    """
    # Mock RBACMiddleware.verify_signature to always pass
    mock_verify = mocker.patch(
        'algo_studio.api.middleware.rbac.RBACMiddleware.verify_signature',
        return_value=True
    )

    # Mock the require_permission decorator to pass through
    mock_require = mocker.patch(
        'algo_studio.api.middleware.rbac.require_permission',
        return_value=lambda: MagicMock(
            user_id="test-user",
            username="testuser",
            role="developer"
        )
    )

    yield {
        'verify_signature': mock_verify,
        'require_permission': mock_require
    }


@pytest.fixture
def mock_audit_auth(mocker):
    """Mock Audit middleware authentication for API routes tests.

    Patches the AuditMiddleware's verify_signature to always return True,
    preventing audit logging from interfering with route tests.
    """
    mock_verify = mocker.patch(
        'algo_studio.api.middleware.audit.AuditMiddleware.verify_signature',
        return_value=True
    )
    yield mock_verify


@pytest.fixture
def mock_auth_dependencies(mocker):
    """Combined fixture for mocking both RBAC and Audit auth.

    Use this fixture when testing routes that require both RBAC and Audit auth.
    """
    mock_rbac = mocker.patch(
        'algo_studio.api.middleware.rbac.RBACMiddleware.verify_signature',
        return_value=True
    )
    mock_audit = mocker.patch(
        'algo_studio.api.middleware.audit.AuditMiddleware.verify_signature',
        return_value=True
    )
    mock_require = mocker.patch(
        'algo_studio.api.middleware.rbac.require_permission',
        return_value=lambda: MagicMock(
            user_id="test-user",
            username="testuser",
            role="developer"
        )
    )
    yield {
        'rbac_verify': mock_rbac,
        'audit_verify': mock_audit,
        'require_permission': mock_require
    }


@pytest.fixture
def clean_app_state():
    """Clean up app state between tests to prevent pollution.

    Resets TaskManager instances after each test.
    """
    yield
    # Clean up TaskManager state after test
    try:
        from algo_studio.core.task import TaskManager
        TaskManager._instances = {}
    except ImportError:
        pass


@pytest.fixture
def mock_progress_store(mocker):
    """Mock ProgressStore for SSE tests.

    Provides a mock progress store that can be configured to return
    specific progress values during SSE endpoint testing.
    """
    mock_store = MagicMock()
    mock_store.get.remote = AsyncMock(return_value=0)
    mock_store.get_task_progress.remote = AsyncMock(return_value={'progress': 0, 'status': 'pending'})

    mocker.patch(
        'algo_studio.core.task.get_progress_store',
        return_value=mock_store
    )
    mocker.patch(
        'algo_studio.api.routes.tasks.get_progress_store',
        return_value=mock_store
    )

    yield mock_store


@pytest.fixture
def mock_task_manager(mocker):
    """Mock TaskManager for route tests.

    Provides a mock task manager that doesn't interact with the real
    TaskManager instance.
    """
    mock_manager = MagicMock()

    # Configure default task responses
    mock_task = MagicMock()
    mock_task.task_id = "test-task-123"
    mock_task.task_type = "train"
    mock_task.algorithm_name = "simple_classifier"
    mock_task.algorithm_version = "v1"
    mock_task.status = TaskStatus.PENDING  # Use TaskStatus enum, not MagicMock
    mock_task.created_at = datetime.now()
    mock_task.started_at = None
    mock_task.completed_at = None
    mock_task.assigned_node = None
    mock_task.error = None
    mock_task.progress = 0

    mock_manager.get_task.return_value = mock_task
    mock_manager.list_tasks_paginated.return_value = ([], None)
    mock_manager.create_task.return_value = mock_task

    mocker.patch('algo_studio.api.routes.tasks.task_manager', mock_manager)

    yield mock_manager


class MockUser:
    """Mock authenticated user for tests."""

    def __init__(self, user_id="test-user", username="testuser", role="developer"):
        self.user_id = user_id
        self.username = username
        self.role = role


@pytest.fixture
def authenticated_user():
    """Provide an authenticated user object for route tests."""
    return MockUser()


@pytest.fixture
def admin_user():
    """Provide an admin user object for route tests."""
    return MockUser(user_id="admin-user", username="admin", role="admin")
