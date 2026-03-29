# from: @coordinator
# to: @test-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 2

## 任务: P0 - 修复 pytest-asyncio 配置 + 启用分支覆盖

### 背景
Round 1 分析发现 221 个测试失败 (RuntimeError: This event loop is already running)
这是阻塞性问题，必须立即修复。

### 具体任务

1. **修复 pytest-asyncio 配置**

   在 `pytest.ini` 或 `pyproject.toml` 中配置:
   ```ini
   [pytest]
   asyncio_mode = auto
   asyncio_default_fixture_loop_scope = function
   ```

   或在 `pyproject.toml` 中:
   ```toml
   [tool.pytest.ini_options]
   asyncio_mode = "auto"
   asyncio_default_fixture_loop_scope = "function"
   ```

2. **启用分支覆盖**

   在 `pyproject.toml` 中:
   ```toml
   [tool.coverage.run]
   branch = true
   ```

3. **验证修复**
   ```bash
   PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ -v --tb=short -x
   ```
   确认失败数从 221 减少到 0 或极少数

4. **更新测试覆盖率基线**
   - 运行完整覆盖率报告
   - 确认分支覆盖已启用

### 输出
完成后在 `talks/test-engineer-to-coordinator-round2-2026-03-28.md` 汇报：
- pytest-asyncio 修复结果
- 分支覆盖启用结果
- 修复后的测试通过数
