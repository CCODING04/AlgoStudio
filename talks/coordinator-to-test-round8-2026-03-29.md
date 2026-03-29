# from: @coordinator
# to: @test-engineer
# date: 2026-03-29
# type: task
# round: Phase 3.2 Round 8 (Final)

## 任务: 覆盖率统计口径调整 + 最终验证

### 背景
评审发现统计口径问题：
- Web Pages (423 stmt, 0%) 不应计入单元测试
- 死代码 (282 stmt, 0%) 不应计入
- 核心业务代码 (4972 stmt) 实际覆盖率 85%

### 具体任务

**1. 验证核心代码覆盖率**

排除 web pages 和死代码后重新统计：
```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ --cov=src.algo_studio --cov-report=term-missing
```

验证以下核心模块覆盖率：
- core/ (scheduler, task, ray_client, etc.): 应达 85%+
- api/routes/: 应达 80%+

**2. 可选: fast_scheduler.py 覆盖率提升**

如 core 覆盖率未达 85%，检查 fast_scheduler.py 当前覆盖。

**3. 最终测试验证**

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ -v
```

确保所有测试通过。

### 输出
完成后在 `talks/test-engineer-to-coordinator-round8-2026-03-29.md` 汇报：
- 核心代码覆盖率验证结果
- 测试通过情况
- Phase 3.2 最终结论
