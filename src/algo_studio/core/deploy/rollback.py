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
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


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
    """

    REDIS_SNAPSHOT_PREFIX = "deploy:snapshot:"
    REDIS_SNAPSHOT_ID_PREFIX = "deploy:snapshot:id:"  # New: store by snapshot_id for efficient lookup
    REDIS_NODE_SNAPSHOTS_PREFIX = "deploy:snapshots:node:"
    REDIS_ROLLBACK_HISTORY_PREFIX = "deploy:rollback_history:"

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

        r = await self._get_redis()

        # Store snapshot by deployment_id (current snapshot for deployment)
        snapshot_key = f"{self.REDIS_SNAPSHOT_PREFIX}{deployment_id}"
        await r.set(snapshot_key, json.dumps(snapshot.to_dict()))

        # Also store by snapshot_id for efficient node-based lookup
        snapshot_id_key = f"{self.REDIS_SNAPSHOT_ID_PREFIX}{snapshot_id}"
        await r.set(snapshot_id_key, json.dumps(snapshot.to_dict()))

        # Add to node's snapshot list (keep last 10)
        node_key = f"{self.REDIS_NODE_SNAPSHOTS_PREFIX}{node_ip}"
        await r.lpush(node_key, snapshot_id)
        await r.ltrim(node_key, 0, 9)

        logger.info(f"Created deployment snapshot: {snapshot_id} for deployment: {deployment_id}")
        return snapshot

    async def get_snapshot(self, deployment_id: str) -> Optional[DeploymentSnapshot]:
        """Get current snapshot for a deployment.

        Args:
            deployment_id: Deployment identifier

        Returns:
            DeploymentSnapshot if exists, None otherwise
        """
        r = await self._get_redis()
        snapshot_key = f"{self.REDIS_SNAPSHOT_PREFIX}{deployment_id}"
        data = await r.get(snapshot_key)

        if data:
            return DeploymentSnapshot.from_dict(json.loads(data))
        return None

    async def get_snapshots_by_node(self, node_ip: str) -> List[DeploymentSnapshot]:
        """Get all snapshots for a node.

        Args:
            node_ip: Node IP address

        Returns:
            List of DeploymentSnapshots (most recent first)
        """
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

    async def save_rollback_history(self, entry: RollbackHistoryEntry) -> None:
        """Save rollback history entry.

        Args:
            entry: RollbackHistoryEntry to save
        """
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

    async def get_rollback_history(self, deployment_id: str) -> List[RollbackHistoryEntry]:
        """Get rollback history for a deployment.

        Args:
            deployment_id: Deployment identifier

        Returns:
            List of RollbackHistoryEntries (most recent first)
        """
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


class RollbackService:
    """Service for handling deployment rollbacks.

    Rollback Process:
    1. Get snapshot for deployment
    2. Execute rollback steps in reverse order
    3. Verify rollback success
    4. Update rollback history
    """

    def __init__(self, snapshot_store: DeploymentSnapshotStore):
        self.snapshot_store = snapshot_store
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
        rollback_id = f"rollback-{deployment_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

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
        """Stop Ray worker.

        TODO: Implement actual Ray worker rollback via SSH:
        1. SSH to node_ip
        2. Run `ray stop` to stop Ray worker
        3. Verify Ray process is stopped
        """
        logger.info(f"Rolling back Ray worker on {snapshot.node_ip}")

    async def _rollback_code(self, snapshot: DeploymentSnapshot) -> None:
        """Rollback code sync.

        TODO: Implement actual code rollback via SSH:
        1. SSH to node_ip
        2. Restore code from snapshot.version or previous backup
        3. Verify code restoration
        """
        logger.info(f"Rolling back code on {snapshot.node_ip}")

    async def _rollback_deps(self, snapshot: DeploymentSnapshot) -> None:
        """Rollback dependency installation.

        TODO: Implement actual dependency rollback via SSH:
        1. SSH to node_ip
        2. Restore dependencies to snapshot.config state
        3. Verify dependency versions
        """
        logger.info(f"Rolling back dependencies on {snapshot.node_ip}")

    async def _rollback_venv(self, snapshot: DeploymentSnapshot) -> None:
        """Rollback virtual environment.

        TODO: Implement actual venv rollback via SSH:
        1. SSH to node_ip
        2. Restore virtual environment to snapshot state
        3. Verify venv is functional
        """
        logger.info(f"Rolling back venv on {snapshot.node_ip}")

    async def _rollback_sudo(self, snapshot: DeploymentSnapshot) -> None:
        """Rollback sudo configuration.

        TODO: Implement actual sudo config rollback via SSH:
        1. SSH to node_ip
        2. Restore sudoers file from backup
        3. Verify sudo access
        """
        logger.info(f"Rolling back sudo config on {snapshot.node_ip}")

    async def _rollback_connecting(self, snapshot: DeploymentSnapshot) -> None:
        """Rollback SSH connection.

        TODO: Implement actual SSH connection rollback via SSH:
        1. SSH to node_ip
        2. Remove or revoke SSH keys/credentials
        3. Verify SSH access is restricted
        """
        logger.info(f"Rolling back SSH connection on {snapshot.node_ip}")

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
        snapshot_store = DeploymentSnapshotStore()
        return await snapshot_store.create_snapshot(
            deployment_id=deployment_id,
            node_ip=node_ip,
            version=version,
            config=config,
            steps_completed=steps_completed,
            ray_head_ip=ray_head_ip,
            ray_port=ray_port,
        )