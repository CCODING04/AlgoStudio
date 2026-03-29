# DevOps Engineer 回复: Phase 3.5 Dashboard 部署功能

**日期**: 2026-03-29
**收件人**: @coordinator
**主题**: Dashboard 部署功能技术分析和方案

---

## 1. 当前部署问题分析

### 问题 1: SSH 密码无法配置 (Critical)

**位置**: `src/frontend/src/app/(main)/deploy/page.tsx:39`

```typescript
const sshPassword = process.env.NEXT_PUBLIC_DEPLOY_SSH_PASSWORD || '';
```

- 密码默认为空字符串，部署必然失败
- 前端无法安全存储 SSH 密码（不能使用 NEXT_PUBLIC_ 前缀）
- 需要后端 API 或 secret storage 来管理凭据

### 问题 2: 部署进度是假数据 (Critical)

**位置**: `src/frontend/src/components/deploy/DeployProgress.tsx:34-64`

```typescript
// Simulate deployment progress for now (would use SSE in production)
useEffect(() => {
  const steps = [
    { progress: 10, step: '正在连接主机...', message: `正在连接到 ${hostId}` },
    // ... fake progress via setInterval
  };
```

- 使用 `setInterval` 模拟进度，与实际部署无关
- 部署实际状态由 SSE 端点 `/api/deploy/worker/{task_id}/progress` 提供，但前端未连接
- 用户看到"部署成功"但实际部署可能失败

### 问题 3: 部署向导只是 UI 壳

**位置**: `src/frontend/src/components/deploy/DeployWizard.tsx`

- 算法选择后调用 `onDeploy(hostId, algorithmName, algorithmVersion)`
- 但 `page.tsx` 的 `handleDeploy` 只传了 `node_ip`, `username`, `password`, `head_ip`, `ray_port`
- `algorithmName` 和 `algorithmVersion` 被忽略 - 没有实际同步算法文件
- 配置选项（GPU 内存限制、自动重启）存储在 state 但从未使用

### 问题 4: 缺少预部署验证

- 没有验证主机是否可 SSH 连接
- 没有验证 SSH 凭据是否正确
- 可能向离线节点发起部署

---

## 2. Dashboard 部署方案

### 方案架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Web Console (Frontend)                   │
├─────────────────────────────────────────────────────────────┤
│  DeployWizard      │  DeployProgress (SSE)  │  CredentialModal │
│  - Algorithm       │  - Real progress       │  - SSH password  │
│  - Host selection  │  - Step updates        │  - SSH key opt   │
│  - Config options  │  - Log streaming       │                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      API Server (Backend)                    │
├─────────────────────────────────────────────────────────────┤
│  POST /api/deploy/worker      - Trigger deployment           │
│  GET  /api/deploy/worker/{id} - Get status (polling)         │
│  GET  /api/deploy/worker/{id}/progress - SSE stream           │
│  POST /api/deploy/credential  - Store SSH credential         │
│  GET  /api/deploy/nodes/available - Validated available nodes │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    SSH Deployer (Core)                      │
├─────────────────────────────────────────────────────────────┤
│  scripts/ssh_deploy.py                                       │
│  - SSH connection + sudo setup                               │
│  - uv environment creation                                   │
│  - Dependency installation (torch, algo_studio)               │
│  - Code synchronization (rsync-like)                         │
│  - Ray worker startup                                        │
│  - Deployment verification                                   │
└─────────────────────────────────────────────────────────────┘
```

### 关键改进

#### 2.1 凭据管理

**问题**: 前端不能存储 SSH 密码

**解决方案**:
1. 新增 `/api/deploy/credential` 端点（POST）存储加密凭据到 Redis
2. 凭据与用户关联，支持多用户多凭据
3. 部署时前端传入 `credential_id` 而非明文密码
4. 首次部署时弹出模态框让用户输入密码（通过 API 存储）

```python
# 新端点
@router.post("/credential")
async def store_credential(request: StoreCredentialRequest):
    """Store SSH credential encrypted in Redis"""
    # 加密存储，返回 credential_id
```

#### 2.2 实时进度 SSE 连接

**当前**: `DeployProgress.tsx` 使用 setInterval 模拟

**修复**: 实际连接 SSE 端点

```typescript
// useDeploySSE hook
const { data: progress, status } = useEventSource(
  `/api/deploy/worker/${taskId}/progress`,
  { eventSourceInit: { withCredentials: true } }
);
```

#### 2.3 预部署验证

部署前增加验证步骤：

```python
# 新端点
@router.get("/nodes/validate/{node_ip}")
async def validate_node(node_ip: str, credential_id: str):
    """Validate node is reachable and credentials work"""
    # 1. Ping check (network reachability)
    # 2. SSH connection test with credentials
    # 3. Ray not already running on that node
    # Return: { valid: bool, error?: string, gpu_info?: dict }
```

#### 2.4 算法同步（可选扩展）

当前部署只启动 Ray Worker，不同步算法代码。如果需要预装算法：

1. 算法已存在于共享存储（如 JuiceFS），部署时指定路径
2. 或部署时 rsync 算法目录到节点

---

## 3. 关键步骤设计

### Phase A: 基础修复（让部署可用）

| Step | 任务 | 组件 | 预计工时 |
|------|------|------|----------|
| A1 | 实现凭据管理 API + Redis 存储 | Backend | 2h |
| A2 | 前端 CredentialModal 组件 | Frontend | 2h |
| A3 | 连接 SSE 端点获取真实进度 | Frontend | 1h |
| A4 | 预部署节点验证端点 | Backend | 1h |

### Phase B: 体验优化

| Step | 任务 | 组件 | 预计工时 |
|------|------|------|----------|
| B1 | 部署向导集成验证 | Frontend | 1h |
| B2 | 部署日志实时显示 | Frontend | 2h |
| B3 | 失败自动重试机制 | Backend | 1h |

---

## 4. 疑问和不同观点

### Q1: 部署的到底是什么？

当前实现 (`ssh_deploy.py`) 部署的是 **Ray Worker 节点**，不是算法。

**两种理解**:
1. **部署 Worker 节点**: 让 Worker 加入 Ray 集群（当前实现）
2. **部署算法到 Worker**: 在已加入集群的 Worker 上安装特定算法

规划文档说"快速选择算法和目标节点"，暗示是后者。但当前 `ssh_deploy.py` 不支持算法同步。

**建议**: 明确 Phase 3.5 的"部署算法"是指什么。如果是算法同步，需要扩展 `ssh_deploy.py`。

### Q2: SSH 密码 vs SSH Key

当前 `ssh_deploy.py` 使用密码认证：

```python
# scripts/ssh_deploy.py
async with asyncssh.connect(
    host=node_ip,
    username=username,
    password=password,  # 密码认证
    ...
)
```

生产环境建议用 SSH Key 认证，更安全且自动化更方便。

**建议**: Phase 3.5 增加 SSH Key 支持作为选项。

### Q3: 离线节点处理

Hosts 页面显示节点 `status: online/offline`。但 DeployWizard 的下拉框不过滤离线节点，可能选择离线节点然后部署失败。

**建议**: DeployWizard Step 2 只显示 `status === 'online'` 的节点（已有），但如果用户主动输入 IP，应该有验证。

---

## 5. 优先级建议

基于问题严重性，我建议 Phase 3.5 按以下顺序实施：

1. **P0 (Critical)**: SSE 真实进度连接 - 当前用户看到假进度
2. **P0 (Critical)**: 凭据管理 - 当前部署无法输入密码
3. **P1**: 预部署验证 - 避免部署到不可用节点
4. **P2**: 日志实时显示、失败重试等体验优化

---

## 6. 依赖关系

- 凭据管理 API 需要 Redis 连接（已有）
- SSE 进度端点已实现 (`/api/deploy/worker/{task_id}/progress`)，前端只需连接
- 节点验证需要能执行 ping/ssh test

---

**回复人**: @devops-engineer
**日期**: 2026-03-29
