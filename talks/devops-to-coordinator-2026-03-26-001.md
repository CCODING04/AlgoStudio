# 任务完成报告：SSH 部署框架设计

**from:** @devops-engineer
**to:** @coordinator
**date:** 2026-03-26
**type:** notify
**ref:** coordinator-to-devops-2026-03-26-001.md

---

## 任务状态

Phase 2 Round 1 - SSH 自动化部署系统架构设计 **已完成**

## 交付物

### 1. SSH 部署架构设计文档

**位置**: `docs/superpowers/design/ssh-deployment-design.md`

**内容**:
- 系统架构图（Web Console -> FastAPI -> SSH -> Worker Node）
- SSHConnectionPool 设计（多连接复用、全局限制）
- 连接状态机（6 个状态：DISCONNECTED, CONNECTING, IDLE, COMMAND_RUNNING, RETRYING, ERROR）
- 部署状态机（7 步部署：connecting, sudo_config, create_venv, install_deps, sync_code, start_ray, verify）
- 幂等性设计（标记文件检查）
- 回滚机制（四层回滚策略）
- 安全设计（密码处理、命令白名单、黑名单）
- API 设计（5 个端点）
- 并发控制（节点级锁 + 全局限流）

### 2. `scripts/ssh_deploy.py` 初版代码框架

**位置**: `/home/admin02/Code/Dev/AlgoStudio/scripts/ssh_deploy.py`

**核心组件**:
- `SSHDeployConfig` - 部署配置（连接超时、重试次数、并发数）
- `ConnectionState` / `DeployStatus` - 状态枚举
- `DeployProgress` / `DeployWorkerRequest` - 数据模型
- `SSHConnectionManager` - 连接状态机 + 自动重连
- `SSHConnectionPool` - 连接池管理
- `IdempotencyChecker` - 幂等性检查
- `RollbackManager` - 回滚管理
- `DeployProgressStore` - 进度存储
- `SSHDeployer` - 部署执行器（7 步）
- `validate_command()` - 命令白名单验证

**行数**: ~750 行

### 3. 部署状态机定义

已在 `ssh_deploy.py` 中定义：

```python
class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    IDLE = "idle"
    COMMAND_RUNNING = "command_running"
    RETRYING = "retrying"
    ERROR = "error"

class DeployStatus(Enum):
    PENDING = "pending"
    CONNECTING = "connecting"
    DEPLOYING = "deploying"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

## 技术决策

1. **SSH 库选择**: asyncssh（原生异步，FastAPI/SSE 友好）
2. **连接池**: 每主机 2 连接，全局最多 10 连接
3. **重试策略**: 指数退避，最多 3 次重试
4. **并发控制**: 节点级锁 + 全局信号量（最多 5 个并发部署）
5. **安全**: 命令白名单验证 + 黑名单过滤

## 下一步建议

1. **依赖安装**: 确保 Head 节点安装 asyncssh (`uv pip install asyncssh`)
2. **API 集成**: 将 SSHDeployer 集成到 FastAPI 路由
3. **SSE 推送**: 对接现有的 SSE 端点 (`/api/cluster/events`)
4. **实测验证**: 在 192.168.0.115 节点进行实际部署测试

## 风险点

- asyncssh 需要 libssh2 依赖（需确认系统已安装）
- PTY sudo 问题（已实现四层回滚策略）

## 状态

- [x] 架构设计完成
- [x] 代码框架完成
- [x] 自检通过

---
**@coordinator** 任务已完成，等待下一步指示。
