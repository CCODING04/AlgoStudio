import gradio as gr
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

        # Loading indicator
        loading_indicator = gr.Markdown("加载中...", visible=False)
        error_display = gr.Markdown("", visible=False)

        tasks_table = gr.Dataframe(
            headers=["task_id", "task_type", "algorithm_name", "algorithm_version", "status", "progress", "created_at", "assigned_node"],
            label="任务列表",
            interactive=False,
        )

        def load_tasks(status_filter: str = "全部", show_loading: bool = True):
            """Load tasks with loading state management."""
            try:
                # Show loading indicator
                if show_loading:
                    yield {loading_indicator: gr.update(visible=True), error_display: gr.update(visible=False), tasks_table: gr.update(value=[])}

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
                        f"{t.get('progress', 0)}%",
                        str(t.get("created_at", "")),
                        t.get("assigned_node") or "",
                    ]
                    for t in tasks
                ]
                # Hide loading, show data
                yield {loading_indicator: gr.update(visible=False), error_display: gr.update(visible=False), tasks_table: gr.update(value=rows)}
            except RuntimeError as e:
                print(f"Error loading tasks: {e}")
                # Hide loading, show error
                yield {loading_indicator: gr.update(visible=False), error_display: gr.update(visible=True, value=f"**错误:** {str(e)}"), tasks_table: gr.update(value=[])}
            except Exception as e:
                print(f"Unexpected error loading tasks: {e}")
                yield {loading_indicator: gr.update(visible=False), error_display: gr.update(visible=True, value="**加载失败，请稍后重试**"), tasks_table: gr.update(value=[])}

        def on_filter_change(status_filter: str):
            """Handle filter change with loading state."""
            yield {loading_indicator: gr.update(visible=True), error_display: gr.update(visible=False)}
            yield from load_tasks(status_filter, show_loading=True)

        refresh_btn.click(
            lambda status: load_tasks(status, show_loading=True),
            inputs=[filter_status],
            outputs=[loading_indicator, error_display, tasks_table],
        )
        filter_status.change(
            on_filter_change,
            inputs=[filter_status],
            outputs=[loading_indicator, error_display, tasks_table],
        )

        return tasks_table, refresh_btn, filter_status
