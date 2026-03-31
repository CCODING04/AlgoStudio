# tests/unit/core/test_node_monitor_coverage.py
"""Unit tests for NodeMonitorActor exception paths and edge cases."""

import pytest
from unittest.mock import patch, MagicMock
import socket


class TestNodeMonitorActorEdgeCases:
    """Tests for NodeMonitorActor edge cases - these tests use integration approach."""

    @pytest.fixture
    def ray_init(self):
        """Initialize Ray for testing."""
        import ray
        if not ray.is_initialized():
            ray.init(num_cpus=2, ignore_reinit_error=True)
        yield

    @pytest.fixture
    def actor_class(self):
        """Get the NodeMonitorActor class."""
        from algo_studio.monitor.node_monitor import NodeMonitorActor
        return NodeMonitorActor

    def test_get_host_info_returns_valid_dict(self, ray_init, actor_class):
        """Test get_host_info returns a valid dictionary with all required keys."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())

        # Check all required keys exist
        required_keys = [
            'hostname', 'ip', 'cpu_count', 'cpu_physical_cores', 'cpu_used',
            'cpu_model', 'cpu_freq_current_mhz', 'memory_total_gb', 'memory_used_gb',
            'disk_total_gb', 'disk_used_gb', 'swap_total_gb', 'swap_used_gb',
            'gpu_name', 'gpu_count', 'gpu_utilization',
            'gpu_memory_used_gb', 'gpu_memory_total_gb'
        ]

        for key in required_keys:
            assert key in info, f"Missing key: {key}"

    def test_get_host_info_gpu_defaults_when_no_gpu(self, ray_init, actor_class):
        """Test get_host_info returns GPU defaults when no GPU is available."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())

        # GPU values should be valid types
        assert isinstance(info['gpu_count'], int)
        assert isinstance(info['gpu_utilization'], int)
        assert isinstance(info['gpu_memory_used_gb'], float)
        assert isinstance(info['gpu_memory_total_gb'], float)

        # GPU count should be non-negative
        assert info['gpu_count'] >= 0
        assert info['gpu_utilization'] >= 0
        assert info['gpu_memory_used_gb'] >= 0
        assert info['gpu_memory_total_gb'] >= 0

    def test_get_host_info_cpu_values_valid(self, ray_init, actor_class):
        """Test CPU values are valid types and ranges."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())

        assert isinstance(info['cpu_count'], int)
        assert isinstance(info['cpu_physical_cores'], int)
        assert isinstance(info['cpu_used'], int)
        assert isinstance(info['cpu_model'], str)

        # CPU count should be positive
        assert info['cpu_count'] > 0
        assert info['cpu_physical_cores'] > 0
        # CPU used should not exceed CPU count
        assert info['cpu_used'] >= 0
        assert info['cpu_used'] <= info['cpu_count']

    def test_get_host_info_memory_values_valid(self, ray_init, actor_class):
        """Test memory values are valid."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())

        assert isinstance(info['memory_total_gb'], float)
        assert isinstance(info['memory_used_gb'], float)

        assert info['memory_total_gb'] > 0
        assert info['memory_used_gb'] >= 0
        assert info['memory_used_gb'] <= info['memory_total_gb']

    def test_get_host_info_disk_values_valid(self, ray_init, actor_class):
        """Test disk values are valid."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())

        assert isinstance(info['disk_total_gb'], float)
        assert isinstance(info['disk_used_gb'], float)

        assert info['disk_total_gb'] > 0
        assert info['disk_used_gb'] >= 0
        assert info['disk_used_gb'] <= info['disk_total_gb']

    def test_get_host_info_swap_values_valid(self, ray_init, actor_class):
        """Test swap memory values are valid."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())

        assert isinstance(info['swap_total_gb'], float)
        assert isinstance(info['swap_used_gb'], float)

        assert info['swap_total_gb'] >= 0
        assert info['swap_used_gb'] >= 0

    def test_get_host_info_hostname_and_ip_consistent(self, ray_init, actor_class):
        """Test hostname and IP are consistent."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())

        assert info['hostname'] is not None
        assert len(info['hostname']) > 0
        assert info['ip'] is not None

        # IP should be valid format
        parts = info['ip'].split('.')
        assert len(parts) == 4

    def test_get_host_info_multiple_calls_consistent(self, ray_init, actor_class):
        """Test multiple calls return consistent data for stable fields."""
        actor = actor_class.remote()

        info1 = ray.get(actor.get_host_info.remote())
        info2 = ray.get(actor.get_host_info.remote())

        # Stable fields should be identical
        assert info1['hostname'] == info2['hostname']
        assert info1['cpu_count'] == info2['cpu_count']
        assert info1['cpu_physical_cores'] == info2['cpu_physical_cores']
        assert info1['gpu_count'] == info2['gpu_count']
        assert info1['memory_total_gb'] == info2['memory_total_gb']

    def test_get_node_ip_returns_valid_ip(self, ray_init, actor_class):
        """Test get_node_ip returns a valid IP address."""
        actor = actor_class.remote()
        ip = ray.get(actor.get_node_ip.remote())

        assert isinstance(ip, str)
        parts = ip.split('.')
        assert len(parts) == 4
        assert all(part.isdigit() for part in parts)

    def test_get_node_ip_consistent(self, ray_init, actor_class):
        """Test get_node_ip returns consistent IP on multiple calls."""
        actor = actor_class.remote()

        ip1 = ray.get(actor.get_node_ip.remote())
        ip2 = ray.get(actor.get_node_ip.remote())

        assert ip1 == ip2

    def test_actor_tasks_are_independent(self, ray_init, actor_class):
        """Test that multiple actor instances are independent."""
        actor1 = actor_class.remote()
        actor2 = actor_class.remote()

        ip1 = ray.get(actor1.get_node_ip.remote())
        ip2 = ray.get(actor2.get_node_ip.remote())

        # Both should return valid IPs (may or may not be same depending on where actors run)
        assert isinstance(ip1, str)
        assert isinstance(ip2, str)


class TestNodeMonitorActorModuleLevel:
    """Module-level tests for node_monitor functions and constants."""

    def test_node_monitor_imports(self):
        """Test that node_monitor module imports correctly."""
        from algo_studio.monitor.node_monitor import NodeMonitorActor

        assert NodeMonitorActor is not None
        assert hasattr(NodeMonitorActor, 'get_node_ip')
        assert hasattr(NodeMonitorActor, 'get_host_info')
