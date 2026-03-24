# AlgoStudio Phase 1 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 AI 算法平台的基础设施，包括 Ray Cluster 多机调度、算法仓库、训练/推理任务提交、主机状态监控。

**Architecture:** 采用三层架构（交互层 → API/调度层 → 执行层），Ray 作为任务调度核心，算法以 Git 仓库形式管理，通过统一接口规范实现训练/推理/验证。

**Tech Stack:** Python 3.10+, Ray, FastAPI, Redis/RQ, DVC, Click

---

## 项目文件结构

```
algo-studio/
├── src/
│   └── algo_studio/
│       ├── __init__.py
│       ├── api/                    # API 层
│       │   ├── __init__.py
│       │   ├── main.py             # FastAPI 入口
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── tasks.py        # 任务管理
│       │   │   ├── algorithms.py    # 算法管理
│       │   │   └── hosts.py        # 主机管理
│       │   └── models.py           # Pydantic 模型
│       │
│       ├── core/                   # 核心逻辑
│       │   ├── __init__.py
│       │   ├── algorithm.py        # 算法接口定义
│       │   ├── task.py             # 任务调度
│       │   └── ray_client.py       # Ray 客户端
│       │
│       ├── cli/                    # CLI 工具
│       │   ├── __init__.py
│       │   └── main.py             # Click CLI
│       │
│       └── monitor/                # 监控模块
│           ├── __init__.py
│           └── host_monitor.py     # 主机状态监控
│
├── algorithms/                    # 算法仓库（开发时挂载）
│   └── placeholder.txt
│
├── tests/
│   ├── __init__.py
│   ├── test_algorithm_interface.py
│   ├── test_task_submission.py
│   └── test_host_monitor.py
│
├── docs/
│   └── algorithm_interface_spec.md  # 算法接口规范文档
│
├── scripts/
│   └── setup_ray_cluster.sh        # Ray 集群初始化脚本
│
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## Task 1: 项目脚手架搭建

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `README.md`
- Create: `src/algo_studio/__init__.py`
- Create: `src/algo_studio/api/__init__.py`
- Create: `src/algo_studio/core/__init__.py`
- Create: `src/algo_studio/cli/__init__.py`
- Create: `src/algo_studio/monitor/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "algo-studio"
version = "0.1.0"
description = "AI Algorithm Platform with Auto-Evolution"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "ray[default]>=2.9.0",
    "pydantic>=2.5.0",
    "click>=8.1.0",
    "redis>=5.0.0",
    "numpy>=1.26.0",
    "pyyaml>=6.0.0",
    "psutil>=5.9.0",
    "pynvml>=11.5.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
    "httpx>=0.26.0",
]

[project.scripts]
algo = "algo_studio.cli.main:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: 创建 requirements.txt**

```
fastapi>=0.109.0
uvicorn>=0.27.0
ray[default]>=2.9.0
pydantic>=2.5.0
click>=8.1.0
redis>=5.0.0
numpy>=1.26.0
pyyaml>=6.0.0
psutil>=5.9.0
pynvml>=11.5.0
```

- [ ] **Step 3: 创建目录结构**

```bash
mkdir -p src/algo_studio/api/routes
mkdir -p src/algo_studio/core
mkdir -p src/algo_studio/cli
mkdir -p src/algo_studio/monitor
mkdir -p tests
mkdir -p algorithms
mkdir -p scripts
mkdir -p docs
```

- [ ] **Step 4: 创建空的 __init__.py 文件**

```bash
touch src/algo_studio/__init__.py
touch src/algo_studio/api/__init__.py
touch src/algo_studio/api/routes/__init__.py
touch src/algo_studio/core/__init__.py
touch src/algo_studio/cli/__init__.py
touch src/algo_studio/monitor/__init__.py
touch tests/__init__.py
```

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "chore: initial project scaffold"
```

---

## Task 2: 算法接口定义

**Files:**
- Create: `src/algo_studio/core/algorithm.py`
- Create: `tests/test_algorithm_interface.py`
- Create: `docs/algorithm_interface_spec.md`

- [ ] **Step 1: 编写算法接口测试**

```python
# tests/test_algorithm_interface.py
import pytest
from algo_studio.core.algorithm import AlgorithmInterface, TrainResult, InferenceResult, VerificationResult, AlgorithmMetadata

def test_train_result_dataclass():
    result = TrainResult(
        success=True,
        model_path="/path/to/model.pt",
        metrics={"mAP": 0.78, "FPS": 35}
    )
    assert result.success is True
    assert result.model_path == "/path/to/model.pt"
    assert result.metrics["mAP"] == 0.78

def test_inference_result_dataclass():
    result = InferenceResult(
        success=True,
        outputs=[{"class": "dog", "confidence": 0.95}],
        latency_ms=12.5
    )
    assert result.success is True
    assert len(result.outputs) == 1

def test_algorithm_metadata_dataclass():
    metadata = AlgorithmMetadata(
        name="yolo_family",
        version="v1.0.0",
        task_type="object_detection",
        deployment="edge",
        expected_fps=30
    )
    assert metadata.name == "yolo_family"
    assert metadata.task_type == "object_detection"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_algorithm_interface.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现算法接口**

```python
# src/algo_studio/core/algorithm.py
from dataclasses import dataclass
from typing import Any

@dataclass
class TrainResult:
    success: bool
    model_path: str | None = None
    metrics: dict[str, Any] | None = None
    error: str | None = None

@dataclass
class InferenceResult:
    success: bool
    outputs: list[dict[str, Any]] | None = None
    latency_ms: float | None = None
    error: str | None = None

@dataclass
class VerificationResult:
    success: bool
    passed: bool
    metrics: dict[str, Any] | None = None
    details: str | None = None

@dataclass
class AlgorithmMetadata:
    name: str
    version: str
    task_type: str
    deployment: str  # "edge" | "cloud"
    expected_fps: int | None = None

class AlgorithmInterface:
    """算法接口基类，所有算法必须实现此接口"""

    def train(self, data_path: str, config: dict) -> TrainResult:
        """训练接口"""
        raise NotImplementedError

    def infer(self, inputs: list) -> InferenceResult:
        """推理接口"""
        raise NotImplementedError

    def verify(self, test_data: str) -> VerificationResult:
        """验证接口"""
        raise NotImplementedError

    @staticmethod
    def get_metadata() -> AlgorithmMetadata:
        """返回算法元信息"""
        raise NotImplementedError
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_algorithm_interface.py -v`
Expected: PASS

- [ ] **Step 5: 编写接口规范文档**

```markdown
# 算法接口规范

## 必须实现的方法

### train(data_path: str, config: dict) -> TrainResult
- `data_path`: 训练数据集路径
- `config`: 训练配置（epochs, batch_size 等）
- 返回训练结果和指标

### infer(inputs: list) -> InferenceResult
- `inputs`: 输入数据列表
- 返回推理结果和延迟

### verify(test_data: str) -> VerificationResult
- `test_data`: 测试数据集路径
- 返回验证是否通过

### get_metadata() -> AlgorithmMetadata
- 返回算法元信息
```

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "feat: add algorithm interface definitions"
```

---

## Task 3: Ray 集群客户端

**Files:**
- Create: `src/algo_studio/core/ray_client.py`
- Create: `tests/test_ray_client.py`

- [ ] **Step 1: 编写 Ray 客户端测试**

```python
# tests/test_ray_client.py
import pytest
from unittest.mock import patch, MagicMock
from algo_studio.core.ray_client import RayClient, NodeStatus

def test_node_status_dataclass():
    status = NodeStatus(
        node_id="worker-1",
        ip="192.168.0.101",
        status="idle",
        cpu_used=8,
        cpu_total=24,
        gpu_used=0,
        gpu_total=1,
        memory_used_gb=16,
        memory_total_gb=31,
        disk_used_gb=320,
        disk_total_gb=1800
    )
    assert status.node_id == "worker-1"
    assert status.status == "idle"
    assert status.gpu_available

def test_ray_client_initialization():
    with patch("ray_client.ray") as mock_ray:
        client = RayClient()
        assert client.head_address is None
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_ray_client.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 Ray 客户端**

```python
# src/algo_studio/core/ray_client.py
from dataclasses import dataclass
from typing import Any
import ray

# GPU 可用性检测
try:
    import pynvml
    pynvml.nvmlInit()
    GPU_AVAILABLE = True
except:
    GPU_AVAILABLE = False

@dataclass
class NodeStatus:
    node_id: str
    ip: str
    status: str  # "idle" | "busy" | "offline"
    cpu_used: int
    cpu_total: int
    gpu_used: int
    gpu_total: int
    memory_used_gb: float
    memory_total_gb: float
    disk_used_gb: float
    disk_total_gb: float
    swap_used_gb: float = 0.0
    swap_total_gb: float = 0.0

    @property
    def cpu_available(self) -> int:
        return self.cpu_total - self.cpu_used

    @property
    def gpu_available(self) -> int:
        return self.gpu_total - self.gpu_used

    @property
    def memory_available_gb(self) -> float:
        return self.memory_total_gb - self.memory_used_gb

class RayClient:
    def __init__(self, head_address: str | None = None):
        self.head_address = head_address
        if head_address:
            ray.init(address=head_address)
        else:
            ray.init()

    def get_nodes(self) -> list[NodeStatus]:
        """获取所有节点状态"""
        import psutil
        nodes = []

        for node in ray.nodes():
            resources = node.get("resources", {})
            is_alive = node.get("Alive", False)

            # 获取本机硬件信息用于补充 Ray 节点信息
            cpu_count = psutil.cpu_count()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            status = NodeStatus(
                node_id=node["NodeID"],
                ip=node.get("NodeName", "unknown"),
                status="idle" if is_alive else "offline",
                cpu_used=int(resources.get("CPU", 0)),
                cpu_total=cpu_count,
                gpu_used=int(resources.get("GPU", 0)),
                gpu_total=1 if GPU_AVAILABLE else 0,  # 简化假设每机单卡
                memory_used_gb=round(memory.used / (1024**3), 1),
                memory_total_gb=round(memory.total / (1024**3), 1),
                disk_used_gb=round(disk.used / (1024**3), 1),
                disk_total_gb=round(disk.total / (1024**3), 1),
                swap_used_gb=round(psutil.swap_memory().used / (1024**3), 1),
                swap_total_gb=round(psutil.swap_memory().total / (1024**3), 1)
            )
            nodes.append(status)
        return nodes

    def submit_task(self, func, *args, **kwargs):
        """提交任务到 Ray 集群"""
        return func.options(
            num_cpus=kwargs.get("num_cpus", 1),
            num_gpus=kwargs.get("num_gpus", 0),
            resources=kwargs.get("resources", {})
        ).remote(*args)

    def shutdown(self):
        """关闭 Ray 连接"""
        ray.shutdown()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_ray_client.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat: add Ray client for cluster management"
```

---

## Task 4: 任务调度模块

**Files:**
- Create: `src/algo_studio/core/task.py`
- Create: `tests/test_task.py`

- [ ] **Step 1: 编写任务调度测试**

```python
# tests/test_task.py
import pytest
from algo_studio.core.task import Task, TaskStatus, TaskType, TaskManager

def test_task_dataclass():
    task = Task(
        task_id="task-001",
        task_type=TaskType.TRAIN,
        algorithm_name="yolo",
        algorithm_version="v1.0.0",
        status=TaskStatus.PENDING
    )
    assert task.task_id == "task-001"
    assert task.task_type == TaskType.TRAIN
    assert task.status == TaskStatus.PENDING

def test_task_status_enum():
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.RUNNING.value == "running"
    assert TaskStatus.COMPLETED.value == "completed"
    assert TaskStatus.FAILED.value == "failed"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_task.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现任务调度模块**

```python
# src/algo_studio/core/task.py
from enum import Enum
from dataclasses import dataclass, field
from typing import Any
import uuid
from datetime import datetime
import ray

class TaskType(Enum):
    TRAIN = "train"
    INFER = "infer"
    VERIFY = "verify"

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Task:
    task_id: str
    task_type: TaskType
    algorithm_name: str
    algorithm_version: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    config: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    assigned_node: str | None = None

    @staticmethod
    def create(task_type: TaskType, algorithm_name: str, algorithm_version: str, config: dict) -> "Task":
        """创建新任务"""
        task_id = f"{task_type.value}-{uuid.uuid4().hex[:8]}"
        return Task(
            task_id=task_id,
            task_type=task_type,
            algorithm_name=algorithm_name,
            algorithm_version=algorithm_version,
            config=config
        )

class TaskManager:
    """任务管理器

    Phase 1: 使用内存存储（单实例部署）
    Phase 2: 集成 Redis/RQ 实现分布式任务队列
    """

    def __init__(self):
        self._tasks: dict[str, Task] = {}

    def create_task(self, task_type: TaskType, algorithm_name: str, algorithm_version: str, config: dict) -> Task:
        """创建并注册新任务"""
        task = Task.create(task_type, algorithm_name, algorithm_version, config)
        self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> Task | None:
        """获取任务"""
        return self._tasks.get(task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """列出任务"""
        if status:
            return [t for t in self._tasks.values() if t.status == status]
        return list(self._tasks.values())

    def update_status(self, task_id: str, status: TaskStatus, result: dict | None = None, error: str | None = None):
        """更新任务状态"""
        task = self._tasks.get(task_id)
        if task:
            task.status = status
            if status == TaskStatus.RUNNING:
                task.started_at = datetime.now()
            elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                task.completed_at = datetime.now()
            if result:
                task.result = result
            if error:
                task.error = error

    def dispatch_task(self, task_id: str, ray_client: "RayClient") -> bool:
        """将任务分发到 Ray 集群执行"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        # 获取空闲节点
        nodes = ray_client.get_nodes()
        idle_nodes = [n for n in nodes if n.status == "idle" and n.gpu_available > 0]

        if not idle_nodes:
            # 没有空闲 GPU 节点，尝试 CPU 节点
            idle_nodes = [n for n in nodes if n.status == "idle"]

        if not idle_nodes:
            return False

        # 选择第一个空闲节点
        selected_node = idle_nodes[0]
        task.assigned_node = selected_node.node_id

        # 更新状态为运行中
        self.update_status(task_id, TaskStatus.RUNNING)

        # 根据 task_type 提交到 Ray
        if task.task_type == TaskType.TRAIN:
            ray_client.submit_task(
                run_training,
                task.task_id,
                task.algorithm_name,
                task.algorithm_version,
                task.config,
                num_gpus=1
            )
        elif task.task_type == TaskType.INFER:
            ray_client.submit_task(
                run_inference,
                task.task_id,
                task.algorithm_name,
                task.algorithm_version,
                task.config,
                num_gpus=0
            )
        elif task.task_type == TaskType.VERIFY:
            ray_client.submit_task(
                run_verification,
                task.task_id,
                task.algorithm_name,
                task.algorithm_version,
                task.config,
                num_gpus=0
            )

        return True


# 训练/推理/验证的 Ray 任务函数（实际实现时在 core/ray_tasks.py 中定义）
@ray.remote
def run_training(task_id: str, algo_name: str, algo_version: str, config: dict) -> dict:
    """Ray 训练任务"""
    # TODO: 实际加载算法、执行训练
    # 1. 从 AlgorithmWarehouse 获取算法路径
    # 2. 加载数据
    # 3. 执行训练
    # 4. 返回结果
    return {"task_id": task_id, "status": "completed", "metrics": {"mAP": 0.0}}


@ray.remote
def run_inference(task_id: str, algo_name: str, algo_version: str, config: dict) -> dict:
    """Ray 推理任务"""
    return {"task_id": task_id, "status": "completed", "results": []}


@ray.remote
def run_verification(task_id: str, algo_name: str, algo_version: str, config: dict) -> dict:
    """Ray 验证任务"""
    return {"task_id": task_id, "status": "completed", "passed": True}
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_task.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat: add task scheduling module with Ray integration"
```

---

## Task 5: 算法仓库 (Algorithm Warehouse)

**Files:**
- Create: `src/algo_studio/core/warehouse.py`
- Create: `tests/test_warehouse.py`

- [ ] **Step 1: 编写算法仓库测试**

```python
# tests/test_warehouse.py
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_warehouse.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现算法仓库模块**

```python
# src/algo_studio/core/warehouse.py
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
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_warehouse.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat: add algorithm warehouse for version management"
```

---

## Task 6: DVC 数据集集成

**Files:**
- Create: `src/algo_studio/core/dataset.py`
- Create: `tests/test_dataset.py`

- [ ] **Step 1: 编写数据集测试**

```python
# tests/test_dataset.py
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_dataset.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现数据集管理模块**

```python
# src/algo_studio/core/dataset.py
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
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_dataset.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat: add DVC dataset integration"
```

---

## Task 7: API 路由 - 任务管理

**Files:**
- Create: `src/algo_studio/api/main.py`
- Create: `src/algo_studio/api/routes/tasks.py`
- Create: `src/algo_studio/api/routes/hosts.py`
- Create: `src/algo_studio/api/models.py`
- Create: `tests/test_api_tasks.py`

- [ ] **Step 1: 编写任务 API 测试**

```python
# tests/test_api_tasks.py
import pytest
from httpx import AsyncClient, ASGITransport
from algo_studio.api.main import app

@pytest.mark.asyncio
async def test_create_task():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/tasks",
            json={
                "task_type": "train",
                "algorithm_name": "yolo",
                "algorithm_version": "v1.0.0",
                "config": {"epochs": 100}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] is not None
        assert data["status"] == "pending"

@pytest.mark.asyncio
async def test_list_tasks():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_api_tasks.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 Pydantic 模型**

```python
# src/algo_studio/api/models.py
from pydantic import BaseModel, Field
from typing import Any

class TaskCreateRequest(BaseModel):
    task_type: str = Field(..., description="train/infer/verify")
    algorithm_name: str = Field(..., description="算法名称")
    algorithm_version: str = Field(..., description="算法版本")
    config: dict[str, Any] = Field(default_factory=dict, description="任务配置")

class TaskResponse(BaseModel):
    task_id: str
    task_type: str
    algorithm_name: str
    algorithm_version: str
    status: str
    created_at: str
    assigned_node: str | None = None

class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int
```

- [ ] **Step 4: 实现任务路由**

```python
# src/algo_studio/api/routes/tasks.py
from fastapi import APIRouter, HTTPException
from algo_studio.api.models import TaskCreateRequest, TaskResponse, TaskListResponse
from algo_studio.core.task import TaskManager, TaskType, TaskStatus

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# 全局任务管理器实例
task_manager = TaskManager()

@router.post("", response_model=TaskResponse)
async def create_task(request: TaskCreateRequest):
    """创建新任务"""
    try:
        task_type = TaskType(request.task_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid task_type: {request.task_type}")

    task = task_manager.create_task(
        task_type=task_type,
        algorithm_name=request.algorithm_name,
        algorithm_version=request.algorithm_version,
        config=request.config
    )

    return TaskResponse(
        task_id=task.task_id,
        task_type=task.task_type.value,
        algorithm_name=task.algorithm_name,
        algorithm_version=task.algorithm_version,
        status=task.status.value,
        created_at=task.created_at.isoformat(),
        assigned_node=task.assigned_node
    )

@router.get("", response_model=TaskListResponse)
async def list_tasks(status: str | None = None):
    """列出所有任务"""
    filter_status = None
    if status:
        try:
            filter_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    tasks = task_manager.list_tasks(status=filter_status)
    return TaskListResponse(
        tasks=[
            TaskResponse(
                task_id=t.task_id,
                task_type=t.task_type.value,
                algorithm_name=t.algorithm_name,
                algorithm_version=t.algorithm_version,
                status=t.status.value,
                created_at=t.created_at.isoformat(),
                assigned_node=t.assigned_node
            )
            for t in tasks
        ],
        total=len(tasks)
    )

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """获取指定任务"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return TaskResponse(
        task_id=task.task_id,
        task_type=task.task_type.value,
        algorithm_name=task.algorithm_name,
        algorithm_version=task.algorithm_version,
        status=task.status.value,
        created_at=task.created_at.isoformat(),
        assigned_node=task.assigned_node
    )
```

- [ ] **Step 5: 实现 FastAPI 主入口**

```python
# src/algo_studio/api/main.py
from fastapi import FastAPI
from algo_studio.api.routes import tasks, hosts

app = FastAPI(
    title="AlgoStudio API",
    description="AI Algorithm Platform API",
    version="0.1.0"
)

app.include_router(tasks.router)
app.include_router(hosts.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: 实现主机状态 API 路由**

```python
# src/algo_studio/api/routes/hosts.py
from fastapi import APIRouter
from algo_studio.core.ray_client import RayClient
from algo_studio.monitor.host_monitor import HostMonitor

router = APIRouter(prefix="/api/hosts", tags=["hosts"])
ray_client = RayClient()
local_monitor = HostMonitor()

@router.get("/status")
async def get_host_status():
    """获取所有集群主机状态"""
    try:
        # 获取 Ray 集群节点列表
        nodes = ray_client.get_nodes()

        # 获取本机详细信息
        local_info = local_monitor.get_host_info()

        return {
            "cluster_nodes": [
                {
                    "node_id": n.node_id,
                    "ip": n.ip,
                    "status": n.status,
                    "resources": {
                        "cpu": {"total": n.cpu_total, "used": n.cpu_used, "available": n.cpu_available},
                        "gpu": {"total": n.gpu_total, "used": n.gpu_used, "available": n.gpu_available},
                        "memory": {"total": f"{n.memory_total_gb}Gi", "used": f"{n.memory_used_gb}Gi", "available": f"{n.memory_available_gb}Gi"},
                        "disk": {"total": f"{n.disk_total_gb}G", "used": f"{n.disk_used_gb}G"},
                        "swap": {"total": f"{n.swap_total_gb}Gi", "used": f"{n.swap_used_gb}Gi"}
                    }
                }
                for n in nodes
            ],
            "local_host": {
                "hostname": local_info.hostname,
                "ip": local_info.ip,
                "resources": {
                    "cpu": {"total": local_info.cpu_count, "used": local_info.cpu_used},
                    "gpu": {"total": local_info.gpu_count, "used": local_info.gpu_used, "name": local_info.gpu_name},
                    "memory": {"total": f"{local_info.memory_total_gb}Gi", "used": f"{local_info.memory_used_gb}Gi"},
                    "disk": {"total": f"{local_info.disk_total_gb}G", "used": f"{local_info.disk_used_gb}G"},
                    "swap": {"total": f"{local_info.swap_total_gb}Gi", "used": f"{local_info.swap_used_gb}Gi"}
                }
            }
        }
    except Exception as e:
        # 如果 Ray 未初始化，返回本地状态
        return {
            "cluster_nodes": [],
            "local_host": local_monitor.to_dict(),
            "error": str(e)
        }
```

- [ ] **Step 7: 运行测试验证通过**

Run: `pytest tests/test_api_tasks.py -v`
Expected: PASS

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "feat: add task management API routes"
```

---

## Task 8: 主机状态监控

**Files:**
- Create: `src/algo_studio/monitor/host_monitor.py`
- Create: `tests/test_host_monitor.py`

- [ ] **Step 1: 编写主机监控测试**

```python
# tests/test_host_monitor.py
import pytest
from algo_studio.monitor.host_monitor import HostMonitor, HostInfo

def test_host_info_dataclass():
    info = HostInfo(
        hostname="worker-1",
        ip="192.168.0.101",
        cpu_count=24,
        cpu_used=8,
        memory_total_gb=31,
        memory_used_gb=16,
        gpu_name="RTX 4090",
        gpu_count=1,
        gpu_used=0,
        disk_total_gb=1800,
        disk_used_gb=320,
        swap_total_gb=15,
        swap_used_gb=1
    )
    assert info.hostname == "worker-1"
    assert info.cpu_available == 16
    assert info.gpu_available == 1

def test_host_monitor_initialization():
    monitor = HostMonitor()
    assert monitor is not None
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_host_monitor.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现主机监控模块**

```python
# src/algo_studio/monitor/host_monitor.py
import socket
import psutil
from dataclasses import dataclass

try:
    import pynvml
    pynvml.nvmlInit()
    GPU_AVAILABLE = True
except:
    GPU_AVAILABLE = False

@dataclass
class HostInfo:
    hostname: str
    ip: str
    cpu_count: int
    cpu_used: int
    memory_total_gb: float
    memory_used_gb: float
    gpu_name: str | None
    gpu_count: int
    gpu_used: int
    disk_total_gb: float
    disk_used_gb: float
    swap_total_gb: float
    swap_used_gb: float

    @property
    def cpu_available(self) -> int:
        return self.cpu_count - self.cpu_used

    @property
    def memory_available_gb(self) -> float:
        return self.memory_total_gb - self.memory_used_gb

    @property
    def gpu_available(self) -> int:
        return self.gpu_count - self.gpu_used

class HostMonitor:
    """主机状态监控"""

    def get_host_info(self) -> HostInfo:
        """获取本机状态信息"""
        cpu_count = psutil.cpu_count()
        cpu_used = psutil.cpu_percent(interval=1)

        memory = psutil.virtual_memory()
        memory_total_gb = memory.total / (1024**3)
        memory_used_gb = memory.used / (1024**3)

        disk = psutil.disk_usage("/")
        disk_total_gb = disk.total / (1024**3)
        disk_used_gb = disk.used / (1024**3)

        swap = psutil.swap_memory()
        swap_total_gb = swap.total / (1024**3)
        swap_used_gb = swap.used / (1024**3)

        gpu_name = None
        gpu_count = 0
        gpu_used = 0

        if GPU_AVAILABLE:
            try:
                gpu_count = pynvml.nvmlDeviceGetCount()
                if gpu_count > 0:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    gpu_name = pynvml.nvmlDeviceGetName(handle)
                    memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    gpu_used = int(memory_info.used / (1024**3))
            except:
                pass

        return HostInfo(
            hostname=socket.gethostname(),
            ip=socket.gethostbyname(socket.gethostname()),
            cpu_count=cpu_count,
            cpu_used=int(cpu_used * cpu_count / 100),
            memory_total_gb=round(memory_total_gb, 1),
            memory_used_gb=round(memory_used_gb, 1),
            gpu_name=gpu_name,
            gpu_count=gpu_count,
            gpu_used=gpu_used,
            disk_total_gb=round(disk_total_gb, 1),
            disk_used_gb=round(disk_used_gb, 1),
            swap_total_gb=round(swap_total_gb, 1),
            swap_used_gb=round(swap_used_gb, 1)
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        info = self.get_host_info()
        return {
            "hostname": info.hostname,
            "ip": info.ip,
            "status": "online",
            "resources": {
                "cpu": {"total": info.cpu_count, "used": info.cpu_used},
                "gpu": {"total": info.gpu_count, "used": info.gpu_used, "name": info.gpu_name},
                "memory": {"total": f"{info.memory_total_gb}Gi", "used": f"{info.memory_used_gb}Gi"},
                "disk": {"total": f"{info.disk_total_gb}G", "used": f"{info.disk_used_gb}G"},
                "swap": {"total": f"{info.swap_total_gb}Gi", "used": f"{info.swap_used_gb}Gi"}
            }
        }
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_host_monitor.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat: add host status monitoring module"
```

---

## Task 9: CLI 工具

**Files:**
- Create: `src/algo_studio/cli/main.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: 编写 CLI 测试**

```python
# tests/test_cli.py
import pytest
from click.testing import CliRunner
from algo_studio.cli.main import cli

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "AlgoStudio CLI" in result.output

def test_task_command():
    runner = CliRunner()
    result = runner.invoke(cli, ["task", "--help"])
    assert result.exit_code == 0
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 CLI 工具**

```python
# src/algo_studio/cli/main.py
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
        response = requests.get(f"{API_BASE}/api/hosts/status")
        response.raise_for_status()
        data = response.json()
        click.echo(json.dumps(data, indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat: add CLI tool with task and host commands"
```

---

## Task 10: Ray 集群初始化脚本

**Files:**
- Create: `scripts/setup_ray_cluster.sh`

- [ ] **Step 1: 编写集群初始化脚本**

```bash
#!/bin/bash
# scripts/setup_ray_cluster.sh
# Ray 集群初始化脚本

set -e

RAY_HEAD_PORT=6379
OBJECT_STORE_MEMORY=5GB

usage() {
    echo "Usage: $0 {head|worker|stop}"
    echo "  head    - 初始化 Head 节点"
    echo "  worker  - 以 Worker 身份加入集群（需要 HEAD_IP）"
    echo "  stop    - 停止 Ray 集群"
    exit 1
}

init_head() {
    echo "Initializing Ray Head node..."
    ray start --head --port=$RAY_HEAD_PORT --object-store-memory=$OBJECT_STORE_MEMORY
    echo "Ray Head node initialized."
    echo "Run 'ray status' to check cluster status."
}

init_worker() {
    if [ -z "$HEAD_IP" ]; then
        echo "Error: HEAD_IP environment variable not set"
        echo "Usage: HEAD_IP=192.168.0.100 $0 worker"
        exit 1
    fi

    echo "Initializing Ray Worker node, connecting to $HEAD_IP..."
    ray start --address="$HEAD_IP:$RAY_HEAD_PORT" --object-store-memory=$OBJECT_STORE_MEMORY
    echo "Ray Worker node initialized."
}

stop_ray() {
    echo "Stopping Ray..."
    ray stop
    echo "Ray stopped."
}

case "$1" in
    head)
        init_head
        ;;
    worker)
        init_worker
        ;;
    stop)
        stop_ray
        ;;
    *)
        usage
        ;;
esac
```

- [ ] **Step 2: 添加执行权限并提交**

```bash
chmod +x scripts/setup_ray_cluster.sh
git add -A
git commit -m "feat: add Ray cluster setup scripts"
```

---

## Task 11: 集成测试

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 编写集成测试**

```python
# tests/test_integration.py
import pytest
import subprocess
import time

def test_api_health():
    """测试 API 服务健康检查"""
    import requests
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    except requests.exceptions.ConnectionError:
        pytest.skip("API server not running")

def test_ray_initialization():
    """测试 Ray 是否可用"""
    import ray
    if not ray.is_initialized():
        ray.init()
    assert ray.is_initialized()
    ray.shutdown()
```

- [ ] **Step 2: 运行集成测试**

Run: `pytest tests/test_integration.py -v`
Expected: PASS (或 SKIP 如果服务未运行)

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "test: add integration tests"
```

---

## Task 12: README 文档

**Files:**
- Create: `README.md`

- [ ] **Step 1: 编写 README**

```markdown
# AlgoStudio

AI 算法平台，支持算法自我迭代进化和多机调度训练。

## 特性

- **Ray 集群调度** - 多机 GPU 训练自动调度
- **算法仓库** - 统一的算法接口规范和版本管理
- **任务管理** - 训练/推理/验证任务提交和追踪
- **主机监控** - CPU/GPU/内存/磁盘状态监控
- **AI 集成** - Multi-Agent 自动迭代进化（Phase 2）
- **Git 协作** - 演进日志和实验记录版本化管理（Phase 2）

## 快速开始

### 环境隔离（重要！）

**使用 uv 隔离部署，不污染系统环境：**

```bash
# 创建独立 Python 环境（使用 uv）
uv venv algo-studio-env
source algo-studio-env/bin/activate

# uv 会创建 .venv 目录，通过 symlink 链接系统 Python
# 方便打包、迁移、不污染原系统环境
```

### 安装

```bash
# 激活环境后安装
uv pip install -e .

# 或者安装依赖
uv pip install -r requirements.txt
```

### 启动 Ray 集群

```bash
# Head 节点
./scripts/setup_ray_cluster.sh head

# Worker 节点
HEAD_IP=192.168.0.100 ./scripts/setup_ray_cluster.sh worker
```

### 启动 API 服务

```bash
# 设置 PYTHONPATH 以便找到 src 模块
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# 启动服务
uvicorn algo_studio.api.main:app --host 0.0.0.0 --port 8000
```

### 使用 CLI

```bash
# 提交训练任务
algo task submit --type train --algo yolo --version v1.0.0 --config '{"epochs": 100}'

# 列出任务
algo task list

# 查看任务状态
algo task status task-001
```

## 项目结构

```
algo-studio/
├── src/algo_studio/
│   ├── api/           # FastAPI 路由
│   ├── core/          # 核心逻辑（算法接口、任务调度、Ray 客户端）
│   ├── cli/           # CLI 工具
│   └── monitor/       # 主机监控
├── tests/             # 测试
├── scripts/           # 集群初始化脚本
└── docs/              # 文档
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 启动 API（开发模式）
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
uvicorn algo_studio.api.main:app --reload
```

## License

MIT
```

- [ ] **Step 2: 提交**

```bash
git add -A
git commit -m "docs: add README"
```

---

## Phase 1 总结

完成 Phase 1 后，你将拥有：

1. **项目脚手架** - 完整的 Python 项目结构
2. **算法接口规范** - 训练/推理/验证统一接口定义
3. **Ray 集群支持** - 多机任务调度基础
4. **任务管理 API** - 任务提交、查询、状态追踪
5. **主机监控** - CPU/GPU/内存/磁盘状态获取
6. **CLI 工具** - 命令行管理任务和主机
7. **集群初始化脚本** - 快速部署 Ray 集群

**下一步（Phase 2）：**
- AI Agent 集成
- 演进日志 + Git 分支模型
- Web 控制台
- 算法仓库完整实现
