# src/algo_studio/core/quota/store.py
"""Quota storage layer with optimistic locking support."""

import sqlite3
import redis
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from algo_studio.core.quota.exceptions import (
    OptimisticLockError,
    QuotaNotFoundError,
)


class QuotaScope:
    """Quota scope constants."""
    GLOBAL = "global"
    TEAM = "team"
    USER = "user"


class ResourceQuota:
    """Resource quota request/limit container."""

    def __init__(
        self,
        cpu_cores: int = 0,
        gpu_count: int = 0,
        gpu_memory_gb: float = 0.0,
        memory_gb: float = 0.0,
        disk_gb: float = 0.0,
        concurrent_tasks: int = 0,
        tasks_per_day: int = 0,
        gpu_hours_per_day: float = 0.0,
    ):
        self.cpu_cores = cpu_cores
        self.gpu_count = gpu_count
        self.gpu_memory_gb = gpu_memory_gb
        self.memory_gb = memory_gb
        self.disk_gb = disk_gb
        self.concurrent_tasks = concurrent_tasks
        self.tasks_per_day = tasks_per_day
        self.gpu_hours_per_day = gpu_hours_per_day

    def to_tuple(self) -> tuple:
        return (
            self.cpu_cores,
            self.gpu_count,
            self.gpu_memory_gb,
            self.memory_gb,
            self.disk_gb,
            self.concurrent_tasks,
        )


class QuotaStoreInterface(ABC):
    """Abstract interface for quota storage."""

    @abstractmethod
    def get_quota(self, quota_id: str) -> Optional[Dict[str, Any]]:
        """Get quota by ID."""
        pass

    @abstractmethod
    def get_quota_by_scope(self, scope: str, scope_id: str) -> Optional[Dict[str, Any]]:
        """Get quota by scope."""
        pass

    @abstractmethod
    def create_quota(self, quota_data: Dict[str, Any]) -> bool:
        """Create a new quota."""
        pass

    @abstractmethod
    def update_quota(self, quota_id: str, quota_data: Dict[str, Any]) -> bool:
        """Update an existing quota."""
        pass

    @abstractmethod
    def delete_quota(self, quota_id: str) -> bool:
        """Delete a quota."""
        pass

    @abstractmethod
    def get_usage(self, quota_id: str) -> Optional[Dict[str, Any]]:
        """Get current usage for a quota."""
        pass

    @abstractmethod
    def increment_usage(self, quota_id: str, resources: ResourceQuota, expected_version: int = None) -> bool:
        """Atomically increment usage with optimistic locking."""
        pass

    @abstractmethod
    def decrement_usage(self, quota_id: str, resources: ResourceQuota, expected_version: int = None) -> bool:
        """Atomically decrement usage (with floor at 0) and optional optimistic locking.

        Args:
            quota_id: The quota ID to decrement
            resources: Resources to subtract
            expected_version: If provided, use optimistic locking with this version

        Returns:
            True if decrement succeeded

        Raises:
            OptimisticLockError: If version mismatch occurs
        """
        pass

    @abstractmethod
    def get_all_usage(self) -> Dict[str, Dict[str, Any]]:
        """Get usage for all quotas."""
        pass

    @abstractmethod
    def get_bulk_usage(self, quota_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get usage for multiple quotas in one query."""
        pass

    @abstractmethod
    def list_quotas(self, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        """List quotas, optionally filtered by scope."""
        pass


class SQLiteQuotaStore(QuotaStoreInterface):
    """SQLite implementation of quota storage with optimistic locking.

    Uses WAL mode and version-based optimistic locking for concurrent safety.
    """

    def __init__(self, db_path: str = None):
        """Initialize SQLite quota store.

        Args:
            db_path: Path to SQLite database. Uses default if None.
        """
        if db_path is None:
            base_path = Path.home() / ".algo_studio"
            base_path.mkdir(exist_ok=True)
            db_path = str(base_path / "quota_store.db")

        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Enable WAL mode
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")

        # Quotas table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quotas (
                quota_id TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                name TEXT NOT NULL,
                cpu_cores INTEGER DEFAULT 0,
                gpu_count INTEGER DEFAULT 0,
                gpu_memory_gb REAL DEFAULT 0.0,
                memory_gb REAL DEFAULT 0.0,
                disk_gb REAL DEFAULT 0.0,
                concurrent_tasks INTEGER DEFAULT 0,
                tasks_per_day INTEGER DEFAULT 50,
                gpu_hours_per_day REAL DEFAULT 24.0,
                alert_threshold INTEGER DEFAULT 80,
                weight REAL DEFAULT 1.0,
                guaranteed_gpu_count INTEGER DEFAULT 0,
                guaranteed_cpu_cores INTEGER DEFAULT 0,
                guaranteed_memory_gb REAL DEFAULT 0.0,
                parent_quota_id TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Quota usages table with version for optimistic locking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quota_usages (
                quota_id TEXT PRIMARY KEY,
                cpu_cores_used REAL DEFAULT 0.0,
                gpu_count_used INTEGER DEFAULT 0,
                gpu_memory_gb_used REAL DEFAULT 0.0,
                memory_gb_used REAL DEFAULT 0.0,
                disk_gb_used REAL DEFAULT 0.0,
                concurrent_tasks_used INTEGER DEFAULT 0,
                tasks_today INTEGER DEFAULT 0,
                gpu_minutes_today REAL DEFAULT 0.0,
                version INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (quota_id) REFERENCES quotas(quota_id) ON DELETE CASCADE
            )
        """)

        # Index for scope queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_quotas_scope
            ON quotas(scope, scope_id)
        """)

        conn.commit()
        conn.close()

    @contextmanager
    def _transaction(self):
        """Context manager for transactions with immediate lock acquisition."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_quota(self, quota_id: str) -> Optional[Dict[str, Any]]:
        """Get quota by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM quotas WHERE quota_id = ?", (quota_id,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return self._row_to_quota(row)

    def get_quota_by_scope(self, scope: str, scope_id: str) -> Optional[Dict[str, Any]]:
        """Get quota by scope."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM quotas WHERE scope = ? AND scope_id = ? AND is_active = 1",
            (scope, scope_id)
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return self._row_to_quota(row)

    def _row_to_quota(self, row: tuple) -> Dict[str, Any]:
        """Convert a database row to a quota dictionary."""
        return {
            "quota_id": row[0],
            "scope": row[1],
            "scope_id": row[2],
            "name": row[3],
            "cpu_cores": row[4],
            "gpu_count": row[5],
            "gpu_memory_gb": row[6],
            "memory_gb": row[7],
            "disk_gb": row[8],
            "concurrent_tasks": row[9],
            "tasks_per_day": row[10],
            "gpu_hours_per_day": row[11],
            "alert_threshold": row[12],
            "weight": row[13] if len(row) > 13 else 1.0,
            "guaranteed_gpu_count": row[14] if len(row) > 14 else 0,
            "guaranteed_cpu_cores": row[15] if len(row) > 15 else 0,
            "guaranteed_memory_gb": row[16] if len(row) > 16 else 0.0,
            "parent_quota_id": row[17] if len(row) > 17 else None,
            "is_active": bool(row[18]) if len(row) > 18 else True,
            "created_at": row[19] if len(row) > 19 else None,
            "updated_at": row[20] if len(row) > 20 else None,
        }

    def create_quota(self, quota_data: Dict[str, Any]) -> bool:
        """Create a new quota."""
        with self._transaction() as cursor:
            cursor.execute("""
                INSERT INTO quotas (
                    quota_id, scope, scope_id, name,
                    cpu_cores, gpu_count, gpu_memory_gb, memory_gb, disk_gb,
                    concurrent_tasks, tasks_per_day, gpu_hours_per_day,
                    alert_threshold, weight, guaranteed_gpu_count,
                    guaranteed_cpu_cores, guaranteed_memory_gb,
                    parent_quota_id, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                quota_data["quota_id"],
                quota_data["scope"],
                quota_data["scope_id"],
                quota_data["name"],
                quota_data.get("cpu_cores", 0),
                quota_data.get("gpu_count", 0),
                quota_data.get("gpu_memory_gb", 0.0),
                quota_data.get("memory_gb", 0.0),
                quota_data.get("disk_gb", 0.0),
                quota_data.get("concurrent_tasks", 0),
                quota_data.get("tasks_per_day", 50),
                quota_data.get("gpu_hours_per_day", 24.0),
                quota_data.get("alert_threshold", 80),
                quota_data.get("weight", 1.0),
                quota_data.get("guaranteed_gpu_count", 0),
                quota_data.get("guaranteed_cpu_cores", 0),
                quota_data.get("guaranteed_memory_gb", 0.0),
                quota_data.get("parent_quota_id"),
                1 if quota_data.get("is_active", True) else 0,
            ))

            # Create usage record with version 0
            cursor.execute("""
                INSERT INTO quota_usages (quota_id, version)
                VALUES (?, 0)
            """, (quota_data["quota_id"],))

        return True

    def update_quota(self, quota_id: str, quota_data: Dict[str, Any]) -> bool:
        """Update an existing quota."""
        with self._transaction() as cursor:
            cursor.execute("""
                UPDATE quotas SET
                    name = COALESCE(?, name),
                    cpu_cores = COALESCE(?, cpu_cores),
                    gpu_count = COALESCE(?, gpu_count),
                    gpu_memory_gb = COALESCE(?, gpu_memory_gb),
                    memory_gb = COALESCE(?, memory_gb),
                    disk_gb = COALESCE(?, disk_gb),
                    concurrent_tasks = COALESCE(?, concurrent_tasks),
                    tasks_per_day = COALESCE(?, tasks_per_day),
                    gpu_hours_per_day = COALESCE(?, gpu_hours_per_day),
                    alert_threshold = COALESCE(?, alert_threshold),
                    parent_quota_id = COALESCE(?, parent_quota_id),
                    is_active = COALESCE(?, is_active),
                    updated_at = CURRENT_TIMESTAMP
                WHERE quota_id = ?
            """, (
                quota_data.get("name"),
                quota_data.get("cpu_cores"),
                quota_data.get("gpu_count"),
                quota_data.get("gpu_memory_gb"),
                quota_data.get("memory_gb"),
                quota_data.get("disk_gb"),
                quota_data.get("concurrent_tasks"),
                quota_data.get("tasks_per_day"),
                quota_data.get("gpu_hours_per_day"),
                quota_data.get("alert_threshold"),
                quota_data.get("parent_quota_id"),
                1 if quota_data.get("is_active") else 0 if quota_data.get("is_active") is not None else None,
                quota_id,
            ))
            return cursor.rowcount > 0

    def delete_quota(self, quota_id: str) -> bool:
        """Delete a quota."""
        with self._transaction() as cursor:
            cursor.execute("DELETE FROM quotas WHERE quota_id = ?", (quota_id,))
            return cursor.rowcount > 0

    def get_usage(self, quota_id: str) -> Optional[Dict[str, Any]]:
        """Get current usage for a quota."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM quota_usages WHERE quota_id = ?", (quota_id,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return {
            "quota_id": row[0],
            "cpu_cores_used": row[1],
            "gpu_count_used": row[2],
            "gpu_memory_gb_used": row[3],
            "memory_gb_used": row[4],
            "disk_gb_used": row[5],
            "concurrent_tasks_used": row[6],
            "tasks_today": row[7],
            "gpu_minutes_today": row[8],
            "version": row[9],
            "updated_at": row[10],
        }

    def increment_usage(
        self, quota_id: str, resources: ResourceQuota, expected_version: int = None
    ) -> bool:
        """Atomically increment usage with optimistic locking.

        Args:
            quota_id: The quota ID to increment
            resources: Resources to add
            expected_version: If provided, use optimistic locking with this version

        Returns:
            True if increment succeeded

        Raises:
            OptimisticLockError: If version mismatch occurs
        """
        with self._transaction() as cursor:
            # Get current version
            cursor.execute(
                "SELECT version FROM quota_usages WHERE quota_id = ?",
                (quota_id,)
            )
            row = cursor.fetchone()
            if row is None:
                raise QuotaNotFoundError(f"Quota usage not found: {quota_id}", quota_id=quota_id)

            current_version = row[0]

            # Check optimistic lock if version provided
            if expected_version is not None and current_version != expected_version:
                raise OptimisticLockError(
                    f"Version mismatch for quota {quota_id}",
                    quota_id=quota_id,
                    expected_version=expected_version,
                    actual_version=current_version,
                )

            # Atomic increment with version check
            if expected_version is not None:
                # Full optimistic lock: UPDATE ... WHERE version = expected_version
                cursor.execute("""
                    UPDATE quota_usages
                    SET cpu_cores_used = cpu_cores_used + ?,
                        gpu_count_used = gpu_count_used + ?,
                        gpu_memory_gb_used = gpu_memory_gb_used + ?,
                        memory_gb_used = memory_gb_used + ?,
                        disk_gb_used = disk_gb_used + ?,
                        concurrent_tasks_used = concurrent_tasks_used + ?,
                        version = version + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE quota_id = ? AND version = ?
                """, (
                    resources.cpu_cores,
                    resources.gpu_count,
                    resources.gpu_memory_gb,
                    resources.memory_gb,
                    resources.disk_gb,
                    resources.concurrent_tasks,
                    quota_id,
                    expected_version,
                ))
            else:
                # No version check - just increment (for backward compatibility)
                cursor.execute("""
                    UPDATE quota_usages
                    SET cpu_cores_used = cpu_cores_used + ?,
                        gpu_count_used = gpu_count_used + ?,
                        gpu_memory_gb_used = gpu_memory_gb_used + ?,
                        memory_gb_used = memory_gb_used + ?,
                        disk_gb_used = disk_gb_used + ?,
                        concurrent_tasks_used = concurrent_tasks_used + ?,
                        version = version + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE quota_id = ?
                """, (
                    resources.cpu_cores,
                    resources.gpu_count,
                    resources.gpu_memory_gb,
                    resources.memory_gb,
                    resources.disk_gb,
                    resources.concurrent_tasks,
                    quota_id,
                ))

            if cursor.rowcount == 0:
                # This shouldn't happen with expected_version=None, but possible with version mismatch
                raise OptimisticLockError(
                    f"Failed to update quota {quota_id} - version mismatch",
                    quota_id=quota_id,
                )

            return True

    def decrement_usage(
        self, quota_id: str, resources: ResourceQuota, expected_version: int = None
    ) -> bool:
        """Atomically decrement usage (with floor at 0) and optional optimistic locking.

        Args:
            quota_id: The quota ID to decrement
            resources: Resources to subtract
            expected_version: If provided, use optimistic locking with this version

        Returns:
            True if decrement succeeded

        Raises:
            OptimisticLockError: If version mismatch occurs
            QuotaNotFoundError: If quota usage not found
        """
        with self._transaction() as cursor:
            # Get current version
            cursor.execute(
                "SELECT version FROM quota_usages WHERE quota_id = ?",
                (quota_id,)
            )
            row = cursor.fetchone()
            if row is None:
                raise QuotaNotFoundError(f"Quota usage not found: {quota_id}", quota_id=quota_id)

            current_version = row[0]

            # Check optimistic lock if version provided
            if expected_version is not None and current_version != expected_version:
                raise OptimisticLockError(
                    f"Version mismatch for quota {quota_id}",
                    quota_id=quota_id,
                    expected_version=expected_version,
                    actual_version=current_version,
                )

            # Atomic decrement with version check
            if expected_version is not None:
                # Full optimistic lock: UPDATE ... WHERE version = expected_version
                cursor.execute("""
                    UPDATE quota_usages
                    SET cpu_cores_used = MAX(0, cpu_cores_used - ?),
                        gpu_count_used = MAX(0, gpu_count_used - ?),
                        gpu_memory_gb_used = MAX(0, gpu_memory_gb_used - ?),
                        memory_gb_used = MAX(0, memory_gb_used - ?),
                        disk_gb_used = MAX(0, disk_gb_used - ?),
                        concurrent_tasks_used = MAX(0, concurrent_tasks_used - ?),
                        version = version + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE quota_id = ? AND version = ?
                """, (
                    resources.cpu_cores,
                    resources.gpu_count,
                    resources.gpu_memory_gb,
                    resources.memory_gb,
                    resources.disk_gb,
                    resources.concurrent_tasks,
                    quota_id,
                    expected_version,
                ))
            else:
                # No version check - just decrement (for backward compatibility)
                cursor.execute("""
                    UPDATE quota_usages
                    SET cpu_cores_used = MAX(0, cpu_cores_used - ?),
                        gpu_count_used = MAX(0, gpu_count_used - ?),
                        gpu_memory_gb_used = MAX(0, gpu_memory_gb_used - ?),
                        memory_gb_used = MAX(0, memory_gb_used - ?),
                        disk_gb_used = MAX(0, disk_gb_used - ?),
                        concurrent_tasks_used = MAX(0, concurrent_tasks_used - ?),
                        version = version + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE quota_id = ?
                """, (
                    resources.cpu_cores,
                    resources.gpu_count,
                    resources.gpu_memory_gb,
                    resources.memory_gb,
                    resources.disk_gb,
                    resources.concurrent_tasks,
                    quota_id,
                ))

            if cursor.rowcount == 0:
                raise OptimisticLockError(
                    f"Failed to update quota {quota_id} - version mismatch",
                    quota_id=quota_id,
                )

            return True

    def get_all_usage(self) -> Dict[str, Dict[str, Any]]:
        """Get usage for all quotas."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM quota_usages")
        rows = cursor.fetchall()
        conn.close()

        result = {}
        for row in rows:
            result[row[0]] = {
                "quota_id": row[0],
                "cpu_cores_used": row[1],
                "gpu_count_used": row[2],
                "gpu_memory_gb_used": row[3],
                "memory_gb_used": row[4],
                "disk_gb_used": row[5],
                "concurrent_tasks_used": row[6],
                "tasks_today": row[7],
                "gpu_minutes_today": row[8],
                "version": row[9],
                "updated_at": row[10],
            }
        return result

    def get_bulk_usage(self, quota_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get usage for multiple quotas in one query (for performance)."""
        if not quota_ids:
            return {}

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        placeholders = ",".join("?" * len(quota_ids))
        cursor.execute(f"SELECT * FROM quota_usages WHERE quota_id IN ({placeholders})", quota_ids)
        rows = cursor.fetchall()
        conn.close()

        result = {}
        for row in rows:
            result[row[0]] = {
                "quota_id": row[0],
                "cpu_cores_used": row[1],
                "gpu_count_used": row[2],
                "gpu_memory_gb_used": row[3],
                "memory_gb_used": row[4],
                "disk_gb_used": row[5],
                "concurrent_tasks_used": row[6],
                "tasks_today": row[7],
                "gpu_minutes_today": row[8],
                "version": row[9],
                "updated_at": row[10],
            }
        return result

    def list_quotas(self, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        """List quotas, optionally filtered by scope."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if scope:
            cursor.execute(
                "SELECT * FROM quotas WHERE scope = ? AND is_active = 1",
                (scope,)
            )
        else:
            cursor.execute("SELECT * FROM quotas WHERE is_active = 1")

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_quota(row) for row in rows]

    def get_quota_inheritance_chain(self, quota_id: str) -> List[str]:
        """Get the inheritance chain from this quota up to root.

        Returns list of quota_ids from this quota to root (global).
        """
        chain = []
        current_id = quota_id

        while current_id:
            quota = self.get_quota(current_id)
            if quota is None:
                break
            chain.append(current_id)
            current_id = quota.get("parent_quota_id")

        return chain

    def validate_inheritance_chain(self, quota_id: str) -> tuple[bool, List[str]]:
        """Validate that inheritance chain is valid (no cycles, all exist).

        Returns:
            (is_valid, error_chain) - error_chain is empty if valid
        """
        errors = []
        visited = set()
        current_id = quota_id

        while current_id:
            if current_id in visited:
                errors.append(f"Cycle detected: {current_id} appears twice in chain")
                return False, errors

            visited.add(current_id)
            quota = self.get_quota(current_id)

            if quota is None:
                errors.append(f"Quota not found: {current_id}")
                return False, errors

            # Check that parent exists if specified
            parent_id = quota.get("parent_quota_id")
            if parent_id:
                parent_quota = self.get_quota(parent_id)
                if parent_quota is None:
                    errors.append(f"Parent quota not found: {parent_id}")
                    return False, errors

            current_id = parent_id

        return True, []


class RedisQuotaStore(QuotaStoreInterface):
    """Redis implementation of quota storage with optimistic locking.

    Uses Redis hashes for quota/usage data and version-based optimistic locking.
    Suitable for distributed multi-node Ray clusters.
    """

    # Redis key prefixes
    QUOTA_KEY_PREFIX = "quota:"
    USAGE_KEY_PREFIX = "usage:"
    SCOPE_INDEX_KEY = "quota:scope_index"

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6380):
        """Initialize Redis quota store.

        Args:
            redis_host: Redis server host
            redis_port: Redis server port
        """
        import redis
        self._redis_host = redis_host
        self._redis_port = redis_port
        self._redis: Optional[redis.Redis] = None

    def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        import redis
        if self._redis is None:
            self._redis = redis.Redis(
                host=self._redis_host,
                port=self._redis_port,
                decode_responses=True,
            )
        return self._redis

    def _quota_key(self, quota_id: str) -> str:
        """Get Redis key for quota data."""
        return f"{self.QUOTA_KEY_PREFIX}{quota_id}"

    def _usage_key(self, quota_id: str) -> str:
        """Get Redis key for usage data."""
        return f"{self.USAGE_KEY_PREFIX}{quota_id}"

    def _scope_key(self, scope: str, scope_id: str) -> str:
        """Get quota_id by scope."""
        return f"{self.SCOPE_INDEX_KEY}:{scope}:{scope_id}"

    def get_quota(self, quota_id: str) -> Optional[Dict[str, Any]]:
        """Get quota by ID."""
        r = self._get_redis()
        data = r.hgetall(self._quota_key(quota_id))
        if not data:
            return None

        return {
            "quota_id": quota_id,
            "scope": data.get("scope"),
            "scope_id": data.get("scope_id"),
            "name": data.get("name"),
            "cpu_cores": int(data.get("cpu_cores", 0)),
            "gpu_count": int(data.get("gpu_count", 0)),
            "gpu_memory_gb": float(data.get("gpu_memory_gb", 0.0)),
            "memory_gb": float(data.get("memory_gb", 0.0)),
            "disk_gb": float(data.get("disk_gb", 0.0)),
            "concurrent_tasks": int(data.get("concurrent_tasks", 0)),
            "tasks_per_day": int(data.get("tasks_per_day", 50)),
            "gpu_hours_per_day": float(data.get("gpu_hours_per_day", 24.0)),
            "alert_threshold": int(data.get("alert_threshold", 80)),
            "parent_quota_id": data.get("parent_quota_id") or None,
            "is_active": bool(int(data.get("is_active", 1))),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        }

    def get_quota_by_scope(self, scope: str, scope_id: str) -> Optional[Dict[str, Any]]:
        """Get quota by scope."""
        r = self._get_redis()
        quota_id = r.get(self._scope_key(scope, scope_id))
        if quota_id:
            return self.get_quota(quota_id)
        return None

    def create_quota(self, quota_data: Dict[str, Any]) -> bool:
        """Create a new quota."""
        r = self._get_redis()
        quota_id = quota_data["quota_id"]
        scope = quota_data["scope"]
        scope_id = quota_data["scope_id"]

        # Check if scope already exists
        if r.exists(self._scope_key(scope, scope_id)):
            return False

        from datetime import datetime
        now = datetime.utcnow().isoformat()

        # Store quota data
        quota_key = self._quota_key(quota_id)
        r.hset(quota_key, mapping={
            "scope": scope,
            "scope_id": scope_id,
            "name": quota_data["name"],
            "cpu_cores": quota_data.get("cpu_cores", 0),
            "gpu_count": quota_data.get("gpu_count", 0),
            "gpu_memory_gb": quota_data.get("gpu_memory_gb", 0.0),
            "memory_gb": quota_data.get("memory_gb", 0.0),
            "disk_gb": quota_data.get("disk_gb", 0.0),
            "concurrent_tasks": quota_data.get("concurrent_tasks", 0),
            "tasks_per_day": quota_data.get("tasks_per_day", 50),
            "gpu_hours_per_day": quota_data.get("gpu_hours_per_day", 24.0),
            "alert_threshold": quota_data.get("alert_threshold", 80),
            "parent_quota_id": quota_data.get("parent_quota_id") or "",
            "is_active": 1 if quota_data.get("is_active", True) else 0,
            "weight": quota_data.get("weight", 1.0),
            "guaranteed_gpu_count": quota_data.get("guaranteed_gpu_count", 0),
            "guaranteed_cpu_cores": quota_data.get("guaranteed_cpu_cores", 0),
            "guaranteed_memory_gb": quota_data.get("guaranteed_memory_gb", 0.0),
            "created_at": now,
            "updated_at": now,
        })

        # Create usage record with version 0
        usage_key = self._usage_key(quota_id)
        r.hset(usage_key, mapping={
            "cpu_cores_used": 0.0,
            "gpu_count_used": 0,
            "gpu_memory_gb_used": 0.0,
            "memory_gb_used": 0.0,
            "disk_gb_used": 0.0,
            "concurrent_tasks_used": 0,
            "tasks_today": 0,
            "gpu_minutes_today": 0.0,
            "version": 0,
            "updated_at": now,
        })

        # Index by scope
        r.set(self._scope_key(scope, scope_id), quota_id)

        return True

    def update_quota(self, quota_id: str, quota_data: Dict[str, Any]) -> bool:
        """Update an existing quota."""
        r = self._get_redis()
        quota_key = self._quota_key(quota_id)

        if not r.exists(quota_key):
            return False

        # Build update mapping
        updates = {}
        for key in ["name", "cpu_cores", "gpu_count", "gpu_memory_gb", "memory_gb",
                    "disk_gb", "concurrent_tasks", "tasks_per_day", "gpu_hours_per_day",
                    "alert_threshold", "parent_quota_id"]:
            if key in quota_data:
                updates[key] = quota_data[key]

        if "is_active" in quota_data:
            updates["is_active"] = 1 if quota_data["is_active"] else 0

        if updates:
            from datetime import datetime
            updates["updated_at"] = datetime.utcnow().isoformat()
            r.hset(quota_key, mapping=updates)

        return True

    def delete_quota(self, quota_id: str) -> bool:
        """Delete a quota."""
        r = self._get_redis()
        quota_key = self._quota_key(quota_id)

        # Get scope info first
        data = r.hgetall(quota_key)
        if not data:
            return False

        # Delete scope index
        scope_key = self._scope_key(data.get("scope", ""), data.get("scope_id", ""))
        r.delete(scope_key)

        # Delete quota and usage
        r.delete(quota_key)
        r.delete(self._usage_key(quota_id))

        return True

    def get_usage(self, quota_id: str) -> Optional[Dict[str, Any]]:
        """Get current usage for a quota."""
        r = self._get_redis()
        data = r.hgetall(self._usage_key(quota_id))

        if not data:
            return None

        return {
            "quota_id": quota_id,
            "cpu_cores_used": float(data.get("cpu_cores_used", 0.0)),
            "gpu_count_used": int(data.get("gpu_count_used", 0)),
            "gpu_memory_gb_used": float(data.get("gpu_memory_gb_used", 0.0)),
            "memory_gb_used": float(data.get("memory_gb_used", 0.0)),
            "disk_gb_used": float(data.get("disk_gb_used", 0.0)),
            "concurrent_tasks_used": int(data.get("concurrent_tasks_used", 0)),
            "tasks_today": int(data.get("tasks_today", 0)),
            "gpu_minutes_today": float(data.get("gpu_minutes_today", 0.0)),
            "version": int(data.get("version", 0)),
            "updated_at": data.get("updated_at"),
        }

    def increment_usage(
        self, quota_id: str, resources: ResourceQuota, expected_version: int = None
    ) -> bool:
        """Atomically increment usage with optimistic locking.

        Args:
            quota_id: The quota ID to increment
            resources: Resources to add
            expected_version: If provided, use optimistic locking with this version

        Returns:
            True if increment succeeded

        Raises:
            OptimisticLockError: If version mismatch occurs
            QuotaNotFoundError: If quota usage not found
        """
        r = self._get_redis()
        usage_key = self._usage_key(quota_id)

        # Get current version
        current_version = r.hget(usage_key, "version")
        if current_version is None:
            raise QuotaNotFoundError(f"Quota usage not found: {quota_id}", quota_id=quota_id)

        current_version = int(current_version)

        # Check optimistic lock if version provided
        if expected_version is not None and current_version != expected_version:
            raise OptimisticLockError(
                f"Version mismatch for quota {quota_id}",
                quota_id=quota_id,
                expected_version=expected_version,
                actual_version=current_version,
            )

        # Atomic increment using Lua script for check-and-set
        lua_script = """
        local usage_key = KEYS[1]
        local expected_version = ARGV[1]
        local cpu_cores = ARGV[2]
        local gpu_count = ARGV[3]
        local gpu_memory_gb = ARGV[4]
        local memory_gb = ARGV[5]
        local disk_gb = ARGV[6]
        local concurrent_tasks = ARGV[7]
        local new_version = ARGV[8]

        -- If expected_version is provided, check it
        if expected_version ~= "" then
            local current_ver = tonumber(redis.call("HGET", usage_key, "version"))
            if current_ver ~= tonumber(expected_version) then
                return -1  -- Version mismatch
            end
        end

        -- Perform increment
        redis.call("HINCRBYFLOAT", usage_key, "cpu_cores_used", cpu_cores)
        redis.call("HINCRBY", usage_key, "gpu_count_used", gpu_count)
        redis.call("HINCRBYFLOAT", usage_key, "gpu_memory_gb_used", gpu_memory_gb)
        redis.call("HINCRBYFLOAT", usage_key, "memory_gb_used", memory_gb)
        redis.call("HINCRBYFLOAT", usage_key, "disk_gb_used", disk_gb)
        redis.call("HINCRBY", usage_key, "concurrent_tasks_used", concurrent_tasks)
        redis.call("HINCRBY", usage_key, "version", 1)
        redis.call("HSET", usage_key, "updated_at", ARGV[9])

        return 1  -- Success
        """

        from datetime import datetime
        now = datetime.utcnow().isoformat()

        result = r.eval(
            lua_script,
            1,
            usage_key,
            expected_version if expected_version is not None else "",
            resources.cpu_cores,
            resources.gpu_count,
            resources.gpu_memory_gb,
            resources.memory_gb,
            resources.disk_gb,
            resources.concurrent_tasks,
            current_version + 1,
            now,
        )

        if result == -1:
            raise OptimisticLockError(
                f"Version mismatch for quota {quota_id}",
                quota_id=quota_id,
                expected_version=expected_version,
                actual_version=current_version,
            )

        return True

    def decrement_usage(
        self, quota_id: str, resources: ResourceQuota, expected_version: int = None
    ) -> bool:
        """Atomically decrement usage (with floor at 0) and optional optimistic locking.

        Args:
            quota_id: The quota ID to decrement
            resources: Resources to subtract
            expected_version: If provided, use optimistic locking with this version

        Returns:
            True if decrement succeeded

        Raises:
            OptimisticLockError: If version mismatch occurs
            QuotaNotFoundError: If quota usage not found
        """
        r = self._get_redis()
        usage_key = self._usage_key(quota_id)

        # Get current version
        current_version = r.hget(usage_key, "version")
        if current_version is None:
            raise QuotaNotFoundError(f"Quota usage not found: {quota_id}", quota_id=quota_id)

        current_version = int(current_version)

        # Check optimistic lock if version provided
        if expected_version is not None and current_version != expected_version:
            raise OptimisticLockError(
                f"Version mismatch for quota {quota_id}",
                quota_id=quota_id,
                expected_version=expected_version,
                actual_version=current_version,
            )

        # Atomic decrement using Lua script
        lua_script = """
        local usage_key = KEYS[1]
        local expected_version = ARGV[1]
        local cpu_cores = ARGV[2]
        local gpu_count = ARGV[3]
        local gpu_memory_gb = ARGV[4]
        local memory_gb = ARGV[5]
        local disk_gb = ARGV[6]
        local concurrent_tasks = ARGV[7]
        local new_version = ARGV[8]

        -- If expected_version is provided, check it
        if expected_version ~= "" then
            local current_ver = tonumber(redis.call("HGET", usage_key, "version"))
            if current_ver ~= tonumber(expected_version) then
                return -1  -- Version mismatch
            end
        end

        -- Perform decrement with floor at 0
        local current_cpu = tonumber(redis.call("HGET", usage_key, "cpu_cores_used") or 0)
        local current_gpu = tonumber(redis.call("HGET", usage_key, "gpu_count_used") or 0)
        local current_gpu_mem = tonumber(redis.call("HGET", usage_key, "gpu_memory_gb_used") or 0)
        local current_mem = tonumber(redis.call("HGET", usage_key, "memory_gb_used") or 0)
        local current_disk = tonumber(redis.call("HGET", usage_key, "disk_gb_used") or 0)
        local current_tasks = tonumber(redis.call("HGET", usage_key, "concurrent_tasks_used") or 0)

        local new_cpu = math.max(0, current_cpu - tonumber(cpu_cores))
        local new_gpu = math.max(0, current_gpu - tonumber(gpu_count))
        local new_gpu_mem = math.max(0, current_gpu_mem - tonumber(gpu_memory_gb))
        local new_mem = math.max(0, current_mem - tonumber(memory_gb))
        local new_disk = math.max(0, current_disk - tonumber(disk_gb))
        local new_tasks = math.max(0, current_tasks - tonumber(concurrent_tasks))

        redis.call("HSET", usage_key, "cpu_cores_used", new_cpu)
        redis.call("HSET", usage_key, "gpu_count_used", new_gpu)
        redis.call("HSET", usage_key, "gpu_memory_gb_used", new_gpu_mem)
        redis.call("HSET", usage_key, "memory_gb_used", new_mem)
        redis.call("HSET", usage_key, "disk_gb_used", new_disk)
        redis.call("HSET", usage_key, "concurrent_tasks_used", new_tasks)
        redis.call("HINCRBY", usage_key, "version", 1)
        redis.call("HSET", usage_key, "updated_at", ARGV[9])

        return 1  -- Success
        """

        from datetime import datetime
        now = datetime.utcnow().isoformat()

        result = r.eval(
            lua_script,
            1,
            usage_key,
            expected_version if expected_version is not None else "",
            resources.cpu_cores,
            resources.gpu_count,
            resources.gpu_memory_gb,
            resources.memory_gb,
            resources.disk_gb,
            resources.concurrent_tasks,
            current_version + 1,
            now,
        )

        if result == -1:
            raise OptimisticLockError(
                f"Version mismatch for quota {quota_id}",
                quota_id=quota_id,
                expected_version=expected_version,
                actual_version=current_version,
            )

        return True

    def get_all_usage(self) -> Dict[str, Dict[str, Any]]:
        """Get usage for all quotas."""
        r = self._get_redis()
        keys = r.keys(f"{self.USAGE_KEY_PREFIX}*")

        result = {}
        for key in keys:
            quota_id = key.replace(self.USAGE_KEY_PREFIX, "")
            data = r.hgetall(key)
            if data:
                result[quota_id] = {
                    "quota_id": quota_id,
                    "cpu_cores_used": float(data.get("cpu_cores_used", 0.0)),
                    "gpu_count_used": int(data.get("gpu_count_used", 0)),
                    "gpu_memory_gb_used": float(data.get("gpu_memory_gb_used", 0.0)),
                    "memory_gb_used": float(data.get("memory_gb_used", 0.0)),
                    "disk_gb_used": float(data.get("disk_gb_used", 0.0)),
                    "concurrent_tasks_used": int(data.get("concurrent_tasks_used", 0)),
                    "tasks_today": int(data.get("tasks_today", 0)),
                    "gpu_minutes_today": float(data.get("gpu_minutes_today", 0.0)),
                    "version": int(data.get("version", 0)),
                    "updated_at": data.get("updated_at"),
                }

        return result

    def get_bulk_usage(self, quota_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get usage for multiple quotas in one query."""
        if not quota_ids:
            return {}

        r = self._get_redis()
        pipeline = r.pipeline()

        for quota_id in quota_ids:
            pipeline.hgetall(self._usage_key(quota_id))

        results = pipeline.execute()

        result = {}
        for quota_id, data in zip(quota_ids, results):
            if data:
                result[quota_id] = {
                    "quota_id": quota_id,
                    "cpu_cores_used": float(data.get("cpu_cores_used", 0.0)),
                    "gpu_count_used": int(data.get("gpu_count_used", 0)),
                    "gpu_memory_gb_used": float(data.get("gpu_memory_gb_used", 0.0)),
                    "memory_gb_used": float(data.get("memory_gb_used", 0.0)),
                    "disk_gb_used": float(data.get("disk_gb_used", 0.0)),
                    "concurrent_tasks_used": int(data.get("concurrent_tasks_used", 0)),
                    "tasks_today": int(data.get("tasks_today", 0)),
                    "gpu_minutes_today": float(data.get("gpu_minutes_today", 0.0)),
                    "version": int(data.get("version", 0)),
                    "updated_at": data.get("updated_at"),
                }

        return result

    def list_quotas(self, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        """List quotas, optionally filtered by scope."""
        r = self._get_redis()
        quota_keys = r.keys(f"{self.QUOTA_KEY_PREFIX}*")

        result = []
        for key in quota_keys:
            quota_id = key.replace(self.QUOTA_KEY_PREFIX, "")
            quota = self.get_quota(quota_id)
            if quota and quota.get("is_active"):
                if scope is None or quota.get("scope") == scope:
                    result.append(quota)

        return result

    def get_quota_inheritance_chain(self, quota_id: str) -> List[str]:
        """Get the inheritance chain from this quota up to root."""
        chain = []
        current_id = quota_id

        while current_id:
            quota = self.get_quota(current_id)
            if quota is None:
                break
            chain.append(current_id)
            current_id = quota.get("parent_quota_id")

        return chain

    def validate_inheritance_chain(self, quota_id: str) -> tuple[bool, List[str]]:
        """Validate that inheritance chain is valid (no cycles, all exist)."""
        errors = []
        visited = set()
        current_id = quota_id

        while current_id:
            if current_id in visited:
                errors.append(f"Cycle detected: {current_id} appears twice in chain")
                return False, errors

            visited.add(current_id)
            quota = self.get_quota(current_id)

            if quota is None:
                errors.append(f"Quota not found: {current_id}")
                return False, errors

            parent_id = quota.get("parent_quota_id")
            if parent_id:
                parent_quota = self.get_quota(parent_id)
                if parent_quota is None:
                    errors.append(f"Parent quota not found: {parent_id}")
                    return False, errors

            current_id = parent_id

        return True, []

