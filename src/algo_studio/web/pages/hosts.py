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


def _render_host_card(hostname: str, ip: str, status: str, resources: dict, is_local: bool = False) -> str:
    """Render one host as an HTML card string."""
    hostname = html.escape(str(hostname))
    ip = html.escape(str(ip))
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

    def parse_val(s, unit=""):
        try:
            return float(str(s).rstrip("GiG"))
        except (ValueError, TypeError):
            return 0.0

    gpu_name = html.escape(str(gpu.get("name", "N/A")))
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

        refresh_btn.click(fn=load_hosts, outputs=[html_output])

        return html_output, refresh_btn, auto_refresh


def load_hosts() -> str:
    """Load hosts status and return HTML cards."""
    try:
        data = get_hosts_status()
        nodes = data.get("cluster_nodes", [])
        local = data.get("local_host", {})

        cards = []
        if local.get("hostname"):
            cards.append(_render_host_card(
                hostname=local.get("hostname", ""),
                ip=local.get("ip", ""),
                status=local.get("status", "offline"),
                resources=local.get("resources", {}),
                is_local=True,
            ))
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
    except RuntimeError as e:
        print(f"Error loading hosts: {e}")
        return "<p>加载失败，请稍后重试</p>"
