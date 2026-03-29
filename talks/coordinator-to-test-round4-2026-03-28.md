# from: @coordinator
# to: @test-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 4

## 任务: P0 - pytest-asyncio 集成测试修复

### 背景
全量测试发现 237 个集成测试失败，错误: `RuntimeError: This event loop is already running`

问题原因:
- unit tests 在单独运行时 asyncio 配置有效
- 但 integration/e2e 测试运行时与 unit tests 冲突
- 需要对不同测试类型使用不同的 asyncio 配置

### 具体任务

1. **分析问题根源**
   ```bash
   PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_database_integration.py -v --tb=short 2>&1 | head -50
   ```

2. **修复方案**

   在 `pyproject.toml` 中添加针对 integration tests 的配置:
   ```toml
   [tool.pytest.ini_options]
   asyncio_mode = "auto"
   asyncio_default_fixture_loop_scope = "function"
   asyncio_mode_scope = "session"  # 新增: session 级别的 event loop
   ```

   或者为 integration tests 创建单独的 `pytest.ini`:
   ```ini
   [pytest]
   asyncio_mode = "strict"
   asyncio_default_fixture_loop_scope = "module"
   ```

3. **验证修复**
   ```bash
   # 测试 integration tests
   PYTHONPATH=src .venv/bin/python -m pytest tests/integration/ -v --tb=short -x

   # 测试全量 unit tests
   PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ -v --tb=short
   ```

4. **确认修复后测试数量**
   - integration tests: 应该通过
   - unit tests: 保持 510+ 通过
   - 全量: 目标 800+ 通过

### 输出
完成后在 `talks/test-engineer-to-coordinator-round4-2026-03-28.md` 汇报：
- 问题根源分析
- 修复方案
- 修复后的测试结果
