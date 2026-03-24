import json
import os
from dataclasses import dataclass
from typing import Any

@dataclass
class AlgorithmVersion:
    name: str
    version: str
    path: str
    metadata: dict[str, Any]

class AlgorithmWarehouse:
    """算法仓库 - 管理算法注册、版本、查找"""

    def __init__(self, base_path: str = "/algorithms"):
        self.base_path = base_path
        self._index: dict[str, AlgorithmVersion] = {}

    def register(self, name: str, version: str, path: str):
        """注册新算法版本"""
        metadata_path = os.path.join(path, "metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path) as f:
                metadata = json.load(f)
        else:
            metadata = {"name": name, "version": version}

        version_info = AlgorithmVersion(
            name=name,
            version=version,
            path=path,
            metadata=metadata
        )
        key = f"{name}:{version}"
        self._index[key] = version_info

    def list_versions(self, name: str) -> list[AlgorithmVersion]:
        """列出某算法的所有版本"""
        return [v for v in self._index.values() if v.name == name]

    def get_version(self, name: str, version: str) -> AlgorithmVersion | None:
        """获取指定版本"""
        key = f"{name}:{version}"
        return self._index.get(key)

    def list_algorithms(self) -> list[str]:
        """列出所有算法"""
        return list(set(v.name for v in self._index.values()))

    def rebuild_index(self):
        """从文件系统重建索引"""
        self._index = {}
        if not os.path.exists(self.base_path):
            return

        for algo_name in os.listdir(self.base_path):
            algo_dir = os.path.join(self.base_path, algo_name)
            if not os.path.isdir(algo_dir):
                continue

            for version in os.listdir(algo_dir):
                version_dir = os.path.join(algo_dir, version)
                if not os.path.isdir(version_dir):
                    continue

                metadata_path = os.path.join(version_dir, "metadata.json")
                if os.path.exists(metadata_path):
                    with open(metadata_path) as f:
                        metadata = json.load(f)
                else:
                    metadata = {}

                key = f"{algo_name}:{version}"
                self._index[key] = AlgorithmVersion(
                    name=algo_name,
                    version=version,
                    path=version_dir,
                    metadata=metadata
                )