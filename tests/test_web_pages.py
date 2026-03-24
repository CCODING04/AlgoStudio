import pytest
from unittest.mock import MagicMock, patch


class TestDashboardPage:
    def test_make_page_returns_components(self):
        # Mock gr module to avoid Blocks context requirement
        with patch('algo_studio.web.pages.dashboard.gr') as mock_gr:
            # Setup mock chain for context managers
            mock_column = MagicMock()
            mock_column.__enter__ = MagicMock(return_value=None)
            mock_column.__exit__ = MagicMock(return_value=None)
            mock_gr.Column.return_value = mock_column

            mock_row = MagicMock()
            mock_row.__enter__ = MagicMock(return_value=None)
            mock_row.__exit__ = MagicMock(return_value=None)
            mock_gr.Row.return_value = mock_row

            # Mock gr components
            mock_gr.Markdown.return_value = MagicMock()
            mock_gr.Number.return_value = MagicMock()
            mock_gr.Button.return_value = MagicMock()

            # Import and run make_page
            from algo_studio.web.pages.dashboard import make_page

            # Mock the client functions
            with patch('algo_studio.web.pages.dashboard.get_tasks') as mock_get_tasks:
                mock_get_tasks.return_value = {
                    "tasks": [
                        {"id": "1", "status": "running"},
                        {"id": "2", "status": "pending"},
                        {"id": "3", "status": "failed"},
                        {"id": "4", "status": "running"},
                    ],
                    "total": 4
                }

                page = make_page()

            # Verify page returns expected components
            assert page is not None
            assert len(page) == 5  # refresh_btn, total_box, running_box, pending_box, failed_box

            # Verify the mock was called (meaning our code ran)
            assert mock_gr.Column.called
            assert mock_gr.Row.called
            assert mock_gr.Markdown.called
            assert mock_gr.Number.call_count == 4  # 4 stat boxes
            assert mock_gr.Button.called

    def test_load_stats_error_handling(self):
        # Test that load_stats handles errors gracefully
        with patch('algo_studio.web.pages.dashboard.gr') as mock_gr:
            mock_column = MagicMock()
            mock_column.__enter__ = MagicMock(return_value=None)
            mock_column.__exit__ = MagicMock(return_value=None)
            mock_gr.Column.return_value = mock_column

            mock_row = MagicMock()
            mock_row.__enter__ = MagicMock(return_value=None)
            mock_row.__exit__ = MagicMock(return_value=None)
            mock_gr.Row.return_value = mock_row

            mock_gr.Markdown.return_value = MagicMock()
            mock_gr.Number.return_value = MagicMock()
            mock_gr.Button.return_value = MagicMock()

            from algo_studio.web.pages.dashboard import make_page

            # Mock get_tasks to raise an exception
            with patch('algo_studio.web.pages.dashboard.get_tasks') as mock_get_tasks:
                mock_get_tasks.side_effect = RuntimeError("API connection failed")

                page = make_page()

                # Verify that page still renders even when API fails
                assert page is not None
                assert mock_gr.Column.called


class TestTasksPage:
    def test_make_page_returns_components(self):
        # Mock gr module to avoid Blocks context requirement
        with patch('algo_studio.web.pages.tasks.gr') as mock_gr:
            # Setup mock chain for context managers
            mock_column = MagicMock()
            mock_column.__enter__ = MagicMock(return_value=None)
            mock_column.__exit__ = MagicMock(return_value=None)
            mock_gr.Column.return_value = mock_column

            mock_row = MagicMock()
            mock_row.__enter__ = MagicMock(return_value=None)
            mock_row.__exit__ = MagicMock(return_value=None)
            mock_gr.Row.return_value = mock_row

            # Mock gr components
            mock_gr.Markdown.return_value = MagicMock()
            mock_gr.Dropdown.return_value = MagicMock()
            mock_gr.Button.return_value = MagicMock()
            mock_gr.Dataframe.return_value = MagicMock()

            # Import and run make_page
            from algo_studio.web.pages.tasks import make_page

            page = make_page()
            assert page is not None
            # Should return 3 components
            assert len(page) == 3
