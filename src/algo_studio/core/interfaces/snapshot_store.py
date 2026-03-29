# src/algo_studio/core/interfaces/snapshot_store.py
"""Snapshot storage interface for deployment rollback functionality.

This module defines the abstract interface for snapshot storage,
enabling different storage implementations (Redis, SQLite, In-Memory).

Phase 1: Creates SnapshotStoreInterface + InMemorySnapshotStore
Phase 2.3: Updated to use DeploymentSnapshot types for RollbackService
"""

import copy
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from algo_studio.core.deploy.rollback import DeploymentSnapshot, RollbackHistoryEntry


class SnapshotStoreInterface(ABC):
    """Abstract interface for snapshot storage.

    Implementations should provide:
    - Async/await support for I/O operations
    - CRUD operations for snapshots using DeploymentSnapshot objects
    - Rollback history management

    Example:
        ```python
        class RedisSnapshotStore(SnapshotStoreInterface):
            async def save_snapshot(self, snapshot: DeploymentSnapshot) -> bool:
                ...

            async def get_snapshot(self, deployment_id: str) -> Optional[DeploymentSnapshot]:
                ...

            async def list_snapshots(self, limit: int = 10) -> List[DeploymentSnapshot]:
                ...

            async def delete_snapshot(self, deployment_id: str) -> bool:
                ...

            async def save_rollback_history(self, entry: RollbackHistoryEntry) -> None:
                ...

            async def get_rollback_history(self, deployment_id: str) -> List[RollbackHistoryEntry]:
                ...
        ```
    """

    @abstractmethod
    async def save_snapshot(self, snapshot: DeploymentSnapshot) -> bool:
        """Save a deployment snapshot.

        Args:
            snapshot: DeploymentSnapshot to store

        Returns:
            True if save succeeded, False otherwise
        """
        pass

    @abstractmethod
    async def get_snapshot(self, deployment_id: str) -> Optional[DeploymentSnapshot]:
        """Retrieve a snapshot by deployment ID.

        Args:
            deployment_id: Unique identifier for the deployment

        Returns:
            DeploymentSnapshot if found, None otherwise
        """
        pass

    @abstractmethod
    async def list_snapshots(self, limit: int = 10) -> List[DeploymentSnapshot]:
        """List recent snapshots.

        Args:
            limit: Maximum number of snapshots to return (default 10)

        Returns:
            List of DeploymentSnapshots, most recent first
        """
        pass

    @abstractmethod
    async def delete_snapshot(self, deployment_id: str) -> bool:
        """Delete a snapshot by deployment ID.

        Args:
            deployment_id: Unique identifier for the deployment

        Returns:
            True if deletion succeeded, False otherwise
        """
        pass

    @abstractmethod
    async def save_rollback_history(self, entry: RollbackHistoryEntry) -> None:
        """Save rollback history entry.

        Args:
            entry: RollbackHistoryEntry to save
        """
        pass

    @abstractmethod
    async def get_rollback_history(self, deployment_id: str) -> List[RollbackHistoryEntry]:
        """Get rollback history for a deployment.

        Args:
            deployment_id: Deployment identifier

        Returns:
            List of RollbackHistoryEntries (most recent first)
        """
        pass


class InMemorySnapshotStore(SnapshotStoreInterface):
    """In-memory implementation of snapshot storage for testing/development.

    WARNING: This implementation is NOT persistent and will lose data on restart.
    Use only for testing or single-instance development environments.

    Phase 1 use case: Provides a simple implementation for interface verification.
    """

    def __init__(self):
        self._snapshots: Dict[str, DeploymentSnapshot] = {}
        self._insertion_order: List[str] = []
        self._history: Dict[str, List[RollbackHistoryEntry]] = {}

    async def save_snapshot(self, snapshot: DeploymentSnapshot) -> bool:
        """Save snapshot to memory.

        Args:
            snapshot: DeploymentSnapshot to store

        Returns:
            True (always succeeds for in-memory store)
        """
        self._snapshots[snapshot.deployment_id] = snapshot
        if snapshot.deployment_id not in self._insertion_order:
            self._insertion_order.append(snapshot.deployment_id)
        return True

    async def get_snapshot(self, deployment_id: str) -> Optional[DeploymentSnapshot]:
        """Retrieve snapshot from memory (returns a deep copy for data independence).

        Args:
            deployment_id: Unique identifier for the deployment

        Returns:
            Deep copy of DeploymentSnapshot if found, None otherwise
        """
        snapshot = self._snapshots.get(deployment_id)
        if snapshot is None:
            return None
        # Return a deep copy to prevent external modifications from affecting stored data
        return copy.deepcopy(snapshot)

    async def list_snapshots(self, limit: int = 10) -> List[DeploymentSnapshot]:
        """List recent snapshots from memory (returns deep copies for data independence).

        Args:
            limit: Maximum number of snapshots to return

        Returns:
            List of deep copies of DeploymentSnapshots, most recent first
        """
        result = []
        for dep_id in reversed(self._insertion_order):
            if dep_id in self._snapshots:
                # Return deep copies to prevent external modifications
                result.append(copy.deepcopy(self._snapshots[dep_id]))
                if len(result) >= limit:
                    break
        return result

    async def delete_snapshot(self, deployment_id: str) -> bool:
        """Delete snapshot from memory.

        Args:
            deployment_id: Unique identifier for the deployment

        Returns:
            True if deleted, False if not found
        """
        if deployment_id in self._snapshots:
            del self._snapshots[deployment_id]
            if deployment_id in self._insertion_order:
                self._insertion_order.remove(deployment_id)
            return True
        return False

    async def save_rollback_history(self, entry: RollbackHistoryEntry) -> None:
        """Save rollback history entry.

        Args:
            entry: RollbackHistoryEntry to save
        """
        if entry.deployment_id not in self._history:
            self._history[entry.deployment_id] = []
        self._history[entry.deployment_id].append(entry)
        # Keep last 50 entries
        self._history[entry.deployment_id] = self._history[entry.deployment_id][-50:]

    async def get_rollback_history(self, deployment_id: str) -> List[RollbackHistoryEntry]:
        """Get rollback history for a deployment.

        Args:
            deployment_id: Deployment identifier

        Returns:
            List of RollbackHistoryEntries (most recent first)
        """
        return self._history.get(deployment_id, [])
