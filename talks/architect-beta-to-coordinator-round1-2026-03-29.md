# Phase 3.2 Round 1 API/安全架构评审报告

**评审人**: @architect-beta
**日期**: 2026-03-29
**评审内容**: SSE 测试 + Sentinel 配置 + 故障转移脚本

---

## 评审结论

| 评审项 | 状态 | 优先级 |
|--------|------|--------|
| SSE 测试 mock 策略 | 有条件通过 | 需修复 |
| Audit mock 覆盖率 | 有条件通过 | 需补充 |
| Sentinel 配置 | 通过 | - |
| 故障转移脚本 | 有条件通过 | 需改进 |

---

## 1. SSE 测试评审 (test_tasks_sse.py)

### 优点

1. **Mock 结构合理**: 使用 `patch('algo_studio.api.routes.tasks.task_manager')` 和 `patch('algo_studio.api.routes.tasks.get_progress_store')` 正确隔离了依赖
2. **超时处理正确**: 使用 `asyncio.wait_for` 处理 SSE 流挂起问题
3. **清理机制完善**: `cleanup_sse_state` fixture 正确清理 `TaskManager._instances`
4. **事件格式验证**: `TestSSEEventFormat` 类验证了 JSON 序列化格式

### 问题 (需要修复)

#### 问题 1: MockTask 的 status 比较不匹配实际实现 [重要]

**位置**: `test_tasks_sse.py` 第 84-111 行

**问题描述**:
`MockTask.status` 返回 `MagicMock(value=self._status)`，但实际代码 (`tasks.py` 第 232 行) 使用:
```python
if current_task.status == TaskStatus.COMPLETED:
```

而 `TaskStatus.COMPLETED` 是枚举值，不是字符串。MagicMock 的比较会失败。

**实际代码期望**:
```python
# tasks.py line 232
if current_task.status == TaskStatus.COMPLETED:  # 需要 .value 或枚举比较

# tasks.py line 261
"status": current_task.status.value,  # 使用 .value 属性
```

**建议修复**:
```python
class MockTask:
    def __init__(self, task_id="test-task-123", task_type="train",
                 status="pending", progress=0, error=None):
        from algo_studio.core.task import TaskStatus
        self._status = TaskStatus(status) if isinstance(status, str) else status
        self._task_type = task_type

    @property
    def status(self):
        return self._status  # 返回实际的 TaskStatus 枚举

    @property
    def task_type(self):
        return self._task_type
```

#### 问题 2: 测试未验证 SSE 事件实际输出 [中等]

**位置**: `TestSSEProgressGenerator` 类

**问题描述**:
测试只检查 `assert generator is not None`，没有验证实际生成的 SSE 事件格式。

`TestSSEEventFormat` 只测试 JSON 序列化，不是真正的 SSE 事件验证。

**建议补充**:
```python
async def test_progress_generator_yields_completed_event(self):
    """Test that progress generator yields completed event for completed tasks."""
    # ... existing setup ...

    # 实际调用 generator 并验证事件
    events = []
    async for event in generator:
        events.append(event)
        if event.get("event") == "completed":
            break

    assert len(events) > 0
    assert events[0]["event"] == "completed"
    assert "task_id" in events[0]["data"]
```

#### 问题 3: `mock_progress_store.get.remote` 签名不匹配 [轻微]

**位置**: 第 151-152 行

**问题描述**:
```python
mock_store_instance.get.remote = AsyncMock(return_value=0)
```

实际代码调用: `ray.get(progress_store.get.remote(task_id))`，所以 `get.remote` 实际上是一个不需要参数的函数（task_id 在创建 remote 时绑定）。

这在当前测试中可以工作，但不够准确。

---

## 2. Audit Mock 覆盖率评审 (test_audit.py)

### 优点

1. **Mock 方法正确**: 使用 `patch.object(AuditMiddleware, '_create_audit_log', new_callable=AsyncMock)` 正确隔离了数据库写入
2. **覆盖完整**: 测试了公共路由排除、API 请求记录、匿名用户、资源 ID 解析等
3. **SSE 排除验证**: `test_sse_progress_not_logged` 正确验证了 SSE 端点被排除

### 覆盖缺口

#### 缺口 1: 认证失败路径的 Audit 记录 [重要]

**缺失测试**:
- 无效签名 (401 INVALID_SIGNATURE) 是否有 audit 记录?
- 缺失 user_id (401 UNAUTHORIZED) 是否有 audit 记录?
- 超时 timestamp ( replay attack 防护) 是否有记录?

**建议补充**:
```python
async def test_auth_failure_logged(self):
    """Test that authentication failures are logged."""
    with patch.object(AuditMiddleware, '_create_audit_log', new_callable=AsyncMock) as mock_log:
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        # Invalid signature
        response = await client.get(
            "/api/tasks",
            headers={"X-User-ID": "test", "X-Signature": "invalid", "X-Timestamp": "123"}
        )
        assert response.status_code == 401
        # Should still log the attempt for security auditing
        mock_log.assert_called_once()
```

#### 缺口 2: 403 Permission Denied 的 Audit 记录 [中等]

**建议补充**:
```python
async def test_permission_denied_logged(self):
    """Test that permission denied responses are logged."""
    # viewer role trying to delete task (requires developer+)
```

---

## 3. Sentinel 配置评审

### 评审结果: 通过

**配置文件**: `configs/sentinel/sentinel-26380.conf`

| 配置项 | 值 | 评估 |
|--------|-----|------|
| `sentinel monitor mymaster 192.168.0.126 6380 2` | quorum=2 | 正确 (需要 2 票才failover) |
| `down-after-milliseconds` | 5000ms | 合理 (5秒超时) |
| `failover-timeout` | 10000ms | 合理 |
| `parallel-syncs` | 1 | 正确 (避免新master过载) |
| `deny-scripts-reconfig` | yes | 良好安全实践 |
| `protected-mode` | no | 合理 (bind 0.0.0.0 需要) |
| `bind` | 0.0.0.0 | 需确认网络访问控制 |

### 安全建议

1. **认证**: 建议启用 `sentinel auth-pass` 如果 master 需要密码
2. **网络隔离**: `bind 0.0.0.0` 应配合防火墙规则

---

## 4. 故障转移脚本评审

### 评审结果: 有条件通过 (需改进)

**脚本**: `scripts/test_sentinel_failover.sh`

### 问题 1: DEBUG SLEEP 使用警告 [安全]

第 97-98 行:
```bash
redis-cli -p $MASTER_PORT DEBUG SLEEP $sleep_duration &
```

`DEBUG SLEEP` 是 Redis 调试命令，在生产环境禁用。当前脚本头部有警告这是正确的。

**建议**: 添加环境检查，只允许在非生产环境运行:
```bash
if [ "$REDIS_ENV" = "production" ]; then
    log_error "Cannot run failover simulation in production!"
    exit 1
fi
```

### 问题 2: 缺少自动验证断言 [功能]

脚本只输出信息，不验证 failover 是否成功。

**建议**:
```bash
# 在 simulate_master_failure 后验证
expected_master=$(redis-cli -p $SENTINEL_PORT SENTINEL get-master-addr-by-name mymaster)
if [ "$expected_master" != "$OLD_MASTER" ]; then
    log_info "Failover successful: new master at $expected_master"
else
    log_error "Failover failed: master unchanged"
fi
```

---

## 5. API 测试覆盖率评估

### 覆盖率提升

Phase 3.2 Round 1 新增:
- `test_tasks_sse.py`: 15 个 SSE 相关测试
- `test_audit.py`: 已存在，覆盖 audit middleware

### 覆盖率缺口

1. **SSE 端点认证路径**: 需要测试不同角色 (viewer/developer/admin) 的 SSE 访问
2. **并发 SSE 连接**: 多客户端同时连接的压力测试
3. **SSE 重连机制**: 客户端断线重连的场景

---

## 总结

**必须修复** (阻塞问题):
1. `MockTask.status` 返回值必须匹配实际 `TaskStatus` 枚举类型

**建议修复** (质量提升):
2. SSE 测试应验证实际事件输出，不只是 `is not None`
3. Audit 测试应补充认证失败路径的覆盖

**可选改进** (长期):
4. 故障转移脚本添加自动验证断言

**整体评估**: 代码质量良好，mock 策略基本正确，但存在与实际枚举类型不匹配的潜在问题需要修复。
