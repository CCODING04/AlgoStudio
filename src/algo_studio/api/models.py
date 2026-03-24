# src/algo_studio/api/models.py
from pydantic import BaseModel, Field
from typing import Any

class TaskCreateRequest(BaseModel):
    task_type: str = Field(..., description="train/infer/verify")
    algorithm_name: str = Field(..., description="算法名称")
    algorithm_version: str = Field(..., description="算法版本")
    config: dict[str, Any] = Field(default_factory=dict, description="任务配置")

class TaskResponse(BaseModel):
    task_id: str
    task_type: str
    algorithm_name: str
    algorithm_version: str
    status: str
    created_at: str
    assigned_node: str | None = None

class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int