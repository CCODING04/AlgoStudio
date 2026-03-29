# SSH 部署系统架构设计

**版本**: v1.0
**日期**: 2026-03-26
**状态**: Phase 2 Round 1 交付物

---

## 1. 系统架构

### 1.1 整体架构

```
Web Console
    │
    │ POST /api/deploy/worker
    ▼
FastAPI ─────────────────────────────────────────┐
    │                                              │
    ├── asyncio.create_task(run_deploy_task)       │
    │                                              │
    │   ┌──────────────────────────────┐          │
    │   │     DeployProgressStore      │◄─────────┤
    │   │     (内存/Ray Actor)          │          │
    │   └──────────────────────────────┘          │
    │            │                                  │
    │            │ 更新进度                         │
    │            ▼                                  │
    │   SSH (asyncssh) ──► Worker Node              │
    │            │                                  │
    │            │ 执行脚本                         │
    │            ▼                                  │
    └──────────────────────────────────────────────┘
                │
                │ GET /api/deploy/worker/{id}/progress
                ▼
           SSE Client
```

### 1.2 核心组件

| 组件 | 职责 |
|------|------|
| `SSHConnectionPool` | 连接池管理，支持多节点并发 |
| `SSHConnectionManager` | 单连接状态机，处理重连 |
| `DeployProgressStore` | 部署进度存储，SSE 推送 |
| `SSHDeployer` | 部署任务执行器 |
| `IdempotencyChecker` | 幂等性检查 |
| `RollbackManager` | 回滚管理 |

---

## 2. SSH 连接池设计

### 2.1 SSHConnectionPool

```python
class SSHConnectionPool:
    """asyncssh 连接池，支持多节点并发部署"""

    def __init__(
        self,
        max_connections_per_host: int = 2,
        global_max_connections: int = 10,
        connection_timeout: int = 30
    ):
        self.max_per_host = max_connections_per_host
        self.global_max = global_max_connections
        self.timeout = connection_timeout
        self._available: Dict[str, List[asyncssh.Connection]] = defaultdict(list)
        self._active_count = 0
        self._lock = asyncio.Lock()
```

**关键特性**:
- 每个主机多个连接复用（列表队列）
- 全局连接数限制
- 线程安全的获取/释放

### 2.2 连接状态机

```python
class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    IDLE = "idle"
    COMMAND_RUNNING = "command_running"
    RETRYING = "retrying"
    ERROR = "error"
```

**状态转换规则**:

| 当前状态 | 事件 | 目标状态 | 动作 |
|---------|------|---------|------|
| DISCONNECTED | connect() 调用 | CONNECTING | 建立 SSH 连接 |
| CONNECTING | 连接成功 | IDLE | 设置 keepalive |
| CONNECTING | 连接失败 | RETRYING | 记录错误，延迟等待 |
| IDLE | execute() 调用 | COMMAND_RUNNING | 执行命令 |
| IDLE | 连接断开事件 | DISCONNECTED | 触发重连逻辑 |
| COMMAND_RUNNING | 命令完成(exit=0) | IDLE | 返回结果 |
| COMMAND_RUNNING | 命令完成(exit≠0) | ERROR | 记录错误 |
| COMMAND_RUNNING | 连接断开 | RETRYING | 延迟等待重连 |
| RETRYING | 重试超时 | CONNECTING | 重新建立连接 |
| RETRYING | 达到最大重试 | ERROR | 放弃重连 |
| ERROR | reset() 调用 | DISCONNECTED | 重置状态 |

---

## 3. 部署状态机

### 3.1 部署状态

```python
class DeployStatus(str, Enum):
    PENDING = "pending"
    CONNECTING = "connecting"
    DEPLOYING = "deploying"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

### 3.2 部署步骤

| Step | 名称 | 权重 | 描述 |
|------|------|------|------|
| 1 | connecting | 5% | 建立 SSH 连接 |
| 2 | sudo_config | 10% | 配置 sudo 免密码 |
| 3 | create_venv | 20% | 创建 uv 虚拟环境 |
| 4 | install_deps | 25% | 安装依赖 |
| 5 | sync_code | 15% | 同步代码 |
| 6 | start_ray | 15% | 启动 Ray Worker |
| 7 | verify | 10% | 验证连接 |

---

## 4. 幂等性设计

### 4.1 步骤检测

每个部署步骤完成后会创建标记文件：
- `~/.sudo_configured` - sudo 免密码配置完成
- `~/.venv_ready` - 虚拟环境创建完成
- `~/.deps_installed` - 依赖安装完成
- `~/.code_synced` - 代码同步完成
- `~/.ray_started` - Ray Worker 已启动

### 4.2 幂等检查流程

```
部署开始
    │
    ▼
检查步骤标记文件是否存在
    │
    ├── 存在 ──► 跳过该步骤
    │
    └── 不存在 ──► 执行步骤
                    │
                    ▼
              验证步骤结果
                    │
                    ├── 成功 ──► 创建标记文件
                    │
                    └── 失败 ──► 回滚并报错
```

---

## 5. 回滚机制

### 5.1 四层回滚策略

| 层级 | 策略 | 触发条件 |
|------|------|----------|
| L1 | 预配置 sudo NOPASSWD | 首选方案，无需 PTY |
| L2 | get_pty=True + sudo -S | sudoers 不可写但有密码 |
| L3 | sudo -n 检查 + 非 PTY | 无法获取 PTY |
| L4 | 部署失败报告 | 所有方案均失败 |

### 5.2 回滚执行顺序

回滚按相反顺序执行已完成的步骤：
1. 停止 Ray Worker (`ray stop`)
2. 删除代码同步标记
3. 删除依赖安装标记
4. 删除虚拟环境 (`rm -rf ~/.venv-ray`)
5. 删除 sudoers 配置

---

## 6. 安全设计

### 6.1 密码处理

- 密码不落地存储（不使用文件保存）
- 内存加密（尽量缩短明文存在时间）
- TLS 传输（Web -> API 使用 HTTPS）
- 审计日志（记录谁、何时、哪个节点）

### 6.2 命令白名单

仅允许执行白名单中的命令：
- `bash join_cluster.sh`
- `ray start/stop/status`
- `uv python install`, `uv venv`, `uv pip install`
- `rsync -avz --delete ...`
- `sudo tee /etc/sudoers.d/admin02`

### 6.3 危险命令黑名单

绝对禁止：
- `; rm -rf` - 管道后的删除
- `> /dev/sd*` - 直接写设备
- `dd if=* of=/dev` - 磁盘直接写入
- `; shutdown/reboot` - 关机重启
- `eval $var` - eval 变量

---

## 7. API 设计

### 7.1 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/deploy/worker` | 发起部署任务 |
| GET | `/api/deploy/worker/{task_id}` | 获取部署状态 |
| GET | `/api/deploy/worker/{task_id}/progress` | SSE 进度流 |
| DELETE | `/api/deploy/worker/{task_id}` | 取消部署 |
| GET | `/api/deploy/workers` | 列出所有部署记录 |

### 7.2 请求/响应模型

```python
class DeployWorkerRequest(BaseModel):
    node_ip: str
    username: str = "admin02"
    password: str  # 不存储
    head_ip: str
    ray_port: int = 6379
    proxy_url: Optional[str] = None

class DeployProgress(BaseModel):
    task_id: str
    status: DeployStatus
    step: str
    progress: int  # 0-100
    message: str
    error: Optional[str] = None
    node_ip: str
    started_at: datetime
    completed_at: Optional[datetime] = None
```

---

## 8. 并发控制

### 8.1 节点级锁

同一 Worker 节点同时只能有一个部署任务：
```python
self._locks: Dict[str, asyncio.Lock] = {}

async with self._locks[node_ip]:
    # 执行部署
```

### 8.2 全局限流

最多同时部署 N 个节点：
```python
self._semaphore = asyncio.Semaphore(max_concurrent_deploys)
```

---

## 9. 错误处理

### 9.1 错误码

| 错误码 | 说明 |
|--------|------|
| CONNECTION_FAILED | SSH 连接失败 |
| AUTH_FAILED | 认证失败 |
| TIMEOUT | 操作超时 |
| STEP_FAILED | 部署步骤失败 |
| VERIFICATION_FAILED | 验证失败 |

### 9.2 重试策略

- 每步最多 3 次重试
- 指数退避：`delay = base_delay * 2^retry_count`
- 最大延迟：60 秒

---

## 10. 文件结构

```
scripts/
├── ssh_deploy.py           # SSH 部署核心脚本
├── join_cluster.sh        # Ray Worker 加入脚本
└── worker_deploy.sh       # 完整部署脚本

src/algo_studio/
├── core/
│   └── ssh_manager.py      # SSHConnectionManager + SSHConnectionPool
├── api/routes/
│   └── deploy.py           # 部署 API 端点
└── services/
    └── deploy_service.py   # 部署服务

docs/superpowers/design/
└── ssh-deployment-design.md  # 本文档
```
