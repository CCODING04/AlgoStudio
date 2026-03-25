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
import os
import sys

# 算法基础路径 - 支持环境变量配置
# 默认使用 ~/Code/Dev/AlgoStudio/algorithms
import pathlib
_ALGO_STUDIO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
ALGORITHM_BASE_PATH = os.environ.get("ALGORITHM_BASE_PATH", str(_ALGO_STUDIO_ROOT / "algorithms"))


def _load_algorithm(algo_name: str, algo_version: str):
    """动态加载算法实例"""
    import importlib.util
    import os

    algo_path = os.path.join(ALGORITHM_BASE_PATH, algo_name, algo_version)

    # 添加算法目录到 sys.path
    sys.path.insert(0, algo_path)

    module_file = None

    # 查找算法实现文件
    for candidate in ["classifier.py", "detector.py", "model.py", "algorithm.py"]:
        candidate_path = os.path.join(algo_path, candidate)
        if os.path.exists(candidate_path):
            module_file = candidate_path
            break

    if not module_file:
        raise FileNotFoundError(f"Algorithm implementation not found in {algo_path}")

    # 动态加载模块
    spec = importlib.util.spec_from_file_location(f"{algo_name}.{algo_version}", module_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # 查找算法类（有 train, infer, verify, get_metadata 方法的类，排除数据类）
    exclude_names = {'TrainResult', 'InferenceResult', 'VerificationResult', 'AlgorithmMetadata'}
    for attr_name in dir(module):
        if attr_name in exclude_names:
            continue
        attr = getattr(module, attr_name)
        if (isinstance(attr, type) and
            callable(getattr(attr, 'train', None)) and
            callable(getattr(attr, 'infer', None)) and
            callable(getattr(attr, 'verify', None)) and
            callable(getattr(attr, 'get_metadata', None))):
            return attr()

    raise ValueError(f"No algorithm implementation found in {algo_path}")

    raise ValueError(f"No AlgorithmInterface implementation found in {algo_path}")


@ray.remote
def run_training(task_id: str, algo_name: str, algo_version: str, config: dict) -> dict:
    """Ray 训练任务"""
    try:
        algo = _load_algorithm(algo_name, algo_version)
        data_path = config.get("data_path", "")
        result = algo.train(data_path, config)

        return {
            "task_id": task_id,
            "status": "completed" if result.success else "failed",
            "success": result.success,
            "model_path": result.model_path,
            "metrics": result.metrics,
            "error": result.error
        }
    except Exception as e:
        return {"task_id": task_id, "status": "failed", "success": False, "error": str(e)}


@ray.remote
def run_inference(task_id: str, algo_name: str, algo_version: str, config: dict) -> dict:
    """Ray 推理任务"""
    try:
        algo = _load_algorithm(algo_name, algo_version)
        inputs = config.get("inputs", [])
        result = algo.infer(inputs)

        return {
            "task_id": task_id,
            "status": "completed" if result.success else "failed",
            "success": result.success,
            "outputs": result.outputs,
            "latency_ms": result.latency_ms,
            "error": result.error
        }
    except Exception as e:
        return {"task_id": task_id, "status": "failed", "success": False, "error": str(e)}


@ray.remote
def run_verification(task_id: str, algo_name: str, algo_version: str, config: dict) -> dict:
    """Ray 验证任务"""
    try:
        algo = _load_algorithm(algo_name, algo_version)
        test_data = config.get("test_data", "")
        result = algo.verify(test_data)

        return {
            "task_id": task_id,
            "status": "completed" if result.success else "failed",
            "success": result.success,
            "passed": result.passed,
            "metrics": result.metrics,
            "details": result.details
        }
    except Exception as e:
        return {"task_id": task_id, "status": "failed", "success": False, "error": str(e)}
