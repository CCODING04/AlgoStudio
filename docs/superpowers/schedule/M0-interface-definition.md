# M0: 接口定义文档

**阶段：** Week 1 - 接口定义
**创建日期：** 2026-03-26
**状态：** 完成
**版本：** v1.0

---

## 1. 概述

本文档定义 AlgoStudio 平台三个核心模块之间的接口规范，确保后续并行开发时各团队可以独立工作。

### 1.1 涉及模块

| 模块 | 负责人 | 接口消费者 |
|------|--------|-----------|
| Dataset Storage | Infrastructure Engineer | 后端、AI调度 |
| Ray Dashboard API | Backend Engineer | AI调度、前端 |
| Platform Agentic | AI Scheduling Engineer | 后端、Dataset Storage |

### 1.2 接口依赖关系

```
Dataset Storage ──┬──> Platform Agentic (读取数据集位置)
                  │
Ray Dashboard API ─┼──> Platform Agentic (提供节点状态)
                  │
Backend API ──────┴──> Platform Agentic (任务调度)
```

---

## 2. Ray API 返回格式 (Backend <-> Ray 集群)

### 2.1 RayAPIClient 统一响应格式

```python
# src/algo_studio/core/ray_dashboard_client.py

@dataclass
class RayAPIResponse:
    success: bool           # 请求是否成功
    data: Any              # 业务数据
    error: Optional[str] = None  # 错误信息
    cached: bool = False   # 是否来自缓存
```

### 2.2 节点状态数据结构 (NodeStatus)

**来源：** `src/algo_studio/core/ray_client.py`

```python
@dataclass
class NodeStatus:
    # 核心标识
    node_id: str           # Ray NodeID (不可读，建议使用 hostname 或 IP)
    ip: str                # 节点 IP 地址
    hostname: Optional[str] = None  # 主机名 (推荐用于显示)

    # 状态
    status: str            # "idle" | "busy" | "offline"

    # CPU 资源
    cpu_used: int          # 已使用 CPU 核心数
    cpu_total: int         # 总 CPU 核心数
    cpu_model: Optional[str] = None
    cpu_physical_cores: Optional[int] = None
    cpu_freq_current_mhz: Optional[float] = None

    # GPU 资源
    gpu_used: int          # 已使用 GPU 数量
    gpu_total: int         # 总 GPU 数量
    gpu_utilization: Optional[int] = None  # 0-100
    gpu_memory_used_gb: Optional[float] = None
    gpu_memory_total_gb: Optional[float] = None
    gpu_name: Optional[str] = None

    # 内存资源
    memory_used_gb: float
    memory_total_gb: float

    # 磁盘资源
    disk_used_gb: float
    disk_total_gb: float

    # Swap 资源
    swap_used_gb: float = 0.0
    swap_total_gb: float = 0.0

    # 计算属性
    @property
    def cpu_available(self) -> int:
        return self.cpu_total - self.cpu_used

    @property
    def gpu_available(self) -> int:
        return self.gpu_total - self.gpu_used

    @property
    def memory_available_gb(self) -> float:
        return self.memory_total_gb - self.memory_used_gb
```

**重要说明：**
- `assigned_node` 字段应使用 `hostname` 或 `ip`，而非 `node_id`
- `node_id` 是 Ray 内部的 NodeID，不便于人类阅读和调试

### 2.3 任务状态数据结构

**来源：** `src/algo_studio/core/task.py` + API 响应

```python
@dataclass
class TaskStatus:
    task_id: str                    # 任务 ID
    task_type: str                  # "train" | "infer" | "verify"
    algorithm_name: str             # 算法名称
    algorithm_version: str          # 算法版本

    status: str                     # "pending" | "running" | "completed" | "failed" | "cancelled"
    created_at: datetime             # 创建时间
    started_at: Optional[datetime] = None   # 开始时间
    completed_at: Optional[datetime] = None # 完成时间

    assigned_node: Optional[str] = None     # 调度到的节点 (hostname 或 IP)
    error: Optional[str] = None              # 错误信息

    progress: int = 0                        # 进度 0-100
```

### 2.4 Ray Dashboard API 端点

```python
# API 路由前缀: /api/cluster

GET  /api/cluster/status          # 集群综合状态
GET  /api/cluster/nodes           # 节点列表
GET  /api/cluster/nodes/{node_id} # 节点详情
GET  /api/cluster/actors          # Actor 列表
GET  /api/cluster/actors/{actor_id} # Actor 详情
GET  /api/cluster/tasks           # Task 列表
GET  /api/cluster/jobs            # Job 列表
GET  /api/cluster/health          # 健康检查
WS   /api/cluster/events          # SSE 实时事件流
```

---

## 3. 节点状态数据结构 (Backend -> AI Scheduling)

### 3.1 节点状态 API 响应格式

```python
# src/algo_studio/api/routes/cluster.py

class NodeInfo(BaseModel):
    node_id: str
    ip: str
    hostname: Optional[str] = None
    status: str               # "alive" | "dead"

    # 资源信息
    cpu_count: int = 0
    memory_total_gb: float = 0
    memory_used_gb: float = 0
    gpu_count: int = 0
    gpu_utilization: Optional[int] = None  # GPU 利用率 0-100

    class Config:
        from_attributes = True

class ClusterStatusResponse(BaseModel):
    connected: bool
    ray_version: Optional[str] = None
    cluster_status: Optional[Dict[str, Any]] = None
    nodes: List[NodeInfo] = []
    actors_count: int = 0
    tasks_count: int = 0
    error: Optional[str] = None
```

### 3.2 节点状态转换

```
Ray 集群视角                    AI 调度视角
─────────────                   ───────────
"alive" (Idle)      ──────>     "idle"    # 可用节点
"alive" (Busy)      ──────>     "busy"    # 忙碌节点
"dead"              ──────>     "offline"  # 离线节点
```

---

## 4. 任务调度接口 (AI Scheduling -> Backend)

### 4.1 调度输入: TaskProfile (任务画像)

```python
# src/algo_studio/core/scheduler/profiles/task_profile.py

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class TaskType(Enum):
    TRAIN = "train"
    INFER = "infer"
    VERIFY = "verify"

@dataclass
class TaskProfile:
    """任务特征画像 - AI 调度模块的输入格式"""

    task_id: str
    task_type: TaskType

    # 资源需求
    num_gpus: int = 0
    num_cpus: int = 1
    memory_gb: float = 0.0

    # 优先级 (1-10, 10 最高)
    priority: int = 5

    # 亲和性偏好
    preferred_nodes: List[str] = field(default_factory=list)  # hostname 列表
    data_locality: Optional[str] = None  # 数据所在节点 hostname

    # 任务特征
    estimated_duration_minutes: int = 30
    is_retry: bool = False
    retry_count: int = 0

    # 超时设置
    timeout_minutes: int = 120
```

### 4.2 调度评分输出: NodeScore (节点评分)

```python
# src/algo_studio/core/scheduler/profiles/node_score.py

@dataclass
class NodeScore:
    """节点评分结果"""

    node: NodeStatus        # 原始节点状态

    # 各维度得分 (0-100)
    gpu_score: float = 0.0       # GPU 匹配度
    memory_score: float = 0.0   # 内存匹配度
    load_score: float = 0.0     # 当前负载 (负载越低得分越高)
    health_score: float = 0.0   # 健康度
    affinity_score: float = 0.0 # 亲和性得分

    # 综合得分
    total_score: float = 0.0

    # 评分原因
    reasons: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)

# NodeScorer 默认权重配置
DEFAULT_WEIGHTS = {
    "gpu_score": 0.35,       # GPU 匹配度权重 (最重要)
    "memory_score": 0.25,    # 内存匹配度权重
    "load_score": 0.20,      # 当前负载权重
    "health_score": 0.10,    # 健康度权重
    "affinity_score": 0.10,  # 亲和性得分权重
}
```

### 4.3 调度决策输出: SchedulingDecision

```python
# src/algo_studio/core/scheduler/profiles/scheduling_decision.py

@dataclass
class SchedulingDecision:
    """调度决策结果"""

    decision_id: str
    task_id: str

    selected_node: Optional[NodeStatus]  # 选中的节点 (None 表示无可用节点)
    alternative_nodes: List[NodeScore] = field(default_factory=list)  # 备选节点

    routing_path: str = "fast"           # "fast" | "deep"
    confidence: float = 0.0              # 置信度 0.0 - 1.0
    reasoning: str = ""

    created_at: datetime = field(default_factory=datetime.now)

    # Fallback 信息
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
```

### 4.4 dispatch_task 扩展接口

**现有接口 (向后兼容):**
```python
# src/algo_studio/core/task.py

def dispatch_task(self, task_id: str, ray_client: "RayClient") -> bool:
    """传统派发方式 - 使用简单的首个空闲节点选择"""
    # ... 现有实现
```

**扩展接口 (Agentic Scheduler):**
```python
# src/algo_studio/core/task.py

def dispatch_task_with_scheduler(
    self,
    task_id: str,
    ray_client: "RayClient",
    scheduler: "AgenticScheduler"
) -> bool:
    """使用 AgenticScheduler 派发任务

    Args:
        task_id: 任务 ID
        ray_client: Ray 客户端
        scheduler: Agentic 调度器实例

    Returns:
        bool: 派发是否成功
    """
    task = self.get_task(task_id)
    if not task:
        return False

    # 使用调度器决策
    decision = scheduler.schedule(task)

    if not decision.selected_node:
        self.update_status(task_id, TaskStatus.FAILED, error="No available node")
        return False

    # 使用决策中的节点 hostname 或 IP
    selected_node = decision.selected_node
    task.assigned_node = selected_node.hostname or selected_node.ip or selected_node.node_id

    # 提交到 Ray
    node_ip = selected_node.ip
    return self._submit_to_ray(task, ray_client, node_ip=node_ip)
```

### 4.5 TaskAnalyzer 接口

```python
# src/algo_studio/core/scheduler/analyzers/base.py

class TaskAnalyzerInterface(ABC):
    """任务分析器接口"""

    @abstractmethod
    def analyze(self, task: Task) -> TaskProfile:
        """
        分析任务并生成任务画像

        Args:
            task: 原始任务对象

        Returns:
            TaskProfile: 任务画像

        Raises:
            AnalysisError: 当分析失败时
        """
        pass

    @abstractmethod
    def get_resource_requirements(self, task: Task) -> ResourceRequirements:
        """提取任务的资源需求"""
        pass
```

### 4.6 NodeScorer 接口

```python
# src/algo_studio/core/scheduler/scorers/base.py

class NodeScorerInterface(ABC):
    """节点评分器接口"""

    @abstractmethod
    def score(self, task_profile: TaskProfile, nodes: List[NodeStatus]) -> List[NodeScore]:
        """
        对可用节点进行多维度评分

        Args:
            task_profile: 任务画像
            nodes: 可用节点列表

        Returns:
            List[NodeScore]: 按得分降序排列的节点评分列表
        """
        pass

    @abstractmethod
    def explain_score(self, node_score: NodeScore) -> str:
        """解释节点评分原因"""
        pass
```

### 4.7 AgenticScheduler 接口

```python
# src/algo_studio/core/scheduler/agents/base.py

class AgenticSchedulerInterface(ABC):
    """Agentic 调度器接口"""

    @abstractmethod
    def schedule(self, task: Task) -> SchedulingDecision:
        """同步调度决策 (Fast Path)"""

    @abstractmethod
    async def schedule_async(self, task: Task) -> SchedulingDecision:
        """异步调度决策 (支持 Deep Path)"""

    @abstractmethod
    def should_use_deep_path(self, task_profile: TaskProfile) -> bool:
        """判断是否使用 Deep Path"""

    @abstractmethod
    def should_use_deep_path_with_context(
        self,
        task_profile: TaskProfile,
        queue_length: int,
        avg_node_load: float,
    ) -> bool:
        """
        基于完整上下文判断是否使用 Deep Path

        判断规则 (满足任一条件即走 Deep Path):
        1. 任务复杂度 >= 7
        2. 重试任务且 retry_count >= 2
        3. 队列长度 > 20 且 avg_node_load > 0.7
        4. 任务需要特定节点亲和性 (preferred_nodes 非空)
        5. 任务 timeout > 120 分钟
        6. 之前 Fast Path 失败过 (is_retry=True 且 fallback_used=True)
        """
        pass
```

---

## 5. 数据流图

### 5.1 任务调度数据流

```
用户提交任务
    │
    ▼
Backend API: POST /api/tasks
    │
    ▼
TaskManager.create_task()
    │
    ▼
TaskManager.dispatch_task()
    │
    ├─ 传统模式 ────────────────────────────────────────
    │      ▼
    │   RayClient.get_nodes() ──> 返回 List[NodeStatus]
    │      ▼
    │   选择首个空闲节点
    │      ▼
    │   RayClient.submit_task()
    │
    └─ Agentic 模式 (新) ─────────────────────────────────
               ▼
            TaskAnalyzer.analyze(task) ──> TaskProfile
               ▼
            NodeScorer.score(task_profile, nodes) ──> List[NodeScore]
               ▼
            AgenticScheduler.schedule() ──> SchedulingDecision
               ▼
            SafetyValidator.validate()
               ▼
            RayClient.submit_task_with_decision()
```

### 5.2 节点状态数据流

```
Ray 集群
    │
    ▼
Ray Dashboard API (GCS)
    │
    ▼
RayAPIClient.get_cluster_status()
    │
    ▼
Backend API: GET /api/cluster/status
    │
    ├─> 前端 Dashboard (SSE 实时推送)
    │
    └─> AI Scheduling
               ▼
            NodeScorer.score()
               ▼
            SchedulingDecision
```

---

## 6. 错误处理约定

### 6.1 错误类型

```python
class SchedulingError(Exception):
    """调度异常基类"""
    pass

class NoAvailableNodeError(SchedulingError):
    """没有可用节点"""
    pass

class ValidationError(SchedulingError):
    """验证失败"""
    pass

class AnalysisError(Exception):
    """任务分析异常"""
    pass

class LLMError(Exception):
    """LLM 调用异常"""
    pass
```

### 6.2 错误响应格式

```json
{
    "success": false,
    "error": {
        "code": "NO_AVAILABLE_NODE",
        "message": "没有可用节点来执行任务",
        "details": {
            "task_id": "train-xxxx",
            "required_gpus": 1,
            "available_nodes": []
        }
    }
}
```

---

## 7. 常量配置

### 7.1 调度器配置

```python
# 配置项 (可通过配置文件覆盖)

SCHEDULER_CONFIG = {
    # Fast/Deep Path 路由
    "fast_path_threshold": 5,              # 复杂度 >=5 考虑 Deep Path
    "deep_path_timeout_seconds": 2.0,      # Deep Path 超时时间

    # Fallback 配置
    "fallback_on_error": True,             # 错误时是否降级到 Fast Path
    "cache_decisions": True,               # 是否缓存调度决策
    "cache_ttl_hours": 24,                 # 缓存 TTL

    # NodeScorer 权重
    "scorer_weights": {
        "gpu_score": 0.35,
        "memory_score": 0.25,
        "load_score": 0.20,
        "health_score": 0.10,
        "affinity_score": 0.10,
    },

    # Deep Path 判断规则
    "deep_path_rules": {
        "complexity_threshold": 7,
        "retry_count_threshold": 2,
        "queue_length_threshold": 20,
        "load_threshold": 0.7,
        "timeout_threshold_minutes": 120,
    }
}
```

---

## 8. 版本兼容性

### 8.1 Ray 版本兼容

| Ray 版本 | 状态 API | 节点 API | Actor API |
|----------|----------|----------|-----------|
| 2.5.x | `/api/v0/...` | `/api/v0/nodes` | `/api/v0/actors` |
| 2.6.x | `/api/v0/...` | `/api/v0/nodes` | `/api/v0/actors` |
| 2.8.x | `/api/v0/...` | `/nodes` | `/api/v0/actors` |

### 8.2 Python 版本要求

- Python >= 3.8 (for dataclasses support)
- 推荐 Python >= 3.10 (for better type hints)

---

## 9. 实施检查清单

### 9.1 Backend Engineer 需实现

- [ ] `RayAPIClient` 类 (`src/algo_studio/core/ray_dashboard_client.py`)
- [ ] `RayAPICompat` 版本兼容类 (`src/algo_studio/core/ray_compat.py`)
- [ ] `/api/cluster/*` 路由 (`src/algo_studio/api/routes/cluster.py`)
- [ ] SSE 端点实现
- [ ] 健康检查机制

### 9.2 AI Scheduling Engineer 需实现

- [ ] `TaskProfile` 数据类
- [ ] `NodeScore` 数据类
- [ ] `SchedulingDecision` 数据类
- [ ] `TaskAnalyzer` 接口和实现
- [ ] `NodeScorer` 接口和实现
- [ ] `AgenticScheduler` 主调度器
- [ ] `SafetyValidator`
- [ ] Fast Path 规则引擎
- [ ] Deep Path LLM 集成 (M4)

### 9.3 Integration 需对接

- [ ] `TaskManager.dispatch_task()` 调用 `AgenticScheduler`
- [ ] 节点状态从 `RayClient.get_nodes()` 获取
- [ ] `assigned_node` 使用 `hostname` 而非 `node_id`

---

**文档版本历史：**

| 版本 | 日期 | 修改内容 |
|------|------|---------|
| v1.0 | 2026-03-26 | 初始版本，定义三个模块间的核心接口 |
