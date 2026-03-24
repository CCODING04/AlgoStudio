import requests
from algo_studio.web.config import API_BASE


def _get(url: str, error_msg: str) -> dict:
    """Internal GET helper."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"{error_msg}: {e}") from e


def get_tasks() -> dict:
    """Fetch all tasks from the API."""
    return _get(f"{API_BASE}/api/tasks", "Failed to fetch tasks")


def get_hosts_status() -> dict:
    """Fetch cluster and local host status from the API."""
    return _get(f"{API_BASE}/api/hosts/status", "Failed to fetch hosts status")
