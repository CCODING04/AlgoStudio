import os
import subprocess
from dataclasses import dataclass
from typing import Any

@dataclass
class DatasetInfo:
    name: str
    path: str
    version: str | None
    size_gb: float | None

class DatasetManager:
    """数据集管理 - 使用 DVC 进行版本控制"""

    def __init__(self, base_path: str = "/nas/datasets"):
        self.base_path = base_path

    def list_datasets(self) -> list[DatasetInfo]:
        """列出所有数据集"""
        datasets = []
        if not os.path.exists(self.base_path):
            return datasets

        for name in os.listdir(self.base_path):
            path = os.path.join(self.base_path, name)
            if not os.path.isdir(path):
                continue

            # 尝试获取 DVC 版本
            version = self._get_dvc_version(path)

            # 计算大小
            size_gb = self._calculate_size(path)

            datasets.append(DatasetInfo(
                name=name,
                path=path,
                version=version,
                size_gb=size_gb
            ))
        return datasets

    def _get_dvc_version(self, path: str) -> str | None:
        """获取 DVC 跟踪的版本（数据集的 Git commit hash）"""
        try:
            # 使用 git rev-parse 获取数据集的版本（commit hash）
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()[:8]  # 返回短 hash
        except:
            pass
        return None

    def _calculate_size(self, path: str) -> float | None:
        """计算目录大小（GB）"""
        total = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total += os.path.getsize(fp)
            return round(total / (1024**3), 2)
        except:
            return None

    def add_dataset(self, name: str, path: str):
        """添加数据集到 DVC"""
        dataset_path = os.path.join(self.base_path, name)
        os.makedirs(dataset_path, exist_ok=True)

        # 拷贝数据
        import shutil
        shutil.copytree(path, os.path.join(dataset_path, "data"), dirs_exist_ok=True)

        # 初始化 DVC
        subprocess.run(["dvc", "init"], cwd=dataset_path, check=True)
        subprocess.run(["dvc", "add", "data"], cwd=dataset_path, check=True)