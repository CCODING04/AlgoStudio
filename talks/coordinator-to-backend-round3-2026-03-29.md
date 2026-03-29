# from: @coordinator
# to: @backend-engineer
# date: 2026-03-29
# type: task
# round: Phase 3.2 Round 3

## 任务: core/task.py 和 core/ray_client.py 辅助测试

### 背景
覆盖率冲刺阶段，需要为 core/task.py 和 core/ray_client.py 添加测试。

### 具体任务

**1. 分析 core/task.py**

查看 `src/algo_studio/core/task.py`：
- TaskManager 类结构
- 任务状态机
- Ray 任务分发逻辑

**2. 分析 core/ray_client.py**

查看 `src/algo_studio/core/ray_client.py`：
- Ray 连接管理
- 节点查询接口
- 任务提交接口

**3. 编写测试助手**

创建 `tests/unit/core/conftest.py`：
```python
import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def mock_ray_client():
    client = MagicMock()
    client.nodes = MagicMock(return_value=[])
    return client
```

### 输出
完成后在 `talks/backend-to-coordinator-round3-2026-03-29.md` 汇报分析结果。
