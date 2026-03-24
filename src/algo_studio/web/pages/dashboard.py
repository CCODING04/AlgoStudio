import gradio as gr
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