import html

import gradio as gr
from algo_studio.web.client import get_hosts_status


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
    gpu_used = float(gpu.get("used", 0) or 0)

    cpu_total = float(cpu.get("total", 0) or 0)
    cpu_used = float(cpu.get("used", 0) or 0)

    mem_total = _parse_size(memory.get("total", "0Gi"))
    mem_used = _parse_size(memory.get("used", "0Gi"))

    disk_total = _parse_size(disk.get("total", "0G"))
    disk_used = _parse_size(disk.get("used", "0G"))

    swap_total = _parse_size(swap.get("total", "0Gi"))
    swap_used = _parse_size(swap.get("used", "0Gi"))

    return f"""
    <div style="{border_style}border-radius:8px;padding:16px;margin:8px 0;background:#fafafa">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <strong style="font-size:15px">{hostname_esc} {label}</strong>
            <span>{status_icon} {status_display}</span>
        </div>
        <div style="font-size:12px;color:#6b7280;margin-bottom:12px">IP: {ip_esc}</div>
        <div style="font-size:13px;margin-bottom:8px">
            <strong>GPU {f'({gpu_name})' if gpu_name != '无' else ''}</strong>
            {_bar(gpu_used, gpu_total)}
        </div>
        <div style="font-size:13px;margin-bottom:8px">
            <strong>CPU</strong>
            {_bar(cpu_used, cpu_total)}
        </div>
        <div style="font-size:13px;margin-bottom:8px">
            <strong>Memory</strong>
            {_bar(mem_used, mem_total, unit="Gi")}
        </div>
        <div style="font-size:13px;margin-bottom:8px">
            <strong>Disk</strong>
            {_bar(disk_used, disk_total, unit="G")}
        </div>
        <div style="font-size:13px">
            <strong>Swap</strong>
            {_bar(swap_used, swap_total, unit="Gi")}
        </div>
    </div>
    """


def make_page():
    """Build the Hosts monitoring page."""
    with gr.Column():
        gr.Markdown("## 主机监控")
        refresh_btn = gr.Button("刷新", variant="primary")
        html_output = gr.HTML(label="主机状态", value="<p>点击刷新以加载数据</p>")

        refresh_btn.click(fn=load_hosts, outputs=[html_output])

        return html_output, refresh_btn


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
