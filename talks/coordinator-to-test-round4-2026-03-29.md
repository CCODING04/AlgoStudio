# from: @coordinator
# to: @test-engineer
# date: 2026-03-29
# type: task
# round: Phase 3.2 Round 4

## 任务: routing + scorers + agentic_scheduler 覆盖率冲刺

### 背景
评审建议：使用接口驱动测试和依赖注入隔离外部依赖。

Round 3 成就：task.py 80%，audit.py 100%
Round 4 目标：62% → 66%

### 具体任务

**1. routing 模块测试**

创建 `tests/unit/api/routes/test_complexity_evaluator.py`：
- 测试 ComplexityEvaluator
- 测试评估逻辑

创建 `tests/unit/api/routes/test_router.py`：
- 测试路由选择逻辑

**2. scorers 模块测试**

创建 `tests/unit/scheduler/test_multi_dim_scorer.py`：
- 测试多维评分逻辑
- 测试资源评估

**3. agentic_scheduler 测试**

创建 `tests/unit/scheduler/test_agentic_scheduler.py`：
- 黑盒测试调度器行为
- 使用 mock 隔离外部依赖

**4. node_monitor.py 测试**

创建 `tests/unit/core/test_node_monitor.py`：
- 测试 NodeMonitorActor
- 测试 GPU 信息获取

**5. 验证覆盖率**
```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ -v --cov=src.algo_studio --cov-report=term-missing
```

### 输出
完成后在 `talks/test-engineer-to-coordinator-round4-2026-03-29.md` 汇报：
- 各模块覆盖率
- 与66%目标的差距
