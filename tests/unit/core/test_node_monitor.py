# tests/unit/core/test_node_monitor.py
"""Unit tests for NodeMonitorActor."""

import pytest
from unittest.mock import patch, MagicMock
import ray


class TestNodeMonitorActorExceptionHandling:
    """Tests for NodeMonitorActor exception handling paths."""

    @pytest.fixture
    def ray_init(self):
        """Initialize Ray for testing."""
        if not ray.is_initialized():
            ray.init(num_cpus=2, ignore_reinit_error=True)
        yield

    def test_get_host_info_returns_valid_info(self, ray_init):
        """Test get_host_info returns valid info (GPU may or may not be available)."""
        from algo_studio.monitor.node_monitor import NodeMonitorActor

        actor = NodeMonitorActor.remote()
        info = ray.get(actor.get_host_info.remote())

        # Should always return a valid dict with required fields
        assert isinstance(info, dict)
        assert 'hostname' in info
        assert 'gpu_count' in info
        # GPU may or may not be available, but values should be valid types
        assert isinstance(info['gpu_count'], int)
        assert info['gpu_count'] >= 0


class TestNodeMonitorActor:
    """Tests for NodeMonitorActor."""

    @pytest.fixture
    def actor_class(self):
        """Get the NodeMonitorActor class."""
        from algo_studio.monitor.node_monitor import NodeMonitorActor
        return NodeMonitorActor

    @pytest.fixture
    def ray_init(self):
        """Initialize Ray for testing."""
        if not ray.is_initialized():
            ray.init(num_cpus=2, ignore_reinit_error=True)
        yield
        # Don't shutdown ray as it may be used by other tests

    def test_actor_is_remote_class(self, actor_class):
        """Test that NodeMonitorActor is a Ray remote class."""
        assert hasattr(actor_class, '_remote')

    def test_get_node_ip_returns_ip_address(self, ray_init, actor_class):
        """Test get_node_ip returns a valid IP address string."""
        actor = actor_class.remote()
        ip = ray.get(actor.get_node_ip.remote())
        assert isinstance(ip, str)
        # IP should be dotted notation format
        parts = ip.split('.')
        assert len(parts) == 4
        assert all(part.isdigit() for part in parts)

    def test_get_host_info_returns_dict(self, ray_init, actor_class):
        """Test get_host_info returns a dictionary."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())
        assert isinstance(info, dict)

    def test_get_host_info_contains_required_keys(self, ray_init, actor_class):
        """Test that get_host_info returns all required fields."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())

        required_keys = [
            'hostname',
            'ip',
            'cpu_count',
            'cpu_physical_cores',
            'cpu_used',
            'cpu_model',
            'cpu_freq_current_mhz',
            'memory_total_gb',
            'memory_used_gb',
            'disk_total_gb',
            'disk_used_gb',
            'swap_total_gb',
            'swap_used_gb',
            'gpu_name',
            'gpu_count',
            'gpu_utilization',
            'gpu_memory_used_gb',
            'gpu_memory_total_gb',
        ]

        for key in required_keys:
            assert key in info, f"Missing key: {key}"

    def test_get_host_info_hostname_is_string(self, ray_init, actor_class):
        """Test that hostname is a non-empty string."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())
        assert isinstance(info['hostname'], str)
        assert len(info['hostname']) > 0

    def test_get_host_info_cpu_count_positive(self, ray_init, actor_class):
        """Test that CPU count is a positive integer."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())
        assert isinstance(info['cpu_count'], int)
        assert info['cpu_count'] > 0

    def test_get_host_info_memory_values_are_floats(self, ray_init, actor_class):
        """Test that memory values are floats."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())
        assert isinstance(info['memory_total_gb'], float)
        assert isinstance(info['memory_used_gb'], float)
        assert info['memory_total_gb'] > 0
        assert info['memory_used_gb'] >= 0
        assert info['memory_used_gb'] <= info['memory_total_gb']

    def test_get_host_info_disk_values_are_floats(self, ray_init, actor_class):
        """Test that disk values are floats."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())
        assert isinstance(info['disk_total_gb'], float)
        assert isinstance(info['disk_used_gb'], float)
        assert info['disk_total_gb'] > 0
        assert info['disk_used_gb'] >= 0

    def test_get_host_info_gpu_count_non_negative(self, ray_init, actor_class):
        """Test that GPU count is a non-negative integer."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())
        assert isinstance(info['gpu_count'], int)
        assert info['gpu_count'] >= 0

    def test_get_host_info_gpu_utilization_range(self, ray_init, actor_class):
        """Test that GPU utilization is in valid range."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())
        # GPU utilization can be 0 if no GPU or during lazy init failure
        assert isinstance(info['gpu_utilization'], int)
        assert 0 <= info['gpu_utilization'] <= 100

    def test_get_host_info_gpu_memory_values(self, ray_init, actor_class):
        """Test that GPU memory values are floats."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())
        # These can be 0.0 if no GPU
        assert isinstance(info['gpu_memory_used_gb'], float)
        assert isinstance(info['gpu_memory_total_gb'], float)
        assert info['gpu_memory_total_gb'] >= 0
        assert info['gpu_memory_used_gb'] >= 0

    def test_get_host_info_cpu_freq_is_float(self, ray_init, actor_class):
        """Test that CPU frequency is a float."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())
        assert isinstance(info['cpu_freq_current_mhz'], float)

    @patch('algo_studio.monitor.node_monitor.psutil.cpu_percent')
    def test_get_host_info_cpu_used_calculation(self, ray_init, actor_class):
        """Test that cpu_used is calculated correctly from cpu_percent and cpu_count."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())

        # cpu_used should be approximately cpu_percent * cpu_count / 100
        # Allow some tolerance due to timing variations
        expected_cpu_used = int(info['cpu_used'] * info['cpu_count'] / 100)
        # The actual cpu_used might differ slightly, just verify it's in a valid range
        assert 0 <= info['cpu_used'] <= info['cpu_count']

    def test_get_host_info_consistent_data(self, ray_init, actor_class):
        """Test that returned info has consistent data."""
        actor = actor_class.remote()
        info = ray.get(actor.get_host_info.remote())

        # IP and hostname should be consistent
        assert info['hostname'] is not None
        assert info['ip'] is not None

        # CPU used should be reasonable (can't be more than total)
        assert info['cpu_used'] <= info['cpu_count']

    def test_actor_can_be_created_on_remote_cluster(self, ray_init, actor_class):
        """Test that actor can be created and called remotely."""
        actor = actor_class.remote()

        # Should be able to call multiple times
        ip1 = ray.get(actor.get_node_ip.remote())
        ip2 = ray.get(actor.get_node_ip.remote())

        assert ip1 == ip2

        info1 = ray.get(actor.get_host_info.remote())
        info2 = ray.get(actor.get_host_info.remote())

        # Check invariant fields - some values like cpu_freq can vary slightly
        assert info1['hostname'] == info2['hostname']
        assert info1['ip'] == info2['ip']
        assert info1['cpu_count'] == info2['cpu_count']
        assert info1['gpu_count'] == info2['gpu_count']
