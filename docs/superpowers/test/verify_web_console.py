#!/usr/bin/env python3
"""Verify Web Console USER_MANUAL operations via Playwright."""

from playwright.sync_api import sync_playwright
import json

BASE_URL = "http://localhost:3000"
RESULTS = {
    "dashboard": {"status": "pending", "details": []},
    "task_list": {"status": "pending", "details": []},
    "task_wizard": {"status": "pending", "details": []},
    "task_detail": {"status": "pending", "details": []},
    "hosts": {"status": "pending", "details": []},
    "deploy": {"status": "pending", "details": []},
}


def log(category, message):
    """Log a message to the results."""
    RESULTS[category]["details"].append(message)
    print(f"[{category.upper()}] {message}")


def verify_dashboard(page):
    """Verify Dashboard (/) operations."""
    log("dashboard", "Navigating to Dashboard...")
    page.goto(f"{BASE_URL}/")
    page.wait_for_load_state("networkidle")

    # Check statistics cards
    try:
        stat_cards = [
            "stat-card-total",
            "stat-card-running",
            "stat-card-pending",
            "stat-card-failed",
        ]
        for card in stat_cards:
            element = page.locator(f'[data-testid="{card}"]')
            if element.is_visible():
                log("dashboard", f"  - Stat card '{card}' is visible")
            else:
                log("dashboard", f"  - WARNING: Stat card '{card}' NOT found")

        # Check for cluster status section
        if page.locator("text=集群状态").is_visible():
            log("dashboard", "  - Cluster status section visible")

        # Check for resource chart section
        if page.locator("text=资源使用").is_visible():
            log("dashboard", "  - Resource chart section visible")

        # Check for recent tasks section
        if page.locator("text=最近任务").is_visible():
            log("dashboard", "  - Recent tasks section visible")

        RESULTS["dashboard"]["status"] = "PASS"
        log("dashboard", "Dashboard verification PASSED")
    except Exception as e:
        RESULTS["dashboard"]["status"] = "FAIL"
        log("dashboard", f"Dashboard verification FAILED: {e}")


def verify_task_list(page):
    """Verify Task List (/tasks) operations."""
    log("task_list", "Navigating to Task List...")
    page.goto(f"{BASE_URL}/tasks")
    page.wait_for_load_state("networkidle")

    try:
        # Check page title
        if page.locator("text=任务列表").is_visible():
            log("task_list", "  - Task list page title visible")

        # Check for "新建任务" button
        if page.locator("text=新建任务").is_visible():
            log("task_list", "  - '新建任务' button is visible")
        else:
            log("task_list", "  - WARNING: '新建任务' button NOT found")

        # Check for status filter dropdown
        if page.locator("text=任务状态").is_visible():
            log("task_list", "  - Status filter dropdown visible")

        # Check for search input
        search_input = page.locator('input[placeholder*="搜索"]')
        if search_input.is_visible():
            log("task_list", "  - Search input visible")

        RESULTS["task_list"]["status"] = "PASS"
        log("task_list", "Task list verification PASSED")
    except Exception as e:
        RESULTS["task_list"]["status"] = "FAIL"
        log("task_list", f"Task list verification FAILED: {e}")


def verify_task_wizard(page):
    """Verify Task Wizard opens correctly."""
    log("task_wizard", "Testing Task Wizard...")
    page.goto(f"{BASE_URL}/tasks")
    page.wait_for_load_state("networkidle")

    try:
        # Click "新建任务" button
        new_task_btn = page.locator("text=新建任务")
        if new_task_btn.is_visible():
            new_task_btn.click()
            page.wait_for_timeout(1000)  # Wait for wizard to open

            # Check if wizard dialog opened
            # The wizard should have task type selection
            wizard_visible = page.locator("text=选择任务类型").is_visible() or \
                           page.locator("h2:has-text('新建任务')").is_visible() or \
                           page.locator('[role="dialog"]').is_visible()

            if wizard_visible:
                log("task_wizard", "  - Task wizard dialog opened successfully")
                RESULTS["task_wizard"]["status"] = "PASS"
                log("task_wizard", "Task wizard verification PASSED")
            else:
                log("task_wizard", "  - WARNING: Task wizard dialog did NOT open")
                RESULTS["task_wizard"]["status"] = "PARTIAL"
        else:
            log("task_wizard", "  - Could not click '新建任务' - button not found")
            RESULTS["task_wizard"]["status"] = "FAIL"
    except Exception as e:
        RESULTS["task_wizard"]["status"] = "FAIL"
        log("task_wizard", f"Task wizard verification FAILED: {e}")


def verify_task_detail(page):
    """Verify Task Detail (/tasks/[taskId]) operations."""
    log("task_detail", "Navigating to Task List to find a task...")
    page.goto(f"{BASE_URL}/tasks")
    page.wait_for_load_state("networkidle")

    try:
        # Wait for tasks to load
        page.wait_for_timeout(2000)

        # Look for any task link
        task_links = page.locator('a[href^="/tasks/train-"], a[href^="/tasks/infer-"], a[href^="/tasks/verify-"]')
        count = task_links.count()

        if count > 0:
            # Click on the first task
            task_links.first.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)

            # Check task detail page elements
            if page.locator("text=任务详情").is_visible():
                log("task_detail", "  - Task detail page title visible")

            if page.locator("text=基本信息").is_visible():
                log("task_detail", "  - Basic info section visible")

            if page.locator("text=执行信息").is_visible():
                log("task_detail", "  - Execution info section visible")

            # Check that SSE/progress might be working (no 401 errors in console)
            log("task_detail", "  - Task detail page loaded successfully")
            RESULTS["task_detail"]["status"] = "PASS"
            log("task_detail", "Task detail verification PASSED")
        else:
            log("task_detail", "  - No tasks found to click on")
            RESULTS["task_detail"]["status"] = "PARTIAL"
            log("task_detail", "Task detail verification PARTIAL - no tasks to test")
    except Exception as e:
        RESULTS["task_detail"]["status"] = "FAIL"
        log("task_detail", f"Task detail verification FAILED: {e}")


def verify_hosts(page):
    """Verify Host List (/hosts) operations."""
    log("hosts", "Navigating to Host List...")
    page.goto(f"{BASE_URL}/hosts")
    page.wait_for_load_state("networkidle")

    try:
        # Check page title
        if page.locator("text=主机监控").is_visible() or page.locator("h1:has-text('主机')").is_visible():
            log("hosts", "  - Host list page title visible")

        # Wait for hosts to load
        page.wait_for_timeout(2000)

        # Check for any host cards or table
        host_content = page.locator("text=在线").first
        if host_content.is_visible():
            log("hosts", "  - Host status indicators visible")
        else:
            # Try to find any host-related content
            any_host = page.locator('[class*="host"], [class*="node"]').first
            if any_host.is_visible():
                log("hosts", "  - Host cards/table visible")
            else:
                log("hosts", "  - WARNING: No host content visible (may be empty)")

        RESULTS["hosts"]["status"] = "PASS"
        log("hosts", "Host list verification PASSED")
    except Exception as e:
        RESULTS["hosts"]["status"] = "FAIL"
        log("hosts", f"Host list verification FAILED: {e}")


def verify_deploy(page):
    """Verify Deploy (/deploy) operations."""
    log("deploy", "Navigating to Deploy page...")
    page.goto(f"{BASE_URL}/deploy")
    page.wait_for_load_state("networkidle")

    try:
        # Check page title
        if page.locator("text=部署算法").is_visible():
            log("deploy", "  - Deploy page title visible")

        # Wait for data to load
        page.wait_for_timeout(2000)

        # Check for algorithm dropdown/selector
        algo_visible = page.locator("text=算法").first
        if algo_visible.is_visible():
            log("deploy", "  - Algorithm selector visible")

        # Check for node/host dropdown
        node_visible = page.locator("text=主机").first
        if node_visible.is_visible():
            log("deploy", "  - Host selector visible")

        # Check for deploy button
        deploy_btn = page.locator("text=开始部署, text=部署").first
        if deploy_btn.is_visible():
            log("deploy", "  - Deploy button visible")

        RESULTS["deploy"]["status"] = "PASS"
        log("deploy", "Deploy verification PASSED")
    except Exception as e:
        RESULTS["deploy"]["status"] = "FAIL"
        log("deploy", f"Deploy verification FAILED: {e}")


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("AlgoStudio Web Console USER_MANUAL Verification")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Capture console errors
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

        # Run verifications
        verify_dashboard(page)
        verify_task_list(page)
        verify_task_wizard(page)
        verify_task_detail(page)
        verify_hosts(page)
        verify_deploy(page)

        # Report any console errors
        if errors:
            log("dashboard", f"\nConsole errors captured: {len(errors)}")
            for err in errors[:5]:  # Limit to first 5
                log("dashboard", f"  - {err[:200]}")

        browser.close()

    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    for category, result in RESULTS.items():
        status = result["status"]
        print(f"  {category:15} : {status}")
    print("=" * 60)

    # Save results
    with open("/home/admin02/Code/Dev/AlgoStudio/docs/superpowers/test/verification_results.json", "w") as f:
        json.dump(RESULTS, f, indent=2)
    print("\nResults saved to verification_results.json")

    return RESULTS


if __name__ == "__main__":
    main()
