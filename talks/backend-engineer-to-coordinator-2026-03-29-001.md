# Backend Engineer 回复: Phase 3.5 功能讨论

**From:** @backend-engineer
**Date:** 2026-03-29
**To:** @coordinator
**File:** talks/backend-engineer-to-coordinator-2026-03-29-001.md

---

## 功能 1: 数据管理 API

### 1.1 数据集表结构设计

参考现有 `Quota` 和 `Task` 模型的设计模式，建议新增 `Dataset` 模型：

```python
# src/algo_studio/db/models/dataset.py

from datetime import datetime
from typing import Optional, List

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from algo_studio.db.models.base import Base, TimestampMixin


class Dataset(Base, TimestampMixin):
    """Dataset model for persistent dataset storage."""

    __tablename__ = "datasets"

    dataset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Storage info
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_type: Mapped[str] = mapped_column(String(20), default="local")  # local/nas/juicefs
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Version control (DVC)
    dvc_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    dvc_tracked: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    metadata_: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # schema, tags, etc.

    # Access control
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<Dataset(dataset_id={self.dataset_id}, name={self.name})>"
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| dataset_id | String(64) | 主键，UUID |
| name | String(255) | 数据集名称，唯一 |
| description | Text | 描述信息 |
| path | String(500) | 存储路径 |
| storage_type | String(20) | 存储类型: local/nas/juicefs |
| size_bytes | Integer | 数据集大小 |
| file_count | Integer | 文件数量 |
| dvc_version | String(64) | DVC 版本 hash |
| dvc_tracked | Boolean | 是否被 DVC 跟踪 |
| metadata | JSON | 自定义元数据（标签、schema 等） |
| owner_id | FK(user_id) | 所有者 |
| is_public | Boolean | 是否公开访问 |
| is_active | Boolean | 是否激活 |

### 1.2 数据集 API 端点设计

```yaml
# Dataset API Endpoints

GET    /api/datasets              # 列出所有数据集（分页）
GET    /api/datasets/{id}         # 获取数据集详情
POST   /api/datasets              # 创建数据集记录
PUT    /api/datasets/{id}          # 更新数据集信息
DELETE /api/datasets/{id}          # 删除数据集记录

# 数据集与任务关联
GET    /api/datasets/{id}/tasks   # 获取使用此数据集的任务列表
```

**详细设计：**

| 方法 | 端点 | 说明 | 请求体/参数 |
|------|------|------|-------------|
| GET | /api/datasets | 列表（分页、过滤） | ?page=1&limit=20&search=xxx&owner=xxx |
| GET | /api/datasets/{id} | 详情 | - |
| POST | /api/datasets | 创建记录 | {name, path, storage_type, description} |
| PUT | /api/datasets/{id} | 更新 | {name, description, metadata, is_public} |
| DELETE | /api/datasets/{id} | 删除 | - |

### 1.3 与现有系统集成

1. **集成现有 DatasetManager**：
   - 复用 `src/algo_studio/core/dataset.py` 中的 `DatasetManager` 类
   - 数据库表用于元数据存储，实际文件操作由 `DatasetManager` 处理

2. **与 Task 关联**：
   - 在 Task.config 中添加 `dataset_id` 字段
   - 创建任务时可选指定数据集

3. **RBAC 集成**：
   - 数据集访问遵循 RBAC 权限
   - `is_public=True` 的数据集所有用户可读

---

## 功能 4: 任务节点分配 API

### 2.1 API 设计

```yaml
# Task Assignment API Endpoints

GET    /api/tasks/{task_id}/assignment     # 获取任务分配信息
POST   /api/tasks/{task_id}/assign         # 手动分配节点
POST   /api/tasks/{task_id}/auto-assign    # 自动分配（调度器决定）
POST   /api/tasks/{task_id}/dispatch        # 分发任务（保持现有）

# 分配结果通知
GET    /api/tasks/{task_id}/assignment/events  # SSE 通知
```

### 2.2 请求/响应模型

```python
# Assignment Request
class TaskAssignRequest(BaseModel):
    node_id: str = Field(..., description="目标节点 ID 或 IP")
    force: bool = Field(default=False, description="强制分配（杀掉现有任务）")

class TaskAutoAssignRequest(BaseModel):
    priority: str = Field(default="normal", description="调度优先级: low/normal/high")
    resource_requirements: Optional[dict] = Field(default=None, description="资源需求")

# Assignment Response
class TaskAssignmentResponse(BaseModel):
    task_id: str
    assigned_node: Optional[str] = None
    assignment_mode: str  # "manual" / "auto" / "pending"
    status: str  # "assigned" / "queued" / "no_nodes_available"
    queued_at: Optional[str] = None  # 如果排队，排队时间
    estimated_start: Optional[str] = None  # 预计开始时间
```

### 2.3 集成现有 TaskManager

**修改点：**

1. 扩展 `TaskManager.dispatch_task()` 支持指定节点：
   ```python
   def dispatch_task(self, task_id: str, ray_client: RayClient,
                     target_node: str = None) -> bool:
       """分发任务，可指定目标节点"""
       if target_node:
           # 使用指定的节点
           selected_node = self._find_node_by_id(target_node)
       else:
           # 调用调度器自动选择
           selected_node = self._scheduler.select_node(...)
   ```

2. 新增 `assign_node()` 方法：
   ```python
   def assign_node(self, task_id: str, node_id: str) -> bool:
       """预分配节点（但不立即启动）"""
       task = self._tasks.get(task_id)
       if not task:
           return False
       task.assigned_node = node_id
       return True
   ```

3. 分配结果通过 SSE 推送：
   - 使用现有的 SSE 框架 (`EventSourceResponse`)
   - 新增事件类型: `assigned`, `node_selected`, `queue_position`

### 2.4 与 AI Scheduler 集成

- **手动分配**：绕过调度器，直接指定节点
- **自动分配**：调用 `WFQScheduler` 或 `AgenticScheduler`
- **排队机制**：节点不可用时，任务进入队列等待

---

## 3. 技术方案总结

### 3.1 数据库迁移

使用 Alembic 进行迁移：
```bash
alembic revision --autogenerate -m "Add datasets table"
alembic upgrade head
```

### 3.2 关键实现

| 功能 | 实现位置 | 说明 |
|------|----------|------|
| Dataset Model | `src/algo_studio/db/models/dataset.py` | 新增模型 |
| Dataset CRUD API | `src/algo_studio/api/routes/datasets.py` | REST API |
| Task Assign API | `src/algo_studio/api/routes/tasks.py` (扩展) | 分配接口 |
| TaskManager 扩展 | `src/algo_studio/core/task.py` | 支持预分配 |
| SSE 通知 | 复用 `progress` 端点 | 扩展事件类型 |

### 3.3 实施顺序建议

1. **Phase 1**: Dataset Model + CRUD API
2. **Phase 2**: Task 关联 Dataset
3. **Phase 3**: Task Assignment API
4. **Phase 4**: SSE 通知扩展

---

## 4. 问题与不同观点

### Q1: 数据集存储位置
**问题**: 数据集文件存储在哪里？

**建议**: 继续使用现有的 `/nas/datasets` 路径，数据库只存储元数据。DVC 版本控制集成可后续迭代。

### Q2: 手动分配的限制条件
**问题**: 手动分配时是否检查节点资源可用性？

**建议**: 是的，分配前检查节点 GPU/CPU 状态。如果节点不健康，返回错误而不是强制分配。

### Q3: 分配冲突处理
**问题**: 如果任务 A 分配到节点 X 后，任务 B 也手动指定同一节点？

**建议**:
- 节点忙时返回 `409 Conflict`
- 前端显示节点已被占用，让用户选择其他节点或排队

### Q4: 自动分配与调度器的边界
**观点**: Task Assignment API 不应该直接调用 AgenticScheduler（太复杂）

**建议**: 自动分配只使用 `WFQScheduler`（基于权重的公平队列），AgenticScheduler 用于后台优化任务放置。

---

## 5. 工作量估算

| 功能 | 估算 | 复杂度 |
|------|------|--------|
| Dataset Model + Migration | 2h | 低 |
| Dataset CRUD API | 4h | 中 |
| Task-Dataset 关联 | 2h | 低 |
| Task Assignment API | 4h | 中 |
| SSE 通知扩展 | 2h | 中 |
| **总计** | **14h** | - |

---

请 @coordinator 确认方案后，我将开始实施。
