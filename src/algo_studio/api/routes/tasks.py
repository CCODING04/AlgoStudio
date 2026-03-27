# src/algo_studio/api/routes/tasks.py
from fastapi import APIRouter, HTTPException, Query
from algo_studio.api.models import TaskCreateRequest, TaskResponse, TaskListResponse, TaskPaginatedResponse
from algo_studio.core.task import TaskManager, TaskType, TaskStatus
from algo_studio.core.ray_client import RayClient
from algo_studio.api.middleware.rbac import require_permission, Permission

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
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        assigned_node=task.assigned_node,
        error=task.error,
        progress=task.progress
    )


@router.get("", response_model=TaskPaginatedResponse)
async def list_tasks(
    status: str | None = None,
    cursor: str | None = Query(default=None, description="Pagination cursor"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
):
    """列出所有任务（游标分页）

    使用游标分页替代传统的 offset/limit，支持高效翻页。
    返回 next_cursor 用于获取下一页。
    """
    filter_status = None
    if status:
        try:
            filter_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    tasks, next_cursor = task_manager.list_tasks_paginated(
        status=filter_status,
        cursor=cursor,
        limit=limit
    )

    task_responses = [
        TaskResponse(
            task_id=t.task_id,
            task_type=t.task_type.value,
            algorithm_name=t.algorithm_name,
            algorithm_version=t.algorithm_version,
            status=t.status.value,
            created_at=t.created_at.isoformat(),
            started_at=t.started_at.isoformat() if t.started_at else None,
            completed_at=t.completed_at.isoformat() if t.completed_at else None,
            assigned_node=t.assigned_node,
            error=t.error,
            progress=t.progress
        )
        for t in tasks
    ]

    return TaskPaginatedResponse(
        items=task_responses,
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
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
        algorithm_name=task.algorithm_name,
        algorithm_version=task.algorithm_version,
        status=task.status.value,
        created_at=task.created_at.isoformat(),
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        assigned_node=task.assigned_node,
        error=task.error,
        progress=task.progress
    )


@router.post("/{task_id}/dispatch")
async def dispatch_task(task_id: str):
    """分发任务到 Ray 集群执行（异步模式，立即返回）"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    if task.status != TaskStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Task already dispatched, status: {task.status.value}")

    # 更新状态为 RUNNING（让客户端立即能看到状态变化）
    task_manager.update_status(task_id, TaskStatus.RUNNING)

    # 在后台线程中执行 Ray 任务（不阻塞 API）
    import asyncio
    asyncio.create_task(
        asyncio.to_thread(task_manager.dispatch_task, task_id, ray_client)
    )

    task = task_manager.get_task(task_id)
    return TaskResponse(
        task_id=task.task_id,
        task_type=task.task_type.value,
        algorithm_name=task.algorithm_name,
        algorithm_version=task.algorithm_version,
        status=task.status.value,
        created_at=task.created_at.isoformat(),
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        assigned_node=task.assigned_node,
        error=task.error,
        progress=task.progress
    )


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """删除指定任务"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    if task.status == TaskStatus.RUNNING:
        raise HTTPException(status_code=400, detail=f"Cannot delete running task")

    task_manager.delete_task(task_id)
    return {"message": "Task deleted successfully", "task_id": task_id}