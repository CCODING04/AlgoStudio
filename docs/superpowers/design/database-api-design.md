# AlgoStudio Phase 2 Database API Design

**Version:** 1.0
**Date:** 2026-03-26
**Author:** Backend Engineer

---

## 1. Overview

This document describes the database schema and API design for Phase 2 of the AlgoStudio backend. It covers:

1. **SQLite WAL Mode Configuration** - Alembic migration setup
2. **User Model** - RBAC-ready user management
3. **Task History Model** - Persistent task storage
4. **Quota Models** - Resource quota and usage tracking
5. **API Endpoints** - REST API for database operations

---

## 2. SQLite WAL Mode Configuration

### 2.1 Why WAL Mode?

SQLite WAL (Write-Ahead Logging) mode provides:
- **Better concurrency**: Readers don't block writers and vice versa
- **Write performance**: Reduces lock contention
- **Crash recovery**: Better durability

### 2.2 Alembic Configuration

Location: `/home/admin02/Code/Dev/AlgoStudio/alembic.ini`

```ini
[alembic]
script_location = src/algo_studio/db/migrations
sqlalchemy.url = sqlite+aiosqlite:///./algo_studio.db
```

### 2.3 WAL Mode Migration

The initial migration (`001_initial.py`) enables WAL mode:

```sql
PRAGMA journal_mode=WAL;
```

This is executed during migration upgrade to ensure WAL mode is active.

### 2.4 PRAGMA Settings

| Setting | Value | Description |
|---------|-------|-------------|
| `journal_mode` | WAL | Write-Ahead Logging mode |
| `busy_timeout` | 30000 | Wait up to 30s for locks |

---

## 3. Database Models

### 3.1 Entity Relationship Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    User     │────▶│    Task     │     │    Quota    │
│             │     │             │     │             │
│ user_id (PK)│     │ task_id (PK)│     │ quota_id (PK│
│ username    │     │ user_id (FK)│     │ scope       │
│ email       │     │ status      │     │ scope_id    │
│ role        │     │ ...         │     │ ...         │
└─────────────┘     └─────────────┘     └─────────────┘
       │                                       │
       │                                       │
       ▼                                       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  QuotaUsage │     │  QuotaUsage │     │  QuotaAlert │
│             │◀────│  History    │     │             │
│ quota_id (PK)     │ quota_id (FK)     │ alert_id (PK)
│ concurrent_ │     │ metric      │     │ quota_id (FK)
│ ...         │     │ value       │     │ level       │
└─────────────┘     └─────────────┘     └─────────────┘
```

### 3.2 User Model

**Table:** `users`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| user_id | VARCHAR(64) | PRIMARY KEY | Unique user identifier |
| username | VARCHAR(100) | UNIQUE, NOT NULL | Username for login |
| email | VARCHAR(255) | UNIQUE | User email address |
| password_hash | VARCHAR(255) | | Bcrypt hashed password |
| role | VARCHAR(20) | DEFAULT 'viewer' | RBAC role: viewer/developer/admin |
| is_active | BOOLEAN | DEFAULT TRUE | Account active status |
| is_superuser | BOOLEAN | DEFAULT FALSE | Superuser flag |
| created_at | TIMESTAMP | NOT NULL | Account creation time |
| updated_at | TIMESTAMP | | Last update time |

**RBAC Roles:**

| Role | Permissions |
|------|-------------|
| viewer | task.read |
| developer | task.create, task.read, task.delete |
| admin | All permissions including admin.user, admin.quota, admin.alert |

### 3.3 Task History Model

**Table:** `tasks`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| task_id | VARCHAR(64) | PRIMARY KEY | Unique task identifier |
| task_type | VARCHAR(20) | NOT NULL | train/infer/verify |
| algorithm_name | VARCHAR(100) | NOT NULL | Algorithm name |
| algorithm_version | VARCHAR(20) | NOT NULL | Algorithm version |
| status | VARCHAR(20) | NOT NULL | pending/running/completed/failed/cancelled |
| config | JSON | | Task configuration |
| result | JSON | | Task execution result |
| error | TEXT | | Error message if failed |
| assigned_node | VARCHAR(100) | | Assigned compute node |
| user_id | VARCHAR(64) | FK(users.user_id) | Owner user |
| progress | INTEGER | DEFAULT 0 | Progress 0-100 |
| created_at | TIMESTAMP | NOT NULL | Task creation time |
| started_at | TIMESTAMP | | Task start time |
| completed_at | TIMESTAMP | | Task completion time |

**Indexes:**
- `idx_tasks_status` on `status`
- `idx_tasks_user` on `user_id`
- `idx_tasks_created` on `created_at`

### 3.4 Quota Models

**Table:** `quotas`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| quota_id | VARCHAR(64) | PRIMARY KEY | Unique quota identifier |
| scope | VARCHAR(20) | NOT NULL | user/team/global |
| scope_id | VARCHAR(64) | NOT NULL | user_id or team_id |
| name | VARCHAR(100) | NOT NULL | Quota name |
| cpu_cores | INTEGER | DEFAULT 0 | CPU cores limit (0=unlimited) |
| gpu_count | INTEGER | DEFAULT 0 | GPU count limit |
| gpu_memory_gb | FLOAT | DEFAULT 0.0 | GPU memory limit (GB) |
| memory_gb | FLOAT | DEFAULT 0.0 | Memory limit (GB) |
| disk_gb | FLOAT | DEFAULT 0.0 | Disk storage limit (GB) |
| concurrent_tasks | INTEGER | DEFAULT 0 | Max concurrent tasks |
| tasks_per_day | INTEGER | DEFAULT 50 | Daily task limit |
| gpu_hours_per_day | FLOAT | DEFAULT 24.0 | Daily GPU hours limit |
| alert_threshold | INTEGER | DEFAULT 80 | Alert threshold (%) |
| parent_quota_id | VARCHAR(64) | | Parent quota for inheritance |
| is_active | BOOLEAN | DEFAULT TRUE | Quota active status |
| created_at | TIMESTAMP | NOT NULL | Creation time |
| updated_at | TIMESTAMP | | Last update time |

**Indexes:**
- `idx_quotas_scope` on `(scope, scope_id)`

**Table:** `quota_usages`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| quota_id | VARCHAR(64) | PRIMARY KEY, FK | Reference to quota |
| cpu_cores_used | FLOAT | DEFAULT 0.0 | Current CPU usage |
| gpu_count_used | INTEGER | DEFAULT 0 | Current GPU usage |
| gpu_memory_gb_used | FLOAT | DEFAULT 0.0 | Current GPU memory usage |
| memory_gb_used | FLOAT | DEFAULT 0.0 | Current memory usage |
| disk_gb_used | FLOAT | DEFAULT 0.0 | Current disk usage |
| concurrent_tasks_used | INTEGER | DEFAULT 0 | Current concurrent tasks |
| tasks_today | INTEGER | DEFAULT 0 | Tasks created today |
| gpu_minutes_today | FLOAT | DEFAULT 0.0 | GPU minutes used today |
| updated_at | TIMESTAMP | NOT NULL | Last update time |

**Table:** `quota_usage_history`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTO | History ID |
| quota_id | VARCHAR(64) | FK | Reference to quota |
| metric | VARCHAR(50) | NOT NULL | Metric name |
| value | FLOAT | NOT NULL | Metric value |
| recorded_at | TIMESTAMP | NOT NULL | Recording time |

**Indexes:**
- `idx_usage_history_quota` on `quota_id`
- `idx_usage_history_recorded` on `recorded_at`

**Table:** `quota_alerts`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| alert_id | VARCHAR(64) | PRIMARY KEY | Alert identifier |
| quota_id | VARCHAR(64) | FK | Reference to quota |
| scope | VARCHAR(20) | NOT NULL | user/team/global |
| scope_id | VARCHAR(64) | NOT NULL | user_id or team_id |
| level | VARCHAR(20) | NOT NULL | info/warning/critical |
| metric | VARCHAR(50) | NOT NULL | Triggered metric |
| usage_percentage | FLOAT | NOT NULL | Usage at alert time (%) |
| threshold | INTEGER | NOT NULL | Threshold that triggered |
| message | TEXT | | Alert message |
| task_id | VARCHAR(64) | | Associated task (for queue alerts) |
| is_acknowledged | BOOLEAN | DEFAULT FALSE | Acknowledged status |
| acknowledged_by | VARCHAR(64) | | User who acknowledged |
| acknowledged_at | TIMESTAMP | | Acknowledgement time |
| created_at | TIMESTAMP | NOT NULL | Alert creation time |

**Indexes:**
- `idx_alerts_quota` on `quota_id`
- `idx_alerts_created` on `created_at`

---

## 4. API Endpoints

### 4.1 Task CRUD API

#### Create Task
```
POST /api/tasks
```

**Request:**
```json
{
  "task_type": "train",
  "algorithm_name": "simple_classifier",
  "algorithm_version": "v1",
  "config": {
    "data_path": "/data/train",
    "epochs": 100
  },
  "user_id": "user-123"
}
```

**Response (201):**
```json
{
  "task_id": "train-abc12345",
  "task_type": "train",
  "algorithm_name": "simple_classifier",
  "algorithm_version": "v1",
  "status": "pending",
  "config": {...},
  "user_id": "user-123",
  "created_at": "2026-03-26T10:00:00Z"
}
```

#### Get Task
```
GET /api/tasks/{task_id}
```

#### List Tasks
```
GET /api/tasks?status=running&user_id=user-123&limit=50&offset=0
```

#### Delete Task
```
DELETE /api/tasks/{task_id}
```

### 4.2 User Management API

#### Create User
```
POST /api/users
```

**Request:**
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "secure_password",
  "role": "developer"
}
```

#### Get User
```
GET /api/users/{user_id}
```

#### List Users
```
GET /api/users?role=developer&limit=20
```

#### Update User
```
PATCH /api/users/{user_id}
```

#### Delete User
```
DELETE /api/users/{user_id}
```

### 4.3 Quota Management API

#### Create Quota
```
POST /api/quotas
```

**Request:**
```json
{
  "scope": "user",
  "scope_id": "user-123",
  "name": "User Quota",
  "limits": {
    "cpu_cores": 16,
    "gpu_count": 2,
    "gpu_memory_gb": 48.0,
    "memory_gb": 128.0,
    "disk_gb": 500.0,
    "concurrent_tasks": 5,
    "tasks_per_day": 50,
    "gpu_hours_per_day": 24.0
  },
  "alert_threshold": 80
}
```

#### Get Quota
```
GET /api/quotas/{quota_id}
```

#### Get Quota by Scope
```
GET /api/quotas/scope/{scope}/{scope_id}
```

**Example:** `GET /api/quotas/scope/user/user-123`

#### Update Quota
```
PATCH /api/quotas/{quota_id}
```

#### Delete Quota
```
DELETE /api/quotas/{quota_id}
```

### 4.4 Quota Usage API

#### Get Quota Usage
```
GET /api/quotas/{quota_id}/usage
```

**Response:**
```json
{
  "quota_id": "quota-123",
  "usage": {
    "cpu_cores_used": 8.0,
    "gpu_count_used": 1,
    "gpu_memory_gb_used": 24.0,
    "memory_gb_used": 64.0,
    "disk_gb_used": 200.0,
    "concurrent_tasks_used": 2,
    "tasks_today": 15,
    "gpu_minutes_today": 480.0
  },
  "percentages": {
    "cpu_cores": 50.0,
    "gpu_count": 50.0,
    "gpu_memory_gb": 50.0,
    "memory_gb": 50.0,
    "concurrent_tasks": 40.0
  }
}
```

#### Get All Quotas Usage Overview
```
GET /api/quotas/usage/overview
```

### 4.5 Alert API

#### List Alerts
```
GET /api/quotas/alerts?acknowledged=false&limit=50
```

#### Acknowledge Alert
```
POST /api/quotas/alerts/{alert_id}/acknowledge
```

**Request:**
```json
{
  "acknowledged_by": "admin-user-id"
}
```

---

## 5. Request/Response Models

### 5.1 Task Models

```python
class TaskCreateRequest(BaseModel):
    task_type: str  # train/infer/verify
    algorithm_name: str
    algorithm_version: str
    config: Dict[str, Any] = {}
    user_id: Optional[str] = None

class TaskResponse(BaseModel):
    task_id: str
    task_type: str
    algorithm_name: str
    algorithm_version: str
    status: str
    config: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    assigned_node: Optional[str]
    user_id: Optional[str]
    progress: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
```

### 5.2 User Models

```python
class UserCreateRequest(BaseModel):
    username: str
    email: Optional[str]
    password: str
    role: str = "viewer"  # viewer/developer/admin

class UserResponse(BaseModel):
    user_id: str
    username: str
    email: Optional[str]
    role: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: Optional[datetime]
```

### 5.3 Quota Models

```python
class QuotaLimits(BaseModel):
    cpu_cores: int = 0
    gpu_count: int = 0
    gpu_memory_gb: float = 0.0
    memory_gb: float = 0.0
    disk_gb: float = 0.0
    concurrent_tasks: int = 0
    tasks_per_day: int = 50
    gpu_hours_per_day: float = 24.0

class QuotaCreateRequest(BaseModel):
    scope: str  # user/team/global
    scope_id: str
    name: str
    limits: QuotaLimits
    alert_threshold: int = 80
    parent_quota_id: Optional[str] = None

class QuotaResponse(BaseModel):
    quota_id: str
    scope: str
    scope_id: str
    name: str
    limits: QuotaLimits
    alert_threshold: int
    parent_quota_id: Optional[str]
    is_active: bool
    usage: Dict[str, float]
    percentages: Dict[str, float]
    created_at: datetime
    updated_at: Optional[datetime]
```

---

## 6. Error Responses

All API endpoints return consistent error responses:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Task with ID train-abc123 not found",
    "details": {}
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| VALIDATION_ERROR | 400 | Invalid request data |
| RESOURCE_NOT_FOUND | 404 | Resource does not exist |
| DUPLICATE_RESOURCE | 409 | Resource already exists |
| PERMISSION_DENIED | 403 | Insufficient permissions |
| QUOTA_EXCEEDED | 422 | Resource quota exceeded |
| INTERNAL_ERROR | 500 | Internal server error |

---

## 7. File Structure

```
src/algo_studio/
├── db/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py          # Base model and mixins
│   │   ├── user.py          # User model
│   │   ├── task.py          # Task history model
│   │   └── quota.py         # Quota models
│   ├── migrations/
│   │   ├── versions/
│   │   │   └── 001_initial.py  # Initial migration with WAL
│   │   ├── env.py           # Alembic env config
│   │   └── script.py.mako   # Migration template
│   └── session.py          # Database session manager
```

---

## 8. Migration Commands

```bash
# Initialize Alembic (already done)
alembic init alembic

# Create a new migration
alembic revision --autogenerate -m "Add new column"

# Run migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current migration
alembic current

# Show migration history
alembic history
```

---

**Document Status:** Complete
**Next Review:** Before Phase 2.1 gate review
