"""
SQLiteMemoryStore - SQLite-based memory layer implementation
"""

import json
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from algo_studio.core.scheduler.profiles.task_profile import TaskType
from algo_studio.core.scheduler.profiles.scheduling_decision import SchedulingDecision
from algo_studio.core.scheduler.memory.base import (
    MemoryLayerInterface,
    NodeCharacteristics,
    TaskOutcome,
)


class SQLiteMemoryStore(MemoryLayerInterface):
    """
    SQLite-based memory store for scheduling history.

    Stores:
    - Scheduling decisions
    - Task outcomes
    - Node characteristics
    - Cached decisions
    """

    def __init__(self, db_path: str = None):
        """
        Initialize SQLite memory store.

        Args:
            db_path: Path to SQLite database. Uses default if None.
        """
        if db_path is None:
            # Default path in algo_studio data directory
            base_path = Path.home() / ".algo_studio"
            base_path.mkdir(exist_ok=True)
            db_path = str(base_path / "scheduler_memory.db")

        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Node characteristics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS node_characteristics (
                node_id TEXT PRIMARY KEY,
                hostname TEXT,
                ip TEXT,
                total_tasks INTEGER DEFAULT 0,
                success_tasks INTEGER DEFAULT 0,
                failure_tasks INTEGER DEFAULT 0,
                avg_gpu_utilization REAL DEFAULT 0.0,
                avg_memory_usage REAL DEFAULT 0.0,
                avg_task_duration_minutes REAL DEFAULT 0.0,
                train_success_rate REAL DEFAULT 0.0,
                infer_success_rate REAL DEFAULT 0.0,
                verify_success_rate REAL DEFAULT 0.0,
                last_heartbeat TEXT,
                consecutive_failures INTEGER DEFAULT 0,
                is_healthy INTEGER DEFAULT 1
            )
        """)

        # Scheduling records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduling_records (
                record_id TEXT PRIMARY KEY,
                decision_json TEXT,
                outcome_json TEXT,
                created_at TEXT
            )
        """)

        # Decision cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_cache (
                task_profile_hash TEXT PRIMARY KEY,
                decision_json TEXT,
                created_at TEXT,
                expires_at TEXT
            )
        """)

        conn.commit()
        conn.close()

    def record_decision(
        self,
        decision: SchedulingDecision,
        outcome: TaskOutcome,
    ) -> None:
        """
        Record scheduling decision and outcome.

        Args:
            decision: Scheduling decision
            outcome: Task execution outcome
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Update node characteristics
            if decision.selected_node:
                node = decision.selected_node
                self._update_node_characteristics(
                    cursor,
                    node.node_id,
                    node.hostname,
                    node.ip,
                    outcome,
                )

            # Record scheduling decision
            cursor.execute(
                """
                INSERT INTO scheduling_records
                (record_id, decision_json, outcome_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    decision.decision_id,
                    json.dumps(decision.to_dict()),
                    json.dumps({
                        "task_id": outcome.task_id,
                        "success": outcome.success,
                        "duration_minutes": outcome.duration_minutes,
                        "error": outcome.error,
                    }),
                    datetime.now().isoformat(),
                ),
            )

            conn.commit()
        finally:
            conn.close()

    def _update_node_characteristics(
        self,
        cursor: sqlite3.Cursor,
        node_id: str,
        hostname: str,
        ip: str,
        outcome: TaskOutcome,
    ):
        """Update node characteristics with new outcome"""
        # Get existing characteristics
        cursor.execute(
            "SELECT * FROM node_characteristics WHERE node_id = ?",
            (node_id,)
        )
        row = cursor.fetchone()

        if row:
            # Update existing
            total = row[3] + 1
            success = row[4] + (1 if outcome.success else 0)
            failure = row[5] + (0 if outcome.success else 1)

            cursor.execute(
                """
                UPDATE node_characteristics SET
                    total_tasks = ?,
                    success_tasks = ?,
                    failure_tasks = ?,
                    consecutive_failures = ?,
                    is_healthy = ?
                WHERE node_id = ?
                """,
                (
                    total,
                    success,
                    failure,
                    0 if outcome.success else row[13] + 1,
                    1 if outcome.success or row[13] < 3 else 0,
                    node_id,
                ),
            )
        else:
            # Insert new
            cursor.execute(
                """
                INSERT INTO node_characteristics
                (node_id, hostname, ip, total_tasks, success_tasks, failure_tasks,
                 consecutive_failures, is_healthy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    hostname,
                    ip,
                    1,
                    1 if outcome.success else 0,
                    0 if outcome.success else 1,
                    0 if outcome.success else 1,
                    1 if outcome.success else 0,
                ),
            )

    def get_node_characteristics(self, node_id: str) -> Optional[NodeCharacteristics]:
        """
        Get node characteristics.

        Args:
            node_id: Node ID

        Returns:
            NodeCharacteristics if found, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM node_characteristics WHERE node_id = ?",
            (node_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return NodeCharacteristics(
            node_id=row[0],
            hostname=row[1],
            ip=row[2],
            total_tasks=row[3],
            success_tasks=row[4],
            failure_tasks=row[5],
            avg_gpu_utilization=row[6],
            avg_memory_usage=row[7],
            avg_task_duration_minutes=row[8],
            train_success_rate=row[9],
            infer_success_rate=row[10],
            verify_success_rate=row[11],
            last_heartbeat=datetime.fromisoformat(row[12]) if row[12] else None,
            consecutive_failures=row[13],
            is_healthy=bool(row[14]),
        )

    def get_success_rate(self, task_type: TaskType, node_id: str) -> float:
        """
        Get success rate for task type on node.

        Args:
            task_type: Task type
            node_id: Node ID

        Returns:
            Success rate (0.0 - 1.0)
        """
        chars = self.get_node_characteristics(node_id)
        if chars is None:
            return 0.0

        rate_map = {
            TaskType.TRAIN: chars.train_success_rate,
            TaskType.INFER: chars.infer_success_rate,
            TaskType.VERIFY: chars.verify_success_rate,
        }

        return rate_map.get(task_type, 0.0)

    def get_cached_decision(self, task_profile_hash: str) -> Optional[SchedulingDecision]:
        """
        Get cached scheduling decision.

        Args:
            task_profile_hash: Hash of task profile

        Returns:
            Cached decision if found and not expired, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT decision_json, expires_at FROM decision_cache
            WHERE task_profile_hash = ?
            """,
            (task_profile_hash,)
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        expires_at = datetime.fromisoformat(row[1])
        if expires_at < datetime.now():
            return None

        # Would need to reconstruct SchedulingDecision from dict
        # This is simplified - full implementation would need proper deserialization
        return None

    def cache_decision(
        self,
        task_profile_hash: str,
        decision: SchedulingDecision,
    ) -> None:
        """
        Cache scheduling decision.

        Args:
            task_profile_hash: Hash of task profile
            decision: Decision to cache
        """
        from datetime import timedelta

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        expires_at = datetime.now() + timedelta(hours=24)

        cursor.execute(
            """
            INSERT OR REPLACE INTO decision_cache
            (task_profile_hash, decision_json, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                task_profile_hash,
                json.dumps(decision.to_dict()),
                datetime.now().isoformat(),
                expires_at.isoformat(),
            ),
        )

        conn.commit()
        conn.close()

    @staticmethod
    def hash_task_profile(task_profile: dict) -> str:
        """Generate hash for task profile"""
        profile_str = json.dumps(task_profile, sort_keys=True)
        return hashlib.sha256(profile_str.encode()).hexdigest()[:16]
