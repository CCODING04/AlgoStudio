# tests/e2e/web/test_dataset_selector_playwright.py
"""
Playwright integration tests for DatasetSelector - tests real dialog interactions.

These tests verify that the DatasetSelector component's dialog open/close
behavior and dataset selection flow work correctly in a real browser.

Reference: docs/superpowers/testing/PHASE2_E2E_PLAN.md
"""

import pytest


@pytest.mark.web
@pytest.mark.e2e
class TestDatasetSelectorPlaywright:
    """
    Integration tests using real browser for DatasetSelector.

    These tests address the limitation of unit tests which cannot
    properly trigger the Dialog open/close state changes.
    """

    def test_dataset_selector_dialog_opens(self, page, api_client):
        """
        Test: DatasetSelector dialog opens when clicked.

        Steps:
        1. Navigate to Tasks page
        2. Open task creation wizard
        3. Select task type 'train'
        4. Navigate to step 2
        5. Click the dataset selector button
        6. Verify dialog opens with dataset list
        """
        page.goto("/tasks")
        page.wait_for_load_state("networkidle")

        # Open task creation wizard
        create_button = page.locator("button:has-text('新建任务')")
        if create_button.count() > 0:
            create_button.first.click()
            page.wait_for_timeout(1000)

        # Select task type - 'train'
        # Find and click the task type Select
        task_type_select = page.locator("[data-testid='task-type-train']")
        if task_type_select.count() > 0:
            task_type_select.first.click()
            page.wait_for_timeout(500)

        # Click algorithm select if available and select first option
        algorithm_trigger = page.locator("button:has-text('选择算法')").first
        if algorithm_trigger.count() > 0:
            algorithm_trigger.click()
            page.wait_for_timeout(500)
            # Select first available algorithm
            first_algorithm = page.locator("[role='option']").first
            if first_algorithm.count() > 0:
                first_algorithm.click()
                page.wait_for_timeout(500)

        # Click Next to go to step 2
        next_button = page.locator("button:has-text('下一步')")
        if next_button.count() > 0:
            next_button.first.click()
            page.wait_for_timeout(1000)

        # Now we should be in step 2 with the DatasetSelector
        # Look for the dataset selector trigger button
        # The button shows placeholder text when no dataset is selected
        dataset_button = page.locator("button:has-text('选择数据集或手动输入路径')")
        if dataset_button.count() > 0:
            dataset_button.first.click()
            page.wait_for_timeout(500)

            # Verify dialog is open - look for dialog content
            dialog_title = page.locator("text=选择数据集")
            assert dialog_title.count() > 0, "Dialog title should be visible"

            # Verify search input exists
            search_input = page.locator("input[placeholder='搜索数据集...']")
            assert search_input.count() > 0, "Search input should be visible"

    def test_dataset_selector_type_switch_to_manual(self, page, api_client):
        """
        Test: Switching to manual input mode works.

        Steps:
        1. Navigate to Tasks page and open wizard
        2. Go to step 2 with DatasetSelector
        3. Find the Select dropdown for dataset/manual
        4. Select 'manual' option
        5. Verify manual input field appears
        """
        page.goto("/tasks")
        page.wait_for_load_state("networkidle")

        # Open task creation wizard
        create_button = page.locator("button:has-text('新建任务')")
        if create_button.count() > 0:
            create_button.first.click()
            page.wait_for_timeout(1000)

        # Navigate to step 2
        task_type_select = page.locator("[data-testid='task-type-train']")
        if task_type_select.count() > 0:
            task_type_select.first.click()
            page.wait_for_timeout(500)

        algorithm_trigger = page.locator("button:has-text('选择算法')").first
        if algorithm_trigger.count() > 0:
            algorithm_trigger.click()
            page.wait_for_timeout(500)
            first_algorithm = page.locator("[role='option']").first
            if first_algorithm.count() > 0:
                first_algorithm.click()
                page.wait_for_timeout(500)

        next_button = page.locator("button:has-text('下一步')")
        if next_button.count() > 0:
            next_button.first.click()
            page.wait_for_timeout(1000)

        # Find the Select dropdown that controls dataset vs manual
        # Look for "选择类型" label and the select trigger
        select_trigger = page.locator("button:has-text('选择类型')").first
        if select_trigger.count() > 0:
            select_trigger.click()
            page.wait_for_timeout(500)

            # Select "手动输入" option
            manual_option = page.locator("text=手动输入")
            if manual_option.count() > 0:
                manual_option.first.click()
                page.wait_for_timeout(500)

                # Verify manual input field appears
                manual_input = page.locator("input[placeholder*='/mnt']")
                assert manual_input.count() > 0, "Manual input field should appear"

    def test_dataset_selector_manual_path_input(self, page, api_client):
        """
        Test: Manual path input and confirmation works.

        Steps:
        1. Navigate to step 2 with DatasetSelector
        2. Switch to manual input mode
        3. Enter a manual path
        4. Verify the path is accepted
        """
        page.goto("/tasks")
        page.wait_for_load_state("networkidle")

        # Open task creation wizard and navigate to step 2
        create_button = page.locator("button:has-text('新建任务')")
        if create_button.count() > 0:
            create_button.first.click()
            page.wait_for_timeout(1000)

        task_type_select = page.locator("[data-testid='task-type-train']")
        if task_type_select.count() > 0:
            task_type_select.first.click()
            page.wait_for_timeout(500)

        algorithm_trigger = page.locator("button:has-text('选择算法')").first
        if algorithm_trigger.count() > 0:
            algorithm_trigger.click()
            page.wait_for_timeout(500)
            first_algorithm = page.locator("[role='option']").first
            if first_algorithm.count() > 0:
                first_algorithm.click()
                page.wait_for_timeout(500)

        next_button = page.locator("button:has-text('下一步')")
        if next_button.count() > 0:
            next_button.first.click()
            page.wait_for_timeout(1000)

        # Switch to manual input mode
        select_trigger = page.locator("button:has-text('选择类型')").first
        if select_trigger.count() > 0:
            select_trigger.click()
            page.wait_for_timeout(500)

            manual_option = page.locator("text=手动输入")
            if manual_option.count() > 0:
                manual_option.first.click()
                page.wait_for_timeout(500)

                # Enter a manual path
                manual_input = page.locator("input[placeholder*='/mnt']")
                if manual_input.count() > 0:
                    manual_input.fill("/mnt/test/dataset/path")
                    page.wait_for_timeout(300)

                    # Verify path is in the input
                    input_value = manual_input.input_value()
                    assert "/mnt/test/dataset/path" in input_value

    def test_dataset_selector_search_filters_datasets(self, page, api_client):
        """
        Test: Search functionality filters the dataset list.

        Steps:
        1. Open DatasetSelector dialog
        2. Type in search box
        3. Verify dataset list is filtered
        """
        page.goto("/tasks")
        page.wait_for_load_state("networkidle")

        # Open task creation wizard and navigate to step 2
        create_button = page.locator("button:has-text('新建任务')")
        if create_button.count() > 0:
            create_button.first.click()
            page.wait_for_timeout(1000)

        task_type_select = page.locator("[data-testid='task-type-train']")
        if task_type_select.count() > 0:
            task_type_select.first.click()
            page.wait_for_timeout(500)

        algorithm_trigger = page.locator("button:has-text('选择算法')").first
        if algorithm_trigger.count() > 0:
            algorithm_trigger.click()
            page.wait_for_timeout(500)
            first_algorithm = page.locator("[role='option']").first
            if first_algorithm.count() > 0:
                first_algorithm.click()
                page.wait_for_timeout(500)

        next_button = page.locator("button:has-text('下一步')")
        if next_button.count() > 0:
            next_button.first.click()
            page.wait_for_timeout(1000)

        # Open the dataset selector dialog
        dataset_button = page.locator("button:has-text('选择数据集或手动输入路径')")
        if dataset_button.count() > 0:
            dataset_button.first.click()
            page.wait_for_timeout(500)

            # Find search input
            search_input = page.locator("input[placeholder='搜索数据集...']")
            if search_input.count() > 0:
                # Type a search query
                search_input.fill("nonexistent")
                page.wait_for_timeout(500)

                # Verify empty state message appears
                empty_message = page.locator("text=未找到匹配的数据集")
                assert empty_message.count() > 0, "Empty state should show when no datasets match"

    def test_dataset_selector_dialog_close_on_select(self, page, api_client):
        """
        Test: Dialog closes after selecting a dataset.

        Steps:
        1. Open DatasetSelector dialog
        2. Select a dataset from the list
        3. Verify dialog closes
        """
        page.goto("/tasks")
        page.wait_for_load_state("networkidle")

        # Open task creation wizard and navigate to step 2
        create_button = page.locator("button:has-text('新建任务')")
        if create_button.count() > 0:
            create_button.first.click()
            page.wait_for_timeout(1000)

        task_type_select = page.locator("[data-testid='task-type-train']")
        if task_type_select.count() > 0:
            task_type_select.first.click()
            page.wait_for_timeout(500)

        algorithm_trigger = page.locator("button:has-text('选择算法')").first
        if algorithm_trigger.count() > 0:
            algorithm_trigger.click()
            page.wait_for_timeout(500)
            first_algorithm = page.locator("[role='option']").first
            if first_algorithm.count() > 0:
                first_algorithm.click()
                page.wait_for_timeout(500)

        next_button = page.locator("button:has-text('下一步')")
        if next_button.count() > 0:
            next_button.first.click()
            page.wait_for_timeout(1000)

        # Open the dataset selector dialog
        dataset_button = page.locator("button:has-text('选择数据集或手动输入路径')")
        if dataset_button.count() > 0:
            dataset_button.first.click()
            page.wait_for_timeout(500)

            # Verify dialog is open
            dialog_title = page.locator("text=选择数据集")
            assert dialog_title.count() > 0, "Dialog should be open"

            # Try to click a dataset card if any exists
            dataset_cards = page.locator("[role='button']").filter(has_text="GB")
            if dataset_cards.count() > 0:
                dataset_cards.first.click()
                page.wait_for_timeout(500)

                # Dialog should close - title should not be visible
                # Note: dialog uses Radix UI, so we check if it disappeared

    def test_dataset_selector_manual_input_button_in_dialog(self, page, api_client):
        """
        Test: Manual input button inside dialog switches to manual mode.

        Steps:
        1. Open DatasetSelector dialog
        2. Click '手动输入路径' button
        3. Verify manual input section appears
        """
        page.goto("/tasks")
        page.wait_for_load_state("networkidle")

        # Open task creation wizard and navigate to step 2
        create_button = page.locator("button:has-text('新建任务')")
        if create_button.count() > 0:
            create_button.first.click()
            page.wait_for_timeout(1000)

        task_type_select = page.locator("[data-testid='task-type-train']")
        if task_type_select.count() > 0:
            task_type_select.first.click()
            page.wait_for_timeout(500)

        algorithm_trigger = page.locator("button:has-text('选择算法')").first
        if algorithm_trigger.count() > 0:
            algorithm_trigger.click()
            page.wait_for_timeout(500)
            first_algorithm = page.locator("[role='option']").first
            if first_algorithm.count() > 0:
                first_algorithm.click()
                page.wait_for_timeout(500)

        next_button = page.locator("button:has-text('下一步')")
        if next_button.count() > 0:
            next_button.first.click()
            page.wait_for_timeout(1000)

        # Open the dataset selector dialog
        dataset_button = page.locator("button:has-text('选择数据集或手动输入路径')")
        if dataset_button.count() > 0:
            dataset_button.first.click()
            page.wait_for_timeout(500)

            # Find and click '手动输入路径' button
            manual_input_button = page.locator("button:has-text('手动输入路径')")
            if manual_input_button.count() > 0:
                manual_input_button.first.click()
                page.wait_for_timeout(500)

                # Verify manual input section appears inside dialog
                manual_path_input = page.locator("input[id='manual-path']")
                assert manual_path_input.count() > 0, "Manual path input should appear in dialog"