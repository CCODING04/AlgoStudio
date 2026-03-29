# Phase 3.5 R9 安全修复: Critical 问题

**From:** Coordinator
**Date:** 2026-03-29
**To:** @backend-engineer
**Topic:** R9 安全修复 - Critical 安全问题

---

## 问题来源

@architect-beta 评审发现以下 Critical 安全问题:

### Critical 问题

| # | 问题 | 严重性 |
|---|------|--------|
| 1 | Dataset API 缺少 RBAC `require_permission()` 装饰器 | Critical |
| 2 | `list_datasets` 暴露所有数据集，无访问过滤 | Critical |
| 3 | 加密密钥重启后丢失 - 生成的密钥是临时的 | Critical |
| 4 | Redis 连接无密码认证支持 | Critical |
| 5 | SQL 通配符注入风险 (`%`, `_` 未转义) | Important |

### 参考

评审报告: `talks/architect-beta-to-coordinator-2026-03-29-001.md`

---

## 修复任务

### Task 1: Dataset API RBAC

**修复**:
1. 为 dataset endpoints 添加 `require_permission(Permission.DATASET_READ)`
2. 确保所有端点使用装饰器而非手动检查

### Task 2: list_datasets 访问过滤

**修复**:
1. 只返回用户有权限访问的数据集
2. 公开数据集对所有人可见
3. 私有数据集只对 owner 可见

### Task 3: 加密密钥持久化

**修复**:
1. 验证加密密钥存在，不存在则 fail fast
2. 提供环境变量或配置文件方式存储密钥
3. 不能每次重启生成新密钥

### Task 4: Redis 密码认证

**修复**:
1. CredentialStore 支持 Redis 密码认证
2. 从环境变量读取 Redis 密码

### Task 5: SQL 通配符转义

**修复**:
1. 在搜索过滤中转义 `%` 和 `_`

---

## 交付要求

1. 修复上述所有问题
2. 提交代码到 master
3. 回复到 `talks/backend-engineer-to-coordinator-2026-03-29-007.md`
4. 更新 schedule.md

---

**截止**: 立即执行