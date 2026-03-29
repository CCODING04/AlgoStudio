# from: @coordinator
# to: @test-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 6

## 任务: api.routes 覆盖率提升

### 背景
Phase 2.5 目标: 65% 覆盖率
当前: api.routes 约 44%

### 具体任务

1. **分析 api.routes 覆盖率**
   ```bash
   PYTHONPATH=src .venv/bin/python -m pytest tests/unit/api/routes/ --cov=src.algo_studio.api.routes --cov-report=term-missing
   ```

2. **优先补充测试的模块** (按缺失率排序):
   - cluster.py (39% → 目标 60%)
   - deploy.py (45% → 目标 60%)
   - hosts.py (47% → 目标 60%)
   - audit.py (36% → 目标 50%)

3. **目标**: 整体 api.routes 覆盖率提升至 55%+

### 输出
完成后在 `talks/test-engineer-to-coordinator-round6-2026-03-28.md` 汇报：
- 当前覆盖率
- 新增测试数量
- api.routes 覆盖率提升结果
