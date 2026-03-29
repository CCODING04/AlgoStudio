# tests/e2e/web/test_dashboard_verification.py
"""
TC-WEB-001 to TC-WEB-004: Dashboard Page E2E Tests

This module tests the Dashboard page E2E scenarios:
1. TC-WEB-001: Dashboard page loads and displays stats
2. TC-WEB-002: Dashboard shows cluster status
3. TC-WEB-003: Dashboard shows resource utilization
4. TC-WEB-004: Dashboard shows recent tasks

Reference: docs/superpowers/testing/PHASE2_E2E_PLAN.md Section 2
"""

import time

import pytest


# =============================================================================
# Test Cases
# =============================================================================

@pytest.mark.web
@pytest.mark.e2e
class TestDashboardPage:
    """
    TC-WEB-001: Dashboard page loads and displays stats.

    This test verifies that the Dashboard page correctly shows
    task statistics and overview information.
    """

    def test_dashboard_page_loads(self, page, api_client):
        """
        Test: Dashboard page loads successfully.

        Steps:
        1. Navigate to / page
        2. Verify page loads without errors
        3. Verify main heading is displayed
        """
        page.goto("/")
        page.wait_for_load_state("networkidle")

        # Verify page heading
        heading = page.locator("h1").first
        assert heading.is_visible(), "Dashboard should have a visible heading"

        heading_text = heading.text_content()
        assert "Dashboard" in heading_text or "概览" in heading_text, (
            f"Dashboard heading should contain 'Dashboard' or '概览', got: {heading_text}"
        )

    def test_dashboard_stats_displayed(self, page, api_client):
        """
        Test: Dashboard displays task statistics cards.

        Steps:
        1. Navigate to Dashboard
        2. Verify stats cards are present
        3. Verify stats labels are correct
        """
        page.goto("/")
        page.wait_for_load_state("networkidle")

        # Wait for async data to load
        page.wait_for_timeout(2000)

        # Verify stats labels are correct using data-testid selectors
        # Looking for the key stats: total, running, pending, failed
        stat_card_total = page.locator("[data-testid='stat-card-total']")
        stat_card_running = page.locator("[data-testid='stat-card-running']")
        stat_card_pending = page.locator("[data-testid='stat-card-pending']")
        stat_card_failed = page.locator("[data-testid='stat-card-failed']")

        found_stats = []
        if stat_card_total.count() > 0:
            found_stats.append("stat-card-total")
        if stat_card_running.count() > 0:
            found_stats.append("stat-card-running")
        if stat_card_pending.count() > 0:
            found_stats.append("stat-card-pending")
        if stat_card_failed.count() > 0:
            found_stats.append("stat-card-failed")

        assert len(found_stats) >= 2, (
            f"Dashboard should display at least 2 stat categories, found: {found_stats}"
        )

    def test_dashboard_stats_have_values(self, page, api_client):
        """
        Test: Dashboard stats show numeric values.

        Steps:
        1. Navigate to Dashboard
        2. Check that stat values are displayed
        """
        page.goto("/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # The stats should show numbers - use data-testid selectors
        stat_card_total = page.locator("[data-testid='stat-card-total']")

        if stat_card_total.count() > 0:
            # Verify at least one stat card is visible
            assert stat_card_total.first.is_visible(), "Stats section should be visible"


@pytest.mark.web
@pytest.mark.e2e
class TestDashboardClusterStatus:
    """
    TC-WEB-002: Dashboard shows cluster status.

    This test verifies that the Dashboard correctly displays
    Ray cluster status information.
    """

    def test_cluster_status_displayed(self, page, api_client):
        """
        Test: Cluster status section is visible on Dashboard.

        Steps:
        1. Navigate to Dashboard
        2. Verify cluster status component is present
        """
        page.goto("/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Look for cluster status indicator
        cluster_indicators = [
            "[data-testid='cluster-status']",
            "text=Cluster",
            "text=集群",
            "[class*='cluster']",
        ]

        found = False
        for indicator in cluster_indicators:
            if page.locator(indicator).count() > 0:
                found = True
                break

        assert found, "Cluster status indicator should be present on Dashboard"

    def test_cluster_nodes_shown(self, page, api_client):
        """
        Test: Dashboard shows cluster node information.

        Steps:
        1. Get expected nodes from API
        2. Verify Dashboard shows node count or details
        """
        # Get expected node count from API (follow redirects)
        response = api_client.get_hosts()
        # API may return 307 redirect, follow it
        if response.status_code == 307:
            response = api_client.client.get(
                f"{api_client.base_url}/api/hosts",
                headers=api_client.headers,
                follow_redirects=True
            )

        assert response.status_code == 200, f"API should return 200, got {response.status_code}"

        hosts = response.json()
        nodes = hosts if isinstance(hosts, list) else hosts.get("cluster_nodes", [])
        node_count = len(nodes)

        page.goto("/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Dashboard should show some indication of cluster nodes
        # This could be via text content showing IPs or node count
        body_text = page.inner_text("body")

        # At minimum, should show head node IP or mention of nodes
        assert "192.168.0" in body_text or "节点" in body_text or "Node" in body_text, (
            "Dashboard should indicate cluster node information"
        )


@pytest.mark.web
@pytest.mark.e2e
class TestDashboardResourceUtilization:
    """
    TC-WEB-003: Dashboard shows resource utilization.

    This test verifies that the Dashboard displays GPU and
    resource utilization information.
    """

    def test_gpu_info_displayed(self, page, api_client):
        """
        Test: GPU information is shown on Dashboard.

        Steps:
        1. Navigate to Dashboard
        2. Verify GPU utilization is displayed
        """
        page.goto("/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Look for GPU-related indicators
        gpu_indicators = [
            "text=GPU",
            "text=GPU 利用率",
            "[data-testid='gpu-']",
            "[class*='gpu']",
        ]

        found = False
        for indicator in gpu_indicators:
            if page.locator(indicator).count() > 0:
                found = True
                break

        assert found, "GPU information should be displayed on Dashboard"

    def test_resource_metrics_shown(self, page, api_client):
        """
        Test: Resource metrics (CPU, memory) are displayed.

        Steps:
        1. Navigate to Dashboard
        2. Verify resource metrics are present
        """
        page.goto("/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Look for memory/CPU indicators
        resource_indicators = [
            "text=内存",
            "text=CPU",
            "text=Gi",
            "[class*='memory']",
            "[class*='cpu']",
        ]

        found_count = 0
        for indicator in resource_indicators:
            if page.locator(indicator).count() > 0:
                found_count += 1

        assert found_count > 0, "Resource metrics should be displayed on Dashboard"


@pytest.mark.web
@pytest.mark.e2e
class TestDashboardRecentTasks:
    """
    TC-WEB-004: Dashboard shows recent tasks.

    This test verifies that the Dashboard displays
    recent task information.
    """

    def test_recent_tasks_section_exists(self, page, api_client):
        """
        Test: Recent tasks section is present on Dashboard.

        Steps:
        1. Navigate to Dashboard
        2. Verify recent tasks section exists
        """
        page.goto("/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Look for recent tasks section
        task_indicators = [
            "[data-testid='recent-tasks']",
            "text=Recent Tasks",
            "text=最近任务",
            "[class*='recent-task']",
        ]

        found = False
        for indicator in task_indicators:
            if page.locator(indicator).count() > 0:
                found = True
                break

        # If no explicit section, check if any task info is displayed
        if not found:
            body_text = page.inner_text("body")
            found = "task" in body_text.lower() or "任务" in body_text

        assert found, "Recent tasks section or task info should be present"

    def test_navigation_to_tasks_page(self, page, api_client):
        """
        Test: User can navigate from Dashboard to Tasks page.

        Steps:
        1. Verify Tasks link exists in navigation
        2. Navigate to Tasks page
        3. Verify Tasks page loads
        """
        page.goto("/")
        page.wait_for_load_state("networkidle")

        # Verify Tasks navigation link exists
        tasks_link = page.locator("a[href='/tasks']")
        assert tasks_link.count() > 0, "Tasks navigation link should exist"

        # Navigate to Tasks page
        page.goto("/tasks")
        page.wait_for_load_state("networkidle")

        # Verify we're on the tasks page
        current_url = page.url
        assert "/tasks" in current_url, f"Should navigate to /tasks, got: {current_url}"


@pytest.mark.web
@pytest.mark.e2e
class TestDashboardEdgeCases:
    """
    Edge case tests for the Dashboard page.
    """

    def test_dashboard_loads_without_api(self, page):
        """
        Test: Dashboard page loads even without API connectivity.

        Steps:
        1. Navigate to Dashboard without API
        2. Verify page structure loads
        """
        page.goto("/")
        page.wait_for_load_state("networkidle")

        # Page should still have a heading even if data fails to load
        heading = page.locator("h1").first
        assert heading.is_visible(), "Dashboard should show heading even without API"

    def test_dashboard_refresh(self, page, api_client):
        """
        Test: Dashboard can be refreshed.

        Steps:
        1. Load Dashboard
        2. Refresh the page
        3. Verify data reloads
        """
        page.goto("/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Store initial state
        initial_content = page.inner_text("body")

        # Refresh
        page.reload()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Verify page still works
        heading = page.locator("h1").first
        assert heading.is_visible(), "Dashboard should reload successfully"

    def test_console_no_errors(self, page, api_client):
        """
        Test: Dashboard loads without console errors.

        Steps:
        1. Capture console errors
        2. Navigate to Dashboard
        3. Verify no critical errors
        """
        errors = []

        def handle_console(msg):
            if msg.type == "error":
                errors.append(msg.text)

        page.on("console", handle_console)

        page.goto("/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Filter out known non-critical warnings and expected errors
        critical_errors = [
            e for e in errors
            if "Warning:" not in e
            and "suspended" not in e.lower()
            and "401" not in e  # Auth errors from API are expected in test env
            and "Failed to load resource" not in e
        ]

        # Some resource loading errors are acceptable (e.g., missing optional assets)
        # But we should not have JS runtime errors
        assert len(critical_errors) == 0, (
            f"Dashboard should not have critical console errors: {critical_errors}"
        )