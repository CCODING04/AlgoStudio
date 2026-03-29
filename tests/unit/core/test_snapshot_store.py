"""Unit tests for InMemorySnapshotStore."""

import pytest
from datetime import datetime
from algo_studio.core.interfaces.snapshot_store import (
    SnapshotStoreInterface,
    InMemorySnapshotStore
)
from algo_studio.core.deploy.rollback import DeploymentSnapshot


def create_test_snapshot(
    snapshot_id: str = "snap-1",
    deployment_id: str = "deploy-1",
    node_ip: str = "127.0.0.1",
    version: str = "1.0",
    config: dict = None,
    steps_completed: list = None,
    artifacts: list = None,
    metadata: dict = None,
) -> DeploymentSnapshot:
    """Helper to create a test DeploymentSnapshot."""
    return DeploymentSnapshot(
        snapshot_id=snapshot_id,
        deployment_id=deployment_id,
        node_ip=node_ip,
        version=version,
        config=config or {},
        steps_completed=steps_completed or [],
        created_at=datetime.now(),
        ray_head_ip="127.0.0.1",
        ray_port=6379,
        artifacts=artifacts or [],
        metadata=metadata or {}
    )


@pytest.fixture
def store():
    return InMemorySnapshotStore()


@pytest.mark.asyncio
async def test_save_and_get_snapshot(store):
    """Test saving and retrieving a snapshot."""
    snapshot = create_test_snapshot(
        snapshot_id="snap-1",
        deployment_id="deploy-1",
        config={"version": "1.0", "config": {"key": "value"}}
    )
    result = await store.save_snapshot(snapshot)
    assert result is True

    retrieved = await store.get_snapshot("deploy-1")
    assert retrieved is not None
    assert retrieved.snapshot_id == "snap-1"
    assert retrieved.config["version"] == "1.0"
    assert retrieved.config["config"]["key"] == "value"


@pytest.mark.asyncio
async def test_get_nonexistent(store):
    """Test getting a non-existent snapshot returns None."""
    result = await store.get_snapshot("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_list_snapshots(store):
    """Test listing snapshots returns saved snapshots."""
    snapshot1 = create_test_snapshot(snapshot_id="snap-1", deployment_id="deploy-1", config={"data": "1"})
    snapshot2 = create_test_snapshot(snapshot_id="snap-2", deployment_id="deploy-2", config={"data": "2"})
    snapshot3 = create_test_snapshot(snapshot_id="snap-3", deployment_id="deploy-3", config={"data": "3"})

    await store.save_snapshot(snapshot1)
    await store.save_snapshot(snapshot2)
    await store.save_snapshot(snapshot3)

    snapshots = await store.list_snapshots(limit=2)
    assert len(snapshots) == 2


@pytest.mark.asyncio
async def test_delete_snapshot(store):
    """Test deleting an existing snapshot."""
    snapshot = create_test_snapshot(snapshot_id="snap-1", deployment_id="deploy-1", config={"data": "1"})
    await store.save_snapshot(snapshot)

    result = await store.delete_snapshot("deploy-1")
    assert result is True

    retrieved = await store.get_snapshot("deploy-1")
    assert retrieved is None


@pytest.mark.asyncio
async def test_delete_nonexistent(store):
    """Test deleting a non-existent snapshot returns False."""
    result = await store.delete_snapshot("nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_list_snapshots_order(store):
    """Test that list_snapshots returns most recent first."""
    snapshot1 = create_test_snapshot(snapshot_id="snap-1", deployment_id="deploy-1", config={"order": 1})
    snapshot2 = create_test_snapshot(snapshot_id="snap-2", deployment_id="deploy-2", config={"order": 2})
    snapshot3 = create_test_snapshot(snapshot_id="snap-3", deployment_id="deploy-3", config={"order": 3})

    await store.save_snapshot(snapshot1)
    await store.save_snapshot(snapshot2)
    await store.save_snapshot(snapshot3)

    snapshots = await store.list_snapshots(limit=10)
    # Most recent first (snap-3, snap-2, snap-1)
    assert snapshots[0].config["order"] == 3
    assert snapshots[1].config["order"] == 2
    assert snapshots[2].config["order"] == 1


@pytest.mark.asyncio
async def test_snapshot_data_independence(store):
    """Test that modifying returned snapshot doesn't affect stored data."""
    snapshot = create_test_snapshot(
        snapshot_id="snap-1",
        deployment_id="deploy-1",
        config={"version": "1.0", "config": {"key": "original"}}
    )
    await store.save_snapshot(snapshot)

    retrieved = await store.get_snapshot("deploy-1")
    retrieved.config["config"]["key"] = "modified"

    # Verify original data is unchanged
    stored = await store.get_snapshot("deploy-1")
    assert stored.config["config"]["key"] == "original"


@pytest.mark.asyncio
async def test_update_existing_snapshot(store):
    """Test that updating an existing snapshot replaces it."""
    snapshot1 = create_test_snapshot(
        snapshot_id="snap-1",
        deployment_id="deploy-1",
        config={"version": "1.0", "data": "original"}
    )
    snapshot2 = create_test_snapshot(
        snapshot_id="snap-1-updated",
        deployment_id="deploy-1",
        config={"version": "2.0", "data": "updated"}
    )

    await store.save_snapshot(snapshot1)
    await store.save_snapshot(snapshot2)

    retrieved = await store.get_snapshot("deploy-1")
    assert retrieved.config["version"] == "2.0"
    assert retrieved.config["data"] == "updated"


@pytest.mark.asyncio
async def test_list_snapshots_default_limit(store):
    """Test that list_snapshots uses default limit of 10."""
    # Create 15 snapshots
    for i in range(15):
        snapshot = create_test_snapshot(
            snapshot_id=f"snap-{i}",
            deployment_id=f"deploy-{i}",
            config={"index": i}
        )
        await store.save_snapshot(snapshot)

    snapshots = await store.list_snapshots()
    assert len(snapshots) == 10  # Default limit


@pytest.mark.asyncio
async def test_multiple_save_same_deployment_id(store):
    """Test that saving twice with same deployment_id updates, not duplicates."""
    snapshot1 = create_test_snapshot(snapshot_id="snap-1", deployment_id="deploy-1", config={"data": "first"})
    snapshot2 = create_test_snapshot(snapshot_id="snap-2", deployment_id="deploy-1", config={"data": "second"})

    await store.save_snapshot(snapshot1)
    await store.save_snapshot(snapshot2)

    snapshots = await store.list_snapshots()
    # Should only have one entry for deploy-1
    assert len(snapshots) == 1
    assert snapshots[0].config["data"] == "second"
