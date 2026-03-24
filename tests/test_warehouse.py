import pytest
import tempfile
import os
from algo_studio.core.warehouse import AlgorithmWarehouse, AlgorithmVersion

def test_algorithm_version_dataclass():
    version = AlgorithmVersion(
        name="yolo",
        version="v1.0.0",
        path="/algorithms/yolo/v1.0.0",
        metadata={"task_type": "object_detection", "deployment": "edge"}
    )
    assert version.name == "yolo"
    assert version.version == "v1.0.0"

def test_algorithm_warehouse_register():
    with tempfile.TemporaryDirectory() as tmpdir:
        warehouse = AlgorithmWarehouse(base_path=tmpdir)
        algo_path = os.path.join(tmpdir, "yolo/v1.0.0")
        os.makedirs(algo_path)

        # 创建 metadata.json
        import json
        with open(os.path.join(algo_path, "metadata.json"), "w") as f:
            json.dump({"name": "yolo", "version": "v1.0.0", "task_type": "object_detection"}, f)

        warehouse.register("yolo", "v1.0.0", algo_path)
        versions = warehouse.list_versions("yolo")
        assert len(versions) == 1
        assert versions[0].version == "v1.0.0"