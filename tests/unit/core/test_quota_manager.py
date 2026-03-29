# tests/unit/core/test_quota_manager.py
"""Unit tests for QuotaManager."""

import os
import tempfile
import pytest
import unittest.mock
from typing import Dict, Any
from unittest.mock import MagicMock

from algo_studio.core.quota.manager import QuotaManager
from algo_studio.core.quota.store import SQLiteQuotaStore, ResourceQuota, QuotaScope
from algo_studio.core.quota.exceptions import (
    QuotaExceededError,
    QuotaNotFoundError,
    OptimisticLockError,
    InheritanceValidationError,
)


class TestSQLiteQuotaStore:
    """Tests for SQLiteQuotaStore."""

    @pytest.fixture
    def store(self):
        """Create a temporary store for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        store = SQLiteQuotaStore(db_path=db_path)
        yield store
        # Cleanup
        os.unlink(db_path)

    def test_create_and_get_quota(self, store):
        """Test creating and retrieving a quota."""
        quota_data = {
            "quota_id": "test-quota-1",
            "scope": QuotaScope.USER,
            "scope_id": "user123",
            "name": "Test User Quota",
            "cpu_cores": 10,
            "gpu_count": 2,
            "gpu_memory_gb": 16.0,
            "memory_gb": 32.0,
            "concurrent_tasks": 5,
        }
        store.create_quota(quota_data)

        retrieved = store.get_quota("test-quota-1")
        assert retrieved is not None
        assert retrieved["quota_id"] == "test-quota-1"
        assert retrieved["cpu_cores"] == 10
        assert retrieved["gpu_count"] == 2

    def test_get_quota_by_scope(self, store):
        """Test retrieving quota by scope."""
        quota_data = {
            "quota_id": "user-quota-1",
            "scope": QuotaScope.USER,
            "scope_id": "alice",
            "name": "Alice Quota",
            "cpu_cores": 8,
        }
        store.create_quota(quota_data)

        retrieved = store.get_quota_by_scope(QuotaScope.USER, "alice")
        assert retrieved is not None
        assert retrieved["scope_id"] == "alice"

        not_found = store.get_quota_by_scope(QuotaScope.USER, "bob")
        assert not_found is None

    def test_increment_usage_with_version(self, store):
        """Test optimistic locking on increment_usage."""
        # Create quota
        quota_data = {
            "quota_id": "vtest-1",
            "scope": QuotaScope.USER,
            "scope_id": "user1",
            "name": "Version Test",
            "cpu_cores": 10,
        }
        store.create_quota(quota_data)

        # Get initial version
        usage = store.get_usage("vtest-1")
        assert usage["version"] == 0

        # Increment without version check
        resources = ResourceQuota(cpu_cores=2)
        store.increment_usage("vtest-1", resources)

        usage = store.get_usage("vtest-1")
        assert usage["version"] == 1
        assert usage["cpu_cores_used"] == 2

        # Increment with correct version
        store.increment_usage("vtest-1", resources, expected_version=1)
        usage = store.get_usage("vtest-1")
        assert usage["version"] == 2
        assert usage["cpu_cores_used"] == 4

    def test_increment_usage_version_mismatch(self, store):
        """Test that version mismatch raises OptimisticLockError."""
        quota_data = {
            "quota_id": "vtest-2",
            "scope": QuotaScope.USER,
            "scope_id": "user2",
            "name": "Version Mismatch Test",
            "cpu_cores": 10,
        }
        store.create_quota(quota_data)

        resources = ResourceQuota(cpu_cores=1)

        # Try with wrong version
        with pytest.raises(OptimisticLockError) as exc_info:
            store.increment_usage("vtest-2", resources, expected_version=99)
        assert exc_info.value.expected_version == 99

    def test_decrement_usage_floor_at_zero(self, store):
        """Test that decrement_usage doesn't go below zero."""
        quota_data = {
            "quota_id": "decr-test",
            "scope": QuotaScope.USER,
            "scope_id": "user3",
            "name": "Decrement Test",
            "cpu_cores": 10,
        }
        store.create_quota(quota_data)

        resources = ResourceQuota(cpu_cores=5)
        store.increment_usage("decr-test", resources)

        # Decrement more than available
        store.decrement_usage("decr-test", ResourceQuota(cpu_cores=100))

        usage = store.get_usage("decr-test")
        assert usage["cpu_cores_used"] == 0

    def test_decrement_usage_with_version(self, store):
        """Test optimistic locking on decrement_usage."""
        quota_data = {
            "quota_id": "decr-lock-test",
            "scope": QuotaScope.USER,
            "scope_id": "user-lock",
            "name": "Decrement Lock Test",
            "cpu_cores": 10,
        }
        store.create_quota(quota_data)

        # Increment first
        resources = ResourceQuota(cpu_cores=5)
        store.increment_usage("decr-lock-test", resources)

        # Get current version
        usage = store.get_usage("decr-lock-test")
        assert usage["version"] == 1

        # Decrement with correct version
        store.decrement_usage("decr-lock-test", ResourceQuota(cpu_cores=2), expected_version=1)

        usage = store.get_usage("decr-lock-test")
        assert usage["version"] == 2
        assert usage["cpu_cores_used"] == 3

    def test_decrement_usage_version_mismatch(self, store):
        """Test that version mismatch raises OptimisticLockError on decrement."""
        quota_data = {
            "quota_id": "decr-mismatch-test",
            "scope": QuotaScope.USER,
            "scope_id": "user-mismatch",
            "name": "Decrement Mismatch Test",
            "cpu_cores": 10,
        }
        store.create_quota(quota_data)

        resources = ResourceQuota(cpu_cores=3)
        store.increment_usage("decr-mismatch-test", resources)

        # Try with wrong version
        with pytest.raises(OptimisticLockError) as exc_info:
            store.decrement_usage("decr-mismatch-test", resources, expected_version=99)
        assert exc_info.value.expected_version == 99
        assert exc_info.value.actual_version == 1

    def test_get_bulk_usage(self, store):
        """Test batch fetching of usage data."""
        # Create multiple quotas
        for i in range(5):
            store.create_quota({
                "quota_id": f"bulk-{i}",
                "scope": QuotaScope.USER,
                "scope_id": f"user{i}",
                "name": f"User {i}",
                "cpu_cores": 10,
            })
            store.increment_usage(f"bulk-{i}", ResourceQuota(cpu_cores=i))

        # Bulk fetch
        ids = ["bulk-0", "bulk-2", "bulk-4"]
        result = store.get_bulk_usage(ids)

        assert len(result) == 3
        assert result["bulk-0"]["cpu_cores_used"] == 0
        assert result["bulk-2"]["cpu_cores_used"] == 2
        assert result["bulk-4"]["cpu_cores_used"] == 4

    def test_inheritance_chain_validation(self, store):
        """Test inheritance chain validation (no cycles, all exist)."""
        # Create global -> team -> user chain
        store.create_quota({
            "quota_id": "global-1",
            "scope": QuotaScope.GLOBAL,
            "scope_id": "global",
            "name": "Global",
            "cpu_cores": 100,
        })
        store.create_quota({
            "quota_id": "team-1",
            "scope": QuotaScope.TEAM,
            "scope_id": "team-a",
            "name": "Team A",
            "parent_quota_id": "global-1",
            "cpu_cores": 50,
        })
        store.create_quota({
            "quota_id": "user-1",
            "scope": QuotaScope.USER,
            "scope_id": "alice",
            "name": "Alice",
            "parent_quota_id": "team-1",
            "cpu_cores": 10,
        })

        # Valid chain
        is_valid, errors = store.validate_inheritance_chain("user-1")
        assert is_valid
        assert len(errors) == 0

        # Cycle detection - modify user to point to itself
        store.update_quota("user-1", {"parent_quota_id": "user-1"})
        is_valid, errors = store.validate_inheritance_chain("user-1")
        assert not is_valid
        assert "Cycle detected" in errors[0]

    def test_list_quotas_by_scope(self, store):
        """Test listing quotas filtered by scope."""
        store.create_quota({
            "quota_id": "g1", "scope": QuotaScope.GLOBAL, "scope_id": "g",
            "name": "Global", "cpu_cores": 100,
        })
        store.create_quota({
            "quota_id": "t1", "scope": QuotaScope.TEAM, "scope_id": "t1",
            "name": "Team 1", "cpu_cores": 50,
        })
        store.create_quota({
            "quota_id": "u1", "scope": QuotaScope.USER, "scope_id": "u1",
            "name": "User 1", "cpu_cores": 10,
        })

        all_quotas = store.list_quotas()
        assert len(all_quotas) == 3

        global_quotas = store.list_quotas(QuotaScope.GLOBAL)
        assert len(global_quotas) == 1
        assert global_quotas[0]["quota_id"] == "g1"


class TestQuotaManager:
    """Tests for QuotaManager."""

    @pytest.fixture
    def store(self):
        """Create a temporary store for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        store = SQLiteQuotaStore(db_path=db_path)
        yield store
        os.unlink(db_path)

    @pytest.fixture
    def manager(self, store):
        """Create a QuotaManager with the test store."""
        return QuotaManager(store)

    @pytest.fixture
    def global_quota(self, store):
        """Create a global quota."""
        store.create_quota({
            "quota_id": "global",
            "scope": QuotaScope.GLOBAL,
            "scope_id": "global",
            "name": "Global Quota",
            "cpu_cores": 100,
            "gpu_count": 4,
            "memory_gb": 256.0,
        })
        return "global"

    @pytest.fixture
    def team_quota(self, store):
        """Create a team quota inheriting from global."""
        store.create_quota({
            "quota_id": "team-a",
            "scope": QuotaScope.TEAM,
            "scope_id": "team-a",
            "name": "Team A",
            "parent_quota_id": "global",
            "cpu_cores": 50,
            "gpu_count": 2,
            "memory_gb": 128.0,
        })
        return "team-a"

    @pytest.fixture
    def user_quota(self, store):
        """Create a user quota inheriting from team."""
        store.create_quota({
            "quota_id": "alice",
            "scope": QuotaScope.USER,
            "scope_id": "alice",
            "name": "Alice",
            "parent_quota_id": "team-a",
            "cpu_cores": 20,
            "gpu_count": 1,
            "gpu_memory_gb": 8.0,
            "memory_gb": 128.0,
            "concurrent_tasks": 5,
        })
        return "alice"

    def test_check_quota_no_quota_defined(self, manager):
        """Test that no quota means unlimited."""
        allowed, quota, usage, reasons = manager.check_quota(
            "unknown_user", None, ResourceQuota(cpu_cores=10)
        )
        assert allowed is True
        assert quota is None

    def test_check_quota_within_limits(self, manager, store, global_quota):
        """Test checking quota when within limits."""
        allowed, quota, usage, reasons = manager.check_quota(
            "user1", None, ResourceQuota(cpu_cores=10)
        )
        assert allowed is True
        assert quota["quota_id"] == "global"

    def test_check_quota_exceeded(self, manager, store, global_quota):
        """Test checking quota when exceeded."""
        # Use most of the quota
        store.increment_usage("global", ResourceQuota(cpu_cores=95))

        allowed, quota, usage, reasons = manager.check_quota(
            "user1", None, ResourceQuota(cpu_cores=10)
        )
        assert allowed is False
        assert len(reasons) > 0
        assert "CPU cores" in reasons[0]

    def test_check_quota_inheritance_user_priority(self, manager, store, global_quota, team_quota, user_quota):
        """Test that user quota takes priority over team/global."""
        # User has 20 cores, team has 50, global has 100
        # Request 25 - should fail due to user quota limit
        allowed, quota, usage, reasons = manager.check_quota(
            "alice", "team-a", ResourceQuota(cpu_cores=25)
        )
        assert allowed is False
        assert quota["quota_id"] == "alice"

        # Request 15 - should succeed within user limit
        allowed, quota, usage, reasons = manager.check_quota(
            "alice", "team-a", ResourceQuota(cpu_cores=15)
        )
        assert allowed is True

    def test_check_quota_inheritance_team_fallback(self, manager, store, global_quota, team_quota):
        """Test that team quota is used when no user quota exists."""
        allowed, quota, usage, reasons = manager.check_quota(
            "bob", "team-a", ResourceQuota(cpu_cores=30)
        )
        assert allowed is True
        assert quota["quota_id"] == "team-a"

    def test_allocate_resources(self, manager, store, global_quota):
        """Test allocating resources."""
        resources = ResourceQuota(cpu_cores=10, gpu_count=1)

        success = manager.allocate_resources("global", resources)
        assert success is True

        usage = store.get_usage("global")
        assert usage["cpu_cores_used"] == 10
        assert usage["gpu_count_used"] == 1

    def test_allocate_resources_with_optimistic_lock(self, manager, store, global_quota):
        """Test allocating with optimistic locking."""
        usage = store.get_usage("global")
        version = usage["version"]

        resources = ResourceQuota(cpu_cores=5)
        success = manager.allocate_resources("global", resources, expected_version=version)
        assert success is True

        usage = store.get_usage("global")
        assert usage["version"] == version + 1

        # Reject stale version
        with pytest.raises(OptimisticLockError):
            manager.allocate_resources("global", resources, expected_version=version)

    def test_release_resources(self, manager, store, global_quota):
        """Test releasing resources."""
        # First allocate
        manager.allocate_resources("global", ResourceQuota(cpu_cores=50))

        # Then release
        success = manager.release_resources("global", ResourceQuota(cpu_cores=30))
        assert success is True

        usage = store.get_usage("global")
        assert usage["cpu_cores_used"] == 20

    def test_validate_inheritance_valid_chain(self, manager, store, global_quota, team_quota, user_quota):
        """Test validating a valid inheritance chain."""
        is_valid, errors = manager.validate_inheritance("alice")
        assert is_valid
        assert len(errors) == 0

    def test_validate_inheritance_user_to_user_parent_invalid(self, manager, store, global_quota, user_quota):
        """Test that user quota cannot have another user quota as parent."""
        store.create_quota({
            "quota_id": "user-bad-parent",
            "scope": QuotaScope.USER,
            "scope_id": "bad",
            "name": "Bad User",
            "parent_quota_id": "alice",  # alice is a user quota from user_quota fixture
            "cpu_cores": 5,
        })

        is_valid, errors = manager.validate_inheritance("user-bad-parent")
        assert is_valid is False
        assert any("User quota cannot have another user quota as parent" in e for e in errors)

    def test_validate_inheritance_global_with_parent_invalid(self, manager, store, global_quota):
        """Test that global quota should not have a parent."""
        # Give global a parent (which is invalid)
        store.update_quota("global", {"parent_quota_id": "some-parent"})

        is_valid, errors = manager.validate_inheritance("global")
        assert is_valid is False
        assert any("Global quota should not have a parent" in e for e in errors)

    def test_validate_inheritance_nonexistent_quota(self, manager):
        """Test validating a quota that doesn't exist."""
        with pytest.raises(QuotaNotFoundError):
            manager.validate_inheritance("nonexistent")

    def test_validate_inheritance_or_raise(self, manager, store, global_quota, team_quota, user_quota):
        """Test validate_inheritance_or_raise raises on invalid."""
        # Valid case should not raise
        manager.validate_inheritance_or_raise("alice")

        # Invalid case should raise
        store.update_quota("global", {"parent_quota_id": "team-a"})  # Global with team parent
        with pytest.raises(InheritanceValidationError) as exc_info:
            manager.validate_inheritance_or_raise("global")
        assert exc_info.value.quota_id == "global"
        assert len(exc_info.value.chain) > 0

    def test_check_task_submission_train(self, manager, store, user_quota):
        """Test task submission check for training task."""
        # alice has 1 GPU, train needs 1 GPU
        allowed, error = manager.check_task_submission("alice", "team-a", "train")
        assert allowed is True

        # Use all GPU quota
        store.increment_usage("alice", ResourceQuota(gpu_count=1))

        allowed, error = manager.check_task_submission("alice", "team-a", "train")
        assert allowed is False
        assert "GPU count" in error

    def test_check_task_submission_infer(self, manager, store, user_quota):
        """Test task submission check for inference task."""
        # Infer doesn't need GPU, should be allowed
        allowed, error = manager.check_task_submission("alice", "team-a", "infer")
        assert allowed is True

    def test_get_usage_percentage(self, manager, store, user_quota):
        """Test calculating usage percentages."""
        # Use 10 of 20 cores = 50%, 64 of 128GB memory = 50%
        store.increment_usage("alice", ResourceQuota(cpu_cores=10, memory_gb=64))

        usage = store.get_usage("alice")
        quota = store.get_quota("alice")

        percentages = manager.get_usage_percentage(quota, usage)
        assert percentages["cpu_cores"] == 50.0
        assert percentages["memory_gb"] == 50.0
        assert percentages["gpu_count"] == 0.0  # Not used

    def test_get_effective_quota_with_inheritance(self, manager, store, global_quota, team_quota, user_quota):
        """Test getting effective quota with inheritance info."""
        effective = manager.get_effective_quota_with_inheritance("alice", "team-a")

        assert effective is not None
        assert effective["quota_id"] == "alice"
        assert effective["scope"] == QuotaScope.USER
        assert "inheritance_chain" in effective
        assert "global" in effective["inheritance_chain"]
        assert "team-a" in effective["inheritance_chain"]

    def test_unlimited_quota_allows_allocation(self, manager, store):
        """Test that unlimited quota (all zeros) allows any allocation."""
        store.create_quota({
            "quota_id": "unlimited",
            "scope": QuotaScope.USER,
            "scope_id": "nobody",
            "name": "Unlimited",
            "cpu_cores": 0,  # Unlimited
            "gpu_count": 0,
            "memory_gb": 0,
        })

        allowed, quota, usage, reasons = manager.check_quota(
            "nobody", None, ResourceQuota(cpu_cores=9999)
        )
        assert allowed is True

    def test_create_quota(self, manager):
        """Test creating a quota via manager."""
        quota_id = manager.create_quota({
            "scope": QuotaScope.USER,
            "scope_id": "newuser",
            "name": "New User",
            "cpu_cores": 15,
        })

        assert quota_id is not None
        quota = manager.get_quota(quota_id)
        assert quota["name"] == "New User"
        assert quota["cpu_cores"] == 15

    def test_multiple_resource_dimensions(self, manager, store, user_quota):
        """Test checking multiple resource dimensions simultaneously."""
        # Use some resources
        store.increment_usage("alice", ResourceQuota(
            cpu_cores=15, gpu_count=1, memory_gb=40
        ))

        # Alice has: 20 cores, 1 GPU, 128GB memory
        # Used: 15 cores, 1 GPU, 40GB memory
        # Available: 5 cores, 0 GPU, 88GB memory
        # Request: 5 cores, 1 GPU, 30GB - should fail on GPU (0 available, 1 requested)
        allowed, quota, usage, reasons = manager.check_quota(
            "alice", "team-a",
            ResourceQuota(cpu_cores=5, gpu_count=1, memory_gb=30)
        )
        assert allowed is False
        assert any("GPU" in r for r in reasons)

        # Same request without GPU - should succeed
        allowed, quota, usage, reasons = manager.check_quota(
            "alice", "team-a",
            ResourceQuota(cpu_cores=5, memory_gb=30)
        )
        assert allowed is True


class TestResourceQuota:
    """Tests for ResourceQuota class."""

    def test_to_tuple(self):
        """Test converting ResourceQuota to tuple."""
        rq = ResourceQuota(
            cpu_cores=4,
            gpu_count=2,
            gpu_memory_gb=16.0,
            memory_gb=32.0,
            disk_gb=100.0,
            concurrent_tasks=5,
        )
        t = rq.to_tuple()
        assert t == (4, 2, 16.0, 32.0, 100.0, 5)

    def test_defaults(self):
        """Test default values."""
        rq = ResourceQuota()
        assert rq.cpu_cores == 0
        assert rq.gpu_count == 0
        assert rq.gpu_memory_gb == 0.0
        assert rq.memory_gb == 0.0
        assert rq.disk_gb == 0.0
        assert rq.concurrent_tasks == 0


class TestRedisQuotaStore:
    """Tests for RedisQuotaStore using mocks."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        from unittest.mock import MagicMock
        mock = MagicMock()
        mock.hgetall.return_value = {}
        mock.hget.return_value = None
        mock.exists.return_value = False
        mock.keys.return_value = []
        mock.pipeline.return_value = MagicMock(execute=MagicMock(return_value=[]))
        return mock

    @pytest.fixture
    def store(self, mock_redis):
        """Create a RedisQuotaStore with mocked Redis."""
        from algo_studio.core.quota.store import RedisQuotaStore
        store = RedisQuotaStore(redis_host="localhost", redis_port=6380)
        store._redis = mock_redis
        return store

    def test_create_and_get_quota(self, store, mock_redis):
        """Test creating and retrieving a quota."""
        quota_data = {
            "quota_id": "redis-quota-1",
            "scope": QuotaScope.USER,
            "scope_id": "user123",
            "name": "Test User Quota",
            "cpu_cores": 10,
            "gpu_count": 2,
            "gpu_memory_gb": 16.0,
            "memory_gb": 32.0,
            "concurrent_tasks": 5,
        }

        # Scope doesn't exist
        mock_redis.exists.return_value = False

        result = store.create_quota(quota_data)
        assert result is True

        # Verify quota was stored
        mock_redis.hset.assert_any_call(
            "quota:redis-quota-1",
            mapping=unittest.mock.ANY
        )

    def test_get_quota_not_found(self, store, mock_redis):
        """Test getting a non-existent quota."""
        mock_redis.hgetall.return_value = {}
        result = store.get_quota("nonexistent")
        assert result is None

    def test_get_quota_by_scope(self, store, mock_redis):
        """Test retrieving quota by scope."""
        mock_redis.get.return_value = "redis-quota-1"
        mock_redis.hgetall.return_value = {
            "scope": QuotaScope.USER,
            "scope_id": "user123",
            "name": "Test",
            "cpu_cores": "10",
            "gpu_count": "2",
            "gpu_memory_gb": "16.0",
            "memory_gb": "32.0",
            "disk_gb": "0.0",
            "concurrent_tasks": "5",
            "tasks_per_day": "50",
            "gpu_hours_per_day": "24.0",
            "alert_threshold": "80",
            "parent_quota_id": "",
            "is_active": "1",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }

        result = store.get_quota_by_scope(QuotaScope.USER, "user123")
        assert result is not None
        assert result["quota_id"] == "redis-quota-1"

    def test_increment_usage_with_version(self, store, mock_redis):
        """Test optimistic locking on increment_usage."""
        quota_id = "redis-quota-lock"

        # First call returns version 0, second call (after eval) returns version 1
        mock_redis.hget.side_effect = ["0", "1"]

        resources = ResourceQuota(cpu_cores=2)

        # Mock the eval to return success
        mock_redis.eval.return_value = 1

        result = store.increment_usage(quota_id, resources, expected_version=0)
        assert result is True

    def test_increment_usage_version_mismatch(self, store, mock_redis):
        """Test that version mismatch raises OptimisticLockError."""
        from algo_studio.core.quota.exceptions import OptimisticLockError

        quota_id = "redis-quota-mismatch"

        # Return version 1 when we expect 0
        mock_redis.hget.return_value = "1"

        resources = ResourceQuota(cpu_cores=2)

        with pytest.raises(OptimisticLockError) as exc_info:
            store.increment_usage(quota_id, resources, expected_version=0)
        assert exc_info.value.expected_version == 0
        assert exc_info.value.actual_version == 1

    def test_decrement_usage_with_version(self, store, mock_redis):
        """Test optimistic locking on decrement_usage."""
        quota_id = "redis-quota-decr-lock"

        # First call returns version 1
        mock_redis.hget.side_effect = ["1", "2"]

        resources = ResourceQuota(cpu_cores=2)

        # Mock the eval to return success
        mock_redis.eval.return_value = 1

        result = store.decrement_usage(quota_id, resources, expected_version=1)
        assert result is True

    def test_decrement_usage_version_mismatch(self, store, mock_redis):
        """Test that version mismatch raises OptimisticLockError on decrement."""
        from algo_studio.core.quota.exceptions import OptimisticLockError

        quota_id = "redis-quota-decr-mismatch"

        # Return version 2 when we expect 1
        mock_redis.hget.return_value = "2"

        resources = ResourceQuota(cpu_cores=2)

        with pytest.raises(OptimisticLockError) as exc_info:
            store.decrement_usage(quota_id, resources, expected_version=1)
        assert exc_info.value.expected_version == 1
        assert exc_info.value.actual_version == 2

    def test_decrement_usage_floor_at_zero(self, store, mock_redis):
        """Test that decrement_usage doesn't go below zero."""
        quota_id = "redis-quota-floor"

        mock_redis.hget.return_value = "1"
        mock_redis.eval.return_value = 1

        resources = ResourceQuota(cpu_cores=100)

        result = store.decrement_usage(quota_id, resources)
        assert result is True

    def test_get_usage(self, store, mock_redis):
        """Test getting usage data."""
        quota_id = "redis-quota-usage"

        mock_redis.hgetall.return_value = {
            "cpu_cores_used": "5.0",
            "gpu_count_used": "1",
            "gpu_memory_gb_used": "8.0",
            "memory_gb_used": "16.0",
            "disk_gb_used": "0.0",
            "concurrent_tasks_used": "2",
            "tasks_today": "10",
            "gpu_minutes_today": "120.0",
            "version": "3",
            "updated_at": "2026-01-01T00:00:00",
        }

        result = store.get_usage(quota_id)
        assert result is not None
        assert result["cpu_cores_used"] == 5.0
        assert result["gpu_count_used"] == 1
        assert result["version"] == 3

    def test_get_bulk_usage(self, store, mock_redis):
        """Test batch fetching of usage data."""
        mock_pipeline = MagicMock()
        mock_pipeline.execute.return_value = [
            {
                "cpu_cores_used": "5.0",
                "gpu_count_used": "1",
                "gpu_memory_gb_used": "8.0",
                "memory_gb_used": "16.0",
                "disk_gb_used": "0.0",
                "concurrent_tasks_used": "2",
                "tasks_today": "10",
                "gpu_minutes_today": "120.0",
                "version": "3",
                "updated_at": "2026-01-01T00:00:00",
            },
            {
                "cpu_cores_used": "3.0",
                "gpu_count_used": "0",
                "gpu_memory_gb_used": "0.0",
                "memory_gb_used": "8.0",
                "disk_gb_used": "0.0",
                "concurrent_tasks_used": "1",
                "tasks_today": "5",
                "gpu_minutes_today": "0.0",
                "version": "1",
                "updated_at": "2026-01-01T00:00:00",
            },
        ]
        mock_redis.pipeline.return_value = mock_pipeline

        result = store.get_bulk_usage(["quota-1", "quota-2"])

        assert len(result) == 2
        assert result["quota-1"]["cpu_cores_used"] == 5.0
        assert result["quota-2"]["cpu_cores_used"] == 3.0

    def test_list_quotas(self, store, mock_redis):
        """Test listing quotas."""
        mock_redis.keys.return_value = ["quota:q1", "quota:q2"]
        # list_quotas calls get_quota for each key, and get_quota calls hgetall
        # We need 4 values: 2 for first list_quotas call + 2 for second list_quotas call
        mock_redis.hgetall.side_effect = [
            {
                "scope": QuotaScope.USER,
                "scope_id": "user1",
                "name": "User 1",
                "cpu_cores": "10",
                "gpu_count": "2",
                "gpu_memory_gb": "16.0",
                "memory_gb": "32.0",
                "disk_gb": "0.0",
                "concurrent_tasks": "5",
                "tasks_per_day": "50",
                "gpu_hours_per_day": "24.0",
                "alert_threshold": "80",
                "parent_quota_id": "",
                "is_active": "1",
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:00:00",
            },
            {
                "scope": QuotaScope.GLOBAL,
                "scope_id": "global",
                "name": "Global",
                "cpu_cores": "100",
                "gpu_count": "4",
                "gpu_memory_gb": "64.0",
                "memory_gb": "256.0",
                "disk_gb": "0.0",
                "concurrent_tasks": "10",
                "tasks_per_day": "100",
                "gpu_hours_per_day": "48.0",
                "alert_threshold": "80",
                "parent_quota_id": "",
                "is_active": "1",
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:00:00",
            },
            {
                "scope": QuotaScope.USER,
                "scope_id": "user1",
                "name": "User 1",
                "cpu_cores": "10",
                "gpu_count": "2",
                "gpu_memory_gb": "16.0",
                "memory_gb": "32.0",
                "disk_gb": "0.0",
                "concurrent_tasks": "5",
                "tasks_per_day": "50",
                "gpu_hours_per_day": "24.0",
                "alert_threshold": "80",
                "parent_quota_id": "",
                "is_active": "1",
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:00:00",
            },
            {
                "scope": QuotaScope.GLOBAL,
                "scope_id": "global",
                "name": "Global",
                "cpu_cores": "100",
                "gpu_count": "4",
                "gpu_memory_gb": "64.0",
                "memory_gb": "256.0",
                "disk_gb": "0.0",
                "concurrent_tasks": "10",
                "tasks_per_day": "100",
                "gpu_hours_per_day": "48.0",
                "alert_threshold": "80",
                "parent_quota_id": "",
                "is_active": "1",
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:00:00",
            },
        ]

        result = store.list_quotas()
        assert len(result) == 2

        # Filter by scope
        result_user = store.list_quotas(scope=QuotaScope.USER)
        assert len(result_user) == 1
        assert result_user[0]["scope"] == QuotaScope.USER

    def test_inheritance_chain_validation(self, store, mock_redis):
        """Test inheritance chain validation."""
        # Mock the chain: user-1 -> team-1 -> global-1
        call_count = [0]

        def mock_hgetall(key):
            call_count[0] += 1
            if "user-1" in key:
                return {
                    "scope": QuotaScope.USER,
                    "scope_id": "alice",
                    "name": "Alice",
                    "cpu_cores": "10",
                    "gpu_count": "1",
                    "gpu_memory_gb": "8.0",
                    "memory_gb": "32.0",
                    "disk_gb": "0.0",
                    "concurrent_tasks": "5",
                    "tasks_per_day": "50",
                    "gpu_hours_per_day": "24.0",
                    "alert_threshold": "80",
                    "parent_quota_id": "team-1",
                    "is_active": "1",
                    "created_at": "2026-01-01T00:00:00",
                    "updated_at": "2026-01-01T00:00:00",
                }
            elif "team-1" in key:
                return {
                    "scope": QuotaScope.TEAM,
                    "scope_id": "team-a",
                    "name": "Team A",
                    "cpu_cores": "50",
                    "gpu_count": "2",
                    "gpu_memory_gb": "32.0",
                    "memory_gb": "128.0",
                    "disk_gb": "0.0",
                    "concurrent_tasks": "10",
                    "tasks_per_day": "100",
                    "gpu_hours_per_day": "48.0",
                    "alert_threshold": "80",
                    "parent_quota_id": "global-1",
                    "is_active": "1",
                    "created_at": "2026-01-01T00:00:00",
                    "updated_at": "2026-01-01T00:00:00",
                }
            elif "global-1" in key:
                return {
                    "scope": QuotaScope.GLOBAL,
                    "scope_id": "global",
                    "name": "Global",
                    "cpu_cores": "100",
                    "gpu_count": "4",
                    "gpu_memory_gb": "64.0",
                    "memory_gb": "256.0",
                    "disk_gb": "0.0",
                    "concurrent_tasks": "10",
                    "tasks_per_day": "100",
                    "gpu_hours_per_day": "48.0",
                    "alert_threshold": "80",
                    "parent_quota_id": "",
                    "is_active": "1",
                    "created_at": "2026-01-01T00:00:00",
                    "updated_at": "2026-01-01T00:00:00",
                }
            return {}

        mock_redis.hgetall.side_effect = mock_hgetall

        is_valid, errors = store.validate_inheritance_chain("user-1")
        assert is_valid
        assert len(errors) == 0

