# M5: 集成测试策略文档

**创建日期:** 2026-03-26
**角色:** QA Engineer
**状态:** 准备阶段完成

---

## 1. 测试策略概述

### 1.1 测试分层

```
┌─────────────────────────────────────────────────────────────┐
│                    端到端测试 (E2E)                          │
│         - 真实 Ray 集群集成测试                               │
│         - 跨模块数据流验证                                   │
├─────────────────────────────────────────────────────────────┤
│                    集成测试 (Integration)                    │
│         - API 端点测试 (FastAPI + AsyncClient)               │
│         - Scheduler 与 RayClient 集成                       │
│         - TaskManager 与 AgenticScheduler 集成               │
├─────────────────────────────────────────────────────────────┤
│                    单元测试 (Unit)                           │
│         - M2: RayAPIClient, CircuitBreaker, Cache           │
│         - M3: TaskAnalyzer, NodeScorer, Router, Validator  │
│         - M3: FastPathScheduler, AgenticScheduler            │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 测试覆盖率目标

| 模块 | 当前状态 | 覆盖率目标 |
|------|----------|------------|
| M2 Ray Dashboard API | 29 tests | 80% |
| M3 Agentic Fast Path | 74 tests | 80% |
| M4 Deep Path (LLM) | Pending | 70% |
| M1 Storage | Pending (Infra) | 60% |
| 集成测试 | Pending | 50% |

---

## 2. 已完成测试

### 2.1 M2 - Ray Dashboard API 测试 (`test_ray_dashboard_client.py`)

| 测试类 | 测试数量 | 覆盖范围 |
|--------|----------|----------|
| `TestRayAPIClient` | 24 | 初始化、缓存、熔断器、HTTP 请求 |
| `TestRayAPIResponse` | 3 | 响应格式 |

**关键测试用例:**
- `test_cache_hit` / `test_cache_miss` - 缓存功能
- `test_circuit_breaker_opens_after_threshold` - 熔断器打开
- `test_circuit_breaker_half_open_after_timeout` - 熔断器恢复
- `test_make_request_retries_on_timeout` - 重试机制
- `test_make_request_caches_result` - 缓存命中

### 2.2 M3 - Agentic Scheduler 测试

| 测试文件 | 测试数量 | 覆盖范围 |
|----------|----------|----------|
| `test_task_analyzer.py` | 17 | 任务分析、资源提取 |
| `test_node_scorer.py` | 13 | 多维度节点评分 |
| `test_router.py` | 14 | Fast/Deep 路径路由 |
| `test_resource_validator.py` | 13 | 资源安全验证 |
| `test_fast_scheduler.py` | 9 | Fast Path 调度 |
| `test_agentic_scheduler.py` | 7 | 调度器门面 |

**关键测试用例:**

1. **TaskAnalyzer:**
   - `test_analyze_train_task_defaults` - 训练任务默认资源
   - `test_analyze_with_batch_size_memory_scaling` - 批大小影响内存
   - `test_complexity_calculation_complex_task` - 复杂度计算

2. **NodeScorer:**
   - `test_score_single_idle_gpu_node` - 空闲 GPU 节点评分
   - `test_score_preferred_node_match` - 亲和性匹配
   - `test_score_multiple_nodes_sorted_by_score` - 多节点排序

3. **Router:**
   - `test_high_load_with_long_queue_uses_deep_path` - 高负载触发 Deep Path
   - `test_preferred_nodes_uses_deep_path` - 亲和性触发 Deep Path

4. **FastPathScheduler:**
   - `test_schedule_selects_best_node` - 选择最优节点
   - `test_schedule_offline_nodes_skipped` - 跳过离线节点

5. **ResourceValidator:**
   - `test_validate_insufficient_gpu` - GPU 不足验证
   - `test_validate_gpu_overcommit_allowed` - GPU 超配验证

---

## 3. 测试执行指南

### 3.1 运行所有测试

```bash
# 设置 PYTHONPATH
export PYTHONPATH=src

# 运行所有测试
.venv/bin/python -m pytest tests/ -v

# 运行 M2 测试
.venv/bin/python -m pytest tests/test_ray_dashboard_client.py -v

# 运行 M3 测试
.venv/bin/python -m pytest tests/test_scheduler/ -v
```

### 3.2 运行特定测试

```bash
# 运行单个测试文件
.venv/bin/python -m pytest tests/test_scheduler/test_task_analyzer.py -v

# 运行单个测试用例
.venv/bin/python -m pytest tests/test_scheduler/test_task_analyzer.py::TestDefaultTaskAnalyzer::test_analyze_train_task_defaults -v

# 运行带标记的测试
.venv/bin/python -m pytest tests/ -m "not slow" -v
```

---

## 4. 待完成测试

### 4.1 API 集成测试 (`test_api_cluster.py`)

```python
# 待实现 - 测试集群 API 端点
async def test_cluster_status_endpoint():
    """测试 /api/cluster/status 端点"""

async def test_cluster_nodes_endpoint():
    """测试 /api/cluster/nodes 端点"""

async def test_cluster_health_endpoint():
    """测试 /api/cluster/health 端点"""

async def test_cluster_events_endpoint():
    """测试 /api/cluster/events SSE 端点"""
```

### 4.2 Agentic 集成测试

```python
# 待实现 - 测试 AgenticScheduler 完整流程
def test_agentic_schedule_end_to_end():
    """测试完整调度流程"""

def test_agentic_fallback_to_fast_path():
    """测试 Deep Path 降级到 Fast Path"""

def test_agentic_validation_fallback():
    """测试验证失败后的备选节点选择"""
```

### 4.3 E2E 测试

```python
# 待实现 - 端到端测试（需要真实 Ray 集群）
@pytest.mark.integration
def test_task_lifecycle():
    """测试任务完整生命周期"""

@pytest.mark.integration
def test_scheduler_with_real_ray_cluster():
    """测试调度器与真实 Ray 集群集成"""
```

---

## 5. Mock 使用策略

### 5.1 Ray Client Mock

```python
# 使用 MagicMock 模拟 RayClient
mock_client = MagicMock(spec=RayClient)
mock_client.get_nodes.return_value = [create_test_node()]
```

### 5.2 Ray API Mock

```python
# 使用 responses 或 unittest.mock 模拟 HTTP 请求
@patch('requests.request')
def test_api_with_mock(mock_request):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"nodes": []}
    mock_request.return_value = mock_response
```

---

## 6. 测试数据

### 6.1 测试节点

```python
def create_test_node(
    hostname="worker-1",
    status="idle",
    gpu_available=1,
    memory_available_gb=16,
):
    """创建测试用 NodeStatus"""
    return NodeStatus(
        node_id="node-1",
        ip="192.168.0.101",
        hostname=hostname,
        status=status,
        cpu_used=8,
        cpu_total=24,
        gpu_used=0,
        gpu_total=gpu_available,
        memory_used_gb=16,
        memory_total_gb=memory_available_gb + 16,
        disk_used_gb=100,
        disk_total_gb=500,
    )
```

### 6.2 测试任务

```python
def create_test_task(
    task_type=TaskType.TRAIN,
    config=None,
):
    """创建测试用 Task"""
    return Task(
        task_id="test-task-001",
        task_type=task_type,
        algorithm_name="test_algo",
        algorithm_version="v1",
        config=config or {},
    )
```

---

## 7. 持续集成

### 7.1 GitHub Actions 配置

```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-asyncio
      - name: Run tests
        run: |
          PYTHONPATH=src pytest tests/ -v --ignore=tests/test_integration.py
```

---

## 8. 问题跟踪

### 8.1 已知问题

| 问题 | 状态 | 说明 |
|------|------|------|
| `test_host_info_dataclass` 失败 | 已知 | HostInfo 参数不匹配，需要更新测试 |
| SSE 端点需要 `sse-starlette` | 已知 | 可选依赖 |

### 8.2 待决策

| 问题 | 说明 |
|------|------|
| M4 Deep Path LLM 测试 | 等待 LLM 集成完成 |
| M1 Storage 测试 | 等待基础设施部署 |

---

**下一步:**
1. 实现 API 集成测试 (`test_api_cluster.py`)
2. 实现 Agentic 集成测试
3. M4 Deep Path LLM 测试（等待 M4 完成）
4. E2E 测试脚本
