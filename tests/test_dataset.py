import pytest
import tempfile
import os
from algo_studio.core.dataset import DatasetManager

def test_dataset_manager_initialization():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = DatasetManager(base_path=tmpdir)
        assert manager.base_path == tmpdir

def test_dataset_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试数据集目录
        os.makedirs(os.path.join(tmpdir, "dataset_v1"))
        os.makedirs(os.path.join(tmpdir, "dataset_v2"))

        manager = DatasetManager(base_path=tmpdir)
        datasets = manager.list_datasets()
        assert len(datasets) == 2