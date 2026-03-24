# tests/test_task.py
import pytest
from algo_studio.core.task import Task, TaskStatus, TaskType, TaskManager

def test_task_dataclass():
    task = Task(
        task_id="task-001",
        task_type=TaskType.TRAIN,
        algorithm_name="yolo",
        algorithm_version="v1.0.0",
        status=TaskStatus.PENDING
    )
    assert task.task_id == "task-001"
    assert task.task_type == TaskType.TRAIN
    assert task.status == TaskStatus.PENDING

def test_task_status_enum():
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.RUNNING.value == "running"
    assert TaskStatus.COMPLETED.value == "completed"
    assert TaskStatus.FAILED.value == "failed"