import click
import requests
import json
import os

API_BASE = os.environ.get("ALGO_STUDIO_API", "http://localhost:8000")

@click.group()
@click.version_option(version="0.1.0")
def cli():
    """AlgoStudio CLI - AI Algorithm Platform"""
    pass

@cli.group()
def task():
    """Task management commands"""
    pass

@task.command("list")
@click.option("--status", help="Filter by status")
def task_list(status):
    """List all tasks"""
    url = f"{API_BASE}/api/tasks"
    if status:
        url += f"?status={status}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        click.echo(f"Total: {data['total']}")
        for t in data["tasks"]:
            click.echo(f"  {t['task_id']} | {t['task_type']} | {t['status']} | {t['algorithm_name']}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@task.command("submit")
@click.option("--type", "task_type", required=True, help="train/infer/verify")
@click.option("--algo", "algorithm_name", required=True, help="Algorithm name")
@click.option("--version", "algorithm_version", required=True, help="Algorithm version")
@click.option("--config", help="Config JSON string")
def task_submit(task_type, algorithm_name, algorithm_version, config):
    """Submit a new task"""
    config_dict = json.loads(config) if config else {}

    try:
        response = requests.post(
            f"{API_BASE}/api/tasks",
            json={
                "task_type": task_type,
                "algorithm_name": algorithm_name,
                "algorithm_version": algorithm_version,
                "config": config_dict
            }
        )
        response.raise_for_status()
        data = response.json()
        click.echo(f"Task created: {data['task_id']}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@task.command("status")
@click.argument("task_id")
def task_status(task_id):
    """Get task status"""
    try:
        response = requests.get(f"{API_BASE}/api/tasks/{task_id}")
        response.raise_for_status()
        data = response.json()
        click.echo(json.dumps(data, indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

# 直接提交训练/推理/验证的便捷命令
@cli.command("train")
@click.option("--algo", "algorithm_name", required=True, help="Algorithm name")
@click.option("--version", "algorithm_version", default="latest", help="Algorithm version")
@click.option("--data", "data_path", required=True, help="Dataset path")
@click.option("--epochs", default=100, help="Number of epochs")
def train(algorithm_name, algorithm_version, data_path, epochs):
    """Submit a training task"""
    config = {"data": data_path, "epochs": epochs}
    try:
        response = requests.post(
            f"{API_BASE}/api/tasks",
            json={
                "task_type": "train",
                "algorithm_name": algorithm_name,
                "algorithm_version": algorithm_version,
                "config": config
            }
        )
        response.raise_for_status()
        data = response.json()
        click.echo(f"Training task created: {data['task_id']}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@cli.command("infer")
@click.option("--algo", "algorithm_name", required=True, help="Algorithm name")
@click.option("--version", "algorithm_version", default="latest", help="Algorithm version")
@click.option("--input", "input_path", required=True, help="Input data path")
@click.option("--output", "output_path", default=None, help="Output result path")
def infer(algorithm_name, algorithm_version, input_path, output_path):
    """Submit an inference task"""
    config = {"input": input_path, "output": output_path}
    try:
        response = requests.post(
            f"{API_BASE}/api/tasks",
            json={
                "task_type": "infer",
                "algorithm_name": algorithm_name,
                "algorithm_version": algorithm_version,
                "config": config
            }
        )
        response.raise_for_status()
        data = response.json()
        click.echo(f"Inference task created: {data['task_id']}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@cli.command("log")
@click.option("--iteration", "iteration_id", default=None, help="Specific iteration ID")
@click.option("--algo", "algorithm_name", default=None, help="Filter by algorithm name")
def log(iteration_id, algorithm_name):
    """View evolution logs"""
    # TODO: 实现从 Git 仓库读取演进日志
    click.echo("Evolution logs:")
    click.echo("  (Not yet implemented - will read from evolution/ logs directory)")

@cli.group()
def host():
    """Host management commands"""
    pass

@host.command("status")
def host_status():
    """Get host status"""
    try:
        response = requests.get(f"{API_BASE}/api/hosts")
        response.raise_for_status()
        data = response.json()
        click.echo(json.dumps(data, indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

if __name__ == "__main__":
    cli()