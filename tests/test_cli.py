# tests/test_cli.py
import pytest
from click.testing import CliRunner
from algo_studio.cli.main import cli

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "AlgoStudio CLI" in result.output

def test_task_command():
    runner = CliRunner()
    result = runner.invoke(cli, ["task", "--help"])
    assert result.exit_code == 0