# Phase 3.2 Round 3 评审报告

**日期:** 2026-03-29
**Round:** 3/8
**评审结果:** CONDITIONAL PASS

---

## 一、Round 3 成果总结

| 指标 | 上轮 (R2) | 本轮 (R3) | 变化 |
|------|-----------|-----------|------|
| 整体覆盖率 | 61% | 62% | +1% |
| core/task.py | 55% | 80% | +25% ✅ |
| core/ray_client.py | N/A | 84% | 新增测试 ✅ |
| audit.py | 36% | 100% | +64% ✅ |
| 测试通过数 | N/A | 704 | ✅ |

**亮点:**
1. pytest-asyncio 修复生效，704 tests 通过
2. task.py 覆盖率 55% → 80% (超预期)
3. audit.py 覆盖率 36% → 100% (超预期)
4. ray_client.py 新增 18 tests，达到 84%

---

## 二、覆盖率差距分析

### 2.1 当前状态 vs 80% 目标

| 模块 | 当前覆盖 | 目标 | 差距 | 预估提升潜力 |
|------|----------|------|------|--------------|
| **整体** | 62% | 80% | **18%** | - |
| core/scheduler/routing | 9-13% | 80% | ~70% | **高** |
| core/scheduler/scorers | 10% | 80% | ~70% | **高** |
| core/scheduler/agents | 17-28% | 60% | ~40% | **高** |
| monitor/node_monitor | 13% | 60% | ~47% | 中 |
| core/ray_dashboard_client | 24% | 60% | ~36% | 中 |
| api/routes/deploy | 63% | 80% | ~17% | 中 |

### 2.2 重点突破模块 (按潜力排序)

**第一梯队 (高回报):**
```
core/scheduler/routing/complexity_evaluator.py  - 9%
core/scheduler/routing/router.py                - 13%
core/scheduler/scorers/multi_dim_scorer.py      - 10%
core/scheduler/agents/deep_path_agent.py        - 18%
core/scheduler/agents/fast_scheduler.py          - 28%
```

这些模块合计约 800+ statements，覆盖率每提升 10% 约等于 +1.5% 整体覆盖率。

**第二梯队 (中等回报):**
```
monitor/node_monitor.py                         - 13%
core/ray_dashboard_client.py                     - 24%
core/scheduler/agentic_scheduler.py              - 25%
api/routes/deploy.py                             - 63%
```

---

## 三、架构评审意见

### 3.1 代码质量观察

**正面:**
- task.py 测试结构清晰，使用 pytest-asyncio 正确
- audit.py 测试覆盖全面，fixture 设计合理
- ray_client.py 测试隔离良好

**关注点:**
- routing/scorers 模块接口复杂，直接 mock 难度高
- LLM provider 测试需要实际 API 或深度 mock
- node_monitor.py 依赖 pynvml，直接测试困难

### 3.2 测试工程建议

**针对 routing/scorers 模块:**

建议采用**接口驱动测试**策略：

```python
# 1. 为 ComplexityEvaluator 创建轻量级 mock
class MockComplexityEvaluator:
    def evaluate(self, task) -> float:
        return 0.5  # deterministic for tests

# 2. 使用 dependency injection 而非 monkey-patching
@pytest.fixture
def complexity_evaluator():
    return MockComplexityEvaluator()

def test_router(complexity_evaluator):
    router = Router(evaluator=complexity_evaluator)
    # test
```

**针对 agentic_scheduler 模块:**

建议采用**黑盒集成测试**：

```python
async def test_agentic_scheduler_full_flow():
    """测试完整调度流程，不关心内部实现"""
    scheduler = AgenticScheduler()
    result = await scheduler.schedule(task)
    assert result.assigned_node is not None
    assert result.path in ["fast", "deep"]
```

---

## 四、Round 4 修复指令

### 4.1 覆盖率冲刺策略

| 任务 | 负责人 | 优先级 | 目标提升 |
|------|--------|--------|----------|
| routing/complexity_evaluator + router 测试 | @test-engineer | P0 | +3% |
| scorers/multi_dim_scorer 测试 | @test-engineer | P0 | +2% |
| agentic_scheduler 黑盒测试 | @test-engineer | P1 | +2% |
| node_monitor.py 单元测试 | @test-engineer | P1 | +1% |
| deploy.py 补充测试 | @test-engineer | P2 | +1% |

### 4.2 具体修复指令

**@test-engineer:**

1. **routing 模块 (P0)**
   - 创建 `tests/unit/scheduler/test_complexity_evaluator.py`
   - 创建 `tests/unit/scheduler/test_router.py`
   - 使用 MockComplexityEvaluator 隔离外部依赖

2. **scorers 模块 (P0)**
   - 创建 `tests/unit/scheduler/test_multi_dim_scorer.py`
   - 测试 4 个核心方法: score(), compare(), normalize(), aggregate()

3. **agentic_scheduler (P1)**
   - 创建 `tests/unit/scheduler/test_agentic_scheduler.py`
   - 专注端到端流程测试，不深入内部 agent 逻辑

4. **node_monitor.py (P1)**
   - 创建 `tests/unit/monitor/test_node_monitor.py`
   - Mock pynvml，测试逻辑分支

---

## 五、18% 覆盖率差距解决方案

### 5.1 差距分解

```
目标: 80% (当前 62%)
差距: 18% = 1022 lines

分解:
- routing 模块 (9% → 60%): 约 +3% 整体
- scorers 模块 (10% → 60%): 约 +2.5% 整体
- agents 模块 (18-28% → 50%): 约 +2% 整体
- agentic_scheduler (25% → 50%): 约 +1.5% 整体
- node_monitor (13% → 50%): 约 +1.5% 整体
- deploy.py (63% → 80%): 约 +1% 整体
- 其他优化: 约 +6.5% 整体
```

### 5.2 可行性评估

**结论: 可行，但需要高效执行**

按上述计划执行 4 轮 (R4-R7) 后，预计可达:
- R4: 62% → 66%
- R5: 66% → 71%
- R6: 71% → 76%
- R7: 76% → 80%

**风险点:**
1. routing/scorers 接口复杂，测试设计耗时长
2. node_monitor.py 依赖 pynvml，需要深度 mock
3. LLM providers 测试需要外部依赖

**缓解措施:**
- 优先完成接口清晰的模块 (routing/scorers)
- node_monitor 降低目标至 40%
- LLM providers 保持低目标或 skip

---

## 六、最终结论

### 评审结果: CONDITIONAL PASS

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构完整性 | 8/10 | 模块划分清晰，接口设计合理 |
| 测试质量 | 7/10 | task.py/audit.py 改进显著 |
| 覆盖率进度 | 6/10 | +1% 进度偏慢 |
| 目标可达性 | 7/10 | 18% 差距可行但需高效执行 |

### 是否进入 Round 4: YES

**理由:**
1. ✅ pytest-asyncio 修复完成，704 tests 通过
2. ✅ task.py 80% (超预期 20%)
3. ✅ audit.py 100% (超预期 40%)
4. ⚠️ 整体覆盖率 62% (差 18%)

**但考虑到:**
- Phase 2.4 已遗留覆盖率低问题 (评审记录: 6/10)
- Phase 3.2 核心目标就是提升覆盖率
- 18% 差距需要多轮持续努力

**建议:**
1. 立即启动 routing/scorers 模块测试 (高潜力)
2. @test-engineer 并行处理多个低覆盖模块
3. 考虑引入 pytest-xdist 加速测试执行
4. Round 4 目标: 66%+

---

## 附录: 覆盖率详细数据

```
模块                        | 覆盖  | 语句数 | 未覆盖
---------------------------|-------|--------|--------
routing/complexity_eval    |   9%  |   49   |   42
routing/router             |  13%  |   41   |   32
scorers/multi_dim_scorer   |  10%  |  109   |   93
agents/deep_path_agent     |  18%  |  109   |   83
agents/fast_scheduler      |  28%  |   43   |   27
agentic_scheduler          |  25%  |  101   |   71
node_monitor               |  13%  |   54   |   46
ray_dashboard_client        |  24%  |  175   |  123
deploy.py                  |  63%  |  231   |   76
```
