# AlgoStudio Phase 2 测试策略

**版本:** v1.0
**日期:** 2026-03-26
**状态:** 草稿
**负责人:** @test-engineer

---

## 1. 测试目标

| 目标 | 指标 |
|------|------|
| 单元测试覆盖率 | ≥ 80% |
| 功能测试用例数 | ≥ 100 个 |
| API 测试覆盖率 | ≥ 90% |
| 调度算法测试覆盖率 | ≥ 85% |
| CI 集成测试通过率 | 100% |

---

## 2. 测试框架

### 2.1 技术栈

| 工具 | 用途 | 版本要求 |
|------|------|----------|
| pytest | 测试框架 | ≥ 7.4.0 |
| pytest-asyncio | 异步测试 | ≥ 0.23.0 |
| pytest-cov | 覆盖率 | ≥ 4.1.0 |
| pytest-mock | Mock 测试 | ≥ 3.12.0 |
| factory-boy | 测试数据工厂 | ≥ 3.3.0 |
| Faker | 动态测试数据 | ≥ 22.0.0 |
| httpx | API 客户端 | ≥ 0.26.0 |

### 2.2 pytest 配置

```ini
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
```

### 2.3 覆盖率目标

```
Line Coverage:     80%
Branch Coverage:   75%
Function Coverage: 90%
```

---

## 3. 测试目录结构

```
tests/
├── conftest.py                 # 共享 fixtures 和配置
├── factories/                  # 测试数据工厂
│   ├── __init__.py
│   ├── task_factory.py
│   ├── node_factory.py
│   └── algorithm_factory.py
├── unit/                       # 单元测试
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── test_task.py
│   │   ├── test_task_manager.py
│   │   └── test_ray_client.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── test_models.py
│   │   ├── test_tasks_api.py
│   │   └── test_hosts_api.py
│   └── scheduler/
│       ├── __init__.py
│       ├── test_analyzers.py
│       ├── test_scorers.py
│       └── test_validators.py
├── integration/               # 集成测试
│   ├── __init__.py
│   ├── test_task_dispatch.py
│   └── test_scheduler_integration.py
├── api/                        # API 测试
│   ├── __init__.py
│   ├── test_tasks_endpoint.py
│   ├── test_hosts_endpoint.py
│   └── test_cluster_endpoint.py
├── e2e/                        # E2E 测试 (由 @qa 提供)
│   └── ...
└── reports/                    # 测试报告
    ├── coverage-html/
    └── coverage.xml
```

---

## 4. 测试策略

### 4.1 单元测试策略

**目标:** 每个模块独立测试，Mock 所有外部依赖

| 模块 | 测试重点 | Mock 对象 |
|------|----------|-----------|
| core/task | Task dataclass, TaskManager CRUD | Ray actors |
| core/ray_client | 节点查询，任务提交 | ray, NodeMonitorActor |
| api/routes | HTTP 请求/响应 | FastAPI app |
| scheduler | 调度算法 | LLM provider, node scorer |

**原则:**
- 每个测试只验证一个功能点
- 使用 fixtures 提供测试数据
- 使用 `pytest-mock` 进行依赖隔离
- 覆盖率 ≥ 80%

### 4.2 集成测试策略

**目标:** 验证模块间交互

| 测试场景 | 涉及模块 |
|----------|----------|
| 任务创建→调度 | API → TaskManager → RayClient |
| 进度更新流程 | ProgressReporter → ProgressStore |
| 调度决策流程 | TaskAnalyzer → NodeScorer → Router |

**原则:**
- 使用真实组件替代 Mock
- 在测试环境启动完整的 Ray 集群
- 测试后清理所有资源

### 4.3 API 测试策略

**目标:** 验证 HTTP 端点行为

| 端点 | 测试用例数 |
|------|------------|
| POST /api/tasks | 5+ |
| GET /api/tasks | 3+ |
| GET /api/tasks/{task_id} | 5+ |
| POST /api/tasks/{task_id}/dispatch | 3+ |
| GET /api/hosts | 3+ |

**原则:**
- 使用 `httpx.AsyncClient` 进行测试
- 验证状态码、响应结构、错误处理
- 测试参数验证和边界条件

### 4.4 Mock 测试策略

**目标:** 隔离被测模块，模拟外部依赖

```python
# 示例: Mock Ray Client
@pytest.fixture
def mock_ray_client():
    mock = MagicMock(spec=RayClient)
    mock.get_nodes.return_value = [mock_node()]
    return mock

def test_task_dispatch(mock_ray_client, mock_task_manager):
    manager = mock_task_manager
    manager.dispatch_task("task-001", mock_ray_client)
    mock_ray_client.submit_task.assert_called_once()
```

**Mock 层级:**
1. **单元测试:** Mock 所有外部依赖（Ray, Redis, FileSystem）
2. **集成测试:** Mock 外部服务（LLM Provider），使用真实内部组件
3. **E2E 测试:** 无 Mock，使用真实环境

---

## 5. 测试数据管理

### 5.1 Factory Pattern

使用 `factory-boy` + `Faker` 生成测试数据:

```python
# factories/task_factory.py
import factory
from faker import Faker

fake = Faker()

class TaskFactory(factory.Factory):
    class Meta:
        model = dict

    task_id = factory.LazyFunction(lambda: f"task-{fake.uuid4()}")
    task_type = factory.Faker("random_element", elements=["train", "infer", "verify"])
    algorithm_name = "simple_classifier"
    algorithm_version = "v1"
    status = "pending"
```

### 5.2 Fixture 管理

```python
# conftest.py
@pytest.fixture
def sample_task_data(task_factory):
    return task_factory.create(task_id="test-001")

@pytest.fixture
def sample_tasks_list(task_factory):
    return [task_factory.create() for _ in range(5)]
```

---

## 6. 测试用例设计

### 6.1 Task 单元测试 (10+)

```python
# tests/unit/core/test_task.py

def test_task_creation():
    """验证 Task 创建"""

def test_task_status_transitions():
    """验证任务状态转换"""

def test_task_manager_create():
    """验证 TaskManager.create_task"""

def test_task_manager_get():
    """验证 TaskManager.get_task"""

def test_task_manager_list():
    """验证 TaskManager.list_tasks with filtering"""

def test_task_manager_update_status():
    """验证状态更新"""

def test_task_progress_update():
    """验证进度更新"""

def test_task_timestamps():
    """验证时间戳自动设置"""

def test_task_dispatch_no_idle_nodes():
    """验证无可用节点时的处理"""

def test_task_result_storage():
    """验证结果存储"""
```

### 6.2 API 测试 (10+)

```python
# tests/api/test_tasks_endpoint.py

@pytest.mark.asyncio
async def test_create_task_success():
    """创建任务成功"""

@pytest.mark.asyncio
async def test_create_task_invalid_type():
    """无效任务类型"""

@pytest.mark.asyncio
async def test_list_tasks_empty():
    """空列表"""

@pytest.mark.asyncio
async def test_list_tasks_with_filter():
    """状态过滤"""

@pytest.mark.asyncio
async def test_get_task_found():
    """获取存在的任务"""

@pytest.mark.asyncio
async def test_get_task_not_found():
    """任务不存在"""

@pytest.mark.asyncio
async def test_dispatch_task_success():
    """分发成功"""

@pytest.mark.asyncio
async def test_dispatch_task_already_dispatched():
    """重复分发"""
```

### 6.3 调度算法测试 (10+)

```python
# tests/unit/scheduler/test_fast_scheduler.py

def test_fast_path_decision():
    """Fast Path 决策"""

def test_node_selection_by_score():
    """节点评分选择"""

def test_resource_validation():
    """资源验证"""

def test_quota_check():
    """配额检查"""

def test_priority_ordering():
    """优先级排序"""
```

### 6.4 SSH 部署测试 (5+)

```python
# tests/integration/test_ssh_deploy.py

@pytest.mark.asyncio
async def test_ssh_connect():
    """SSH 连接"""

@pytest.mark.asyncio
async def test_deploy_worker_node():
    """部署 Worker 节点"""

@pytest.mark.asyncio
async def test_deploy_failure_handling():
    """部署失败处理"""
```

---

## 7. CI/CD 集成

### 7.1 GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      - name: Run unit tests
        run: |
          pytest tests/unit -v --cov=src/algo_studio --cov-report=xml

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v4
      - name: Set up Ray
        uses: ./.github/actions/setup-ray
      - name: Run integration tests
        run: |
          pytest tests/integration -v
```

### 7.2 测试报告

- **Coverage:** XML 格式上传到 Codecov
- **HTML Report:** 保存在 `tests/reports/coverage-html/`
- **Test Results:** 保存在 `tests/reports/`

---

## 8. 执行计划

| 阶段 | 时间 | 任务 |
|------|------|------|
| Phase 2 R1 | Week 1 | 测试框架搭建、策略设计、初步测试用例 |
| Phase 2 R2 | Week 2 | 单元测试完善、API 测试 |
| Phase 2 R3 | Week 3-4 | 集成测试、E2E 测试 |
| Phase 2 R4 | Week 5-6 | 性能测试、回归测试 |

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Ray 集群环境不稳定 | 测试失败 | 使用 Mock，隔离外部依赖 |
| 测试数据生成复杂 | 开发延迟 | 使用 Factory Pattern 简化 |
| 覆盖率目标过高 | 无法达成 | 分阶段目标，逐步提高 |

---

**文档状态:** 草稿，待评审
**下次评审:** 2026-03-27
