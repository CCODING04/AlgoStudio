# tests/e2e/playwright.config.py
"""
Playwright configuration for AlgoStudio E2E tests.

This module provides a unified Python-based Playwright configuration.
All E2E tests use Python Playwright (playwright.sync_api).

Version: Python Playwright >= 1.40
"""

import os
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright


# =============================================================================
# Configuration
# =============================================================================

TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent.parent

# Environment variables with defaults
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "http://localhost:3000")
RAY_ADDRESS = os.getenv("RAY_ADDRESS", "192.168.0.126:6379")
RAY_HEAD_HOST = os.getenv("RAY_HEAD_HOST", "192.168.0.126")

# CI mode detection
IS_CI = os.getenv("CI", "").lower() in ("true", "1", "yes")


# =============================================================================
# Playwright Options
# =============================================================================

def get_playwright_config() -> dict:
    """
    Returns Playwright configuration dictionary.

    This replaces the TypeScript playwright.config.ts with a Python-only
    approach to ensure consistency across the test suite.
    """
    return {
        "test_dir": str(TEST_DIR),
        "fully_parallel": not IS_CI,
        "forbid_only": IS_CI,
        "retries": 2 if IS_CI else 1,
        "workers": 1 if IS_CI else None,  # None = auto
        "timeout": 30000,  # 30 seconds
        "expect_timeout": 10000,  # 10 seconds for expect
        "headless": True,
        "screenshot": "only-on-failure" if not IS_CI else "always",
        "video": "retain-on-failure" if not IS_CI else "off",
        "trace": "on-first-retry" if not IS_CI else "off",
        "base_url": WEB_BASE_URL,
        "api_base_url": API_BASE_URL,
        "ray_address": RAY_ADDRESS,
        "ray_head_host": RAY_HEAD_HOST,
    }


# =============================================================================
# Browser Projects
# =============================================================================

BROWSER_PROJECTS = [
    {
        "name": "chromium",
        "browser_name": "chromium",
        "channel": None,
        "headless": True,
    },
    # Firefox and Safari can be enabled for cross-browser testing
    # {
    #     "name": "firefox",
    #     "browser_name": "firefox",
    #     "headless": True,
    # },
]


# =============================================================================
# Pytest Configuration
# =============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "e2e: end-to-end tests")
    config.addinivalue_line("markers", "slow: slow running tests")
    config.addinivalue_line("markers", "cluster: cluster tests")
    config.addinivalue_line("markers", "web: web console tests")
    config.addinivalue_line("markers", "ssh: SSH deployment tests")
    config.addinivalue_line("markers", "mock: tests using mocks")
    config.addinivalue_line("markers", "skip_ci: tests that cannot run in CI environments")


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def browser_config():
    """Provide browser configuration for tests."""
    return get_playwright_config()


@pytest.fixture(scope="session")
def api_client():
    """Provide a simple API client for tests."""
    import httpx

    class APIClient:
        def __init__(self, base_url: str, api_key: str = "test-api-key"):
            self.base_url = base_url
            self.headers = {"X-API-Key": api_key}
            self.client = httpx.Client(base_url=base_url, headers=self.headers, timeout=30.0)

        def get_tasks(self, status: Optional[str] = None):
            params = {"status": status} if status else {}
            return self.client.get("/api/tasks", params=params)

        def get_task(self, task_id: str):
            return self.client.get(f"/api/tasks/{task_id}")

        def create_task(self, task_data: dict):
            return self.client.post("/api/tasks", json=task_data)

        def cancel_task(self, task_id: str):
            return self.client.post(f"/api/tasks/{task_id}/cancel")

        def get_hosts(self):
            return self.client.get("/api/hosts")

        def get_host(self, node_id: str):
            return self.client.get(f"/api/hosts/{node_id}")

        # Deployment methods
        def list_deployments(self, status: Optional[str] = None, node_ip: Optional[str] = None):
            """List all deployment records with optional filtering."""
            params = {}
            if status:
                params["status"] = status
            if node_ip:
                params["node_ip"] = node_ip
            return self.client.get("/api/deploy/workers", params=params)

        def get_deployment(self, task_id: str):
            """Get specific deployment details by task ID."""
            return self.client.get(f"/api/deploy/worker/{task_id}")

        def create_deployment(self, deploy_data: dict):
            """Trigger new worker deployment."""
            return self.client.post("/api/deploy/worker", json=deploy_data)

        def get_deployment_progress(self, task_id: str):
            """Get SSE progress stream for deployment task."""
            # Note: This returns the raw response for SSE handling
            return self.client.get(f"/api/deploy/worker/{task_id}/progress")

        def close(self):
            self.client.close()

    return APIClient(base_url=API_BASE_URL)


@pytest.fixture(scope="session")
def ray_cluster():
    """Provide Ray cluster connection info."""
    return {
        "address": RAY_ADDRESS,
        "head_host": RAY_HEAD_HOST,
    }


# =============================================================================
# Session Scoped Browser Fixture
# =============================================================================

@pytest.fixture(scope="session")
def playwright_instance():
    """Provide a playwright instance for the test session."""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright_instance):
    """Provide a browser instance for all tests."""
    browser = playwright_instance.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    yield browser
    browser.close()


@pytest.fixture
def context(browser):
    """Provide a new browser context for each test."""
    context = browser.new_context(
        base_url=WEB_BASE_URL,
        ignore_https_errors=True,
    )
    yield context
    context.close()


@pytest.fixture
def page(context):
    """Provide a new page for each test."""
    page = context.new_page()
    yield page
    page.close()
