# Phase 3.5 R1 任务派发: Redis 凭据管理 API

**From:** Coordinator
**Date:** 2026-03-29
**To:** @devops-engineer
**Topic:** R1 Sprint 1 P0 Bug 修复任务

---

## 任务背景

Phase 3.5 第 1 轮迭代 (R1)，Sprint 1 阶段。

### 问题分析 (来自 @devops-engineer)

| 问题 | 严重度 | 说明 |
|------|--------|------|
| SSH 密码无法配置 | **P0** | NEXT_PUBLIC_DEPLOY_SSH_PASSWORD 为空，前端无法安全存储 SSH 密码 |
| 部署进度是假数据 | **P0** | setInterval 模拟，与实际状态无关 |

---

## 任务清单

### Task 1: Redis 凭据管理 API

**要求**:
1. 实现 `/api/deploy/credential` POST 端点 - 存储加密凭据到 Redis
2. 实现 `/api/deploy/credentials` GET 端点 - 列出用户凭据
3. 实现 `/api/deploy/credential/{id}` DELETE 端点 - 删除凭据
4. 凭据加密存储，返回 credential_id
5. 凭据与用户关联（多用户多凭据）

**参考**:
- `src/algo_studio/api/routes/deploy.py`
- Redis 已运行在 6380 端口

**API 设计**:
```python
# Store credential
POST /api/deploy/credential
Body: {"name": "my-ssh-key", "username": "admin", "password": "xxx", "type": "password"}
Response: {"credential_id": "cred_xxx"}

# List credentials
GET /api/deploy/credentials
Response: [{"id": "cred_xxx", "name": "my-ssh-key", "username": "admin", "type": "password", "created_at": "..."}]

# Delete credential
DELETE /api/deploy/credential/{id}
Response: {"success": true}
```

**完成标准**: 凭据 API 可用，前端可存储和获取凭据

---

### Task 2: 预部署节点验证 API (可选)

**要求**:
1. 实现 `/api/deploy/nodes/validate/{node_ip}` GET 端点
2. 验证: Ping + SSH 连接
3. 返回: `{ valid: bool, error?: string, gpu_info?: dict }`

**完成标准**: 部署前可验证节点可用性

---

## 交付要求

1. 完成上述任务，代码提交到 master
2. 回复到 `talks/devops-engineer-to-coordinator-2026-03-29-003.md`
3. 更新 `docs/superpowers/schedule/schedule.md` 任务状态

---

**截止**: 2026-03-29 下午