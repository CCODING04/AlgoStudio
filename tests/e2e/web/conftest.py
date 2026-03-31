# tests/e2e/web/conftest.py
"""
Pytest configuration and fixtures for AlgoStudio Web E2E tests.

This module provides Playwright browser/page fixtures and API client
for web console testing.
"""

import os
from typing import Optional

import pytest
from playwright.sync_api import sync_playwright


# =============================================================================
# Configuration
# =============================================================================

WEB_BASE_URL = os.getenv("WEB_BASE_URL", "http://localhost:3000")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


# =============================================================================
# Fixtures
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
        # Add auth headers for API calls
        extra_http_headers={
            "X-User-ID": "test-user",
            "X-User-Role": "admin",
        },
    )
    yield context
    context.close()


@pytest.fixture
def page(context):
    """Provide a new page for each test."""
    page = context.new_page()

    # Set mock credentials before any navigation using add_init_script
    # This runs before any JavaScript on the page
    context.add_init_script("""
        // Override getStoredCredentials before the page loads
        // This prevents the credential modal from appearing
        Object.defineProperty(window, 'getStoredCredentials', {
            value: function() {
                return {
                    username: 'admin02',
                    password: 'test-password',
                    credentialId: 'test-credential-id'
                };
            },
            writable: false,
            configurable: true
        });
    """)

    yield page
    page.close()


def _dismiss_modal(page):
    """Helper to dismiss credential modal if present."""
    import time
    start_time = time.time()
    while time.time() - start_time < 3:
        try:
            modal = page.locator('[data-testid="credential-modal"]')
            if modal.count() > 0 and modal.is_visible():
                # Modal is visible, dismiss it - try pressing Escape first
                page.keyboard.press("Escape")
                page.wait_for_timeout(1000)
                # Check if modal is gone
                modal = page.locator('[data-testid="credential-modal"]')
                if modal.count() == 0 or not modal.is_visible():
                    return
                # Try clicking the cancel button directly
                try:
                    page.locator('[data-testid="credential-cancel"]').click(force=True, timeout=2000)
                    page.wait_for_timeout(500)
                    return
                except Exception:
                    pass
                # Try filling in credentials and saving
                try:
                    page.fill('[data-testid="credential-username"]', 'admin02', timeout=2000)
                    page.fill('[data-testid="credential-password"]', 'test-password', timeout=2000)
                    page.locator('[data-testid="credential-save"]').click(force=True, timeout=2000)
                    page.wait_for_timeout(500)
                    return
                except Exception:
                    pass
                page.wait_for_timeout(500)
            else:
                page.wait_for_timeout(500)
        except Exception:
            page.wait_for_timeout(500)


@pytest.fixture(scope="session")
def api_client():
    """Provide a simple API client for tests."""
    import httpx

    class APIClient:
        def __init__(self, base_url: str):
            self.base_url = base_url
            self.headers = {
                "X-User-ID": "test-user",
                "X-User-Role": "admin",
            }
            self.client = httpx.Client(base_url=base_url, headers=self.headers, timeout=30.0, follow_redirects=True)

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

        def list_deployments(self, status: Optional[str] = None, node_ip: Optional[str] = None):
            params = {}
            if status:
                params["status"] = status
            if node_ip:
                params["node_ip"] = node_ip
            return self.client.get("/api/deploy/workers", params=params)

        def get_deployment(self, task_id: str):
            return self.client.get(f"/api/deploy/worker/{task_id}")

        def create_deployment(self, deploy_data: dict):
            return self.client.post("/api/deploy/worker", json=deploy_data)

        def get_deployment_progress(self, task_id: str):
            return self.client.get(f"/api/deploy/worker/{task_id}/progress")

        def close(self):
            self.client.close()

    return APIClient(base_url=API_BASE_URL)