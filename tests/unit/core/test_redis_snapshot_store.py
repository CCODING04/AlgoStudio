# tests/unit/core/test_redis_snapshot_store.py
"""Unit tests for RedisSnapshotStore."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from algo_studio.core.interfaces.redis_snapshot_store import RedisSnapshotStore
from algo_studio.core.deploy.rollback import DeploymentSnapshot, RollbackHistoryEntry, RollbackStatus


def create_test_snapshot(
    deployment_id: str = "deploy-1",
    snapshot_id: str = "snap-1",
    node_ip: str = "192.168.0.115",
) -> DeploymentSnapshot:
    """Create a test DeploymentSnapshot."""
    return DeploymentSnapshot(
        snapshot_id=snapshot_id,
        deployment_id=deployment_id,
        node_ip=node_ip,
        version="v1.0",
        config={"key": "value"},
        steps_completed=["step1", "step2"],
        created_at=datetime.now(),
        ray_head_ip="192.168.0.126",
        ray_port=6379,
        artifacts=["artifact1"],
        metadata={"meta": "data"},
    )


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock = AsyncMock()
    mock._data = {}  # In-memory storage for mock

    # Track calls for verification
    mock._calls = []

    async def mock_set(key, value, *args, **kwargs):
        mock._data[key] = value
        mock._calls.append(("set", key, value))

    async def mock_get(key):
        mock._calls.append(("get", key))
        return mock._data.get(key)

    async def mock_delete(*keys):
        for key in keys:
            mock._data.pop(key, None)
        mock._calls.append(("delete", keys))
        return len(keys)

    async def mock_zadd(key, mapping):
        mock._calls.append(("zadd", key, mapping))
        return 1

    async def mock_zrevrange(key, start, end):
        mock._calls.append(("zrevrange", key, start, end))
        return []

    async def mock_lpush(key, *values):
        if key not in mock._data:
            mock._data[key] = []
        if isinstance(mock._data[key], list):
            mock._data[key] = list(mock._data[key])
            mock._data[key].insert(0, *values)
        else:
            mock._data[key] = list(values) + [mock._data[key]]
        return len(mock._data[key])

    async def mock_ltrim(key, start, end):
        if key in mock._data and isinstance(mock._data[key], list):
            mock._data[key] = mock._data[key][start:end+1] if end >= 0 else []
        return True

    async def mock_lrem(key, count, value):
        if key in mock._data and isinstance(mock._data[key], list):
            if count == 0:
                mock._data[key] = [v for v in mock._data[key] if v != value]
            else:
                removed = 0
                new_list = []
                for v in mock._data[key]:
                    if v == value and removed < count:
                        removed += 1
                    else:
                        new_list.append(v)
                mock._data[key] = new_list
        return 1

    async def mock_mget(keys):
        mock._calls.append(("mget", keys))
        return [mock._data.get(k) for k in keys]

    async def mock_pipeline():
        pipe = MagicMock()
        pipe._data = {}
        pipe._ops = []

        async def pipe_set(key, value):
            pipe._ops.append(("set", key, value))
            pipe._data[key] = value

        async def pipe_delete(key):
            pipe._ops.append(("delete", key))
            pipe._data[key] = None

        async def pipe_zrem(key, member):
            pipe._ops.append(("zrem", key, member))

        pipe.set = MagicMock(side_effect=pipe_set)
        pipe.delete = MagicMock(side_effect=pipe_delete)
        pipe.zrem = MagicMock(side_effect=pipe_zrem)

        async def pipe_execute():
            for op, key, value in pipe._ops:
                if op == "set":
                    mock._data[key] = value
                elif op == "delete":
                    mock._data.pop(key, None)
            return [1 for _ in pipe._ops]

        pipe.execute = MagicMock(side_effect=pipe_execute)
        return pipe

    mock.set = AsyncMock(side_effect=mock_set)
    mock.get = AsyncMock(side_effect=mock_get)
    mock.delete = AsyncMock(side_effect=mock_delete)
    mock.zadd = AsyncMock(side_effect=mock_zadd)
    mock.zrevrange = AsyncMock(side_effect=mock_zrevrange)
    mock.lpush = AsyncMock(side_effect=mock_lpush)
    mock.ltrim = AsyncMock(side_effect=mock_ltrim)
    mock.lrem = AsyncMock(side_effect=mock_lrem)
    mock.mget = AsyncMock(side_effect=mock_mget)

    # Create a pipeline mock that simulates redis.asyncio behavior
    # pipeline() returns a synchronous object, but execute() is async
    class PipeMock:
        def __init__(self, parent_mock):
            self._parent = parent_mock
            self._ops = []

        def set(self, key, value):
            self._ops.append(("set", key, value))
            return self  # For chaining

        def delete(self, key):
            self._ops.append(("delete", key, None))
            return self  # For chaining

        def zrem(self, key, member):
            self._ops.append(("zrem", key, member))
            return self  # For chaining

        async def execute(self):
            # Simulate the Redis pipeline execute
            results = []
            for op in self._ops:
                if op[0] == "delete":
                    self._parent._data.pop(op[1], None)
                    results.append(1)
                elif op[0] == "zrem":
                    results.append(1)
            return results

    def get_pipeline():
        return PipeMock(mock)

    mock.pipeline = MagicMock(side_effect=get_pipeline)

    return mock


@pytest.fixture
def store(mock_redis):
    """Create a RedisSnapshotStore with mock Redis."""
    store = RedisSnapshotStore(redis_host="localhost", redis_port=6380)
    store._redis = mock_redis
    return store


@pytest.mark.asyncio
async def test_save_and_get_snapshot(store, mock_redis):
    """Test saving and retrieving a snapshot."""
    snapshot = create_test_snapshot()

    # Mock zrevrange for list_snapshots
    mock_redis.zrevrange = AsyncMock(return_value=["deploy-1"])

    # Test save
    result = await store.save_snapshot(snapshot)
    assert result is True

    # Test get
    retrieved = await store.get_snapshot("deploy-1")
    assert retrieved is not None
    assert retrieved.deployment_id == "deploy-1"
    assert retrieved.snapshot_id == "snap-1"
    assert retrieved.node_ip == "192.168.0.115"


@pytest.mark.asyncio
async def test_get_nonexistent_returns_none(store, mock_redis):
    """Test that getting a nonexistent snapshot returns None."""
    # Ensure the key doesn't exist
    mock_redis._data.pop("deploy:snapshot:nonexistent", None)

    result = await store.get_snapshot("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_delete_snapshot(store, mock_redis):
    """Test deleting a snapshot."""
    snapshot = create_test_snapshot()

    # First save
    await store.save_snapshot(snapshot)

    # Verify it exists
    retrieved = await store.get_snapshot("deploy-1")
    assert retrieved is not None

    # Mock the get for delete to return snapshot data
    import json
    mock_redis.get = AsyncMock(return_value=json.dumps(snapshot.to_dict()))

    # Delete
    result = await store.delete_snapshot("deploy-1")
    assert result is True


@pytest.mark.asyncio
async def test_list_snapshots(store, mock_redis):
    """Test listing snapshots."""
    # Create and save multiple snapshots
    snapshot1 = create_test_snapshot(deployment_id="deploy-1", snapshot_id="snap-1")
    snapshot2 = create_test_snapshot(deployment_id="deploy-2", snapshot_id="snap-2")

    # Save snapshots
    import json
    mock_redis._data["deploy:snapshot:deploy-1"] = json.dumps(snapshot1.to_dict())
    mock_redis._data["deploy:snapshot:deploy-2"] = json.dumps(snapshot2.to_dict())

    # Mock zrevrange to return deployment IDs
    mock_redis.zrevrange = AsyncMock(return_value=["deploy-1", "deploy-2"])

    # List snapshots
    snapshots = await store.list_snapshots(limit=10)
    assert len(snapshots) == 2
    assert snapshots[0].deployment_id == "deploy-1"
    assert snapshots[1].deployment_id == "deploy-2"


@pytest.mark.asyncio
async def test_list_snapshots_empty(store, mock_redis):
    """Test listing snapshots when none exist."""
    mock_redis.zrevrange = AsyncMock(return_value=[])

    snapshots = await store.list_snapshots()
    assert len(snapshots) == 0


@pytest.mark.asyncio
async def test_save_rollback_history(store, mock_redis):
    """Test saving rollback history."""
    entry = RollbackHistoryEntry(
        rollback_id="rollback-1",
        deployment_id="deploy-1",
        snapshot_id="snap-1",
        status=RollbackStatus.COMPLETED,
        initiated_by="admin",
        initiated_at=datetime.now(),
    )

    await store.save_rollback_history(entry)

    # Verify it was stored
    history = await store.get_rollback_history("deploy-1")
    assert len(history) == 1
    assert history[0].rollback_id == "rollback-1"
    assert history[0].status == RollbackStatus.COMPLETED


@pytest.mark.asyncio
async def test_get_rollback_history(store, mock_redis):
    """Test getting rollback history."""
    # First save some history
    entry1 = RollbackHistoryEntry(
        rollback_id="rollback-1",
        deployment_id="deploy-1",
        snapshot_id="snap-1",
        status=RollbackStatus.COMPLETED,
        initiated_by="admin",
        initiated_at=datetime.now(),
    )
    entry2 = RollbackHistoryEntry(
        rollback_id="rollback-2",
        deployment_id="deploy-1",
        snapshot_id="snap-2",
        status=RollbackStatus.FAILED,
        initiated_by="admin",
        initiated_at=datetime.now(),
    )

    await store.save_rollback_history(entry1)
    await store.save_rollback_history(entry2)

    # Get history
    history = await store.get_rollback_history("deploy-1")
    assert len(history) == 2


@pytest.mark.asyncio
async def test_get_rollback_history_empty(store, mock_redis):
    """Test getting rollback history for deployment with no history."""
    mock_redis._data.pop("deploy:rollback_history:deploy-nonexistent", None)

    history = await store.get_rollback_history("deploy-nonexistent")
    assert len(history) == 0


@pytest.mark.asyncio
async def test_save_snapshot_failure(store, mock_redis):
    """Test save_snapshot handles Redis errors gracefully."""
    snapshot = create_test_snapshot()

    # Make Redis raise an exception
    mock_redis.set = AsyncMock(side_effect=Exception("Redis connection error"))

    result = await store.save_snapshot(snapshot)
    assert result is False


@pytest.mark.asyncio
async def test_get_snapshot_failure(store, mock_redis):
    """Test get_snapshot handles Redis errors gracefully."""
    # Make Redis raise an exception
    mock_redis.get = AsyncMock(side_effect=Exception("Redis connection error"))

    result = await store.get_snapshot("deploy-1")
    assert result is None


@pytest.mark.asyncio
async def test_delete_snapshot_failure(store, mock_redis):
    """Test delete_snapshot handles Redis errors gracefully."""
    # Make Redis raise an exception
    mock_redis.get = AsyncMock(side_effect=Exception("Redis connection error"))

    result = await store.delete_snapshot("deploy-1")
    assert result is False
