# AlgoStudio Phase 2 实施计划甘特图

**项目：** AlgoStudio Phase 2 平台能力拓展
**总工期：** 10-12 周
**团队：** 8 人（@coordinator + 7 专家角色）
**最后更新：** 2026-03-27
**项目状态：** 🚀 Phase 2 Round 7 完成 (Tasks API 测试完整)

## Round 1-4 评审结果

| 评审类型 | Round 1 | Round 2 | Round 3 | Round 4-7 |
|----------|---------|---------|---------|---------|
| 架构评审 | 80.3 | 69.2 | P0修复 | 安全9/10, 架构9/10 |
| 测试质量 | 64 | 72 | - | 8/10 → PASS |
| 性能评审 | 84 | 93 | - | - |
| QA评审 | 80 | 68 | - | 7→8→PASS |
| **平均** | **77.1** | **75.6** | **P0完成** | **测试完整** |

详见: `docs/superpowers/schedule/round1-review.md`, `round2-review.md`

---

## Phase 2 目标

基于 Phase 1 研究成果，实施以下核心功能：
1. SSH 自动化部署系统
2. 任务进度实时追踪
3. 资源配额管理系统
4. Web Console 完整功能
5. 性能基准测试体系

---

## 甘特图

```
周次    │ W1 │ W2 │ W3 │ W4 │ W5 │ W6 │ W7 │ W8 │ W9 │ W10│ W11│ W12│
────────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
Phase 2.1│████│████│    │    │    │    │    │    │    │    │    │    │
Phase 2.2│    │    │████│████│    │    │    │    │    │    │    │    │
Phase 2.3│    │    │    │    │████│████│    │    │    │    │    │    │
Phase 2.4│    │    │    │    │    │    │████│████│    │    │    │    │
测试集成 │    │    │    │    │    │    │    │    │████│████│    │    │
迭代评审 │████│████│████│████│████│████│████│████│████│████│    │    │
```

---

## 里程碑详情

### Phase 2.1 (Week 1-2): 基础设施与框架

| 任务 | 负责人 | 状态 | 依赖 |
|------|--------|------|------|
| SSH 部署框架设计 | @devops-engineer | ✅ Round1完成 | - |
| 数据库迁移框架 | @backend-engineer | ✅ Round1完成 | - |
| 配额数据模型设计 | @ai-scheduling-engineer | ✅ Round1完成 | - |
| Next.js 项目初始化 | @frontend-engineer | ✅ Round1完成 | - |
| pytest 测试框架搭建 | @test-engineer | ✅ Round1完成 | - |
| 性能测试计划制定 | @performance-engineer | ✅ Round1完成 | - |

**Round 2 任务:** 安全修复、CI/CD配置、集成完善

### Phase 2.2 (Week 3-4): 核心功能开发

| 任务 | 负责人 | 状态 | 依赖 |
|------|--------|------|------|
| SSH Worker 部署实现 | @devops-engineer | ✅ Round1-4完成 | Phase 2.1 |
| 告警系统实现 | @backend-engineer | ✅ RBAC完成 | Phase 2.1 |
| 任务进度 API | @backend-engineer | ✅ Round4完成 | Phase 2.1 |
| QuotaManager 实现 | @ai-scheduling-engineer | ✅ Redis后端完成 | Phase 2.1 |
| Dashboard/Tasks 页面 | @frontend-engineer | ✅ Round2完成 | Phase 2.2 |
| 单元测试编写 | @test-engineer | ✅ Round1-4完成 | Phase 2.2 |
| RBAC/HMAC 安全测试 | @test-engineer | ✅ 25 tests完成 | Phase 2.2 |
| SSH 安全修复 | @devops-engineer | ✅ 已修复并提交 | Phase 2.2 |

### Phase 2.3 (Week 5-6): 高级功能

| 任务 | 负责人 | 状态 | 依赖 | 备注 |
|------|--------|------|------|------|
| 部署状态监控 | @devops-engineer | 待开始 | Phase 2.2 | REST API → SSE → 部署触发 |
| RBAC 权限系统 | @backend-engineer | 待开始 | Phase 2.2 | AuditLog 延至 Phase 2.4 |
| 公平调度算法 | @ai-scheduling-engineer | 待开始 | Phase 2.2 | VFT 公式需验证 |
| Hosts/Deploy 页面 | @frontend-engineer | 待开始 | Phase 2.2 | 需后端 API 确认 |
| E2E 测试编写 | @qa-engineer | 待开始 | Phase 2.2 | 新增 RBAC/Task E2E |
| API 性能基准 | @performance-engineer | 待开始 | Phase 2.2 | 并行测试模式 |

**Phase 2.3 已确认决策:**
- ✅ 任务删除: 软删除 (deleted_at 字段)
- ✅ AuditLog 保留期: 180 天
- ✅ xterm.js: 使用 `@xterm/xterm`
- ✅ Redis 端口: 6380

### Phase 2.4 (Week 7-8): 完善与优化

| 任务 | 负责人 | 状态 | 依赖 |
|------|--------|------|------|
| 回滚机制完善 | @devops-engineer | 待开始 | Phase 2.3 |
| 审计日志中间件 | @backend-engineer | 待开始 | Phase 2.3 |
| 调度性能优化 | @ai-scheduling-engineer | 待开始 | Phase 2.3 |
| Web Console 完善 (Next.js) | @frontend-engineer | 待开始 | Phase 2.3 |
| 验收测试执行 | @qa-engineer | 待开始 | Phase 2.3 |
| 完整性能基准 | @performance-engineer | 待开始 | Phase 2.3 |
| hosts.py API 单元测试 (A2) | @test-engineer | 待开始 | Phase 2.3 |

### 测试集成 (Week 9-10)

| 任务 | 负责人 | 状态 | 依赖 |
|------|--------|------|------|
| 三模块集成测试 | @qa-engineer | 待开始 | Phase 2.4 |
| 性能测试验证 | @performance-engineer | 待开始 | Phase 2.4 |
| E2E 测试验证 | @qa-engineer | 待开始 | Phase 2.4 |
| 最终评审 | 全体 | 待开始 | All |

---

## 角色任务分配

| 角色 | Subagent | Phase 2 职责 | 当前状态 |
|------|----------|--------------|----------|
| 项目协调 | @coordinator | 任务分配、进度跟踪 | ✅ Phase 2.3 完成 |
| 运维开发 | @devops-engineer | SSH部署、CI/CD、环境 | ✅ Phase 2.3 完成 |
| 后端工程 | @backend-engineer | 告警、API、RBAC、持久化 | ✅ Phase 2.3 完成 |
| AI调度工程 | @ai-scheduling-engineer | 配额管理、公平调度 | ✅ Phase 2.3 完成 |
| 前端工程 | @frontend-engineer | Next.js Web Console | ⏳ Phase 2.4 待开始 |
| 测试工程 | @test-engineer | 单元/功能测试 | ✅ Phase 2.3 完成 |
| QA工程 | @qa-engineer | 系统/验收/E2E测试 | ✅ Phase 2.3 完成 |
| 性能工程 | @performance-engineer | 性能基准、监控 | ✅ Phase 2.3 完成 |

---

## 迭代评审机制

### 10 轮迭代计划

| 迭代 | 周次 | 评审内容 |
|------|------|---------|
| Round 1 | W1 | Phase 2.1 架构设计评审 |
| Round 2 | W2 | Phase 2.1 实现评审 |
| Round 3 | W3 | Phase 2.2 架构设计评审 |
| Round 4 | W4 | Phase 2.2 实现评审 |
| Round 5 | W5 | Phase 2.3 架构设计评审 |
| Round 6 | W6 | Phase 2.3 实现评审 |
| Round 7 | W7 | Phase 2.4 架构设计评审 |
| Round 8 | W8 | Phase 2.4 实现评审 |
| Round 9 | W9 | 测试集成评审 |
| Round 10 | W10 | 最终评审与交付 |

### 评审团队

每轮评审由以下角色参与：
- **@coordinator** - 主持评审
- **3 名架构师** - 软件架构评审
- **@qa-engineer** - 质量评审
- **@test-engineer** - 测试覆盖评审
- **@performance-engineer** - 性能评审

### 评分标准

| 维度 | 权重 | 评分范围 |
|------|------|---------|
| 功能完整性 | 30% | 0-10 |
| 代码质量 | 20% | 0-10 |
| 测试覆盖 | 20% | 0-10 |
| 性能达标 | 15% | 0-10 |
| 架构合理性 | 15% | 0-10 |

---

## 进度更新日志

| 日期 | 里程碑 | 更新内容 | 执行者 |
|------|--------|---------|--------|
| 2026-03-26 | Phase 2 启动 | 创建 Phase 2 调度计划 | @coordinator |
| 2026-03-27 | Phase 2.2 完成 | Round 4-7 完成，122 tests 通过 | @coordinator |
| 2026-03-27 | SSH 安全修复 | MITM 防护、连接池原子性修复 | @devops-engineer |
| 2026-03-27 | RBAC/HMAC 测试 | 25 tests + 26 Tasks API tests | @test-engineer |
| 2026-03-27 | Phase 2.3 架构设计 | RBAC/Fair Scheduling/Frontend 设计文档 | @backend/ai-scheduling/frontend |
