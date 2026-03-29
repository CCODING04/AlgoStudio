# Phase 2.3 反馈

## 部署状态监控

### 任务分解

Phase 2.3 "部署状态监控" 需要构建以下组件：

**1. 后端 API 路由 (`src/algo_studio/api/routes/deploy.py`)**

根据 `docs/superpowers/design/ssh-deployment-design.md` 中的 API 设计，需要实现：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/deploy/worker` | 发起部署任务 |
| GET | `/api/deploy/worker/{task_id}` | 获取部署状态 |
| GET | `/api/deploy/worker/{task_id}/progress` | SSE 进度流 |
| DELETE | `/api/deploy/worker/{task_id}` | 取消部署 |
| GET | `/api/deploy/workers` | 列出所有部署记录 |

**2. API 响应模型**

将 `scripts/ssh_deploy.py` 中的 `DeployWorkerRequest` 和 `DeployProgress` 模型迁移到 API 层（Pydantic models）。

**3. SSE 实时推送集成**

`DeployProgressStore` 已使用 Redis 存储进度，但缺少 SSE 推送机制。需要：
- 使用 Redis pub/sub 或定时轮询触发 SSE 事件
- 或者利用现有的 `ProgressReporter` 模式

**4. 前端集成**

`src/frontend/src/app/(main)/deploy/page.tsx` 目前是占位页面，需要 `@frontend-engineer` 开发完整 UI。

---

### 实现建议

**顺序建议：**

1. **先实现 REST API** (`GET /deploy/worker/{task_id}`, `GET /deploy/workers`)
   - 不涉及 SSE，依赖最少，可独立测试
   - 直接调用 `DeployProgressStore` 查询 Redis

2. **再实现 SSE 进度流** (`GET /deploy/worker/{task_id}/progress`)
   - 需要 Redis pub/sub 或后台任务通知机制
   - 可参考 `src/algo_studio/api/routes/tasks.py` 中的 SSE 实现模式

3. **最后实现部署触发** (`POST /deploy/worker`)
   - 需要集成 `SSHDeployer`
   - 确保命令验证和错误处理完善

**代码复用建议：**

- `scripts/ssh_deploy.py` 中的 `DeployProgressStore`、`DeployWorkerRequest`、`DeployStatus` 可迁移到 `src/algo_studio/core/deploy_store.py`
- `SSHDeployer` 可保持独立，通过 API 调用触发

---

### 依赖关系

| 依赖 | 说明 |
|------|------|
| Redis (localhost:6380) | `DeployProgressStore` 已使用，必须可用 |
| SSHDeployer | 核心部署逻辑已在 `scripts/ssh_deploy.py` 实现 |
| `@frontend-engineer` | 需要 `Hosts/Deploy` 页面开发（Phase 2.3 任务） |

**关键依赖：**
- Phase 2.3 的 `@frontend-engineer` 任务是 "Hosts/Deploy 页面"，与本任务耦合
- 前端 SSE 订阅需要后端先提供 `/api/deploy/worker/{task_id}/progress` 端点

---

### 甘特图调整建议

当前 Phase 2.3 在 Week 5-6，与 `@frontend-engineer` 的 "Hosts/Deploy 页面" 并行。

**建议：**
- 将后端 API 路由开发（`deploy.py`）安排在 Week 5 上半周
- 将 SSE 集成安排在 Week 5 下半周
- 前端页面可从 Week 5 下半周开始对接后端 API

---

### 其他

**已完成的基础工作：**

`scripts/ssh_deploy.py` 已实现：
- `DeployProgressStore` (Redis 持久化)
- `DeployStatus` 状态机 (PENDING/CONNECTING/DEPLOYING/VERIFYING/COMPLETED/FAILED/CANCELLED)
- `IdempotencyChecker` (幂等性检查)
- `RollbackManager` (回滚机制)
- 命令白名单验证

**潜在问题：**

1. **Redis 端口一致性**：注意 MEMORY.md 中提到 Redis 端口改为 6380，`ssh_deploy.py` 中已使用 6380，需确认其他服务一致

2. **Actor 序列化**：`SSHDeployer.deploy_worker()` 使用 `asyncio.create_task()` 后台执行，需确保 Redis 连接在异步上下文中正确传递

3. **SSH Key 认证**：`ssh_deploy.py` 已实现 key 认证降级（无 key 时使用密码），但设计文档中 MITM 防护依赖 host_key_verify=True，需确保 known_hosts 正确管理
