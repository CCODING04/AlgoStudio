# AGENTS.md — AlgoStudio

## 0. 项目概览

AlgoStudio 是 AI 算法训练平台，支持多机 GPU 调度、算法版本管理和任务追踪。
核心能力：Ray 集群调度 / 任务管理 / 主机监控 / RBAC 权限。
技术栈：Python / FastAPI / Ray / Redis / JuiceFS

---

## 1. 当前状态

**当前阶段**：Phase 2.3 - Round 8 完成
**已完成**：Round 1-8 全部通过专家评审
**当前阶段**：Phase 2.4 Round 6 进行中
**已完成**：Phase 2.3 Round 1-8 完成，Phase 2.4 Round 1-5 完成
**下一步**：Phase 2.4 Round 6 - Web Console 4个问题修复 + 评审

**已知问题** (pending-decisions.md)：
- A1: ProgressReporter Actor 在成功路径未清理 (Medium) - ✅ 已修复
- A2: hosts.py API 缺少单元测试 (Medium) - 待 Phase 2.4

---

## 2. 项目结构

```
src/algo_studio/
├── api/routes/       # FastAPI 路由 (tasks.py, hosts.py, deploy.py)
├── core/             # 核心逻辑 (task.py, ray_client.py, quota/)
├── monitor/          # 主机监控 (host_monitor.py, node_monitor.py)
├── web/              # Web UI (pages/, client.py)
└── cli/              # 命令行工具
tests/
├── unit/            # 单元测试
├── integration/     # 集成测试
├── e2e/             # 端到端测试
└── performance/     # 性能测试
docs/superpowers/
├── schedule/        # 进度跟踪 (iteration-review-mechanism.md)
├── backlog/          # 待决策问题 (pending-decisions.md)
├── team/            # 团队架构 (TEAM_STRUCTURE.md)
└── research/        # 研究报告
talks/               # Agent 间沟通记录
```

---

## 3. 开发协议

### 开始工作前 (必做)
1. 读 `docs/superpowers/schedule/iteration-review-mechanism.md` 确认当前 Round
2. 读 `docs/superpowers/backlog/pending-decisions.md` 确认阻塞问题
3. 在 `talks/` 创建进度更新文件

### 代码规则
4. 所有新模块必须有测试文件 `tests/test_<module>.py`
5. 函数必须有 docstring，公共 API 必须有类型注解
6. 使用 `uv` 隔离环境，不直接 `pip install`
7. 不修改已有接口签名，需先记录变更原因

### 文档更新 (必做)
8. 完成任务后更新 `iteration-review-mechanism.md` 任务状态
9. 技术决策记录到 `pending-decisions.md`
10. 接口变更更新到对应 spec 文档

### 提交前
11. 运行 `PYTHONPATH=src pytest tests/` 确保测试通过
12. 提交格式：`type: 简短描述` (如 `feat: 添加节点评分算法`)

### Phase 迭代不停止原则
13. **Round 连续执行**: 评审结束后由 Coordinator 直接分派修复任务，不等待用户确认
14. **不停止直到**: 达到指定 Round 次数(Round 5) 或评审无修改意见
15. **错误不过夜**: 评审发现的问题必须立即修复，不累积

---

## 4. 接口约定

### 算法接口 (Duck Typing)
```
algorithms/<name>/<version>/
├── train(data_path, config, progress_callback) -> TrainResult
├── infer(inputs) -> InferenceResult
├── verify(test_data) -> VerificationResult
└── get_metadata() -> AlgorithmMetadata
```
**关键**: pynvml 必须在方法内部 import，避免 Ray Actor 反序列化问题

### API 路由规范
- 前缀：`/api/hosts/`, `/api/tasks/`, `/api/deploy/`
- 认证：HMAC-SHA256 签名 (Header: X-User-ID, X-Role, X-Signature)
- 公开路由：`/health`, `/api/hosts`, `/api/hosts/status`, `/api/cluster`

### 模块边界
- `core/` 不依赖 `api/` 和 `monitor/`
- `api/` 可调用 `core/`，不能反过来
- `monitor/` 独立模块，不依赖其他

---

## 5. 常用命令

```bash
# 环境
uv venv algo-studio-env && source algo-studio-env/bin/activate
uv pip install -e .

# Ray 集群
ray stop && ~/Code/Dev/AlgoStudio/.venv/bin/ray start --head --port=6379 --object-store-memory=5368709120

# API 服务
PYTHONPATH=src .venv/bin/uvicorn algo_studio.api.main:app --host 0.0.0.0 --port 8000

# 测试
PYTHONPATH=src pytest tests/test_scheduler/test_fair_scheduler.py -v

# 单个测试
PYTHONPATH=src pytest tests/test_ray_client.py -v
```

---

## 6. 参考文档

| 文档 | 用途 | 何时读 |
|------|------|--------|
| `docs/superpowers/schedule/iteration-review-mechanism.md` | 当前 Round 和进度 | 每次开始前 |
| `docs/superpowers/backlog/pending-decisions.md` | 待决策问题 | 需要做决策时 |
| `docs/superpowers/team/TEAM_STRUCTURE.md` | 角色职责边界 | 理解分工时 |
| `docs/superpowers/research/*.md` | 技术研究报告 | 实施相关功能前 |
| `CLAUDE.md` | 项目环境配置 | 首次了解项目时 |

---

## 7. Agent 角色协议

被指定为某角色时，严格遵守职责边界：

| 角色 | 核心职责 | 不碰 |
|------|---------|------|
| @architect-alpha | 技术决策、进度协调 | 业务代码 |
| @architect-beta | API/安全评审 | 调度算法 |
| @architect-gamma | 调度/性能评审 | 基础设施 |
| @devops-engineer | Ray 集群、部署脚本 | 应用逻辑 |
| @backend-engineer | FastAPI 路由、RBAC | 调度算法 |
| @ai-scheduling-engineer | WFQScheduler、QuotaManager | 基础设施 |
| @frontend-engineer | Web UI、SSE | 业务逻辑 |
| @qa-engineer | E2E 测试、质量验证 | 功能代码 |
| @performance-engineer | 性能基准测试 | 功能代码 |

**规则**：不属于职责范围的代码，发现问题后记录到 `talks/` 而不是直接修改。

---

## 8. Agent 沟通协议

### 消息格式
`talks/from-To-日期-序号.md`

### 必需字段
```
# from: @角色
# to: @角色
# date: YYYY-MM-DD
# type: task | update | decision | notify
## 内容
[具体内容]
## 状态
Status: pending | accepted | done
```

### 问题挖掘流程 (复杂问题)
1. 问题定义 → 2. 团队并行搜索 → 3. 开会讨论 → 4. 投票决策 → 5. 实施跟踪

---

*最后更新：2026-03-27*
