from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import uuid
from datetime import datetime
import ray

class TaskType(Enum):
    TRAIN = "train"
    INFER = "infer"
    VERIFY = "verify"

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Task:
    task_id: str
    task_type: TaskType
    algorithm_name: str
    algorithm_version: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    config: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    assigned_node: Optional[str] = None

    @staticmethod
    def create(task_type: TaskType, algorithm_name: str, algorithm_version: str, config: Dict) -> "Task":
        """创建新任务"""
        task_id = f"{task_type.value}-{uuid.uuid4().hex[:8]}"
        return Task(
            task_id=task_id,
            task_type=task_type,
            algorithm_name=algorithm_name,
            algorithm_version=algorithm_version,
            config=config
        )

class TaskManager:
    """任务管理器

    Phase 1: 使用内存存储（单实例部署）
    Phase 2: 集成 Redis/RQ 实现分布式任务队列
    """

    def __init__(self):
        self._tasks: Dict[str, Task] = {}

    def create_task(self, task_type: TaskType, algorithm_name: str, algorithm_version: str, config: Dict) -> Task:
        """创建并注册新任务"""
        task = Task.create(task_type, algorithm_name, algorithm_version, config)
        self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> Task | None:
        """获取任务"""
        return self._tasks.get(task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """列出任务"""
        if status:
            return [t for t in self._tasks.values() if t.status == status]
        return list(self._tasks.values())

    def update_status(self, task_id: str, status: TaskStatus, result: dict | None = None, error: str | None = None):
        """更新任务状态"""
        task = self._tasks.get(task_id)
        if task:
            task.status = status
            if status == TaskStatus.RUNNING:
                task.started_at = datetime.now()
            elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                task.completed_at = datetime.now()
            if result:
                task.result = result
            if error:
                task.error = error

    def dispatch_task(self, task_id: str, ray_client: "RayClient") -> bool:
        """将任务分发到 Ray 集群执行"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        # 获取空闲节点
        nodes = ray_client.get_nodes()
        idle_nodes = [n for n in nodes if n.status == "idle" and n.gpu_available > 0]

        if not idle_nodes:
            # 没有空闲 GPU 节点，尝试 CPU 节点
            idle_nodes = [n for n in nodes if n.status == "idle"]

        if not idle_nodes:
            return False

        # 选择第一个空闲节点
        selected_node = idle_nodes[0]
        task.assigned_node = selected_node.node_id

        # 更新状态为运行中
        self.update_status(task_id, TaskStatus.RUNNING)

        # 根据 task_type 提交到 Ray
        if task.task_type == TaskType.TRAIN:
            ray_client.submit_task(
                run_training,
                task.task_id,
                task.algorithm_name,
                task.algorithm_version,
                task.config,
                num_gpus=1
            )
        elif task.task_type == TaskType.INFER:
            ray_client.submit_task(
                run_inference,
                task.task_id,
                task.algorithm_name,
                task.algorithm_version,
                task.config,
                num_gpus=0
            )
        elif task.task_type == TaskType.VERIFY:
            ray_client.submit_task(
                run_verification,
                task.task_id,
                task.algorithm_name,
                task.algorithm_version,
                task.config,
                num_gpus=0
            )

        return True


# 训练/推理/验证的 Ray 任务函数
@ray.remote
def run_training(task_id: str, algo_name: str, algo_version: str, config: dict) -> dict:
    """Ray 训练任务"""
    return {"task_id": task_id, "status": "completed", "metrics": {"mAP": 0.0}}


@ray.remote
def run_inference(task_id: str, algo_name: str, algo_version: str, config: dict) -> dict:
    """Ray 推理任务"""
    return {"task_id": task_id, "status": "completed", "results": []}


@ray.remote
def run_verification(task_id: str, algo_name: str, algo_version: str, config: dict) -> dict:
    """Ray 验证任务"""
    return {"task_id": task_id, "status": "completed", "passed": True}
