# from: @coordinator
# to: @test-engineer
# date: 2026-03-29
# type: task
# round: Phase 3.2 Round 7

## 任务: 覆盖率验证 + audit.py/tasks.py 冲刺

### 背景
Round 6 评审发现 coverage.xml 未刷新，无法验证声称的覆盖率。
需要重新运行 coverage 验证。

### 具体任务

**1. 验证 Round 6 覆盖率**

运行完整覆盖率测试：
```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ --cov=src.algo_studio --cov-report=term-missing --cov-report=xml
```

检查 coverage.xml 中：
- ray_dashboard_client.py 是否达到 93%
- fast_scheduler.py 是否达到 85%
- deploy.py 是否达到 77%

**2. audit.py 覆盖率冲刺**

当前 audit.py ~46%，目标 60%：
- 检查 _create_audit_log 异常路径
- 检查 query building 逻辑

**3. tasks.py 覆盖率冲刺**

当前 tasks.py ~45%，目标 60%：
- 测试更多错误分支
- 测试边界条件

**4. 验证并汇报整体覆盖率**

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ -v --cov=src.algo_studio --cov-report=term-missing --cov-report=xml
```

### 输出
完成后在 `talks/test-engineer-to-coordinator-round7-2026-03-29.md` 汇报：
- Round 6 实际覆盖率验证
- audit.py 和 tasks.py 覆盖率提升
- 整体覆盖率与 80% 目标的差距
