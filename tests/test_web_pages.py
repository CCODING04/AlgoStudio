import pytest
from unittest.mock import MagicMock, patch


class TestDashboardPage:
    def test_make_page_returns_column(self):
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
            mock_gr.Checkbox.return_value = MagicMock()

            # Import and run make_page
            from algo_studio.web.pages.dashboard import make_page

            # Mock the client functions
            with patch('algo_studio.web.pages.dashboard.get_tasks') as mock_get_tasks, \
                 patch('algo_studio.web.pages.dashboard.get_hosts_status') as mock_get_hosts:
                mock_get_tasks.return_value = {"tasks": [], "total": 0}
                mock_get_hosts.return_value = {"cluster_nodes": [], "local_host": {}}

                page = make_page()

            assert page is not None
            # Verify the mock was called (meaning our code ran)
            assert mock_gr.Column.called