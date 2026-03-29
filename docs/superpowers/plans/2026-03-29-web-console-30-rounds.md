# Phase 3.6: Web Console 迭代优化 - 30 轮计划

> **目标:** 通过 30 轮迭代，将 Web Console 测试覆盖率达到 99%，解决所有已知问题，实现项目 100% 完成度

**版本:** v1.0
**日期:** 2026-03-29
**状态:** 执行中

---

## 1. 当前状态分析

### 1.1 测试覆盖现状

| 类型 | 通过 | 失败 | 覆盖率 |
|------|------|------|--------|
| Unit Tests | 1024 | 51 | 70% |
| E2E Web | 已知问题 | - | 待评估 |

### 1.2 失败测试分析

| 模块 | 失败数 | 主要问题 |
|------|--------|----------|
| Dataset API | 26 | RBAC 认证、fixture 问题 |
| RBAC | 14 | timestamp/signature 验证 |
| Tasks API | 9 | 认证头缺失 |
| Hosts | 1 | keep_alive 逻辑 |
| Rollback | 1 | SnapshotMixin |

### 1.3 Web Console 问题

| 优先级 | 问题 | 状态 |
|--------|------|------|
| HIGH | Task Creation Wizard 不打开 | ✅ 已修复 |
| MEDIUM | Dashboard 资源图表不显示 | ✅ 已修复 |
| LOW | 404 资源错误 | 待验证 |
| HIGH | Dataset CRUD 操作问题 | 待修复 |
| MEDIUM | Hosts 显示 idle vs online | ✅ 已修复 |

---

## 2. 迭代目标

### 2.1 覆盖率目标

| 阶段 | 目标覆盖率 | 轮次 |
|------|------------|------|
| Phase 1 | 75% → 85% | R1-R10 |
| Phase 2 | 85% → 92% | R11-R20 |
| Phase 3 | 92% → 99% | R21-R30 |

### 2.2 测试类型目标

| 类型 | 当前 | 目标 |
|------|------|------|
| Unit Tests | 1024 | 1500+ |
| E2E Web | 基础 | 完整覆盖 |
| Integration | 部分 | 完整 |

---

## 3. 30 轮迭代计划

### Round 1-5: 修复失败测试

| Round | 任务 | 负责人 | 测试目标 |
|-------|------|--------|----------|
| R1 | 修复 Dataset API 测试 | @test-engineer | 26 测试修复 |
| R2 | 修复 RBAC 测试 | @test-engineer | 14 测试修复 |
| R3 | 修复 Tasks API 测试 | @test-engineer | 9 测试修复 |
| R4 | 修复 Hosts/Rollback 测试 | @test-engineer | 2 测试修复 |
| R5 | 验证所有修复 + 覆盖率检查 | @qa-engineer | 覆盖率 75% |

### Round 6-10: Web Console 功能完善

| Round | 任务 | 负责人 | 功能目标 |
|-------|------|--------|----------|
| R6 | Dataset 页面功能修复 | @frontend-engineer | CRUD 完整 |
| R7 | Task Creation Wizard 验证 | @frontend-engineer | 完整流程 |
| R8 | Deploy Wizard 完善 | @frontend-engineer | 端到端 |
| R9 | Hosts 页面完善 | @frontend-engineer | 详情页 |
| R10 | Dashboard 图表完善 | @frontend-engineer | 实时数据 |

### Round 11-15: E2E 测试扩展

| Round | 任务 | 负责人 | 覆盖目标 |
|-------|------|--------|----------|
| R11 | Dataset E2E 测试 | @qa-engineer | 完整 CRUD |
| R12 | Task E2E 测试 | @qa-engineer | 创建/分配/监控 |
| R13 | Deploy E2E 测试 | @qa-engineer | 完整流程 |
| R14 | Hosts E2E 测试 | @qa-engineer | 监控/详情 |
| R15 | Dashboard E2E 测试 | @qa-engineer | 图表/统计 |

### Round 16-20: 覆盖率提升 Phase 1

| Round | 任务 | 负责人 | 覆盖率目标 |
|-------|------|--------|------------|
| R16 | 核心模块覆盖率提升 | @test-engineer | 80% |
| R17 | API 路由覆盖率提升 | @test-engineer | 82% |
| R18 | Scheduler 覆盖率提升 | @test-engineer | 85% |
| R19 | Core 覆盖率提升 | @test-engineer | 87% |
| R20 | 中间件覆盖率提升 | @test-engineer | 90% |

### Round 21-25: 覆盖率提升 Phase 2

| Round | 任务 | 负责人 | 覆盖率目标 |
|-------|------|--------|------------|
| R21 | Auth/RBAC 覆盖率 | @test-engineer | 92% |
| R22 | Deploy/Rollback 覆盖率 | @test-engineer | 93% |
| R23 | Quota/Snapshot 覆盖率 | @test-engineer | 95% |
| R24 | Monitor 覆盖率 | @test-engineer | 97% |
| R25 | 剩余模块覆盖率 | @test-engineer | 98% |

### Round 26-30: 最终优化

| Round | 任务 | 负责人 | 目标 |
|-------|------|--------|------|
| R26 | 测试优化/性能 | @performance-engineer | 测试 < 60s |
| R27 | 边界情况覆盖 | @test-engineer | 99% |
| R28 | 最终审查/修复 | @architect-beta | 安全评审 |
| R29 | 用户验收测试 | @qa-engineer | UAT 通过 |
| R30 | 最终评审/交付 | @coordinator | 100% 完成 |

---

## 4. 评审团队

| 角色 | Subagent | 职责 |
|------|----------|------|
| @coordinator | 协调员 | 任务分配、进度跟踪 |
| @test-engineer | 测试工程师 | 单元测试、覆盖率 |
| @qa-engineer-v2 | QA 工程师 | E2E 测试、质量评审 |
| @frontend-engineer | 前端工程师 | Web Console 修复 |
| @backend-engineer | 后端工程师 | API 修复支持 |
| @architect-alpha | 首席架构师 | 架构评审 |
| @architect-beta | 平台架构师 | API/安全评审 |

---

## 5. 执行流程

### 每个 Round 的标准流程

```
1. Coordinator 分配任务
2. 负责人执行开发和测试
3. 运行测试套件验证
4. 提交评审报告
5. Coordinator 汇总并发布下一轮任务
```

### 每日 Standup

- 08:00 AM: 检查进度
- 如有阻塞，立即协调解决

---

## 6. 质量标准

### 通过标准 (每 Round)

| 标准 | 要求 |
|------|------|
| Critical Issues | 0 |
| High Issues | 已修复或跟踪 |
| 测试通过率 | ≥ 95% |
| 覆盖率 | 按阶段目标 |

### 最终交付标准

| 标准 | 要求 |
|------|------|
| 测试覆盖率 | ≥ 99% |
| 测试通过率 | ≥ 99% |
| Critical Issues | 0 |
| High Issues | 0 |
| E2E 测试 | 全部通过 |

---

## 7. 当前 Round 状态

### Phase 3.6 Round 进度

| Round | 状态 | 主要任务 | 成果 |
|-------|------|----------|------|
| R1 | 🔄 进行中 | 修复 Dataset API 测试 | 待完成 |
| R2-R30 | ⏳ 待开始 | - | - |

---

## 8. 修复指令 (Round 1)

### 任务分配

| ID | 问题 | 负责人 | 优先级 |
|----|------|--------|--------|
| F1 | Dataset API 26 测试失败 | @test-engineer | P0 |
| F2 | RBAC 14 测试失败 | @test-engineer | P0 |
| F3 | Tasks API 9 测试失败 | @test-engineer | P0 |
| F4 | Hosts/Rollback 2 测试失败 | @test-engineer | P1 |

### 修复指南

**Dataset API 测试问题:**
- 检查 `test_datasets.py` 中的 fixture `auth_headers`
- 确认 RBAC 签名生成逻辑
- 验证 API 路由注册

**RBAC 测试问题:**
- timestamp 过期时间检查
- signature 生成算法验证
- secret key 配置

**Tasks API 测试问题:**
- auth_headers fixture 缺失
- signature 计算错误
- 缺少 X-Timestamp header

---

**文档状态:** 执行中
**下次更新:** Round 1 完成后
