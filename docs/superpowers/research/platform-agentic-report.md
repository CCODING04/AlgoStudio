# 平台 Agentic 拓展调研报告

**调研时间:** 2026-03-26
**Agent:** platform-agentic-researcher
**版本:** v2.0 (深化实现版)

---

## 1. 当前平台任务调度流程分析

### 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| TaskManager | `src/algo_studio/core/task.py` | 任务生命周期管理 (PENDING → RUNNING → COMPLETED/FAILED) |
| RayClient | `src/algo_studio/core/ray_client.py` | Ray 集群交互，通过 NodeMonitorActor 获取节点状态 |
| dispatch flow | `task.py` | 简单的"首个空闲节点"选择，无负载均衡，无重试机制 |

### 当前调度流程

```
用户提交任务 → 选择首个空闲节点 → 派发任务 → 监控进度 → 完成
```

### 现有局限性

1. **规则简单** - 仅基于"首个空闲节点"，无法感知复杂场景
2. **无负载感知** - 不考虑节点当前负载、GPU 利用率
3. **无重试策略** - 任务失败后无智能重试
4. **无亲和性调度** - 不考虑数据局部性、节点特性

---

## 2. Agent 化需求和目标

### 目标

- 让 Agent 自动分析任务需求（GPU、内存、优先级）
- 自动选择最优执行节点（而非简单规则）
- 自动监控和调整任务执行（失败重试、负载均衡）
- 持续学习优化调度策略

### 核心能力

1. **感知 (Perception)** - 实时感知集群状态、节点健康度、任务特征
2. **认知 (Cognition)** - 分析任务需求，做出调度决策
3. **行动 (Action)** - 执行调度指令，跟踪结果
4. **学习 (Learning)** - 从历史中学习，优化策略

---

## 3. 技术方案对比

| 方案 | 复杂度 | 延迟 | 决策质量 | 适用场景 |
|------|--------|------|----------|----------|
| 增强规则引擎 | 低 | <10ms | 良好 | 简单任务、固定规则 |
| LLM Agent (ReAct) | 高 | 500ms-2s | 优秀 | 复杂推理、多维度决策 |
| **混合架构 (推荐)** | 中 | 50-200ms | 最佳 | 通用场景 |

---

## 4. 推荐架构设计

### 混合架构 (Hybrid Design)

```
                    ┌─────────────────────────────────────┐
                    │         AgenticScheduler            │
                    │         (任务调度 Agent)            │
                    └─────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
            │ TaskAnalyzer│ │ NodeScorer │ │SafetyValidator
            │ (任务分析)   │ │ (节点评分)   │ │ (安全验证)  │
            └─────────────┘ └─────────────┘ └─────────────┘
```

### 核心组件

| 组件 | 职责 |
|------|------|
| TaskAnalyzer | 提取任务画像 (GPU 需求、内存、优先级、数据特征) |
| NodeScorer | 多维度评分 (GPU 匹配度、内存、负载、健康度) |
| AgenticScheduler | 路由决策：Fast Path(规则) vs Deep Path(LLM) |
| SafetyValidator | 确保调度决策满足资源约束 |
| MemoryLayer | 调度历史、节点特性学习 |

### 决策流程

```
任务提交
    │
    ▼
TaskAnalyzer 提取任务特征
    │
    ├─── GPU 任务? ───→ NodeScorer 多维度评分
    │                      │
    │                      ▼
    │                 AgenticScheduler
    │                      │
    │         ┌────────────┴────────────┐
    │         ▼                         ▼
    │    Fast Path                  Deep Path
    │  (规则引擎)                   (LLM Agent)
    │    <10ms                        500ms
    │         │                         │
    │         └────────────┬────────────┘
    │                      ▼
    │              SafetyValidator
    │                      │
    └──────────────────────┘
```

### LLM Fallback

当 LLM 不可用或响应超时时，自动降级到规则引擎：
- LLM 故障 → 降级到增强规则引擎
- 响应超时 (>2s) → 使用缓存决策或规则引擎
- 高负载时 → 批量使用规则引擎

---

## 5. 详细接口定义

### 5.1 核心数据结构

#### TaskProfile (任务画像)

```python
@dataclass
class TaskProfile:
    """任务特征画像"""
    task_id: str
    task_type: TaskType  # TRAIN, INFER, VERIFY

    # 资源需求
    num_gpus: int = 0
    num_cpus: int = 1
    memory_gb: float = 0.0

    # 优先级 (1-10, 10 最高)
    priority: int = 5

    # 亲和性偏好
    preferred_nodes: List[str] = field(default_factory=list)  # hostname 列表
    data_locality: Optional[str] = None  # 数据所在节点

    # 任务特征
    estimated_duration_minutes: int = 30
    is_retry: bool = False
    retry_count: int = 0

    # 超时设置
    timeout_minutes: int = 120
```

#### NodeScore (节点评分)

```python
@dataclass
class NodeScore:
    """节点评分结果"""
    node: NodeStatus

    # 各维度得分 (0-100)
    gpu_score: float = 0.0      # GPU 匹配度
    memory_score: float = 0.0  # 内存匹配度
    load_score: float = 0.0    # 当前负载
    health_score: float = 0.0  # 健康度
    affinity_score: float = 0.0 # 亲和性得分

    # 综合得分
    total_score: float = 0.0

    # 评分原因
    reasons: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
```

#### SchedulingDecision (调度决策)

```python
@dataclass
class SchedulingDecision:
    """调度决策结果"""
    decision_id: str
    task_id: str
    selected_node: Optional[NodeStatus]
    alternative_nodes: List[NodeScore] = field(default_factory=list)
    routing_path: str = "fast"  # "fast" | "deep"
    confidence: float = 0.0    # 0.0 - 1.0
    reasoning: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    # Fallback 信息
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
```

### 5.2 核心接口定义

#### TaskAnalyzer Interface

```python
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
        """
        提取任务的资源需求

        Args:
            task: 原始任务对象

        Returns:
            ResourceRequirements: 资源需求规格
        """
        pass
```

#### NodeScorer Interface

```python
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
        """
        解释节点评分原因

        Args:
            node_score: 节点评分

        Returns:
            str: 评分解释
        """
        pass
```

#### AgenticScheduler Interface

```python
class AgenticSchedulerInterface(ABC):
    """Agentic 调度器接口"""

    @abstractmethod
    def schedule(self, task: Task) -> SchedulingDecision:
        """
        为任务执行调度决策

        Args:
            task: 待调度任务

        Returns:
            SchedulingDecision: 调度决策

        Raises:
            SchedulingError: 当调度失败时
        """
        pass

    @abstractmethod
    async def schedule_async(self, task: Task) -> SchedulingDecision:
        """
        异步版本调度决策（支持 LLM Deep Path）

        Args:
            task: 待调度任务

        Returns:
            SchedulingDecision: 调度决策
        """
        pass

    @abstractmethod
    def should_use_deep_path(self, task_profile: TaskProfile) -> bool:
        """
        判断是否应该使用 Deep Path (LLM)

        Args:
            task_profile: 任务画像

        Returns:
            bool: True 使用 Deep Path, False 使用 Fast Path
        """
        pass

    @abstractmethod
    def should_use_deep_path_with_context(
        self,
        task_profile: TaskProfile,
        queue_length: int,
        avg_node_load: float,
    ) -> bool:
        """
        基于完整上下文判断是否使用 Deep Path (LLM)

        判断规则 (满足任一条件即走 Deep Path):
        1. 任务复杂度 >= 7 (多维度资源需求、亲和性约束)
        2. 重试任务且 retry_count >= 2
        3. 队列长度 > 20 且 avg_node_load > 0.7 (高负载场景)
        4. 任务需要特定节点亲和性 (preferred_nodes 非空)
        5. 任务 timeout > 120 分钟 (长时任务)
        6. 之前 Fast Path 失败过 (is_retry=True 且 fallback_used=True)

        Args:
            task_profile: 任务画像
            queue_length: 当前等待调度的任务数量
            avg_node_load: 集群平均节点负载 (0.0-1.0)

        Returns:
            bool: True 使用 Deep Path, False 使用 Fast Path
        """
        pass
```

#### SafetyValidator Interface

```python
class SafetyValidatorInterface(ABC):
    """安全验证器接口"""

    @abstractmethod
    def validate(self, decision: SchedulingDecision, task_profile: TaskProfile) -> ValidationResult:
        """
        验证调度决策的安全性

        Args:
            decision: 调度决策
            task_profile: 任务画像

        Returns:
            ValidationResult: 验证结果
        """
        pass

    @abstractmethod
    def can_schedule(self, task_profile: TaskProfile, node: NodeStatus) -> bool:
        """
        快速检查任务是否可以在指定节点执行

        Args:
            task_profile: 任务画像
            node: 目标节点

        Returns:
            bool: 是否可以在该节点执行
        """
        pass
```

#### MemoryLayer Interface

```python
class MemoryLayerInterface(ABC):
    """记忆层接口"""

    @abstractmethod
    def record_decision(self, decision: SchedulingDecision, outcome: TaskOutcome) -> None:
        """
        记录调度决策和执行结果

        Args:
            decision: 调度决策
            outcome: 任务执行结果
        """
        pass

    @abstractmethod
    def get_node_characteristics(self, node_id: str) -> NodeCharacteristics:
        """
        获取节点特征（从历史中学习）

        Args:
            node_id: 节点 ID

        Returns:
            NodeCharacteristics: 节点特征
        """
        pass

    @abstractmethod
    def get_success_rate(self, task_type: TaskType, node_id: str) -> float:
        """
        获取任务类型在指定节点的成功率

        Args:
            task_type: 任务类型
            node_id: 节点 ID

        Returns:
            float: 成功率 (0.0 - 1.0)
        """
        pass

    @abstractmethod
    def suggest_optimization(self) -> List[OptimizationSuggestion]:
        """
        基于历史数据提出优化建议

        Returns:
            List[OptimizationSuggestion]: 优化建议列表
        """
        pass
```

### 5.3 Memory Layer 存储后端选择

| 方案 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| **SQLite** (默认) | 单调度器、低并发 (<10 调度/秒) | 部署简单、无外部依赖 | 并发写入有锁竞争 |
| **Redis** (推荐生产) | 多调度器、高并发 (>=10 调度/秒) | 支持高并发、原子操作、持久化 | 需要额外部署 Redis |

#### Redis 备选方案配置

```python
# src/algo_studio/core/scheduler/memory/redis_store.py

class RedisMemoryStore:
    """基于 Redis 的记忆层存储"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6380,
        db: int = 0,
        password: Optional[str] = None,
        key_prefix: str = "algo_studio:scheduler:",
    ):
        import redis
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True,
        )
        self.key_prefix = key_prefix

    # 调度记录存储 (Hash)
    # key: scheduling:record:{record_id}
    # field: decision_json, outcome_json, created_at

    # 节点特征存储 (Hash)
    # key: node:chars:{node_id}
    # field: success_rate, avg_gpu_utilization, etc.

    # 缓存决策 (String with TTL)
    # key: cache:decision:{task_profile_hash}
    # value: decision_json
    # TTL: 1 hour

    async def record_decision_async(
        self,
        decision: SchedulingDecision,
        outcome: TaskOutcome,
    ) -> None:
        """异步记录调度决策"""
        import json
        record_key = f"{self.key_prefix}scheduling:record:{decision.decision_id}"
        data = {
            "decision": json.dumps(asdict(decision)),
            "outcome": json.dumps(asdict(outcome)),
            "created_at": datetime.now().isoformat(),
        }
        await self.client.hsetAsync(record_key, mapping=data)

    def get_cached_decision(self, task_profile_hash: str) -> Optional[SchedulingDecision]:
        """获取缓存的调度决策"""
        cache_key = f"{self.key_prefix}cache:decision:{task_profile_hash}"
        cached = self.client.get(cache_key)
        if cached:
            return SchedulingDecision(**json.loads(cached))
        return None
```

#### 迁移策略

1. **Phase 1-2**: 使用 SQLite 单机部署
2. **Phase 3**: 当并发调度 >= 10/秒 时，引入 Redis
3. **双写策略**: 迁移期间同时写入 SQLite 和 Redis，验证一致性后切换

### 5.4 错误类型定义

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

class TimeoutError(Exception):
    """超时异常"""
    pass
```

---

## 6. 数据结构设计

### 6.1 状态机定义

```
                    ┌─────────────┐
                    │   PENDING   │
                    └──────┬──────┘
                           │ schedule()
                           ▼
              ┌────────────────────────┐
              │     ANALYZING          │
              └───────────┬────────────┘
                          │ analyze()
                          ▼
              ┌────────────────────────┐
              │    SCORING_NODES      │
              └───────────┬────────────┘
                          │ score()
                          ▼
              ┌────────────────────────┐
              │    DECIDING           │
              │  (Fast/Deep Path)     │
              └───────────┬────────────┘
                          │ decide()
                          ▼
              ┌────────────────────────┐
              │    VALIDATING         │
              └───────────┬────────────┘
                          │ validate()
           ┌──────────────┴──────────────┐
           │ valid                       │ invalid
           ▼                             ▼
┌──────────────────┐          ┌──────────────────┐
│    DISPATCHING   │          │    RE_ROUTING    │
└────────┬─────────┘          └────────┬─────────┘
         │ dispatch()                   │ retry with fallback
         ▼
┌──────────────────┐
│     RUNNING      │
└────────┬─────────┘
         │ complete/fail
         ▼
┌──────────────────┐
│   COMPLETED/     │
│     FAILED       │
└──────────────────┘
```

### 6.2 节点特征学习数据结构

```python
@dataclass
class NodeCharacteristics:
    """节点特征（从历史学习）"""
    node_id: str
    hostname: str
    ip: str

    # 可靠性指标
    total_tasks: int = 0
    success_tasks: int = 0
    failure_tasks: int = 0

    # 性能指标
    avg_gpu_utilization: float = 0.0
    avg_memory_usage: float = 0.0
    avg_task_duration_minutes: float = 0.0

    # 任务类型偏好
    train_success_rate: float = 0.0
    infer_success_rate: float = 0.0
    verify_success_rate: float = 0.0

    # 健康度
    last_heartbeat: Optional[datetime] = None
    consecutive_failures: int = 0
    is_healthy: bool = True

    @property
    def success_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.success_tasks / self.total_tasks
```

### 6.3 调度历史记录

```python
@dataclass
class SchedulingRecord:
    """调度历史记录"""
    record_id: str
    decision: SchedulingDecision
    task: Task

    # 执行结果
    started_at: datetime
    completed_at: Optional[datetime] = None
    actual_duration_minutes: Optional[float] = None

    # 运行时指标
    actual_gpu_utilization: Optional[float] = None
    actual_memory_used_gb: Optional[float] = None

    # 结果
    outcome: Optional[TaskOutcome] = None  # SUCCESS, FAILURE, TIMEOUT, CANCELLED

    # 反思
    reflection: Optional[str] = None  # 分析原因（如果失败）
```

---

## 7. 实施任务分解 (9 周)

### Phase 1: 增强规则引擎 + NodeScorer (Week 1-2)

#### Week 1: 核心数据结构和基础框架 (5 人天)

| 任务 | 人天 | 交付物 | 验收标准 |
|------|------|--------|----------|
| 创建 `scheduler/` 目录结构 | 0.5 | 目录创建 | 目录存在且符合设计 |
| 实现 `TaskProfile` 数据类 | 0.5 | `task_profile.py` | 单元测试通过 |
| 实现 `NodeScore` 数据类 | 0.5 | `node_score.py` | 单元测试通过 |
| 实现基础 `TaskAnalyzer` | 1.0 | `task_analyzer.py` | 能从 Task 提取 TaskProfile |
| 实现基础 `NodeScorer` | 1.0 | `node_scorer.py` | 能对节点进行多维度评分 |
| 编写单元测试 | 1.5 | `test_task_analyzer.py`, `test_node_scorer.py` | 测试覆盖率 >80% |

#### Week 2: 调度器和集成 (5 人天)

| 任务 | 人天 | 交付物 | 验收标准 |
|------|------|--------|----------|
| 实现 `SafetyValidator` | 1.0 | `safety_validator.py` | 能验证资源约束 |
| 实现 `AgenticScheduler` Fast Path | 1.5 | `agentic_scheduler.py` | 能选择最优节点 |
| 集成到 `TaskManager.dispatch_task()` | 1.0 | 修改 `task.py` | API 能调用新调度器 |
| 基准测试 | 0.5 | `benchmark_results.md` | 调度延迟 <50ms |
| 文档更新 | 1.0 | API 文档 | 文档完整 |

**Phase 1 里程碑:** 调度器能基于多维度评分选择最优节点，Fast Path 响应延迟 <50ms

---

### Phase 2: Agent 框架 + Memory 层 (Week 3-5)

#### Week 3: Agent 框架核心 (5 人天)

| 任务 | 人天 | 交付物 | 验收标准 |
|------|------|--------|----------|
| 实现 `MemoryLayer` 基础结构 | 1.5 | `memory_layer.py` | 能记录和查询历史 |
| 实现 `SchedulingRecord` 存储 | 1.0 | `memory_layer.py` | 使用 SQLite/Redis |
| 实现 `NodeCharacteristics` 学习 | 1.0 | `memory_layer.py` | 能计算节点特征 |
| 实现决策记录回调 | 0.5 | `agentic_scheduler.py` | 任务完成后记录 |
| 单元测试 | 1.0 | `test_memory_layer.py` | 测试覆盖率 >80% |

#### Week 4: 路由机制 (5 人天)

| 任务 | 人天 | 交付物 | 验收标准 |
|------|------|--------|----------|
| 实现 Fast/Deep Path 路由 | 1.5 | `router.py` | 复杂任务走 Deep Path |
| 实现任务复杂度评估器 | 1.0 | `complexity_evaluator.py` | 评估规则明确 |
| 实现 `DeepPathAgent` 框架 | 1.5 | `deep_path_agent.py` | 支持 LLM 集成预留 |
| 集成路由到调度器 | 1.0 | `agentic_scheduler.py` | 路由生效 |
| 单元测试 | 0.5 | `test_router.py` | 路由正确 |

#### Week 5: 优化和集成 (5 人天)

| 任务 | 人天 | 交付物 | 验收标准 |
|------|------|--------|----------|
| 实现节点亲和性学习 | 1.0 | `memory_layer.py` | 能学习数据局部性 |
| 实现成功率预测 | 1.0 | `success_predictor.py` | 能预测任务成功率 |
| 优化调度器性能 | 1.0 | `agentic_scheduler.py` | 缓存机制有效 |
| API 对接 | 1.0 | `routes/scheduler.py` | 新 API 端点可用 |
| 集成测试 | 1.0 | `test_integration.py` | 端到端测试通过 |

**Phase 2 里程碑:** Memory 层能记录调度历史并学习节点特征，路由机制能区分 Fast/Deep Path

---

### Phase 3: LLM 集成 + Fallback (Week 6-7)

#### Week 6: LLM 集成 (5 人天)

| 任务 | 人天 | 交付物 | 验收标准 |
|------|------|--------|----------|
| 实现 LLM Provider 抽象 | 1.0 | `llm_provider.py` | 支持 OpenAI/Anthropic |
| 实现 `DeepPathAgent` LLM 调用 | 2.0 | `deep_path_agent.py` | 能生成调度决策 |
| 实现 ReAct 推理循环 | 1.5 | `deep_path_agent.py` | 支持 Thought/Action/Observation |
| 单元测试 | 0.5 | `test_llm_provider.py` | Mock 测试通过 |

#### Week 7: Fallback 和容错 (5 人天)

| 任务 | 人天 | 交付物 | 验收标准 |
|------|------|--------|----------|
| 实现 Fallback 降级机制 | 1.5 | `agentic_scheduler.py` | LLM 失败自动降级 |
| 实现超时处理 | 1.0 | `deep_path_agent.py` | 超时自动降级 |
| 实现缓存决策复用 | 1.0 | `memory_layer.py` | 类似决策使用缓存 |
| 负载过高降级策略 | 1.0 | `router.py` | 高负载时强制 Fast Path |
| 集成测试 | 0.5 | `test_fallback.py` | 降级机制有效 |

**Phase 3 里程碑:** LLM Deep Path 可用，Fallback 降级机制完善

---

### Phase 4: 生产部署 + 监控 (Week 8-9)

#### Week 8: 生产部署 (5 人天)

| 任务 | 人天 | 交付物 | 验收标准 |
|------|------|--------|----------|
| 配置管理 | 1.0 | `config.yaml` | 支持配置化 |
| 健康检查接口 | 0.5 | `/health` | 能检查调度器状态 |
| 指标暴露 (Prometheus) | 1.5 | `/metrics` | 关键指标可采集 |
| 日志规范化 | 1.0 | Structured logging | JSON 格式日志 |
| 部署脚本 | 1.0 | `deploy.sh` | 一键部署 |

#### Week 9: 监控和调优 (5 人天)

| 任务 | 人天 | 交付物 | 验收标准 |
|------|------|--------|----------|
| 调度决策监控面板 | 1.5 | Grafana dashboard | 决策可视化 |
| 告警规则配置 | 1.0 | `alerts.yaml` | 失败率超标告警 |
| 定期报告生成 | 1.0 | `reports.py` | 周报自动生成 |
| 性能调优 | 1.0 | Benchmark 优化 | P99 延迟优化 |
| 文档完善 | 0.5 | 运维文档 | 文档完整 |

**Phase 4 里程碑:** 生产级部署，监控告警完善

---

## 8. 代码目录结构

```
src/algo_studio/
├── core/
│   ├── task.py              # [现有] TaskManager, Task
│   ├── ray_client.py        # [现有] RayClient
│   └── scheduler/           # [新增] Agentic Scheduler
│       ├── __init__.py
│       ├── profiles/        # 数据结构
│       │   ├── __init__.py
│       │   ├── task_profile.py
│       │   ├── node_score.py
│       │   └── scheduling_decision.py
│       ├── analyzers/      # 任务分析
│       │   ├── __init__.py
│       │   ├── base.py      # TaskAnalyzerInterface
│       │   └── default_analyzer.py
│       ├── scorers/         # 节点评分
│       │   ├── __init__.py
│       │   ├── base.py      # NodeScorerInterface
│       │   └── multi_dim_scorer.py
│       ├── validators/      # 安全验证
│       │   ├── __init__.py
│       │   ├── base.py      # SafetyValidatorInterface
│       │   └── resource_validator.py
│       ├── memory/          # 记忆层
│       │   ├── __init__.py
│       │   ├── base.py      # MemoryLayerInterface
│       │   ├── sqlite_store.py
│       │   └── node_characteristics.py
│       ├── routing/         # 路由决策
│       │   ├── __init__.py
│       │   ├── router.py
│       │   └── complexity_evaluator.py
│       ├── agents/          # Deep Path Agent
│       │   ├── __init__.py
│       │   ├── base.py      # AgenticSchedulerInterface
│       │   ├── fast_scheduler.py
│       │   ├── deep_path_agent.py
│       │   └── llm/
│       │       ├── __init__.py
│       │       ├── base.py  # LLMProviderInterface
│       │       ├── openai_provider.py
│       │       └── anthropic_provider.py
│       ├── agentic_scheduler.py  # [主调度器]
│       └── exceptions.py
├── monitor/
│   ├── node_monitor.py      # [现有] NodeMonitorActor
│   └── host_monitor.py      # [现有] HostMonitor
├── api/
│   ├── main.py              # [现有] FastAPI app
│   ├── models.py            # [现有] Pydantic models
│   └── routes/
│       ├── tasks.py         # [现有] Task endpoints
│       ├── hosts.py         # [现有] Host endpoints
│       └── scheduler.py     # [新增] Scheduler endpoints
└── web/
    └── ...                  # [现有] Web UI
```

---

## 9. 核心类/函数列表

### 核心类

| 类名 | 文件 | 职责 |
|------|------|------|
| `TaskManager` | `core/task.py` | [现有] 任务生命周期管理 |
| `RayClient` | `core/ray_client.py` | [现有] Ray 集群交互 |
| `AgenticScheduler` | `scheduler/agentic_scheduler.py` | [新增] 主调度器门面 |
| `TaskAnalyzer` | `scheduler/analyzers/default_analyzer.py` | [新增] 任务分析 |
| `MultiDimNodeScorer` | `scheduler/scorers/multi_dim_scorer.py` | [新增] 多维度节点评分 |
| `SafetyValidator` | `scheduler/validators/resource_validator.py` | [新增] 资源安全验证 |
| `MemoryLayer` | `scheduler/memory/sqlite_store.py` | [新增] 调度记忆存储 |
| `FastPathScheduler` | `scheduler/agents/fast_scheduler.py` | [新增] Fast Path 调度器 |
| `DeepPathAgent` | `scheduler/agents/deep_path_agent.py` | [新增] Deep Path LLM Agent |
| `Router` | `scheduler/routing/router.py` | [新增] Fast/Deep 路由 |

### 核心函数签名

```python
# AgenticScheduler 主调度器
class AgenticScheduler:
    def schedule(self, task: Task) -> SchedulingDecision:
        """同步调度决策 (Fast Path)"""

    async def schedule_async(self, task: Task) -> SchedulingDecision:
        """异步调度决策 (支持 Deep Path)"""

    def should_use_deep_path(self, task_profile: TaskProfile) -> bool:
        """判断是否使用 Deep Path"""

# TaskAnalyzer
class TaskAnalyzer:
    def analyze(self, task: Task) -> TaskProfile:
        """从 Task 提取 TaskProfile"""

    def get_resource_requirements(self, task: Task) -> ResourceRequirements:
        """提取资源需求"""

# NodeScorer
class MultiDimNodeScorer:
    # 默认权重配置 (可根据实际调优调整)
    DEFAULT_WEIGHTS = {
        "gpu_score": 0.35,       # GPU 匹配度权重 (最重要)
        "memory_score": 0.25,    # 内存匹配度权重
        "load_score": 0.20,      # 当前负载权重 (负载越低得分越高)
        "health_score": 0.10,    # 健康度权重
        "affinity_score": 0.10,  # 亲和性得分权重
    }

    def score(self, task_profile: TaskProfile, nodes: List[NodeStatus]) -> List[NodeScore]:
        """
        多维度节点评分

        评分公式:
        total_score = (
            gpu_score * gpu_weight +
            memory_score * memory_weight +
            load_score * load_weight +
            health_score * health_weight +
            affinity_score * affinity_weight
        ) * 100

        其中:
        - gpu_score: 任务所需 GPU 数 / 节点可用 GPU 数 (0-100)
        - memory_score: 任务所需内存 / 节点可用内存 (0-100)
        - load_score: (1 - 当前负载率) * 100 (负载越低得分越高)
        - health_score: 基于节点健康状态 (0-100)
        - affinity_score: 基于历史成功率 (0-100)
        """
        pass

    def explain_score(self, node_score: NodeScore) -> str:
        """解释评分原因"""

# MemoryLayer
class MemoryLayer:
    def record_decision(self, decision: SchedulingDecision, outcome: TaskOutcome) -> None:
        """记录调度决策和结果"""

    def get_node_characteristics(self, node_id: str) -> NodeCharacteristics:
        """获取节点特征"""

    def get_success_rate(self, task_type: TaskType, node_id: str) -> float:
        """获取任务在节点的成功率"""

    def get_cached_decision(self, task_profile: TaskProfile) -> Optional[SchedulingDecision]:
        """获取缓存的调度决策"""

# DeepPathAgent
class DeepPathAgent:
    async def decide(self, task_profile: TaskProfile, nodes: List[NodeStatus]) -> SchedulingDecision:
        """LLM 驱动的调度决策"""

    def think(self, context: dict) -> str:
        """ReAct Thought"""

    def act(self, action: str, params: dict) -> dict:
        """ReAct Action"""

    def observe(self, observation: dict) -> None:
        """ReAct Observation"""
```

---

## 10. 测试策略

### 单元测试 (覆盖率目标 >80%)

| 测试文件 | 覆盖范围 | 关键断言 |
|----------|----------|----------|
| `test_task_profile.py` | TaskProfile 创建和验证 | 资源需求正确提取 |
| `test_node_score.py` | NodeScore 计算 | 评分公式正确 |
| `test_default_analyzer.py` | 任务分析逻辑 | 能区分 GPU/CPU 任务 |
| `test_multi_dim_scorer.py` | 多维度评分 | 权重配置生效 |
| `test_resource_validator.py` | 安全验证 | 资源不足时拒绝 |
| `test_memory_layer.py` | 记忆存储 | 记录和查询正确 |
| `test_router.py` | 路由决策 | 复杂任务走 Deep Path |
| `test_fast_scheduler.py` | Fast Path | 评分最高节点被选中 |
| `test_deep_path_agent.py` | Deep Path | LLM 调用和降级 |
| `test_fallback.py` | Fallback | LLM 失败时自动降级 |

### 集成测试

| 测试文件 | 覆盖范围 | 验收标准 |
|----------|----------|----------|
| `test_agentic_scheduler.py` | 完整调度流程 | 能选择节点并派发 |
| `test_with_llm.py` | LLM 集成 | Deep Path 正常工作 |
| `test_fallback_integration.py` | 降级集成 | LLM 失败时 Fast Path 接管 |

### 基准测试

```python
# benchmark_results.md
| 场景 | Fast Path 延迟 | Deep Path 延迟 | 成功率 |
|------|----------------|---------------|--------|
| 简单 GPU 任务 | <10ms | N/A | >99% |
| 复杂 GPU 任务 | <50ms | 500-2000ms | >95% |
| LLM 故障时 | <20ms | N/A | >99% |
| 高负载 (100 并发) | <100ms | N/A | >98% |
```

---

## 11. 与现有 AlgoStudio 代码的集成点

### 11.1 TaskManager 复用策略

现有 `TaskManager` 保持不变，仅修改 `dispatch_task()` 方法：

```python
# src/algo_studio/core/task.py

# [修改] dispatch_task 方法
def dispatch_task(self, task_id: str, ray_client: "RayClient") -> bool:
    # ... 保留现有初始化代码 ...

    # [替换] 使用 AgenticScheduler 替代简单的节点选择
    from algo_studio.core.scheduler import AgenticScheduler

    scheduler = AgenticScheduler()

    # 获取调度决策
    decision = scheduler.schedule(task)

    if not decision.selected_node:
        self.update_status(task_id, TaskStatus.FAILED, error="No available node")
        return False

    # 使用决策中的节点
    selected_node = decision.selected_node
    task.assigned_node = selected_node.hostname or selected_node.ip or selected_node.node_id

    # ... 后续代码保持不变 ...
```

### 11.2 RayClient 扩展策略

`RayClient` 保持现有接口不变，新增可选的调度上下文：

```python
# src/algo_studio/core/ray_client.py

class RayClient:
    # ... 现有代码保持不变 ...

    def submit_task_with_decision(self, func, decision: SchedulingDecision, *args, **kwargs):
        """
        使用调度决策提交任务（保留原有方法以兼容）

        Args:
            func: Ray remote function
            decision: 调度决策结果
            *args, **kwargs: 其他参数
        """
        node_ip = decision.selected_node.ip if decision.selected_node else None
        return self.submit_task(func, *args, node_ip=node_ip, **kwargs)
```

### 11.3 API 层对接

新增调度器状态 API 端点：

```python
# src/algo_studio/api/routes/scheduler.py

from fastapi import APIRouter, HTTPException
from algo_studio.core.scheduler import AgenticScheduler

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

scheduler = AgenticScheduler()

@router.get("/status")
async def get_scheduler_status():
    """获取调度器状态"""
    return {
        "status": "healthy",
        "fast_path_enabled": True,
        "deep_path_enabled": True,
        "memory_layer_available": True,
    }

@router.get("/decision/{task_id}")
async def get_decision(task_id: str):
    """获取历史调度决策"""
    decision = scheduler.memory.get_decision(task_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision

@router.get("/nodes/{node_id}/characteristics")
async def get_node_characteristics(node_id: str):
    """获取节点特征"""
    chars = scheduler.memory.get_node_characteristics(node_id)
    if not chars:
        raise HTTPException(status_code=404, detail="Node not found")
    return chars

@router.post("/config")
async def update_scheduler_config(config: SchedulerConfig):
    """更新调度器配置"""
    scheduler.update_config(config)
    return {"status": "updated"}
```

### 11.4 数据模型扩展

```python
# src/algo_studio/api/models.py

# [新增] 调度器相关模型
from pydantic import BaseModel
from typing import Optional, List

class SchedulerConfig(BaseModel):
    """调度器配置"""
    fast_path_threshold: int = 5  # 复杂度 >=5 走 Deep Path
    deep_path_timeout_seconds: float = 2.0
    fallback_on_error: bool = True
    cache_decisions: bool = True
    cache_ttl_hours: int = 24

class NodeCharacteristicsResponse(BaseModel):
    """节点特征响应"""
    node_id: str
    hostname: str
    success_rate: float
    avg_task_duration_minutes: float
    train_success_rate: float
    infer_success_rate: float
    verify_success_rate: float
    is_healthy: bool

class SchedulingDecisionResponse(BaseModel):
    """调度决策响应"""
    decision_id: str
    task_id: str
    selected_node: Optional[str]
    routing_path: str
    confidence: float
    reasoning: str
    created_at: str
```

---

## 12. 风险评估和缓解措施

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| LLM 响应延迟影响调度时效 | 中 | Fast Path 降级机制 |
| LLM 幻觉导致错误调度 | 中 | SafetyValidator 安全校验 |
| 系统复杂度增加 | 低 | 渐进式实施 |
| 节点状态感知延迟 | 低 | 定期心跳 + 缓存 |
| Memory Layer 数据丢失 | 低 | 定期持久化 + Redis 备份 |

---

## 13. 验收标准总结

### Phase 1 验收

- [ ] `TaskProfile` 能正确提取任务特征
- [ ] `MultiDimNodeScorer` 能对节点进行多维度评分
- [ ] Fast Path 调度延迟 <50ms
- [ ] 单元测试覆盖率 >80%

### Phase 2 验收

- [ ] Memory Layer 能记录调度历史
- [ ] 节点特征能正确学习和查询
- [ ] 路由机制能区分 Fast/Deep Path
- [ ] 集成测试通过

### Phase 3 验收

- [ ] LLM Deep Path 能正常工作
- [ ] Fallback 降级机制有效
- [ ] 超时处理正确

### Phase 4 验收

- [ ] 支持配置化管理
- [ ] 监控指标可采集
- [ ] 告警规则配置完成
- [ ] 运维文档完整

---

## 14. Manager 评估

| 维度 | 评分 (1-10) | 说明 |
|------|-------------|------|
| 完整性 | 10 | 覆盖接口定义、数据结构、实施计划、测试策略 |
| 逻辑性 | 9 | 混合架构方案合理，接口定义清晰 |
| 可行性 | 9 | 9 周路线图可行，Phase 1 最简单，可渐进实施 |
| 创新性 | 7 | 混合架构是常见设计模式 |

**总体评价:** 报告完整详细，架构设计合理可行。接口定义清晰，与现有代码集成方案明确。

**建议:** 可以从 Phase 1 增强规则引擎开始，逐步过渡到 LLM Deep Path。

---

**RESEARCH COMPLETE**
