# tests/test_ray_client.py
import pytest
from unittest.mock import patch, MagicMock
from algo_studio.core.ray_client import RayClient, NodeStatus

def test_node_status_dataclass():
    status = NodeStatus(
        node_id="worker-1",
        ip="192.168.0.101",
        status="idle",
        cpu_used=8,
        cpu_total=24,
        gpu_used=0,
        gpu_total=1,
        memory_used_gb=16,
        memory_total_gb=31,
        disk_used_gb=320,
        disk_total_gb=1800
    )
    assert status.node_id == "worker-1"
    assert status.status == "idle"
    assert status.gpu_available

def test_ray_client_initialization():
    with patch("algo_studio.core.ray_client.ray") as mock_ray:
        client = RayClient()
        assert client.head_address is None