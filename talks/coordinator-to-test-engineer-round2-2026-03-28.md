# from: @coordinator
# to: @test-engineer
# date: 2026-03-28
# type: task
# round: Phase 3 Round 2

## 任务: rollback.py SSH mock 测试

### 当前状态
- Round 1: 43 测试通过，覆盖率 38%
- rollback_id microsecond 修复已完成

### 待完成问题
| ID | 问题 | 严重性 |
|----|------|--------|
| P3-1 | SSH rollback methods 未测试 | High |

### 具体任务

为 `RollbackService` 的 SSH rollback 方法添加单元测试：

1. `_rollback_ray()` - mock `asyncssh.connect`，测试 ray stop
2. `_rollback_code()` - 测试代码回滚
3. `_rollback_deps()` - 测试依赖移除
4. `_rollback_venv()` - 测试 venv 移除
5. `_rollback_sudo()` - 测试 sudo 配置回滚
6. `_rollback_connecting()` - 测试连接回滚

### SSH Mock 方案
```python
from unittest.mock import AsyncMock, patch

# Mock asyncssh.connect
with patch('asyncssh.connect', new_callable=AsyncMock) as mock_connect:
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(return_value=MockResult(exit_status=0))
    mock_connect.return_value = mock_conn
    # 调用 rollback 方法
```

### 目标
- 新增 SSH mock 测试 15-20 个
- 覆盖率提升至 55%+

### 输出
完成后在 `talks/test-engineer-to-coordinator-round2-2026-03-28.md` 汇报：
- 新增测试数量
- 覆盖率变化
- 发现的问题