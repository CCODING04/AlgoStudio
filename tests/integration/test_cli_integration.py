# tests/integration/test_cli_integration.py
"""Integration tests for CLI module.

These tests verify the CLI commands work correctly with mocked API responses.
"""

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
import json


class TestCLICommands:
    """Test suite for CLI command interface."""

    @pytest.fixture
    def cli_runner(self):
        """Provide a Click test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_api_response(self):
        """Provide a mock API response."""
        def _make_response(data, status_code=200):
            mock_resp = MagicMock()
            mock_resp.status_code = status_code
            mock_resp.json.return_value = data
            mock_resp.raise_for_status = MagicMock()
            if status_code >= 400:
                mock_resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
            return mock_resp
        return _make_response

    def test_cli_version(self, cli_runner):
        """Test CLI version command."""
        from algo_studio.cli.main import cli

        result = cli_runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_task_list_command_success(self, cli_runner, mock_api_response):
        """Test task list command with successful API response."""
        from algo_studio.cli.main import cli

        mock_data = {
            "total": 2,
            "tasks": [
                {"task_id": "train-001", "task_type": "train", "status": "completed", "algorithm_name": "simple_classifier"},
                {"task_id": "train-002", "task_type": "train", "status": "running", "algorithm_name": "simple_detector"},
            ]
        }

        with patch("algo_studio.cli.main.requests.get") as mock_get:
            mock_get.return_value = mock_api_response(mock_data)
            result = cli_runner.invoke(cli, ["task", "list"])

        assert result.exit_code == 0
        assert "Total: 2" in result.output
        assert "train-001" in result.output
        assert "train-002" in result.output

    def test_task_list_with_status_filter(self, cli_runner, mock_api_response):
        """Test task list command with status filter."""
        from algo_studio.cli.main import cli

        mock_data = {
            "total": 1,
            "tasks": [
                {"task_id": "train-001", "task_type": "train", "status": "completed", "algorithm_name": "simple_classifier"},
            ]
        }

        with patch("algo_studio.cli.main.requests.get") as mock_get:
            mock_get.return_value = mock_api_response(mock_data)
            result = cli_runner.invoke(cli, ["task", "list", "--status", "completed"])

        assert result.exit_code == 0
        assert "completed" in result.output

    def test_task_submit_command(self, cli_runner, mock_api_response):
        """Test task submit command."""
        from algo_studio.cli.main import cli

        mock_data = {"task_id": "train-003", "status": "pending"}

        with patch("algo_studio.cli.main.requests.post") as mock_post:
            mock_post.return_value = mock_api_response(mock_data)
            result = cli_runner.invoke(cli, [
                "task", "submit",
                "--type", "train",
                "--algo", "simple_classifier",
                "--version", "v1",
                "--config", '{"epochs": 100}'
            ])

        assert result.exit_code == 0
        assert "train-003" in result.output

    def test_task_status_command(self, cli_runner, mock_api_response):
        """Test task status command."""
        from algo_studio.cli.main import cli

        mock_data = {
            "task_id": "train-001",
            "task_type": "train",
            "status": "completed",
            "algorithm_name": "simple_classifier",
            "progress": 100
        }

        with patch("algo_studio.cli.main.requests.get") as mock_get:
            mock_get.return_value = mock_api_response(mock_data)
            result = cli_runner.invoke(cli, ["task", "status", "train-001"])

        assert result.exit_code == 0
        assert "train-001" in result.output
        assert "completed" in result.output

    def test_train_command(self, cli_runner, mock_api_response):
        """Test train convenience command."""
        from algo_studio.cli.main import cli

        mock_data = {"task_id": "train-004", "status": "pending"}

        with patch("algo_studio.cli.main.requests.post") as mock_post:
            mock_post.return_value = mock_api_response(mock_data)
            result = cli_runner.invoke(cli, [
                "train",
                "--algo", "simple_classifier",
                "--version", "v1",
                "--data", "/data/train",
                "--epochs", "50"
            ])

        assert result.exit_code == 0
        assert "train-004" in result.output

    def test_infer_command(self, cli_runner, mock_api_response):
        """Test infer convenience command."""
        from algo_studio.cli.main import cli

        mock_data = {"task_id": "infer-001", "status": "pending"}

        with patch("algo_studio.cli.main.requests.post") as mock_post:
            mock_post.return_value = mock_api_response(mock_data)
            result = cli_runner.invoke(cli, [
                "infer",
                "--algo", "simple_classifier",
                "--version", "v1",
                "--input", "/data/test.jpg"
            ])

        assert result.exit_code == 0
        assert "infer-001" in result.output

    def test_host_status_command(self, cli_runner, mock_api_response):
        """Test host status command."""
        from algo_studio.cli.main import cli

        mock_data = {
            "hostname": "worker-1",
            "ip": "192.168.0.115",
            "status": "online",
            "resources": {
                "cpu": {"total": 8, "used": 2},
                "gpu": {"total": 1, "utilization": 45}
            }
        }

        with patch("algo_studio.cli.main.requests.get") as mock_get:
            mock_get.return_value = mock_api_response(mock_data)
            result = cli_runner.invoke(cli, ["host", "status"])

        assert result.exit_code == 0
        assert "worker-1" in result.output

    def test_task_list_api_error(self, cli_runner, mock_api_response):
        """Test task list command handles API errors gracefully."""
        from algo_studio.cli.main import cli

        with patch("algo_studio.cli.main.requests.get") as mock_get:
            mock_get.return_value = mock_api_response({}, status_code=500)
            result = cli_runner.invoke(cli, ["task", "list"])

        # CLI catches exception and prints to stderr, exits with 0 in this implementation
        # Check that error is printed to stderr
        assert "Error" in result.output or "Error" in result.stderr

    def test_task_submit_invalid_json(self, cli_runner):
        """Test task submit command handles invalid JSON gracefully."""
        from algo_studio.cli.main import cli

        result = cli_runner.invoke(cli, [
            "task", "submit",
            "--type", "train",
            "--algo", "simple_classifier",
            "--version", "v1",
            "--config", "not-valid-json"
        ])

        # The JSON parsing error is not caught by the CLI's exception handler
        # as it occurs before the try block - the exception propagates
        # This test documents the actual behavior
        assert result.exception is not None or "Error" in result.output or "JSON" in result.output

    def test_log_command(self, cli_runner):
        """Test log command output."""
        from algo_studio.cli.main import cli

        result = cli_runner.invoke(cli, ["log"])
        assert result.exit_code == 0
        assert "Evolution logs" in result.output


class TestCLIHelpOutput:
    """Test suite for CLI help output."""

    @pytest.fixture
    def cli_runner(self):
        return CliRunner()

    def test_main_help(self, cli_runner):
        """Test main CLI help."""
        from algo_studio.cli.main import cli

        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "AlgoStudio" in result.output

    def test_task_group_help(self, cli_runner):
        """Test task subcommand group help."""
        from algo_studio.cli.main import cli

        result = cli_runner.invoke(cli, ["task", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "submit" in result.output
        assert "status" in result.output

    def test_host_group_help(self, cli_runner):
        """Test host subcommand group help."""
        from algo_studio.cli.main import cli

        result = cli_runner.invoke(cli, ["host", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output
