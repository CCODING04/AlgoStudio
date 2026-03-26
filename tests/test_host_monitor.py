# tests/test_host_monitor.py
import pytest
from algo_studio.monitor.host_monitor import HostMonitor, HostInfo

def test_host_info_dataclass():
    info = HostInfo(
        hostname="worker-1",
        ip="192.168.0.101",
        cpu_count=24,
        cpu_physical_cores=12,
        cpu_used=8,
        cpu_model="Intel Xeon",
        cpu_freq_current_mhz=2400.0,
        memory_total_gb=31,
        memory_used_gb=16,
        gpu_name="RTX 4090",
        gpu_count=1,
        gpu_utilization=0,
        gpu_memory_used_gb=0.0,
        gpu_memory_total_gb=24.0,
        disk_total_gb=1800,
        disk_used_gb=320,
        swap_total_gb=15,
        swap_used_gb=1
    )
    assert info.hostname == "worker-1"
    assert info.cpu_available == 16
    assert info.gpu_available == 1  # gpu_utilization=0 means all 1 GPU available

def test_host_monitor_initialization():
    monitor = HostMonitor()
    assert monitor is not None