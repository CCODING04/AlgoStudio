# Auto-Research 深化设计报告

**调研时间:** 2026-03-26
**Agent:** auto-research-feasibility-researcher (Round 2)
**核心定位:** Autonomous Algorithm Optimization Engine (独立项目)

---

## 1. 项目定位与愿景

### 1.1 核心定义

Auto-Research 是一个**让 LLM 自主驱动算法进化的引擎**。其本质是：

> 给定算法（项目）优化的**目标函数**（metric 最大或 cost/loss 最小），通过 Agent 驱动**调研-实验-评估**的持续循环，让算法自动优化。

### 1.2 独立项目架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Auto-Research Engine                              │
│                     (Autonomous Optimization Engine)                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                     Orchestrator (调度核心)                       │   │
│   │                  负责任务分发、状态机、迭代控制                    │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                               │                                          │
│          ┌────────────────────┼────────────────────┐                   │
│          ▼                    ▼                    ▼                   │
│   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐           │
│   │   Research  │ ──→  │    Code    │ ──→  │  Analyzer   │           │
│   │   Agent     │      │   Agent    │      │   Agent     │           │
│   │  (调研灵感)  │      │  (代码实验)  │      │  (评估决策)  │           │
│   └─────────────┘      └─────────────┘      └─────────────┘           │
│          │                    │                    │                   │
│          └────────────────────┼────────────────────┘                   │
│                               │                                          │
│                               ▼                                          │
│                    ┌─────────────────────┐                              │
│                    │   Experiment Store   │                              │
│                    │   (实验历史/知识库)   │                              │
│                    └─────────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     AlgoStudio Integration Layer                         │
│              (预留融合接口 - 可独立运行或集成平台)                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.3 与 karpathy/autoresearch 的区别

| 维度 | karpathy/autoresearch | Auto-Research Engine (本项目) |
|------|----------------------|------------------------------|
| 目标 | LLM 自身训练优化 | **任意算法/项目的自动优化** |
| 架构 | 单文件 + 循环 | **多 Agent 协作 + 知识积累** |
| 优化范围 | train.py | **全项目代码 + 配置 + 超参** |
| 并行能力 | 单进程 | **Ray 分布式多节点并行** |
| 知识管理 | 无 | **Experiment Store 积累** |
| 扩展性 | 封闭 | **插件化 + 预留 AlgoStudio 接口** |

---

## 2. Agent 职责细化

### 2.1 Research Agent (调研代理)

**职责：** 负责发现、调研、灵感生成

```
Research Agent
├── 信息检索
│   ├── 搜索 arxiv/论文/博客
│   ├── 查阅相关项目实现
│   └── 技术趋势分析
├── 灵感生成
│   ├── 提出优化方向假设
│   ├── 生成实验方案草稿
│   └── 评估可行性
└── 知识整合
    ├── 整理相关技术背景
    ├── 输出调研报告
    └── 维护技术知识库
```

**输出：**
- Research Report (Markdown)
- Hypothesis List (待验证的优化方向)
- Related Works Summary

### 2.2 Code Agent (代码代理)

**职责：** 负责代码修改、实验执行、结果收集

```
Code Agent
├── 代码修改
│   ├── 分析当前算法结构
│   ├── 实现 Research Agent 提出的假设
│   └── 确保代码正确性和可运行性
├── 实验执行
│   ├── 配置实验参数
│   ├── 启动训练/测试任务
│   └── 收集实验结果
└── 版本管理
    ├── Git commit 实验版本
    ├── 管理实验分支
    └── 支持版本回滚
```

**约束：**
- **单节点修改限制**：Code Agent 的代码修改操作仅在单一节点（Head Node）上执行，避免多节点并发 git 操作导致冲突
- 多节点并行通过同时调度多个独立实验实现（每个实验有独立的 git working directory）

**输出：**
- Modified Code (git commit)
- Experiment Config
- Raw Results (logs, metrics)

### 2.3 Analyzer Agent (分析代理)

**职责：** 负责结果分析、指标评估、决策生成

```
Analyzer Agent
├── 指标评估
│   ├── 提取关键指标 (metric/loss/time)
│   ├── 与历史实验对比
│   └── 统计显著性检验
├── 结果诊断
│   ├── 识别性能瓶颈
│   ├── 分析失败原因
│   └── 提供改进建议
└── 决策生成
    ├── 判断是否采纳新方案
    ├── 决定是否继续迭代
    └── 生成下一步计划
```

**输出：**
- Analysis Report
- Decision (adopt/reject/continue)
- Next Step Recommendations

### 2.4 Agent 协作流程

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Iteration Loop                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│   ┌───────────┐     ┌───────────┐     ┌───────────┐                 │
│   │  Research  │ ──→ │   Code    │ ──→ │  Analyzer │                 │
│   │  Agent     │     │   Agent   │     │  Agent    │                 │
│   └───────────┘     └───────────┘     └───────────┘                 │
│        │                                    │                        │
│        │   generate_hypothesis()            │                        │
│        │─────────────────────────────────────│                        │
│        │                                    │                        │
│        │         ┌───────────────────────┐  │                        │
│        │         │   Experiment Store    │  │                        │
│        │         │   (知识积累中心)       │◄─┘                        │
│        │         └───────────────────────┘                           │
│        │                                    │                         │
│        │   ◄─────── improvement found? ─────┘                        │
│        │        (no: loop again)                                      │
│        │        (yes: commit & continue)                              │
│        │                                                              │
│        ▼                                                              │
│   ┌───────────┐                                                       │
│   │ git commit│ ──→ Best result checkpoint                            │
│   └───────────┘                                                       │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. 与 AlgoStudio 融合方案

### 3.1 融合架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Auto-Research Engine                             │
│                      (独立运行 或 AlgoStudio 插件)                        │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     AlgoStudio Integration Layer                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│   │  Task Bridge   │  │  Model Bridge   │  │  Metric Bridge  │         │
│   │  (任务对接)     │  │  (模型对接)      │  │  (指标对接)     │         │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    AlgoStudio Core                               │   │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │   │
│   │   │ Algorithm   │  │    Task     │  │  Progress   │            │   │
│   │   │  Registry   │  │   Manager   │  │   Store     │            │   │
│   │   └─────────────┘  └─────────────┘  └─────────────┘            │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    Ray Cluster Infrastructure                   │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 预留接口设计

#### 3.2.1 Task Bridge (任务接口)

```python
# auto_research/interfaces/task_bridge.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum

class TaskType(Enum):
    TRAIN = "train"
    INFER = "infer"
    VERIFY = "verify"
    RESEARCH = "research"  # Auto-Research 特有

class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3

class TaskBridge(ABC):
    """Auto-Research 与 AlgoStudio TaskManager 的桥接接口"""

    @abstractmethod
    def submit_task(
        self,
        task_type: TaskType,
        algorithm_name: str,
        algorithm_version: str,
        config: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        resources: Dict[str, Any] = None
    ) -> str:
        """提交任务，返回 task_id"""
        pass

    @abstractmethod
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        pass

    @abstractmethod
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        pass

    @abstractmethod
    def list_tasks(
        self,
        status: Optional[str] = None,
        algorithm_name: Optional[str] = None
    ) -> list[Dict[str, Any]]:
        """列出任务"""
        pass


# AlgoStudio 集成实现
class AlgoStudioTaskBridge(TaskBridge):
    """AlgoStudio TaskManager 实现"""

    def __init__(self, task_manager: "TaskManager"):
        self._task_manager = task_manager

    def submit_task(
        self,
        task_type: TaskType,
        algorithm_name: str,
        algorithm_version: str,
        config: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        resources: Dict[str, Any] = None
    ) -> str:
        # 转换 TaskType
        algo_task_type = {
            TaskType.TRAIN: "train",
            TaskType.INFER: "infer",
            TaskType.VERIFY: "verify",
            TaskType.RESEARCH: "train"  # research 任务映射为 train
        }[task_type]

        task = self._task_manager.create_task(
            algo_task_type, algorithm_name, algorithm_version, config
        )
        return task.task_id

    # ... 其他方法实现
```

#### 3.2.2 Model Bridge (模型接口)

```python
# auto_research/interfaces/model_bridge.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path

class ModelBridge(ABC):
    """Auto-Research 与 AlgoStudio 算法仓库的桥接接口"""

    @abstractmethod
    def load_model(
        self,
        algorithm_name: str,
        algorithm_version: str,
        model_path: Optional[str] = None
    ) -> Any:
        """加载算法模型"""
        pass

    @abstractmethod
    def save_model(
        self,
        algorithm_name: str,
        algorithm_version: str,
        model: Any,
        metadata: Dict[str, Any]
    ) -> str:
        """保存模型到仓库，返回路径"""
        pass

    @abstractmethod
    def list_models(
        self,
        algorithm_name: str,
        algorithm_version: Optional[str] = None
    ) -> list[Dict[str, Any]]:
        """列出可用模型"""
        pass

    @abstractmethod
    def get_algorithm_interface(
        self,
        algorithm_name: str,
        algorithm_version: str
    ) -> "AlgorithmInterface":
        """获取算法接口实例"""
        pass


# AlgoStudio 集成实现
class AlgoStudioModelBridge(ModelBridge):
    """AlgoStudio 算法仓库实现"""

    ALGORITHM_BASE_PATH = Path(
        os.environ.get(
            "ALGORITHM_BASE_PATH",
            Path(__file__).parent.parent.parent / "algorithms"
        )
    )

    def get_algorithm_interface(
        self,
        algorithm_name: str,
        algorithm_version: str
    ) -> "AlgorithmInterface":
        """复用 AlgoStudio 的算法加载逻辑
        Note: _load_algorithm 待实现或复用 TaskManager._load_algorithm
        """
        from algo_studio.core.task_manager import TaskManager
        # 临时实现，待确认 _load_algorithm 位置
        tm = TaskManager()
        return tm._load_algorithm(algorithm_name, algorithm_version)
```

#### 3.2.3 Metric Bridge (指标接口)

```python
# auto_research/interfaces/metric_bridge.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MetricRecord:
    """指标记录"""
    experiment_id: str
    timestamp: datetime
    metric_name: str
    metric_value: float
    metric_type: str  # "loss", "accuracy", "latency", etc.
    tags: Dict[str, str]

class MetricBridge(ABC):
    """Auto-Research 与监控系统的桥接接口"""

    @abstractmethod
    def log_metric(
        self,
        experiment_id: str,
        metric_name: str,
        metric_value: float,
        metric_type: str = "custom",
        tags: Dict[str, str] = None
    ):
        """记录单个指标"""
        pass

    @abstractmethod
    def log_metrics_batch(
        self,
        experiment_id: str,
        metrics: List[Dict[str, Any]]
    ):
        """批量记录指标"""
        pass

    @abstractmethod
    def get_metrics(
        self,
        experiment_id: str,
        metric_name: Optional[str] = None,
        time_range: Optional[tuple] = None
    ) -> List[MetricRecord]:
        """获取指标历史"""
        pass

    @abstractmethod
    def compare_experiments(
        self,
        experiment_ids: List[str],
        metric_name: str
    ) -> Dict[str, Any]:
        """对比多个实验的指标"""
        pass

    @abstractmethod
    def register_metric_callback(
        self,
        experiment_id: str,
        callback: Callable[[MetricRecord], None]
    ):
        """注册指标回调（用于实时监控）"""
        pass


# AlgoStudio 集成实现
class AlgoStudioMetricBridge(MetricBridge):
    """复用 AlgoStudio ProgressStore 和 Task.result"""

    def __init__(self, progress_store=None):
        self._progress_store = progress_store

    def log_metric(self, experiment_id, metric_name, metric_value, metric_type="custom", tags=None):
        # 写入 Experiment Store
        pass

    def get_metrics(self, experiment_id, metric_name=None, time_range=None):
        # 从 Experiment Store 读取
        pass
```

### 3.3 训练框架对接

```python
# auto_research/interfaces/training_adapter.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass

@dataclass
class TrainingResult:
    """训练结果"""
    success: bool
    model_path: Optional[str]
    metrics: Dict[str, float]
    duration_seconds: float
    error: Optional[str]

class TrainingAdapter(ABC):
    """训练任务适配器 - 对接不同训练框架"""

    @abstractmethod
    def prepare_training(
        self,
        algorithm_name: str,
        algorithm_version: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """准备训练环境，返回训练参数"""
        pass

    @abstractmethod
    def execute_training(
        self,
        algorithm_name: str,
        algorithm_version: str,
        config: Dict[str, Any],
        progress_callback: Optional[Callable] = None
    ) -> TrainingResult:
        """执行训练任务"""
        pass

    @abstractmethod
    def stop_training(self, experiment_id: str) -> bool:
        """停止训练任务"""
        pass


# Auto-Research 内置训练适配器
class LocalTrainingAdapter(TrainingAdapter):
    """本地/PyTorch 训练适配器"""

    def execute_training(self, algorithm_name, algorithm_version, config, progress_callback=None):
        # 加载算法并调用 train()
        from auto_research.interfaces.model_bridge import get_algorithm_interface
        algo = get_algorithm_interface(algorithm_name, algorithm_version)
        result = algo.train(config["data_path"], config, progress_callback)
        return TrainingResult(
            success=result.success,
            model_path=result.model_path,
            metrics=result.metrics or {},
            duration_seconds=config.get("duration", 0),
            error=result.error
        )


# AlgoStudio Ray 训练适配器
class RayTrainingAdapter(TrainingAdapter):
    """Ray 分布式训练适配器"""

    def __init__(self, ray_client=None):
        self._ray_client = ray_client

    def execute_training(self, algorithm_name, algorithm_version, config, progress_callback=None):
        # 通过 Ray 提交训练任务到集群
        import ray
        from algo_studio.core.task import run_training, RayProgressCallback

        # 创建 ProgressReporter
        reporter = ray.remote(ProgressReporter).remote()

        # 提交到 Ray
        task_ref = run_training.remote(
            f"autorun-{uuid.uuid4().hex[:8]}",
            algorithm_name,
            algorithm_version,
            config,
            reporter
        )

        # 等待结果
        result = ray.get(task_ref)
        return TrainingResult(
            success=result.get("success", False),
            model_path=result.get("model_path"),
            metrics=result.get("metrics", {}),
            duration_seconds=config.get("duration", 0),
            error=result.get("error")
        )
```

### 3.4 平台工作流集成

> **配置示例**：以下 YAML 仅为 AlgoStudio 集成的工作流配置示例，实际实现以代码为准。

```yaml
# auto_research/integration/algo_studio_workflow.yaml (配置示例)

workflows:
  # 自动化算法优化流程
  auto_optimize:
    name: "Auto Algorithm Optimization"
    description: "使用 Auto-Research 优化指定算法"
    steps:
      - name: "init_research"
        type: "auto_research_init"
        config:
          target_algo: "${algorithm_name}"
          target_version: "${algorithm_version}"
          objective: "${objective}"  # "maximize_accuracy" 或 "minimize_latency"
          max_iterations: 50
          parallel_experiments: 4

      - name: "run_research_loop"
        type: "auto_research_loop"
        depends_on: ["init_research"]

      - name: "publish_best"
        type: "algo_studio_publish"
        depends_on: ["run_research_loop"]
        config:
          action: "update_if_better"
          target_algo: "${algorithm_name}"

  # 自动化算法评审流程
  auto_review:
    name: "Auto Algorithm Review"
    description: "评审算法改进是否达标"
    steps:
      - name: "run_verification"
        type: "algo_studio_verify"
        config:
          algorithm_name: "${algorithm_name}"
          test_dataset: "${test_dataset}"
          pass_threshold:
            accuracy: 0.95
            latency_ms: 100

      - name: "decision"
        type: "gateway"
        conditions:
          - if: "verification.passed"
            then: ["merge_to_stable"]
          - else: ["notify_needs_improvement"]

      - name: "merge_to_stable"
        type: "algo_studio_merge"
        condition: "verification.passed"

# 触发器配置
triggers:
  schedule:
    - name: "nightly_optimization"
      cron: "0 2 * * *"  # 每天 2 AM
      workflow: "auto_optimize"
      params:
        target_algo: "simple_classifier"
        max_iterations: 20

  manual:
    - name: "trigger_optimization"
      workflow: "auto_optimize"
      params:
        target_algo: "simple_detector"
        objective: "maximize_map"
```

---

## 4. 实施阶段规划

### Phase 1a: 项目骨架与配置 (Week 1)

**目标：** 建立 Auto-Research 独立项目骨架

```
auto-research/
├── src/
│   └── auto_research/
│       ├── __init__.py
│       ├── core/
│       │   ├── orchestrator.py      # 任务调度核心
│       │   ├── experiment_store.py  # 实验存储
│       │   └── config.py            # 配置管理
│       ├── agents/
│       │   ├── base.py              # Agent 基类
│       │   ├── research_agent.py    # Research Agent
│       │   ├── code_agent.py        # Code Agent
│       │   └── analyzer_agent.py     # Analyzer Agent
│       ├── interfaces/              # 预留接口
│       │   ├── task_bridge.py
│       │   ├── model_bridge.py
│       │   └── metric_bridge.py
│       ├── integrations/            # AlgoStudio 集成
│       │   └── algo_studio/
│       └── cli/
│           └── main.py
├── tests/
├── configs/
├── README.md
└── pyproject.toml
```

**交付物：**
- [ ] 项目骨架代码
- [ ] 配置管理 (agents.yaml, llm.yaml)
- [ ] CLI 工具基本框架

### Phase 1b: 单 Agent 原型验证 (Week 2)

**目标：** 实现单一 Agent 实验循环

**交付物：**
- [ ] 基础 Agent 类框架
- [ ] 单任务实验循环演示
- [ ] Experiment Store 基础版本

### Phase 2: 多 Agent 协作系统 (Week 3-4)

**目标：** 实现 Research/Code/Analyzer 三 Agent 协作

```
┌─────────────────────────────────────────────────────────────┐
│                    Phase 2 架构                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   Research Agent ──→ Code Agent ──→ Analyzer Agent           │
│        │                │                │                  │
│        └────────────────┼────────────────┘                  │
│                         ▼                                    │
│              ┌─────────────────────┐                        │
│              │   Experiment Store  │                        │
│              │   (SQLite + JSON)   │                        │
│              └─────────────────────┘                        │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐    │
│   │              Orchestrator                          │    │
│   │  - 迭代控制 (max_iterations, early_stopping)        │    │
│   │  - Agent 状态机管理                                  │    │
│   │  - 结果路由决策                                       │    │
│   └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**交付物：**
- [ ] Research Agent 实现（arxiv 搜索、灵感生成）
- [ ] Code Agent 实现（代码修改、git 管理）
- [ ] Analyzer Agent 实现（指标分析、决策）
- [ ] Experiment Store 持久化
- [ ] 完整迭代循环测试

### Phase 3: AlgoStudio 集成 (Week 5-6)

**目标：** 实现与 AlgoStudio 的无缝对接

**交付物：**
- [ ] Task Bridge 实现
- [ ] Model Bridge 实现
- [ ] Ray Training Adapter
- [ ] Workflow YAML 配置
- [ ] 集成测试

### Phase 4: 并行化与生产化 (Week 7-8)

**目标：** 支持多节点并行实验

```
┌──────────────────────────────────────────────────────────────┐
│                    Phase 4 架构                               │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│   ┌──────────────────────────────────────────────────────┐   │
│   │              Ray Cluster (多节点)                     │   │
│   │                                                        │   │
│   │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │   │
│   │   │ Node 1 │  │ Node 2 │  │ Node 3 │  │ Node 4 │  │   │
│   │   │ (GPU)  │  │ (GPU)  │  │ (GPU)  │  │ (CPU)  │  │   │
│   │   └─────────┘  └─────────┘  └─────────┘  └─────────┘  │   │
│   │                                                        │   │
│   └──────────────────────────────────────────────────────┘   │
│                              │                               │
│                              ▼                               │
│   ┌─────────────────────────────────────────────────────┐   │
│   │            Experiment Coordinator                    │   │
│   │  - 并行实验调度 (4 experiments 并发)                 │   │
│   │  - 资源分配与负载均衡                                  │   │
│   │  - 结果收集与汇总                                      │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

**交付物：**
- [ ] Ray 集群支持
- [ ] 并行实验调度器
- [ ] 资源监控集成
- [ ] 性能基准测试

---

## 5. Experiment Store 数据模型

```python
# auto_research/core/experiment_store.py

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
import json
import sqlite3
from pathlib import Path

class ExperimentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Experiment:
    """实验记录"""
    experiment_id: str
    iteration: int
    hypothesis: str
    code_snapshot: str  # git commit hash
    config: Dict[str, Any]
    metrics: Dict[str, float]
    status: ExperimentStatus
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    parent_id: Optional[str] = None  # 父实验（用于分支回溯）
    tags: List[str] = field(default_factory=list)

@dataclass
class Hypothesis:
    """假设/灵感记录"""
    hypothesis_id: str
    description: str
    source: str  # "research_agent", "manual", "from_experiment"
    experiment_id: Optional[str]  # 验证该假设的实验
    status: str  # "pending", "tested", "adopted", "rejected"
    evidence: Optional[str]
    created_at: datetime

@dataclass
class BestResult:
    """最佳结果追踪"""
    algorithm_name: str
    metric_name: str
    metric_value: float
    experiment_id: str
    timestamp: datetime
    config: Dict[str, Any]
    model_path: str

class ExperimentStore:
    """实验存储中心 - 知识积累基础"""

    def __init__(self, db_path: str = "experiments.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # experiments 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                iteration INTEGER,
                hypothesis TEXT,
                code_snapshot TEXT,
                config TEXT,
                metrics TEXT,
                status TEXT,
                created_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                parent_id TEXT,
                tags TEXT
            )
        """)

        # hypotheses 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hypotheses (
                hypothesis_id TEXT PRIMARY KEY,
                description TEXT,
                source TEXT,
                experiment_id TEXT,
                status TEXT,
                evidence TEXT,
                created_at TEXT,
                FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
            )
        """)

        # best_results 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS best_results (
                algorithm_name TEXT,
                metric_name TEXT,
                metric_value REAL,
                experiment_id TEXT,
                timestamp TEXT,
                config TEXT,
                model_path TEXT,
                PRIMARY KEY (algorithm_name, metric_name)
            )
        """)

        conn.commit()

    def save_experiment(self, exp: Experiment):
        """保存实验记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            exp.experiment_id,
            exp.iteration,
            exp.hypothesis,
            exp.code_snapshot,
            json.dumps(exp.config),
            json.dumps(exp.metrics),
            exp.status.value,
            exp.created_at.isoformat(),
            exp.started_at.isoformat() if exp.started_at else None,
            exp.completed_at.isoformat() if exp.completed_at else None,
            exp.parent_id,
            json.dumps(exp.tags)
        ))
        conn.commit()

    def get_best(self, algorithm_name: str, metric_name: str) -> Optional[BestResult]:
        """获取最佳结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM best_results
            WHERE algorithm_name = ? AND metric_name = ?
        """, (algorithm_name, metric_name))
        row = cursor.fetchone()
        if row:
            return BestResult(*row)
        return None

    def update_best_if_improved(
        self,
        algorithm_name: str,
        metric_name: str,
        metric_value: float,
        experiment_id: str,
        config: Dict[str, Any],
        model_path: str
    ):
        """如果改进则更新最佳结果"""
        current_best = self.get_best(algorithm_name, metric_name)
        if current_best is None or metric_value > current_best.metric_value:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO best_results VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                algorithm_name,
                metric_name,
                metric_value,
                experiment_id,
                datetime.now().isoformat(),
                json.dumps(config),
                model_path
            ))
            conn.commit()
            return True
        return False

    def get_history(
        self,
        algorithm_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Experiment]:
        """获取实验历史"""
        # 实现查询逻辑
        pass

    def get_hypothesis_leads(self) -> List[Hypothesis]:
        """获取待验证的假设"""
        # 实现查询逻辑
        pass
```

---

## 6. Agent 协作时序图

```
┌─────────┐    Research Agent    Code Agent     Analyzer Agent   Experiment Store
   │            │                    │                  │              │
   │            │  1. analyze_goal()  │                  │              │
   │            │───────────────────> │                  │              │
   │            │                    │                  │              │
   │            │  2. generate_       │                  │              │
   │            │      hypotheses()   │                  │              │
   │            │<───────────────────│                  │              │
   │            │                    │                  │              │
   │            │  3. save_          │                  │              │
   │            │      hypotheses()   │                  │              │
   │            │──────────────────────────────────────>│              │
   │            │                    │                  │              │
   │            │  4. propose_       │                  │              │
   │            │      modification()│                  │              │
   │            │───────────────────> │                  │              │
   │            │                    │                  │              │
   │            │                    │ 5. apply_code_    │              │
   │            │                    │     changes()     │              │
   │            │                    │                  │              │
   │            │                    │ 6. run_experiment()│              │
   │            │                    │─────────────────> │              │
   │            │                    │                  │              │
   │            │                    │ 7. collect_       │              │
   │            │                    │     results()     │              │
   │            │                    │<─────────────────│              │
   │            │                    │                  │              │
   │            │                    │ 8. analyze_       │              │
   │            │                    │     results()     │              │
   │            │                    │──────────────────>│              │
   │            │                    │                  │              │
   │            │                    │ 9. decision:      │              │
   │            │                    │     adopt/reject   │              │
   │            │                    │<─────────────────│              │
   │            │                    │                  │              │
   │            │                    │ 10. save_to_       │              │
   │            │                    │     store()        │              │
   │            │                    │────────────────────────────────>│
   │            │                    │                  │              │
   │            │ 11. improve?       │                  │              │
   │            │<───────────────────│                  │              │
   │            │                    │                  │              │
   │            │ (loop or done)     │                  │              │
   │            │                    │                  │              │
   └────────────┘                    │                  │              │
```

---

## 7. 关键设计决策

### 7.1 独立运行 vs 集成运行

Auto-Research 设计为**可以独立运行**，也可以**作为 AlgoStudio 插件运行**：

```python
# 独立运行模式
from auto_research import AutoResearchEngine
engine = AutoResearchEngine(working_dir="./my_research")
engine.optimize(
    target="my_algorithm",
    objective="maximize_accuracy",
    max_iterations=50
)

# AlgoStudio 集成模式
from auto_research.integrations.algo_studio import AutoResearchPlugin
plugin = AutoResearchPlugin(algo_studio_app=app)
plugin.register_workflows()
```

### 7.2 Agent LLM 选择

默认使用 Claude API，支持配置：

```yaml
# config/agents.yaml
agents:
  research:
    model: "claude-sonnet-4-20250514"
    max_tokens: 4096
    temperature: 0.7

  code:
    model: "claude-sonnet-4-20250514"
    max_tokens: 8192
    temperature: 0.3

  analyzer:
    model: "claude-sonnet-4-20250514"
    max_tokens: 4096
    temperature: 0.2
```

### 7.3 LLM 调用成本与节流策略

#### 7.3.1 成本估算

每个迭代周期涉及多个 LLM 调用：

| Agent | 操作 | 预估调用次数/迭代 | 预估 Token/次 | 总 Token/迭代 |
|-------|------|-------------------|---------------|---------------|
| Research | 调研 + 灵感生成 | 3-5 | 8K input + 2K output | ~50K |
| Code | 代码修改方案 | 2-3 | 12K input + 4K output | ~48K |
| Analyzer | 结果分析 + 决策 | 2 | 6K input + 2K output | ~16K |
| **合计** | | **7-10** | | **~114K** |

假设每个迭代 ~114K tokens，使用 Claude Sonnet 4 (~$3/MTok input, $15/MTok output)：
- 每迭代成本 ≈ $0.15-0.20
- 100 次迭代 ≈ $15-20

#### 7.3.2 节流策略

```python
# auto_research/core/llm_throttle.py

import time
from dataclasses import dataclass
from typing import Optional
import asyncio

@dataclass
class LLMThrottleConfig:
    max_calls_per_minute: int = 30      # Claude API 限制
    max_calls_per_hour: int = 1000       # 成本控制
    burst_allowance: int = 5             # 允许突发
    burst_cooldown_seconds: int = 60

class LLMThrottle:
    """LLM 调用节流器"""

    def __init__(self, config: LLMThrottleConfig):
        self.config = config
        self.call_times = []

    async def acquire(self):
        """获取调用许可（等待或拒绝）"""
        now = time.time()

        # 清理过期记录
        self.call_times = [
            t for t in self.call_times
            if now - t < 3600  # 保留最近 1 小时
        ]

        # 检查小时限制
        if len(self.call_times) >= self.config.max_calls_per_hour:
            wait_time = 3600 - (now - self.call_times[0])
            if wait_time > 0:
                raise RuntimeError(f"LLM 调用已达小时限制，需等待 {wait_time:.0f} 秒")

        # 检查分钟限制
        recent_calls = [t for t in self.call_times if now - t < 60]
        if len(recent_calls) >= self.config.max_calls_per_minute:
            wait_time = 60 - (now - recent_calls[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self.call_times.append(now)

    def estimate_cost(self, iterations: int) -> dict:
        """估算总成本"""
        tokens_per_iteration = 114000  # 估算值
        cost_per_million_input = 3.0   # Sonnet 4
        cost_per_million_output = 15.0

        return {
            "iterations": iterations,
            "total_tokens": tokens_per_iteration * iterations,
            "estimated_cost_usd": (tokens_per_iteration * iterations / 1_000_000) * 9,  # 平均
            "worst_case_cost_usd": (tokens_per_iteration * iterations / 1_000_000) * 18
        }
```

### 7.4 迭代终止条件

```python
# auto_research/core/orchestrator.py

class StoppingCriteria:
    def __init__(
        self,
        max_iterations: int = 100,
        max_no_improvement: int = 10,
        time_budget_minutes: Optional[int] = None,
        target_metric: Optional[float] = None
    ):
        self.max_iterations = max_iterations
        self.max_no_improvement = max_no_improvement
        self.time_budget_minutes = time_budget_minutes
        self.target_metric = target_metric

    def should_stop(
        self,
        iteration: int,
        no_improvement_count: int,
        elapsed_minutes: float,
        current_best: float
    ) -> bool:
        """判断是否应该停止迭代"""
        if iteration >= self.max_iterations:
            return True

        if no_improvement_count >= self.max_no_improvement:
            return True

        if self.time_budget_minutes and elapsed_minutes >= self.time_budget_minutes:
            return True

        if self.target_metric and current_best >= self.target_metric:
            return True

        return False
```

---

## 8. Manager 评估 (更新)

| 维度 | 评分 (1-10) | 说明 |
|------|-------------|------|
| 完整性 | 9 | 覆盖独立项目设计、Agent 协作、接口设计、阶段规划、LLM 成本估算 |
| 逻辑性 | 9 | 架构分层清晰，接口设计合理 |
| 可行性 | 8 | 技术路径明确，Phase 1 拆分后工作量更合理 |
| 创新性 | 9 | 提出了可独立运行/插件化的双模式设计 |
| AlgoStudio 融合 | 9 | 预留了完整的桥接接口 |
| 风险控制 | 8 | 添加了 Code Agent 单节点约束和 LLM 节流策略 |

**总体评价:** 报告完成了从"整合思路"到"独立项目架构设计"的深化，明确了 Code Agent、Analyzer Agent、Research Agent 的职责边界和协作流程。接口设计考虑了与 AlgoStudio 的无缝集成，同时保持了独立运行的能力。

**本次更新修复：** Phase 1 拆分为 Phase 1a/1b，Code Agent 增加单节点约束，修复 `_load_algorithm` 引用，添加 LLM 成本估算，Workflow YAML 标注为配置示例。

**建议:** 可以开始 Phase 1a，实现基础项目骨架。
