# src/algo_studio/api/models.py
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

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
    assigned_node: Optional[str] = None

class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int