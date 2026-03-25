# src/algo_studio/api/routes/tasks.py
from fastapi import APIRouter, HTTPException
from algo_studio.api.models import TaskCreateRequest, TaskResponse, TaskListResponse
from algo_studio.core.task import TaskManager, TaskType, TaskStatus
from algo_studio.core.ray_client import RayClient

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# 全局任务管理器实例
task_manager = TaskManager()
ray_client = RayClient()


@router.post("", response_model=TaskResponse)
async def create_task(request: TaskCreateRequest):
    """创建新任务"""
    try:
        task_type = TaskType(request.task_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid task_type: {request.task_type}")

    task = task_manager.create_task(
        task_type=task_type,
        algorithm_name=request.algorithm_name,
        algorithm_version=request.algorithm_version,
        config=request.config
    )

    return TaskResponse(
        task_id=task.task_id,
        task_type=task.task_type.value,
        algorithm_name=task.algorithm_name,
        algorithm_version=task.algorithm_version,
        status=task.status.value,
        created_at=task.created_at.isoformat(),
        assigned_node=task.assigned_node
    )


@router.get("", response_model=TaskListResponse)
async def list_tasks(status: str | None = None):
    """列出所有任务"""
    filter_status = None
    if status:
        try:
            filter_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    tasks = task_manager.list_tasks(status=filter_status)
    return TaskListResponse(
        tasks=[
            TaskResponse(
                task_id=t.task_id,
                task_type=t.task_type.value,
                algorithm_name=t.algorithm_name,
                algorithm_version=t.algorithm_version,
                status=t.status.value,
                created_at=t.created_at.isoformat(),
                assigned_node=t.assigned_node
            )
            for t in tasks
        ],
        total=len(tasks)
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """获取指定任务"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return TaskResponse(
        task_id=task.task_id,
        task_type=task.task_type.value,
        algorithm_name=t.algorithm_name,
        algorithm_version=t.algorithm_version,
        status=t.status.value,
        created_at=t.created_at.isoformat(),
        assigned_node=t.assigned_node
    )


@router.post("/{task_id}/dispatch")
async def dispatch_task(task_id: str):
    """分发任务到 Ray 集群执行"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    if task.status != TaskStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Task already dispatched, status: {task.status.value}")

    success = task_manager.dispatch_task(task_id, ray_client)
    if not success:
        raise HTTPException(status_code=503, detail="No available nodes or dispatch failed")

    task = task_manager.get_task(task_id)
    return {
        "task_id": task.task_id,
        "status": task.status.value,
        "assigned_node": task.assigned_node,
        "message": "Task dispatched successfully"
    }