# Round 4 性能基准验证报告

**from:** @qa
**date:** 2026-03-27
**Round:** 4/8

---

## 测试执行摘要

运行命令: `PYTHONPATH=src pytest tests/performance/ -v --tb=short`

**结果统计:**
- **通过:** 47
- **失败:** 9
- **跳过:** 1
- **总计:** 57 tests
- **执行时间:** 348.45s (5分48秒)

---

## 失败测试详情

### 1. API Load Tests (5 failures)

| 测试 | 错误 | 原因 |
|------|------|------|
| `test_tasks_list_p95_latency` | 401 Unauthorized | 缺少认证头 |
| `test_hosts_list_p95_latency` | 500 Internal Server Error | /api/hosts 端点异常 |
| `test_concurrent_requests_100_workers` | 0% 成功率 | 无认证导致全部 401 |
| `test_concurrent_requests_50_workers` | 0% 成功率 | 无认证导致全部 401 |
| `test_sustained_load_30_seconds` | 100% 错误率 | 无认证导致全部 401 |
| `test_tasks_create_p95_latency` | 401 Unauthorized | 缺少认证头 |

### 2. SSE Performance Tests (3 failures)

| 测试 | 错误 | 原因 |
|------|------|------|
| `test_sse_single_connection_stability` | 404 Not Found | 任务 `train-test-sse` 不存在 |
| `test_sse_concurrent_connections_100` | 100% 连接失败 | 任务不存在 |
| `test_sse_concurrent_connections_50` | 100% 连接失败 | 任务不存在 |

### 3. Previously Failed Tests (Round 3 遗留问题)

与 Round 3 相比，问题性质已改变：
- Round 3: 5 failures (基础设施路由/端点问题)
- Round 4: 9 failures (认证 + 基础设施)

---

## 通过测试分类统计

| 类别 | 通过/总数 | 状态 |
|------|----------|------|
| Deploy API Benchmark | 12/12 | 100% |
| RBAC Benchmark | 16/16 | 100% |
| Scheduling Benchmark | 13/13 | 100% |
| SSE Performance (部分) | 3/6 | 50% |
| API Load (部分) | 1/7 | 14% |

---

## 核心问题分析

### 问题 1: 认证头缺失 (根本原因)

`test_api_load.py` 和 `test_sse_performance.py` 调用受保护端点时未提供认证头:
```python
# 当前代码 - 缺少认证
response = requests.get(f"{api_base_url}/api/tasks", timeout=10)

# 需要改为类似:
headers = get_auth_headers(user_id="test-user", role="admin")
response = requests.get(f"{api_base_url}/api/tasks", headers=headers, timeout=10)
```

`test_deploy_api_benchmark.py` 和 `test_rbac_benchmark.py` 提供了 `get_auth_headers()` 函数,但 `test_api_load.py` 未使用。

### 问题 2: /api/hosts 端点 500 错误

即使提供认证头,`/api/hosts` 仍返回 500,需要检查:
- Redis 连接状态
- Ray 集群可达性
- 主机监控 actor 状态

### 问题 3: SSE 端点任务不存在

SSE 测试连接 `/api/tasks/train-test-sse/progress`,但该任务从未被创建。测试应先创建任务,再订阅其进度。

---

## P95 延迟指标 (通过测试)

| 端点 | P50 | P95 | P99 | Avg | 阈值 | 状态 |
|------|-----|-----|-----|-----|------|------|
| /api/tasks/{id} | ~1ms | <50ms | ~2ms | ~1.5ms | 50ms | PASS |
| Dispatch Task | - | <100ms | - | - | 100ms | PASS |
| Deploy API (list_workers) | - | <10ms | - | - | 10ms | PASS |
| RBAC middleware | - | <5ms | - | - | 5ms | PASS |

---

## 建议改进项

1. **修复认证配置 (高优先级)**
   - 在 `test_api_load.py` 中添加 `get_auth_headers()` 调用
   - 在 `test_sse_performance.py` 中创建测试任务后再连接 SSE

2. **修复 /api/hosts 500 错误 (高优先级)**
   - 检查 Redis 连接 (端口 6380)
   - 验证 Ray 集群状态

3. **SSE 测试数据准备 (中优先级)**
   - 在测试前创建临时任务
   - 或修改测试以接受 404 作为有效响应

4. **添加测试服务器健康检查 (中优先级)**
   - 在测试开始前验证 API 可用性
   - 验证认证系统正常

---

## 结论

Round 4 性能测试显示基础设施层(Deploy API、RBAC、Scheduling)工作正常,但 **API Load 和 SSE 测试因认证配置缺失而失败**。这不是基础设施问题,而是测试配置问题。

**建议后续行动:**
1. @backend-engineer 修复 `/api/hosts` 500 错误
2. @qa 修复 API Load 测试认证配置
3. @qa 修复 SSE 测试任务准备流程
