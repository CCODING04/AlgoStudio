"""Deploy page for Worker node deployment via SSH."""

import json
import re
import threading
import time
from datetime import datetime

import gradio as gr
import requests
from algo_studio.web.config import API_BASE


# IP address regex pattern (IPv4 only)
_IPV4_PATTERN = re.compile(
    r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
    r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
)

# SSE reconnect settings
_SSE_RECONNECT_DELAY = 2.0  # seconds
_SSE_MAX_RETRIES = 3
_SSE_TIMEOUT = 30  # seconds


def _validate_ip(ip: str) -> tuple[bool, str]:
    """Validate IP address format. Returns (is_valid, error_message)."""
    if not ip or not _IPV4_PATTERN.match(ip.strip()):
        return False, f"Invalid IP address format: {ip}"
    return True, ""


def _make_request(method: str, url: str, error_msg: str, **kwargs) -> dict:
    """Internal request helper with error handling."""
    try:
        if method.upper() == "GET":
            resp = requests.get(url, timeout=30, **kwargs)
        elif method.upper() == "POST":
            resp = requests.post(url, timeout=60, **kwargs)
        else:
            raise RuntimeError(f"Unsupported method: {method}")
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"{error_msg}: {e}") from e


def _list_workers() -> list:
    """List all deployment workers."""
    try:
        data = _make_request("GET", f"{API_BASE}/api/deploy/workers", "Failed to list workers")
        return data.get("items", [])
    except Exception as e:
        print(f"Error listing workers: {e}")
        return []


def _get_worker(task_id: str) -> dict:
    """Get deployment worker status."""
    return _make_request("GET", f"{API_BASE}/api/deploy/worker/{task_id}", f"Failed to get worker {task_id}")


def _parse_sse_response(response) -> tuple[str, dict]:
    """Parse SSE event stream response. Returns (event_type, data)."""
    content = response.content.decode("utf-8")
    lines = content.split("\n")

    event_type = "message"
    data = {}

    for line in lines:
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data_str = line[5:].strip()
            if data_str:
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    pass

    return event_type, data


def _poll_deployment_progress(task_id: str, max_retries: int = _SSE_MAX_RETRIES) -> dict | None:
    """Poll deployment progress with retry mechanism. Returns final state or None on failure."""
    url = f"{API_BASE}/api/deploy/worker/{task_id}/progress"

    for attempt in range(max_retries):
        try:
            response = requests.get(url, stream=True, timeout=_SSE_TIMEOUT)
            response.raise_for_status()

            # For SSE, we just get the current state (not streaming)
            # The SSE endpoint will handle the streaming on the client side
            # Here we just fetch the current status
            return _get_worker(task_id)

        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                time.sleep(_SSE_RECONNECT_DELAY * (attempt + 1))
            continue
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(_SSE_RECONNECT_DELAY)
            continue
        except requests.exceptions.RequestException as e:
            print(f"Error polling deployment progress: {e}")
            return None

    return None


def _fetch_workers_retry(retries: int = 3, delay: float = 1.0) -> tuple[list, str | None]:
    """Fetch workers list with retry mechanism. Returns (workers_list, error_message)."""
    last_error = None
    for attempt in range(retries):
        try:
            workers = _list_workers()
            return workers, None
        except requests.exceptions.ConnectionError:
            last_error = "连接失败: 无法连接到服务器"
        except requests.exceptions.Timeout:
            last_error = "请求超时: 服务器响应时间过长"
        except requests.exceptions.RequestException as e:
            last_error = f"请求失败: {str(e)}"
        except Exception as e:
            last_error = f"未知错误: {str(e)}"

        if attempt < retries - 1:
            time.sleep(delay * (attempt + 1))

    return [], last_error


def _deploy_worker(node_ip: str, username: str, password: str, head_ip: str, ray_port: int = 6379) -> dict:
    """Trigger worker deployment."""
    # Validate inputs
    is_valid, error = _validate_ip(node_ip)
    if not is_valid:
        raise RuntimeError(f"Invalid node IP: {error}")

    is_valid, error = _validate_ip(head_ip)
    if not is_valid:
        raise RuntimeError(f"Invalid head IP: {error}")

    if ray_port < 1 or ray_port > 65535:
        raise RuntimeError(f"Invalid Ray port: {ray_port}")

    payload = {
        "node_ip": node_ip.strip(),
        "username": username.strip() or "admin02",
        "password": password,
        "head_ip": head_ip.strip(),
        "ray_port": ray_port,
    }

    return _make_request("POST", f"{API_BASE}/api/deploy/worker", "Failed to deploy worker", json=payload)


def make_page():
    """Build the Deploy page."""
    with gr.Column():
        gr.Markdown("## Worker 部署")

        # Deployment form
        with gr.Group():
            gr.Markdown("### 部署新 Worker 节点")

            with gr.Row():
                node_ip = gr.Textbox(
                    label="Worker 节点 IP",
                    placeholder="192.168.0.115",
                    info="Worker 节点的 IP 地址",
                )
                username = gr.Textbox(
                    label="用户名",
                    value="admin02",
                    info="SSH 用户名",
                )

            with gr.Row():
                password = gr.Textbox(
                    label="密码",
                    placeholder="Enter SSH password",
                    type="password",
                    info="SSH 密码",
                )
                head_ip = gr.Textbox(
                    label="Head 节点 IP",
                    placeholder="192.168.0.126",
                    info="Ray Head 节点 IP",
                )

            with gr.Row():
                ray_port = gr.Number(
                    label="Ray 端口",
                    value=6379,
                    info="Ray 集群端口 (1-65535)",
                    minimum=1,
                    maximum=65535,
                )
                deploy_btn = gr.Button("部署", variant="primary")

        # Status and progress display
        with gr.Group():
            gr.Markdown("### 部署状态")

            status_loading = gr.Markdown("加载中...", visible=False)
            status_error = gr.Markdown("", visible=False)
            status_display = gr.HTML(value="<p>暂无部署任务</p>")

            with gr.Row():
                refresh_btn = gr.Button("刷新状态", variant="secondary")
                clear_btn = gr.Button("清除")

        # Worker list
        with gr.Group():
            gr.Markdown("### 部署历史")

            workers_table = gr.Dataframe(
                headers=["task_id", "node_ip", "status", "step", "progress", "message", "error"],
                label="部署记录",
                interactive=False,
            )
            workers_error = gr.Markdown("", visible=False)

        def deploy_with_validation(node_ip: str, username: str, password: str, head_ip: str, ray_port: int):
            """Handle deployment with validation and loading states."""
            # Validate inputs
            if not node_ip or not node_ip.strip():
                yield {status_error: gr.update(visible=True, value="**错误:** Worker 节点 IP 不能为空"), status_loading: gr.update(visible=False), status_display: gr.update(value="<p style='color:red'>部署失败: IP 地址不能为空</p>")}
                return
            if not head_ip or not head_ip.strip():
                yield {status_error: gr.update(visible=True, value="**错误:** Head 节点 IP 不能为空"), status_loading: gr.update(visible=False), status_display: gr.update(value="<p style='color:red'>部署失败: Head IP 地址不能为空</p>")}
                return
            if not password or not password.strip():
                yield {status_error: gr.update(visible=True, value="**错误:** 密码不能为空"), status_loading: gr.update(visible=False), status_display: gr.update(value="<p style='color:red'>部署失败: 密码不能为空</p>")}
                return

            # Validate IP formats
            is_valid, error = _validate_ip(node_ip)
            if not is_valid:
                yield {status_error: gr.update(visible=True, value=f"**错误:** {error}"), status_loading: gr.update(visible=False), status_display: gr.update(value=f"<p style='color:red'>部署失败: {error}</p>")}
                return

            is_valid, error = _validate_ip(head_ip)
            if not is_valid:
                yield {status_error: gr.update(visible=True, value=f"**错误:** {error}"), status_loading: gr.update(visible=False), status_display: gr.update(value=f"<p style='color:red'>部署失败: {error}</p>")}
                return

            # Validate port
            port = int(ray_port) if ray_port else 6379
            if port < 1 or port > 65535:
                yield {status_error: gr.update(visible=True, value=f"**错误:** Ray 端口必须在 1-65535 之间"), status_loading: gr.update(visible=False), status_display: gr.update(value=f"<p style='color:red'>部署失败: 端口无效</p>")}
                return

            try:
                # Show loading
                yield {status_loading: gr.update(visible=True, value="正在发起部署..."), status_error: gr.update(visible=False), status_display: gr.update(value="<p>正在发起部署任务...</p>")}

                result = _deploy_worker(
                    node_ip=node_ip.strip(),
                    username=username.strip() or "admin02",
                    password=password,
                    head_ip=head_ip.strip(),
                    ray_port=port,
                )

                task_id = result.get("task_id", "unknown")
                message = result.get("message", "部署已发起")

                # If deployment is already in progress, show that message
                if "already in progress" in message:
                    yield {status_loading: gr.update(visible=False), status_error: gr.update(visible=False), status_display: gr.update(value=f"<p style='color:orange'>⚠️ {message}</p><p>Task ID: {task_id}</p>")}
                else:
                    yield {status_loading: gr.update(visible=False), status_error: gr.update(visible=False), status_display: gr.update(value=f"<p style='color:green'>✓ {message}</p><p>Task ID: {task_id}</p>")}

            except RuntimeError as e:
                yield {status_loading: gr.update(visible=False), status_error: gr.update(visible=True, value=f"**错误:** {str(e)}"), status_display: gr.update(value=f"<p style='color:red'>部署失败: {str(e)}</p>")}
            except Exception as e:
                yield {status_loading: gr.update(visible=False), status_error: gr.update(visible=True, value=f"**错误:** 部署请求失败"), status_display: gr.update(value=f"<p style='color:red'>部署失败: {str(e)}</p>")}

        def load_workers_list():
            """Load workers list with retry mechanism and better error handling."""
            try:
                yield {status_loading: gr.update(visible=True), status_error: gr.update(visible=False), workers_error: gr.update(visible=False)}

                workers, error = _fetch_workers_retry(retries=3, delay=1.0)

                if error:
                    yield {status_loading: gr.update(visible=False), status_error: gr.update(visible=False), workers_error: gr.update(visible=True, value=f"**错误:** {error}"), workers_table: gr.update(value=[])}
                    return

                if not workers:
                    yield {status_loading: gr.update(visible=False), status_error: gr.update(visible=False), workers_error: gr.update(visible=False), workers_table: gr.update(value=[])}
                    return

                rows = [
                    [
                        w.get("task_id", ""),
                        w.get("node_ip", ""),
                        w.get("status", ""),
                        w.get("step", ""),
                        f"{w.get('progress', 0)}%",
                        w.get("message", "") or "",
                        w.get("error", "") or "",
                    ]
                    for w in workers
                ]
                from datetime import datetime
                now = datetime.now().strftime("%H:%M:%S")
                yield {
                    status_loading: gr.update(visible=False),
                    status_error: gr.update(visible=False),
                    workers_error: gr.update(visible=False),
                    workers_table: gr.update(value=rows),
                }
            except Exception as e:
                yield {status_loading: gr.update(visible=False), status_error: gr.update(visible=False), workers_error: gr.update(visible=True, value=f"**错误:** {str(e)}"), workers_table: gr.update(value=[])}

        def clear_status():
            """Clear all status displays."""
            return {
                status_loading: gr.update(visible=False),
                status_error: gr.update(visible=False),
                status_display: gr.update(value="<p>暂无部署任务</p>"),
            }

        # Event handlers
        deploy_btn.click(
            deploy_with_validation,
            inputs=[node_ip, username, password, head_ip, ray_port],
            outputs=[status_loading, status_error, status_display],
        )

        refresh_btn.click(
            load_workers_list,
            outputs=[status_loading, status_error, workers_table, workers_error],
        )

        clear_btn.click(
            clear_status,
            outputs=[status_loading, status_error, status_display],
        )

        # Load workers list on page load
        workers = _list_workers()
        if workers:
            rows = [
                [
                    w.get("task_id", ""),
                    w.get("node_ip", ""),
                    w.get("status", ""),
                    w.get("step", ""),
                    f"{w.get('progress', 0)}%",
                    w.get("message", "") or "",
                    w.get("error", "") or "",
                ]
                for w in workers
            ]
        else:
            rows = []

        return {
            workers_table: gr.update(value=rows),
        }
