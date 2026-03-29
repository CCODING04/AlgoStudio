# 公平调度算法设计文档

**任务:** Phase 2 Round 1 - 公平调度算法设计
**负责人:** @ai-scheduling-engineer
**日期:** 2026-03-26
**版本:** v1.0

---

## 1. 设计目标

### 1.1 问题分析

原简单 FIFO 调度的问题:
1. **低使用率用户获得过高优先级**: 用户 A 只用了 10%，用户 B 用了 90%，A 的任务总是优先
2. **可能导致低使用率用户抢占所有空闲资源**: 即使高使用率用户有紧急任务，也可能排队
3. **缺乏时间公平性**: 长期未调度的任务应该获得补偿
4. **无层级队列**: 高优先级任务无法优先

### 1.2 设计目标

- 实现加权公平队列 (Weighted Fair Queuing)
- 支持层级队列调度 (GLOBAL → TEAM → USER)
- 防止低使用率用户过度抢占资源
- 防止任务饿死 (starvation)

---

## 2. 公平调度算法

### 2.1 优先级计算公式

```python
def calculate_task_priority(task: Task, quota: Quota, usage: QuotaUsage,
                            now: datetime) -> float:
    """
    计算任务优先级 (考虑配额公平性，防止饥饿)

    改进点:
    1. 引入任务等待时间补偿
    2. 限制低使用率用户的优先级优势上限
    3. 考虑资源类型的公平性
    """
    base_priority = task.priority * 10  # 基础优先级 1-100

    # 1. 资源需求紧迫度
    resource_demand = (
        task.requested_resources.gpu_count * 10 +
        task.requested_resources.gpu_memory_gb +
        task.requested_resources.cpu_cores +
        task.requested_resources.memory_gb * 0.5
    )

    # 2. 配额使用率因子 (带上限，防止过度倾斜)
    if quota.limits.gpu_count > 0:
        usage_ratio = min(usage.gpu_count_used / quota.limits.gpu_count, 0.8)
    else:
        usage_ratio = 0.5

    fairness_bonus = 1.0 - usage_ratio * 0.8

    # 3. 等待时间补偿 (防止饥饿)
    wait_hours = (now - task.created_at).total_seconds() / 3600
    wait_compensation = min(wait_hours * 0.05, 0.5)

    # 4. 综合优先级
    fairness_factor = 0.5 + 0.3 * fairness_bonus + 0.2 * wait_compensation
    final_priority = base_priority * fairness_factor

    # 小任务优先
    if resource_demand < 10:
        final_priority *= 1.1

    return final_priority
```

### 2.2 公式详解

```
final_priority = base_priority × (
    0.5 +                                    # 基础权重
    0.3 × (1 - min(usage_ratio, 0.8) × 0.8) +  # 公平加成 (上限 0.24)
    0.2 × min(wait_hours × 0.05, 0.5)        # 等待补偿 (上限 0.1)
) × resource_demand_factor
```

### 2.3 参数说明

| 参数 | 值 | 说明 |
|------|-----|------|
| 基础权重 | 0.5 | 保证高优先级任务的基础竞争力 |
| 公平加成系数 | 0.3 | 公平性因素占总权重 30% |
| 使用率上限 | 0.8 | 防止低使用率用户获得超过 24% 的加成 |
| 等待补偿系数 | 0.2 | 等待时间因素占总权重 20% |
| 等待增长率 | 0.05/hour | 每小时等待增加 5% 优先级 |
| 等待补偿上限 | 0.5 | 最多补偿 50% |

### 2.4 业界对照

| 系统 | 等待补偿率 | 使用率上限 | 说明 |
|------|------------|------------|------|
| **slurm** | 20-50%/hour | 0.5-0.8 | Age factor 随等待时间增长，上限 50% |
| **YARN** | Fair Share 权重 | 0.5-1.0 | 资源不足时权重决定调度顺序 |
| **Kubernetes** | 0-100% 优先级权重 | 无明确上限 | Pod 优先级影响抢占顺序 |
| **本研究** | **5%/hour** | **0.8 (80%)** | 与 slurm 类似的等待补偿机制 |

---

## 3. 层级队列调度

### 3.1 队列结构

```
┌─────────────────────────────────────────────────────────────┐
│                     GLOBAL QUEUE                            │
│  (所有任务进入，按优先级排序)                                  │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  TEAM A QUEUE │ │  TEAM B QUEUE │ │  TEAM C QUEUE │
│  (权重: 0.4)  │ │  (权重: 0.3)  │ │  (权重: 0.3)  │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  USER A1 (0.6)│ │  USER B1 (0.5)│ │  USER C1 (0.5)│
│  USER A2 (0.4)│ │               │ │               │
└───────────────┘ └───────────────┘ └───────────────┘
```

### 3.2 调度流程

```python
class HierarchicalScheduler:
    """层级队列调度器"""

    def schedule(self, pending_tasks: List[Task],
                 available_resources: ResourceQuota) -> List[SchedulingDecision]:
        """
        层级调度流程:

        1. 按层级分组任务 (GLOBAL → TEAM → USER)
        2. 计算每层级的可用配额
        3. 在每层级内使用公平调度
        4. 合并结果返回
        """

        # 1. 按用户和团队分组
        team_groups = self._group_by_team(pending_tasks)
        user_groups = self._group_by_user(pending_tasks)

        # 2. 计算团队权重 (基于配额比例)
        team_weights = self._calculate_team_weights(team_groups)

        # 3. 调度决策
        decisions = []

        # 先调度高优先级任务
        sorted_tasks = sorted(pending_tasks,
                             key=lambda t: self._get_priority_score(t),
                             reverse=True)

        for task in sorted_tasks:
            if self._can_schedule(task, available_resources):
                decision = self._schedule_task(task)
                decisions.append(decision)
                available_resources = self._subtract_resources(
                    available_resources, task.requested_resources
                )

        return decisions

    def _get_priority_score(self, task: Task) -> float:
        """计算任务优先级分数"""
        quota = self.quota_manager._get_effective_quota(
            task.user_id, task.team_id
        )
        usage = self.quota_manager.store.get_usage(quota.quota_id) if quota else None

        return calculate_task_priority(task, quota, usage, datetime.now())
```

---

## 4. 加权公平队列实现

### 4.1 加权轮询

```python
class WeightedFairQueue:
    """加权公平队列"""

    def __init__(self):
        self.queues: Dict[str, List[Task]] = {}  # user_id -> tasks
        self.weights: Dict[str, float] = {}       # user_id -> weight

    def enqueue(self, task: Task, weight: float):
        """入队"""
        user_id = task.user_id
        if user_id not in self.queues:
            self.queues[user_id] = []
            self.weights[user_id] = weight
        self.queues[user_id].append(task)

    def dequeue(self) -> Optional[Task]:
        """出队 (加权轮询)"""
        if not self.queues:
            return None

        # 找出当前应该调度的队列
        selected_user = self._select_queue()
        if not selected_user:
            return None

        return self.queues[selected_user].pop(0)

    def _select_queue(self) -> Optional[str]:
        """选择下一个队列 (Weighted Round Robin)"""
        # 计算虚拟时间
        min_virtual_time = float('inf')
        selected = None

        for user_id, queue in self.queues.items():
            if not queue:
                continue

            weight = self.weights.get(user_id, 1.0)
            # 虚拟时间 = 任务数 / 权重
            virtual_time = len(queue) / weight

            if virtual_time < min_virtual_time:
                min_virtual_time = virtual_time
                selected = user_id

        return selected
```

### 4.2 资源预留

```python
class ResourceReservation:
    """资源预留管理器"""

    def __init__(self, quota_manager: QuotaManager):
        self.quota_manager = quota_manager
        self.reservations: Dict[str, ResourceQuota] = {}

    def reserve(self, task_id: str, resources: ResourceQuota,
                quota_id: str) -> bool:
        """预留资源"""
        success = self.quota_manager.allocate_resources(quota_id, resources)
        if success:
            self.reservations[task_id] = resources
        return success

    def release(self, task_id: str, quota_id: str) -> bool:
        """释放预留"""
        resources = self.reservations.pop(task_id, None)
        if resources:
            return self.quota_manager.release_resources(quota_id, resources)
        return False
```

---

## 5. 与 AgenticScheduler 集成

### 5.1 集成点

```python
# src/algo_studio/core/scheduler/agentic_scheduler.py

class AgenticScheduler:
    def __init__(self, quota_manager: QuotaManager = None, ...):
        # ... existing code ...
        self.quota_manager = quota_manager
        self.quota_validator = QuotaValidator(quota_manager) if quota_manager else None
        self.fair_scheduler = HierarchicalScheduler(quota_manager)

    def schedule(self, task: Task) -> SchedulingDecision:
        # 原有分析逻辑...

        # 集成公平调度
        if self.quota_manager:
            # 获取所有待调度任务
            pending_tasks = self.task_manager.list_tasks(status=TaskStatus.PENDING)

            # 使用公平调度算法排序
            sorted_tasks = self.fair_scheduler.sort_by_priority(pending_tasks)

            # 验证配额约束
            if self.quota_validator:
                for t in sorted_tasks:
                    validation = self.quota_validator.validate_scheduling(
                        decision, t
                    )
                    if not validation.is_valid:
                        # 跳过或记录警告
                        pass

        # ... rest of existing code ...
```

### 5.2 调度决策增强

```python
@dataclass
class SchedulingDecision:
    # ... existing fields ...
    fairness_score: float = 0.0          # 公平性得分
    wait_time_hours: float = 0.0         # 等待时间
    quota_usage_ratio: float = 0.0       # 配额使用率
    scheduling_path: str = "fast"        # 调度路径
```

---

## 6. 参数标定

### 6.1 参数敏感性分析

| 参数 | 当前值 | 变体 A | 变体 B | 变体 C |
|------|--------|--------|--------|--------|
| 等待补偿率 | 0.05/hr | 0.03/hr | 0.05/hr | 0.08/hr |
| 使用率上限 | 0.8 | 0.8 | 0.6 | 0.8 |

### 6.2 验证指标

| 指标 | 目标值 | 告警阈值 |
|------|--------|----------|
| Jain's Fairness Index | >= 0.7 | < 0.7 |
| 高优先级任务延迟率 | < 基线 1.2x | > 1.2x |
| 饿死任务数量 | 0 | > 0 |
| 平均等待时间 | 持平或下降 | > 基线 20% |

### 6.3 验证方案

1. **仿真测试** (Week 1-2)
   - 3 用户竞争同一 GPU，每用户初始使用率不同 (20%, 50%, 80%)
   - 统计 Jain's Fairness Index

2. **灰度发布** (Week 3-4)
   - 先对 10% 流量启用新算法
   - 观察任务完成率、等待时间变化

---

## 7. 公平调度配置

### 7.1 配置项

```python
# src/algo_studio/core/config.py

FAIR_SCHEDULING_CONFIG = {
    "enabled": True,
    "base_weight": 0.5,
    "fairness_weight": 0.3,
    "wait_compensation_weight": 0.2,
    "wait_compensation_rate": 0.05,  # per hour
    "wait_compensation_cap": 0.5,
    "usage_ratio_cap": 0.8,
    "small_task_threshold": 10,
    "small_task_bonus": 1.1,
    "queue_timeout_minutes": 30,
    "starvation_threshold_hours": 2,
}
```

### 7.2 禁用选项

```python
# 简单模式 - 禁用公平调度
scheduler = AgenticScheduler(
    quota_manager=quota_manager,
    fair_scheduling_enabled=False  # 使用简单 FIFO
)
```

---

## 8. 实施任务

### 8.1 Week 3 任务

| 任务 | 人天 | 交付物 | 验收标准 |
|------|------|--------|----------|
| 实现公平调度算法 | 1.5 | fair_scheduler.py | 算法测试通过 |
| 集成到 AgenticScheduler | 1.5 | agentic_scheduler.py | 调度时校验配额 |
| 集成测试 | 0.5 | test_quota_integration.py | 端到端测试通过 |

---

## 9. 验收标准

- [ ] 仿真测试 Jain's Fairness Index >= 0.7
- [ ] 高优先级任务延迟 < 基线 1.2 倍
- [ ] 无任务等待超过 2 小时 (饿死检测)
- [ ] 参数敏感性分析报告已通过评审
- [ ] 灰度发布方案已制定

---

**文档状态:** 设计完成
**下一步:** 实现 Phase 2 Round 2 任务
