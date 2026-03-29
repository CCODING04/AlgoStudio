# tests/unit/scheduler/test_role_aware_scheduling.py
"""Unit tests for role-aware scheduling in WFQScheduler."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from algo_studio.core.scheduler.wfq_scheduler import (
    WFQScheduler,
    FairSchedulingDecision,
)
from algo_studio.core.task import Task, TaskType, TaskStatus
from algo_studio.core.quota.manager import QuotaManager
from algo_studio.core.quota.store import ResourceQuota, SQLiteQuotaStore


class TestFairSchedulingDecisionRoleAware:
    """Tests for FairSchedulingDecision role-aware methods."""

    def _make_task(self, task_id, task_type=TaskType.TRAIN):
        """Create a task."""
        return Task(
            task_id=task_id,
            task_type=task_type,
            algorithm_name="test_algo",
            algorithm_version="v1",
        )

    def _make_decision(self, task, target_role=None, target_labels=None):
        """Create a scheduling decision."""
        return FairSchedulingDecision(
            decision_id="test-decision-001",
            task=task,
            selection_method="wfq",
            queue_path="global",
            target_role=target_role,
            target_labels=target_labels or [],
        )

    def test_requires_head_node_true_when_role_is_head(self):
        """Test requires_head_node returns True when target_role is 'head'."""
        task = self._make_task("task-001")
        decision = self._make_decision(task, target_role="head")
        assert decision.requires_head_node() is True
        assert decision.requires_worker_node() is False

    def test_requires_worker_node_true_when_role_is_worker(self):
        """Test requires_worker_node returns True when target_role is 'worker'."""
        task = self._make_task("task-001")
        decision = self._make_decision(task, target_role="worker")
        assert decision.requires_worker_node() is True
        assert decision.requires_head_node() is False

    def test_requires_head_worker_false_when_role_is_none(self):
        """Test requires_* returns False when target_role is None."""
        task = self._make_task("task-001")
        decision = self._make_decision(task, target_role=None)
        assert decision.requires_head_node() is False
        assert decision.requires_worker_node() is False

    def test_has_label_requirements_true_when_labels_set(self):
        """Test has_label_requirements returns True when labels are set."""
        task = self._make_task("task-001")
        decision = self._make_decision(task, target_labels=["gpu", "training"])
        assert decision.has_label_requirements() is True

    def test_has_label_requirements_false_when_labels_empty(self):
        """Test has_label_requirements returns False when labels are empty."""
        task = self._make_task("task-001")
        decision = self._make_decision(task, target_labels=[])
        assert decision.has_label_requirements() is False

    def test_matches_node_role_matches(self):
        """Test matches_node returns True when role matches."""
        task = self._make_task("task-001")
        decision = self._make_decision(task, target_role="head")
        assert decision.matches_node("head", ["head", "gpu"]) is True

    def test_matches_node_role_mismatch(self):
        """Test matches_node returns False when role doesn't match."""
        task = self._make_task("task-001")
        decision = self._make_decision(task, target_role="head")
        assert decision.matches_node("worker", ["worker", "gpu"]) is False

    def test_matches_node_role_any(self):
        """Test matches_node returns True when target_role is None (any)."""
        task = self._make_task("task-001")
        decision = self._make_decision(task, target_role=None)
        assert decision.matches_node("head", ["head", "gpu"]) is True
        assert decision.matches_node("worker", ["worker", "gpu"]) is True

    def test_matches_node_labels_all_present(self):
        """Test matches_node returns True when all required labels present."""
        task = self._make_task("task-001")
        decision = self._make_decision(task, target_labels=["gpu", "training"])
        assert decision.matches_node("worker", ["worker", "gpu", "training"]) is True

    def test_matches_node_labels_some_missing(self):
        """Test matches_node returns False when some labels missing."""
        task = self._make_task("task-001")
        decision = self._make_decision(task, target_labels=["gpu", "training"])
        assert decision.matches_node("worker", ["worker", "gpu"]) is False

    def test_matches_node_no_label_requirements(self):
        """Test matches_node returns True when no label requirements."""
        task = self._make_task("task-001")
        decision = self._make_decision(task, target_labels=[])
        assert decision.matches_node("worker", ["worker", "gpu"]) is True


class TestWFQSchedulerRoleAware:
    """Tests for WFQScheduler role-aware scheduling methods."""

    @pytest.fixture
    def quota_store(self, tmp_path):
        """Create an in-memory SQLite quota store for testing."""
        store = SQLiteQuotaStore(db_path=str(tmp_path / "test_quota.db"))
        store.create_quota({
            "quota_id": "global",
            "scope": "global",
            "scope_id": "global",
            "name": "Global Quota",
            "weight": 1.0,
            "guaranteed_gpu_count": 2,
            "guaranteed_cpu_cores": 8,
            "guaranteed_memory_gb": 32.0,
            "cpu_cores": 32,
            "gpu_count": 4,
            "memory_gb": 128.0,
        })
        return store

    @pytest.fixture
    def quota_manager(self, quota_store):
        """Create a QuotaManager with test store."""
        return QuotaManager(quota_store)

    @pytest.fixture
    def scheduler(self, quota_manager):
        """Create a WFQScheduler instance."""
        return WFQScheduler(quota_manager, total_cluster_gpu=4)

    def _make_node(self, ip, role="worker", labels=None, status="idle"):
        """Create a mock node."""
        node = MagicMock()
        node.ip = ip
        node.role = role
        node.labels = labels or set()
        node.status = status
        return node

    def test_filter_nodes_by_role_no_filter(self, scheduler):
        """Test filter_nodes_by_role returns all nodes when no requirements."""
        nodes = [
            self._make_node("192.168.0.126", "head"),
            self._make_node("192.168.0.115", "worker"),
        ]
        result = scheduler.filter_nodes_by_role(nodes)
        assert len(result) == 2

    def test_filter_nodes_by_role_head_only(self, scheduler):
        """Test filter_nodes_by_role returns only head nodes."""
        nodes = [
            self._make_node("192.168.0.126", "head"),
            self._make_node("192.168.0.115", "worker"),
        ]
        result = scheduler.filter_nodes_by_role(nodes, target_role="head")
        assert len(result) == 1
        assert result[0].role == "head"

    def test_filter_nodes_by_role_worker_only(self, scheduler):
        """Test filter_nodes_by_role returns only worker nodes."""
        nodes = [
            self._make_node("192.168.0.126", "head"),
            self._make_node("192.168.0.115", "worker"),
        ]
        result = scheduler.filter_nodes_by_role(nodes, target_role="worker")
        assert len(result) == 1
        assert result[0].role == "worker"

    def test_filter_nodes_by_role_with_labels(self, scheduler):
        """Test filter_nodes_by_role filters by labels."""
        nodes = [
            self._make_node("192.168.0.126", "head", {"head", "gpu", "training"}),
            self._make_node("192.168.0.115", "worker", {"worker", "gpu"}),
        ]
        result = scheduler.filter_nodes_by_role(
            nodes,
            target_labels=["gpu"],
        )
        assert len(result) == 2

    def test_filter_nodes_by_role_with_labels_and_role(self, scheduler):
        """Test filter_nodes_by_role filters by role AND labels."""
        nodes = [
            self._make_node("192.168.0.126", "head", {"head", "gpu", "training"}),
            self._make_node("192.168.0.115", "worker", {"worker", "gpu"}),
        ]
        result = scheduler.filter_nodes_by_role(
            nodes,
            target_role="head",
            target_labels=["training"],
        )
        assert len(result) == 1
        assert result[0].role == "head"

    def test_filter_nodes_by_role_empty_list(self, scheduler):
        """Test filter_nodes_by_role returns empty list for empty input."""
        result = scheduler.filter_nodes_by_role([])
        assert len(result) == 0

    def test_filter_nodes_by_role_no_match(self, scheduler):
        """Test filter_nodes_by_role returns empty list when no match."""
        nodes = [
            self._make_node("192.168.0.126", "head", {"head", "gpu"}),
        ]
        result = scheduler.filter_nodes_by_role(
            nodes,
            target_role="worker",
        )
        assert len(result) == 0

    def test_select_best_node_for_decision_idle_nodes_preferred(self, scheduler):
        """Test select_best_node_for_decision prefers idle nodes."""
        task = Task(
            task_id="task-001",
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
        )
        decision = FairSchedulingDecision(
            decision_id="test-decision-001",
            task=task,
        )

        idle_node = self._make_node("192.168.0.115", "worker", status="idle")
        busy_node = self._make_node("192.168.0.126", "head", status="busy")
        nodes = [busy_node, idle_node]

        result = scheduler.select_best_node_for_decision(nodes, decision)
        assert result == idle_node

    def test_select_best_node_for_decision_role_filter(self, scheduler):
        """Test select_best_node_for_decision filters by role."""
        task = Task(
            task_id="task-001",
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
        )
        decision = FairSchedulingDecision(
            decision_id="test-decision-001",
            task=task,
            target_role="head",
        )

        worker_node = self._make_node("192.168.0.115", "worker", status="idle")
        head_node = self._make_node("192.168.0.126", "head", status="idle")
        nodes = [worker_node, head_node]

        result = scheduler.select_best_node_for_decision(nodes, decision)
        assert result == head_node

    def test_select_best_node_for_decision_no_match(self, scheduler):
        """Test select_best_node_for_decision returns None when no match."""
        task = Task(
            task_id="task-001",
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
        )
        decision = FairSchedulingDecision(
            decision_id="test-decision-001",
            task=task,
            target_role="head",
        )

        worker_node = self._make_node("192.168.0.115", "worker", status="idle")
        nodes = [worker_node]

        result = scheduler.select_best_node_for_decision(nodes, decision)
        assert result is None

    def test_select_best_node_for_decision_label_filter(self, scheduler):
        """Test select_best_node_for_decision filters by labels."""
        task = Task(
            task_id="task-001",
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
        )
        decision = FairSchedulingDecision(
            decision_id="test-decision-001",
            task=task,
            target_labels=["training"],
        )

        node1 = self._make_node("192.168.0.115", "worker", {"worker", "gpu"})
        node2 = self._make_node("192.168.0.126", "worker", {"worker", "gpu", "training"})
        nodes = [node1, node2]

        result = scheduler.select_best_node_for_decision(nodes, decision)
        assert result == node2

    def test_create_decision_extracts_target_role_from_task(self, scheduler):
        """Test _create_decision extracts target_role from task."""
        task = Task(
            task_id="task-001",
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
        )
        # Add required attributes that WFQScheduler expects
        task.tenant_id = "team-001"
        task.user_id = "user-001"
        task.team_id = "team-001"
        task.target_role = "head"
        task.target_labels = ["training"]

        decision = scheduler._create_decision(
            task=task,
            queue_path="global",
            method="wfq",
        )

        assert decision.target_role == "head"
        assert decision.target_labels == ["training"]

    def test_create_decision_explicit_target_role_overrides_task(self, scheduler):
        """Test _create_decision explicit target_role overrides task attribute."""
        task = Task(
            task_id="task-001",
            task_type=TaskType.TRAIN,
            algorithm_name="test_algo",
            algorithm_version="v1",
        )
        # Add required attributes that WFQScheduler expects
        task.tenant_id = "team-001"
        task.user_id = "user-001"
        task.team_id = "team-001"
        task.target_role = "head"
        task.target_labels = ["training"]

        decision = scheduler._create_decision(
            task=task,
            queue_path="global",
            method="wfq",
            target_role="worker",
            target_labels=["inference"],
        )

        assert decision.target_role == "worker"
        assert decision.target_labels == ["inference"]
