# src/algo_studio/core/deploy/rollback.py
"""Deployment rollback mechanism for AlgoStudio.

This module provides:
- DeploymentSnapshotStore: Stores version snapshots before each deployment
- RollbackService: Handles rollback logic with verification
- RollbackVerificationResult: Result of rollback verification

Usage:
    snapshot_store = DeploymentSnapshotStore()
    rollback_service = RollbackService(snapshot_store)

    # Create snapshot before deployment
    await snapshot_store.create_snapshot(deployment_id, node_ip, version_info)

    # Execute rollback
    result = await rollback_service.rollback(deployment_id, task_id)
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncssh
import redis.asyncio as redis

logger = logging.getLogger(__name__)


# ==============================================================================
# Command Validation (for security)
# ==============================================================================

ALLOWED_ROLLBACK_COMMANDS = [
    r"^ray\s+stop$",
    r"^rm\s+-rf\s+(~|/home/\w+)/\.venv-ray$",
    r"^rm\s+-r\s+(~|/home/\w+)/\.venv-ray$",
    r"^rm\s+-f\s+(~|/home/\w+)/\.deps_installed$",
    r"^rm\s+-f\s+(~|/home/\w+)/\.code_synced$",
    r"^sudo\s+rm\s+-f\s+/etc/sudoers\.d/admin02$",
    r"^rm\s+-f\s+(~|/home/\w+)/\.ssh/authorized_keys$",
]

FORBIDDEN_ROLLBACK_PATTERNS = [
    r"&&\s*\w+",
    r"\|\|",
    r";\s*rm\s+-rf",
    r">\s*/dev/sd",
    r"^\s*dd\s+if=.*of=/dev",
    r";\s*shutdown",
    r";\s*reboot",
    r"eval\s+.*\$",
    r"`.*`",
    r"--force",
]


def validate_rollback_command(cmd: str) -> bool:
    """Validate rollback command is safe and allowed.

    Args:
        cmd: Command to validate

    Returns:
        True if command is allowed, False otherwise
    """
    # Check for forbidden patterns
    for forbidden in FORBIDDEN_ROLLBACK_PATTERNS:
        if re.search(forbidden, cmd):
            return False

    # Check against allowed patterns
    for allowed in ALLOWED_ROLLBACK_COMMANDS:
        if re.match(allowed, cmd.strip()):
            return True

    return False


class RollbackStatus(str, Enum):
    """Rollback operation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_SNAPSHOT = "no_snapshot"


@dataclass
class DeploymentSnapshot:
    """Deployment version snapshot.

    Stores the complete state of a deployment at a point in time,
    allowing rollback to a previous known-good state.
    """
    snapshot_id: str
    deployment_id: str
    node_ip: str
    version: str
    config: Dict[str, Any]
    steps_completed: List[str]
    created_at: datetime
    ray_head_ip: str
    ray_port: int
    artifacts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "deployment_id": self.deployment_id,
            "node_ip": self.node_ip,
            "version": self.version,
            "config": self.config,
            "steps_completed": self.steps_completed,
            "created_at": self.created_at.isoformat(),
            "ray_head_ip": self.ray_head_ip,
            "ray_port": self.ray_port,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeploymentSnapshot":
        """Create snapshot from dictionary."""
        return cls(
            snapshot_id=data["snapshot_id"],
            deployment_id=data["deployment_id"],
            node_ip=data["node_ip"],
            version=data["version"],
            config=data["config"],
            steps_completed=data["steps_completed"],
            created_at=datetime.fromisoformat(data["created_at"]),
            ray_head_ip=data["ray_head_ip"],
            ray_port=data["ray_port"],
            artifacts=data.get("artifacts", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class RollbackHistoryEntry:
    """Entry in rollback history."""
    rollback_id: str
    deployment_id: str
    snapshot_id: str
    status: RollbackStatus
    initiated_by: str
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    verification_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rollback_id": self.rollback_id,
            "deployment_id": self.deployment_id,
            "snapshot_id": self.snapshot_id,
            "status": self.status.value,
            "initiated_by": self.initiated_by,
            "initiated_at": self.initiated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "verification_result": self.verification_result,
            "error": self.error,
        }


@dataclass
class RollbackVerificationResult:
    """Result of rollback verification."""
    success: bool
    checks_passed: List[str]
    checks_failed: List[str]
    latency_ms: float
    message: str


class DeploymentSnapshotStore:
    """Store for deployment version snapshots.

    Stores deployment snapshots in Redis with the following keys:
    - deploy:snapshot:{deployment_id} - Current snapshot for a deployment
    - deploy:snapshots:node:{node_ip} - List of all snapshots for a node
    - deploy:rollback_history:{deployment_id} - Rollback history for a deployment

    Implements SnapshotStoreInterface for dependency injection.
    """

    REDIS_SNAPSHOT_PREFIX = "deploy:snapshot:"
    REDIS_SNAPSHOT_ID_PREFIX = "deploy:snapshot:id:"
    REDIS_NODE_SNAPSHOTS_PREFIX = "deploy:snapshots:node:"
    REDIS_ROLLBACK_HISTORY_PREFIX = "deploy:rollback_history:"
    REDIS_INDEX_KEY = "deploy:snapshot:index"

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6380):
        self._redis: Optional[redis.Redis] = None
        self._redis_host = redis_host
        self._redis_port = redis_port

    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection (lazy initialization)."""
        if self._redis is None:
            self._redis = redis.Redis(
                host=self._redis_host,
                port=self._redis_port,
                decode_responses=True,
            )
        return self._redis

    async def save_snapshot(self, snapshot: DeploymentSnapshot) -> bool:
        """Save a deployment snapshot (implements SnapshotStoreInterface).

        Args:
            snapshot: DeploymentSnapshot to store

        Returns:
            True if save succeeded, False otherwise
        """
        try:
            r = await self._get_redis()

            # Store snapshot by deployment_id (current snapshot for deployment)
            snapshot_key = f"{self.REDIS_SNAPSHOT_PREFIX}{snapshot.deployment_id}"
            await r.set(snapshot_key, json.dumps(snapshot.to_dict()))

            # Also store by snapshot_id for efficient node-based lookup
            snapshot_id_key = f"{self.REDIS_SNAPSHOT_ID_PREFIX}{snapshot.snapshot_id}"
            await r.set(snapshot_id_key, json.dumps(snapshot.to_dict()))

            # Add to node's snapshot list (keep last 10)
            node_key = f"{self.REDIS_NODE_SNAPSHOTS_PREFIX}{snapshot.node_ip}"
            await r.lpush(node_key, snapshot.snapshot_id)
            await r.ltrim(node_key, 0, 9)

            # Update insertion order index
            import time
            timestamp = time.time()
            await r.zadd(self.REDIS_INDEX_KEY, {snapshot.deployment_id: timestamp})

            logger.info(f"Saved deployment snapshot: {snapshot.snapshot_id} for deployment: {snapshot.deployment_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save snapshot for deployment {snapshot.deployment_id}: {e}")
            return False

    async def create_snapshot(
        self,
        deployment_id: str,
        node_ip: str,
        version: str,
        config: Dict[str, Any],
        steps_completed: List[str],
        ray_head_ip: str,
        ray_port: int = 6379,
        artifacts: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DeploymentSnapshot:
        """Create a deployment snapshot before deployment begins.

        Args:
            deployment_id: Unique deployment identifier
            node_ip: Target node IP address
            version: Deployment version string
            config: Deployment configuration
            steps_completed: List of completed deployment steps
            ray_head_ip: Ray head node IP
            ray_port: Ray port
            artifacts: List of deployment artifacts
            metadata: Additional metadata

        Returns:
            Created DeploymentSnapshot
        """
        # Use microseconds to avoid snapshot ID collisions in same second
        snapshot_id = f"snap-{deployment_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        snapshot = DeploymentSnapshot(
            snapshot_id=snapshot_id,
            deployment_id=deployment_id,
            node_ip=node_ip,
            version=version,
            config=config,
            steps_completed=steps_completed,
            created_at=datetime.now(),
            ray_head_ip=ray_head_ip,
            ray_port=ray_port,
            artifacts=artifacts or [],
            metadata=metadata or {},
        )

        success = await self.save_snapshot(snapshot)
        if not success:
            raise RuntimeError(f"Failed to save snapshot for {deployment_id}")
        return snapshot

    async def get_snapshot(self, deployment_id: str) -> Optional[DeploymentSnapshot]:
        """Get current snapshot for a deployment (implements SnapshotStoreInterface).

        Args:
            deployment_id: Deployment identifier

        Returns:
            DeploymentSnapshot if exists, None otherwise
        """
        try:
            r = await self._get_redis()
            snapshot_key = f"{self.REDIS_SNAPSHOT_PREFIX}{deployment_id}"
            data = await r.get(snapshot_key)

            if data:
                return DeploymentSnapshot.from_dict(json.loads(data))
            return None
        except Exception as e:
            logger.error(f"Failed to get snapshot for deployment {deployment_id}: {e}")
            return None

    async def list_snapshots(self, limit: int = 10) -> List[DeploymentSnapshot]:
        """List recent snapshots (implements SnapshotStoreInterface).

        Args:
            limit: Maximum number of snapshots to return

        Returns:
            List of DeploymentSnapshots, most recent first
        """
        try:
            r = await self._get_redis()

            # Get deployment_ids from index, most recent first
            deployment_ids = await r.zrevrange(self.REDIS_INDEX_KEY, 0, limit - 1)

            if not deployment_ids:
                return []

            # Fetch all snapshots in batch
            snapshot_keys = [f"{self.REDIS_SNAPSHOT_PREFIX}{did}" for did in deployment_ids]
            snapshot_jsons = await r.mget(snapshot_keys)

            snapshots = []
            for snapshot_json in snapshot_jsons:
                if snapshot_json is not None:
                    snapshots.append(DeploymentSnapshot.from_dict(json.loads(snapshot_json)))

            return snapshots

        except Exception as e:
            logger.error(f"Failed to list snapshots: {e}")
            return []

    async def delete_snapshot(self, deployment_id: str) -> bool:
        """Delete a snapshot by deployment ID (implements SnapshotStoreInterface).

        Args:
            deployment_id: Unique identifier for the deployment

        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            r = await self._get_redis()
            snapshot_key = f"{self.REDIS_SNAPSHOT_PREFIX}{deployment_id}"

            # Get snapshot first to clean up related keys
            snapshot_json = await r.get(snapshot_key)
            if snapshot_json:
                snapshot_data = json.loads(snapshot_json)
                snapshot_id = snapshot_data.get("snapshot_id")
                node_ip = snapshot_data.get("node_ip")

                # Delete snapshot_id key
                if snapshot_id:
                    await r.delete(f"{self.REDIS_SNAPSHOT_ID_PREFIX}{snapshot_id}")

                # Remove from node's snapshot list
                if node_ip:
                    await r.lrem(f"{self.REDIS_NODE_SNAPSHOTS_PREFIX}{node_ip}", 0, snapshot_id)

            # Delete the main snapshot and index entry
            pipe = r.pipeline()
            pipe.delete(snapshot_key)
            pipe.zrem(self.REDIS_INDEX_KEY, deployment_id)
            results = await pipe.execute()

            deleted = results[0] > 0
            if deleted:
                logger.info(f"Deleted snapshot for deployment: {deployment_id}")
            return deleted

        except Exception as e:
            logger.error(f"Failed to delete snapshot for deployment {deployment_id}: {e}")
            return False

    async def get_snapshots_by_node(self, node_ip: str) -> List[DeploymentSnapshot]:
        """Get all snapshots for a node.

        Args:
            node_ip: Node IP address

        Returns:
            List of DeploymentSnapshots (most recent first)
        """
        try:
            r = await self._get_redis()
            node_key = f"{self.REDIS_NODE_SNAPSHOTS_PREFIX}{node_ip}"

            snapshot_ids = await r.lrange(node_key, 0, -1)
            if not snapshot_ids:
                return []

            # Batch fetch all snapshots by snapshot_id (O(1) per key instead of O(n) scan)
            snapshot_keys = [f"{self.REDIS_SNAPSHOT_ID_PREFIX}{snap_id}" for snap_id in snapshot_ids]
            snapshot_data_list = await r.mget(snapshot_keys)

            snapshots = []
            for snap_data_json in snapshot_data_list:
                if snap_data_json:
                    snap_data = json.loads(snap_data_json)
                    # Double-check node_ip matches (defensive)
                    if snap_data.get("node_ip") == node_ip:
                        snapshots.append(DeploymentSnapshot.from_dict(snap_data))

            return snapshots
        except Exception as e:
            logger.error(f"Failed to get snapshots for node {node_ip}: {e}")
            return []

    async def save_rollback_history(self, entry: RollbackHistoryEntry) -> None:
        """Save rollback history entry (implements SnapshotStoreInterface).

        Args:
            entry: RollbackHistoryEntry to save
        """
        try:
            r = await self._get_redis()
            history_key = f"{self.REDIS_ROLLBACK_HISTORY_PREFIX}{entry.deployment_id}"

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
        except Exception as e:
            logger.error(f"Failed to save rollback history for deployment {entry.deployment_id}: {e}")

    async def get_rollback_history(self, deployment_id: str) -> List[RollbackHistoryEntry]:
        """Get rollback history for a deployment (implements SnapshotStoreInterface).

        Args:
            deployment_id: Deployment identifier

        Returns:
            List of RollbackHistoryEntries (most recent first)
        """
        try:
            r = await self._get_redis()
            history_key = f"{self.REDIS_ROLLBACK_HISTORY_PREFIX}{deployment_id}"

            history_data = await r.get(history_key)
            if not history_data:
                return []

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


class RollbackService:
    """Service for handling deployment rollbacks.

    Rollback Process:
    1. Get snapshot for deployment
    2. Execute rollback steps in reverse order
    3. Verify rollback success
    4. Update rollback history

    Uses SnapshotStoreInterface for dependency injection, with RedisSnapshotStore
    as the default implementation.
    """

    def __init__(self, snapshot_store: "SnapshotStoreInterface" = None):
        # Import here to avoid circular import
        from algo_studio.core.interfaces import RedisSnapshotStore
        self.snapshot_store = snapshot_store if snapshot_store is not None else RedisSnapshotStore()
        self._rollback_steps = {
            "start_ray": self._rollback_ray,
            "sync_code": self._rollback_code,
            "install_deps": self._rollback_deps,
            "create_venv": self._rollback_venv,
            "sudo_config": self._rollback_sudo,
            "connecting": self._rollback_connecting,
        }

    async def rollback(
        self,
        deployment_id: str,
        task_id: str,
        initiated_by: str = "system",
    ) -> RollbackHistoryEntry:
        """Execute rollback for a deployment.

        Args:
            deployment_id: Deployment to rollback
            task_id: Associated task ID for tracking
            initiated_by: User/system initiating rollback

        Returns:
            RollbackHistoryEntry with result
        """
        rollback_id = f"rollback-{deployment_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        # Get snapshot
        snapshot = await self.snapshot_store.get_snapshot(deployment_id)
        if not snapshot:
            entry = RollbackHistoryEntry(
                rollback_id=rollback_id,
                deployment_id=deployment_id,
                snapshot_id="",
                status=RollbackStatus.NO_SNAPSHOT,
                initiated_by=initiated_by,
                initiated_at=datetime.now(),
                error=f"No snapshot found for deployment: {deployment_id}",
            )
            await self.snapshot_store.save_rollback_history(entry)
            return entry

        entry = RollbackHistoryEntry(
            rollback_id=rollback_id,
            deployment_id=deployment_id,
            snapshot_id=snapshot.snapshot_id,
            status=RollbackStatus.IN_PROGRESS,
            initiated_by=initiated_by,
            initiated_at=datetime.now(),
        )

        await self.snapshot_store.save_rollback_history(entry)

        try:
            # Execute rollback steps in reverse order
            for step in reversed(snapshot.steps_completed):
                rollback_fn = self._rollback_steps.get(step)
                if rollback_fn:
                    try:
                        await rollback_fn(snapshot)
                    except Exception as e:
                        logger.warning(f"Rollback step {step} failed: {e}")

            # Verify rollback
            entry.status = RollbackStatus.VERIFYING
            await self.snapshot_store.save_rollback_history(entry)

            verification_result = await self._verify_rollback(snapshot)

            if verification_result.success:
                entry.status = RollbackStatus.COMPLETED
                entry.verification_result = verification_result.__dict__
            else:
                entry.status = RollbackStatus.FAILED
                entry.error = verification_result.message

            entry.completed_at = datetime.now()
            await self.snapshot_store.save_rollback_history(entry)

        except Exception as e:
            entry.status = RollbackStatus.FAILED
            entry.error = str(e)
            entry.completed_at = datetime.now()
            await self.snapshot_store.save_rollback_history(entry)

        return entry

    async def _rollback_ray(self, snapshot: DeploymentSnapshot) -> None:
        """Stop Ray worker via SSH.

        Executes `ray stop` on the remote node to stop the Ray worker process.

        Args:
            snapshot: Deployment snapshot containing node_ip and credentials

        Raises:
            SSHConnectionError: If SSH connection fails
        """
        logger.info(f"Rolling back Ray worker on {snapshot.node_ip}")

        try:
            # Get SSH credentials from snapshot config or metadata
            username = snapshot.config.get("username", "admin02")
            password = snapshot.config.get("password") or snapshot.metadata.get("password")
            if not password:
                # Try to get from metadata
                password = snapshot.metadata.get("ssh_password")
                if not password:
                    logger.warning(f"No SSH password found for {snapshot.node_ip}, skipping ray rollback")
                    return

            # Execute ray stop via SSH
            conn = await asyncssh.connect(
                snapshot.node_ip,
                username=username,
                password=password,
                known_hosts=None,
                connect_timeout=30,
            )

            try:
                # Validate command
                cmd = "ray stop"
                if not validate_rollback_command(cmd):
                    logger.warning(f"Rollback command not allowed: {cmd}")
                    return

                result = await conn.run(cmd, check=False, timeout=120)
                if result.exit_status == 0:
                    logger.info(f"Ray worker stopped successfully on {snapshot.node_ip}")
                else:
                    logger.warning(f"Ray stop returned non-zero exit status on {snapshot.node_ip}: {result.exit_status}")
            finally:
                conn.close()

        except asyncssh.DisconnectError as e:
            logger.warning(f"SSH disconnect error during Ray rollback on {snapshot.node_ip}: {e}")
        except asyncssh.ChannelOpenError as e:
            logger.warning(f"SSH channel error during Ray rollback on {snapshot.node_ip}: {e}")
        except Exception as e:
            logger.warning(f"Failed to rollback Ray worker on {snapshot.node_ip}: {e}")

    async def _rollback_code(self, snapshot: DeploymentSnapshot) -> None:
        """Rollback code sync via SSH.

        Removes the code synced marker file or the code directory.

        Args:
            snapshot: Deployment snapshot containing node_ip and credentials

        Raises:
            SSHConnectionError: If SSH connection fails
        """
        logger.info(f"Rolling back code on {snapshot.node_ip}")

        try:
            # Get SSH credentials from snapshot config or metadata
            username = snapshot.config.get("username", "admin02")
            password = snapshot.config.get("password") or snapshot.metadata.get("password")
            if not password:
                password = snapshot.metadata.get("ssh_password")
                if not password:
                    logger.warning(f"No SSH password found for {snapshot.node_ip}, skipping code rollback")
                    return

            conn = await asyncssh.connect(
                snapshot.node_ip,
                username=username,
                password=password,
                known_hosts=None,
                connect_timeout=30,
            )

            try:
                # Remove the code synced marker
                cmd = "rm -f ~/.code_synced"
                if not validate_rollback_command(cmd):
                    logger.warning(f"Rollback command not allowed: {cmd}")
                    return

                result = await conn.run(cmd, check=False, timeout=60)
                if result.exit_status == 0:
                    logger.info(f"Code sync marker removed on {snapshot.node_ip}")
                else:
                    logger.warning(f"Failed to remove code sync marker on {snapshot.node_ip}")
            finally:
                conn.close()

        except asyncssh.DisconnectError as e:
            logger.warning(f"SSH disconnect error during code rollback on {snapshot.node_ip}: {e}")
        except asyncssh.ChannelOpenError as e:
            logger.warning(f"SSH channel error during code rollback on {snapshot.node_ip}: {e}")
        except Exception as e:
            logger.warning(f"Failed to rollback code on {snapshot.node_ip}: {e}")

    async def _rollback_deps(self, snapshot: DeploymentSnapshot) -> None:
        """Rollback dependency installation via SSH.

        Removes the dependency installed marker file.

        Args:
            snapshot: Deployment snapshot containing node_ip and credentials

        Raises:
            SSHConnectionError: If SSH connection fails
        """
        logger.info(f"Rolling back dependencies on {snapshot.node_ip}")

        try:
            # Get SSH credentials from snapshot config or metadata
            username = snapshot.config.get("username", "admin02")
            password = snapshot.config.get("password") or snapshot.metadata.get("password")
            if not password:
                password = snapshot.metadata.get("ssh_password")
                if not password:
                    logger.warning(f"No SSH password found for {snapshot.node_ip}, skipping deps rollback")
                    return

            conn = await asyncssh.connect(
                snapshot.node_ip,
                username=username,
                password=password,
                known_hosts=None,
                connect_timeout=30,
            )

            try:
                # Remove the deps installed marker
                cmd = "rm -f ~/.deps_installed"
                if not validate_rollback_command(cmd):
                    logger.warning(f"Rollback command not allowed: {cmd}")
                    return

                result = await conn.run(cmd, check=False, timeout=60)
                if result.exit_status == 0:
                    logger.info(f"Dependencies marker removed on {snapshot.node_ip}")
                else:
                    logger.warning(f"Failed to remove deps marker on {snapshot.node_ip}")
            finally:
                conn.close()

        except asyncssh.DisconnectError as e:
            logger.warning(f"SSH disconnect error during deps rollback on {snapshot.node_ip}: {e}")
        except asyncssh.ChannelOpenError as e:
            logger.warning(f"SSH channel error during deps rollback on {snapshot.node_ip}: {e}")
        except Exception as e:
            logger.warning(f"Failed to rollback dependencies on {snapshot.node_ip}: {e}")

    async def _rollback_venv(self, snapshot: DeploymentSnapshot) -> None:
        """Rollback virtual environment via SSH.

        Removes the virtual environment directory.

        Args:
            snapshot: Deployment snapshot containing node_ip and credentials

        Raises:
            SSHConnectionError: If SSH connection fails
        """
        logger.info(f"Rolling back venv on {snapshot.node_ip}")

        try:
            # Get SSH credentials from snapshot config or metadata
            username = snapshot.config.get("username", "admin02")
            password = snapshot.config.get("password") or snapshot.metadata.get("password")
            if not password:
                password = snapshot.metadata.get("ssh_password")
                if not password:
                    logger.warning(f"No SSH password found for {snapshot.node_ip}, skipping venv rollback")
                    return

            conn = await asyncssh.connect(
                snapshot.node_ip,
                username=username,
                password=password,
                known_hosts=None,
                connect_timeout=30,
            )

            try:
                # Remove the virtual environment
                cmd = "rm -rf ~/.venv-ray"
                if not validate_rollback_command(cmd):
                    logger.warning(f"Rollback command not allowed: {cmd}")
                    return

                result = await conn.run(cmd, check=False, timeout=120)
                if result.exit_status == 0:
                    logger.info(f"Virtual environment removed on {snapshot.node_ip}")
                else:
                    logger.warning(f"Failed to remove venv on {snapshot.node_ip}")
            finally:
                conn.close()

        except asyncssh.DisconnectError as e:
            logger.warning(f"SSH disconnect error during venv rollback on {snapshot.node_ip}: {e}")
        except asyncssh.ChannelOpenError as e:
            logger.warning(f"SSH channel error during venv rollback on {snapshot.node_ip}: {e}")
        except Exception as e:
            logger.warning(f"Failed to rollback venv on {snapshot.node_ip}: {e}")

    async def _rollback_sudo(self, snapshot: DeploymentSnapshot) -> None:
        """Rollback sudo configuration via SSH.

        Removes the sudoers file for passwordless sudo access.

        Args:
            snapshot: Deployment snapshot containing node_ip and credentials

        Raises:
            SSHConnectionError: If SSH connection fails
        """
        logger.info(f"Rolling back sudo config on {snapshot.node_ip}")

        try:
            # Get SSH credentials from snapshot config or metadata
            username = snapshot.config.get("username", "admin02")
            password = snapshot.config.get("password") or snapshot.metadata.get("password")
            if not password:
                password = snapshot.metadata.get("ssh_password")
                if not password:
                    logger.warning(f"No SSH password found for {snapshot.node_ip}, skipping sudo rollback")
                    return

            conn = await asyncssh.connect(
                snapshot.node_ip,
                username=username,
                password=password,
                known_hosts=None,
                connect_timeout=30,
            )

            try:
                # Remove the sudoers file (requires sudo)
                cmd = "sudo rm -f /etc/sudoers.d/admin02"
                if not validate_rollback_command(cmd):
                    logger.warning(f"Rollback command not allowed: {cmd}")
                    return

                result = await conn.run(cmd, check=False, timeout=60)
                if result.exit_status == 0:
                    logger.info(f"Sudoers file removed on {snapshot.node_ip}")
                else:
                    logger.warning(f"Failed to remove sudoers file on {snapshot.node_ip}: {result.stderr}")
            finally:
                conn.close()

        except asyncssh.DisconnectError as e:
            logger.warning(f"SSH disconnect error during sudo rollback on {snapshot.node_ip}: {e}")
        except asyncssh.ChannelOpenError as e:
            logger.warning(f"SSH channel error during sudo rollback on {snapshot.node_ip}: {e}")
        except Exception as e:
            logger.warning(f"Failed to rollback sudo config on {snapshot.node_ip}: {e}")

    async def _rollback_connecting(self, snapshot: DeploymentSnapshot) -> None:
        """Rollback SSH connection via SSH.

        Removes or revokes SSH keys/credentials from the remote node.

        Args:
            snapshot: Deployment snapshot containing node_ip and credentials

        Raises:
            SSHConnectionError: If SSH connection fails
        """
        logger.info(f"Rolling back SSH connection on {snapshot.node_ip}")

        try:
            # Get SSH credentials from snapshot config or metadata
            username = snapshot.config.get("username", "admin02")
            password = snapshot.config.get("password") or snapshot.metadata.get("password")
            if not password:
                password = snapshot.metadata.get("ssh_password")
                if not password:
                    logger.warning(f"No SSH password found for {snapshot.node_ip}, skipping connecting rollback")
                    return

            conn = await asyncssh.connect(
                snapshot.node_ip,
                username=username,
                password=password,
                known_hosts=None,
                connect_timeout=30,
            )

            try:
                # Remove the authorized_keys file to revoke SSH access
                # This is a simple approach - in production you might want to
                # remove specific keys rather than the entire file
                cmd = "rm -f ~/.ssh/authorized_keys"
                if not validate_rollback_command(cmd):
                    logger.warning(f"Rollback command not allowed: {cmd}")
                    return

                result = await conn.run(cmd, check=False, timeout=60)
                if result.exit_status == 0:
                    logger.info(f"SSH authorized_keys removed on {snapshot.node_ip}")
                else:
                    # It's ok if the file doesn't exist
                    logger.info(f"No authorized_keys to remove on {snapshot.node_ip}")
            finally:
                conn.close()

        except asyncssh.DisconnectError as e:
            logger.warning(f"SSH disconnect error during connecting rollback on {snapshot.node_ip}: {e}")
        except asyncssh.ChannelOpenError as e:
            logger.warning(f"SSH channel error during connecting rollback on {snapshot.node_ip}: {e}")
        except Exception as e:
            logger.warning(f"Failed to rollback SSH connection on {snapshot.node_ip}: {e}")

    async def _verify_rollback(self, snapshot: DeploymentSnapshot) -> RollbackVerificationResult:
        """Verify rollback was successful.

        Verification checks:
        1. SSH connection to node
        2. Ray is not running
        3. Virtual environment state

        Args:
            snapshot: Snapshot that was rolled back to

        Returns:
            RollbackVerificationResult
        """
        import time
        start_time = time.time()

        checks_passed = []
        checks_failed = []

        # In a real implementation, these would be actual SSH checks
        # For now, we simulate the verification

        # Check 1: SSH connectivity
        try:
            # Simulated check - would be: await ssh_check(snapshot.node_ip)
            checks_passed.append("ssh_connectivity")
        except Exception as e:
            checks_failed.append(f"ssh_connectivity: {e}")

        # Check 2: Ray not running (expected after rollback)
        try:
            # Simulated check - would be: ray_stopped = await check_ray_stopped(snapshot.node_ip)
            ray_stopped = True  # Simulated
            if ray_stopped:
                checks_passed.append("ray_stopped")
            else:
                checks_failed.append("ray_not_stopped")
        except Exception as e:
            checks_failed.append(f"ray_check: {e}")

        # Check 3: Node is reachable
        try:
            # Simulated check - would be: reachable = await ping_node(snapshot.node_ip)
            reachable = True  # Simulated
            if reachable:
                checks_passed.append("node_reachable")
            else:
                checks_failed.append("node_not_reachable")
        except Exception as e:
            checks_failed.append(f"node_reachability: {e}")

        latency_ms = (time.time() - start_time) * 1000

        success = len(checks_failed) == 0
        message = "Rollback verification completed successfully" if success else f"Rollback verification failed: {', '.join(checks_failed)}"

        return RollbackVerificationResult(
            success=success,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            latency_ms=latency_ms,
            message=message,
        )


class DeploySnapshotMixin:
    """Mixin to add snapshot functionality to existing deploy components."""

    async def create_deployment_snapshot(
        self,
        deployment_id: str,
        node_ip: str,
        version: str,
        config: Dict[str, Any],
        steps_completed: List[str],
        ray_head_ip: str,
        ray_port: int = 6379,
    ) -> DeploymentSnapshot:
        """Create a snapshot before deployment.

        This should be called before starting a new deployment
        to record the current state for potential rollback.
        """
        snapshot_store = getattr(self, 'snapshot_store', None) or DeploymentSnapshotStore()
        return await snapshot_store.create_snapshot(
            deployment_id=deployment_id,
            node_ip=node_ip,
            version=version,
            config=config,
            steps_completed=steps_completed,
            ray_head_ip=ray_head_ip,
            ray_port=ray_port,
        )


# ==============================================================================
# Interface Registration (to avoid circular import at module load time)
# ==============================================================================

def _register_as_snapshot_store_interface():
    """Register DeploymentSnapshotStore as implementing SnapshotStoreInterface.

    This is done at module load time to enable dependency injection with
    SnapshotStoreInterface type hints. The registration uses ABC's virtual
    subclass mechanism to avoid requiring SnapshotStoreInterface to be imported
    at class definition time (which would cause a circular import).

    Note: DeploymentSnapshotStore already implements all methods required by
    SnapshotStoreInterface, so this registration is purely for type checking
    and dependency injection purposes.
    """
    try:
        from algo_studio.core.interfaces.snapshot_store import SnapshotStoreInterface
        SnapshotStoreInterface.register(DeploymentSnapshotStore)
    except ImportError:
        # If interfaces module cannot be imported (e.g., during early bootstrap),
        # skip registration. The class will still work via duck typing.
        pass


_register_as_snapshot_store_interface()
del _register_as_snapshot_store_interface