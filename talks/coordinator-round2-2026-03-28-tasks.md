# Phase 3 Round 2 Task Assignments

## Context

Round 1 complete: rollback_id microsecond fix applied, 43 tests pass, coverage 38%.

## Round 2 Focus

**Goal:** Increase coverage by adding SSH method tests with proper mocking.

## Task: Add SSH Mock Tests for Rollback Methods

### Coverage Gap Analysis

The following methods are NOT covered (lines 511-811):
- `_rollback_ray` (lines 486-539)
- `_rollback_code` (lines 541-593)
- `_rollback_deps` (lines 595-647)
- `_rollback_venv` (lines 649-701)
- `_rollback_sudo` (lines 703-754)
- `_rollback_connecting` (lines 756-811)

These are not covered because they require SSH credentials.

### Solution: Mock asyncssh

Use `unittest.mock.AsyncMock` and `patch('asyncssh.connect')` to mock SSH behavior.

### Test Pattern

```python
@pytest.mark.asyncio
async def test_rollback_ray_with_ssh(self):
    """Test _rollback_ray executes ray stop via SSH."""
    store = MockSnapshotStore()
    service = RollbackService(store)

    # Create snapshot with password
    snapshot = DeploymentSnapshot(
        snapshot_id="snap-ssh",
        deployment_id="deploy-ssh",
        node_ip="192.168.0.115",
        version="v1.0.0",
        config={"username": "admin02", "password": "test123"},
        steps_completed=["start_ray"],
        created_at=datetime.now(),
        ray_head_ip="192.168.0.126",
        ray_port=6379,
    )
    await store.save_snapshot(snapshot)

    # Mock SSH
    mock_conn = AsyncMock()
    mock_result = AsyncMock()
    mock_result.exit_status = 0
    mock_conn.run = AsyncMock(return_value=mock_result)
    mock_conn.close = AsyncMock()

    with patch('asyncssh.connect', return_value=mock_conn):
        await service._rollback_ray(snapshot)

    # Verify SSH was called
    mock_conn.run.assert_called_once_with("ray stop", check=False, timeout=120)
```

### Tasks

1. Add `test_rollback_ray_with_ssh` test
2. Add `test_rollback_code_with_ssh` test
3. Add `test_rollback_deps_with_ssh` test
4. Add `test_rollback_venv_with_ssh` test
5. Add `test_rollback_sudo_with_ssh` test
6. Add `test_rollback_connecting_with_ssh` test
7. Run all tests to verify coverage increase

### Expected Coverage Increase

Each SSH method has ~50 lines. Covering all 6 should push coverage from 38% to ~60%+.

## Execution

Execute in: `/home/admin02/Code/Dev/AlgoStudio`

Run tests:
```bash
PYTHONPATH=src pytest tests/unit/core/test_rollback.py -v --cov=src/algo_studio/core/deploy/rollback --cov-report=term-missing
```

## Output

- Updated test file: `tests/unit/core/test_rollback.py`
- Coverage report
- Commit with message: "test: add SSH mock tests for rollback methods"
