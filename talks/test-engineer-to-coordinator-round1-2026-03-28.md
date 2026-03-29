# from: @test-engineer
# to: @coordinator
# date: 2026-03-28
# type: report
# round: Phase 3.1 Round 1

## Phase 3.1 Round 1 任务完成汇报: 测试覆盖率分析

---

## 一、当前覆盖率分析

### 1.1 整体覆盖率
| 指标 | 数值 |
|------|------|
| **总行数** | 5458 |
| **覆盖行数** | 3406 |
| **总覆盖率** | **62.4%** |
| **分支覆盖** | **0%** (未启用) |

### 1.2 关键模块覆盖率

| 模块 | 当前覆盖率 | 目标覆盖率 | 差距 |
|------|----------|----------|------|
| **api.routes** | **44.16%** | 70% (Phase 2.5) | -25.84% |
| **core.scheduler.routing** | **49.46%** | 80% | -30.54% |
| **core.scheduler.scorers** | **87.1%** | 80%+ | **已达标** |
| **core.deploy.rollback** | **77.87%** | 89% | -11.13% |

### 1.3 api.routes 详细分析

| 文件 | 语句数 | 缺失数 | 覆盖率 |
|------|-------|-------|--------|
| algorithms.py | 34 | 34 | **0%** |
| audit.py | 67 | 36 | **46%** |
| cluster.py | 214 | 131 | **39%** |
| deploy.py | 231 | 126 | **45%** |
| hosts.py | 43 | 23 | **47%** |
| tasks.py | 102 | 37 | **64%** |

### 1.4 core.scheduler.routing 详细分析

| 文件 | 语句数 | 缺失数 | 覆盖率 |
|------|-------|-------|--------|
| complexity_evaluator.py | 49 | 42 | **14%** |
| router.py | 41 | 5 | **88%** |

---

## 二、覆盖率提升计划

### 2.1 Phase 2.5 目标: 65%

**api.routes (44% -> 65%, 需提升约21个百分点)**

| 文件 | 优先级 | 需新增测试用例数 | 关键缺失 |
|------|--------|----------------|---------|
| algorithms.py | **P0** | 8-10 | 全部缺失，需新增 |
| cluster.py | **P1** | 15-20 | 状态查询/节点管理 |
| deploy.py | **P1** | 12-15 | SSH部署流程 |
| tasks.py | **P2** | 8-10 | 状态转换/SSE |

**core.deploy.rollback (78% -> 85%)**

| 文件 | 优先级 | 需新增测试用例数 | 关键缺失 |
|------|--------|----------------|---------|
| rollback.py | P2 | 5-8 | 错误路径/边界条件 |

### 2.2 Phase 3.1 目标: 80%

**core.scheduler.routing (49% -> 80%, 需提升约31个百分点)**

| 文件 | 优先级 | 需新增测试用例数 | 关键缺失 |
|------|--------|----------------|---------|
| complexity_evaluator.py | **P0** | 12-15 | 复杂度计算逻辑 |
| router.py | P1 | 3-5 | 路由决策 |

**api.routes 全面提升 (65% -> 80%)**

需要额外约 30-40 个测试用例覆盖剩余边界条件。

---

## 三、预估新增测试数量

| 阶段 | 新增测试用例数 | 覆盖模块 |
|------|--------------|---------|
| Phase 2.5 | **45-60** | api.routes |
| Phase 3.1 | **50-70** | routing + 全模块提升 |
| **总计** | **95-130** | |

---

## 四、关键问题

### 4.1 测试基础设施问题
**问题**: 221 个测试失败，原因是 `RuntimeError: This event loop is already running`

**影响模块**:
- tests/unit/core/test_global_queue.py
- tests/unit/scheduler/test_wfq_scheduler.py
- tests/unit/test_rollback.py
- tests/integration/test_database_integration.py

**根因**: pytest-asyncio 事件循环配置问题

**修复方案**: 在 pytest.ini 中配置:
```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
```

### 4.2 分支覆盖未启用
**问题**: branch-rate=0，未启用分支覆盖

**修复方案**: 在 pyproject.toml 或 pytest.ini 中启用分支覆盖:
```toml
[tool.coverage.run]
branch = true
```

---

## 五、行动计划

### Immediate (本周)
1. [ ] 修复 pytest-asyncio 配置问题
2. [ ] 启用分支覆盖
3. [ ] 新增 10-15 个 api.routes 测试用例

### Phase 2.5 (本轮迭代)
1. [ ] api.routes 覆盖率提升至 65%
2. [ ] core.deploy.rollback 覆盖率提升至 85%
3. [ ] 新增 45-60 个测试用例

### Phase 3.1 (下轮迭代)
1. [ ] 整体覆盖率提升至 80%
2. [ ] core.scheduler.routing 覆盖率提升至 80%+
3. [ ] 启用分支覆盖率达到 60%+

---

## 六、测试数据生成器状态

已创建测试工厂:
- `tests/factories/deploy_factory.py` - 部署测试数据

待创建:
- `tests/factories/task_factory.py` - 任务测试数据
- `tests/factories/host_factory.py` - 主机测试数据

---

## 七、CI 集成状态

- 测试脚本: `.github/workflows/test.yml` (需验证)
- 覆盖率报告: `tests/reports/coverage.xml`
- HTML 报告: `tests/reports/coverage-html/`

---

**报告完成时间**: 2026-03-28
**测试工程师**: @test-engineer
