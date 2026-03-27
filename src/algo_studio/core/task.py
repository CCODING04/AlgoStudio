from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple
import uuid
from datetime import datetime
import ray

from algo_studio.api.pagination import CursorParams, encode_cursor, decode_cursor


@ray.remote
class ProgressStore:
    """Ray Actor，共享进度存储"""

    def __init__(self):
        self._progress: Dict[str, int] = {}

    def update(self, task_id: str, current: int, total: int):
        """更新进度"""
        self._progress[task_id] = int((current / total) * 100) if total > 0 else 0

    def get(self, task_id: str) -> int:
        """获取进度"""
        return self._progress.get(task_id, 0)


# 全局进度存储 Actor
_progress_store_actor = None
_PROGRESS_STORE_NAME = "algo_studio_progress_store"


def get_progress_store() -> "ProgressStore":
    """获取或创建全局进度存储 Actor（使用固定名称确保跨进程获取同一实例）"""
    global _progress_store_actor
    if _progress_store_actor is None:
        try:
            _progress_store_actor = ray.get_actor(_PROGRESS_STORE_NAME, namespace="algo_studio")
        except Exception:
            # Actor 不存在，创建新的
            _progress_store_actor = ProgressStore.options(
                name=_PROGRESS_STORE_NAME,
                namespace="algo_studio",
                lifetime="detached"
            ).remote()
    return _progress_store_actor


@ray.remote
class ProgressReporter:
    """Ray Actor，用于向 TaskManager 报告进度"""

    def update_progress(self, task_id: str, current: int, total: int, description: str = ""):
        """更新任务进度"""
        print(f"[ProgressReporter] update_progress: task_id={task_id}, current={current}, total={total}, desc={description}")
        progress_store = get_progress_store()
        progress_store.update.remote(task_id, current, total)

    def get_progress(self, task_id: str) -> int:
        """获取任务进度"""
        progress_store = get_progress_store()
        return ray.get(progress_store.get.remote(task_id))

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
    progress: int = 0  # 0-100

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
        """获取任务（自动同步进度）"""
        task = self._tasks.get(task_id)
        if task:
            self.sync_progress(task_id)
        return task

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """列出任务"""
        if status:
            return [t for t in self._tasks.values() if t.status == status]
        return list(self._tasks.values())

    def list_tasks_paginated(
        self,
        status: TaskStatus | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> Tuple[list[Task], str | None]:
        """列出任务（游标分页）

        Args:
            status: Optional status filter
            cursor: Pagination cursor (base64 encoded)
            limit: Number of items per page (max 100)

        Returns:
            Tuple of (tasks, next_cursor)
            - tasks: List of tasks for current page
            - next_cursor: Cursor for next page (None if last page)
        """
        limit = min(limit, 100)  # Cap at 100

        # Get all tasks, sorted by created_at descending (newest first)
        all_tasks = self.list_tasks(status=status)
        all_tasks.sort(key=lambda t: t.created_at, reverse=True)

        # Decode cursor to get starting point
        start_idx = 0
        if cursor:
            try:
                decoded = decode_cursor(cursor)
                # Find the task with the cursor's sort value
                for i, t in enumerate(all_tasks):
                    if t.created_at.isoformat() == decoded.sort_value and t.task_id == decoded.id:
                        start_idx = i + 1
                        break
            except ValueError:
                pass  # Invalid cursor, start from beginning

        # Get page of tasks
        page_tasks = all_tasks[start_idx:start_idx + limit]

        # Determine next cursor
        next_cursor = None
        if len(all_tasks) > start_idx + limit:
            last_task = page_tasks[-1]
            next_cursor = encode_cursor(
                last_task.created_at.isoformat(),
                last_task.task_id
            )

        return page_tasks, next_cursor

    def update_status(self, task_id: str, status: TaskStatus, result: dict | None = None, error: str | None = None, progress: int | None = None):
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
            if error is not None:
                task.error = error
            if progress is not None:
                task.progress = progress

    def update_progress(self, task_id: str, progress: int, description: str = ""):
        """更新任务进度（由 ProgressReporter Actor 调用）"""
        task = self._tasks.get(task_id)
        if task:
            task.progress = progress
            # 可选：存储 description 用于显示

    def delete_task(self, task_id: str) -> bool:
        """删除指定任务"""
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    def sync_progress(self, task_id: str):
        """从共享存储同步进度"""
        task = self._tasks.get(task_id)
        if task:
            progress_store = get_progress_store()
            task.progress = ray.get(progress_store.get.remote(task_id))

    def dispatch_task(self, task_id: str, ray_client: "RayClient") -> bool:
        """将任务分发到 Ray 集群执行并等待结果"""
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
            # No nodes available - mark task as failed with appropriate error
            self.update_status(task_id, TaskStatus.FAILED, error="No available nodes in Ray cluster")
            return False

        # 选择第一个空闲节点
        selected_node = idle_nodes[0]
        # 优先使用 hostname，其次 ip，最后是 node_id
        task.assigned_node = selected_node.hostname or selected_node.ip or selected_node.node_id

        # 更新状态为运行中
        self.update_status(task_id, TaskStatus.RUNNING)

        # 创建 ProgressReporter Actor
        progress_reporter = ProgressReporter.remote()

        # 根据 task_type 提交到 Ray（使用 node_ip 确保在目标节点运行）
        try:
            if task.task_type == TaskType.TRAIN:
                result_ref = ray_client.submit_task(
                    run_training,
                    task.task_id,
                    task.algorithm_name,
                    task.algorithm_version,
                    task.config,
                    progress_reporter,
                    num_gpus=1,
                    node_ip=selected_node.ip
                )
            elif task.task_type == TaskType.INFER:
                result_ref = ray_client.submit_task(
                    run_inference,
                    task.task_id,
                    task.algorithm_name,
                    task.algorithm_version,
                    task.config,
                    progress_reporter,
                    num_gpus=0,
                    node_ip=selected_node.ip
                )
            elif task.task_type == TaskType.VERIFY:
                result_ref = ray_client.submit_task(
                    run_verification,
                    task.task_id,
                    task.algorithm_name,
                    task.algorithm_version,
                    task.config,
                    progress_reporter,
                    num_gpus=0,
                    node_ip=selected_node.ip
                )
            else:
                self.update_status(task_id, TaskStatus.FAILED, error=f"Unknown task type: {task.task_type}")
                return False
        except Exception as e:
            self.update_status(task_id, TaskStatus.FAILED, error=f"Failed to submit task: {str(e)}")
            return False

        # 等待 Ray 任务完成并更新状态
        try:
            result = ray.get(result_ref)
            if result.get("status") == "completed":
                self.update_status(task_id, TaskStatus.COMPLETED, result=result)
            else:
                self.update_status(task_id, TaskStatus.FAILED, error=result.get("error"))
        except Exception as e:
            self.update_status(task_id, TaskStatus.FAILED, error=str(e))

        # 清理 ProgressReporter Actor（成功或失败都要清理）
        finally:
            try:
                ray.kill(progress_reporter, no_restart=True)
            except:
                pass

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
    exclude_names = {'TrainResult', 'InferenceResult', 'VerificationResult', 'AlgorithmMetadata',
                      'NullProgressCallback', 'RayProgressCallback', 'ProgressReporter'}
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


class RayProgressCallback:
    """Ray 分布式进度回调，通过 ProgressReporter Actor 更新进度"""

    def __init__(self, task_id: str, reporter):
        self.task_id = task_id
        self.reporter = reporter

    def update(self, current: int, total: int, description: str = ""):
        """更新进度"""
        self.reporter.update_progress.remote(self.task_id, current, total, description)

    def set_description(self, description: str):
        """设置描述（暂不支持）"""
        pass


@ray.remote
def run_training(task_id: str, algo_name: str, algo_version: str, config: dict, progress_reporter=None) -> dict:
    """Ray 训练任务"""
    try:
        algo = _load_algorithm(algo_name, algo_version)
        data_path = config.get("data_path", "")

        # 创建进度回调
        if progress_reporter:
            progress_callback = RayProgressCallback(task_id, progress_reporter)
        else:
            # 使用空回调
            class NullCallback:
                def update(self, current, total, description=""): pass
                def set_description(self, description): pass
            progress_callback = NullCallback()

        result = algo.train(data_path, config, progress_callback)

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
def run_inference(task_id: str, algo_name: str, algo_version: str, config: dict, progress_reporter=None) -> dict:
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
def run_verification(task_id: str, algo_name: str, algo_version: str, config: dict, progress_reporter=None) -> dict:
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
