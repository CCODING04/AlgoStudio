# tests/test_host_monitor.py
import pytest
from algo_studio.monitor.host_monitor import HostMonitor, HostInfo

def test_host_info_dataclass():
    info = HostInfo(
        hostname="worker-1",
        ip="192.168.0.101",
        cpu_count=24,
        cpu_used=8,
        memory_total_gb=31,
        memory_used_gb=16,
        gpu_name="RTX 4090",
        gpu_count=1,
        gpu_used=0,
        disk_total_gb=1800,
        disk_used_gb=320,
        swap_total_gb=15,
        swap_used_gb=1
    )
    assert info.hostname == "worker-1"
    assert info.cpu_available == 16
    assert info.gpu_available == 1

def test_host_monitor_initialization():
    monitor = HostMonitor()
    assert monitor is not None