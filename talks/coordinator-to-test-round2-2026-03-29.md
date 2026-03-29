# from: @coordinator
# to: @test-engineer
# date: 2026-03-29
# type: task
# round: Phase 3.2 Round 2

## 任务: Scheduler 单元测试 + MockTask 修复

### 背景
评审发现 scheduler 模块（wfq_scheduler, tenant_queue, global_queue）覆盖率 0%，是整体覆盖率 80% 目标的主要差距。
同时发现 MockTask.status 返回 MagicMock 而非 TaskStatus 枚举。

### 具体任务

**1. 修复 MockTask.status 类型问题**

修改 `tests/unit/api/routes/conftest.py` 中的 MockTask：
```python
# 错误: 返回 MagicMock
@property
def status(self):
    return MagicMock(value=self._status)

# 正确: 返回实际 TaskStatus 枚举
@property
def status(self):
    return self._status  # 应该是 TaskStatus 枚举类型
```

**2. 添加 WFQScheduler 单元测试**

创建 `tests/unit/scheduler/test_wfq_scheduler.py`：
- 测试 VFT 计算
- 测试资源配额计算
- 测试多租户优先级

**3. 添加 TenantQueue 单元测试**

创建 `tests/unit/scheduler/test_tenant_queue.py`：
- 测试租户资源预留
- 测试公平份额计算

**4. 添加 GlobalSchedulerQueue 单元测试**

创建 `tests/unit/scheduler/test_global_scheduler_queue.py`：
- 测试全局队列管理
- 测试任务分发

**5. 增强 SSE generator 测试**

修改 `test_tasks_sse.py`，使用 `async for` 或 `anext()` 真正迭代 SSE generator。

**6. 验证覆盖率提升**
```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ -v --cov=src.algo_studio.core.scheduler --cov-report=term-missing
```

### 输出
完成后在 `talks/test-engineer-to-coordinator-round2-2026-03-29.md` 汇报：
- 各模块覆盖率提升结果
- 新增测试数量
- MockTask 修复确认
