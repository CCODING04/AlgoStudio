# from: @coordinator
# to: @test-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 1

## 任务: 测试覆盖率分析

### 背景
评审团决策：分阶段达成 80% 覆盖率
Phase 2.5 目标: 65%

### 具体任务

1. **分析当前覆盖率报告**
   - 查看 `tests/reports/coverage.xml`
   - 确认各模块当前覆盖率:
     - api.routes (当前 47%)
     - core.scheduler.routing
     - core.scheduler.scorers
     - core.deploy.rollback (当前 89%)

2. **制定覆盖率提升计划**
   - api.routes: 47% → 70% (Phase 2.5)
   - routing/scorers: 提升至 80%+
   - 启用分支覆盖 (branch=true)

3. **准备 Phase 3.1 测试策略**
   - 确定需要新增的测试用例数量
   - 识别高优先级测试模块

### 输出
完成后在 `talks/test-engineer-to-coordinator-round1-2026-03-28.md` 汇报：
- 当前覆盖率分析
- 覆盖率提升计划
- 预估新增测试数量
