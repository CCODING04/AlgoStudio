# Web Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 3-page Gradio-based Web Console for AlgoStudio — Dashboard, Tasks list, Hosts monitoring — consuming Phase 1 FastAPI endpoints.

**Architecture:** Gradio Blocks app with tab-based navigation. API client module (`client.py`) centralizes all HTTP calls to the FastAPI backend. Each page is a self-contained Gradio UI module. Responsive layout via Gradio's fluid layout + CSS.

**Tech Stack:** Gradio 5.x, requests, FastAPI (existing Phase 1)

---

## File Structure

```
src/algo_studio/web/
├── __init__.py
├── config.py          # Theme, layout constants, API base URL
├── client.py         # API client: get_tasks(), get_hosts_status()
├── app.py            # Gradio Blocks app, tab navigation
└── pages/
    ├── __init__.py
    ├── dashboard.py  # Dashboard page (stats + cluster cards)
    ├── tasks.py      # Tasks list page (Dataframe)
    └── hosts.py      # Hosts monitoring page (resource bars)

tests/
├── test_web_client.py       # Unit tests for API client
├── test_web_pages.py        # Unit tests for each page module
└── test_web_app.py          # Integration test for app startup
```

**Key design decisions:**
- `client.py` is the single place to call FastAPI — pages import from it, not raw `requests`
- Each page exports a `make_page()` function returning a `gr.Row` or `gr.Column`
- `app.py` assembles pages via `with gr.Tab()` and sets `fluid=True`

---

## Task 1: Create web module scaffold + config

**Files:**
- Create: `src/algo_studio/web/__init__.py`
- Create: `src/algo_studio/web/config.py`
- Create: `src/algo_studio/web/pages/__init__.py`

- [ ] **Step 1: Create `src/algo_studio/web/__init__.py`**

```python
"""AlgoStudio Web Console."""
```

- [ ] **Step 2: Create `src/algo_studio/web/config.py`**

```python
import os

API_BASE = os.environ.get("ALGO_STUDIO_API", "http://localhost:8000")
REFRESH_INTERVAL = 30  # seconds
```

- [ ] **Step 3: Create `src/algo_studio/web/pages/__init__.py`**

```python
"""Web Console pages."""
```

- [ ] **Step 4: Commit**

```bash
git add src/algo_studio/web/__init__.py src/algo_studio/web/config.py src/algo_studio/web/pages/__init__.py
git commit -m "feat(web): create web module scaffold and config"
```

---

## Task 2: Build API client module

**Files:**
- Create: `src/algo_studio/web/client.py`
- Create: `tests/test_web_client.py`

- [ ] **Step 1: Write failing test in `tests/test_web_client.py`**

```python
import pytest
from unittest.mock import patch, MagicMock
from algo_studio.web.client import get_tasks, get_hosts_status


class TestGetTasks:
    @patch("algo_studio.web.client.requests.get")
    def test_returns_list_of_tasks(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "tasks": [
                {"task_id": "train-001", "task_type": "train", "status": "pending"}
            ],
            "total": 1
        }
        mock_get.return_value = mock_resp

        result = get_tasks()

        assert result["total"] == 1
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["task_id"] == "train-001"
        mock_get.assert_called_once()


class TestGetHostsStatus:
    @patch("algo_studio.web.client.requests.get")
    def test_returns_cluster_and_local(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "cluster_nodes": [],
            "local_host": {"hostname": "test", "ip": "127.0.1.1", "status": "online"}
        }
        mock_get.return_value = mock_resp

        result = get_hosts_status()

        assert "cluster_nodes" in result
        assert "local_host" in result
        mock_get.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/admin02/Code/Dev/AlgoStudio
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
pytest tests/test_web_client.py -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Write implementation in `src/algo_studio/web/client.py`**

```python
import requests
from algo_studio.web.config import API_BASE


def get_tasks():
    """Fetch all tasks from the API."""
    resp = requests.get(f"{API_BASE}/api/tasks", timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_hosts_status():
    """Fetch cluster and local host status from the API."""
    resp = requests.get(f"{API_BASE}/api/hosts/status", timeout=10)
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
pytest tests/test_web_client.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/algo_studio/web/client.py tests/test_web_client.py
git commit -m "feat(web): add API client module"
```

---

## Task 3: Build Dashboard page

**Files:**
- Create: `src/algo_studio/web/pages/dashboard.py`
- Create: `tests/test_web_pages.py` (add TestDashboard class)

- [ ] **Step 1: Write failing test in `tests/test_web_pages.py`**

```python
import pytest
from algo_studio.web.pages.dashboard import make_page


class TestDashboardPage:
    def test_make_page_returns_column(self):
        page = make_page()
        assert page is not None
        # Page should be a gr.Column or have visible components
```

- [ ] **Step 2: Run test to verify it fails**

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
pytest tests/test_web_pages.py::TestDashboardPage -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Write implementation in `src/algo_studio/web/pages/dashboard.py`**

```python
import gr
from algo_studio.web.client import get_tasks, get_hosts_status


def make_page():
    """Build the Dashboard page."""
    with gr.Column():
        gr.Markdown("## 仪表盘")
        with gr.Row():
            total_box = gr.Number(label="任务总数", interactive=False)
            running_box = gr.Number(label="训练中", interactive=False)
            pending_box = gr.Number(label="待处理", interactive=False)
            failed_box = gr.Number(label="失败", interactive=False)

        refresh_btn = gr.Button("刷新", variant="primary")
        auto_refresh = gr.Checkbox(label="自动刷新 (30秒)", value=False)

        cluster_cards = gr.Column()

        def load_stats():
            data = get_tasks()
            tasks = data.get("tasks", [])
            total = data.get("total", 0)
            running = sum(1 for t in tasks if t.get("status") == "running")
            pending = sum(1 for t in tasks if t.get("status") == "pending")
            failed = sum(1 for t in tasks if t.get("status") == "failed")
            return total, running, pending, failed

        def load_cluster():
            data = get_hosts_status()
            nodes = data.get("cluster_nodes", [])
            local = data.get("local_host", {})
            return nodes, local

        refresh_btn.click(
            load_stats,
            outputs=[total_box, running_box, pending_box, failed_box]
        )

        return refresh_btn, auto_refresh, total_box, running_box, pending_box, failed_box, cluster_cards
```

- [ ] **Step 4: Run test to verify it passes**

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
pytest tests/test_web_pages.py::TestDashboardPage -v
```

- [ ] **Step 5: Commit**

```bash
git add src/algo_studio/web/pages/dashboard.py tests/test_web_pages.py
git commit -m "feat(web): build Dashboard page"
```

---

## Task 4: Build Tasks page

**Files:**
- Modify: `src/algo_studio/web/pages/tasks.py` (create)
- Modify: `tests/test_web_pages.py` (add TestTasksPage)

- [ ] **Step 1: Write implementation in `src/algo_studio/web/pages/tasks.py`**

```python
import gr
from algo_studio.web.client import get_tasks


def make_page():
    """Build the Tasks list page."""
    with gr.Column():
        gr.Markdown("## 任务列表")

        with gr.Row():
            filter_status = gr.Dropdown(
                label="状态筛选",
                choices=["全部", "pending", "running", "completed", "failed", "cancelled"],
                value="全部",
            )
            refresh_btn = gr.Button("刷新", variant="primary")

        tasks_table = gr.Dataframe(
            headers=["task_id", "task_type", "algorithm_name", "algorithm_version", "status", "created_at", "assigned_node"],
            label="任务列表",
            interactive=False,
        )

        def load_tasks(status_filter="全部"):
            data = get_tasks()
            tasks = data.get("tasks", [])
            if status_filter != "全部":
                tasks = [t for t in tasks if t.get("status") == status_filter]
            rows = [
                [
                    t.get("task_id", ""),
                    t.get("task_type", ""),
                    t.get("algorithm_name", ""),
                    t.get("algorithm_version", ""),
                    t.get("status", ""),
                    str(t.get("created_at", "")),
                    t.get("assigned_node") or "",
                ]
                for t in tasks
            ]
            return rows

        refresh_btn.click(
            lambda v: load_tasks(v),
            inputs=[filter_status],
            outputs=[tasks_table],
        )
        filter_status.change(
            lambda v: load_tasks(v),
            inputs=[filter_status],
            outputs=[tasks_table],
        )

        return tasks_table, refresh_btn, filter_status
```

- [ ] **Step 2: Add test in `tests/test_web_pages.py`**

```python
class TestTasksPage:
    def test_make_page_returns_tasks_table(self):
        page = make_page()
        assert page is not None
```

- [ ] **Step 3: Run tests**

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
pytest tests/test_web_pages.py::TestTasksPage -v
```

- [ ] **Step 4: Commit**

```bash
git add src/algo_studio/web/pages/tasks.py tests/test_web_pages.py
git commit -m "feat(web): build Tasks list page"
```

---

## Task 5: Build Hosts monitoring page

**Files:**
- Create: `src/algo_studio/web/pages/hosts.py`
- Modify: `tests/test_web_pages.py` (add TestHostsPage)

- [ ] **Step 1: Write implementation in `src/algo_studio/web/pages/hosts.py`**

```python
import gr
from algo_studio.web.client import get_hosts_status


def _color_pct(pct: float) -> str:
    """Return color based on usage percentage."""
    if pct < 60:
        return "#22c55e"   # green
    elif pct < 85:
        return "#eab308"   # yellow
    else:
        return "#ef4444"   # red


def _render_host_card(hostname: str, ip: str, status: str, resources: dict, is_local: bool = False) -> str:
    """Render one host as an HTML card string."""
    label = "(本机)" if is_local else ""
    status_icon = "🟢" if status == "online" else "🔴"

    gpu = resources.get("gpu", {})
    cpu = resources.get("cpu", {})
    memory = resources.get("memory", {})
    disk = resources.get("disk", {})
    swap = resources.get("swap", {})

    def bar(used: float, total: float, unit: str = "") -> str:
        pct = used / total * 100 if total > 0 else 0
        color = _color_pct(pct)
        used_str = f"{used:.1f}" if isinstance(used, float) else str(used)
        total_str = f"{total:.1f}" if isinstance(total, float) else str(total)
        return (
            f'<div style="margin:4px 0">'
            f'<div style="display:flex;justify-content:space-between;font-size:13px">'
            f'<span>{used_str}{unit} / {total_str}{unit}</span>'
            f'<span>{pct:.0f}%</span></div>'
            f'<div style="background:#e5e7eb;border-radius:4px;height:8px;margin-top:2px">'
            f'<div style="width:{pct:.0f}%;background:{color};height:8px;border-radius:4px"></div></div>'
            f'</div>'
        )

    # Parse numeric values from resource strings like "9.7Gi", "31.2Gi"
    def parse_val(s, unit=""):
        try:
            return float(str(s).rstrip("GiG"))
        except (ValueError, TypeError):
            return 0.0

    gpu_name = gpu.get("name", "N/A")
    gpu_total = gpu.get("total", 0) or 0
    gpu_used = gpu.get("used", 0) or 0

    cpu_total = cpu.get("total", 0) or 0
    cpu_used = cpu.get("used", 0) or 0

    mem_str = memory.get("total", "0Gi")
    mem_used_str = memory.get("used", "0Gi")

    disk_str = disk.get("total", "0G")
    disk_used_str = disk.get("used", "0G")

    swap_str = swap.get("total", "0Gi")
    swap_used_str = swap.get("used", "0Gi")

    return f"""
    <div style="border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin:8px 0;background:#fafafa">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <strong style="font-size:15px">{hostname} {label}</strong>
            <span>{status_icon} {status.capitalize()}</span>
        </div>
        <div style="font-size:12px;color:#6b7280;margin-bottom:12px">IP: {ip}</div>
        <div style="font-size:13px;margin-bottom:8px">
            <strong>GPU ({gpu_name})</strong>
            {bar(gpu_used, gpu_total)}
        </div>
        <div style="font-size:13px;margin-bottom:8px">
            <strong>CPU</strong>
            {bar(cpu_used, cpu_total)}
        </div>
        <div style="font-size:13px;margin-bottom:8px">
            <strong>Memory</strong>
            {bar(parse_val(mem_used_str), parse_val(mem_str), unit="Gi")}
        </div>
        <div style="font-size:13px;margin-bottom:8px">
            <strong>Disk</strong>
            {bar(parse_val(disk_used_str), parse_val(disk_str), unit="G")}
        </div>
        <div style="font-size:13px">
            <strong>Swap</strong>
            {bar(parse_val(swap_used_str), parse_val(swap_str), unit="Gi")}
        </div>
    </div>
    """


def make_page():
    """Build the Hosts monitoring page."""
    with gr.Column():
        gr.Markdown("## 主机监控")
        with gr.Row():
            refresh_btn = gr.Button("刷新", variant="primary")
            auto_refresh = gr.Checkbox(label="自动刷新 (30秒)", value=False)

        html_output = gr.HTML(label="主机状态", value="<p>点击刷新以加载数据</p>")

        def load_hosts() -> str:
            data = get_hosts_status()
            nodes = data.get("cluster_nodes", [])
            local = data.get("local_host", {})

            cards = []
            # Local host first
            if local.get("hostname"):
                cards.append(_render_host_card(
                    hostname=local.get("hostname", ""),
                    ip=local.get("ip", ""),
                    status=local.get("status", "offline"),
                    resources=local.get("resources", {}),
                    is_local=True,
                ))
            # Then cluster nodes
            for node in nodes:
                cards.append(_render_host_card(
                    hostname=node.get("hostname", node.get("ip", "Unknown")),
                    ip=node.get("ip", ""),
                    status=node.get("status", "offline"),
                    resources=node.get("resources", {}),
                ))
            if not cards:
                return "<p>无可用主机</p>"
            return "\n".join(cards)

        refresh_btn.click(fn=load_hosts, outputs=[html_output])

        return html_output, refresh_btn, auto_refresh
```

- [ ] **Step 2: Add test in `tests/test_web_pages.py`**

```python
class TestHostsPage:
    def test_make_page_returns_column(self):
        page = make_page()
        assert page is not None
```

- [ ] **Step 3: Run tests**

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
pytest tests/test_web_pages.py::TestHostsPage -v
```

- [ ] **Step 4: Commit**

```bash
git add src/algo_studio/web/pages/hosts.py tests/test_web_pages.py
git commit -m "feat(web): build Hosts monitoring page"
```

---

## Task 6: Assemble Gradio app with tab navigation

**Files:**
- Create: `src/algo_studio/web/app.py`
- Modify: `src/algo_studio/web/__init__.py` (add run entry point)

- [ ] **Step 1: Write `src/algo_studio/web/app.py`**

```python
import gr
from algo_studio.web.pages.dashboard import make_page as make_dashboard
from algo_studio.web.pages.tasks import make_page as make_tasks
from algo_studio.web.pages.hosts import make_page as make_hosts


def create_app():
    """Create the Gradio Blocks app."""
    with gr.Blocks(title="AlgoStudio", theme=gr.themes.Default()) as app:
        gr.Markdown("# AlgoStudio 控制台")

        with gr.Tab("仪表盘"):
            make_dashboard()

        with gr.Tab("任务列表"):
            make_tasks()

        with gr.Tab("主机监控"):
            make_hosts()

    return app


app = create_app()

if __name__ == "__main__":
    import os
    host = os.environ.get("GRADIO_HOST", "0.0.0.0")
    port = int(os.environ.get("GRADIO_PORT", "7860"))
    app.launch(server_name=host, server_port=port)
```

- [ ] **Step 2: Update `src/algo_studio/web/__init__.py`**

```python
"""AlgoStudio Web Console."""

from algo_studio.web.app import app

__all__ = ["app"]
```

- [ ] **Step 3: Write integration test in `tests/test_web_app.py`**

```python
import pytest
from algo_studio.web.app import create_app


def test_app_creates_successfully():
    app = create_app()
    assert app is not None
    assert app.title == "AlgoStudio"
```

- [ ] **Step 4: Run test**

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
pytest tests/test_web_app.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/algo_studio/web/app.py src/algo_studio/web/__init__.py tests/test_web_app.py
git commit -m "feat(web): assemble Gradio app with tab navigation"
```

---

## Task 7: Add requirements and README update

**Files:**
- Create: `requirements-web.txt`
- Modify: `README.md` (add Web Console section)

- [ ] **Step 1: Create `requirements-web.txt`**

```
gradio>=5.0.0
requests
```

- [ ] **Step 2: Update README section**

Add under "## Quick Start" or "## Usage":

```markdown
### Web Console (Phase 2)

```bash
# Install web dependencies
pip install -r requirements-web.txt

# Start web console
PYTHONPATH="$(pwd)/src" python -m algo_studio.web.app --host 0.0.0.0 --port 7860

# Access
open http://localhost:7860
```
```

- [ ] **Step 3: Commit**

```bash
git add requirements-web.txt README.md
git commit -m "docs: add Web Console usage to README"
```

---

## Verification

After all tasks complete:

```bash
# 1. Run all web tests
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
pytest tests/test_web_*.py -v

# 2. Install gradio
pip install -r requirements-web.txt

# 3. Start API server (Phase 1)
PYTHONPATH="$(pwd)/src" .venv/bin/python -m uvicorn algo_studio.api.main:app --host 0.0.0.0 --port 8000 &

# 4. Start web console
sleep 2
PYTHONPATH="$(pwd)/src" python -m algo_studio.web.app --host 0.0.0.0 --port 7860
# Open http://localhost:7860
```
