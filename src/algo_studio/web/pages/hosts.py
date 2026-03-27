import html
import threading
import time

import gradio as gr
import requests
from algo_studio.web.client import get_hosts_status
from algo_studio.web.config import REFRESH_INTERVAL

# Global state for auto-refresh
_refresh_active = False
_refresh_thread = None


def _color_pct(pct: float) -> str:
    """Return color based on usage percentage."""
    if pct < 60:
        return "#22c55e"   # green
    elif pct < 85:
        return "#eab308"   # yellow
    else:
        return "#ef4444"   # red


def _parse_size(s: str) -> float:
    """Parse size string like '100Gi', '500G', '1.5T' to float."""
    s = str(s).strip()
    for sufx in ["Ti", "Gi", "Mi", "Ki", "T", "G", "M", "K"]:
        if s.endswith(sufx):
            try:
                return float(s[:-len(sufx)])
            except ValueError:
                return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _bar(used: float, total: float, unit: str = "") -> str:
    """Render a progress bar HTML snippet."""
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


def _fetch_hosts_retry(retries: int = 3, delay: float = 1.0) -> tuple[dict | None, str | None]:
    """Fetch hosts with retry mechanism. Returns (data, error_message)."""
    last_error = None
    for attempt in range(retries):
        try:
            data = get_hosts_status()
            return data, None
        except requests.exceptions.ConnectionError as e:
            last_error = f"连接失败: 无法连接到服务器，请检查API服务是否运行"
        except requests.exceptions.Timeout as e:
            last_error = f"请求超时: 服务器响应时间过长"
        except requests.exceptions.RequestException as e:
            last_error = f"请求失败: {str(e)}"
        except Exception as e:
            last_error = f"未知错误: {str(e)}"

        if attempt < retries - 1:
            time.sleep(delay * (attempt + 1))  # Exponential backoff

    return None, last_error


def _render_host_card(hostname: str, ip: str, status: str,
                      gpu: dict, cpu: dict, memory: dict,
                      disk: dict, swap: dict,
                      is_local: bool = False) -> str:
    """Render one host as an HTML card string."""
    hostname_esc = html.escape(str(hostname)) if hostname else ip
    ip_esc = html.escape(str(ip))

    if is_local:
        label = "宿主机 (Head)"
        border_color = "#3b82f6"  # blue for head node
        border_style = f"border:2px solid {border_color};"
    else:
        label = ""
        border_style = "border:1px solid #e5e7eb;"

    status_icon = "🟢" if status == "online" or status == "idle" else "🔴"
    status_display = "Online" if status == "idle" else status.capitalize()

    gpu_name = html.escape(str(gpu.get("name", ""))) if gpu.get("name") else "无"
    gpu_total = float(gpu.get("total", 0) or 0)
    gpu_utilization = gpu.get("utilization")
    gpu_mem_used = gpu.get("memory_used")
    gpu_mem_total = gpu.get("memory_total")

    cpu_total = float(cpu.get("total", 0) or 0)
    cpu_used = float(cpu.get("used", 0) or 0)
    cpu_model = html.escape(str(cpu.get("model", ""))) if cpu.get("model") else None
    cpu_physical = cpu.get("physical_cores")
    cpu_freq = cpu.get("freq_mhz")

    # 远端节点显示 "获取失败"
    unknown_label = '<span style="color:#9ca3af;font-size:12px">（获取失败）</span>'

    mem_total = _parse_size(memory.get("total", "0Gi")) if memory.get("total") else 0
    mem_used = _parse_size(memory.get("used", "0Gi")) if memory.get("used") else 0

    disk_total = _parse_size(disk.get("total", "0G")) if disk.get("total") else 0
    disk_used = _parse_size(disk.get("used", "0G")) if disk.get("used") else 0

    swap_total = _parse_size(swap.get("total", "0Gi")) if swap.get("total") else 0
    swap_used = _parse_size(swap.get("used", "0Gi")) if swap.get("used") else 0

    # CPU 信息行
    cpu_info_parts = []
    if cpu_model:
        cpu_info_parts.append(f"{cpu_model}")
    if cpu_physical:
        threads = int(cpu_total) if cpu_total else 0
        cpu_info_parts.append(f"{cpu_physical}P / {threads}T")
    elif cpu_total:
        cpu_info_parts.append(f"{int(cpu_total)} 线程")
    if cpu_freq:
        cpu_info_parts.append(f"{cpu_freq:.0f} MHz")
    cpu_info_str = " · ".join(cpu_info_parts) if cpu_info_parts else ""

    # GPU 区块
    if gpu_name == "无" or gpu_utilization is None:
        gpu_section = f'''
        <div style="font-size:13px;margin-bottom:8px">
            <strong>GPU {f"({gpu_name})" if gpu_name != "无" else ""}</strong>
            <div style="font-size:12px;color:#9ca3af;margin:2px 0">{unknown_label}</div>
        </div>
        '''
    else:
        gpu_section = f'''
        <div style="font-size:13px;margin-bottom:8px">
            <strong>GPU {f'({gpu_name})' if gpu_name != "无" else ""}</strong>
            <div style="font-size:12px;color:#6b7280;margin:2px 0 4px">利用率</div>
            {_bar(float(gpu_utilization), 100, unit="%")}
            <div style="font-size:12px;color:#6b7280;margin:2px 0 4px">显存</div>
            {_bar(_parse_size(gpu_mem_used), _parse_size(gpu_mem_total), unit="Gi")}
        </div>
        '''

    # CPU 区块
    if not cpu_info_str and not cpu_total:
        cpu_section = f'''
        <div style="font-size:13px;margin-bottom:8px">
            <strong>CPU</strong>
            <div style="font-size:12px;color:#9ca3af;margin:2px 0">{unknown_label}</div>
        </div>
        '''
    else:
        cpu_section = f'''
        <div style="font-size:13px;margin-bottom:8px">
            <strong>CPU</strong>
            {f'<div style="font-size:12px;color:#6b7280;margin:2px 0 4px">{cpu_info_str}</div>' if cpu_info_str else ""}
            {_bar(cpu_used, cpu_total)}
        </div>
        '''

    # Memory 区块
    if not mem_total:
        mem_section = f'''
        <div style="font-size:13px;margin-bottom:8px">
            <strong>Memory</strong>
            <div style="font-size:12px;color:#9ca3af;margin:2px 0">{unknown_label}</div>
        </div>
        '''
    else:
        mem_section = f'''
        <div style="font-size:13px;margin-bottom:8px">
            <strong>Memory</strong>
            {_bar(mem_used, mem_total, unit="Gi")}
        </div>
        '''

    # Disk 区块
    if not disk_total:
        disk_section = f'''
        <div style="font-size:13px;margin-bottom:8px">
            <strong>Disk</strong>
            <div style="font-size:12px;color:#9ca3af;margin:2px 0">{unknown_label}</div>
        </div>
        '''
    else:
        disk_section = f'''
        <div style="font-size:13px;margin-bottom:8px">
            <strong>Disk</strong>
            {_bar(disk_used, disk_total, unit="G")}
        </div>
        '''

    # Swap 区块
    if not swap_total:
        swap_section = f'''
        <div style="font-size:13px">
            <strong>Swap</strong>
            <div style="font-size:12px;color:#9ca3af;margin:2px 0">{unknown_label}</div>
        </div>
        '''
    else:
        swap_section = f'''
        <div style="font-size:13px">
            <strong>Swap</strong>
            {_bar(swap_used, swap_total, unit="Gi")}
        </div>
        '''

    return f"""
    <div style="{border_style}border-radius:8px;padding:16px;margin:8px 0;background:#fafafa">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <strong style="font-size:15px">{hostname_esc} {label}</strong>
            <span>{status_icon} {status_display}</span>
        </div>
        <div style="font-size:12px;color:#6b7280;margin-bottom:12px">IP: {ip_esc}</div>
        {gpu_section}
        {cpu_section}
        {mem_section}
        {disk_section}
        {swap_section}
    </div>
    """


def make_page():
    """Build the Hosts monitoring page."""
    global _refresh_active, _refresh_thread

    with gr.Column():
        gr.Markdown("## 主机监控")

        # Auto-refresh controls
        with gr.Row():
            auto_refresh = gr.Checkbox(label="自动刷新", value=False, scale=0)
            interval_display = gr.Number(label="刷新间隔(秒)", value=REFRESH_INTERVAL, scale=0, min_width=100)
            refresh_btn = gr.Button("刷新", variant="primary", scale=1)

        loading_indicator = gr.Markdown("加载中...", visible=False)
        error_display = gr.Markdown("", visible=False)
        last_updated = gr.Markdown("", visible=False)
        html_output = gr.HTML(label="主机状态", value="<p>点击刷新以加载数据</p>")

        def load_hosts_with_state():
            """Load hosts with loading state management and retry."""
            try:
                yield {loading_indicator: gr.update(visible=True), error_display: gr.update(visible=False), html_output: gr.update(value="<p>加载中...</p>")}

                data, error = _fetch_hosts_retry(retries=3, delay=1.0)

                if error:
                    yield {loading_indicator: gr.update(visible=False), error_display: gr.update(visible=True, value=f"**错误:** {error}"), html_output: gr.update(value="<p>加载失败，请检查网络连接后重试</p>")}
                    return

                nodes = data.get("cluster_nodes", [])

                if not nodes:
                    yield {loading_indicator: gr.update(visible=False), error_display: gr.update(visible=False), html_output: gr.update(value="<p>无可用主机（Ray 集群未启动）</p>")}
                    return

                cards = []
                for node in nodes:
                    resources = node.get("resources", {})
                    cards.append(_render_host_card(
                        hostname=node.get("hostname"),
                        ip=node.get("ip", ""),
                        status=node.get("status", "offline"),
                        gpu=resources.get("gpu", {}),
                        cpu=resources.get("cpu", {}),
                        memory=resources.get("memory", {}),
                        disk=resources.get("disk", {}),
                        swap=resources.get("swap", {}),
                        is_local=node.get("is_local", False),
                    ))

                from datetime import datetime
                now = datetime.now().strftime("%H:%M:%S")
                yield {
                    loading_indicator: gr.update(visible=False),
                    error_display: gr.update(visible=False),
                    html_output: gr.update(value="\n".join(cards)),
                    last_updated: gr.update(visible=True, value=f"<p style='color:#6b7280;font-size:12px'>最后更新: {now}</p>")
                }
            except RuntimeError as e:
                print(f"Error loading hosts: {e}")
                yield {loading_indicator: gr.update(visible=False), error_display: gr.update(visible=True, value=f"**错误:** {str(e)}"), html_output: gr.update(value="<p>加载失败，请稍后重试</p>")}
            except Exception as e:
                print(f"Unexpected error loading hosts: {e}")
                yield {loading_indicator: gr.update(visible=False), error_display: gr.update(visible=True, value="**加载失败，请稍后重试**"), html_output: gr.update(value="<p>加载失败，请稍后重试</p>")}

        def toggle_auto_refresh(enabled: bool, interval: float):
            """Toggle auto-refresh on/off."""
            global _refresh_active, _refresh_thread

            if enabled:
                _refresh_active = True
                # Start background thread for auto-refresh
                def auto_refresh_loop():
                    while _refresh_active:
                        time.sleep(interval)
                        if not _refresh_active:
                            break
                        # Trigger refresh via JavaScript would be complex in Gradio
                        # Instead, we'll rely on the interval setting
                _refresh_thread = threading.Thread(target=auto_refresh_loop, daemon=True)
                _refresh_thread.start()
            else:
                _refresh_active = False

            return {loading_indicator: gr.update(visible=False)}

        def update_interval_value(interval: float) -> float:
            """Validate and return interval value."""
            if interval < 5:
                return 5.0  # Minimum 5 seconds
            return interval

        refresh_btn.click(
            load_hosts_with_state,
            outputs=[loading_indicator, error_display, html_output, last_updated],
        )

        auto_refresh.change(
            toggle_auto_refresh,
            inputs=[auto_refresh, interval_display],
            outputs=[loading_indicator],
        )

        interval_display.change(
            update_interval_value,
            inputs=[interval_display],
            outputs=[interval_display],
        )

        return html_output, refresh_btn, loading_indicator, error_display


def load_hosts() -> str:
    """Load hosts status and return HTML cards."""
    try:
        data = get_hosts_status()
        nodes = data.get("cluster_nodes", [])

        if not nodes:
            return "<p>无可用主机（Ray 集群未启动）</p>"

        cards = []
        for node in nodes:
            resources = node.get("resources", {})
            cards.append(_render_host_card(
                hostname=node.get("hostname"),
                ip=node.get("ip", ""),
                status=node.get("status", "offline"),
                gpu=resources.get("gpu", {}),
                cpu=resources.get("cpu", {}),
                memory=resources.get("memory", {}),
                disk=resources.get("disk", {}),
                swap=resources.get("swap", {}),
                is_local=node.get("is_local", False),
            ))

        return "\n".join(cards)
    except RuntimeError as e:
        print(f"Error loading hosts: {e}")
        return "<p>加载失败，请稍后重试</p>"
