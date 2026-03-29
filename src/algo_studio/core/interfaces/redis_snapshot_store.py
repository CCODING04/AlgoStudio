# src/algo_studio/core/interfaces/redis_snapshot_store.py
"""Redis implementation of snapshot storage for deployment rollback functionality.

This module provides RedisSnapshotStore that implements SnapshotStoreInterface
using Redis as the backing store with JSON serialization.

Phase 1: Redis implementation with 7-day TTL on snapshots
Phase 2.3: Updated to use DeploymentSnapshot types

Usage:
    store = RedisSnapshotStore()
    await store.save_snapshot(DeploymentSnapshot(...))
    snapshot = await store.get_snapshot("deploy-1")
    snapshots = await store.list_snapshots(limit=10)
    await store.delete_snapshot("deploy-1")
    await store.save_rollback_history(entry)
    history = await store.get_rollback_history("deploy-1")
"""

import json
import logging
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from algo_studio.core.deploy.rollback import DeploymentSnapshot, RollbackHistoryEntry
from .snapshot_store import SnapshotStoreInterface

logger = logging.getLogger(__name__)

# Default TTL: 7 days in seconds
DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60

# Redis key prefixes
REDIS_SNAPSHOT_PREFIX = "deploy:snapshot:"
REDIS_SNAPSHOT_ID_PREFIX = "deploy:snapshot:id:"
REDIS_NODE_SNAPSHOTS_PREFIX = "deploy:snapshots:node:"
REDIS_INDEX_KEY = "deploy:snapshot:index"
REDIS_ROLLBACK_HISTORY_PREFIX = "deploy:rollback_history:"


class RedisSnapshotStore(SnapshotStoreInterface):
    """Redis implementation of snapshot storage.

    Stores snapshots in Redis with the following key patterns:
    - deploy:snapshot:{deployment_id} - Current snapshot for a deployment
    - deploy:snapshot:id:{snapshot_id} - Snapshot data by snapshot ID
    - deploy:snapshots:node:{node_ip} - List of snapshots per node
    - deploy:rollback_history:{deployment_id} - Rollback history

    Features:
    - JSON serialization for DeploymentSnapshot objects
    - 7-day TTL by default (configurable)
    - Lazy Redis connection initialization
    - Rollback history management
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6380,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ):
        """Initialize RedisSnapshotStore.

        Args:
            redis_host: Redis server hostname (default: localhost)
            redis_port: Redis server port (default: 6380)
            ttl_seconds: Time-to-live for snapshots in seconds (default: 7 days)
        """
        self._redis_host = redis_host
        self._redis_port = redis_port
        self._ttl_seconds = ttl_seconds
        self._redis: Optional[redis.Redis] = None

    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection (lazy initialization).

        Returns:
            Redis client instance
        """
        if self._redis is None:
            self._redis = redis.Redis(
                host=self._redis_host,
                port=self._redis_port,
                decode_responses=True,
            )
        return self._redis

    async def save_snapshot(self, snapshot: DeploymentSnapshot) -> bool:
        """Save a deployment snapshot to Redis.

        Args:
            snapshot: DeploymentSnapshot to store

        Returns:
            True if save succeeded, False otherwise
        """
        try:
            r = await self._get_redis()

            # Store snapshot by deployment_id (current snapshot for deployment)
            snapshot_key = f"{REDIS_SNAPSHOT_PREFIX}{snapshot.deployment_id}"
            await r.set(snapshot_key, json.dumps(snapshot.to_dict()))

            # Also store by snapshot_id for efficient node-based lookup
            snapshot_id_key = f"{REDIS_SNAPSHOT_ID_PREFIX}{snapshot.snapshot_id}"
            await r.set(snapshot_id_key, json.dumps(snapshot.to_dict()))

            # Add to node's snapshot list (keep last 10)
            node_key = f"{REDIS_NODE_SNAPSHOTS_PREFIX}{snapshot.node_ip}"
            await r.lpush(node_key, snapshot.snapshot_id)
            await r.ltrim(node_key, 0, 9)

            # Update insertion order index
            import time
            timestamp = time.time()
            await r.zadd(REDIS_INDEX_KEY, {snapshot.deployment_id: timestamp})

            logger.debug(f"Saved snapshot for deployment: {snapshot.deployment_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save snapshot for deployment {snapshot.deployment_id}: {e}")
            return False

    async def get_snapshot(self, deployment_id: str) -> Optional[DeploymentSnapshot]:
        """Retrieve a snapshot by deployment ID.

        Args:
            deployment_id: Unique identifier for the deployment

        Returns:
            DeploymentSnapshot if found, None otherwise
        """
        try:
            r = await self._get_redis()
            snapshot_key = f"{REDIS_SNAPSHOT_PREFIX}{deployment_id}"

            snapshot_json = await r.get(snapshot_key)
            if snapshot_json is None:
                return None

            return DeploymentSnapshot.from_dict(json.loads(snapshot_json))

        except Exception as e:
            logger.error(f"Failed to get snapshot for deployment {deployment_id}: {e}")
            return None

    async def list_snapshots(self, limit: int = 10) -> List[DeploymentSnapshot]:
        """List recent snapshots from Redis.

        Args:
            limit: Maximum number of snapshots to return (default: 10)

        Returns:
            List of DeploymentSnapshots, most recent first
        """
        try:
            r = await self._get_redis()

            # Get deployment_ids from index, most recent first (highest score)
            deployment_ids = await r.zrevrange(REDIS_INDEX_KEY, 0, limit - 1)

            if not deployment_ids:
                return []

            # Fetch all snapshots in batch using mget
            snapshot_keys = [f"{REDIS_SNAPSHOT_PREFIX}{did}" for did in deployment_ids]
            snapshot_jsons = await r.mget(snapshot_keys)

            # Parse JSON and maintain order (most recent first)
            snapshots = []
            for snapshot_json in snapshot_jsons:
                if snapshot_json is not None:
                    snapshots.append(DeploymentSnapshot.from_dict(json.loads(snapshot_json)))

            return snapshots

        except Exception as e:
            logger.error(f"Failed to list snapshots: {e}")
            return []

    async def delete_snapshot(self, deployment_id: str) -> bool:
        """Delete a snapshot by deployment ID.

        Args:
            deployment_id: Unique identifier for the deployment

        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            r = await self._get_redis()
            snapshot_key = f"{REDIS_SNAPSHOT_PREFIX}{deployment_id}"

            # Get snapshot first to clean up related keys
            snapshot_json = await r.get(snapshot_key)
            if snapshot_json:
                snapshot_data = json.loads(snapshot_json)
                snapshot_id = snapshot_data.get("snapshot_id")
                node_ip = snapshot_data.get("node_ip")

                # Delete snapshot_id key
                if snapshot_id:
                    await r.delete(f"{REDIS_SNAPSHOT_ID_PREFIX}{snapshot_id}")

                # Remove from node's snapshot list
                if node_ip:
                    await r.lrem(f"{REDIS_NODE_SNAPSHOTS_PREFIX}{node_ip}", 0, snapshot_id)

            # Delete the main snapshot and index entry
            pipe = r.pipeline()
            pipe.delete(snapshot_key)
            pipe.zrem(REDIS_INDEX_KEY, deployment_id)
            results = await pipe.execute()

            deleted = results[0] > 0
            if deleted:
                logger.debug(f"Deleted snapshot for deployment: {deployment_id}")
            return deleted

        except Exception as e:
            logger.error(f"Failed to delete snapshot for deployment {deployment_id}: {e}")
            return False

    async def save_rollback_history(self, entry: RollbackHistoryEntry) -> None:
        """Save rollback history entry.

        Args:
            entry: RollbackHistoryEntry to save
        """
        try:
            r = await self._get_redis()
            history_key = f"{REDIS_ROLLBACK_HISTORY_PREFIX}{entry.deployment_id}"

            # Get existing history
            history_data = await r.get(history_key)
            history = []
            if history_data:
                history = json.loads(history_data)

            # Add new entry
            history.append(entry.to_dict())

            # Keep last 50 entries
            history = history[-50:]

            await r.set(history_key, json.dumps(history))
            logger.debug(f"Saved rollback history for deployment: {entry.deployment_id}")

        except Exception as e:
            logger.error(f"Failed to save rollback history for deployment {entry.deployment_id}: {e}")

    async def get_rollback_history(self, deployment_id: str) -> List[RollbackHistoryEntry]:
        """Get rollback history for a deployment.

        Args:
            deployment_id: Deployment identifier

        Returns:
            List of RollbackHistoryEntries (most recent first)
        """
        try:
            from datetime import datetime

            r = await self._get_redis()
            history_key = f"{REDIS_ROLLBACK_HISTORY_PREFIX}{deployment_id}"

            history_data = await r.get(history_key)
            if not history_data:
                return []

            from algo_studio.core.deploy.rollback import RollbackStatus
            history = json.loads(history_data)
            entries = []
            for entry_data in history:
                entry = RollbackHistoryEntry(
                    rollback_id=entry_data["rollback_id"],
                    deployment_id=entry_data["deployment_id"],
                    snapshot_id=entry_data["snapshot_id"],
                    status=RollbackStatus(entry_data["status"]),
                    initiated_by=entry_data["initiated_by"],
                    initiated_at=datetime.fromisoformat(entry_data["initiated_at"]),
                    completed_at=datetime.fromisoformat(entry_data["completed_at"]) if entry_data.get("completed_at") else None,
                    verification_result=entry_data.get("verification_result"),
                    error=entry_data.get("error"),
                )
                entries.append(entry)

            return entries

        except Exception as e:
            logger.error(f"Failed to get rollback history for deployment {deployment_id}: {e}")
            return []
