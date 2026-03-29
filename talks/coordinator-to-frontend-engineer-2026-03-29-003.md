# Phase 3.5 R1 任务派发: DeployWizard P0 Bug 修复

**From:** Coordinator
**Date:** 2026-03-29
**To:** @frontend-engineer
**Topic:** R1 Sprint 1 P0 Bug 修复任务

---

## 任务背景

Phase 3.5 第 1 轮迭代 (R1)，Sprint 1 阶段。

### 问题分析 (来自 @devops-engineer)

| 问题 | 严重度 | 说明 |
|------|--------|------|
| 算法版本硬编码 | **P0** | DeployWizard 里的版本是 v1/v2，未对接 API |
| 部署进度是假数据 | **P0** | setInterval 模拟，与实际状态无关 |
| SSH 密码无法配置 | **P0** | NEXT_PUBLIC_DEPLOY_SSH_PASSWORD 为空 |

---

## 任务清单

### Task 1: DeployWizard 版本动态化

**问题**: `src/frontend/src/components/deploy/DeployWizard.tsx` 中算法版本是硬编码的 v1/v2

**要求**:
1. 从 `/api/algorithms` 获取可用算法列表
2. 算法版本从 API 响应获取，而非硬编码
3. 用户选择算法后，版本下拉框应显示该算法的所有版本

**参考文件**:
- `src/frontend/src/components/deploy/DeployWizard.tsx`
- `src/frontend/src/app/api/proxy/algorithms/route.ts` (如存在)

**完成标准**: DeployWizard Step 1 的算法和版本选择器显示真实 API 数据

---

### Task 2: DeployProgress SSE 进度连接

**问题**: `src/frontend/src/components/deploy/DeployProgress.tsx` 使用 setInterval 模拟进度

**要求**:
1. 连接 SSE 端点 `/api/deploy/worker/{task_id}/progress`
2. 显示真实部署步骤和日志
3. 移除 setInterval 模拟代码

**参考文件**:
- `src/frontend/src/components/deploy/DeployProgress.tsx`
- `src/algo_studio/api/routes/deploy.py` (SSE 端点实现)

**完成标准**: DeployProgress 显示真实 SSE 推送的进度

---

### Task 3: CredentialModal 组件集成

**要求**:
1. 部署前弹出模态框让用户输入 SSH 凭据
2. 通过 API `/api/deploy/credential` 存储凭据
3. 获取 `credential_id` 用于后续部署

**参考文件**:
- `src/frontend/src/app/(main)/deploy/page.tsx:39`

**完成标准**: 首次部署时弹出凭据输入框，凭据通过 API 存储

---

## 交付要求

1. 完成上述任务，代码提交到 master
2. 回复到 `talks/frontend-engineer-to-coordinator-2026-03-29-003.md`
3. 更新 `docs/superpowers/schedule/schedule.md` 任务状态

---

**截止**: 2026-03-29 下午