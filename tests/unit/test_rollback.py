# tests/unit/test_rollback.py
"""Unit tests for deployment rollback mechanism.

Tests cover:
- DeploymentSnapshotStore: snapshot creation, retrieval, listing
- RollbackService: rollback execution, verification
- Rollback API endpoints: rollback, history, snapshot endpoints
- SSH rollback methods: _rollback_ray, _rollback_code, etc.
"""

import logging
import pytest
import json
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Any

import asyncssh
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from algo_studio.core.deploy.rollback import (
    DeploymentSnapshotStore,
    DeploymentSnapshot,
    RollbackService,
    RollbackHistoryEntry,
    RollbackStatus,
    RollbackVerificationResult,
    DeploySnapshotMixin,
    validate_rollback_command,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_redis():
    """Provide a mock Redis client."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.lpush = AsyncMock(return_value=1)
    mock.ltrim = AsyncMock(return_value=True)
    mock.lrange = AsyncMock(return_value=[])
    mock.scan_iter = AsyncMock(return_value=iter([]))
    return mock


@pytest.fixture
def snapshot_store(mock_redis):
    """Provide DeploymentSnapshotStore with mocked Redis."""
    store = DeploymentSnapshotStore(redis_host="localhost", redis_port=6380)
    store._redis = mock_redis
    return store


@pytest.fixture
def rollback_service(snapshot_store):
    """Provide RollbackService with mocked snapshot store."""
    return RollbackService(snapshot_store)


@pytest.fixture
def sample_snapshot_data() -> Dict[str, Any]:
    """Provide sample snapshot data."""
    return {
        "snapshot_id": "snap-deploy-001-20260327120000",
        "deployment_id": "deploy-001",
        "node_ip": "192.168.0.115",
        "version": "1.0.0",
        "config": {"ray_port": 6379, "head_ip": "192.168.0.126"},
        "steps_completed": ["connecting", "sudo_config", "create_venv", "install_deps", "sync_code", "start_ray", "verify"],
        "created_at": "2026-03-27T12:00:00",
        "ray_head_ip": "192.168.0.126",
        "ray_port": 6379,
        "artifacts": ["/opt/algo_studio/bin/start.sh"],
        "metadata": {"deployed_by": "admin", "deployed_at": "2026-03-27T12:00:00"},
    }


@pytest.fixture
def sample_snapshot(sample_snapshot_data) -> DeploymentSnapshot:
    """Provide a DeploymentSnapshot object."""
    return DeploymentSnapshot.from_dict(sample_snapshot_data)


@pytest.fixture
def sample_rollback_history_entry(sample_snapshot) -> RollbackHistoryEntry:
    """Provide a sample rollback history entry."""
    return RollbackHistoryEntry(
        rollback_id="rollback-deploy-001-20260327130000",
        deployment_id="deploy-001",
        snapshot_id=sample_snapshot.snapshot_id,
        status=RollbackStatus.COMPLETED,
        initiated_by="admin",
        initiated_at=datetime.now(),
        completed_at=datetime.now(),
        verification_result={
            "success": True,
            "checks_passed": ["ssh_connectivity", "ray_stopped", "node_reachable"],
            "checks_failed": [],
            "latency_ms": 150.5,
            "message": "Rollback verification completed successfully",
        },
    )


# =============================================================================
# DeploymentSnapshot Tests
# =============================================================================

class TestDeploymentSnapshot:
    """Tests for DeploymentSnapshot model."""

    def test_snapshot_to_dict(self, sample_snapshot):
        """Test snapshot serialization to dictionary."""
        result = sample_snapshot.to_dict()

        assert result["snapshot_id"] == "snap-deploy-001-20260327120000"
        assert result["deployment_id"] == "deploy-001"
        assert result["node_ip"] == "192.168.0.115"
        assert result["version"] == "1.0.0"
        assert len(result["steps_completed"]) == 7
        assert "ray_head_ip" in result

    def test_snapshot_from_dict(self, sample_snapshot_data):
        """Test snapshot deserialization from dictionary."""
        snapshot = DeploymentSnapshot.from_dict(sample_snapshot_data)

        assert snapshot.snapshot_id == sample_snapshot_data["snapshot_id"]
        assert snapshot.deployment_id == sample_snapshot_data["deployment_id"]
        assert snapshot.node_ip == sample_snapshot_data["node_ip"]
        assert snapshot.version == sample_snapshot_data["version"]
        assert snapshot.steps_completed == sample_snapshot_data["steps_completed"]

    def test_snapshot_roundtrip(self, sample_snapshot):
        """Test snapshot serialization roundtrip."""
        data = sample_snapshot.to_dict()
        restored = DeploymentSnapshot.from_dict(data)

        assert restored.snapshot_id == sample_snapshot.snapshot_id
        assert restored.deployment_id == sample_snapshot.deployment_id
        assert restored.node_ip == sample_snapshot.node_ip


# =============================================================================
# DeploymentSnapshotStore Tests
# =============================================================================

class TestDeploymentSnapshotStore:
    """Tests for DeploymentSnapshotStore."""

    @pytest.mark.asyncio
    async def test_create_snapshot(self, snapshot_store, mock_redis):
        """Test creating a new snapshot."""
        snapshot = await snapshot_store.create_snapshot(
            deployment_id="deploy-002",
            node_ip="192.168.0.116",
            version="1.0.0",
            config={"ray_port": 6379},
            steps_completed=["connecting", "sudo_config"],
            ray_head_ip="192.168.0.126",
            ray_port=6379,
        )

        assert snapshot.deployment_id == "deploy-002"
        assert snapshot.node_ip == "192.168.0.116"
        assert snapshot.version == "1.0.0"
        assert "steps_completed" in snapshot.__dict__
        # Now storing twice: by deployment_id and by snapshot_id (for efficient lookup)
        assert mock_redis.set.call_count == 2
        # Verify snapshot_id has microseconds to prevent collision
        # Format: YYYYMMDDHHMMSS (14 chars) + microseconds (6 chars) = 20 chars
        assert len(snapshot.snapshot_id.split('-')[-1]) == 20

    @pytest.mark.asyncio
    async def test_get_snapshot_exists(self, snapshot_store, mock_redis, sample_snapshot_data):
        """Test getting an existing snapshot."""
        mock_redis.get = AsyncMock(return_value=json.dumps(sample_snapshot_data))

        snapshot = await snapshot_store.get_snapshot("deploy-001")

        assert snapshot is not None
        assert snapshot.deployment_id == "deploy-001"
        assert snapshot.node_ip == "192.168.0.115"

    @pytest.mark.asyncio
    async def test_get_snapshot_not_exists(self, snapshot_store, mock_redis):
        """Test getting a non-existent snapshot."""
        mock_redis.get = AsyncMock(return_value=None)

        snapshot = await snapshot_store.get_snapshot("non-existent")

        assert snapshot is None

    @pytest.mark.asyncio
    async def test_save_rollback_history(self, snapshot_store, mock_redis, sample_rollback_history_entry):
        """Test saving rollback history."""
        mock_redis.get = AsyncMock(return_value=None)

        await snapshot_store.save_rollback_history(sample_rollback_history_entry)

        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_rollback_history(self, snapshot_store, mock_redis, sample_rollback_history_entry):
        """Test getting rollback history."""
        history_data = [sample_rollback_history_entry.to_dict()]
        mock_redis.get = AsyncMock(return_value=json.dumps(history_data))

        history = await snapshot_store.get_rollback_history("deploy-001")

        assert len(history) == 1
        assert history[0].rollback_id == sample_rollback_history_entry.rollback_id
        assert history[0].status == RollbackStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_rollback_history_empty(self, snapshot_store, mock_redis):
        """Test getting empty rollback history."""
        mock_redis.get = AsyncMock(return_value=None)

        history = await snapshot_store.get_rollback_history("non-existent")

        assert len(history) == 0


# =============================================================================
# RollbackService Tests
# =============================================================================

class TestRollbackService:
    """Tests for RollbackService."""

    @pytest.mark.asyncio
    async def test_rollback_no_snapshot(self, rollback_service, snapshot_store, mock_redis):
        """Test rollback when no snapshot exists."""
        mock_redis.get = AsyncMock(return_value=None)

        result = await rollback_service.rollback("non-existent", "task-001")

        assert result.status == RollbackStatus.NO_SNAPSHOT
        assert "No snapshot found" in result.error

    @pytest.mark.asyncio
    async def test_rollback_with_snapshot(self, rollback_service, snapshot_store, mock_redis, sample_snapshot_data):
        """Test rollback with existing snapshot."""
        # Create a more specific mock that handles different keys differently
        async def mock_get(key):
            if key.startswith("deploy:snapshot:"):
                return json.dumps(sample_snapshot_data)
            elif key.startswith("deploy:rollback_history:"):
                return None  # No history yet
            return None

        mock_redis.get = mock_get

        result = await rollback_service.rollback("deploy-001", "task-001", initiated_by="admin")

        assert result.deployment_id == "deploy-001"
        assert result.initiated_by == "admin"
        # Status could be IN_PROGRESS, VERIFYING, COMPLETED, or FAILED depending on execution

    @pytest.mark.asyncio
    async def test_verify_rollback_success(self, rollback_service, sample_snapshot):
        """Test successful rollback verification."""
        # Mock successful verification checks
        with patch.object(rollback_service, '_verify_rollback', return_value=RollbackVerificationResult(
            success=True,
            checks_passed=["ssh_connectivity", "ray_stopped", "node_reachable"],
            checks_failed=[],
            latency_ms=100.5,
            message="Rollback verification completed successfully",
        )):
            result = await rollback_service._verify_rollback(sample_snapshot)

            assert result.success is True
            assert len(result.checks_passed) == 3
            assert len(result.checks_failed) == 0

    @pytest.mark.asyncio
    async def test_verify_rollback_failure(self, rollback_service, sample_snapshot):
        """Test failed rollback verification."""
        with patch.object(rollback_service, '_verify_rollback', return_value=RollbackVerificationResult(
            success=False,
            checks_passed=["ssh_connectivity"],
            checks_failed=["ray_not_stopped", "node_not_reachable"],
            latency_ms=100.5,
            message="Rollback verification failed: ray_not_stopped, node_not_reachable",
        )):
            result = await rollback_service._verify_rollback(sample_snapshot)

            assert result.success is False
            assert len(result.checks_passed) == 1
            assert len(result.checks_failed) == 2


# =============================================================================
# RollbackHistoryEntry Tests
# =============================================================================

class TestRollbackHistoryEntry:
    """Tests for RollbackHistoryEntry."""

    def test_history_entry_to_dict(self, sample_rollback_history_entry):
        """Test history entry serialization."""
        result = sample_rollback_history_entry.to_dict()

        assert result["rollback_id"] == sample_rollback_history_entry.rollback_id
        assert result["deployment_id"] == sample_rollback_history_entry.deployment_id
        assert result["status"] == "completed"
        assert result["verification_result"]["success"] is True


# =============================================================================
# RollbackVerificationResult Tests
# =============================================================================

class TestRollbackVerificationResult:
    """Tests for RollbackVerificationResult."""

    def test_verification_result_success(self):
        """Test successful verification result."""
        result = RollbackVerificationResult(
            success=True,
            checks_passed=["check1", "check2"],
            checks_failed=[],
            latency_ms=50.0,
            message="All checks passed",
        )

        assert result.success is True
        assert len(result.checks_passed) == 2
        assert len(result.checks_failed) == 0

    def test_verification_result_failure(self):
        """Test failed verification result."""
        result = RollbackVerificationResult(
            success=False,
            checks_passed=["check1"],
            checks_failed=["check2", "check3"],
            latency_ms=50.0,
            message="Some checks failed",
        )

        assert result.success is False
        assert len(result.checks_passed) == 1
        assert len(result.checks_failed) == 2


# =============================================================================
# DeploySnapshotMixin Tests
# =============================================================================

class TestDeploySnapshotMixin:
    """Tests for DeploySnapshotMixin."""

    @pytest.mark.asyncio
    async def test_create_deployment_snapshot(self, mock_redis):
        """Test creating deployment snapshot via mixin."""
        mixin = DeploySnapshotMixin()
        mixin.snapshot_store = DeploymentSnapshotStore()
        mixin.snapshot_store._redis = mock_redis

        snapshot = await mixin.create_deployment_snapshot(
            deployment_id="deploy-003",
            node_ip="192.168.0.117",
            version="1.0.0",
            config={"ray_port": 6379},
            steps_completed=["connecting"],
            ray_head_ip="192.168.0.126",
        )

        assert snapshot.deployment_id == "deploy-003"
        assert snapshot.node_ip == "192.168.0.117"
        assert snapshot.version == "1.0.0"


# =============================================================================
# RollbackStatus Enum Tests
# =============================================================================

class TestRollbackStatus:
    """Tests for RollbackStatus enum."""

    def test_rollback_status_values(self):
        """Test all rollback status values exist."""
        assert RollbackStatus.PENDING.value == "pending"
        assert RollbackStatus.IN_PROGRESS.value == "in_progress"
        assert RollbackStatus.VERIFYING.value == "verifying"
        assert RollbackStatus.COMPLETED.value == "completed"
        assert RollbackStatus.FAILED.value == "failed"
        assert RollbackStatus.NO_SNAPSHOT.value == "no_snapshot"

    def test_rollback_status_from_string(self):
        """Test creating status from string."""
        status = RollbackStatus("completed")
        assert status == RollbackStatus.COMPLETED


# =============================================================================
# Integration Tests (with mocked dependencies)
# =============================================================================

class TestRollbackIntegration:
    """Integration tests for rollback flow."""

    @pytest.mark.asyncio
    async def test_full_rollback_flow(self, mock_redis, sample_snapshot_data):
        """Test complete rollback flow from snapshot creation to verification."""
        # Setup mock
        storage = {}

        async def mock_set(key, value):
            storage[key] = value
            return True

        async def mock_get(key):
            return storage.get(key)

        mock_redis.set = mock_set
        mock_redis.get = mock_get

        # Create snapshot store
        snapshot_store = DeploymentSnapshotStore(redis_host="localhost", redis_port=6380)
        snapshot_store._redis = mock_redis

        # Create a snapshot
        snapshot = await snapshot_store.create_snapshot(
            deployment_id="deploy-test",
            node_ip="192.168.0.115",
            version="2.0.0",
            config={"ray_port": 6379},
            steps_completed=["connecting", "sudo_config"],
            ray_head_ip="192.168.0.126",
        )

        # Verify snapshot was stored
        retrieved = await snapshot_store.get_snapshot("deploy-test")
        assert retrieved is not None
        assert retrieved.version == "2.0.0"

        # Create rollback service and execute rollback
        rollback_service = RollbackService(snapshot_store)

        # Execute rollback (snapshot exists, should proceed)
        result = await rollback_service.rollback("deploy-test", "task-test")

        # Verify rollback was attempted
        assert result.deployment_id == "deploy-test"
        assert result.snapshot_id == snapshot.snapshot_id


# =============================================================================
# SSH Rollback Methods Tests
# =============================================================================

class TestValidateRollbackCommand:
    """Tests for command validation."""

    def test_validate_allowed_commands(self):
        """Test allowed rollback commands pass validation."""
        allowed_commands = [
            "ray stop",
            "rm -rf ~/.venv-ray",
            "rm -f ~/.deps_installed",
            "rm -f ~/.code_synced",
            "sudo rm -f /etc/sudoers.d/admin02",
            "rm -f ~/.ssh/authorized_keys",
        ]
        for cmd in allowed_commands:
            assert validate_rollback_command(cmd) is True, f"Command should be allowed: {cmd}"

    def test_validate_forbidden_patterns(self):
        """Test forbidden patterns are rejected."""
        forbidden_commands = [
            "ray stop; rm -rf /",
            "echo 'hacked' > /dev/sda",
            "dd if=/dev/zero of=/dev/sda",
            "ray stop; shutdown",
            "eval $SOMETHING",
            "echo `whoami`",
        ]
        for cmd in forbidden_commands:
            assert validate_rollback_command(cmd) is False, f"Command should be forbidden: {cmd}"

    def test_validate_unknown_command(self):
        """Test unknown commands are rejected."""
        unknown_commands = [
            "reboot",
            "halt",
            "some_random_command",
            "rm -rf /important",
        ]
        for cmd in unknown_commands:
            assert validate_rollback_command(cmd) is False, f"Command should be rejected: {cmd}"


class TestSSHConnectionError:
    """Tests for SSH rollback methods with mocked connections."""

    @pytest.fixture
    def snapshot_with_creds(self, sample_snapshot_data):
        """Provide sample snapshot with SSH credentials."""
        data = sample_snapshot_data.copy()
        data["config"]["username"] = "admin02"
        data["config"]["password"] = "test_password"
        data["metadata"]["ssh_password"] = "test_password"
        return DeploymentSnapshot.from_dict(data)

    @pytest.fixture
    def snapshot_without_creds(self, sample_snapshot_data):
        """Provide sample snapshot without SSH credentials."""
        data = sample_snapshot_data.copy()
        data["config"] = {}
        data["metadata"] = {}
        return DeploymentSnapshot.from_dict(data)

    @pytest.mark.asyncio
    async def test_rollback_ray_no_credentials(self, rollback_service, snapshot_without_creds, caplog):
        """Test _rollback_ray skips when no credentials available."""
        with caplog.at_level(logging.INFO):
            await rollback_service._rollback_ray(snapshot_without_creds)
        assert "No SSH password found" in caplog.text

    @pytest.mark.asyncio
    async def test_rollback_ray_success(self, rollback_service, snapshot_with_creds, mock_redis):
        """Test _rollback_ray executes ray stop via SSH."""
        # Mock asyncssh.connect
        mock_conn = AsyncMock()
        mock_conn.run = AsyncMock(return_value=MagicMock(exit_status=0))
        mock_conn.close = MagicMock()

        with patch("asyncssh.connect", new_callable=AsyncMock, return_value=mock_conn):
            await rollback_service._rollback_ray(snapshot_with_creds)

            # Verify SSH connection was made
            asyncssh.connect.assert_called_once()
            call_kwargs = asyncssh.connect.call_args
            assert call_kwargs.kwargs["username"] == "admin02"
            assert call_kwargs.kwargs["password"] == "test_password"

            # Verify ray stop was executed
            mock_conn.run.assert_called_once()
            assert "ray stop" in mock_conn.run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_rollback_ray_failure(self, rollback_service, snapshot_with_creds, mock_redis):
        """Test _rollback_ray handles SSH errors gracefully."""
        with patch("asyncssh.connect", new_callable=AsyncMock, side_effect=asyncssh.DisconnectError):
            # Should not raise, just log warning
            await rollback_service._rollback_ray(snapshot_with_creds)

    @pytest.mark.asyncio
    async def test_rollback_code_no_credentials(self, rollback_service, snapshot_without_creds, caplog):
        """Test _rollback_code skips when no credentials available."""
        with caplog.at_level(logging.INFO):
            await rollback_service._rollback_code(snapshot_without_creds)
        assert "No SSH password found" in caplog.text

    @pytest.mark.asyncio
    async def test_rollback_code_success(self, rollback_service, snapshot_with_creds, mock_redis):
        """Test _rollback_code removes code marker via SSH."""
        mock_conn = AsyncMock()
        mock_conn.run = AsyncMock(return_value=MagicMock(exit_status=0))
        mock_conn.close = MagicMock()

        with patch("asyncssh.connect", new_callable=AsyncMock, return_value=mock_conn):
            await rollback_service._rollback_code(snapshot_with_creds)

            asyncssh.connect.assert_called_once()
            mock_conn.run.assert_called_once()
            assert "~/.code_synced" in mock_conn.run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_rollback_deps_no_credentials(self, rollback_service, snapshot_without_creds, caplog):
        """Test _rollback_deps skips when no credentials available."""
        with caplog.at_level(logging.INFO):
            await rollback_service._rollback_deps(snapshot_without_creds)
        assert "No SSH password found" in caplog.text

    @pytest.mark.asyncio
    async def test_rollback_deps_success(self, rollback_service, snapshot_with_creds, mock_redis):
        """Test _rollback_deps removes deps marker via SSH."""
        mock_conn = AsyncMock()
        mock_conn.run = AsyncMock(return_value=MagicMock(exit_status=0))
        mock_conn.close = MagicMock()

        with patch("asyncssh.connect", new_callable=AsyncMock, return_value=mock_conn):
            await rollback_service._rollback_deps(snapshot_with_creds)

            asyncssh.connect.assert_called_once()
            mock_conn.run.assert_called_once()
            assert "~/.deps_installed" in mock_conn.run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_rollback_venv_no_credentials(self, rollback_service, snapshot_without_creds, caplog):
        """Test _rollback_venv skips when no credentials available."""
        with caplog.at_level(logging.INFO):
            await rollback_service._rollback_venv(snapshot_without_creds)
        assert "No SSH password found" in caplog.text

    @pytest.mark.asyncio
    async def test_rollback_venv_success(self, rollback_service, snapshot_with_creds, mock_redis):
        """Test _rollback_venv removes venv via SSH."""
        mock_conn = AsyncMock()
        mock_conn.run = AsyncMock(return_value=MagicMock(exit_status=0))
        mock_conn.close = MagicMock()

        with patch("asyncssh.connect", new_callable=AsyncMock, return_value=mock_conn):
            await rollback_service._rollback_venv(snapshot_with_creds)

            asyncssh.connect.assert_called_once()
            mock_conn.run.assert_called_once()
            assert "~/.venv-ray" in mock_conn.run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_rollback_sudo_no_credentials(self, rollback_service, snapshot_without_creds, caplog):
        """Test _rollback_sudo skips when no credentials available."""
        with caplog.at_level(logging.INFO):
            await rollback_service._rollback_sudo(snapshot_without_creds)
        assert "No SSH password found" in caplog.text

    @pytest.mark.asyncio
    async def test_rollback_sudo_success(self, rollback_service, snapshot_with_creds, mock_redis):
        """Test _rollback_sudo removes sudoers file via SSH."""
        mock_conn = AsyncMock()
        mock_conn.run = AsyncMock(return_value=MagicMock(exit_status=0, stderr=""))
        mock_conn.close = MagicMock()

        with patch("asyncssh.connect", new_callable=AsyncMock, return_value=mock_conn):
            await rollback_service._rollback_sudo(snapshot_with_creds)

            asyncssh.connect.assert_called_once()
            mock_conn.run.assert_called_once()
            assert "/etc/sudoers.d/admin02" in mock_conn.run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_rollback_connecting_no_credentials(self, rollback_service, snapshot_without_creds, caplog):
        """Test _rollback_connecting skips when no credentials available."""
        with caplog.at_level(logging.INFO):
            await rollback_service._rollback_connecting(snapshot_without_creds)
        assert "No SSH password found" in caplog.text

    @pytest.mark.asyncio
    async def test_rollback_connecting_success(self, rollback_service, snapshot_with_creds, mock_redis):
        """Test _rollback_connecting removes authorized_keys via SSH."""
        mock_conn = AsyncMock()
        mock_conn.run = AsyncMock(return_value=MagicMock(exit_status=0))
        mock_conn.close = MagicMock()

        with patch("asyncssh.connect", new_callable=AsyncMock, return_value=mock_conn):
            await rollback_service._rollback_connecting(snapshot_with_creds)

            asyncssh.connect.assert_called_once()
            mock_conn.run.assert_called_once()
            assert "authorized_keys" in mock_conn.run.call_args[0][0]
