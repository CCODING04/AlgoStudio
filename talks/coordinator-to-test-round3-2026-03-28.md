# from: @coordinator
# to: @test-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 3

## 任务: Q3 - api.routes.algorithms.py 测试覆盖 (P0)

### 背景
Round 1 分析发现 `api/routes/algorithms.py` 覆盖率 0% (34 statements 全缺失)
这是 P0 优先级，需要立即补充测试。

### 具体任务

1. **分析 algorithms.py**
   ```bash
   PYTHONPATH=src .venv/bin/python -m pytest tests/unit/api/routes/test_algorithms.py --cov=src.algo_studio.api.routes.algorithms --cov-report=term-missing
   ```

2. **添加测试用例**
   文件: `tests/unit/api/routes/test_algorithms.py`

   测试场景:
   - GET /algorithms - 列出算法
   - GET /algorithms/{name} - 获取算法详情
   - POST /algorithms - 创建算法 (如果存在)
   - 算法版本列表
   - 错误处理 (算法不存在)

3. **运行覆盖率验证**
   ```bash
   PYTHONPATH=src .venv/bin/python -m pytest tests/unit/api/routes/test_algorithms.py -v --cov=src.algo_studio.api.routes.algorithms --cov-report=term-missing
   ```

4. **目标**: algorithms.py 覆盖率从 0% 提升至 60%+

### 输出
完成后在 `talks/test-engineer-to-coordinator-round3-2026-03-28.md` 汇报：
- 新增测试用例数
- algorithms.py 覆盖率提升结果
