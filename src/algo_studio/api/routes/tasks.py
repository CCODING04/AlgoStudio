# src/algo_studio/api/routes/tasks.py
from fastapi import APIRouter, HTTPException, Query, Request
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import ray
from algo_studio.api.models import TaskCreateRequest, TaskResponse, TaskListResponse, TaskPaginatedResponse, DispatchRequest
from algo_studio.core.task import TaskManager, TaskType, TaskStatus, get_progress_store
from algo_studio.core.ray_client import RayClient
from algo_studio.api.middleware.rbac import Permission

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# 全局任务管理器实例
task_manager = TaskManager()
_ray_client = None


def get_ray_client():
    """Lazy initialization of RayClient to avoid ray.init() conflicts."""
    global _ray_client
    if _ray_client is None:
        _ray_client = RayClient()
    return _ray_client


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
async def dispatch_task(task_id: str, request: DispatchRequest = None):
    """分发任务到 Ray 集群执行（异步模式，立即返回）

    支持两种调度模式:
    - auto: 调度器自动选择节点
    - manual: 用户指定节点（通过 node_id）
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    if task.status != TaskStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Task already dispatched, status: {task.status.value}")

    # 解析调度参数
    scheduling_mode = "auto"
    node_id = None
    if request:
        scheduling_mode = request.scheduling_mode if request.scheduling_mode else "auto"
        node_id = request.node_id

    # 手动模式验证
    if scheduling_mode == "manual" and not node_id:
        raise HTTPException(status_code=400, detail="手动调度模式需要指定 node_id")

    # 更新状态为 RUNNING（让客户端立即能看到状态变化）
    task_manager.update_status(task_id, TaskStatus.RUNNING)

    # 在后台线程中执行 Ray 任务（不阻塞 API）
    import asyncio
    asyncio.create_task(
        asyncio.to_thread(task_manager.dispatch_task, task_id, get_ray_client(), node_id, scheduling_mode)
    )

    task = task_manager.get_task(task_id)
    return {
        "task_id": task.task_id,
        "status": task.status.value,
        "scheduling_mode": scheduling_mode,
        "assigned_node": task.assigned_node,
        "message": f"Task dispatched in {scheduling_mode} mode"
    }


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


@router.get("/{task_id}/progress")
async def get_task_progress(task_id: str, request: Request):
    """SSE endpoint for task progress streaming.

    Provides Server-Sent Events (SSE) streaming for real-time task
    progress updates. The stream continues until the task completes,
    fails, or the client disconnects.

    Event types:
    - allocated: Task has been assigned to a node
    - progress: Regular progress update with current percentage
    - completed: Task finished successfully
    - failed: Task failed with error message

    Args:
        task_id: The task ID
        request: FastAPI request object

    Returns:
        EventSourceResponse with SSE stream

    Raises:
        404: Task not found
    """
    # Check if task exists
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    # Get progress store
    progress_store = get_progress_store()

    async def progress_generator():
        """SSE generator for task progress updates."""
        last_progress = 0
        last_status = None
        consecutive_empty = 0
        max_empty_count = 30  # 30 seconds before heartbeat
        allocated_sent = False  # Track if allocated event has been sent

        while True:
            try:
                # Poll current progress from Ray actor
                try:
                    current_progress = ray.get(progress_store.get.remote(task_id))
                except Exception:
                    current_progress = 0

                # Get current task state
                current_task = task_manager.get_task(task_id)
                if not current_task:
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": "Task not found"})
                    }
                    break

                # Check for terminal state
                if current_task.status == TaskStatus.COMPLETED:
                    yield {
                        "event": "completed",
                        "data": json.dumps({
                            "task_id": task_id,
                            "status": "completed",
                            "progress": 100,
                            "message": "Task completed successfully"
                        })
                    }
                    break
                elif current_task.status == TaskStatus.FAILED:
                    yield {
                        "event": "failed",
                        "data": json.dumps({
                            "task_id": task_id,
                            "status": "failed",
                            "error": current_task.error or "Unknown error"
                        })
                    }
                    break

                # Send allocated event if task has been assigned to a node
                if not allocated_sent and current_task.assigned_node:
                    try:
                        allocation_info = ray.get(progress_store.get_allocation.remote(task_id))
                    except Exception:
                        allocation_info = None

                    if allocation_info:
                        yield {
                            "event": "allocated",
                            "data": json.dumps({
                                "task_id": task_id,
                                "node_id": allocation_info.get("node_id"),
                                "node_ip": allocation_info.get("node_ip"),
                                "node_hostname": allocation_info.get("node_hostname"),
                                "assigned_at": allocation_info.get("assigned_at")
                            })
                        }
                        allocated_sent = True

                # Send update if progress changed or heartbeat interval
                if current_progress != last_progress or consecutive_empty >= max_empty_count:
                    yield {
                        "event": "progress",
                        "data": json.dumps({
                            "task_id": task_id,
                            "status": current_task.status.value,
                            "progress": current_progress,
                            "message": f"Task running: {current_progress}%"
                        })
                    }
                    last_progress = current_progress
                    last_status = current_task.status
                    consecutive_empty = 0
                else:
                    consecutive_empty += 1

                # Check if client disconnected
                if await request.is_disconnected():
                    break

                # Poll interval - 1 second
                await asyncio.sleep(1)

            except Exception as e:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(e)})
                }
                break

    return EventSourceResponse(progress_generator())