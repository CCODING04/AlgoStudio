import gradio as gr
from algo_studio.web.client import get_tasks


def make_page():
    """Build the Dashboard page."""
    with gr.Column():
        gr.Markdown("## 仪表盘")
        loading_indicator = gr.Markdown("加载中...", visible=False)
        error_display = gr.Markdown("", visible=False)

        with gr.Row():
            total_box = gr.Number(label="任务总数", interactive=False)
            running_box = gr.Number(label="训练中", interactive=False)
            pending_box = gr.Number(label="待处理", interactive=False)
            failed_box = gr.Number(label="失败", interactive=False)

        refresh_btn = gr.Button("刷新", variant="primary")

        def load_stats():
            """Load dashboard statistics with error handling."""
            try:
                yield {loading_indicator: gr.update(visible=True), error_display: gr.update(visible=False)}
                data = get_tasks()
                tasks = data.get("tasks", [])
                total = len(tasks)
                running = sum(1 for t in tasks if t.get("status") == "running")
                pending = sum(1 for t in tasks if t.get("status") == "pending")
                failed = sum(1 for t in tasks if t.get("status") == "failed")
                yield {loading_indicator: gr.update(visible=False), error_display: gr.update(visible=False), total_box: gr.update(value=total), running_box: gr.update(value=running), pending_box: gr.update(value=pending), failed_box: gr.update(value=failed)}
            except RuntimeError as e:
                print(f"Error loading stats: {e}")
                yield {loading_indicator: gr.update(visible=False), error_display: gr.update(visible=True, value=f"**错误:** {str(e)}"), total_box: gr.update(value=-1), running_box: gr.update(value=-1), pending_box: gr.update(value=-1), failed_box: gr.update(value=-1)}
            except Exception as e:
                print(f"Unexpected error loading stats: {e}")
                yield {loading_indicator: gr.update(visible=False), error_display: gr.update(visible=True, value="**加载失败，请稍后重试**"), total_box: gr.update(value=-1), running_box: gr.update(value=-1), pending_box: gr.update(value=-1), failed_box: gr.update(value=-1)}

        refresh_btn.click(
            load_stats,
            outputs=[loading_indicator, error_display, total_box, running_box, pending_box, failed_box]
        )

        return refresh_btn, total_box, running_box, pending_box, failed_box
