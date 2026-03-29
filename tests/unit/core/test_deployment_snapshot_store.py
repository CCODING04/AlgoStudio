# tests/unit/core/test_deployment_snapshot_store.py
"""Unit tests for DeploymentSnapshotStore."""

import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from algo_studio.core.deploy.rollback import (
    DeploymentSnapshot,
    DeploymentSnapshotStore,
    RollbackHistoryEntry,
    RollbackStatus,
)


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
        config={"username": "admin02"},
        steps_completed=["start_ray", "sync_code"],
        created_at=datetime.now(),
        ray_head_ip="192.168.0.126",
        ray_port=6379,
        artifacts=["model.pt"],
        metadata={"key": "value"},
    )


class MockRedis:
    """Mock Redis client with in-memory storage."""

    def __init__(self):
        self._data = {}  # Regular string storage
        self._zset_data = {}  # Sorted set storage
        self._calls = []

    async def set(self, key, value, *args, **kwargs):
        self._data[key] = value
        self._calls.append(("set", key, value))
        return True

    async def get(self, key):
        self._calls.append(("get", key))
        return self._data.get(key)

    async def delete(self, *keys):
        deleted = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                deleted += 1
        self._calls.append(("delete", keys))
        return deleted

    async def zadd(self, key, mapping):
        if key not in self._zset_data:
            self._zset_data[key] = {}
        self._zset_data[key].update(mapping)
        self._calls.append(("zadd", key, mapping))
        return len(mapping)

    async def zrevrange(self, key, start, end):
        self._calls.append(("zrevrange", key, start, end))
        if key not in self._zset_data:
            return []
        sorted_items = sorted(self._zset_data[key].items(), key=lambda x: x[1], reverse=True)
        result = [item[0] for item in sorted_items[start:end+1]]
        return result

    async def lpush(self, key, *values):
        if key not in self._data:
            self._data[key] = []
        if not isinstance(self._data[key], list):
            self._data[key] = []
        self._data[key] = list(values) + self._data[key]
        return len(self._data[key])

    async def ltrim(self, key, start, end):
        if key in self._data and isinstance(self._data[key], list):
            mock_list = list(self._data[key])
            self._data[key] = mock_list[start:end+1] if end >= 0 else []
        return True

    async def lrem(self, key, count, value):
        if key in self._data and isinstance(self._data[key], list):
            if count == 0:
                self._data[key] = [v for v in self._data[key] if v != value]
            else:
                removed = 0
                new_list = []
                for v in self._data[key]:
                    if v == value and removed < count:
                        removed += 1
                    else:
                        new_list.append(v)
                self._data[key] = new_list
        return 1

    async def mget(self, keys):
        self._calls.append(("mget", keys))
        return [self._data.get(k) for k in keys]

    async def lrange(self, key, start, end):
        self._calls.append(("lrange", key, start, end))
        if key not in self._data or not isinstance(self._data[key], list):
            return []
        return self._data[key][start:end+1] if end >= 0 else self._data[key][start:]

    def pipeline(self):
        return PipeMock(self)


class PipeMock:
    """Mock Redis pipeline."""

    def __init__(self, parent):
        self._parent = parent
        self._ops = []

    def set(self, key, value):
        self._ops.append(("set", key, value))
        return self

    def delete(self, key):
        self._ops.append(("delete", key))
        return self

    def zrem(self, key, member):
        self._ops.append(("zrem", key, member))
        return self

    async def execute(self):
        results = []
        for op in self._ops:
            if op[0] == "delete":
                key = op[1]
                deleted = 1 if key in self._parent._data else 0
                if key in self._parent._data:
                    del self._parent._data[key]
                results.append(deleted)
            elif op[0] == "zrem":
                key, member = op[1], op[2]
                if key in self._parent._zset_data and member in self._parent._zset_data[key]:
                    del self._parent._zset_data[key][member]
                results.append(1)
        return results


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    return MockRedis()


@pytest.fixture
def store(mock_redis):
    """Create a DeploymentSnapshotStore with mock Redis."""
    store = DeploymentSnapshotStore(redis_host="localhost", redis_port=6380)
    store._redis = mock_redis
    return store


# ==============================================================================
# Interface Implementation Tests
# ==============================================================================

class TestDeploymentSnapshotStoreInterface:
    """Tests that DeploymentSnapshotStore properly implements SnapshotStoreInterface."""

    def test_isinstance_of_interface(self):
        """Test that DeploymentSnapshotStore is recognized as SnapshotStoreInterface."""
        from algo_studio.core.interfaces.snapshot_store import SnapshotStoreInterface
        store = DeploymentSnapshotStore()
        assert isinstance(store, SnapshotStoreInterface)

    def test_has_required_methods(self):
        """Test that DeploymentSnapshotStore has all required interface methods."""
        store = DeploymentSnapshotStore()
        required_methods = [
            'save_snapshot',
            'get_snapshot',
            'list_snapshots',
            'delete_snapshot',
            'save_rollback_history',
            'get_rollback_history',
        ]
        for method in required_methods:
            assert hasattr(store, method), f"Missing method: {method}"
            assert callable(getattr(store, method)), f"{method} is not callable"


# ==============================================================================
# Snapshot CRUD Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_save_and_get_snapshot(store, mock_redis):
    """Test saving and retrieving a snapshot."""
    snapshot = create_test_snapshot()

    # Test save
    result = await store.save_snapshot(snapshot)
    assert result is True

    # Test get
    retrieved = await store.get_snapshot("deploy-1")
    assert retrieved is not None
    assert retrieved.deployment_id == "deploy-1"
    assert retrieved.snapshot_id == "snap-1"
    assert retrieved.node_ip == "192.168.0.115"
    assert retrieved.version == "v1.0"


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

    # Delete
    result = await store.delete_snapshot("deploy-1")
    assert result is True

    # Verify it's gone
    mock_redis._data.pop("deploy:snapshot:deploy-1", None)
    retrieved = await store.get_snapshot("deploy-1")
    assert retrieved is None


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_false(store, mock_redis):
    """Test that deleting a nonexistent snapshot returns False."""
    # Ensure nothing exists
    mock_redis._data.pop("deploy:snapshot:nonexistent", None)
    mock_redis._zset_data.get("deploy:snapshot:index", {}).pop("nonexistent", None)

    result = await store.delete_snapshot("nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_list_snapshots(store, mock_redis):
    """Test listing snapshots."""
    import time
    # Create and save multiple snapshots
    snapshot1 = create_test_snapshot(deployment_id="deploy-1", snapshot_id="snap-1")
    snapshot2 = create_test_snapshot(deployment_id="deploy-2", snapshot_id="snap-2")

    # Save snapshots via store
    await store.save_snapshot(snapshot1)
    await store.save_snapshot(snapshot2)

    # List snapshots
    snapshots = await store.list_snapshots(limit=10)
    assert len(snapshots) == 2


@pytest.mark.asyncio
async def test_list_snapshots_empty(store, mock_redis):
    """Test listing snapshots when none exist."""
    mock_redis._zset_data.pop("deploy:snapshot:index", None)

    snapshots = await store.list_snapshots()
    assert len(snapshots) == 0


@pytest.mark.asyncio
async def test_list_snapshots_with_limit(store, mock_redis):
    """Test listing snapshots respects limit."""
    import time
    # Create 5 snapshots
    for i in range(5):
        snapshot = create_test_snapshot(deployment_id=f"deploy-{i}", snapshot_id=f"snap-{i}")
        await store.save_snapshot(snapshot)

    # List with limit
    snapshots = await store.list_snapshots(limit=3)
    assert len(snapshots) == 3


# ==============================================================================
# Rollback History Tests
# ==============================================================================

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
async def test_rollback_history_limits_to_50(store, mock_redis):
    """Test that rollback history keeps only the last 50 entries."""
    # Save 55 entries
    for i in range(55):
        entry = RollbackHistoryEntry(
            rollback_id=f"rollback-{i}",
            deployment_id="deploy-1",
            snapshot_id=f"snap-{i}",
            status=RollbackStatus.COMPLETED,
            initiated_by="admin",
            initiated_at=datetime.now(),
        )
        await store.save_rollback_history(entry)

    # Should only have 50 (first 5 dropped: 0-4)
    history = await store.get_rollback_history("deploy-1")
    assert len(history) == 50
    # Entries are stored in insertion order, oldest first, newest last
    # After trimming to 50, we have entries 5-54
    assert history[0].rollback_id == "rollback-5"
    assert history[-1].rollback_id == "rollback-54"


# ==============================================================================
# Create Snapshot Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_create_snapshot(store, mock_redis):
    """Test creating a snapshot via create_snapshot method."""
    snapshot = await store.create_snapshot(
        deployment_id="deploy-new",
        node_ip="192.168.0.200",
        version="v2.0",
        config={"username": "admin10"},
        steps_completed=["step1", "step2"],
        ray_head_ip="192.168.0.126",
        ray_port=6379,
    )

    assert snapshot.deployment_id == "deploy-new"
    assert snapshot.node_ip == "192.168.0.200"
    assert snapshot.version == "v2.0"
    assert snapshot.snapshot_id.startswith("snap-deploy-new-")
    assert len(snapshot.steps_completed) == 2


# ==============================================================================
# Error Handling Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_save_snapshot_failure(store):
    """Test save_snapshot handles Redis errors gracefully."""
    # Create a store with a mock that raises on set
    error_store = DeploymentSnapshotStore(redis_host="localhost", redis_port=6380)

    class ErrorMockRedis:
        def __init__(self):
            self._data = {}

        async def get(self, key):
            return self._data.get(key)

        async def set(self, key, value):
            raise Exception("Redis connection error")

        async def delete(self, *keys):
            return len(keys)

        async def zadd(self, key, mapping):
            return len(mapping)

        async def zrevrange(self, key, start, end):
            return []

        async def lpush(self, key, *values):
            return len(values)

        async def ltrim(self, key, start, end):
            return True

        async def lrem(self, key, count, value):
            return 1

        async def mget(self, keys):
            return [None] * len(keys)

        async def lrange(self, key, start, end):
            return []

        def pipeline(self):
            return PipeMock(self)

    error_store._redis = ErrorMockRedis()
    snapshot = create_test_snapshot()

    result = await error_store.save_snapshot(snapshot)
    assert result is False


@pytest.mark.asyncio
async def test_delete_snapshot_failure(store):
    """Test delete_snapshot handles Redis errors gracefully."""
    # Create a store with a mock that raises on get
    error_store = DeploymentSnapshotStore(redis_host="localhost", redis_port=6380)

    class ErrorMockRedis:
        def __init__(self):
            self._data = {}

        async def get(self, key):
            raise Exception("Redis connection error")

        async def set(self, key, value):
            return True

        async def delete(self, *keys):
            return len(keys)

        async def zadd(self, key, mapping):
            return len(mapping)

        async def zrevrange(self, key, start, end):
            return []

        async def lpush(self, key, *values):
            return len(values)

        async def ltrim(self, key, start, end):
            return True

        async def lrem(self, key, count, value):
            return 1

        async def mget(self, keys):
            return [None] * len(keys)

        async def lrange(self, key, start, end):
            return []

        def pipeline(self):
            return PipeMock(self)

    error_store._redis = ErrorMockRedis()

    result = await error_store.delete_snapshot("deploy-1")
    assert result is False


@pytest.mark.asyncio
async def test_list_snapshots_failure(store):
    """Test list_snapshots handles Redis errors gracefully."""
    # Create a store with a mock that raises on zrevrange
    error_store = DeploymentSnapshotStore(redis_host="localhost", redis_port=6380)

    class ErrorMockRedis:
        def __init__(self):
            self._data = {}

        async def get(self, key):
            return self._data.get(key)

        async def set(self, key, value):
            return True

        async def delete(self, *keys):
            return len(keys)

        async def zadd(self, key, mapping):
            return len(mapping)

        async def zrevrange(self, key, start, end):
            raise Exception("Redis connection error")

        async def lpush(self, key, *values):
            return len(values)

        async def ltrim(self, key, start, end):
            return True

        async def lrem(self, key, count, value):
            return 1

        async def mget(self, keys):
            return [None] * len(keys)

        async def lrange(self, key, start, end):
            return []

        def pipeline(self):
            return PipeMock(self)

    error_store._redis = ErrorMockRedis()

    result = await error_store.list_snapshots()
    assert result == []


# ==============================================================================
# Node-based Snapshot Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_get_snapshots_by_node(store, mock_redis):
    """Test getting all snapshots for a specific node."""
    # Create snapshots for different nodes
    snapshot1 = create_test_snapshot(deployment_id="deploy-1", snapshot_id="snap-1", node_ip="192.168.0.115")
    snapshot2 = create_test_snapshot(deployment_id="deploy-2", snapshot_id="snap-2", node_ip="192.168.0.115")
    snapshot3 = create_test_snapshot(deployment_id="deploy-3", snapshot_id="snap-3", node_ip="192.168.0.200")

    # Save all snapshots
    await store.save_snapshot(snapshot1)
    await store.save_snapshot(snapshot2)
    await store.save_snapshot(snapshot3)

    # Get snapshots for node 115
    snapshots = await store.get_snapshots_by_node("192.168.0.115")
    assert len(snapshots) == 2
    for snap in snapshots:
        assert snap.node_ip == "192.168.0.115"


@pytest.mark.asyncio
async def test_get_snapshots_by_node_empty(store, mock_redis):
    """Test getting snapshots for a node with no snapshots."""
    # Clear any existing data
    mock_redis._data.pop("deploy:snapshots:node:192.168.0.999", None)

    snapshots = await store.get_snapshots_by_node("192.168.0.999")
    assert len(snapshots) == 0
