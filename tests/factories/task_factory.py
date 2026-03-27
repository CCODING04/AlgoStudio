# tests/factories/task_factory.py
"""Task data factory using factory-boy pattern."""

import factory
from faker import Faker
from datetime import datetime
from enum import Enum

fake = Faker()


class TaskTypeEnum(Enum):
    TRAIN = "train"
    INFER = "infer"
    VERIFY = "verify"


class TaskStatusEnum(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskFactory(factory.DictFactory):
    """Factory for generating Task test data dictionaries."""

    task_id = factory.LazyFunction(lambda: f"task-{fake.uuid4()[:8]}")
    task_type = factory.Faker("random_element", elements=["train", "infer", "verify"])
    algorithm_name = factory.Faker("random_element", elements=["simple_classifier", "simple_detector", "yolo"])
    algorithm_version = factory.Faker("random_element", elements=["v1", "v2", "v1.0.0"])
    status = "pending"
    config = factory.LazyFunction(lambda: {"epochs": fake.random_int(10, 100), "batch_size": fake.random_int(8, 64)})
    progress = 0
    created_at = factory.LazyFunction(lambda: datetime.now().isoformat())
    started_at = None
    completed_at = None
    assigned_node = None
    error = None


class TaskCreateRequestFactory(factory.DictFactory):
    """Factory for generating task creation request data."""

    task_type = factory.Faker("random_element", elements=["train", "infer", "verify"])
    algorithm_name = factory.Faker("random_element", elements=["simple_classifier", "simple_detector"])
    algorithm_version = "v1"
    config = factory.LazyFunction(lambda: {"epochs": 100, "batch_size": 32})


class TaskResponseFactory(factory.DictFactory):
    """Factory for generating task response data."""

    task_id = factory.LazyFunction(lambda: f"task-{fake.uuid4()[:8]}")
    task_type = factory.Faker("random_element", elements=["train", "infer", "verify"])
    algorithm_name = "simple_classifier"
    algorithm_version = "v1"
    status = factory.Faker("random_element", elements=["pending", "running", "completed", "failed"])
    created_at = factory.LazyFunction(lambda: datetime.now().isoformat())
    started_at = None
    completed_at = None
    assigned_node = None
    error = None
    progress = factory.LazyFunction(lambda: fake.random_int(0, 100))


class PendingTaskFactory(TaskFactory):
    """Factory for pending tasks."""
    status = "pending"
    progress = 0


class RunningTaskFactory(TaskFactory):
    """Factory for running tasks."""
    status = "running"
    progress = factory.LazyFunction(lambda: fake.random_int(1, 99))
    started_at = factory.LazyFunction(lambda: datetime.now().isoformat())


class CompletedTaskFactory(TaskFactory):
    """Factory for completed tasks."""
    status = "completed"
    progress = 100
    started_at = factory.LazyFunction(lambda: datetime.now().isoformat())
    completed_at = factory.LazyFunction(lambda: datetime.now().isoformat())
    assigned_node = factory.Faker("random_element", elements=["worker-1", "worker-2", "192.168.0.115"])


class FailedTaskFactory(TaskFactory):
    """Factory for failed tasks."""
    status = "failed"
    error = factory.Faker("sentence")
    started_at = factory.LazyFunction(lambda: datetime.now().isoformat())
    completed_at = factory.LazyFunction(lambda: datetime.now().isoformat())
