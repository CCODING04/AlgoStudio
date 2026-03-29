# from: @coordinator
# to: @test-engineer
# date: 2026-03-29
# type: task
# round: Phase 3.2 Round 5

## 任务: agentic_scheduler Deep Path + auth.py RBAC 测试

### 背景
Round 4 成果：68% 覆盖率（超预期）
Round 5 目标：72%

**api/auth.py 当前 0% 覆盖，是明显短板**

### 具体任务

**1. agentic_scheduler Deep Path 测试**

创建 `tests/unit/scheduler/test_agentic_scheduler_deep_path.py`：
- 测试 LLM 调用路径（使用 mock）
- 测试 Deep Path 决策逻辑
- 测试 Claude API 集成

使用 mock 隔离外部依赖：
```python
@pytest.fixture
def mock_anthropic_provider():
    with patch('algo_studio.core.scheduler.agents.llm.AnthropicProvider') as mock:
        mock.return_value.messages.create.return_value = MagicMock(
            content=[MagicMock(text="decision_result")]
        )
        yield mock
```

**2. api/auth.py RBAC 测试**

创建 `tests/unit/api/test_auth.py`：
- 测试 RBACMiddleware
- 测试权限检查
- 测试认证流程

**3. 验证覆盖率**
```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ -v --cov=src.algo_studio --cov-report=term-missing
```

### 输出
完成后在 `talks/test-engineer-to-coordinator-round5-2026-03-29.md` 汇报：
- 各模块覆盖率
- 与72%目标的差距
