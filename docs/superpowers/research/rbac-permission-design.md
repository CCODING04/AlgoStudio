# AlgoStudio Phase 2.3 RBAC Permission System & Task Progress API Architecture

**版本**: v1.0
**日期**: 2026-03-27
**作者**: @backend-engineer
**状态**: 初稿

---

## 目录

1. [RBAC 权限系统架构](#1-rbac-权限系统架构)
2. [任务进度 API 完善](#2-任务进度-api-完善)
3. [数据模型设计](#3-数据模型设计)
4. [API 端点规格](#4-api-端点规格)
5. [数据库 Schema 变更](#5-database-schema-变更)
6. [实现路径](#6-实现路径)

---

## 1. RBAC 权限系统架构

### 1.1 现有架构分析

当前 `src/algo_studio/api/middleware/rbac.py` 实现了基础的 RBAC：
- 3 个角色: `viewer`, `developer`, `admin`
- 6 个权限: `task.read`, `task.create`, `task.delete`, `admin.user`, `admin.quota`, `admin.alert`
- 基于请求头 `X-User-ID`, `X-User-Role`, `X-Signature` 的认证

**缺失能力:**
- 无 Team/Organization 层级结构
- 无细粒度资源级权限控制
- 无权限继承机制
- 无权限变更审计日志

### 1.2 扩展 RBAC 模型

#### 1.2.1 层级结构

```
Organization (组织)
    │
    └── Team (团队)
          │
          └── User (用户)
```

| 层级 | 实体 | 说明 |
|------|------|------|
| Organization | `Organization` | 顶级组织，如 "Algorithmics Inc" |
| Team | `Team` | 组织下的团队，如 "CV Team", "NLP Team" |
| User | `User` | 团队成员 |

#### 1.2.2 权限继承模型

```
Organization Level
    ├── org:read          # 组织内所有资源读取
    ├── org:write         # 组织内所有资源创建/修改
    └── org:admin         # 组织管理权限

Team Level (继承 org:* +)
    ├── team:read         # 本团队资源读取
    ├── team:write         # 本团队资源创建/修改
    ├── team:admin        # 团队管理权限
    └── team:members      # 团队成员管理

User Level (继承 team:* +)
    ├── user:read         # 个人资源读取
    ├── user:write        # 个人资源创建/修改
    └── user:admin        # 个人信息管理
```

#### 1.2.3 任务资源权限模型

任务权限需要考虑 Owner、Team Member、Organization Member、Public 四级：

| 权限 | Owner | Team Member | Org Member | Public |
|------|-------|--------------|------------|--------|
| task:read | ✓ | ✓ (本团队) | ✓ (本组织) | ○ |
| task:write | ✓ | ✓ (本团队) | ○ | ✗ |
| task:delete | ✓ | ✓ (本团队) | ○ | ✗ |
| task:cancel | ✓ | ✓ (本团队) | ○ | ✗ |
| task:read_logs | ✓ | ✓ | ✓ | ✗ |

### 1.3 Team/Organization 数据模型

```python
# src/algo_studio/db/models/organization.py

class Organization(Base, TimestampMixin):
    """组织模型"""
    __tablename__ = "organizations"

    org_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 配额设置
    max_teams: Mapped[int] = mapped_column(Integer, default=10)
    max_users: Mapped[int] = mapped_column(Integer, default=100)
    max_gpu_hours_per_day: Mapped[float] = mapped_column(default=1000.0)


class Team(Base, TimestampMixin):
    """团队模型"""
    __tablename__ = "teams"

    team_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 配额设置（继承组织，可覆盖）
    max_members: Mapped[int] = mapped_column(Integer, default=20)
    max_gpu_hours_per_day: Mapped[Optional[float]] = mapped_column(nullable=True)  # None = 继承组织


class TeamMembership(Base, TimestampMixin):
    """团队成员关系"""
    __tablename__ = "team_memberships"

    membership_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), default="member")  # member, lead, admin

    __table_args__ = (
        UniqueConstraint("user_id", "team_id", name="uq_user_team"),
    )
```

### 1.4 权限继承实现

```python
# src/algo_studio/core/permissions.py

class PermissionChecker:
    """权限检查器，支持层级继承"""

    def __init__(self, user: User, team_memberships: list[TeamMembership] = None):
        self.user = user
        self.team_memberships = team_memberships or []

    def can_read_task(self, task: Task) -> bool:
        """检查是否能读取任务"""
        # Owner 始终可以
        if task.user_id == self.user.user_id:
            return True

        # Admin 始终可以
        if self.user.is_superuser:
            return True

        # Public 任务（已完成且未设置隐私）可被所有人读取
        if task.is_public and task.status == TaskStatus.COMPLETED:
            return True

        # 获取任务所属团队
        task_user = self._get_user(task.user_id)
        if not task_user:
            return False

        # 同团队成员
        if self._is_same_team(task_user):
            return True

        # 同组织成员（需要任务用户属于同一组织）
        if self._is_same_org(task_user):
            return True

        return False

    def can_write_task(self, task: Task) -> bool:
        """检查是否能修改任务"""
        if task.user_id == self.user.user_id:
            return True
        if self.user.is_superuser:
            return True
        # 同团队 lead 或 admin 角色
        return self._has_team_role(task.user_id, ["lead", "admin"])

    def can_delete_task(self, task: Task) -> bool:
        """检查是否能删除任务"""
        return self.can_write_task(task)

    def can_cancel_task(self, task: Task) -> bool:
        """检查是否能取消任务（仅运行中的任务）"""
        if task.status != TaskStatus.RUNNING:
            return False
        return self.can_write_task(task)

    def _is_same_team(self, target_user: User) -> bool:
        """检查是否在同一团队"""
        target_teams = self._get_user_teams(target_user.user_id)
        user_team_ids = {m.team_id for m in self.team_memberships}
        return bool(target_teams & user_team_ids)

    def _is_same_org(self, target_user: User) -> bool:
        """检查是否在同一组织"""
        target_orgs = self._get_user_orgs(target_user.user_id)
        user_orgs = self._get_user_orgs(self.user.user_id)
        return bool(target_orgs & user_orgs)

    def _has_team_role(self, target_user_id: str, roles: list[str]) -> bool:
        """检查是否是团队 lead 或 admin"""
        for membership in self.team_memberships:
            if membership.user_id == target_user_id and membership.role in roles:
                return True
        return False
```

### 1.5 权限变更审计日志

```python
# src/algo_studio/db/models/audit.py

class AuditLog(Base, TimestampMixin):
    """审计日志模型"""
    __tablename__ = "audit_logs"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)  # 执行操作的用户
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # permission.grant, permission.revoke, etc.
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # task, team, user, etc.
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    old_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

# 审计动作类型
class AuditAction(str, Enum):
    PERMISSION_GRANT = "permission.grant"
    PERMISSION_REVOKE = "permission.revoke"
    ROLE_CHANGED = "role.changed"
    TEAM_CREATED = "team.created"
    TEAM_DELETED = "team.deleted"
    MEMBER_ADDED = "member.added"
    MEMBER_REMOVED = "member.removed"
    TASK_CANCELLED = "task.cancelled"
    TASK_DELETED = "task.deleted"
```

---

## 2. 任务进度 API 完善

### 2.1 当前状态

现有 `src/algo_studio/api/routes/tasks.py` 提供:
- `POST /api/tasks` - 创建任务
- `GET /api/tasks` - 列出任务（游标分页）
- `GET /api/tasks/{task_id}` - 获取单个任务
- `POST /api/tasks/{task_id}/dispatch` - 分发任务

**缺失:**
- 任务取消 (DELETE /tasks/{task_id})
- 任务历史 (GET /tasks/{task_id}/history)
- 任务资源使用 (GET /tasks/{task_id}/resources)

### 2.2 新增 API 设计

#### 2.2.1 任务取消

```
DELETE /api/tasks/{task_id}

请求:
  - Path: task_id (string, required)
  - Headers: X-User-ID, X-User-Role, X-Signature, X-Timestamp

响应:
  200 OK:
  {
    "task_id": "train-xxxx",
    "status": "cancelled",
    "cancelled_at": "2026-03-27T10:30:00Z",
    "cancelled_by": "user-id"
  }

  400 Bad Request: 任务已完成或已取消
  403 Forbidden: 无权限取消
  404 Not Found: 任务不存在
```

**取消流程:**
1. 验证用户有取消权限（Owner/Team Lead/Admin）
2. 检查任务状态（仅 PENDING/RUNNING 可取消）
3. 向 Ray 集群发送取消信号（通过 Ray Client）
4. 更新任务状态为 CANCELLED
5. 记录取消审计日志

#### 2.2.2 任务历史

```
GET /api/tasks/{task_id}/history

响应:
  200 OK:
  {
    "task_id": "train-xxxx",
    "history": [
      {
        "event": "created",
        "timestamp": "2026-03-27T10:00:00Z",
        "actor": "user-id",
        "details": {}
      },
      {
        "event": "dispatched",
        "timestamp": "2026-03-27T10:05:00Z",
        "actor": "system",
        "details": {"node": "192.168.0.115"}
      },
      {
        "event": "progress",
        "timestamp": "2026-03-27T10:10:00Z",
        "details": {"progress": 25, "description": "Loading model..."}
      },
      {
        "event": "cancelled",
        "timestamp": "2026-03-27T10:30:00Z",
        "actor": "user-id",
        "details": {"reason": "user_requested"}
      }
    ]
  }
```

#### 2.2.3 任务资源使用

```
GET /api/tasks/{task_id}/resources

响应:
  200 OK:
  {
    "task_id": "train-xxxx",
    "resources": {
      "gpu_usage": {
        "avg_memory_mb": 18432,
        "max_memory_mb": 20480,
        "utilization_percent": 78.5
      },
      "cpu_usage": {
        "avg_percent": 45.2,
        "max_percent": 62.0
      },
      "memory_usage": {
        "avg_mb": 8192,
        "max_mb": 12288
      },
      "execution_time": {
        "started_at": "2026-03-27T10:05:00Z",
        "duration_seconds": 1500,
        "estimated_remaining_seconds": 450
      },
      "io_stats": {
        "bytes_read": 1073741824,
        "bytes_written": 536870912
      }
    },
    "node": "192.168.0.115",
    "collected_at": "2026-03-27T10:30:00Z"
  }
```

---

## 3. 数据模型设计

### 3.1 任务历史记录模型

```python
# src/algo_studio/db/models/task_history.py

class TaskHistory(Base, TimestampMixin):
    """任务历史记录"""
    __tablename__ = "task_history"

    history_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False
    )
    event: Mapped[str] = mapped_column(String(50), nullable=False)  # created, dispatched, progress, completed, failed, cancelled
    actor: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # user_id or "system"
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_task_history_task_id", "task_id"),
        Index("idx_task_history_created_at", "created_at"),
    )


class TaskResourceUsage(Base, TimestampMixin):
    """任务资源使用统计（定期采集）"""
    __tablename__ = "task_resource_usage"

    usage_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False
    )
    node_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # GPU 指标
    gpu_memory_used_mb: Mapped[Optional[float]] = mapped_column(nullable=True)
    gpu_utilization_percent: Mapped[Optional[float]] = mapped_column(nullable=True)

    # CPU 指标
    cpu_percent: Mapped[Optional[float]] = mapped_column(nullable=True)

    # 内存指标
    memory_used_mb: Mapped[Optional[float]] = mapped_column(nullable=True)

    # IO 指标
    disk_read_bytes: Mapped[Optional[int]] = mapped_column(nullable=True)
    disk_write_bytes: Mapped[Optional[int]] = mapped_column(nullable=True)

    # 网络指标（如适用）
    network_bytes_sent: Mapped[Optional[int]] = mapped_column(nullable=True)
    network_bytes_recv: Mapped[Optional[int]] = mapped_column(nullable=True)

    # 任务进度
    task_progress: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-100

    collected_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_task_resource_task_id", "task_id"),
        Index("idx_task_resource_collected", "collected_at"),
    )
```

### 3.2 任务取消模型

```python
# Task 模型需要添加字段
# 在 task.py 的 Task 模型中增加:

class Task(Base, TimestampMixin):
    """任务模型（扩展）"""
    # ... existing fields ...

    # 新增字段
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)  # 公开任务标记
```

---

## 4. API 端点规格

### 4.1 RBAC 相关端点

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/organizations` | GET | 列出用户所在组织 | Yes |
| `/api/organizations/{org_id}` | GET | 获取组织详情 | Yes |
| `/api/organizations/{org_id}/teams` | GET | 列出组织内团队 | Yes |
| `/api/teams` | POST | 创建团队 | Yes (org:write) |
| `/api/teams/{team_id}` | GET | 获取团队详情 | Yes |
| `/api/teams/{team_id}/members` | GET | 列出团队成员 | Yes |
| `/api/teams/{team_id}/members` | POST | 添加团队成员 | Yes (team:admin) |
| `/api/teams/{team_id}/members/{user_id}` | DELETE | 移除团队成员 | Yes (team:admin) |
| `/api/audit-logs` | GET | 查询审计日志 | Yes (admin only) |

### 4.2 任务进度相关端点

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/tasks/{task_id}` | DELETE | 取消任务 | Yes |
| `/api/tasks/{task_id}/history` | GET | 获取任务历史 | Yes |
| `/api/tasks/{task_id}/resources` | GET | 获取资源使用 | Yes |
| `/api/tasks/{task_id}/cancel` | POST | 取消任务（显式） | Yes |

### 4.3 权限检查中间件扩展

```python
# src/algo_studio/api/middleware/rbac.py (扩展)

# 新增资源级权限检查
async def require_task_permission(
    task_id: str,
    permission: TaskPermission
) -> Callable:
    """检查用户对特定任务的权限"""

    async def permission_check(request: Request) -> User:
        user: Optional[User] = getattr(request.state, "user", None)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        checker = PermissionChecker(user, get_team_memberships(user.user_id))

        permission_map = {
            TaskPermission.READ: checker.can_read_task,
            TaskPermission.WRITE: checker.can_write_task,
            TaskPermission.DELETE: checker.can_delete_task,
            TaskPermission.CANCEL: checker.can_cancel_task,
        }

        check_func = permission_map.get(permission)
        if not check_func or not check_func(task):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "PERMISSION_DENIED",
                        "message": f"Permission '{permission.value}' denied for task '{task_id}'"
                    }
                }
            )

        return user

    return permission_check
```

### 4.4 Task SSE Progress 端点扩展

```python
# src/algo_studio/api/routes/tasks.py (扩展)

@router.get("/{task_id}/progress/sse")
async def task_progress_sse(
    task_id: str,
    request: Request,
    user: User = Depends(require_permission(Permission.TASK_READ))
):
    """任务进度 SSE 流（带权限过滤）"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 权限检查
    checker = PermissionChecker(user, get_team_memberships(user.user_id))
    if not checker.can_read_task(task):
        raise HTTPException(status_code=403, detail="Permission denied")

    async def event_generator():
        progress_store = get_progress_store()
        last_progress = -1

        while True:
            if await request.is_disconnected():
                break

            current_progress = ray.get(progress_store.get.remote(task_id))

            if current_progress != last_progress:
                yield {
                    "event": "progress",
                    "data": {
                        "task_id": task_id,
                        "progress": current_progress,
                        "timestamp": datetime.now().isoformat()
                    }
                }
                last_progress = current_progress

                # 任务完成时退出
                task = task_manager.get_task(task_id)
                if task and task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                    break

            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())
```

---

## 5. Database Schema 变更

### 5.1 新增表

```sql
-- 组织表
CREATE TABLE organizations (
    org_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    max_teams INTEGER DEFAULT 10,
    max_users INTEGER DEFAULT 100,
    max_gpu_hours_per_day REAL DEFAULT 1000.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- 团队表
CREATE TABLE teams (
    team_id VARCHAR(64) PRIMARY KEY,
    org_id VARCHAR(64) NOT NULL,
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    max_members INTEGER DEFAULT 20,
    max_gpu_hours_per_day REAL,  -- NULL = inherit from org
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (org_id) REFERENCES organizations(org_id) ON DELETE CASCADE
);

-- 团队成员关系表
CREATE TABLE team_memberships (
    membership_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    team_id VARCHAR(64) NOT NULL,
    role VARCHAR(20) DEFAULT 'member',  -- member, lead, admin
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
    UNIQUE(user_id, team_id)
);

-- 任务历史表
CREATE TABLE task_history (
    history_id VARCHAR(64) PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL,
    event VARCHAR(50) NOT NULL,
    actor VARCHAR(64),
    details JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

CREATE INDEX idx_task_history_task_id ON task_history(task_id);
CREATE INDEX idx_task_history_created_at ON task_history(created_at);

-- 任务资源使用表
CREATE TABLE task_resource_usage (
    usage_id VARCHAR(64) PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL,
    node_ip VARCHAR(45),
    gpu_memory_used_mb REAL,
    gpu_utilization_percent REAL,
    cpu_percent REAL,
    memory_used_mb REAL,
    disk_read_bytes INTEGER,
    disk_write_bytes INTEGER,
    network_bytes_sent INTEGER,
    network_bytes_recv INTEGER,
    task_progress INTEGER,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

CREATE INDEX idx_task_resource_task_id ON task_resource_usage(task_id);
CREATE INDEX idx_task_resource_collected ON task_resource_usage(collected_at);

-- 审计日志表
CREATE TABLE audit_logs (
    audit_id VARCHAR(64) PRIMARY KEY,
    actor_id VARCHAR(64) NOT NULL,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(64) NOT NULL,
    old_value JSON,
    new_value JSON,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_created_at ON audit_logs(created_at);
CREATE INDEX idx_audit_actor ON audit_logs(actor_id);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
```

### 5.2 任务表变更

```sql
-- 新增字段到 tasks 表
ALTER TABLE tasks ADD COLUMN cancelled_at TIMESTAMP;
ALTER TABLE tasks ADD COLUMN cancelled_by VARCHAR(64);
ALTER TABLE tasks ADD COLUMN cancel_reason TEXT;
ALTER TABLE tasks ADD COLUMN is_public BOOLEAN DEFAULT FALSE;
```

---

## 6. 实现路径

### 6.1 Phase 2.3 任务分解 (Week 5-6)

| 任务 | 工期 | 依赖 | 交付物 | 优先级 |
|------|------|------|--------|--------|
| **RBAC 层级扩展** | | | | |
| Organization/Team 模型 | 2d | DB迁移 | 3个新模型 | P0 |
| TeamMembership 管理 API | 2d | Org/Team模型 | CRUD API | P0 |
| PermissionChecker 扩展 | 1d | Team模型 | 继承逻辑实现 | P0 |
| **任务进度 API** | | | | |
| 任务取消功能 | 2d | - | DELETE /tasks/{id} | P0 |
| 任务历史 API | 1d | TaskHistory模型 | GET /tasks/{id}/history | P1 |
| 任务资源 API | 2d | ResourceUsage模型 | GET /tasks/{id}/resources | P1 |
| **审计日志** | | | | |
| AuditLog 模型 | 1d | - | 审计日志表 | P1 |
| 审计中间件 | 1d | AuditLog | 自动记录变更 | P2 |

### 6.2 实现顺序

```
Week 5 Day 1-2: Database Migration + Organization/Team Models
Week 5 Day 3-4: TeamMembership API + PermissionChecker Extension
Week 5 Day 5: Task Cancellation (Backend + API)
Week 6 Day 1-2: Task History API + AuditLog
Week 6 Day 3-4: Task Resources API
Week 6 Day 5: Integration Testing + Documentation
```

### 6.3 关键代码片段

#### 6.3.1 任务取消实现

```python
# src/algo_studio/core/task_manager.py (扩展)

class TaskManager:
    """任务管理器（扩展取消功能）"""

    async def cancel_task(self, task_id: str, cancelled_by: str, reason: str = None) -> Task | None:
        """取消任务"""
        task = self._tasks.get(task_id)
        if not task:
            return None

        if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            raise ValueError(f"Cannot cancel task in status: {task.status.value}")

        # 发送 Ray 取消信号
        if task.status == TaskStatus.RUNNING and task.assigned_node:
            try:
                ray_client = RayClient()
                await ray_client.cancel_task(task_id, task.assigned_node)
            except Exception as e:
                logger.warning(f"Failed to send cancel signal to Ray: {e}")

        # 更新任务状态
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        task.cancelled_at = datetime.now()
        task.cancelled_by = cancelled_by
        task.cancel_reason = reason

        # 记录历史
        self._record_history(
            task_id=task_id,
            event="cancelled",
            actor=cancelled_by,
            details={"reason": reason} if reason else {}
        )

        return task
```

#### 6.3.2 任务历史记录

```python
# src/algo_studio/core/task_manager.py (扩展)

def _record_history(self, task_id: str, event: str, actor: str = None, details: dict = None):
    """记录任务历史"""
    history_id = f"hist-{uuid.uuid4().hex[:12]}"
    history = TaskHistory(
        history_id=history_id,
        task_id=task_id,
        event=event,
        actor=actor or "system",
        details=details or {}
    )
    # 存储到数据库
    self._db_session.add(history)
    self._db_session.commit()
```

#### 6.3.3 资源使用采集

```python
# src/algo_studio/monitor/resource_collector.py (新增)

class ResourceCollector:
    """任务资源使用采集器"""

    def __init__(self, ray_client: RayClient):
        self.ray_client = ray_client

    async def collect_usage(self, task_id: str, node_ip: str) -> TaskResourceUsage:
        """采集指定任务的资源使用"""
        # 从 Ray 指标 API 获取
        metrics = await self.ray_client.get_task_metrics(task_id, node_ip)

        return TaskResourceUsage(
            usage_id=f"usage-{uuid.uuid4().hex[:12]}",
            task_id=task_id,
            node_ip=node_ip,
            gpu_memory_used_mb=metrics.get("gpu_memory_used_mb"),
            gpu_utilization_percent=metrics.get("gpu_utilization"),
            cpu_percent=metrics.get("cpu_percent"),
            memory_used_mb=metrics.get("memory_used_mb"),
            disk_read_bytes=metrics.get("disk_read"),
            disk_write_bytes=metrics.get("disk_write"),
            task_progress=metrics.get("progress", 0),
            collected_at=datetime.now()
        )
```

---

## 附录

### A. 参考资料

1. NIST RBAC: https://csrc.nist.gov/projects/role-based-access-control
2. FastAPI Permissions: https://fastapi.tiangolo.com/tutorial/security/
3. SQLAlchemy Async: https://docs.sqlalchemy.org/en/20/async.html

### B. 待决策项

1. **Organization 默认配额**: 是否需要预设默认组织配额？
2. **任务删除 vs 取消**: DELETE /tasks/{id} 是彻底删除还是标记删除？
3. **资源采集频率**: 任务运行时资源采集间隔（建议 10s）？
4. **审计日志保留期**: 审计日志保留多长时间？（建议 90 天）

### C. 变更记录

| 版本 | 日期 | 修订内容 |
|------|------|----------|
| v1.0 | 2026-03-27 | 初始版本 |

---

**文档状态**: 待评审
