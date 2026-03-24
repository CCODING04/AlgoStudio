import gradio as gr
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
