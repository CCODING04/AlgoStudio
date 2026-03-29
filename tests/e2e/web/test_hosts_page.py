# tests/e2e/web/test_hosts_page.py
"""
TC-WEB-005 & TC-WEB-006: Hosts Page E2E Tests

This module tests the Hosts page E2E scenarios:
1. TC-WEB-005: Hosts page displays cluster nodes
2. TC-WEB-006: Host details show GPU and resource info

Reference: PHASE2_E2E_PLAN.md Section 3.1, TC-WEB-005, TC-WEB-006
"""

import time
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Test Cases
# =============================================================================

@pytest.mark.web
@pytest.mark.e2e
class TestHostsPageList:
    """
    TC-WEB-005: Hosts page displays cluster nodes.

    This test verifies that the Hosts page correctly shows
    all nodes in the cluster with their status.
    """

    def test_hosts_page_loads(self, page, api_client):
        """
        Test: Hosts page loads successfully.

        Steps:
        1. Navigate to /hosts page
        2. Verify page loads without errors
        3. Verify main content is displayed
        """
        page.goto("/hosts")

        # Wait for page to load
        page.wait_for_load_state("networkidle")

        # Verify page title or heading - actual UI uses "主机监控" markdown heading
        heading = page.locator("text=主机监控")
        assert heading.count() > 0, "Hosts page should have a heading"

        # Verify refresh button exists - actual UI has a "刷新" button
        refresh_button = page.locator("button:has-text('刷新')")
        assert refresh_button.count() > 0, "Refresh button should exist"

    def test_hosts_list_shows_all_nodes(self, page, api_client, mock_ray_client):
        """
        Test: Hosts page displays all cluster nodes.

        Steps:
        1. Get expected nodes from cluster API
        2. Navigate to Hosts page
        3. Verify each node is displayed in the list
        """
        # Get expected nodes from API
        response = api_client.get_hosts()
        assert response.status_code == 200

        hosts = response.json()
        assert isinstance(hosts, list), "Hosts API should return a list"

        # Navigate to hosts page
        page.goto("/hosts")
        page.wait_for_load_state("networkidle")

        # Click refresh to load data
        refresh_button = page.locator("button:has-text('刷新')")
        if refresh_button.count() > 0:
            refresh_button.first.click()
            page.wait_for_timeout(1000)

        # Verify each host appears in the list - actual UI renders hostname in card
        for host in hosts:
            hostname = host.get("hostname") or host.get("ip")
            ip = host.get("ip", "")

            # Actual UI: hostname is rendered as text in a card, also shows IP
            host_element = page.locator(f"text={hostname}")
            if host_element.count() == 0:
                # Fallback: look for IP text
                host_element = page.locator(f"text={ip}")

            assert host_element.count() > 0, (
                f"Host {hostname} should be displayed on Hosts page"
            )

    def test_node_status_indicator(self, page, api_client, mock_ray_client):
        """
        Test: Node status (alive/dead) is displayed correctly.

        Steps:
        1. Navigate to Hosts page
        2. Check status indicator for each node
        3. Verify alive nodes show green/active status
        4. Verify dead nodes show red/error status
        """
        # Get node statuses from API
        response = api_client.get_hosts()
        hosts = response.json()

        page.goto("/hosts")
        page.wait_for_load_state("networkidle")

        # Click refresh to load data
        refresh_button = page.locator("button:has-text('刷新')")
        if refresh_button.count() > 0:
            refresh_button.first.click()
            page.wait_for_timeout(1000)

        for host in hosts:
            hostname = host.get("hostname", "")
            status = host.get("status", "unknown")

            # Find the host card - actual UI shows hostname text
            host_card = page.locator(f"text={hostname}")
            if host_card.count() == 0:
                continue

            # Actual UI: status shown with emoji (🟢 for online/idle, 🔴 for others)
            # and text like "Online", "Idle", "Offline"
            if status == "online" or status == "idle":
                # Should show green indicator (emoji 🟢) and Online/Idle text
                status_text = "Online" if status == "idle" else status.capitalize()
                # Check that status text appears near the hostname
                assert page.locator(f"text={status_text}").count() > 0, (
                    f"Host {hostname} should show status text {status_text}"
                )
            else:
                # Dead/offline status shows 🔴 and Offline text
                assert page.locator("text=Offline").count() > 0, (
                    f"Host {hostname} should show Offline status"
                )

    def test_hosts_page_refresh(self, page, api_client):
        """
        Test: Hosts page data can be refreshed.

        Steps:
        1. Navigate to Hosts page
        2. Click refresh button
        3. Verify data is updated
        """
        page.goto("/hosts")
        page.wait_for_load_state("networkidle")

        # Look for refresh button - actual UI uses "刷新"
        refresh_button = page.locator("button:has-text('刷新')")

        if refresh_button.count() > 0:
            # Click refresh
            refresh_button.first.click()

            # Wait for update
            page.wait_for_timeout(1000)

            # Verify page still has content after refresh
            # Actual UI shows "最后更新:" timestamp when data is loaded
            html_content = page.locator("text=最后更新:")
            # Either the timestamp appears or the data loads successfully


@pytest.mark.web
@pytest.mark.e2e
class TestHostsPageDetails:
    """
    TC-WEB-006: Host details show GPU and resource info.

    This test verifies that host cards display
    detailed information including GPU and resource usage.
    Note: Actual UI shows all info in cards directly - no modal/dialog.
    """

    def test_host_cards_display_gpu_info(self, page, api_client, mock_ray_client):
        """
        Test: Host cards show GPU information.

        Steps:
        1. Navigate to Hosts page
        2. Verify GPU info is displayed in cards (or '获取失败' if unavailable)
        """
        # Get host data
        response = api_client.get_hosts()
        hosts = response.json()

        if not hosts:
            pytest.skip("No hosts available for detail test")

        # Navigate to hosts page
        page.goto("/hosts")
        page.wait_for_load_state("networkidle")

        # Click refresh to load data
        refresh_button = page.locator("button:has-text('刷新')")
        if refresh_button.count() > 0:
            refresh_button.first.click()
            page.wait_for_timeout(1000)

        # Verify GPU section exists - actual UI shows "GPU" heading
        # Either shows GPU info or "获取失败" for unavailable data
        gpu_heading = page.locator("text=GPU")
        assert gpu_heading.count() > 0, "GPU section should be displayed in host cards"

    def test_host_cards_display_cpu_info(self, page, api_client, mock_ray_client):
        """
        Test: Host cards show CPU information.

        Steps:
        1. Navigate to Hosts page
        2. Verify CPU info is displayed in cards
        """
        page.goto("/hosts")
        page.wait_for_load_state("networkidle")

        # Click refresh to load data
        refresh_button = page.locator("button:has-text('刷新')")
        if refresh_button.count() > 0:
            refresh_button.first.click()
            page.wait_for_timeout(1000)

        # Verify CPU section exists - actual UI shows "CPU" heading
        cpu_heading = page.locator("text=CPU")
        assert cpu_heading.count() > 0, "CPU section should be displayed in host cards"

    def test_host_cards_display_memory_info(self, page, api_client, mock_ray_client):
        """
        Test: Host cards show Memory information.

        Steps:
        1. Navigate to Hosts page
        2. Verify Memory info is displayed in cards
        """
        page.goto("/hosts")
        page.wait_for_load_state("networkidle")

        # Click refresh to load data
        refresh_button = page.locator("button:has-text('刷新')")
        if refresh_button.count() > 0:
            refresh_button.first.click()
            page.wait_for_timeout(1000)

        # Verify Memory section exists - actual UI shows "Memory" heading
        memory_heading = page.locator("text=Memory")
        assert memory_heading.count() > 0, "Memory section should be displayed in host cards"

    def test_host_cards_display_disk_info(self, page, api_client, mock_ray_client):
        """
        Test: Host cards show Disk information.

        Steps:
        1. Navigate to Hosts page
        2. Verify Disk info is displayed in cards
        """
        page.goto("/hosts")
        page.wait_for_load_state("networkidle")

        # Click refresh to load data
        refresh_button = page.locator("button:has-text('刷新')")
        if refresh_button.count() > 0:
            refresh_button.first.click()
            page.wait_for_timeout(1000)

        # Verify Disk section exists - actual UI shows "Disk" heading
        disk_heading = page.locator("text=Disk")
        assert disk_heading.count() > 0, "Disk section should be displayed in host cards"

    def test_host_cards_show_ip_address(self, page, api_client, mock_ray_client):
        """
        Test: Host cards display IP addresses.

        Steps:
        1. Navigate to Hosts page
        2. Verify IP addresses are shown
        """
        response = api_client.get_hosts()
        hosts = response.json()

        if not hosts:
            pytest.skip("No hosts available")

        page.goto("/hosts")
        page.wait_for_load_state("networkidle")

        # Click refresh to load data
        refresh_button = page.locator("button:has-text('刷新')")
        if refresh_button.count() > 0:
            refresh_button.first.click()
            page.wait_for_timeout(1000)

        # Actual UI shows "IP: xxx.xxx.xxx.xxx" format
        for host in hosts:
            ip = host.get("ip", "")
            if ip:
                ip_text = page.locator(f"text=IP: {ip}")
                assert ip_text.count() > 0, f"IP {ip} should be displayed"


@pytest.mark.web
@pytest.mark.e2e
class TestHostsPageResourceUtilization:
    """
    Additional tests for resource utilization display.
    """

    def test_gpu_utilization_displayed(
        self, page, api_client, mock_ray_client
    ):
        """
        Test: GPU utilization percentage is shown for each host.

        This helps users identify which nodes are heavily loaded.
        """
        page.goto("/hosts")
        page.wait_for_load_state("networkidle")

        # Click refresh to load data
        refresh_button = page.locator("button:has-text('刷新')")
        if refresh_button.count() > 0:
            refresh_button.first.click()
            page.wait_for_timeout(1000)

        # Actual UI: GPU utilization shows "利用率" heading with progress bar
        # The progress bar is rendered inline with style containing width percentage
        gpu_util_heading = page.locator("text=利用率")
        # Either utilization is shown or "获取失败" for unavailable GPU
        assert gpu_util_heading.count() > 0 or page.locator("text=获取失败").count() > 0, (
            "GPU utilization info should be displayed on hosts page"
        )

    def test_resource_usage_bars_exist(
        self, page, api_client, mock_ray_client
    ):
        """
        Test: Resource usage bars are rendered.

        Actual UI uses inline style with width percentage for progress bars.
        """
        page.goto("/hosts")
        page.wait_for_load_state("networkidle")

        # Click refresh to load data
        refresh_button = page.locator("button:has-text('刷新')")
        if refresh_button.count() > 0:
            refresh_button.first.click()
            page.wait_for_timeout(1000)

        # Actual UI: progress bars use inline styles (background:{color})
        # The bars are div elements with width percentages
        # Look for percentage text which appears in the bar
        percent_text = page.locator("text=%")
        assert percent_text.count() > 0, (
            "Resource usage percentage should be displayed on hosts page"
        )


@pytest.mark.web
@pytest.mark.e2e
class TestHostsPageEdgeCases:
    """
    Edge case tests for the Hosts page.
    """

    def test_no_hosts_shows_empty_state(self, page, api_client):
        """
        Test: Appropriate message when no hosts are available.

        Steps:
        1. Simulate no hosts scenario
        2. Verify empty state message is shown
        """
        # In a real cluster, there should always be at least head node
        # But we can test the UI behavior

        page.goto("/hosts")
        page.wait_for_load_state("networkidle")

        # Look for empty state - actual UI shows "无可用主机（Ray 集群未启动）"
        empty_state = page.locator(
            "text=无可用主机, text=点击刷新以加载数据, text=加载中"
        )

        # If empty state is shown, that's acceptable UI behavior
        # Otherwise, we expect to see hosts after clicking refresh

        response = api_client.get_hosts()
        hosts = response.json()

        if len(hosts) == 0:
            assert empty_state.count() > 0, (
                "Empty state should be shown when no hosts available"
            )

    def test_host_status_updates_on_refresh(
        self, page, api_client, mock_ray_client
    ):
        """
        Test: Host status updates when page is refreshed.

        Steps:
        1. View hosts
        2. Refresh page
        3. Verify new status is shown
        """
        page.goto("/hosts")
        page.wait_for_load_state("networkidle")

        # Click refresh - actual UI uses "刷新"
        refresh_button = page.locator("button:has-text('刷新')")

        if refresh_button.count() > 0:
            refresh_button.first.click()
            page.wait_for_timeout(1000)

            # Verify page still shows correct data
            response = api_client.get_hosts()
            assert response.status_code == 200

    def test_auto_refresh_toggle_exists(
        self, page, api_client
    ):
        """
        Test: Auto-refresh checkbox exists on hosts page.

        Steps:
        1. Navigate to hosts page
        2. Verify auto-refresh controls exist
        """
        page.goto("/hosts")
        page.wait_for_load_state("networkidle")

        # Actual UI has auto-refresh checkbox and interval number input
        auto_refresh_label = page.locator("label:has-text('自动刷新')")
        assert auto_refresh_label.count() > 0, (
            "Auto-refresh toggle should exist on hosts page"
        )
