# Phase 2 测试工具配置

**版本:** v1.0
**创建日期:** 2026-03-26
**角色:** QA Engineer

---

## 1. 工具选型

| 工具 | 用途 | 版本 | 状态 |
|------|------|------|------|
| Playwright | E2E 测试 | >= 1.40 | 推荐 |
| Locust | 压力测试 | >= 2.15 | 推荐 |
| Allure | 测试报告 | >= 2.20 | 已配置 |
| pytest | 测试运行器 | >= 7.0 | 已安装 |

---

## 2. Playwright 配置

### 2.1 安装

```bash
cd /home/admin02/Code/Dev/AlgoStudio
uv pip install playwright
playwright install chromium
```

### 2.2 Playwright 配置 (playwright.config.py)

**注意:** Round 2 修复了配置不一致问题 - 统一使用 Python Playwright，不再使用 TypeScript 配置。

```python
# tests/e2e/playwright.config.py
"""
Playwright configuration for AlgoStudio E2E tests.

All E2E tests use Python Playwright (playwright.sync_api).
This replaces the previous TypeScript playwright.config.ts.
"""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright
import pytest

TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent.parent

# Environment variables with defaults
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "http://localhost:3000")
RAY_ADDRESS = os.getenv("RAY_ADDRESS", "192.168.0.126:6379")

IS_CI = os.getenv("CI", "").lower() in ("true", "1", "yes")


def get_playwright_config() -> dict:
    """Returns unified Python-based Playwright configuration."""
    return {
        "test_dir": str(TEST_DIR),
        "fully_parallel": not IS_CI,
        "forbid_only": IS_CI,
        "retries": 2 if IS_CI else 1,
        "workers": 1 if IS_CI else None,
        "timeout": 30000,
        "headless": True,
        "screenshot": "only-on-failure" if not IS_CI else "always",
        "video": "retain-on-failure" if not IS_CI else "off",
        "trace": "on-first-retry" if not IS_CI else "off",
        "base_url": WEB_BASE_URL,
        "api_base_url": API_BASE_URL,
        "ray_address": RAY_ADDRESS,
    }


# Pytest markers
def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: end-to-end tests")
    config.addinivalue_line("markers", "cluster: cluster tests")
    config.addinivalue_line("markers", "web: web console tests")
    config.addinivalue_line("markers", "mock: tests using mocks")
```

### 2.3 Page Object 示例

```python
# tests/e2e/pages/tasks_page.py
from playwright.sync_api import Page, expect

class TasksPage:
    def __init__(self, page: Page):
        self.page = page
        self.url = "/tasks"

    def goto(self):
        self.page.goto(f"{self.page.context.base_url}{self.url}")

    def click_new_task(self):
        self.page.get_by_role("button", name="新建任务").click()

    def select_algorithm(self, name: str, version: str):
        self.page.get_by_label("算法").select_option(f"{name}:{version}")

    def submit_task(self):
        self.page.get_by_role("button", name="提交").click()

    def wait_for_task_status(self, task_id: str, status: str):
        expect(self.page.locator(f"[data-task-id={task_id}]")).to_have_attribute("data-status", status)
```

---

## 3. Locust 配置

### 3.1 安装

```bash
uv pip install locust
```

### 3.2 Locust 配置 (locustfile.py)

```python
# tests/stress/locustfile.py
from locust import HttpUser, task, between, events
import json

class AlgoStudioUser(HttpUser):
    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        """初始化测试用户"""
        self.headers = {"X-API-Key": "test-api-key"}

    @task(3)
    def list_tasks(self):
        """获取任务列表"""
        self.client.get("/api/tasks", headers=self.headers)

    @task(2)
    def get_hosts(self):
        """获取主机列表"""
        self.client.get("/api/hosts", headers=self.headers)

    @task(1)
    def create_task(self):
        """创建训练任务"""
        self.client.post(
            "/api/tasks",
            headers=self.headers,
            json={
                "task_type": "train",
                "algorithm_name": "simple_classifier",
                "algorithm_version": "v1",
                "config": {"epochs": 1}
            }
        )

    @task(1)
    def get_task_status(self):
        """获取任务状态"""
        self.client.get("/api/tasks/train-test-001", headers=self.headers)
```

### 3.3 运行 Locust

```bash
# 单节点模式
locust -f tests/stress/locustfile.py --headless

# 分布式模式
locust -f tests/stress/locustfile.py --master
locust -f tests/stress/locustfile.py --worker
```

---

## 4. Allure 配置

### 4.1 安装

```bash
uv pip install allure-pytest
```

### 4.2 运行测试生成报告

```bash
# 运行测试
PYTHONPATH=src pytest tests/e2e/ --alluredir=tests/reports/allure-results

# 生成 HTML 报告
allure serve tests/reports/allure-results

# 生成静态报告
allure generate tests/reports/allure-results -o tests/reports/allure-report
```

---

## 5. pytest 配置

### 5.1 pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
markers =
    e2e: end-to-end tests
    stress: stress tests
    slow: slow running tests
```

### 5.2 conftest.py 示例 (Round 2 更新)

```python
# tests/e2e/conftest.py
"""
Pytest configuration and shared fixtures for AlgoStudio E2E tests.

Includes:
- Playwright browser/page fixtures
- SSE mock server for CI environments
- Ray cluster mocks
"""

import pytest
import os
import threading
import time
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

# CI environment detection
IS_CI = os.getenv("CI", "").lower() in ("true", "1", "yes")


# SSE Mock Server for CI
class SSEMockRequestHandler(BaseHTTPRequestHandler):
    """Mock SSE handler for CI environments."""

    def do_GET(self):
        if "/sse" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            # Send mock progress events
            for progress in [10, 30, 50, 70, 90, 100]:
                self.wfile.write(f"event: progress\ndata: {json.dumps({'progress': progress})}\n\n".encode())
                time.sleep(0.1)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps([]).encode())


@pytest.fixture(scope="session")
def sse_mock_server():
    """Provide SSE mock server for CI environments."""
    if not IS_CI:
        pytest.skip("Skipping mock server - running against real cluster")

    server = SSEMockServer(port=8888)
    server.start()
    yield server
    server.stop()


@pytest.fixture(scope="session")
def browser():
    """Provide Playwright browser instance."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    """Provide a new page for each test."""
    page = browser.new_page()
    yield page
    page.close()


@pytest.fixture(scope="session")
def api_client():
    """API 测试客户端"""
    import httpx
    return APIClient(base_url="http://localhost:8000", api_key="test-api-key")
```

---

## 6. CI 集成

### 6.1 GitHub Actions 配置

```yaml
# .github/workflows/e2e.yml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -e .
          pip install playwright pytest pytest-asyncio allure-pytest

      - name: Install Playwright browsers
        run: playwright install chromium

      - name: Run E2E tests
        env:
          API_BASE_URL: http://localhost:8000
          RAY_ADDRESS: 192.168.0.126:6379
        run: |
          pytest tests/e2e/ --alluredir=tests/reports/allure-results

      - name: Upload Allure results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: allure-results
          path: tests/reports/allure-results
```

---

**文档状态:** 正式版
