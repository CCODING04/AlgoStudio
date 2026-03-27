# AlgoStudio Phase 2 团队结构

**版本:** v2.0
**日期:** 2026-03-26
**状态:** 正式版

---

## 1. 团队架构概览

Phase 2 团队由 **7** 名成员组成，采用扁平化组织结构：

```
@coordinator (项目协调)
    │
    ├── @devops-engineer ───────────────────────────┐
    │   └── SSH 部署 · CI/CD · 环境配置            │
    │                                               │
    ├── @backend-engineer ───────────────────────┤
    │   └── 告警系统 · API 文档 · RBAC · 持久化   │
    │                                               │
    ├── @ai-scheduling-engineer ───────────────────┤
    │   └── 资源配额 · 公平调度 · Ray 集成        │
    │                                               │
    ├── @frontend-engineer ────────────────────────┤
    │   └── Web Console · 实时数据 · 可视化        │
    │                                               │
    ├── @test-engineer ────────────────────────────┤
    │   └── 单元测试 · 功能测试 · 测试数据        │
    │                                               │
    ├── @qa-engineer ──────────────────────────────┤
    │   └── 系统测试 · 验收测试 · E2E · 缺陷管理 │
    │                                               │
    └── @performance-engineer ──────────────────────┘
        └── 性能测试 · 基准测试 · 监控 · 优化
```

---

## 2. 角色职责定义

### 2.1 @coordinator（项目协调）

**职责：**
- 项目整体进度规划和任务分配
- 里程碑跟踪和风险管理
- 跨团队协调和决策升级
- 依赖链管理（Phase 2.1 → 2.2 → 2.3）

**技能要求：**
- 项目管理（PMP/ACP 优先）
- 风险评估和决策
- 跨团队沟通协调

**Phase 2 交付物：**
- 阶段计划
- 进度报告
- 风险跟踪矩阵

---

### 2.2 @devops-engineer（运维开发工程师）

**职责：**
- SSH 自动化部署系统
- CI/CD 流水线搭建
- 环境配置管理
- 监控和日志系统

**Phase 2 任务：**
- SSH Worker 节点自动部署（asyncssh）
- 部署状态监控和回滚机制
- 环境一致性保障
- CI/CD 流水线集成

**技术栈：**
- asyncssh, paramiko, Shell
- Docker, Docker Compose
- GitHub Actions / GitLab CI
- Prometheus, Grafana

**交付物：**
- `scripts/ssh_deploy.py`
- CI/CD 配置文件
- 部署文档
- 回滚脚本

**测试要求：**
- 单元测试覆盖率 ≥ 80%
- 集成测试通过

---

### 2.3 @backend-engineer（后端工程师）

**职责：**
- FastAPI 核心业务逻辑
- 数据库设计与实现
- Redis 缓存和消息队列
- API 设计与实现

**Phase 2 任务：**
- 告警系统（AlertManager, SSE 推送）
- API 文档自动化（Swagger）
- 用户权限系统（RBAC）
- 任务历史持久化
- 数据库迁移（Alembic）

**技术栈：**
- Python, FastAPI, SQLAlchemy
- SQLite, PostgreSQL, Alembic
- Redis Stream, SSE
- Pydantic, JWT

**交付物：**
- API 端点实现
- 数据库模型
- 告警服务
- RBAC 实现
- API 文档

**测试要求：**
- 单元测试覆盖率 ≥ 80%
- API 集成测试通过

---

### 2.4 @ai-scheduling-engineer（AI调度工程师）

**职责：**
- 任务调度算法设计与实现
- 资源配额管理
- Ray 调度器集成

**Phase 2 任务：**
- 资源配额系统（QuotaManager）
- 公平调度算法实现
- 调度器与 Ray 集成
- 配额告警机制
- 与后端配额 API 对齐

**技术栈：**
- Python, Ray
- 调度算法（公平调度、层级队列）
- SQLite/Redis 配额存储
- pynvml

**交付物：**
- QuotaManager 实现
- 公平调度算法
- 配额 API 集成
- 调度集成代码

**测试要求：**
- 调度算法单元测试
- 配额校验集成测试
- 公平性指标验证

---

### 2.5 @frontend-engineer（前端工程师）

**职责：**
- Next.js Web Console 开发
- React 组件设计与实现
- UI/UX 优化

**Phase 2 任务：**
- Web Console 4 页面（Dashboard/Tasks/Hosts/Deploy）
- SSE 实时数据展示
- 训练曲线可视化（Recharts）
- 日志终端（xterm.js）
- API Key 认证（Header 代理）

**技术栈：**
- Next.js 14+, React, TypeScript
- shadcn/ui, Tailwind CSS
- Recharts, xterm.js
- React Query, Zustand

**交付物：**
- Web Console 应用
- React 组件库
- SSE 实时组件
- 可视化图表组件

**测试要求：**
- 组件单元测试
- E2E 测试（与 @qa 协作）

---

### 2.6 @test-engineer（测试工程师 - 单元/功能测试）

**职责：**
- 单元测试设计与实现
- 功能测试（模块级）
- 测试数据准备
- 自动化测试脚本

**Phase 2 任务：**
- 各模块单元测试（TDD）
- SSH 部署功能测试
- 后端 API 测试
- 配额算法测试
- 测试数据生成

**测试范围：**
- 单元测试（pytest）
- 集成测试（模块间）
- Mock 测试（隔离依赖）
- 冒烟测试

**交付物：**
- 测试用例（≥ 100 个）
- 测试覆盖率报告（≥ 80%）
- 测试数据生成器
- CI 集成测试脚本

**测试工具：**
- pytest, pytest-cov
- pytest-mock
- factory-boy（测试数据）
- Faker（测试数据生成）

---

### 2.7 @qa-engineer（质量保障工程师 - 系统/验收测试）

**职责：**
- 系统测试设计与执行
- 验收测试（UAT）
- 性能测试协作
- 缺陷管理和跟踪

**Phase 2 任务：**
- 端到端测试（SSH 部署流程）
- Web Console 验收测试
- 多节点集群测试
- SQLite/Redis 性能验证
- 缺陷报告和跟踪

**测试范围：**
- E2E 测试（Playwright/Cypress）
- 压力测试
- 兼容性测试
- 验收测试（UAT）

**交付物：**
- E2E 测试用例
- 测试报告
- 缺陷跟踪报告
- 质量评估报告

**测试工具：**
- Playwright / Cypress
- Locust（压力测试）
- Allure（测试报告）
- JIRA（缺陷跟踪）

---

### 2.8 @performance-engineer（性能测试工程师）

**职责：**
确保平台在各种负载下的稳定性和性能指标达标。

**Phase 2 任务：**
- 性能基准测试建立
- 平台性能测试（API、SSE、数据库）
- 算法性能测试（训练、推理、调度）
- 数据性能测试（加载、传输、JuiceFS）
- 性能监控配置
- 性能瓶颈分析

**性能指标定义：**

| 类型 | 指标 | 目标 |
|------|------|------|
| **平台** | API p95 响应 | < 100ms |
| **平台** | SSE 并发 | ≥ 100 连接 |
| **平台** | SQLite p99 | < 100ms |
| **算法** | 训练启动 | < 30s |
| **算法** | GPU 利用率 | ≥ 80% |
| **算法** | 调度延迟 p95 | < 100ms |
| **算法** | 推理延迟 p99 | < 500ms |
| **数据** | 数据集加载 | < 10s |
| **数据** | JuiceFS 吞吐 | ≥ 500 MB/s |

**技术栈：**
- pytest-benchmark, locust, wrk
- prometheus-client, psutil, nvidia-smi
- py-spy, cProfile, line_profiler
- Grafana

**交付物：**
- 性能测试计划（`performance-test-plan.md`）
- 性能基准文档
- 性能测试报告（每周）
- Prometheus 配置
- Grafana 仪表盘

**测试工具：**
- pytest（测试框架）
- pytest-benchmark（基准测试）
- locust（HTTP 负载）
- wrk（高性能基准）
- nvidia-smi（GPU 监控）
- psutil（系统监控）

---

## 3. 测试角色对比

| 维度 | @test-engineer | @qa-engineer | @performance-engineer |
|------|-----------------|--------------|----------------------|
| **测试类型** | 单元/功能 | 系统/验收 | 性能 |
| **测试时机** | 开发过程中 | 开发完成后 | 开发过程中 + 完成后 |
| **关注点** | 正确性 | 功能完整性 | 性能指标 |
| **测试对象** | 模块/函数 | 完整系统 | 关键路径 |
| **自动化** | 全自动 | 半自动 | 全自动 |
| **失败标准** | 任何错误 | 功能缺陷 | 指标不达标 |

---

## 4. 依赖关系

### 4.1 角色间依赖

```
@devops-engineer
    ├── 需要: 环境配置支持
    └── 提供: SSH 部署基础设施给 @backend, @frontend

@backend-engineer
    ├── 需要: @devops 环境, @test 测试框架
    └── 提供: API 给 @frontend, @qa

@ai-scheduling-engineer
    ├── 需要: @backend 数据库模型
    └── 提供: 调度服务

@frontend-engineer
    ├── 需要: @backend API, @devops 环境
    └── 提供: Web Console

@test-engineer
    ├── 需要: 所有模块代码
    └── 提供: 测试报告给 @qa

@qa-engineer
    ├── 需要: @test 测试报告, @frontend Web Console
    └── 提供: UAT 报告

@performance-engineer
    ├── 需要: 所有模块, 监控系统
    └── 提供: 性能报告
```

### 4.2 阶段依赖

```
Phase 2.1 (Week 1-2)
├── @devops: 环境配置
├── @backend: 数据库迁移
├── @ai-scheduling: 配额数据模型
└── @test: 测试框架

Phase 2.2 (Week 3-4)
├── @backend: 告警系统, API
├── @ai-scheduling: 调度集成
├── @frontend: Dashboard/Tasks
└── @test: API 测试

Phase 2.3 (Week 5-6)
├── @backend: RBAC
├── @frontend: Hosts/Deploy
├── @qa: E2E 测试
└── @performance: 性能测试

Phase 2.4 (Week 7-8)
├── @frontend: 完善
├── @qa: 验收测试
└── @performance: 完整基准
```

---

## 5. 沟通机制

### 5.1 例会

| 会议 | 频率 | 参与 | 内容 |
|------|------|------|------|
| 每日站会 | 每日 | 全体 | 进度、阻塞、计划 |
| 每周评审 | 每周 | 全体 + @coordinator | 里程碑评审 |
| 性能同步 | 每周 | @performance + 相关 | 性能指标跟踪 |

### 5.2 文档

| 文档 | 位置 | 更新频率 |
|------|------|---------|
| 进度报告 | `talks/` | 每日 |
| 测试报告 | `tests/reports/` | 每周 |
| 性能报告 | `docs/superpowers/team/perf-reports/` | 每周 |
| 代码审查 | GitHub PR | 按需 |

---

## 6. 验收流程

```
代码提交
    │
    ├── @test-engineer ──→ 单元测试 ──→ 覆盖率报告 ──→ 通过? ──→ 是
    │                          ↓
    │                       失败? ──→ 修复 ──→ 重新测试
    │
    ├── @qa-engineer ──────→ E2E 测试 ──→ 测试报告 ──→ 通过? ──→ 是
    │                          ↓
    │                       失败? ──→ 缺陷跟踪 ──→ 修复
    │
    └── @performance-engineer ──→ 性能测试 ──→ 基准报告 ──→ 达标? ──→ 是
                                   ↓
                                不达标? ──→ 优化建议 ──→ 重新测试
```

---

## 7. 团队技能矩阵

| 角色 | Python | FastAPI | Ray | Next.js | 测试 | 性能分析 |
|------|--------|---------|-----|---------|------|---------|
| @coordinator | ★★☆ | ★☆☆ | ★★☆ | - | ★☆☆ | - |
| @devops | ★★★ | ★★☆ | ★★☆ | - | ★★☆ | ★☆☆ |
| @backend | ★★★ | ★★★ | ★★☆ | - | ★★☆ | ★☆☆ |
| @ai-scheduling | ★★★ | ★★☆ | ★★★ | - | ★★☆ | ★☆☆ |
| @frontend | ★★☆ | ★★☆ | - | ★★★ | ★★☆ | - |
| @test | ★★★ | ★★☆ | ★★☆ | - | ★★★ | ★☆☆ |
| @qa | ★★☆ | ★★☆ | - | ★★☆ | ★★★ | ★★☆ |
| @performance | ★★★ | ★★☆ | ★★☆ | - | ★★☆ | ★★★ |

**说明：** ★★★ 精通 ★★☆ 熟练 ★☆☆ 了解

---

## 8. 扩展计划

### Phase 3 角色需求

| 角色 | 职责 | 优先级 |
|------|------|--------|
| @security-engineer | 安全审计、渗透测试 | 高 |
| @data-engineer | 数据管道、MLOps | 中 |
| @platform-engineer | 平台演进、SRE | 中 |

---

**文档状态:** 正式版
**下次评审:** Phase 2 完成后
