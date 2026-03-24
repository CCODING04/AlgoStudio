import gradio as gr
from algo_studio.web.client import get_tasks


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

        def load_stats():
            try:
                data = get_tasks()
                tasks = data.get("tasks", [])
                total = len(tasks)
                running = sum(1 for t in tasks if t.get("status") == "running")
                pending = sum(1 for t in tasks if t.get("status") == "pending")
                failed = sum(1 for t in tasks if t.get("status") == "failed")
                return total, running, pending, failed
            except Exception as e:
                print(f"Error loading stats: {e}")
                return -1, -1, -1, -1

        refresh_btn.click(
            load_stats,
            outputs=[total_box, running_box, pending_box, failed_box]
        )

        return refresh_btn, total_box, running_box, pending_box, failed_box
