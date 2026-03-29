# from: @coordinator
# to: @test-engineer
# date: 2026-03-29
# type: task
# round: Phase 3.2 Round 1

## 任务: audit.py 认证 mock 重构 + tasks.py SSE 测试

### 背景
Phase 3.2 目标: 覆盖率 80%+

当前状态:
- audit.py: 36% (被 RBAC mock 阻塞)
- tasks.py: 20% (SSE 端点测试困难)

### 具体任务

**1. audit.py 认证 mock 重构**

创建 `tests/unit/api/routes/conftest.py`:
```python
import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def audit_auth_mock(mocker):
    """Mock RBAC auth for audit tests."""
    mock = mocker.patch('algo_studio.api.middleware.rbac.RBACMiddleware.verify_signature')
    mock.return_value = True
    mock_verify = mocker.patch('algo_studio.api.middleware.audit.AuditMiddleware.verify_signature')
    mock_verify.return_value = True
    yield

@pytest.fixture
def audit_app_state():
    """Clean app state between audit tests."""
    yield
    # Reset any audit state
```

**2. tasks.py SSE 端点测试**

创建 `tests/unit/api/routes/test_tasks_sse.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.fixture(autouse=True)
def cleanup_sse_state():
    """Clean SSE state between tests."""
    yield
    # Clear SSE progress store

@pytest.mark.asyncio
async def test_sse_progress_endpoint():
    """Test SSE progress endpoint."""
    # Test with mock SSE client
    pass
```

**3. 验证覆盖率提升**
```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/api/routes/test_audit.py -v --cov=src.algo_studio.api.routes.audit --cov-report=term-missing
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/api/routes/test_tasks.py -v --cov=src.algo_studio.api.routes.tasks --cov-report=term-missing
```

### 输出
完成后在 `talks/test-engineer-to-coordinator-round1-2026-03-29.md` 汇报：
- audit.py 覆盖率提升结果
- tasks.py 覆盖率提升结果
- 新增测试数量
