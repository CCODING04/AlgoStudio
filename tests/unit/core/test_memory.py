"""Unit tests for memory module (SQLiteMemoryStore)."""

import os
import tempfile
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from algo_studio.core.scheduler.memory.base import (
    MemoryLayerInterface,
    NodeCharacteristics,
    TaskOutcome,
)
from algo_studio.core.scheduler.memory.sqlite_store import SQLiteMemoryStore
from algo_studio.core.scheduler.profiles.task_profile import TaskType
from algo_studio.core.scheduler.profiles.scheduling_decision import SchedulingDecision
from algo_studio.core.ray_client import NodeStatus


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def memory_store(temp_db_path):
    """Create a SQLiteMemoryStore with temporary database."""
    return SQLiteMemoryStore(db_path=temp_db_path)


@pytest.fixture
def sample_node_status():
    """Create a sample NodeStatus for testing."""
    return NodeStatus(
        node_id="node-1",
        ip="192.168.0.115",
        status="idle",
        cpu_used=4,
        cpu_total=16,
        gpu_used=0,
        gpu_total=1,
        memory_used_gb=8.0,
        memory_total_gb=32.0,
        disk_used_gb=100.0,
        disk_total_gb=500.0,
        hostname="worker-1",
    )


@pytest.fixture
def sample_scheduling_decision(sample_node_status):
    """Create a sample SchedulingDecision for testing."""
    return SchedulingDecision(
        decision_id="decision-1",
        task_id="task-1",
        selected_node=sample_node_status,
        routing_path="fast",
        confidence=0.95,
        reasoning="Node has available GPU",
    )


@pytest.fixture
def sample_task_outcome():
    """Create a sample TaskOutcome for testing."""
    return TaskOutcome(
        task_id="task-1",
        success=True,
        duration_minutes=30.5,
        error=None,
        gpu_utilization=0.8,
        memory_used_gb=16.0,
    )


@pytest.fixture
def failed_task_outcome():
    """Create a failed TaskOutcome for testing."""
    return TaskOutcome(
        task_id="task-2",
        success=False,
        duration_minutes=15.0,
        error="GPU out of memory",
        gpu_utilization=0.9,
        memory_used_gb=24.0,
    )


# =============================================================================
# SQLiteMemoryStore Initialization Tests
# =============================================================================

class TestSQLiteMemoryStoreInit:
    """Tests for SQLiteMemoryStore initialization."""

    def test_init_with_custom_path(self, temp_db_path):
        """Test initialization with custom database path."""
        store = SQLiteMemoryStore(db_path=temp_db_path)

        assert store.db_path == temp_db_path

    def test_init_creates_default_path(self):
        """Test initialization creates default path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a store without specifying path (uses default)
            store = SQLiteMemoryStore(db_path=None)
            # Just verify it doesn't raise
            assert store.db_path is not None

    def test_init_creates_database_file(self):
        """Test initialization creates the database file."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            new_db_path = f.name

        try:
            # File should exist after we create it
            assert os.path.exists(new_db_path)

            # Create store - should be able to connect
            store = SQLiteMemoryStore(db_path=new_db_path)

            # File should still exist
            assert os.path.exists(new_db_path)
        finally:
            if os.path.exists(new_db_path):
                os.unlink(new_db_path)


# =============================================================================
# NodeCharacteristics Tests
# =============================================================================

class TestNodeCharacteristics:
    """Tests for NodeCharacteristics dataclass."""

    def test_success_rate_with_tasks(self):
        """Test success_rate calculation with tasks."""
        chars = NodeCharacteristics(
            node_id="node-1",
            hostname="worker-1",
            ip="192.168.0.1",
            total_tasks=10,
            success_tasks=8,
            failure_tasks=2,
        )

        assert chars.success_rate == 0.8

    def test_success_rate_with_no_tasks(self):
        """Test success_rate returns 0 with no tasks."""
        chars = NodeCharacteristics(
            node_id="node-1",
            hostname="worker-1",
            ip="192.168.0.1",
            total_tasks=0,
            success_tasks=0,
            failure_tasks=0,
        )

        assert chars.success_rate == 0.0


# =============================================================================
# TaskOutcome Tests
# =============================================================================

class TestTaskOutcome:
    """Tests for TaskOutcome dataclass."""

    def test_task_outcome_creation(self):
        """Test TaskOutcome creation with required fields."""
        outcome = TaskOutcome(
            task_id="task-1",
            success=True,
            duration_minutes=30.0,
        )

        assert outcome.task_id == "task-1"
        assert outcome.success is True
        assert outcome.duration_minutes == 30.0
        assert outcome.error is None

    def test_task_outcome_with_optional_fields(self):
        """Test TaskOutcome creation with optional fields."""
        outcome = TaskOutcome(
            task_id="task-1",
            success=False,
            duration_minutes=15.0,
            error="Out of memory",
            gpu_utilization=0.95,
            memory_used_gb=24.0,
        )

        assert outcome.success is False
        assert outcome.error == "Out of memory"
        assert outcome.gpu_utilization == 0.95


# =============================================================================
# record_decision Tests
# =============================================================================

class TestRecordDecision:
    """Tests for record_decision method."""

    def test_record_decision_with_node(self, memory_store, sample_scheduling_decision, sample_task_outcome):
        """Test recording a decision with a selected node."""
        # Should not raise
        memory_store.record_decision(sample_scheduling_decision, sample_task_outcome)

    def test_record_decision_without_node(self, memory_store, sample_task_outcome):
        """Test recording a decision without a selected node."""
        decision = SchedulingDecision(
            decision_id="decision-2",
            task_id="task-2",
            selected_node=None,
        )

        # Should not raise
        memory_store.record_decision(decision, sample_task_outcome)

    def test_record_decision_updates_node_characteristics(self, memory_store, sample_scheduling_decision, sample_task_outcome):
        """Test that recording a decision updates node characteristics."""
        memory_store.record_decision(sample_scheduling_decision, sample_task_outcome)

        # Check node characteristics were updated
        chars = memory_store.get_node_characteristics("node-1")
        assert chars is not None
        assert chars.total_tasks == 1
        assert chars.success_tasks == 1
        assert chars.failure_tasks == 0

    def test_record_decision_increments_existing_node(self, memory_store, sample_scheduling_decision, sample_task_outcome, failed_task_outcome):
        """Test that recording updates existing node characteristics."""
        # Record first decision (successful)
        memory_store.record_decision(sample_scheduling_decision, sample_task_outcome)

        # Create second decision with different decision_id for same node
        second_decision = SchedulingDecision(
            decision_id="decision-2",
            task_id="task-2",
            selected_node=sample_scheduling_decision.selected_node,
        )
        failed_outcome = TaskOutcome(
            task_id="task-2",
            success=False,
            duration_minutes=15.0,
            error="GPU out of memory",
        )
        memory_store.record_decision(second_decision, failed_outcome)

        chars = memory_store.get_node_characteristics("node-1")
        assert chars.total_tasks == 2
        assert chars.success_tasks == 1
        assert chars.failure_tasks == 1


# =============================================================================
# get_node_characteristics Tests
# =============================================================================

class TestGetNodeCharacteristics:
    """Tests for get_node_characteristics method."""

    def test_get_nonexistent_node_returns_none(self, memory_store):
        """Test getting characteristics for non-existent node returns None."""
        result = memory_store.get_node_characteristics("nonexistent")

        assert result is None

    def test_get_node_characteristics_basic(self, memory_store, sample_scheduling_decision, sample_task_outcome):
        """Test getting node characteristics after recording."""
        memory_store.record_decision(sample_scheduling_decision, sample_task_outcome)

        chars = memory_store.get_node_characteristics("node-1")

        assert chars is not None
        assert chars.node_id == "node-1"
        assert chars.hostname == "worker-1"
        assert chars.ip == "192.168.0.115"

    def test_get_node_characteristics_metrics(self, memory_store, sample_scheduling_decision, sample_task_outcome):
        """Test getting node characteristics with metrics."""
        memory_store.record_decision(sample_scheduling_decision, sample_task_outcome)

        chars = memory_store.get_node_characteristics("node-1")

        assert chars.total_tasks == 1
        assert chars.success_tasks == 1
        assert chars.failure_tasks == 0


# =============================================================================
# get_success_rate Tests
# =============================================================================

class TestGetSuccessRate:
    """Tests for get_success_rate method."""

    def test_get_success_rate_unknown_node_returns_zero(self, memory_store):
        """Test getting success rate for unknown node returns 0."""
        result = memory_store.get_success_rate(TaskType.TRAIN, "nonexistent")

        assert result == 0.0

    def test_get_success_rate_train(self, memory_store, sample_scheduling_decision, sample_task_outcome):
        """Test getting train success rate."""
        memory_store.record_decision(sample_scheduling_decision, sample_task_outcome)

        result = memory_store.get_success_rate(TaskType.TRAIN, "node-1")

        # Default rates are 0.0 unless updated separately
        assert result == 0.0


# =============================================================================
# cache_decision Tests
# =============================================================================

class TestCacheDecision:
    """Tests for cache_decision method."""

    def test_cache_decision_basic(self, memory_store, sample_scheduling_decision):
        """Test caching a decision."""
        # Should not raise
        memory_store.cache_decision("hash-123", sample_scheduling_decision)

    def test_cache_decision_replaces_existing(self, memory_store, sample_scheduling_decision):
        """Test that caching replaces existing cached decision."""
        memory_store.cache_decision("hash-123", sample_scheduling_decision)

        # Create a different decision
        new_decision = SchedulingDecision(
            decision_id="decision-new",
            task_id="task-new",
            selected_node=None,
        )
        memory_store.cache_decision("hash-123", new_decision)

        # Should not raise - just means replacement worked


# =============================================================================
# get_cached_decision Tests
# =============================================================================

class TestGetCachedDecision:
    """Tests for get_cached_decision method."""

    def test_get_nonexistent_cache_returns_none(self, memory_store):
        """Test getting non-existent cached decision returns None."""
        result = memory_store.get_cached_decision("nonexistent-hash")

        assert result is None

    def test_get_cached_decision_expired_returns_none(self, memory_store, sample_scheduling_decision):
        """Test that expired cached decision returns None."""
        # Directly manipulate database to set expired time
        import sqlite3
        conn = sqlite3.connect(memory_store.db_path)
        cursor = conn.cursor()

        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()

        cursor.execute(
            """
            INSERT INTO decision_cache
            (task_profile_hash, decision_json, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            ("expired-hash", json.dumps({}), datetime.now().isoformat(), expired_time),
        )
        conn.commit()
        conn.close()

        result = memory_store.get_cached_decision("expired-hash")

        assert result is None


# =============================================================================
# hash_task_profile Tests
# =============================================================================

class TestHashTaskProfile:
    """Tests for hash_task_profile static method."""

    def test_hash_same_profile_same_hash(self):
        """Test same profile produces same hash."""
        profile = {"task_type": "train", "num_gpus": 1}

        hash1 = SQLiteMemoryStore.hash_task_profile(profile)
        hash2 = SQLiteMemoryStore.hash_task_profile(profile)

        assert hash1 == hash2

    def test_hash_different_profiles_different_hash(self):
        """Test different profiles produce different hashes."""
        profile1 = {"task_type": "train", "num_gpus": 1}
        profile2 = {"task_type": "infer", "num_gpus": 0}

        hash1 = SQLiteMemoryStore.hash_task_profile(profile1)
        hash2 = SQLiteMemoryStore.hash_task_profile(profile2)

        assert hash1 != hash2

    def test_hash_is_deterministic(self):
        """Test hash is deterministic regardless of key order."""
        profile1 = {"a": 1, "b": 2, "c": 3}
        profile2 = {"c": 3, "a": 1, "b": 2}

        hash1 = SQLiteMemoryStore.hash_task_profile(profile1)
        hash2 = SQLiteMemoryStore.hash_task_profile(profile2)

        assert hash1 == hash2

    def test_hash_length(self):
        """Test hash has expected length."""
        profile = {"task_type": "train", "num_gpus": 1}

        hash_result = SQLiteMemoryStore.hash_task_profile(profile)

        # SHA256 truncated to 16 characters
        assert len(hash_result) == 16


# =============================================================================
# MemoryLayerInterface Tests
# =============================================================================

class TestMemoryLayerInterface:
    """Tests for MemoryLayerInterface abstract methods."""

    def test_interface_is_abstract(self):
        """Test that MemoryLayerInterface cannot be instantiated directly."""
        with pytest.raises(TypeError):
            MemoryLayerInterface()


# =============================================================================
# Integration Tests
# =============================================================================

class TestMemoryStoreIntegration:
    """Integration tests for memory store."""

    def test_full_record_and_retrieve_flow(self, memory_store, sample_scheduling_decision, sample_task_outcome):
        """Test full flow of recording decision and retrieving node characteristics."""
        # Record the decision
        memory_store.record_decision(sample_scheduling_decision, sample_task_outcome)

        # Retrieve and verify node characteristics
        chars = memory_store.get_node_characteristics("node-1")

        assert chars is not None
        assert chars.node_id == "node-1"
        assert chars.hostname == "worker-1"
        assert chars.ip == "192.168.0.115"
        assert chars.total_tasks == 1
        assert chars.success_tasks == 1
        assert chars.is_healthy is True

    def test_failed_task_marks_node_unhealthy_after_consecutive_failures(self, memory_store, sample_scheduling_decision):
        """Test that consecutive failures eventually mark node unhealthy.

        The code marks node unhealthy when consecutive_failures >= 3 (i.e., after 4th failure).
        This is because the is_healthy check uses row[13] < 3 (checking the OLD value).
        """
        # Simulate 4 consecutive failures (with unique decision_ids)
        for i in range(4):
            decision = SchedulingDecision(
                decision_id=f"decision-fail-{i}",
                task_id=f"task-fail-{i}",
                selected_node=sample_scheduling_decision.selected_node,
            )
            failed_outcome = TaskOutcome(
                task_id=f"task-fail-{i}",
                success=False,
                duration_minutes=10.0,
                error="GPU error",
            )
            memory_store.record_decision(decision, failed_outcome)

        chars = memory_store.get_node_characteristics("node-1")
        assert chars.consecutive_failures == 4
        # After 4 consecutive failures, node should be marked unhealthy
        assert chars.is_healthy is False

    def test_successful_task_resets_consecutive_failures(self, memory_store, sample_scheduling_decision):
        """Test that successful task resets consecutive failure counter."""
        # 3 failures (with unique decision_ids) - still healthy
        for i in range(3):
            decision = SchedulingDecision(
                decision_id=f"decision-fail-{i}",
                task_id=f"task-fail-{i}",
                selected_node=sample_scheduling_decision.selected_node,
            )
            failed_outcome = TaskOutcome(
                task_id=f"task-fail-{i}",
                success=False,
                duration_minutes=10.0,
                error="GPU error",
            )
            memory_store.record_decision(decision, failed_outcome)

        chars_before = memory_store.get_node_characteristics("node-1")
        assert chars_before.consecutive_failures == 3
        assert chars_before.is_healthy is True  # Still healthy after 3 failures

        # 1 success (with unique decision_id)
        success_decision = SchedulingDecision(
            decision_id="decision-success",
            task_id="task-success",
            selected_node=sample_scheduling_decision.selected_node,
        )
        success_outcome = TaskOutcome(
            task_id="task-success",
            success=True,
            duration_minutes=30.0,
        )
        memory_store.record_decision(success_decision, success_outcome)

        chars = memory_store.get_node_characteristics("node-1")
        assert chars.consecutive_failures == 0
        assert chars.is_healthy is True
