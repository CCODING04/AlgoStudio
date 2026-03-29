# Phase 2.5 任务计划

**版本:** v1.0
**日期:** 2026-03-27
**状态:** 规划中

---

## 1. Phase 2.5 目标

解决 Phase 2.4 最终评审遗留问题，提升系统生产就绪度。

## 2. 遗留问题汇总

### Critical (生产前必须修复)

| # | 问题 | 来源 | 负责人 |
|---|------|------|--------|
| C1 | Rollback SSH 操作是占位符 | 最终评审 | @devops-engineer |
| C2 | `/api/proxy/algorithms` 未实现 | 最终评审 | @frontend-engineer |

### Important (建议修复)

| # | 问题 | 来源 | 负责人 |
|---|------|------|--------|
| I1 | 核心模块测试覆盖率低 | 最终评审 | @test-engineer |
| I2 | pynvml 弃用警告 | 最终评审 | @devops-engineer |

### Suggestion (可选)

| # | 问题 | 来源 | 负责人 |
|---|------|------|--------|
| S1 | hosts.py utility functions 组织 | 最终评审 | @backend-engineer |
| S2 | Web Console SSH 密码暴露 | 最终评审 | @frontend-engineer |

## 3. Phase 2.5 迭代计划

### Round 1: Rollback SSH 实现

| 任务 | 负责人 | 测试目标 |
|------|--------|----------|
| 实现 _rollback_ray SSH 操作 | @devops-engineer | 单元测试 |
| 实现 _rollback_code SSH 操作 | @devops-engineer | 单元测试 |
| 实现 _rollback_deps SSH 操作 | @devops-engineer | 单元测试 |
| 实现 _rollback_venv SSH 操作 | @devops-engineer | 单元测试 |
| 实现 _rollback_sudo SSH 操作 | @devops-engineer | 单元测试 |
| 实现 _rollback_connecting SSH 操作 | @devops-engineer | 单元测试 |

### Round 2: API 完善

| 任务 | 负责人 | 测试目标 |
|------|--------|----------|
| 实现 /api/algorithms 端点 | @backend-engineer | 单元测试 |
| 实现 /api/proxy/algorithms 路由 | @frontend-engineer | 集成测试 |
| 实现 /api/algorithms/list 端点 | @backend-engineer | 单元测试 |

### Round 3: 测试覆盖提升

| 任务 | 负责人 | 测试目标 |
|------|--------|----------|
| permission_checker.py 单元测试 | @test-engineer | > 80% 覆盖 |
| global_queue.py 单元测试 | @test-engineer | > 80% 覆盖 |
| rollback.py 覆盖率提升 | @test-engineer | > 70% 覆盖 |
| memory/ 模块单元测试 | @test-engineer | > 60% 覆盖 |

### Round 4: 优化与清理

| 任务 | 负责人 | 测试目标 |
|------|--------|----------|
| pynvml → nvidia-ml-py 迁移 | @devops-engineer | 无警告 |
| 测试分层标记 (unit/integration/e2e) | @test-engineer | pytest markers |
| hosts.py utils 移到 util 模块 | @backend-engineer | 重构 |
| Web Console SSH 凭据优化 | @frontend-engineer | 安全改进 |

### Round 5: 最终评审

| 任务 | 负责人 | 测试目标 |
|------|--------|----------|
| 完整测试套件运行 | @qa-engineer | 全部通过 |
| 性能基准测试 | @performance-engineer | 全部达标 |
| 最终评审 | @architects | 通过 |

## 4. 任务依赖关系

```
Round 1 (C1 - Rollback SSH)
    │
    ├── _rollback_ray
    ├── _rollback_code
    ├── _rollback_deps
    ├── _rollback_venv
    ├── _rollback_sudo
    └── _rollback_connecting

Round 2 (C2 - API 实现) [可与 Round 1 并行]
    │
    ├── /api/algorithms 端点
    ├── /api/proxy/algorithms 路由
    └── /api/algorithms/list 端点

Round 3 (I1 - 测试覆盖) [依赖 Round 1, 2 完成]
    │
    ├── permission_checker 测试
    ├── global_queue 测试
    ├── rollback.py 覆盖提升
    └── memory/ 模块测试

Round 4 (优化) [可与 Round 3 并行部分]
    │
    ├── pynvml 迁移
    ├── 测试分层标记
    ├── hosts.py utils 重构
    └── SSH 凭据优化

Round 5 (最终评审)
    │
    ├── 完整测试套件
    ├── 性能基准测试
    └── 最终评审
```

## 5. 评审团队

与 Phase 2.4 相同：

| 评审角色 | 职责 |
|----------|------|
| @architect-alpha | 系统架构评审 |
| @architect-beta | API/安全评审 |
| @architect-gamma | 调度/性能评审 |
| @qa-engineer | QA 质量评审 |
| @performance-engineer | 性能基准评审 |

## 6. 完成标准

### Critical 问题修复
- [ ] C1: Rollback SSH 操作实际执行而非占位符
- [ ] C2: `/api/proxy/algorithms` 路由正确返回算法列表

### 测试覆盖
- [ ] permission_checker.py > 80% 覆盖
- [ ] global_queue.py > 80% 覆盖
- [ ] rollback.py > 70% 覆盖

### 性能目标
- [ ] 所有调度性能测试 < 目标值
- [ ] 测试执行时间优化 (目标: unit tests < 5min)

### 评审结果
- [ ] 最终评分 >= 9/10

---

**文档状态:** 规划中 - 待用户确认后启动
