# from: @coordinator
# to: @test-engineer
# date: 2026-03-29
# type: task
# round: Phase 3.2 Round 3

## 任务: pytest-asyncio 修复 + 覆盖率冲刺

### 背景
Round 2 评审发现：
1. **344 tests 失败**：`RuntimeError: This event loop is already running` - pytest-asyncio 配置问题
2. 整体覆盖率 68.3%，距80%差664行
3. core/task.py 和 core/ray_client.py 覆盖率低

### 具体任务

**1. 修复 pytest-asyncio event loop 问题**

检查 `pyproject.toml` 和 `conftest.py`：
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

确保所有 async fixture 正确定义 loop_scope。

**2. 添加 core/task.py 单元测试**

创建 `tests/unit/core/test_task.py`：
- 测试 TaskManager 生命周期
- 测试任务状态转换
- 测试 Ray 任务分发

**3. 添加 core/ray_client.py 单元测试**

创建 `tests/unit/core/test_ray_client.py`：
- 测试 Ray 连接
- 测试节点查询
- 测试任务提交

**4. audit.py 错误路径覆盖（仅9行）**

修改现有 test_audit.py 测试 mock 策略，测试 `_create_audit_log` 内部异常处理。

**5. 验证覆盖率**
```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ -v --cov=src.algo_studio --cov-report=term-missing
```

### 输出
完成后在 `talks/test-engineer-to-coordinator-round3-2026-03-29.md` 汇报：
- event loop 问题修复情况
- 新增测试数量
- 覆盖率提升结果
