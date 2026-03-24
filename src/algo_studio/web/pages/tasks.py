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

        tasks_table = gr.Dataframe(
            headers=["task_id", "task_type", "algorithm_name", "algorithm_version", "status", "created_at", "assigned_node"],
            label="任务列表",
            interactive=False,
        )

        def load_tasks(status_filter: str = "全部"):
            try:
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
            except RuntimeError as e:
                print(f"Error loading tasks: {e}")
                return []

        refresh_btn.click(
            load_tasks,
            inputs=[filter_status],
            outputs=[tasks_table],
        )
        filter_status.change(
            load_tasks,
            inputs=[filter_status],
            outputs=[tasks_table],
        )

        return tasks_table, refresh_btn, filter_status
