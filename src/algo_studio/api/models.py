# src/algo_studio/api/models.py
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from algo_studio.api.pagination import PaginatedResponse


class TaskCreateRequest(BaseModel):
    task_type: str = Field(..., description="train/infer/verify")
    algorithm_name: str = Field(..., description="算法名称")
    algorithm_version: str = Field(..., description="算法版本")
    config: Dict[str, Any] = Field(default_factory=dict, description="任务配置")

class TaskResponse(BaseModel):
    task_id: str
    task_type: str
    algorithm_name: str
    algorithm_version: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    assigned_node: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[int] = None  # 0-100

class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int

class TaskPaginatedResponse(PaginatedResponse[TaskResponse]):
    """Paginated task response using cursor pagination."""
    pass


class DispatchRequest(BaseModel):
    """Request body for task dispatch endpoint."""
    node_id: Optional[str] = Field(None, description="指定节点ID（ip或node_id），为空则自动分配")
    scheduling_mode: str = Field("auto", description="调度模式: auto=自动选择节点, manual=手动指定节点")


class DispatchResponse(BaseModel):
    """Response for task dispatch endpoint."""
    task_id: str
    status: str
    scheduling_mode: str
    assigned_node: Optional[str] = None
    message: str