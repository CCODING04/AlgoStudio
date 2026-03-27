# AlgoStudio Phase 2 后端架构研究报告

**版本**: v5.0
**日期**: 2026-03-26
**作者**: 后端研究员
**状态**: 最终版（根据架构评审第4轮反馈）

---

## 目录

1. [问题分析](#1-问题分析)
2. [告警与通知系统设计](#2-告警与通知系统设计)
3. [API 文档自动化](#3-api-文档自动化)
4. [数据库选型与架构](#4-数据库选型与架构)
5. [用户权限数据模型](#5-用户权限数据模型)
6. [配额管理数据模型](#6-配额管理数据模型)
7. [API 认证方案](#7-api-认证方案)
8. [邮件队列实现设计](#8-邮件队列实现设计)
9. [推荐方案总结](#9-推荐方案总结)
10. [实施计划](#10-实施计划)
11. [风险点和缓解措施](#11-风险点和缓解措施)

---

## 1. 问题分析

### 1.1 当前痛点

| 问题 | 现状 | 影响 |
|------|------|------|
| 任务无持久化 | TaskManager 使用内存存储 `Dict[str, Task]` | 重启后任务历史丢失 |
| 无告警机制 | 任务失败/GPU 问题时无通知 | 用户无法及时发现问题 |
| 无用户权限 | 所有 API 无认证 | 无法区分用户，无法做配额控制 |
| 无 API 文档管理 | 依赖 FastAPI 自动生成 | 无法定制化，无法 API Key 管理 |
| 告警历史缺失 | 告警事件未记录 | 无法追溯和分析 |

### 1.2 Phase 2 需求梳理

#### Task #5: 告警与通知
- **告警规则**: 任务失败、GPU 内存不足、节点离线
- **通知渠道**: Web UI 提醒（已支持 SSE）、邮件通知
- **告警历史**: 持久化存储告警记录

#### Task #10: API 文档
- **Swagger UI 集成**: 深度定制品牌样式
- **API Key 管理**: 创建、轮换、撤销 API Key

#### 后端架构扩展
- **任务历史存储**: 从内存迁移到数据库
- **用户权限**: RBAC 模型
- **配额管理**: 基于用户/角色的任务配额限制

---

## 2. 告警与通知系统设计

### 2.1 技术方案对比

#### 2.1.1 告警规则引擎

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **简单条件配置** | 轻量、易实现、易维护 | 仅支持简单条件 | ★★★★★ |
| rule-engine 库 | Python 原生、表达式丰富 | 维护不活跃 | ★★★☆☆ |
| Drools (Java) | 业界标准、功能强大 | 过于笨重、不适合 Python 项目 | ★☆☆☆☆ |
| 自定义 DSL | 完全可控、可定制 | 开发成本高 | ★★★★☆ |

**推荐**: 采用 **简单条件配置 + Python 表达式** 的轻量方案

#### 2.1.2 实时通知技术对比

| 技术 | 适用场景 | 延迟 | 实现复杂度 | 推荐 |
|------|----------|------|------------|------|
| **SSE (Server-Sent Events)** | Web UI 实时推送 | <100ms | 低 | ★★★★★ |
| WebSocket | 双向通信、聊天类 | <50ms | 中 | ★★★★☆ |
| Polling | 简单轮询 | >1s | 低 | ★★☆☆☆ |

**推荐**: 继续使用 **SSE**（项目已有 `sse-starlette` 依赖）

#### 2.1.3 邮件通知方案

| 方案 | 可靠性 | 异步支持 | 推荐 |
|------|--------|----------|------|
| **aiosmtplib + 邮件队列** | 高（重试机制） | 原生 | ★★★★★ |
| smtplib 同步 | 中（阻塞） | 需线程池 | ★★★☆☆ |
| 第三方服务 (SendGrid) | 高 | API | ★★★☆☆ |

**推荐**: **aiosmtplib + Redis 队列** 实现可靠异步邮件

### 2.2 告警系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Alert System Architecture                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐ │
│  │ Alert Source  │────▶│ Alert Rule  │────▶│ Alert Channel       │ │
│  │              │     │  Engine      │     │                      │ │
│  │ - TaskFailed │     │              │     │ ┌──────────────────┐ │ │
│  │ - GPU OOM    │     │ condition    │     │ │ SSE (Web UI)     │ │ │
│  │ - NodeOffline│     │ evaluation   │     │ ├──────────────────┤ │ │
│  │ - TaskTimeout│     │              │     │ │ Email (aiosmtplib│ │ │
│  └──────────────┘     └──────────────┘     │ ├──────────────────┤ │ │
│                                             │ │ Webhook          │ │ │
│                                             │ └──────────────────┘ │ │
│                                             └──────────────────────┘ │
│                                    │                   │            │
│                                    ▼                   ▼            │
│                           ┌──────────────┐     ┌──────────────┐     │
│                           │ Alert Store  │     │ Alert History │     │
│                           │ (Redis Pub/Sub)│     │ (SQLite/PG)   │     │
│                           └──────────────┘     └──────────────┘     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.3 告警规则配置格式

```yaml
# alerts.yaml
alert_rules:
  - name: "task_failed"
    condition: "task.status == 'failed'"
    severity: "error"
    channels: ["sse", "email"]
    cooldown_seconds: 300  # 防止重复告警

  - name: "gpu_memory_low"
    condition: "gpu_memory_percent > 90"
    severity: "warning"
    channels: ["sse"]
    cooldown_seconds: 600

  - name: "node_offline"
    condition: "node.status == 'offline'"
    severity: "critical"
    channels: ["sse", "email"]
    cooldown_seconds: 60
```

### 2.4 告警数据模型

```python
class AlertType(str, Enum):
    TASK_FAILED = "task_failed"
    TASK_TIMEOUT = "task_timeout"
    GPU_OOM = "gpu_oom"
    NODE_OFFLINE = "node_offline"
    QUOTA_EXCEEDED = "quota_exceeded"

class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class Alert:
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    source: str  # task_id, node_ip, etc.
    created_at: datetime
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
```

---

## 3. API 文档自动化

### 3.1 Swagger UI 深度定制

项目已有 `sse-starlette>=1.6.0`，FastAPI 原生支持 Swagger UI。

#### 定制方案

| 需求 | 实现方式 |
|------|----------|
| 品牌样式定制 | 自定义 CSS/JS，替换 CDN 资源 |
| 离线文档 | 打包 swagger-ui-bundle.js 到 static 目录 |
| API 版本管理 | OpenAPI schema 多版本标签 |
| 认证说明 | 在 Swagger UI 添加 API Key 认证入口 |

#### 实现示例

```python
from fastapi.openapi.docs import get_swagger_ui_html

app = FastAPI(docs_url=None)  # 禁用默认

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="AlgoStudio API",
        swagger_js_url="/static/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui/swagger-ui.css"
    )
```

### 3.2 API Key 管理

#### API Key 模型

```python
@dataclass
class APIKey:
    key_id: str  # 用于索引，不暴露完整 key
    key_hash: str  # SHA256 哈希存储
    user_id: str
    name: str
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    is_active: bool
```

#### Key 管理 API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/keys` | POST | 创建新 API Key |
| `/api/keys` | GET | 列出用户的 Key |
| `/api/keys/{key_id}` | DELETE | 撤销 Key |
| `/api/keys/{key_id}/rotate` | POST | 轮换 Key |

---

## 4. 数据库选型与架构

### 4.1 SQLite vs PostgreSQL 对比

| 维度 | SQLite | PostgreSQL |
|------|--------|------------|
| **适用规模** | 单机/小规模 (<100万记录) | 分布式/大规模 |
| **并发写入** | 支持有限（写锁） | MVCC 高并发 |
| **数据类型** | 基础类型 | JSON、数组、向量等 |
| **部署复杂度** | 无需服务 | 需要部署服务 |
| **备份恢复** | 简单（文件复制） | pg_dump |
| **性能** | 读密集场景优秀 | 复杂查询优秀 |
| **成本** | 免费 | 免费（自部署） |

### 4.2 推荐方案

**Phase 2 建议: SQLite (WAL 模式) + 写入分离 + PostgreSQL 预规划**

理由:
1. **项目规模**: AlgoStudio 是内部算法平台，预计任务量 < 10万/天
2. **部署简单**: 无需额外数据库服务，与项目一起部署
3. **已有方案**: SQLiteStore 已用于 scheduler memory
4. **迁移路径**: 未来如需扩展，可迁移到 PostgreSQL（SQLAlchemy 支持）

**三重写入压力分析**:

SQLite 在 Phase 2 面临的写入操作:
1. **任务状态更新**: 任务创建、状态变更、进度更新（高频）
2. **告警记录写入**: 每条告警需要持久化（中等频率）
3. **配额使用更新**: 任务开始/结束时扣减配额（中等频率）

**并发写入缓解方案**:

| 方案 | 实现方式 | 适用场景 | 推荐度 |
|------|----------|----------|--------|
| **WAL 模式** | `PRAGMA journal_mode=WAL` | 读多写少 | ★★★★★ |
| **连接池** | SQLAlchemy QueuePool(max_overflow=10) | 限制并发 | ★★★★☆ |
| **写入队列** | Redis 队列缓冲写入（批量提交） | 高频写入 | ★★★★☆ |
| **写入分离** | 读库 + 写库分离 | 读写分离 | ★★★☆☆ |
| **PostgreSQL** | 早期引入 | 多节点/高并发 | ★★★☆☆ |

**Phase 2 推荐组合**: WAL 模式 + 写入队列（批量提交）

```python
# 写入队列缓冲：减少 SQLite 随机写入
class WriteBuffer:
    """批量写入缓冲，减少 SQLite 压力"""
    def __init__(self, flush_interval=1.0, max_buffer=100):
        self.buffer = []
        self.flush_interval = flush_interval
        self.max_buffer = max_buffer

    async def add(self, table: str, data: dict):
        self.buffer.append((table, data))
        if len(self.buffer) >= self.max_buffer:
            await self.flush()

    async def flush(self):
        # 批量写入 SQLite
        for table, data in self.buffer:
            await db.execute(f"INSERT INTO {table} ...", data)
        self.buffer.clear()
```

**WAL 模式配置**:
```python
# SQLite 启用 WAL 模式，缓解写锁竞争
engine = create_async_engine(
    "sqlite+aiosqlite:///./algo_studio.db",
    connect_args={"check_same_thread": False},
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10
)
# 连接后执行 PRAGMA journal_mode=WAL
```

**与 Redis 6380 集成**:
- Redis 6380 用于：配额计数器、会话缓存、邮件队列（Stream）
- SQLite 用于：用户数据、任务历史、告警记录（持久化）
- 两者的职责分离：Redis 处理高频轻量操作，SQLite 处理事务性持久化

**Redis 依赖降级方案**:

| Redis 用途 | 降级方案 | 降级条件 |
|------------|----------|----------|
| **配额计数器** | SQLite 本地计数器 | Redis 不可达 |
| **邮件队列** | 同步邮件发送（阻塞） | Redis 不可达 |
| **SSE 告警** | WebSocket 轮询降级 | Redis Pub/Sub 不可达 |
| **会话缓存** | 数据库直接查询 | Redis 不可达 |

```python
class RedisFallback:
    """Redis 降级处理"""

    async def get_quota(user_id: str) -> Optional[int]:
        try:
            return await redis.get(f"quota:{user_id}")
        except redis.ConnectionError:
            # 降级: 从 SQLite 读取
            return await db.query(QuotaUsage).filter(
                QuotaUsage.user_id == user_id
            ).first().concurrent_tasks

    async def enqueue_email(email: EmailMessage):
        try:
            await redis.xadd("email:stream", ...)
        except redis.ConnectionError:
            # 降级: 同步发送邮件
            await send_email_sync(email)
            logger.warning("Redis 不可用，邮件同步发送")
```

> **降级原则**: Redis 不可用时，系统降级为同步模式继续运行，不阻塞核心业务流程。降级期间的配额数据可能略有延迟，但最终一致性由 SQLite 保障。

**Phase 3 建议: PostgreSQL (如需多节点部署)**

> **架构决策点**: 如果 Phase 2 实测发现 SQLite 写入延迟 > 100ms 或频繁锁等待，应在 Phase 2.4 提前引入 PostgreSQL，避免后续重构成本。

### 4.3 数据库模型设计

#### 4.3.1 任务历史表

```sql
CREATE TABLE tasks (
    task_id VARCHAR(64) PRIMARY KEY,
    task_type VARCHAR(20) NOT NULL,  -- train/infer/verify
    algorithm_name VARCHAR(100) NOT NULL,
    algorithm_version VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- pending/running/completed/failed/cancelled
    config JSON,
    result JSON,
    error TEXT,
    assigned_node VARCHAR(100),
    user_id VARCHAR(64),  -- 新增: 关联用户
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    progress INTEGER DEFAULT 0  -- 0-100
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_user ON tasks(user_id);
CREATE INDEX idx_tasks_created ON tasks(created_at DESC);
```

#### 4.3.2 告警历史表

```sql
CREATE TABLE alerts (
    alert_id VARCHAR(64) PRIMARY KEY,
    alert_type VARCHAR(30) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT,
    source VARCHAR(100),  -- task_id, node_ip, etc.
    task_id VARCHAR(64),   -- 关联任务（可选，告警来源是任务时）
    metadata JSON,
    user_id VARCHAR(64),  -- 告警接收人
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP,
    acknowledged_by VARCHAR(64),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_alerts_created ON alerts(created_at DESC);
CREATE INDEX idx_alerts_user ON alerts(user_id);
CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_task ON alerts(task_id);
```

#### 4.3.3 用户表

```sql
CREATE TABLE users (
    user_id VARCHAR(64) PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),  -- bcrypt
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### 4.3.4 API Keys 表

```sql
CREATE TABLE api_keys (
    key_id VARCHAR(64) PRIMARY KEY,
    key_hash VARCHAR(64) NOT NULL,  -- SHA256
    user_id VARCHAR(64) NOT NULL,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    last_used_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
```

### 4.4 Alembic 迁移配置

```python
# alembic/env.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import asyncio

async def run_migrations():
    engine = create_async_engine("sqlite+aiosqlite:///./algo_studio.db")
    async with engine.begin() as conn:
        await conn.run_sync(alembic_env.configure)
```

### 4.5 Alembic 迁移回滚方案

**回滚策略**:

| 场景 | 回滚方式 | 操作 |
|------|----------|------|
| 单次迁移失败 | `alembic downgrade -1` | 回退上一个版本 |
| 数据迁移失败 | `alembic downgrade + 迁移版本` | 保留数据，回退表结构 |
| 严重故障 | 数据库备份恢复 | 从备份恢复 + 重新迁移 |

**迁移安全检查清单**:
```yaml
# 每次迁移必须满足以下条件：
pre_migration_checks:
  - backup_required: true
  - downgraded_test: true      # 先 downgrade 再 upgrade 测试
  - data_integrity_check: true  # 验证数据完整性
  - rollback_plan: documented  # 记录回滚步骤

# 示例迁移脚本结构
migration_template:
  upgrade:
    - backup_database: "cp algo_studio.db algo_studio.db.bak"
    - run_migration: "alembic upgrade head"
    - verify_data: "SELECT COUNT(*) FROM new_table"
  downgrade:
    - restore_backup: "cp algo_studio.db.bak algo_studio.db"
    - verify_restore: "SELECT COUNT(*) FROM original_table"
```

**每日备份机制**:
```bash
# crontab 每日备份
0 2 * * * cp /path/to/algo_studio.db /backup/algo_studio_$(date +%Y%m%d).db
# 保留最近 7 天备份
0 3 * * * find /backup -name "algo_studio_*.db" -mtime +7 -delete
```

---

## 5. 用户权限数据模型

### 5.1 RBAC 模型设计

```
┌─────────┐     ┌──────────┐     ┌───────────┐
│  User   │────▶│ UserRole │◀────│   Role    │
└─────────┘     └──────────┘     └───────────┘
                             │
                             ▼
                        ┌─────────────┐     ┌───────────┐
                        │ RolePermission│────▶│ Permission│
                        └─────────────┘     └───────────┘
```

### 5.2 权限定义

| 权限 | 代码 | 描述 |
|------|------|------|
| task:create | `task.create` | 创建任务 |
| task:read | `task.read` | 查看任务 |
| task:delete | `task.delete` | 删除任务 |
| admin:user | `admin.user` | 管理用户 |
| admin:quota | `admin.quota` | 管理配额 |
| admin:alert | `admin.alert` | 管理告警规则 |

### 5.3 角色定义

| 角色 | 权限 |
|------|------|
| viewer | task:read |
| developer | task:create, task:read, task:delete |
| admin | 全部权限 |

### 5.4 数据模型

```python
class Role(str, Enum):
    VIEWER = "viewer"
    DEVELOPER = "developer"
    ADMIN = "admin"

@dataclass
class User:
    user_id: str
    username: str
    email: Optional[str]
    role: Role
    is_active: bool

@dataclass
class Quota:
    user_id: str
    max_concurrent_tasks: int  # 并发任务数限制
    max_tasks_per_day: int     # 每日任务数限制
    max_gpu_hours_per_day: float  # GPU 小时限制
```

### 5.5 FastAPI 权限依赖

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def get_current_user(api_key: str = Depends(api_key_header)) -> User:
    # 验证 API Key 并返回用户
    ...

def require_permission(permission: str):
    async def permission_check(user: User = Depends(get_current_user)):
        if permission not in get_user_permissions(user):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return permission_check

# 使用
@app.post("/tasks")
async def create_task(
    request: TaskCreateRequest,
    user: User = Depends(require_permission("task.create"))
):
    ...
```

---

## 6. 配额管理数据模型

> **与资源配额报告对齐**: 本节与 `resource-quota-management-report.md` 保持一致，使用统一的 `Quota`, `ResourceQuota`, `QuotaUsage` 数据模型。

### 6.1 配额维度

| 配额类型 | 描述 | 默认值 | 对应字段 |
|----------|------|--------|----------|
| `concurrent_tasks` | 最大并发任务数 | 5 | max_concurrent_tasks |
| `tasks_per_day` | 每日最大任务数 | 50 | max_tasks_per_day |
| `gpu_hours_per_day` | 每日最大 GPU 时长 | 24h | max_gpu_hours_per_day |
| `storage_gb` | 最大存储使用 (GB) | 100GB | max_storage_gb |

### 6.2 配额检查流程

```
创建任务请求
     │
     ▼
┌──────────────┐     超过配额     ┌──────────┐
│ QuotaChecker │────────────────▶│  拒绝请求  │
└──────────────┘                └──────────┘
     │ 通过配额
     ▼
┌──────────────┐
│ 创建任务     │
│ 扣减配额     │
└──────────────┘
```

### 6.3 数据模型（与 resource-quota-report 对齐）

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class QuotaScope(Enum):
    """配额作用域"""
    USER = "user"
    TEAM = "team"
    GLOBAL = "global"

@dataclass
class ResourceQuota:
    """资源配额（与 resource-quota-report 保持一致）"""
    cpu_cores: float = 8.0
    gpu_count: int = 1
    memory_gb: float = 32.0
    disk_gb: float = 100.0
    concurrent_tasks: int = 5
    tasks_per_day: int = 50
    gpu_hours_per_day: float = 24.0

@dataclass
class QuotaUsage:
    """资源使用量"""
    cpu_cores_used: float = 0.0
    gpu_count_used: int = 0
    memory_gb_used: float = 0.0
    disk_gb_used: float = 0.0
    concurrent_tasks: int = 0
    tasks_today: int = 0
    gpu_minutes_today: float = 0.0

@dataclass
class Quota:
    """配额实体"""
    quota_id: str
    scope: QuotaScope
    scope_id: str  # user_id, team_id, 或 "global"
    name: str
    quota: ResourceQuota  # 字段名与 resource-quota-report 一致
    is_active: bool = True
    parent_quota_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def can_allocate(self, usage: QuotaUsage, requested: ResourceQuota) -> tuple[bool, List[str]]:
        """检查是否可以分配指定资源"""
        reasons = []
        if usage.concurrent_tasks + requested.concurrent_tasks > self.quota.concurrent_tasks:
            reasons.append(f"并发任务数超限: {usage.concurrent_tasks}/{self.quota.concurrent_tasks}")
        if usage.tasks_today + 1 > self.quota.tasks_per_day:
            reasons.append(f"每日任务数超限: {usage.tasks_today}/{self.quota.tasks_per_day}")
        if usage.gpu_count_used + requested.gpu_count > self.quota.gpu_count:
            reasons.append(f"GPU 数量超限: {usage.gpu_count_used}/{self.quota.gpu_count}")
        return (len(reasons) == 0, reasons)
```

> **字段名一致性说明**: 本报告使用 `ResourceQuota` 作为字段名，与 `resource-quota-report.md` 保持一致。旧版本中的 `ResourceLimits` 已废弃，统一使用 `ResourceQuota`。

### 6.4 与调度层的数据同步

1. **调度层** (`quota_manager.py`) 使用 `ResourceQuota` 进行实时配额检查
2. **后端层** (`QuotaLimit`) 进行每日/累计配额校验
3. 两者共用 `quota_id` 作为关联键
4. **Redis 6380** 存储实时配额计数器，**SQLite** 存储配额定义和历史

---

## 7. API 认证方案

### 7.1 认证方案对比

| 方案 | 优点 | 缺点 | 推荐场景 |
|------|------|------|----------|
| **API Key** | 简单、适用于服务间调用 | 无用户上下文 | 机器/服务账号 |
| **JWT** | 无状态、带用户上下文 | 需要刷新机制 | Web/移动端 |
| **OAuth2** | 第三方登录、细粒度权限 | 实现复杂 | 需要第三方登录 |
| **Session** | 传统 Web 熟悉 | 不适合 API | 传统 Web 应用 |

### 7.2 推荐方案

**Phase 2: API Key 认证 + SSE 豁免机制**

理由:
1. 实现简单，与现有 Web UI 架构匹配
2. 适用于服务间调用（CLI、Web 前端）
3. 用户身份通过 Key 关联，支持配额和权限

**API Key 认证与 SSE 长连接兼容性解决方案**:

| 方案 | 实现 | 优缺点 |
|------|------|--------|
| **方案 A: SSE 豁免认证** | SSE 端点不强制认证，WebSocket 建立后通过 message 传递 API Key | 简单，但 SSE 端点开放 |
| **方案 B: Token 机制** | SSE 连接时传递临时 token，验证后建立长连接 | 安全，但实现复杂 |
| **方案 C: 分离认证** | 认证服务签发 token，SSE 使用 token 验证 | 架构清晰，适合多端 |

**推荐: 方案 A + 限制**

```python
# SSE 端点使用可选认证
@app.get("/api/alerts/sse")
async def alert_sse(request: Request):
    # 从请求头获取 API Key（如果提供）
    api_key = request.headers.get("X-API-Key")
    user = None
    if api_key:
        user = await verify_api_key(api_key)
    # SSE 仍然关联到 user（如果提供），用于过滤告警
    return EventSourceResponse(
        alert_generator(user),
        media_type="text/event-stream"
    )

# 普通 API 端点强制认证
@app.post("/tasks", dependencies=[Depends(require_api_key)])
async def create_task(...):
    # 强制要求 API Key
    ...
```

> **安全说明**: SSE 豁免认证意味着 `/api/alerts/sse` 端点可以匿名访问，但返回的告警内容会根据请求中的 API Key 过滤（如果提供）。无 Key 的请求返回公开告警（如系统级告警）。

### 7.5 SSE 告警内容过滤逻辑

**匿名访问时的过滤策略**:

```python
async def alert_generator(request: Request, user: Optional[User]):
    """
    SSE 告警生成器

    过滤逻辑:
    - 有 API Key: 只推送该用户有权限看到的告警（user_id 匹配 或 系统级告警）
    - 无 API Key: 只推送系统级公开告警（severity=critical 且 source='system'）
    """
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("alerts:public")  # 所有连接都订阅公共频道

    if user:
        # 有认证用户：额外订阅个人告警频道
        await pubsub.subscribe(f"alerts:user:{user.user_id}")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                alert_data = json.loads(message["data"])
                # 应用过滤规则
                if should_deliver_alert(alert_data, user):
                    yield format_sse_event(alert_data)
    finally:
        await pubsub.unsubscribe()

def should_deliver_alert(alert: dict, user: Optional[User]) -> bool:
    """判断是否应向用户推送此告警"""
    if user is None:
        # 匿名用户：只推送系统级公开告警
        return alert.get("source") == "system" and alert.get("severity") == "critical"

    # 认证用户：推送用户专属告警 + 系统公开告警
    if alert.get("source") == "system" and alert.get("severity") == "critical":
        return True  # 系统公开告警
    if alert.get("user_id") == user.user_id:
        return True  # 用户专属告警
    if alert.get("user_id") is None and alert.get("is_public"):
        return True  # 标记为公开的告警
    return False
```

> **过滤逻辑说明**:
> 1. **匿名用户**: 只能收到 `source=system` 且 `severity=critical` 的系统级公开告警
> 2. **认证用户**: 收到自己的告警 + 所有系统公开告警
> 3. **用户告警隔离**: 用户 A 不会收到用户 B 的告警，确保隐私
> 4. **SSE 连接建立时**: 即使用户提供了 API Key，也会先验证 Key 有效性，无效 Key 会被拒绝连接

### 7.3 API Key 认证实现

```python
# 安全存储: 只存储 key 的 SHA256 哈希
import hashlib
import secrets

def generate_api_key() -> tuple[str, str]:
    """生成 API Key，返回 (raw_key, hash)"""
    raw_key = f"algo_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash

def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """验证 API Key"""
    return hashlib.sha256(raw_key.encode()).hexdigest() == stored_hash

# FastAPI 依赖
async def get_api_key(api_key: str = Depends(APIKeyHeader(name="X-API-Key"))):
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    user = await get_user_by_key_hash(key_hash)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return user
```

### 7.4 API Key 管理自举问题解决

**问题**: API Key 管理本身需要认证，如何创建第一个 API Key？

**解决方案**:

| 方案 | 实现 | 适用场景 |
|------|------|----------|
| **初始管理员账号** | 系统初始化时创建默认管理员账号（环境变量配置密码） | 生产部署 |
| **Setup 模式** | 首次启动进入 setup wizard，创建首个用户和 Key | 开发/演示 |
| **CLI 创建** | 使用 `algo-studio admin create-user` 命令行创建 | 服务器运维 |

**推荐: 初始管理员账号 + 强制环境变量 / 随机生成**

```python
import secrets
import string

def generate_secure_password(length: int = 24) -> str:
    """生成安全的随机密码"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# 系统初始化时检查是否已有管理员
async def ensure_initial_admin():
    admin_exists = await db.query(User).filter(User.is_superuser == True).first()
    if not admin_exists:
        # 优先从环境变量读取初始密码
        initial_password = os.getenv("ALGO_STUDIO_INITIAL_PASSWORD")

        if not initial_password:
            # 降级方案: 随机生成密码并输出到日志（仅开发模式）
            if os.getenv("ALGO_STUDIO_ENV") == "development":
                initial_password = generate_secure_password()
                logger.warning(
                    f"ALGO_STUDIO_INITIAL_PASSWORD 未设置，"
                    f"已生成临时密码供首次登录使用: {initial_password}"
                )
                logger.warning("请在首次登录后通过 /api/users/me/password 接口修改密码")
            else:
                # 生产环境必须设置环境变量
                raise RuntimeError(
                    "ALGO_STUDIO_INITIAL_PASSWORD environment variable must be set on first run. "
                    "Generated passwords are not allowed in production."
                )

        # 创建管理员
        await create_user(
            username="admin",
            password=hash_password(initial_password),
            is_superuser=True
        )
```

> **安全改进说明**:
> 1. **移除硬编码默认密码**: 原 `algo-dev-admin-2026` 已被移除，任何环境都不再使用固定默认密码
> 2. **开发模式随机密码**: 未设置环境变量时，生成 24 位 cryptographically secure 随机密码并输出到日志
> 3. **生产环境强制要求**: 非开发模式下必须设置 `ALGO_STUDIO_INITIAL_PASSWORD`，否则拒绝启动
> 4. **引导用户修改**: 日志提示用户首次登录后修改密码

---

## 8. 邮件队列实现设计

### 8.1 Redis Stream vs Pub/Sub 对比

| 特性 | Redis Stream | Redis Pub/Sub |
|------|---------------|---------------|
| **消息持久化** | 支持（RadixTree 存储） | 不支持（仅转发） |
| **消费确认** | 支持（ACK） | 不支持 |
| **消费者组** | 支持（N consumer groups） | 不支持 |
| **消息重试** | 支持（XPENDING + XCLAIM） | 不支持 |
| **消息堆积** | 支持（可配置 MaxLen） | 不支持 |

**推荐**: **Redis Stream** — 适合可靠消息传递，支持消费失败重试和 dead letter 处理。

### 8.2 邮件队列架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Email Queue Architecture                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     XADD      ┌─────────────────────────────────────┐ │
│  │ AlertService │──────────────▶│ email:stream                       │ │
│  │              │               │                                     │ │
│  └──────────────┘               │  Fields:                             │ │
│                                 │  - to, subject, body                 │ │
│                                 │  - retry_count, max_retries          │ │
│                                 │  - created_at                       │ │
│                                 └───────────────┬─────────────────────┘ │
│                                                 │                        │
│                           XREADGROUP GROUP g1   │                        │
│                           (block: 5000ms)       │                        │
│                                                 ▼                        │
│                                 ┌─────────────────────────────────────┐ │
│                                 │ Consumer: email_worker_1            │ │
│                                 │                                     │ │
│                                 │ 1. XCLAIM message                   │ │
│                                 │ 2. Send email via aiosmtplib        │ │
│                                 │ 3. XACK on success                  │ │
│                                 │ 4. On failure: XCLAIM to DLQ       │ │
│                                 └─────────────────────────────────────┘ │
│                                                 │                        │
│                              XCLAIM (retry > max)  │                    │
│                                                 ▼                        │
│                                 ┌─────────────────────────────────────┐ │
│                                 │ email:dlq (Dead Letter Queue)       │ │
│                                 │                                     │ │
│                                 │ - 保存失败消息                       │ │
│                                 │ - 人工干预或定期清理                 │ │
│                                 └─────────────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.3 邮件队列实现

```python
# email_queue.py
import redis.asyncio as redis
from dataclasses import dataclass
from typing import Optional
import asyncio
import aiosmtplib
from email.mime.text import MIMEText

EMAIL_STREAM = "email:stream"
EMAIL_DLQ = "email:dlq"
CONSUMER_GROUP = "email-workers"
CONSUMER_NAME = f"worker-{uuid.uuid4().hex[:8]}"
MAX_RETRIES = 3
STREAM_MAX_LEN = 10000  # 队列长度限制，防止内存溢出

@dataclass
class EmailMessage:
    to: str
    subject: str
    body: str
    retry_count: int = 0
    max_retries: int = MAX_RETRIES

async def enqueue_email(email: EmailMessage):
    """将邮件放入队列"""
    redis_client = await get_redis_client()
    await redis_client.xadd(
        EMAIL_STREAM,
        {
            "to": email.to,
            "subject": email.subject,
            "body": email.body,
            "retry_count": str(email.retry_count),
            "max_retries": str(email.max_retries)
        },
        maxlen=STREAM_MAX_LEN,  # 自动裁剪旧消息
        approximate=True
    )

async def process_email_stream():
    """邮件消费者（后台运行）"""
    redis_client = await get_redis_client()

    # 确保消费者组存在
    try:
        await redis_client.xgroup_create(
            EMAIL_STREAM, CONSUMER_GROUP, id="0", mkstream=True
        )
    except redis.ResponseError:
        pass  # 组已存在

    while True:
        try:
            # 读取新消息（使用 XREADGROUP 配合 XPENDING 保护）
            messages = await redis_client.xreadgroup(
                CONSUMER_GROUP,
                CONSUMER_NAME,
                {EMAIL_STREAM: ">"},  # 仅读新消息
                count=10,
                block=5000
            )

            if not messages:
                # 检查是否有 pending 消息（消费者崩溃后恢复）
                pending = await redis_client.xpending_range(
                    EMAIL_STREAM, CONSUMER_GROUP, min="-", max="+",
                    count=10
                )
                for p in pending:
                    msg_id = p["message_id"]
                    # 认领超过 30 秒未处理的消息
                    if p["time_since_delivered"] > 30000:
                        await redis_client.xclaim(
                            EMAIL_STREAM, CONSUMER_GROUP, CONSUMER_NAME,
                            min_idle_time=30000, message_ids=[msg_id]
                        )
                        # 重新读取并处理
                        msgs = await redis_client.xrange(EMAIL_STREAM, msg_id, msg_id)
                        if msgs:
                            await process_message(redis_client, EMAIL_STREAM, msgs[0])
                continue

            for stream, msgs in messages:
                for msg_id, fields in msgs:
                    await process_message(redis_client, EMAIL_STREAM, (msg_id, fields))

        except redis.ConnectionError as e:
            logger.error(f"Redis 连接失败: {e}, 等待重连...")
            await asyncio.sleep(5)  # Redis 重连等待
        except Exception as e:
            logger.error(f"消费者异常: {e}")
            await asyncio.sleep(1)

async def process_message(redis_client, stream_name, msg):
    """处理单条消息"""
    msg_id, fields = msg
    try:
        email = EmailMessage(
            to=fields[b"to"].decode(),
            subject=fields[b"subject"].decode(),
            body=fields[b"body"].decode(),
            retry_count=int(fields[b"retry_count"]),
            max_retries=int(fields[b"max_retries"])
        )
        await send_email(email)
        await redis_client.xack(stream_name, CONSUMER_GROUP, msg_id)
    except Exception as e:
        logger.error(f"邮件发送失败 (msg_id={msg_id}): {e}")
        await handle_email_failure(redis_client, msg_id, fields, stream_name)

async def handle_email_failure(redis_client, msg_id, fields, source_stream):
    """处理发送失败的邮件"""
    retry_count = int(fields[b"retry_count"]) + 1
    max_retries = int(fields[b"max_retries"])

    if retry_count >= max_retries:
        # 转移到 Dead Letter Queue
        await redis_client.xadd(
            EMAIL_DLQ,
            {**fields, b"failed_at": str(datetime.now().isoformat())}
        )
        await redis_client.xack(source_stream, CONSUMER_GROUP, msg_id)
        await redis_client.xdel(source_stream, msg_id)
        logger.warning(f"邮件消息 {msg_id} 已转移到 DLQ")
    else:
        # 重新入队（更新重试次数）
        fields[b"retry_count"] = str(retry_count)
        await redis_client.xadd(source_stream, fields, maxlen=STREAM_MAX_LEN, approximate=True)
        await redis_client.xack(source_stream, CONSUMER_GROUP, msg_id)
        await redis_client.xdel(source_stream, msg_id)

async def send_email(email: EmailMessage):
    """发送邮件"""
    message = MIMEText(email.body)
    message["From"] = os.getenv("SMTP_FROM", "noreply@algostudio.local")
    message["To"] = email.to
    message["Subject"] = email.subject

    await aiosmtplib.send(
        message,
        hostname=os.getenv("SMTP_HOST", "localhost"),
        port=int(os.getenv("SMTP_PORT", "587")),
        username=os.getenv("SMTP_USER"),
        password=os.getenv("SMTP_PASSWORD"),
        start_tls=True
    )
```

> **Redis Stream 消费者崩溃保护机制**:
> 1. **XPENDING 检查**: 每次循环检查是否有超过 30 秒未处理的 pending 消息
> 2. **XCLAIM 自动认领**: 崩溃消费者未 ACK 的消息会被其他消费者认领处理
> 3. **队列长度限制**: `maxlen=10000` 防止 Redis 内存溢出
> 4. **连接失败重试**: Redis 连接失败时等待 5 秒后重连，不丢失消息
> 5. **DLQ 兜底**: 超过最大重试次数的消息进入 Dead Letter Queue 保留

### 8.4 邮件队列管理命令

```bash
# 查看队列长度
redis-cli XLEN email:stream

# 查看待处理消息（消费者组）
redis-cli XPENDING email:stream email-workers

# 手动重试 DLQ 中的消息
redis-cli XCLAIM email:stream email-workers <msg_id> 1000

# 查看 DLQ
redis-cli XRANGE email:dlq - +
```

---

## 9. 推荐方案总结

### 8.1 技术栈

| 组件 | 推荐方案 | 理由 |
|------|----------|------|
| **数据库** | SQLite + Alembic | 轻量、已用于 scheduler、可迁移 PG |
| **告警存储** | SQLite | 与主库一致 |
| **实时通知** | SSE (已有) | 低延迟、无依赖 |
| **邮件发送** | aiosmtplib + Redis 队列 | 异步可靠 |
| **规则引擎** | 简单条件配置 | 轻量够用 |
| **认证** | API Key (SHA256) | 简单安全 |
| **权限** | RBAC (3 角色) | 够用即可 |
| **配额** | Redis 计数器 | 高性能 |

### 8.2 新增依赖

```
# 新增 requirements
aiosqlite>=0.19.0      # SQLite 异步驱动
alembic>=1.13.0         # 数据库迁移
aiosmtplib>=3.0.0       # 异步邮件
passlib>=1.7.4          # 密码哈希
bcrypt>=4.1.0           # bcrypt 算法
```

### 8.3 架构分层

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer (FastAPI)                     │
│  Routes: tasks, hosts, alerts, users, keys                      │
├─────────────────────────────────────────────────────────────────┤
│                        Service Layer                             │
│  TaskService, AlertService, UserService, QuotaService            │
├─────────────────────────────────────────────────────────────────┤
│                       Repository Layer                           │
│  TaskRepository, AlertRepository, UserRepository                 │
├─────────────────────────────────────────────────────────────────┤
│                         Data Layer                               │
│  SQLite (tasks, alerts, users, quotas)                          │
│  Redis (session, cache, rate limit)                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. 实施计划

### 10.1 Phase 2.1~2.4 依赖关系与关键路径

```
Phase 2.1 (Week 1-2)
    │
    ├── DB 迁移框架 ──────────┐
    ├── 用户/权限模型 ─────────┼──┐
    ├── API Key 管理 ─────────┼──┼──┐
    └── 认证中间件 ────────────┼──┼──┼──┐
                               │  │  │  │
Phase 2.2 (Week 2-3) ───────────┘  │  │  │
    │                                │  │
    ├── TaskRepository ──────────────┘  │
    ├── 任务历史 API ───────────────────┤
    └── 配额管理 (Redis 6380) ───────────┤
                                        │
Phase 2.3 (Week 3-5) ─────────────────────┘
    │
    ├── 告警数据模型 ──────────────────────────┐
    ├── 告警规则引擎 ───────────────────────────┤
    ├── 告警服务 ───────────────────────────────┤
    │                                            │
    │   ├── SSE 告警推送 (依赖 AlertService) ────┤
    │   └── 邮件通知 (依赖 AlertService) ─────────┤
    │         └── Redis Stream 消费者 ──────────┘
    └── 告警历史 API ────────────────────────────┘

Phase 2.4 (Week 4-5) [可与 Phase 2.3 并行]
    │
    ├── Swagger UI 定制
    └── API 文档部署

关键路径 (Critical Path):
Phase 2.1 → Phase 2.2 → Phase 2.3 (告警系统)
总工期: 5 周
```

### Phase 2.1: 基础设施 (Week 1-2)

| 任务 | 工期 | 依赖 | 交付物 | 优先级 |
|------|------|------|--------|--------|
| 数据库迁移框架 | 2d | - | Alembic 配置、Base 模型 | P0 |
| 用户/权限模型 | 3d | DB 迁移 | User, Role, Permission 模型 | P0 |
| API Key 管理 | 2d | 用户模型 | Key CRUD API | P0 |
| 认证中间件 | 2d | Key 管理 | API Key 验证依赖 | P0 |

### Phase 2.2: 任务历史 (Week 2-3)

| 任务 | 工期 | 依赖 | 交付物 | 优先级 |
|------|------|------|--------|--------|
| TaskRepository | 2d | DB 迁移 | 任务持久化 | P0 |
| 任务历史 API | 2d | Repository | GET /tasks/history | P1 |
| 配额管理 | 3d | 用户模型 | QuotaChecker、API | P0 |

### Phase 2.3: 告警系统 (Week 3-5)

| 任务 | 工期 | 依赖 | 交付物 | 优先级 |
|------|------|------|--------|--------|
| 告警数据模型 | 1d | DB 迁移 | Alert 模型 | P0 |
| 告警规则引擎 | 3d | - | RuleEngine、配置解析 | P1 |
| 告警服务 | 3d | 规则引擎 | AlertService | P0 |
| SSE 告警推送 | 2d | AlertService | /api/alerts/sse | P0 |
| 邮件通知 | 3d | AlertService | EmailSender + Redis Stream | P1 |
| 告警历史 API | 2d | 告警模型 | CRUD API | P2 |

### Phase 2.4: API 文档 (Week 4-5) [可与 Phase 2.3 并行]

| 任务 | 工期 | 依赖 | 交付物 | 优先级 |
|------|------|------|--------|--------|
| Swagger UI 定制 | 2d | - | 品牌样式、本地资源 | P2 |
| API 文档部署 | 1d | - | 离线文档 | P2 |

### 工期估算（修订版 v3.0）

| 阶段 | 工期 | 累计 | 说明 |
|------|------|------|------|
| Phase 2.1 | 2 周 | Week 1-2 | 基础设施 + API Key 自举降级 |
| Phase 2.2 | 1.5 周 | Week 2-3.5 | 任务历史与配额 |
| Phase 2.3 | 2.5 周 | Week 3-6 | 告警系统 + SSE 过滤逻辑 |
| Phase 2.4 | 0.5 周 | Week 5-6 | 可与 Phase 2.3 并行 |
| **总计** | **6 周** | | 原估算 5 周偏乐观 |

**工期调整说明**:
1. Phase 2.1 增加 0.5 周：增加 API Key 自举降级处理实现
2. Phase 2.2 增加 0.5 周：配额管理增加降级方案和三重写入优化
3. Phase 2.3 增加 0.5 周：SSE 告警过滤逻辑 + Redis Stream 崩溃保护机制
4. Phase 2.4 可与 Phase 2.3 并行开发，实际项目工期为 6 周

> **里程碑验收**: Week 6 结束时，核心功能（用户认证、配额、告警 SSE、Redis 降级）应可联调测试。

---

## 11. 风险点和缓解措施

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| **SQLite 写锁竞争** | 高 | 确定 | WAL 模式 + 连接池 + 批量写入缓冲 + 实测验证方案 |
| **邮件发送失败** | 中 | 低 | Redis Stream 重试 + DLQ + 降级（SSE） |
| **API Key 安全** | 高 | 低 | 哈希存储（SHA256）+ 过期机制 + 审计日志 |
| **告警风暴** | 中 | 中 | cooldown 机制 + 去重 + 限流 |
| **迁移数据丢失** | 高 | 低 | Alembic 迁移测试 + 每日备份 |
| **SSE 长连接认证** | 中 | 中 | 可选认证 + Token 过滤 |
| **Phase 2.1~2.4 依赖链延迟** | 高 | 中 | 关键路径识别 + P0 优先 + 阶段门禁 + 并行窗口 |
| **Redis 6380 依赖** | 中 | 低 | SQLite 回退方案（配额用本地计数器） |

### 11.1 依赖链风险缓解措施（详细版）

Phase 2.1→2.2→2.3 的依赖链是主要风险点。以下是更具体的缓解措施：

#### 11.1.1 关键路径识别

```
关键路径 (Critical Path) = Phase 2.1(Week 1-2) → Phase 2.2(Week 2-3.5) → Phase 2.3(Week 3-6)
                                       ↓
                    Phase 2.4 可与 Phase 2.3 并行

关键路径任务（P0 优先）:
1. Phase 2.1: 数据库迁移框架、用户模型、认证中间件
2. Phase 2.2: TaskRepository、配额管理
3. Phase 2.3: 告警数据模型、告警服务、SSE 告警推送
```

#### 11.1.2 阶段门禁（Stage Gate）机制

每个 Phase 结束时进行架构师评审，通过后才进入下一阶段：

| 阶段门禁 | 评审内容 | 通过标准 |
|----------|----------|----------|
| **Gate 2.1** | DB 迁移 + 用户模型 + 认证中间件 | 所有 P0 任务单元测试通过 |
| **Gate 2.2** | TaskRepository + 配额 API | 集成测试通过（Mock Redis） |
| **Gate 2.3** | 告警服务 + SSE 推送 | 端到端告警流程测试通过 |
| **Gate 2.4** | API 文档 + Swagger UI | 文档可访问、样式正确 |

#### 11.1.3 并行窗口（Parallel Window）

Phase 2.3 内部的以下任务可以并行开发：

```
并行窗口 (Week 3-4):
├── 任务 A: 告警数据模型 ──────────────────┐
├── 任务 B: 告警规则引擎 ──────────────────┼──→ 告警服务 (Week 4-5)
├── 任务 C: Redis Stream 消费者 ──────────┘
│
└── 并行 (Week 3-5):
    ├── 任务 D: SSE 告警推送 (依赖 告警服务)
    └── 任务 E: 邮件通知 (依赖 Redis Stream)
```

#### 11.1.4 每日 Standup 跟踪

- **每日同步**: 各子任务负责人每日同步进度
- **阻塞升级**: 任何阻塞超过 24 小时的依赖问题，立即升级给架构师
- **方案调整**: 如 Phase 2.1 延期超过 2 天，压缩 Phase 2.2 的任务范围

#### 11.1.5 降级方案（Dependency Fallback）

如果 Phase 2.1 延期超过 1 周，启用降级方案：

| 场景 | 降级措施 |
|------|----------|
| DB 迁移框架延期 | Phase 2.2 先使用内存存储，Phase 2.3 前完成迁移 |
| 用户模型延期 | Phase 2.2 使用匿名任务 + 配额不区分用户 |
| 认证中间件延期 | Phase 2.2 API 先开放，Phase 2.3 前关闭认证 |

---

### 11.2 SQLite 写锁压力实测验证方案

> **验证目标**: 确认 SQLite WAL 模式 + 批量写入缓冲在高并发场景下的写入延迟和锁等待时间满足 Phase 2 要求。

#### 11.2.1 验证环境

| 组件 | 配置 |
|------|------|
| **测试机器** | Head 节点（192.168.0.126） |
| **SQLite 版本** | 3.44.0+ |
| **测试数据库** | `/tmp/test_algo_studio.db`（隔离测试） |
| **并发客户端数** | 1, 5, 10, 20, 50 |
| **测试时长** | 每场景 5 分钟 |

#### 11.2.2 测试方法

**测试脚本**: `tests/performance/test_sqlite_wal_write.py`

```python
import asyncio
import aiosqlite
import time
import statistics
from concurrent.futures import ThreadPoolExecutor

async def write_task(db_path, task_id, iterations=100):
    """单次写入测试"""
    async with aiosqlite.connect(db_path) as db:
        start = time.perf_counter()
        await db.execute(
            "INSERT INTO tasks (task_id, status, config) VALUES (?, ?, ?)",
            (f"task-{task_id}", "running", '{"test": true}')
        )
        await db.commit()
        return time.perf_counter() - start

async def concurrent_write_test(db_path, num_clients, iterations_per_client):
    """并发写入测试"""
    start = time.perf_counter()
    tasks = [
        write_task(db_path, i, iterations_per_client)
        for i in range(num_clients)
    ]
    results = await asyncio.gather(*tasks)
    total_time = time.perf_counter() - start
    all_latencies = [r for sublist in results for r in sublist]
    return {
        "total_time": total_time,
        "avg_latency_ms": statistics.mean(all_latencies) * 1000,
        "p95_latency_ms": statistics.quantiles(all_latencies, n=20)[18] * 1000,
        "p99_latency_ms": statistics.quantiles(all_latencies, n=100)[98] * 1000,
        "throughput_qps": num_clients * iterations_per_client / total_time
    }

async def run_benchmark():
    """运行基准测试"""
    db_path = "/tmp/test_algo_studio.db"
    scenarios = [
        (1, 1000),   # 1 client, 1000 writes
        (5, 200),    # 5 clients, 200 writes each
        (10, 100),   # 10 clients, 100 writes each
        (20, 50),    # 20 clients, 50 writes each
        (50, 20),    # 50 clients, 20 writes each
    ]

    for num_clients, iters in scenarios:
        result = await concurrent_write_test(db_path, num_clients, iters)
        print(f"Clients={num_clients}: "
              f"avg={result['avg_latency_ms']:.2f}ms, "
              f"p95={result['p95_latency_ms']:.2f}ms, "
              f"p99={result['p99_latency_ms']:.2f}ms, "
              f"qps={result['throughput_qps']:.0f}")
```

#### 11.2.3 性能指标与验收标准

| 指标 | Phase 2 要求 | 验收标准 |
|------|-------------|----------|
| **平均写入延迟** | < 10ms | avg_latency_ms < 10 |
| **P95 写入延迟** | < 50ms | p95_latency_ms < 50 |
| **P99 写入延迟** | < 100ms | p99_latency_ms < 100 |
| **最大并发写入** | 支持 20 并发 | 20 clients 测试 qps > 100 |
| **锁等待时间** | < 5ms | wal_write_delay < 5ms |

#### 11.2.4 实测验证计划

| 阶段 | 时间 | 内容 | 验收人 |
|------|------|------|--------|
| **验证 1** | Phase 2.1 结束时 | SQLite WAL 模式单线程写入基准测试 | 后端研究员 |
| **验证 2** | Phase 2.2 结束时 | 5-10 并发写入 + 批量缓冲测试 | 后端研究员 |
| **验证 3** | Phase 2.3 结束时 | 20 并发写入 + 告警触发场景测试 | 后端研究员 |
| **验证 4** | Phase 2.4 结束时 | 50 并发压力测试 + 极限场景 | 后端研究员 |

#### 11.2.5 决策触发条件

```
如果任意一项不满足验收标准，执行以下决策：

| 不满足项 | 决策 |
|----------|------|
| avg_latency_ms > 20ms | 提前引入 PostgreSQL，暂停 Phase 2.2 优化 |
| p95_latency_ms > 100ms | 启用写入队列缓冲（batch_size=50） |
| p99_latency_ms > 200ms | 启用 Redis 写缓冲 + 异步持久化 |
| 20 并发 qps < 50 | 迁移到 PostgreSQL（Phase 3 提前） |
```

> **实测验证负责人**: 后端研究员
> **验证截止时间**: Phase 2.4 结束时（Week 6）
> **记录文档**: `docs/superpowers/validation/sqlite-wal-validation.md`

---

## 附录

### A. 参考资料

1. FastAPI 官方文档: https://fastapi.tiangolo.com/
2. SQLAlchemy 异步: https://docs.sqlalchemy.org/en/20/async.html
3. Alembic 迁移: https://alembic.sqlalchemy.org/
4. aiosmtplib: https://github.com/Coleam/aiosmtplib
5. Redis Pub/Sub vs Streams: https://redis.io/docs/data-types/streams/
6. RBAC 最佳实践: https://csrc.nist.gov/projects/role-based-access-control

### B. 待决策项

1. **PostgreSQL 迁移时机**: Phase 2 中期（Week 3）评估 SQLite 性能，如写入延迟 > 100ms 则提前引入 PG
2. **邮件 SMTP 配置**: 使用公司邮箱还是第三方服务（SendGrid）？
3. **告警接收人**: 如何确定告警发送给谁（用户配置/角色默认）？
4. **公共资源池**: 是否需要 fallback 到公共资源池的机制？

### C. 重大修订记录

| 版本 | 日期 | 修订内容 |
|------|------|----------|
| v1.1 | 2026-03-26 | 根据架构评审反馈修订：SQLite WAL 模式、Redis Stream 邮件队列、API Key + SSE 兼容方案、Alembic 回滚方案、Phase 2.1~2.4 依赖链、工期重新估算（5 周） |
| v3.0 | 2026-03-26 | 根据架构评审第2轮反馈修订：<br>- ResourceLimits → ResourceQuota 字段名统一<br>- API Key 自举增加降级方案（开发环境默认密码）<br>- Redis Stream 消费者崩溃保护（XPENDING + XCLAIM + 队列长度限制）<br>- SQLite 三重写入压力分析 + 批量写入缓冲方案<br>- Redis 依赖增加降级方案（配额/SSE/邮件/会话）<br>- SSE 告警内容过滤逻辑详细说明<br>- 工期调整至 6 周（5 周偏乐观） |
| v4.0 | 2026-03-26 | 根据架构评审第3轮反馈修订：<br>- 移除 Section 7.4 硬编码默认密码 `algo-dev-admin-2026`<br>- 改为：开发环境使用 cryptographically secure 随机密码 + 日志输出<br>- 生产环境强制要求 `ALGO_STUDIO_INITIAL_PASSWORD` 环境变量<br>- 增加 `generate_secure_password()` 函数实现 |
| v5.0 | 2026-03-26 | 根据架构评审第4轮反馈修订：<br>- **依赖链风险缓解（详细版）**: 增加关键路径识别、阶段门禁机制、并行窗口、降级方案<br>- **SQLite 写锁压力实测验证方案**: 增加测试环境配置、测试脚本模板、性能指标与验收标准、实测验证计划、决策触发条件 |

---

**报告完成**
