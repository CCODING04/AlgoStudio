# tests/integration/test_monitor_integration.py
"""Integration tests for Monitor module.

These tests verify the HostMonitor and NodeMonitor functionality.
"""

import pytest
import socket
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestHostMonitorIntegration:
    """Test suite for HostMonitor integration tests."""

    @pytest.fixture
    def host_monitor(self):
        """Provide a HostMonitor instance."""
        from algo_studio.monitor.host_monitor import HostMonitor
        return HostMonitor()

    def test_host_monitor_get_host_info_returns_valid_structure(self, host_monitor):
        """Test that get_host_info returns a valid HostInfo structure."""
        info = host_monitor.get_host_info()

        assert info.hostname is not None
        assert info.ip is not None
        assert info.cpu_count > 0
        assert info.cpu_physical_cores > 0
        assert info.memory_total_gb > 0
        assert info.memory_used_gb >= 0
        assert info.disk_total_gb > 0
        assert info.disk_used_gb >= 0

    def test_host_monitor_to_dict_returns_valid_structure(self, host_monitor):
        """Test that to_dict returns a valid dictionary structure."""
        result = host_monitor.to_dict()

        assert "hostname" in result
        assert "ip" in result
        assert "status" in result
        assert "resources" in result

        resources = result["resources"]
        assert "cpu" in resources
        assert "gpu" in resources
        assert "memory" in resources
        assert "disk" in resources
        assert "swap" in resources

    def test_host_monitor_cpu_resources(self, host_monitor):
        """Test CPU resource reporting."""
        info = host_monitor.get_host_info()

        assert info.cpu_count >= info.cpu_physical_cores
        assert info.cpu_used >= 0
        assert info.cpu_used <= info.cpu_count

    def test_host_monitor_memory_resources(self, host_monitor):
        """Test memory resource reporting."""
        info = host_monitor.get_host_info()

        assert info.memory_total_gb > 0
        assert info.memory_used_gb >= 0
        assert info.memory_used_gb <= info.memory_total_gb
        assert info.memory_available_gb >= 0
        assert info.memory_available_gb <= info.memory_total_gb

    def test_host_monitor_disk_resources(self, host_monitor):
        """Test disk resource reporting."""
        info = host_monitor.get_host_info()

        assert info.disk_total_gb > 0
        assert info.disk_used_gb >= 0
        assert info.disk_used_gb <= info.disk_total_gb

    def test_host_monitor_swap_resources(self, host_monitor):
        """Test swap resource reporting."""
        info = host_monitor.get_host_info()

        assert info.swap_total_gb >= 0
        assert info.swap_used_gb >= 0

    def test_host_monitor_gpu_available_property(self, host_monitor):
        """Test GPU available property calculation."""
        info = host_monitor.get_host_info()

        # GPU available should be calculated correctly
        if info.gpu_count > 0:
            expected_available = info.gpu_count - 1 if info.gpu_utilization > 0 else info.gpu_count
            assert info.gpu_available == expected_available

    def test_host_monitor_cpu_available_property(self, host_monitor):
        """Test CPU available property calculation."""
        info = host_monitor.get_host_info()

        expected_available = info.cpu_count - info.cpu_used
        assert info.cpu_available == expected_available

    def test_host_monitor_to_dict_resources_structure(self, host_monitor):
        """Test to_dict resources sub-structure."""
        result = host_monitor.to_dict()

        cpu = result["resources"]["cpu"]
        assert "total" in cpu
        assert "used" in cpu
        assert "physical_cores" in cpu

        gpu = result["resources"]["gpu"]
        assert "total" in gpu
        assert "utilization" in gpu

        memory = result["resources"]["memory"]
        assert "total" in memory
        assert "used" in memory

        disk = result["resources"]["disk"]
        assert "total" in disk
        assert "used" in disk


class TestHostMonitorWithMockedGPU:
    """Test suite for HostMonitor with mocked GPU state."""

    @pytest.fixture
    def host_monitor(self):
        from algo_studio.monitor.host_monitor import HostMonitor
        return HostMonitor()

    def test_host_monitor_handles_no_gpu(self, host_monitor):
        """Test host monitor behavior when no GPU is available."""
        with patch("algo_studio.monitor.host_monitor.GPU_AVAILABLE", False):
            info = host_monitor.get_host_info()

            # Should still return valid structure with no GPU info
            assert info.gpu_count == 0
            assert info.gpu_available == 0
            assert info.gpu_utilization == 0

    def test_host_monitor_to_dict_with_no_gpu(self, host_monitor):
        """Test to_dict when no GPU is available."""
        with patch("algo_studio.monitor.host_monitor.GPU_AVAILABLE", False):
            result = host_monitor.to_dict()

            assert result["resources"]["gpu"]["total"] == 0
            assert result["resources"]["gpu"]["name"] is None


class TestHostMonitorEdgeCases:
    """Test suite for HostMonitor edge cases."""

    @pytest.fixture
    def host_monitor(self):
        from algo_studio.monitor.host_monitor import HostMonitor
        return HostMonitor()

    def test_host_monitor_handles_zero_cpu_count(self, host_monitor):
        """Test host monitor with mocked zero CPU count."""
        with patch("psutil.cpu_count", return_value=0):
            info = host_monitor.get_host_info()
            # Should handle gracefully
            assert info.cpu_count >= 0

    def test_host_monitor_handles_zero_physical_cores(self, host_monitor):
        """Test host monitor with mocked zero physical cores."""
        with patch("psutil.cpu_count", logical=False, return_value=0):
            info = host_monitor.get_host_info()
            # Should still return valid structure
            assert info.cpu_physical_cores >= 0
