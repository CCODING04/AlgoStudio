# src/algo_studio/core/ray_compat.py

"""
Ray Dashboard API 版本兼容性处理模块

不同 Ray 版本的 API 路径和响应格式可能存在差异，
此类提供统一的兼容处理。
"""

from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Ray 版本到 API 路径的映射
RAY_VERSION_API_PATHS = {
    # (min_version, max_version): {api_name: path}
    (2, 5): {
        "actors": "/api/v0/actors",
        "tasks": "/api/v0/tasks",
        "nodes": "/api/v0/nodes",
        "jobs": "/api/v0/jobs",
        "health": "/api/gcs_healthz",
    },
    (2, 6): {
        "actors": "/api/v0/actors",
        "tasks": "/api/v0/tasks",
        "nodes": "/api/v0/nodes",
        "jobs": "/api/v0/jobs",
        "health": "/api/gcs_healthz",
    },
    (2, 8): {
        "actors": "/api/v0/actors",
        "tasks": "/api/v0/tasks",
        "nodes": "/nodes",
        "jobs": "/api/v0/jobs",
        "health": "/api/gcs_healthz",
    },
}


class RayAPICompat:
    """Ray API 版本兼容性处理类"""

    def __init__(self, ray_version: str):
        """
        Args:
            ray_version: Ray 版本号，如 "2.5.0", "2.6.3"
        """
        self.ray_version = ray_version
        self._version_tuple = self._parse_version(ray_version)
        self._api_paths = self._get_api_paths()

    def _parse_version(self, version: str) -> tuple:
        """解析版本号为元组"""
        parts = version.split(".")
        return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)

    def _get_api_paths(self) -> Dict[str, str]:
        """获取当前版本对应的 API 路径"""
        for (min_ver, max_ver), paths in RAY_VERSION_API_PATHS.items():
            if min_ver <= self._version_tuple[0] < max_ver:
                return paths

        # 默认返回 2.5+ 的路径
        return RAY_VERSION_API_PATHS[(2, 5)]

    def get_path(self, api_name: str) -> str:
        """获取指定 API 的路径"""
        return self._api_paths.get(api_name, f"/api/v0/{api_name}")

    def get_actors_path(self) -> str:
        return self.get_path("actors")

    def get_tasks_path(self) -> str:
        return self.get_path("tasks")

    def get_nodes_path(self) -> str:
        return self.get_path("nodes")

    def get_jobs_path(self) -> str:
        return self.get_path("jobs")

    def get_health_path(self) -> str:
        return self.get_path("health")


def detect_ray_version() -> Optional[str]:
    """尝试检测 Ray 版本"""
    try:
        import ray
        return ray.__version__
    except ImportError:
        return None