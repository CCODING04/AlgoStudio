# tests/factories/deploy_factory.py
"""Deploy data factory using factory-boy pattern."""

import factory
from faker import Faker
from datetime import datetime
from enum import Enum

fake = Faker()


class DeployStatusEnum(Enum):
    """Deploy status values matching DeployStatus enum."""
    PENDING = "pending"
    CONNECTING = "connecting"
    DEPLOYING = "deploying"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeployWorkerRequestFactory(factory.DictFactory):
    """Factory for generating DeployWorkerRequest test data."""

    node_ip = factory.Faker("random_element", elements=["192.168.0.115", "192.168.0.126", "192.168.0.200"])
    username = factory.Faker("random_element", elements=["admin02", "admin10", "ubuntu"])
    password = factory.Faker("password", length=12)
    head_ip = factory.Faker("random_element", elements=["192.168.0.126", "192.168.0.100"])
    ray_port = factory.Faker("random_element", elements=[6379, 6380, 6379])
    proxy_url = None


class DeployProgressFactory(factory.DictFactory):
    """Factory for generating DeployProgress test data."""

    task_id = factory.LazyFunction(lambda: f"deploy-{fake.uuid4()[:8]}")
    status = factory.Faker("random_element", elements=["pending", "connecting", "deploying", "verifying", "completed", "failed"])
    step = factory.Faker("random_element", elements=["initializing", "connecting", "sudo_config", "create_venv", "install_deps", "sync_code", "start_ray", "verify"])
    step_index = factory.LazyFunction(lambda: fake.random_int(0, 7))
    total_steps = factory.LazyFunction(lambda: 7)
    progress = factory.LazyFunction(lambda: fake.random_int(0, 100))
    message = factory.Faker("sentence")
    error = None
    node_ip = factory.Faker("random_element", elements=["192.168.0.115", "192.168.0.126", "192.168.0.200"])
    started_at = factory.LazyFunction(lambda: datetime.now().isoformat())
    completed_at = None


class PendingDeployFactory(DeployProgressFactory):
    """Factory for pending deploy progress."""
    status = "pending"
    step = "initializing"
    step_index = 0
    progress = 0


class ConnectingDeployFactory(DeployProgressFactory):
    """Factory for connecting deploy progress."""
    status = "connecting"
    step = "connecting"
    step_index = 1
    progress = factory.LazyFunction(lambda: fake.random_int(1, 5))


class DeployingDeployFactory(DeployProgressFactory):
    """Factory for deploying deploy progress."""
    status = "deploying"
    step = factory.Faker("random_element", elements=["sudo_config", "create_venv", "install_deps", "sync_code", "start_ray"])
    progress = factory.LazyFunction(lambda: fake.random_int(10, 80))


class VerifyingDeployFactory(DeployProgressFactory):
    """Factory for verifying deploy progress."""
    status = "verifying"
    step = "verify"
    step_index = 7
    progress = factory.LazyFunction(lambda: fake.random_int(85, 95))


class CompletedDeployFactory(DeployProgressFactory):
    """Factory for completed deploy progress."""
    status = "completed"
    step = "verify"
    step_index = 7
    progress = 100
    message = "部署验证完成"
    completed_at = factory.LazyFunction(lambda: datetime.now().isoformat())


class FailedDeployFactory(DeployProgressFactory):
    """Factory for failed deploy progress."""
    status = "failed"
    progress = factory.LazyFunction(lambda: fake.random_int(5, 95))
    error = factory.Faker("sentence")
    completed_at = factory.LazyFunction(lambda: datetime.now().isoformat())
