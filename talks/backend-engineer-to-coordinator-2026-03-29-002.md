# Dataset Management Backend API - 详细设计方案

## Q1: 数据库表设计

### SQLAlchemy Model

```python
# src/algo_studio/db/models/dataset.py
"""Dataset model for persistent dataset metadata storage."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from algo_studio.db.models.base import Base, TimestampMixin


class Dataset(Base, TimestampMixin):
    """Dataset model for persistent storage.

    Stores dataset metadata including name, path, version, size, and access control.
    """

    __tablename__ = "datasets"

    # Primary key - UUID or name-based
    dataset_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Basic info
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Storage info
    path: Mapped[str] = mapped_column(String(512), nullable=False)  # /nas/datasets/xxx
    storage_type: Mapped[str] = mapped_column(String(20), default="dvc")  # dvc/nas/raw
    size_gb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    file_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Version control (DVC)
    version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # DVC commit hash
    dvc_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Metadata
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Access control
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    team_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("teams.team_id", ondelete="SET NULL"), nullable=True
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="dataset")

    def __repr__(self) -> str:
        return f"<Dataset(dataset_id={self.dataset_id}, name={self.name}, size_gb={self.size_gb})>"


class DatasetAccess(Base):
    """Dataset access control model for per-user permissions."""

    __tablename__ = "dataset_access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("datasets.dataset_id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True
    )
    team_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=True
    )

    # Permission level
    access_level: Mapped[str] = mapped_column(String(20), default="read")  # read/write/admin

    # Timestamps
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    granted_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return f"<DatasetAccess(dataset_id={self.dataset_id}, user_id={self.user_id}, level={self.access_level})>"
```

### Task Model Extension

Add `dataset_id` to existing Task model:

```python
# In Task model (src/algo_studio/db/models/task.py)
dataset_id: Mapped[Optional[str]] = mapped_column(
    String(64), ForeignKey("datasets.dataset_id", ondelete="SET NULL"), nullable=True
)
# Add relationship
dataset: Mapped[Optional["Dataset"]] = relationship("Dataset", back_populates="tasks")
```

---

## Q2: API 端点设计

### RESTful API

```yaml
# Dataset CRUD
GET    /api/datasets                    # List datasets (paginated)
POST   /api/datasets                    # Create dataset
GET    /api/datasets/{dataset_id}       # Get dataset details
PUT    /api/datasets/{dataset_id}       # Update dataset
DELETE /api/datasets/{dataset_id}        # Delete dataset

# Dataset Operations
POST   /api/datasets/{dataset_id}/refresh   # Refresh size/version info
GET    /api/datasets/{dataset_id}/download  # Get download URL

# Access Control
GET    /api/datasets/{dataset_id}/access     # List access permissions
POST   /api/datasets/{dataset_id}/access     # Grant access
DELETE /api/datasets/{dataset_id}/access/{id} # Revoke access

# Task Association
GET    /api/datasets/{dataset_id}/tasks      # List tasks using this dataset
```

### Request/Response Models

```python
# src/algo_studio/api/models/dataset.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class DatasetCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    path: str = Field(..., description="Dataset path on NAS")
    storage_type: str = Field(default="dvc", pattern="^(dvc|nas|raw)$")
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    is_public: bool = False
    team_id: Optional[str] = None


class DatasetUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None


class DatasetResponse(BaseModel):
    dataset_id: str
    name: str
    description: Optional[str]
    path: str
    storage_type: str
    size_gb: Optional[float]
    file_count: Optional[int]
    version: Optional[str]
    metadata: Optional[Dict[str, Any]]
    tags: Optional[List[str]]
    is_public: bool
    owner_id: Optional[str]
    team_id: Optional[str]
    is_active: bool
    last_accessed_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DatasetListResponse(BaseModel):
    items: List[DatasetResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class DatasetAccessRequest(BaseModel):
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    access_level: str = Field(default="read", pattern="^(read|write|admin)$")


class DatasetAccessResponse(BaseModel):
    id: int
    dataset_id: str
    user_id: Optional[str]
    team_id: Optional[str]
    access_level: str
    granted_at: datetime
    granted_by: Optional[str]
```

---

## Q3: 与现有系统集成

### 3.1 与 Task 关联方式

```python
# Task model already has dataset_id foreign key
# Task creation accepts optional dataset_id:

class TaskCreateRequest(BaseModel):
    dataset_id: Optional[str] = None  # Link task to dataset
    # ... existing fields
```

Task Manager 集成:
```python
# In task creation, validate dataset exists:
if request.dataset_id:
    dataset = db.query(Dataset).filter(Dataset.dataset_id == request.dataset_id).first()
    if not dataset:
        raise HTTPException(404, "Dataset not found")
    # Update last_accessed_at
    dataset.last_accessed_at = datetime.utcnow()
```

### 3.2 RBAC 权限集成

扩展 `Permission` 枚举:
```python
class Permission(str, Enum):
    # ... existing
    DATASET_READ = "dataset.read"
    DATASET_CREATE = "dataset.create"
    DATASET_WRITE = "dataset.write"
    DATASET_DELETE = "dataset.delete"
    DATASET_ADMIN = "dataset.admin"
```

RBAC 路由保护:
```python
PROTECTED_ROUTES = {
    # ... existing
    "/api/datasets": [Permission.DATASET_READ],
    "/api/datasets/": [Permission.DATASET_READ],
}

# In RBAC middleware _get_required_permissions():
if path == "/api/datasets" and method == "POST":
    return [Permission.DATASET_CREATE]
if path.startswith("/api/datasets/") and method == "PUT":
    return [Permission.DATASET_WRITE]
if path.startswith("/api/datasets/") and method == "DELETE":
    return [Permission.DATASET_DELETE]
```

数据集级权限检查:
```python
# In dataset route handlers:
async def check_dataset_access(dataset_id: str, user: User, required_level: str):
    """Check if user has required access level to dataset."""
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()

    # Public datasets - anyone can read
    if dataset.is_public and required_level == "read":
        return True

    # Owner has all permissions
    if dataset.owner_id == user.user_id:
        return True

    # Superuser has all permissions
    if user.is_superuser:
        return True

    # Check dataset_access table
    access = db.query(DatasetAccess).filter(
        DatasetAccess.dataset_id == dataset_id,
        DatasetAccess.user_id == user.user_id
    ).first()

    if not access:
        return False

    level_hierarchy = {"read": 0, "write": 1, "admin": 2}
    return level_hierarchy.get(access.access_level, -1) >= level_hierarchy.get(required_level, 99)
```

### 3.3 与 DatasetManager 关系

```python
# src/algo_studio/api/services/dataset_service.py
"""Service layer bridging API and DatasetManager."""

from algo_studio.core.dataset import DatasetManager
from algo_studio.db.models.dataset import Dataset


class DatasetService:
    """Service for dataset operations."""

    def __init__(self, db_session):
        self.db_session = db_session
        self.manager = DatasetManager()  # Uses /nas/datasets

    def list_datasets(self) -> List[DatasetInfo]:
        """List datasets from filesystem (DatasetManager)."""
        return self.manager.list_datasets()

    def sync_from_filesystem(self):
        """Sync dataset metadata from filesystem to database."""
        fs_datasets = self.manager.list_datasets()
        for ds_info in fs_datasets:
            # Check if exists in DB, create if not
            existing = self.db_session.query(Dataset).filter(
                Dataset.name == ds_info.name
            ).first()

            if existing:
                # Update metadata
                existing.size_gb = ds_info.size_gb
                existing.version = ds_info.version
            else:
                # Create new
                new_ds = Dataset(
                    dataset_id=generate_uuid(),
                    name=ds_info.name,
                    path=ds_info.path,
                    version=ds_info.version,
                    size_gb=ds_info.size_gb,
                    storage_type="dvc"
                )
                self.db_session.add(new_ds)
```

---

## Q4: Alembic 迁移

### Migration Script: 002_add_datasets.py

```python
"""Add datasets table

Revision ID: 002_add_datasets
Revises: 001_initial
Create Date: 2026-03-29

This migration:
1. Creates datasets table for dataset metadata storage
2. Creates dataset_access table for access control
3. Adds dataset_id foreign key to tasks table
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '002_add_datasets'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create datasets table
    op.create_table(
        'datasets',
        sa.Column('dataset_id', sa.String(64), primary_key=True),
        sa.Column('name', sa.String(255), unique=True, nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('path', sa.String(512), nullable=False),
        sa.Column('storage_type', sa.String(20), default='dvc'),
        sa.Column('size_gb', sa.Float),
        sa.Column('file_count', sa.Integer),
        sa.Column('version', sa.String(64)),
        sa.Column('dvc_path', sa.String(512)),
        sa.Column('metadata', sa.JSON),
        sa.Column('tags', sa.JSON),
        sa.Column('is_public', sa.Boolean, default=False),
        sa.Column('owner_id', sa.String(64), sa.ForeignKey('users.user_id', ondelete='SET NULL')),
        sa.Column('team_id', sa.String(64), sa.ForeignKey('teams.team_id', ondelete='SET NULL')),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('last_accessed_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now()),
    )
    op.create_index('idx_datasets_name', 'datasets', ['name'])
    op.create_index('idx_datasets_owner', 'datasets', ['owner_id'])
    op.create_index('idx_datasets_team', 'datasets', ['team_id'])

    # Create dataset_access table
    op.create_table(
        'dataset_access',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('dataset_id', sa.String(64), sa.ForeignKey('datasets.dataset_id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(64), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=True),
        sa.Column('team_id', sa.String(64), sa.ForeignKey('teams.team_id', ondelete='CASCADE'), nullable=True),
        sa.Column('access_level', sa.String(20), default='read'),
        sa.Column('granted_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('granted_by', sa.String(64)),
    )
    op.create_index('idx_dataset_access_dataset', 'dataset_access', ['dataset_id'])
    op.create_index('idx_dataset_access_user', 'dataset_access', ['user_id'])
    op.create_index('idx_dataset_access_team', 'dataset_access', ['team_id'])

    # Add dataset_id to tasks table
    op.add_column('tasks', sa.Column('dataset_id', sa.String(64), sa.ForeignKey('datasets.dataset_id', ondelete='SET NULL'), nullable=True))
    op.create_index('idx_tasks_dataset', 'tasks', ['dataset_id'])


def downgrade() -> None:
    op.drop_index('idx_tasks_dataset', 'tasks')
    op.drop_column('tasks', 'dataset_id')
    op.drop_table('dataset_access')
    op.drop_table('datasets')
```

---

## 工作量估算

| 任务 | 工作量 | 说明 |
|------|--------|------|
| Dataset Model | 2h | SQLAlchemy model + DatasetAccess model |
| CRUD API | 3h | 5个基础端点 + 3个access端点 |
| Task 关联 | 1h | dataset_id 字段 + 验证逻辑 |
| RBAC 集成 | 2h | Permission 枚举 + 中间件 + 路由保护 |
| Alembic 迁移 | 1h | 迁移脚本编写 |
| 单元测试 | 2h | Model + API 测试 |
| **总计** | **11h** | |

---

## 实施计划

### Phase 1: Model + Migration (3h)
1. 创建 `src/algo_studio/db/models/dataset.py`
2. 更新 `src/algo_studio/db/models/__init__.py`
3. 创建 Alembic 迁移脚本 `002_add_datasets.py`

### Phase 2: API Endpoints (3h)
1. 创建 `src/algo_studio/api/routes/datasets.py`
2. 创建 `src/algo_studio/api/models/dataset.py` (Pydantic)
3. 创建 `src/algo_studio/api/services/dataset_service.py`
4. 注册路由到 `main.py`

### Phase 3: RBAC Integration (2h)
1. 扩展 `Permission` 枚举
2. 更新 `RBACMiddleware.PROTECTED_ROUTES`
3. 添加数据集级权限检查函数

### Phase 4: Testing (2h)
1. 单元测试: Model CRUD
2. API 测试: 端点测试
3. 集成测试: Task + Dataset 关联

---

## 关键设计决策

1. **dataset_id vs name as key**: 使用 UUID 作为主键，name 作为唯一标识
2. **软删除**: 使用 `is_active` 标志而非物理删除
3. **DVC 集成**: 通过 DatasetManager 读取 DVC 版本信息
4. **访问控制**: 支持 user-level 和 team-level 权限
