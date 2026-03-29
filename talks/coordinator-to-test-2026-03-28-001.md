# Task: Phase 3 Round 2 - SSH Rollback Mock Tests

## Context

You are the @test-engineer for Phase 3 Round 2. Your task is to add mock SSH tests for `RollbackService` to increase test coverage from 38% to 70%+.

## Source Files

**Rollback module:** `/home/admin02/Code/Dev/AlgoStudio/src/algo_studio/core/deploy/rollback.py`
- RollbackService class with 6 SSH methods:
  - `_rollback_ray()` - runs `ray stop`
  - `_rollback_code()` - runs `rm -f ~/.code_synced`
  - `_rollback_deps()` - runs `rm -f ~/.deps_installed`
  - `_rollback_venv()` - runs `rm -rf ~/.venv-ray`
  - `_rollback_sudo()` - runs `sudo rm -f /etc/sudoers.d/admin02`
  - `_rollback_connecting()` - runs `rm -f ~/.ssh/authorized_keys`

**Existing tests:** `/home/admin02/Code/Dev/AlgoStudio/tests/unit/core/test_rollback.py`
- 43 tests already passing
- Command validation tests covered
- Snapshot serialization tests covered
- But SSH methods are NOT mocked

## Implementation Plan

### 1. Import asyncssh error types for mocking

```python
import asyncssh
from unittest.mock import AsyncMock, MagicMock, patch
```

### 2. Create mock SSH connection helper

```python
def create_mock_ssh_connection(exit_status=0, stderr=""):
    """Create a mock SSH connection that executes commands successfully."""
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.exit_status = exit_status
    mock_result.stderr = stderr
    mock_conn.run = AsyncMock(return_value=mock_result)
    mock_conn.close = MagicMock()
    return mock_conn
```

### 3. Test patterns for each SSH method

#### Pattern: Successful execution
```python
@pytest.mark.asyncio
async def test_rollback_ray_success():
    store = MockSnapshotStore()
    service = RollbackService(store)

    snapshot = create_snapshot_with_password()
    await store.save_snapshot(snapshot)

    mock_conn = create_mock_ssh_connection(exit_status=0)
    with patch("asyncssh.connect", new_callable=AsyncMock, return_value=mock_conn):
        await service._rollback_ray(snapshot)

    mock_conn.run.assert_called_once()
    # Verify command "ray stop" was passed
    args, kwargs = mock_conn.run.call_args
    assert args[0] == "ray stop"
```

#### Pattern: SSH connection failure
```python
@pytest.mark.asyncio
async def test_rollback_ray_disconnect_error():
    store = MockSnapshotStore()
    service = RollbackService(store)

    snapshot = create_snapshot_with_password()
    await store.save_snapshot(snapshot)

    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        mock_connect.side_effect = asyncssh.DisconnectError(code=0, reason="Connection refused")
        # Should NOT raise, just log warning
        await service._rollback_ray(snapshot)
```

#### Pattern: Missing credentials (skip)
```python
@pytest.mark.asyncio
async def test_rollback_ray_no_credentials():
    store = MockSnapshotStore()
    service = RollbackService(store)

    snapshot = DeploymentSnapshot(
        snapshot_id="snap-001",
        deployment_id="deploy-001",
        node_ip="192.168.0.115",
        version="v1.0.0",
        config={"username": "admin02"},  # No password!
        steps_completed=["start_ray"],
        created_at=datetime.now(),
        ray_head_ip="192.168.0.126",
        ray_port=6379,
    )
    await store.save_snapshot(snapshot)

    # Should skip without calling SSH
    with patch("asyncssh.connect", new_callable=AsyncMock) as mock_connect:
        await service._rollback_ray(snapshot)
        mock_connect.assert_not_called()
```

### 4. Helper function for creating test snapshots

```python
def create_snapshot_with_password() -> DeploymentSnapshot:
    """Create a test snapshot with SSH credentials."""
    return DeploymentSnapshot(
        snapshot_id="snap-test",
        deployment_id="deploy-test",
        node_ip="192.168.0.115",
        version="v1.0.0",
        config={
            "username": "admin02",
            "password": "test_password"
        },
        steps_completed=["start_ray"],
        created_at=datetime.now(),
        ray_head_ip="192.168.0.126",
        ray_port=6379,
    )
```

### 5. Use `patch("algo_studio.core.deploy.rollback.asyncssh.connect")` for all SSH mocks

Important: Patch the import in the rollback module namespace, not the asyncssh module directly.

## Expected Test Count

| Method | Tests | Description |
|--------|-------|-------------|
| `_rollback_ray` | 4 | success, disconnect_error, channel_error, no_credentials |
| `_rollback_code` | 4 | success, disconnect_error, channel_error, no_credentials |
| `_rollback_deps` | 4 | success, disconnect_error, channel_error, no_credentials |
| `_rollback_venv` | 4 | success, disconnect_error, channel_error, no_credentials |
| `_rollback_sudo` | 4 | success, disconnect_error, channel_error, no_credentials |
| `_rollback_connecting` | 4 | success, disconnect_error, channel_error, no_credentials |
| **Total** | **24** | |

## Output Requirements

After implementing the tests:
1. Run `PYTHONPATH=src pytest tests/unit/core/test_rollback.py -v --tb=short`
2. Run `PYTHONPATH=src pytest tests/unit/core/test_rollback.py --cov=algo_studio.core.deploy.rollback --cov-report=term-missing`
3. Report:
   - Number of tests passed
   - New coverage percentage
   - Any issues found

## Notes

- All SSH methods catch exceptions internally and log warnings - they don't raise
- The `validate_rollback_command()` function is called BEFORE `conn.run()` - test both paths
- Use `@pytest.mark.asyncio` for all async test methods
- The `MockSnapshotStore` class in existing tests can be reused

## File to Modify

`/home/admin02/Code/Dev/AlgoStudio/tests/unit/core/test_rollback.py`

Add new test classes after line 504 (after `TestForbiddenPatterns`).
