# Phase 3.2 实施计划

**项目：** AlgoStudio 平台能力拓展
**阶段：** Phase 3.2 - 覆盖率提升 + Sentinel 完善
**周期：** 8 轮迭代 (Round 1-8)
**最后更新：** 2026-03-29
**项目状态：** 🔄 启动中

---

## 目标

| 指标 | 当前 | 目标 |
|------|------|------|
| 整体覆盖率 | 55% | **80%** |
| api.routes | 62% | **80%** |
| audit.py | 36% | **60%** |
| tasks.py | 20% | **60%** |
| 测试通过率 | 100% | 保持 |

---

## 甘特图 (最大化并行)

```
Round   │ R1 │ R2 │ R3 │ R4 │ R5 │ R6 │ R7 │ R8 │
────────┼────┼────┼────┼────┼────┼────┼────┼────┤
audit覆盖│████│████│    │    │    │    │    │    │
tasks覆盖│████│████│    │    │    │    │    │    │
Sentinel │████│████│    │    │    │    │    │    │
Phase2   │    │    │████│████│    │    │    │    │
验证     │    │    │████│████│████│████│████│████│
80%达标  │    │    │    │    │████│████│████│████│
```

---

## Round 并行任务设计

### Round 1: 三大并行任务

| 任务 | 负责人 | 并行状态 |
|------|--------|----------|
| audit.py 认证 mock 重构 | @test-engineer | 🔄 |
| tasks.py SSE 端点测试 | @test-engineer | 🔄 |
| Sentinel 配置审计 | @devops-engineer | 🔄 |
| Phase 2: DeploymentSnapshotStore 接口定义 | @backend-engineer | 🔄 |

### Round 2: 覆盖率提升 + Sentinel 验证

| 任务 | 负责人 | 并行状态 |
|------|--------|----------|
| audit.py 覆盖率 36% → 60% | @test-engineer | 🔄 |
| tasks.py 覆盖率 20% → 60% | @test-engineer | 🔄 |
| Sentinel 故障转移测试 | @devops-engineer | 🔄 |
| DeploymentSnapshotStore 实现 | @backend-engineer | 🔄 |

### Round 3-4: Phase 2 完成 + 覆盖率验证

| 任务 | 负责人 | 并行状态 |
|------|--------|----------|
| DeploymentSnapshotStore 测试 | @test-engineer | 🔄 |
| RollbackService 重构 | @backend-engineer | 🔄 |
| 整体覆盖率 70% 验证 | @test-engineer | 🔄 |
| Sentinel 秘钥认证验证 | @devops-engineer | 🔄 |

### Round 5-6: 覆盖率冲刺

| 任务 | 负责人 | 并行状态 |
|------|--------|----------|
| 覆盖率 75% 冲刺 | @test-engineer | 🔄 |
| 核心模块 (routing/scorers) 85%+ | @test-engineer | 🔄 |
| 全量集成测试 | @qa-engineer | 🔄 |

### Round 7-8: 最终验证

| 任务 | 负责人 | 并行状态 |
|------|--------|----------|
| 覆盖率 80% 达标 | @test-engineer | 🔄 |
| 全量测试 700+ 通过 | @test-engineer | 🔄 |
| 最终评审 | 评审团 | 🔄 |

---

## Phase 3.2 任务详情

### 并行任务组 1 (Round 1-2)

#### audit.py 认证 mock 重构

**问题**: RBAC 中间件认证 mock 复杂度高

**方案**:
```python
# 创建 audit_auth_mock fixture
@pytest.fixture
def audit_auth_mock(mocker):
    mocker.patch('algo_studio.api.middleware.rbac.RBACMiddleware.verify_signature', return_value=True)
    mocker.patch('algo_studio.api.middleware.audit.AuditMiddleware.should_log', return_value=True)
    yield
    mocker.restore_all()
```

#### tasks.py SSE 端点测试

**问题**: SSE 端点测试 fixture 隔离问题

**方案**:
```python
@pytest.fixture(autouse=True)
def cleanup_sse_state():
    """Clean SSE state between tests."""
    yield
    SSEProgressStore._instances.clear()
```

#### Sentinel 配置审计

**任务**:
1. 提交 sentinel.conf 配置文件到项目
2. 验证 Sentinel 秘钥认证
3. 修复 Sentinel 监控偏差问题

#### DeploymentSnapshotStore Phase 2

**任务**:
1. 创建 DeploymentSnapshotStore 实现
2. 保持向后兼容
3. 添加单元测试

---

## 评审团职责

### 评审团成员
- @architect-alpha: 系统架构评审
- @architect-beta: API/安全架构评审
- @architect-gamma: 调度/性能架构评审
- @test-engineer: 测试工程评审
- @performance-engineer: 性能基准评审
- @qa-engineer: QA 质量评审

### 评审维度
| 维度 | 说明 |
|------|------|
| 可行性 | 技术实现难度 |
| 成本 | 实施成本 |
| 效益 | 解决问题的重要性 |
| 风险 | 实施风险 |
| 可维护性 | 长期维护成本 |

---

## Phase 3.2 Round 进度

| Round | 状态 | 主要任务 | 目标 |
|-------|------|----------|------|
| Round 1 | ⏳ | audit+tasks+Sentinel+Phase2 | 并行任务启动 |
| Round 2 | ⏳ | 覆盖率提升 + 验证 | 70% 覆盖率 |
| Round 3 | ⏳ | Phase 2 完成 | DeploymentSnapshotStore |
| Round 4 | ⏳ | 覆盖率验证 | 75% 覆盖率 |
| Round 5 | ⏳ | 覆盖率冲刺 | 80% 覆盖率 |
| Round 6 | ⏳ | 全量集成测试 | 700+ tests |
| Round 7 | ⏳ | 覆盖率最终验证 | 80% 达标 |
| Round 8 | ⏳ | 最终评审 | Phase 3.2 完成 |

---

## Phase 3.2 目标验收标准

| 标准 | 目标 |
|------|------|
| 整体覆盖率 | 80%+ |
| api.routes | 80%+ |
| audit.py | 60%+ |
| tasks.py | 60%+ |
| 测试通过率 | 100% |
| Sentinel 故障转移 | 验证通过 |
| Phase 2 存储抽象 | 完成 |

---
