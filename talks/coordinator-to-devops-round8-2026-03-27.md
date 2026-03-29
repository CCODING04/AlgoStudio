# Round 8 任务分配: 部署状态监控 REST API

**from:** @coordinator
**to:** @devops-engineer
**date:** 2026-03-27
**type:** task
**priority:** P0
**迭代:** Round 8

---

## 任务背景

Phase 2.3 Round 8 迭代开始。目标: 实现部署状态监控的 REST API 层。

## 任务内容

实现以下 API 端点 (`src/algo_studio/api/routes/deploy.py`):

### 1. GET /api/deploy/workers
获取所有部署记录列表

### 2. GET /api/deploy/worker/{task_id}
获取特定部署的详细信息

### 3. POST /api/deploy/worker
触发新的部署任务

## 实现要求

1. **复用现有逻辑**: 直接调用 `scripts/ssh_deploy.py` 中的 `DeployProgressStore`
2. **API 响应模型**: 创建 Pydantic models (DeployWorkerResponse, DeployProgressResponse)
3. **错误处理**: 404 for not found, 400 for invalid requests
4. **命令白名单**: 复用已有的 validate_command() 逻辑

## 参考文档

- `docs/superpowers/design/ssh-deployment-design.md` (如存在)
- `scripts/ssh_deploy.py` - DeployProgressStore, SSHDeployer
- `src/algo_studio/api/routes/tasks.py` - SSE 实现参考

## 输出

- `src/algo_studio/api/routes/deploy.py`
- 单元测试 (如需要)
- API 文档注释

## 评审

Round 8 评审将在开发完成后进行，由 @architect-alpha, @architect-beta, @architect-gamma 评审。

## 截止日期

Week 5 初期 (2 天)

## 状态

- [ ] 任务已接收
- [ ] REST API 实现完成
- [ ] 单元测试完成
- [ ] 自检完成

---

完成后在 `talks/devops-to-coordinator-round8-2026-03-27.md` 报告