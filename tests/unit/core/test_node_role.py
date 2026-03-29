# tests/unit/core/test_node_role.py
"""Unit tests for node role determination and role-aware scheduling."""

import pytest
from unittest.mock import MagicMock

from algo_studio.core.ray_client import (
    determine_node_role,
    get_default_node_labels,
    NodeStatus,
)


class TestDetermineNodeRole:
    """Tests for determine_node_role function."""

    def test_same_ip_returns_head(self):
        """Test that same IP as head returns 'head'."""
        result = determine_node_role("192.168.0.126", "192.168.0.126")
        assert result == "head"

    def test_different_ip_returns_worker(self):
        """Test that different IP from head returns 'worker'."""
        result = determine_node_role("192.168.0.115", "192.168.0.126")
        assert result == "worker"

    def test_empty_node_ip_returns_worker(self):
        """Test that empty node_ip returns 'worker'."""
        result = determine_node_role("", "192.168.0.126")
        assert result == "worker"

    def test_empty_head_ip_returns_worker(self):
        """Test that empty head_ip returns 'worker'."""
        result = determine_node_role("192.168.0.126", "")
        assert result == "worker"

    def test_none_node_ip_returns_worker(self):
        """Test that None node_ip returns 'worker'."""
        result = determine_node_role(None, "192.168.0.126")
        assert result == "worker"

    def test_none_head_ip_returns_worker(self):
        """Test that None head_ip returns 'worker'."""
        result = determine_node_role("192.168.0.126", None)
        assert result == "worker"

    def test_both_none_returns_worker(self):
        """Test that both None returns 'worker'."""
        result = determine_node_role(None, None)
        assert result == "worker"

    def test_localhost_different_from_head(self):
        """Test localhost vs head IP."""
        result = determine_node_role("127.0.0.1", "192.168.0.126")
        assert result == "worker"


class TestGetDefaultNodeLabels:
    """Tests for get_default_node_labels function."""

    def test_head_labels(self):
        """Test default labels for head node."""
        labels = get_default_node_labels("head")
        assert "head" in labels
        assert "management" in labels
        assert "gpu" in labels

    def test_worker_labels(self):
        """Test default labels for worker node."""
        labels = get_default_node_labels("worker")
        assert "worker" in labels
        assert "gpu" in labels
        assert "management" not in labels

    def test_labels_are_set(self):
        """Test that returned labels are a set."""
        labels = get_default_node_labels("head")
        assert isinstance(labels, set)


class TestNodeStatusRoleAndLabels:
    """Tests for NodeStatus role and labels functionality."""

    def test_is_head_true_when_role_is_head(self):
        """Test is_head returns True when role is 'head'."""
        node = NodeStatus(
            node_id="node-1",
            ip="192.168.0.126",
            status="idle",
            cpu_used=0,
            cpu_total=8,
            gpu_used=0,
            gpu_total=1,
            memory_used_gb=0.0,
            memory_total_gb=32.0,
            disk_used_gb=0.0,
            disk_total_gb=100.0,
            role="head",
        )
        assert node.is_head() is True
        assert node.is_worker() is False

    def test_is_worker_true_when_role_is_worker(self):
        """Test is_worker returns True when role is 'worker'."""
        node = NodeStatus(
            node_id="node-1",
            ip="192.168.0.115",
            status="idle",
            cpu_used=0,
            cpu_total=8,
            gpu_used=0,
            gpu_total=1,
            memory_used_gb=0.0,
            memory_total_gb=32.0,
            disk_used_gb=0.0,
            disk_total_gb=100.0,
            role="worker",
        )
        assert node.is_worker() is True
        assert node.is_head() is False

    def test_has_label_true_when_present(self):
        """Test has_label returns True when label is present."""
        node = NodeStatus(
            node_id="node-1",
            ip="192.168.0.126",
            status="idle",
            cpu_used=0,
            cpu_total=8,
            gpu_used=0,
            gpu_total=1,
            memory_used_gb=0.0,
            memory_total_gb=32.0,
            disk_used_gb=0.0,
            disk_total_gb=100.0,
            role="head",
            labels={"head", "gpu", "training"},
        )
        assert node.has_label("gpu") is True
        assert node.has_label("training") is True
        assert node.has_label("worker") is False

    def test_has_label_false_when_not_present(self):
        """Test has_label returns False when label is not present."""
        node = NodeStatus(
            node_id="node-1",
            ip="192.168.0.115",
            status="idle",
            cpu_used=0,
            cpu_total=8,
            gpu_used=0,
            gpu_total=1,
            memory_used_gb=0.0,
            memory_total_gb=32.0,
            disk_used_gb=0.0,
            disk_total_gb=100.0,
            role="worker",
            labels={"worker", "gpu"},
        )
        assert node.has_label("worker") is True
        assert node.has_label("nonexistent") is False

    def test_default_role_is_worker(self):
        """Test that default role is 'worker' when not specified."""
        node = NodeStatus(
            node_id="node-1",
            ip="192.168.0.115",
            status="idle",
            cpu_used=0,
            cpu_total=8,
            gpu_used=0,
            gpu_total=1,
            memory_used_gb=0.0,
            memory_total_gb=32.0,
            disk_used_gb=0.0,
            disk_total_gb=100.0,
        )
        assert node.role == "worker"
        assert node.is_worker() is True

    def test_default_labels_is_empty_set(self):
        """Test that default labels is empty set when not specified."""
        node = NodeStatus(
            node_id="node-1",
            ip="192.168.0.115",
            status="idle",
            cpu_used=0,
            cpu_total=8,
            gpu_used=0,
            gpu_total=1,
            memory_used_gb=0.0,
            memory_total_gb=32.0,
            disk_used_gb=0.0,
            disk_total_gb=100.0,
        )
        assert node.labels == set()
        assert len(node.labels) == 0
