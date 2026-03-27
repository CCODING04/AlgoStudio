# tests/factories/node_factory.py
"""Node data factory using factory-boy pattern."""

import factory
from faker import Faker
from enum import Enum

fake = Faker()


class NodeStatusEnum(Enum):
    IDLE = "idle"
    BUSY = "busy"
    UNKNOWN = "unknown"


class NodeFactory(factory.DictFactory):
    """Factory for generating Node test data dictionaries."""

    node_id = factory.LazyFunction(lambda: f"node-{fake.uuid4()[:8]}")
    hostname = factory.Faker("random_element", elements=["worker-1", "worker-2", "gpu-server-1"])
    ip = factory.Faker("ipv4")
    status = "idle"
    gpu_available = factory.LazyFunction(lambda: fake.random_int(0, 4))
    gpu_total = 4
    cpu_cores = factory.LazyFunction(lambda: fake.random_int(4, 32))
    memory_total = factory.LazyFunction(lambda: fake.random_int(16, 128))
    memory_available = factory.LazyFunction(lambda: fake.random_int(4, 64))


class IdleNodeFactory(NodeFactory):
    """Factory for idle nodes with available GPU."""
    status = "idle"
    gpu_available = factory.LazyFunction(lambda: fake.random_int(1, 4))


class BusyNodeFactory(NodeFactory):
    """Factory for busy nodes with no available GPU."""
    status = "busy"
    gpu_available = 0


class GPUNodeFactory(NodeFactory):
    """Factory for GPU nodes."""
    gpu_total = factory.LazyFunction(lambda: fake.random_int(1, 8))
    gpu_available = factory.LazyFunction(lambda: fake.random_int(0, 4))


class HostInfoFactory(factory.DictFactory):
    """Factory for host info data from NodeMonitorActor."""

    hostname = factory.Faker("hostname")
    ip = factory.Faker("ipv4")
    gpu_count = factory.LazyFunction(lambda: fake.random_int(1, 8))
    gpu_name = factory.Faker("random_element", elements=["NVIDIA RTX 4090", "NVIDIA A100", "NVIDIA V100"])
    gpu_memory_total = 24 * 1024  # MB
    gpu_memory_available = factory.LazyFunction(lambda: fake.random_int(0, 24) * 1024)
    cpu_count = factory.LazyFunction(lambda: fake.random_int(4, 32))
    memory_total = factory.LazyFunction(lambda: fake.random_int(16, 128) * 1024)
    memory_available = factory.LazyFunction(lambda: fake.random_int(4, 64) * 1024)
    disk_total = factory.LazyFunction(lambda: fake.random_int(256, 1024) * 1024)
    disk_available = factory.LazyFunction(lambda: fake.random_int(128, 512) * 1024)
