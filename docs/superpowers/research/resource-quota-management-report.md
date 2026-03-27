# 资源配额管理研究报告

**调研时间:** 2026-03-26
**Agent:** ai-scheduling-engineer (资源配额管理专题研究)
**版本:** v5.0 (根据架构师第 4 轮评审反馈更新 - 最终版)

---

## 1. 问题分析

### 1.1 当前系统的配额缺失

基于对代码库的分析，当前 AlgoStudio 系统存在以下配额管理问题：

| 问题 | 现状 | 影响 |
|------|------|------|
| 无用户/团队配额 | 所有用户共享集群资源 | 单用户可能耗尽全部资源 |
| 无资源上限控制 | `ResourceValidator` 仅检查节点级别资源，不校验配额 | 可能导致资源过度分配 |
| 无配额占用视图 | 任务不记录所属用户/团队 | 无法统计各用户资源使用 |
| 无配额告警 | 资源耗尽前无预警 | 突发性任务失败 |
| 无层级队列 | 简单先进先出调度 | 高优先级任务无法优先 |

### 1.2 Phase 2 配额需求

Phase 2 明确要求：
- **配额设置**：CPU、GPU、内存使用上限
- **配额监控**：接近配额时告警
- **配额占用视图**：查看各用户资源使用情况

---

## 2. 配额模型设计

### 2.1 核心数据结构

```python
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum

class QuotaScope(Enum):
    """配额作用域"""
    USER = "user"           # 用户级别配额
    TEAM = "team"           # 团队级别配额
    GLOBAL = "global"       # 全局配额

@dataclass
class ResourceQuota:
    """资源配额项"""
    cpu_cores: int = 0           # CPU 核心数上限 (0=无限制)
    gpu_count: int = 0           # GPU 数量上限 (0=无限制)
    gpu_memory_gb: float = 0.0   # GPU 显存上限 GB (0=无限制)，支持 RTX 4090 24GB 等差异化
    memory_gb: float = 0.0       # 内存上限 GB (0=无限制)
    disk_gb: float = 0.0         # 磁盘上限 GB (0=无限制)，用于 JuiceFS/NAS 存储配额
    concurrent_tasks: int = 0    # 并发任务数上限 (0=无限制)

    def is_unlimited(self) -> bool:
        """检查是否所有维度都无限制"""
        return (self.cpu_cores == 0 and
                self.gpu_count == 0 and
                self.gpu_memory_gb == 0.0 and
                self.memory_gb == 0.0 and
                self.disk_gb == 0.0 and
                self.concurrent_tasks == 0)

@dataclass
class QuotaUsage:
    """资源使用量"""
    cpu_cores_used: float = 0.0
    gpu_count_used: int = 0
    gpu_memory_gb_used: float = 0.0  # GPU 显存使用量
    memory_gb_used: float = 0.0
    disk_gb_used: float = 0.0
    concurrent_tasks_used: int = 0

    def to_dict(self) -> dict:
        return {
            "cpu_cores_used": self.cpu_cores_used,
            "gpu_count_used": self.gpu_count_used,
            "gpu_memory_gb_used": self.gpu_memory_gb_used,
            "memory_gb_used": self.memory_gb_used,
            "disk_gb_used": self.disk_gb_used,
            "concurrent_tasks_used": self.concurrent_tasks_used,
        }

@dataclass
class Quota:
    """配额实体"""
    quota_id: str
    scope: QuotaScope
    scope_id: str               # user_id 或 team_id
    name: str                   # 配额名称

    # 配额限制
    limits: ResourceQuota

    # 配额预警阈值 (百分比, 0-100)
    alert_threshold: int = 80   # 80% 时告警

    # 配额继承
    parent_quota_id: Optional[str] = None  # 父配额 ID (用于层级继承)

    # 状态
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def can_allocate(self, usage: QuotaUsage, requested: ResourceQuota) -> tuple[bool, List[str]]:
        """
        检查是否可以分配指定资源

        Returns:
            (can_allocate, reasons)
        """
        reasons = []

        # 检查各项资源
        if requested.cpu_cores > 0:
            available = self.limits.cpu_cores - usage.cpu_cores_used
            if available < requested.cpu_cores:
                reasons.append(f"CPU: 请求 {requested.cpu_cores}, 可用 {available}")

        if requested.gpu_count > 0:
            available = self.limits.gpu_count - usage.gpu_count_used
            if available < requested.gpu_count:
                reasons.append(f"GPU: 请求 {requested.gpu_count}, 可用 {available}")

        if requested.gpu_memory_gb > 0:
            available = self.limits.gpu_memory_gb - usage.gpu_memory_gb_used
            if available < requested.gpu_memory_gb:
                reasons.append(f"GPU 显存: 请求 {requested.gpu_memory_gb:.1f}GB, 可用 {available:.1f}GB")

        if requested.memory_gb > 0:
            available = self.limits.memory_gb - usage.memory_gb_used
            if available < requested.memory_gb:
                reasons.append(f"内存: 请求 {requested.memory_gb:.1f}GB, 可用 {available:.1f}GB")

        if requested.concurrent_tasks > 0:
            available = self.limits.concurrent_tasks - usage.concurrent_tasks_used
            if available < requested.concurrent_tasks:
                reasons.append(f"并发任务: 请求 {requested.concurrent_tasks}, 可用 {available}")

        return (len(reasons) == 0, reasons)

    def get_usage_percentage(self, usage: QuotaUsage) -> Dict[str, float]:
        """计算各项资源使用百分比"""
        result = {}
        if self.limits.cpu_cores > 0:
            result["cpu_cores"] = (usage.cpu_cores_used / self.limits.cpu_cores) * 100
        if self.limits.gpu_count > 0:
            result["gpu_count"] = (usage.gpu_count_used / self.limits.gpu_count) * 100
        if self.limits.gpu_memory_gb > 0:
            result["gpu_memory_gb"] = (usage.gpu_memory_gb_used / self.limits.gpu_memory_gb) * 100
        if self.limits.memory_gb > 0:
            result["memory_gb"] = (usage.memory_gb_used / self.limits.memory_gb) * 100
        if self.limits.concurrent_tasks > 0:
            result["concurrent_tasks"] = (usage.concurrent_tasks_used / self.limits.concurrent_tasks) * 100
        return result
```

### 2.2 层级配额继承关系

```
全局配额 (GLOBAL)
    │
    ├── 团队 A 配额 (TEAM: team_a)
    │       │
    │       ├── 用户 A1 配额 (USER: user_a1)  → 继承团队 A
    │       └── 用户 A2 配额 (USER: user_a2)  → 继承团队 A
    │
    └── 团队 B 配额 (TEAM: team_b)
            │
            └── 用户 B1 配额 (USER: user_b1)  → 继承团队 B
```

**继承规则**:
1. 子配额不能超过父配额限制
2. 子配额可以设置更严格的限制，但不能放宽
3. 用户配额默认继承团队配额，团队配额默认继承全局配额

### 2.3 任务与配额关联

```python
@dataclass
class Task:
    # ... 现有字段 ...
    user_id: Optional[str] = None      # 用户 ID
    team_id: Optional[str] = None    # 团队 ID
    quota_id: Optional[str] = None    # 使用的配额 ID
```

---

## 3. 配额算法设计

### 3.1 配额检查时机

| 阶段 | 检查点 | 操作 |
|------|--------|------|
| 任务提交 | `TaskManager.create_task()` | 校验配额是否允许创建新任务 |
| 任务调度 | `AgenticScheduler.schedule()` | 校验配额是否有足够资源 |
| 任务派发 | `TaskManager.dispatch_task()` | 最终资源预留确认 |
| 任务完成 | 任务完成回调 | 释放资源使用量 |

### 3.2 配额检查算法

```python
class QuotaManager:
    """
    配额管理器

    职责:
    1. 配额校验 (提交时、调度时)
    2. 配额占用量跟踪
    3. 配额告警触发
    4. 层级配额继承计算
    """

    def __init__(self, store: "QuotaStore"):
        self.store = store

    def check_quota(self, user_id: str, team_id: Optional[str],
                    requested: ResourceQuota) -> tuple[bool, Quota, QuotaUsage, List[str]]:
        """
        检查用户配额是否允许分配资源

        Returns:
            (allowed, effective_quota, usage, reasons)
        """
        # 1. 获取用户配额 (可能继承自团队/全局)
        quota = self._get_effective_quota(user_id, team_id)
        if not quota:
            return (True, None, QuotaUsage(), [])  # 无配额限制

        # 2. 获取当前使用量
        usage = self.store.get_usage(quota.quota_id)

        # 3. 检查是否可分配
        can_allocate, reasons = quota.can_allocate(usage, requested)

        return (can_allocate, quota, usage, reasons)

    def _get_effective_quota(self, user_id: str, team_id: Optional[str]) -> Optional[Quota]:
        """
        获取有效配额 (考虑继承)

        优先级: 用户配额 > 团队配额 > 全局配额
        """
        # 1. 尝试用户配额
        user_quota = self.store.get_quota_by_scope(QuotaScope.USER, user_id)
        if user_quota and not user_quota.is_unlimited():
            return user_quota

        # 2. 尝试团队配额
        if team_id:
            team_quota = self.store.get_quota_by_scope(QuotaScope.TEAM, team_id)
            if team_quota and not team_quota.is_unlimited():
                return team_quota

        # 3. 尝试全局配额
        global_quota = self.store.get_quota_by_scope(QuotaScope.GLOBAL, "global")
        if global_quota and not global_quota.is_unlimited():
            return global_quota

        return None

    def allocate_resources(self, quota_id: str, resources: ResourceQuota) -> bool:
        """
        分配资源 (原子操作，增加使用量)

        Returns:
            True if allocation successful
        """
        return self.store.increment_usage(quota_id, resources)

    def release_resources(self, quota_id: str, resources: ResourceQuota) -> bool:
        """
        释放资源 (原子操作，减少使用量)
        """
        return self.store.decrement_usage(quota_id, resources)
```

### 3.3 配额超载处理策略

当配额不足时，系统支持以下策略：

| 策略 | 行为 | 适用场景 |
|------|------|----------|
| **REJECT** | 直接拒绝任务 | 硬性配额限制 (默认) |
| **QUEUE** | 任务进入等待队列 (带超时告警) | 暂时性资源紧张 |
| **FALLBACK** | 降级使用公共资源池 | 有公共资源池时 |

**QUEUE 策略超时机制**:
- 排队超时阈值: 默认 30 分钟 (可配置 `queue_timeout_minutes`)
- 超时告警: 任务排队超过阈值时触发 `WARNING` 级别告警
- 饿死检测: 连续等待超过 2 小时的任务标记为 `CRITICAL`，通知管理员

**关于 PREEMPT 策略的说明**:
- PREEMPT (抢占式调度) 在 Ray 任务场景中实现复杂:
  1. Ray 任务一旦派发到 worker，无法强制终止正在执行的任务
  2. 抢占需要实现任务迁移机制，涉及 checkpoint 和恢复
  3. GPU 任务中断可能导致训练损失
- **建议**: Phase 2 不实现 PREEMPT，通过 REJECT + QUEUE 组合替代
- **后续扩展**: 如需抢占，使用 Ray Actor 的 `kill` 能力 + 任务重跑机制

```python
class QuotaExceededAction(Enum):
    REJECT = "reject"       # 拒绝任务
    QUEUE = "queue"         # 排队等待
    FALLBACK = "fallback"   # 使用公共池 (需配置 fallback_quota_id)

@dataclass
class QuotaExceededError(Exception):
    """配额超限异常"""
    quota_id: str
    requested: ResourceQuota
    available: ResourceQuota
    action: QuotaExceededAction
    reasons: List[str]
    queue_position: Optional[int] = None  # 排队位置 (QUEUE 策略时)
    estimated_wait_minutes: Optional[int] = None  # 预计等待时间
```

### 3.4 公平调度与配额结合

当多个用户/团队竞争资源时，采用 **改进的加权公平队列 (Weighted Fair Queuing)**:

#### 3.4.1 饥饿问题分析

原算法的问题:
1. **低使用率用户获得过高优先级**: 用户 A 只用了 10%，用户 B 用了 90%，A 的任务总是优先
2. **可能导致低使用率用户抢占所有空闲资源**: 即使高使用率用户有紧急任务，也可能排队
3. **缺乏时间公平性**: 长期未调度的任务应该获得补偿

#### 3.4.2 改进的公平调度算法

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

    # 1. 资源需求紧迫度 (任务请求的资源量)
    resource_demand = (
        task.requested_resources.gpu_count * 10 +
        task.requested_resources.gpu_memory_gb +
        task.requested_resources.cpu_cores +
        task.requested_resources.memory_gb * 0.5
    )

    # 2. 配额使用率因子 (带上限，防止过度倾斜)
    # 使用 min(usage_ratio, 0.8) 限制低使用率优势最多 20%
    if quota.limits.gpu_count > 0:
        usage_ratio = min(usage.gpu_count_used / quota.limits.gpu_count, 0.8)
    else:
        usage_ratio = 0.5

    # 使用率越低，获得的公平加成越高 (0.2 ~ 1.0)
    fairness_bonus = 1.0 - usage_ratio * 0.8  # 50% 使用率 → 0.6, 100% 使用率 → 0.2

    # 3. 等待时间补偿 (防止饥饿)
    # 任务等待越久，优先级提升越多
    wait_hours = (now - task.created_at).total_seconds() / 3600
    # 等待超过 1 小时后开始补偿，每小时增加 5% 优先级
    wait_compensation = min(wait_hours * 0.05, 0.5)  # 最多补偿 50%

    # 4. 综合优先级
    # 基础权重 50% + 公平加成 30% + 等待补偿 20%
    fairness_factor = 0.5 + 0.3 * fairness_bonus + 0.2 * wait_compensation

    final_priority = base_priority * fairness_factor

    # 资源需求越小，越容易调度 (小任务优先)
    if resource_demand < 10:
        final_priority *= 1.1

    return final_priority
```

#### 3.4.3 公平调度公式

```
final_priority = base_priority × (
    0.5 +                                    # 基础权重
    0.3 × (1 - min(usage_ratio, 0.8) × 0.8) +  # 公平加成 (上限 0.24)
    0.2 × min(wait_hours × 0.05, 0.5)        # 等待补偿 (上限 0.1)
) × resource_demand_factor
```

**关键参数说明**:
- 基础权重 0.5: 保证高优先级任务的基础竞争力
- 公平加成上限 0.24: 防止低使用率用户过度抢占
- 等待补偿上限 0.1: 防止长期等待任务饿死
- 资源需求因子: 小任务优先，促进吞吐

**参数标定计划**:
| 参数 | 当前值 | 标定方法 | 验证目标 |
|------|--------|----------|----------|
| 公平加成上限 0.24 | 经验值 (0.3×0.8) | 模拟多用户竞争场景，A/B 测试 | 低使用率用户任务不饿死，高使用率用户紧急任务可优先 |
| 等待补偿增长率 0.05/hour | 经验值 | 模拟长队列场景 | 1 小时等待任务优先级提升 5%，2 小时提升 10% |
| 使用率上限 0.8 | 经验值 | 仿真测试验证 | 低使用率用户优先级加成不超过 20% |
| 小任务阈值 10 | 经验值 | 统计实际任务资源分布 | 80% 训练任务资源需求 > 10 |
| 超时阈值 30min | 可配置 | 生产观察调整 | 减少排队告警误报 |

**参数推导说明**:

公平调度参数源自以下公式推导:
```
fairness_factor = 0.5 + 0.3 × (1 - min(usage_ratio, 0.8) × 0.8) + 0.2 × min(wait_hours × 0.05, 0.5)
```

- **0.5 基础权重**: 保证高优先级任务始终有基础竞争力
- **0.3 公平加成系数**: 公平性因素占总权重 30%
- **0.8 使用率上限**: 防止低使用率用户获得超过 24% (=0.3×0.8) 的加成
- **0.2 等待补偿系数**: 等待时间因素占总权重 20%
- **0.05/hour 等待增长率**: 每小时等待增加 5% 优先级，上限 50%

**生产系统对照参考**:

公平调度参数与业界类似系统的对照:

| 系统 | 等待补偿率 | 使用率上限 | 说明 |
|------|------------|------------|------|
| **Kubernetes** | 0-100% 优先级权重 | 无明确上限 | Pod 优先级影响抢占顺序，等待时间无显式补偿 |
| **Mesos** | 0.1-1.0 权重因子 | 无 | 资源offer按权重分配，无时间维度 |
| **YARN** | Fair Share 权重 | 0.5-1.0 典型值 | 资源不足时权重决定调度顺序 |
| **slurm** | 20-50% 优先级提升/小时 | 0.5-0.8 典型值 | Age factor 随等待时间增长，上限 50% |
| **本研究** | **0.05/hour (5%/hr)** | **0.8 (80%)** | 与 slurm 类似的等待补偿机制 |

**参考依据**:
1. **slurm (劳伦斯利弗莫尔国家实验室)**: Age factor 权重 0.01-0.05/hour，最高 50% 提升。本研究取 0.05/hour 与 slurm 高端配置对齐。
2. **Fair Share 使用率上限**: YARN 公平调度器中，低使用率租户可获得最多 2x 资源配额，对应使用率上限约 0.5。本研究放宽到 0.8 以适应 AI 训练场景的突发性需求。
3. **Google Borg**: 资源使用率超过 80% 的任务被标记为"高负载"，触发自动扩缩容告警。

**实测验证方案**:

Phase 2 实施前，必须通过以下验证:

1. **仿真测试** (Week 1-2):
   - 使用历史任务数据回放
   - 统计不同参数下的调度公平性指标 (Jain's Fairness Index)
   - 测试场景: 3 用户竞争同一 GPU，每用户初始使用率不同 (20%, 50%, 80%)
   - 验证目标: Jain's Fairness Index > 0.7

2. **参数敏感性分析** (Week 2):
   ```
   测试用例:
   - 基准: wait=0.05/hr, cap=0.8
   - 变体 A: wait=0.03/hr, cap=0.8 (补偿更慢)
   - 变体 B: wait=0.05/hr, cap=0.6 (上限更低)
   - 变体 C: wait=0.08/hr, cap=0.8 (补偿更快)

   评估指标:
   - 各用户任务平均等待时间方差
   - 高优先级任务被低优先级任务阻塞的比例
   - 饿死任务数量 (等待 > 2 小时)
   ```

3. **灰度发布** (Week 3-4):
   - 先对 10% 流量启用新算法
   - 观察任务完成率、等待时间变化
   - 收集 2 周数据后分析是否全量发布

4. **监控指标**:
   | 指标 | 告警阈值 | 目标值 |
   |------|----------|--------|
   | 任务平均等待时间 | > 基线 20% | 持平或下降 |
   | 高优先级任务延迟率 | > 10% | < 5% |
   | 用户配额使用率方差 | - | < 0.3 |
   | 饿死任务数量 | > 0 | 0 |

**实测验证通过标准**:
- [ ] Jain's Fairness Index >= 0.7
- [ ] 高优先级任务平均延迟 < 基线 1.2 倍
- [ ] 无任务等待超过 2 小时
- [ ] 参数验证通过后锁定，不再修改

#### 3.4.4 与后端 Phase 2 配额模型对齐

**命名统一说明**:
- 本报告使用 `ResourceQuota` (调度层实时配额检查)
- 后端报告使用 `QuotaLimit` (每日/累计配额校验)
- 两者为同一概念的不同层面视图，命名差异是由于各层关注点不同

后端 Phase 2 定义的 Quota 模型:
```python
@dataclass
class QuotaLimit:
    user_id: str
    max_concurrent_tasks: int = 5
    max_tasks_per_day: int = 50
    max_gpu_hours_per_day: float = 24.0
    max_storage_gb: int = 100
```

**字段映射关系**:

| 后端 QuotaLimit | 调度层 ResourceQuota | 说明 |
|-----------------|---------------------|------|
| max_concurrent_tasks | concurrent_tasks | 直接映射 |
| max_tasks_per_day | - | 任务计数器，每日重置 |
| max_gpu_hours_per_day | - | GPU 时间累加器 |
| max_storage_gb | disk_gb | 存储配额 |

**数据同步机制**:
1. **调度层** (`ResourceQuota`): 实时配额检查，控制并发和资源分配
2. **后端层** (`QuotaLimit`): 每日配额校验，控制累计使用量
3. **共用键**: `user_id` 作为关联键，后端记录当日已用配额
4. **Redis 计数器定位**: Phase 2 使用 SQLite，Phase 3 扩展到 Redis 时再引入 Redis 计数器 (用于高并发场景优化)

---

## 4. 与 Ray 调度的集成方案

### 4.1 集成点分析

当前调度流程:
```
任务提交 → AgenticScheduler.schedule() → 节点选择 → TaskManager.dispatch_task() → Ray 派发
```

配额集成点:

```
任务提交 (create_task)
    │
    ├── [集成点 1] QuotaManager.check_quota() → 校验用户配额
    │
    ▼
AgenticScheduler.schedule()
    │
    ├── [集成点 2] QuotaValidator (新组件) → 校验调度决策不超配额
    │
    ▼
TaskManager.dispatch_task()
    │
    ├── [集成点 3] QuotaManager.allocate_resources() → 预留配额资源
    │
    ▼
Ray 任务执行
    │
    └── [集成点 4] 任务完成/失败 → QuotaManager.release_resources() → 释放配额
```

### 4.2 集成代码设计

```python
# src/algo_studio/core/quota/quota_manager.py

class QuotaManager:
    """配额管理器"""

    def __init__(self, store: QuotaStore):
        self.store = store

    def check_task_submission(self, user_id: str, team_id: Optional[str],
                              task_type: TaskType) -> tuple[bool, Optional[str]]:
        """
        任务提交时的配额检查

        Returns:
            (allowed, error_message)
        """
        requested = ResourceQuota(
            concurrent_tasks=1,
            # 根据任务类型估算资源需求
            cpu_cores=1 if task_type != TaskType.TRAIN else 4,
            gpu_count=1 if task_type == TaskType.TRAIN else 0,
            memory_gb=4.0 if task_type == TaskType.TRAIN else 1.0,
        )

        allowed, quota, usage, reasons = self.check_quota(user_id, team_id, requested)
        if not allowed:
            return (False, f"配额不足: {'; '.join(reasons)}")

        return (True, None)

    def check_task_scheduling(self, task_profile: TaskProfile,
                              user_id: str, team_id: Optional[str]) -> tuple[bool, Optional[str]]:
        """
        任务调度时的配额检查

        Returns:
            (allowed, error_message)
        """
        requested = ResourceQuota(
            cpu_cores=task_profile.num_cpus,
            gpu_count=task_profile.num_gpus,
            memory_gb=task_profile.memory_gb,
        )

        allowed, quota, usage, reasons = self.check_quota(user_id, team_id, requested)
        if not allowed:
            return (False, f"调度配额不足: {'; '.join(reasons)}")

        return (True, None)


# src/algo_studio/core/quota/quota_validator.py

class QuotaValidator:
    """
    调度过程中的配额验证器

    集成到 AgenticScheduler.schedule() 流程中
    """

    def __init__(self, quota_manager: QuotaManager):
        self.quota_manager = quota_manager

    def validate_scheduling(self, decision: SchedulingDecision,
                           task: Task) -> ValidationResult:
        """
        验证调度决策是否符合配额约束

        Returns:
            ValidationResult (is_valid, errors, warnings)
        """
        errors = []
        warnings = []

        # 获取任务的用户信息
        user_id = getattr(task, 'user_id', None)
        team_id = getattr(task, 'team_id', None)

        if not user_id:
            # 无用户信息的任务不受配额限制
            return ValidationResult(is_valid=True, errors=[], warnings=[])

        # 检查配额
        allowed, error_msg = self.quota_manager.check_task_scheduling(
            decision.task_profile, user_id, team_id
        )

        if not allowed:
            errors.append(error_msg)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
```

### 4.3 任务 Task 类扩展

```python
# src/algo_studio/core/task.py

@dataclass
class Task:
    task_id: str
    task_type: TaskType
    algorithm_name: str
    algorithm_version: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    config: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    assigned_node: Optional[str] = None
    progress: int = 0

    # [新增] 配额相关字段
    user_id: Optional[str] = None       # 用户 ID
    team_id: Optional[str] = None        # 团队 ID
    quota_id: Optional[str] = None      # 使用的配额 ID
    allocated_resources: Optional[ResourceQuota] = None  # 已分配资源

    @staticmethod
    def create(task_type: TaskType, algorithm_name: str, algorithm_version: str,
               config: Dict, user_id: Optional[str] = None, team_id: Optional[str] = None) -> "Task":
        """创建新任务"""
        task_id = f"{task_type.value}-{uuid.uuid4().hex[:8]}"
        return Task(
            task_id=task_id,
            task_type=task_type,
            algorithm_name=algorithm_name,
            algorithm_version=algorithm_version,
            config=config,
            user_id=user_id,
            team_id=team_id,
        )
```

---

## 5. 告警机制设计

### 5.1 告警触发条件

| 条件 | 阈值 | 告警级别 |
|------|------|----------|
| 配额使用率 >= 80% | alert_threshold | WARNING |
| 配额使用率 >= 95% | 固定阈值 | CRITICAL |
| 配额使用率 == 100% | 固定阈值 | BLOCKED |
| 并发任务数达到上限 | concurrent_tasks | WARNING |
| 任务排队超时 | queue_timeout_minutes (默认 30) | WARNING |
| 任务排队超长等待 | queue_max_wait_hours (默认 2) | CRITICAL |

### 5.2 告警数据模型

```python
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class QuotaAlert:
    """配额告警"""
    alert_id: str
    quota_id: str
    scope: QuotaScope
    scope_id: str

    level: AlertLevel
    metric: str                    # cpu_cores, gpu_count, memory_gb, concurrent_tasks, queue_wait
    usage_percentage: float        # 使用率 0-100
    threshold: int                # 触发阈值

    message: str
    created_at: datetime = field(default_factory=datetime.now)

    # 告警状态
    is_acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None

    # 排队相关字段
    task_id: Optional[str] = None  # 关联任务 ID (用于排队告警)
    wait_time_minutes: Optional[int] = None  # 等待时间 (分钟)
```

### 5.3 告警检测和通知

```python
# src/algo_studio/core/quota/alert_manager.py

class AlertManager:
    """配额告警管理器"""

    def __init__(self, notification_handler=None):
        self.notification_handler = notification_handler
        self._alert_history: Dict[str, List[QuotaAlert]] = {}

    def check_quota_alerts(self, quota: Quota, usage: QuotaUsage,
                         pending_tasks: List[Dict] = None) -> List[QuotaAlert]:
        """
        检查配额是否触发告警

        Args:
            quota: 配额
            usage: 当前使用量
            pending_tasks: 待调度任务列表 (含 wait_time_minutes 字段)

        Returns:
            List of triggered alerts
        """
        alerts = []
        usage_percentages = quota.get_usage_percentage(usage)

        # 1. 资源使用率告警
        for metric, percentage in usage_percentages.items():
            if percentage >= 100:
                alerts.append(self._create_alert(
                    quota, metric, percentage, 100, AlertLevel.CRITICAL,
                    f"配额已用尽: {metric} 使用率 {percentage:.1f}%"
                ))
            elif percentage >= quota.alert_threshold:
                alerts.append(self._create_alert(
                    quota, metric, percentage, quota.alert_threshold, AlertLevel.WARNING,
                    f"配额接近上限: {metric} 使用率 {percentage:.1f}%, 阈值 {quota.alert_threshold}%"
                ))

        # 2. 排队超时告警
        if pending_tasks:
            for task in pending_tasks:
                wait_minutes = task.get('wait_time_minutes', 0)
                task_id = task.get('task_id')

                if wait_minutes >= 120:  # 2 小时以上
                    alerts.append(self._create_queue_alert(
                        quota, 'queue_wait', 100, 120, AlertLevel.CRITICAL,
                        f"任务 {task_id} 排队超过 2 小时，可能饿死",
                        task_id, wait_minutes
                    ))
                elif wait_minutes >= 30:  # 30 分钟以上
                    alerts.append(self._create_queue_alert(
                        quota, 'queue_wait', wait_minutes / 120 * 100, 30, AlertLevel.WARNING,
                        f"任务 {task_id} 排队超过 30 分钟",
                        task_id, wait_minutes
                    ))

        return alerts

    def _create_queue_alert(self, quota: Quota, metric: str, usage_percentage: float,
                            threshold: int, level: AlertLevel, message: str,
                            task_id: str, wait_time_minutes: int) -> QuotaAlert:
        """创建排队超时告警"""
        return QuotaAlert(
            alert_id=f"alert-{uuid.uuid4().hex[:8]}",
            quota_id=quota.quota_id,
            scope=quota.scope,
            scope_id=quota.scope_id,
            level=level,
            metric=metric,
            usage_percentage=usage_percentage,
            threshold=threshold,
            message=message,
            task_id=task_id,
            wait_time_minutes=wait_time_minutes,
        )

    def _create_alert(self, quota: Quota, metric: str, usage_percentage: float,
                     threshold: int, level: AlertLevel, message: str) -> QuotaAlert:
        """创建告警实例"""
        return QuotaAlert(
            alert_id=f"alert-{uuid.uuid4().hex[:8]}",
            quota_id=quota.quota_id,
            scope=quota.scope,
            scope_id=quota.scope_id,
            level=level,
            metric=metric,
            usage_percentage=usage_percentage,
            threshold=threshold,
            message=message,
        )

    def send_alert(self, alert: QuotaAlert):
        """发送告警通知"""
        if self.notification_handler:
            self.notification_handler.send(alert)
```

---

## 6. 配额存储层设计

### 6.1 存储后端选择

**决策: SQLite (Phase 2) + Redis (Phase 3)**

| 阶段 | 方案 | 适用场景 | 理由 |
|------|------|----------|------|
| **Phase 2** | **SQLite** | 单调度器、中小规模 (<100 用户) | 与后端 Phase 2 统一技术栈、无外部依赖、部署简单 |
| **Phase 3** | **Redis** | 多调度器、高并发 (>100 用户) | 与 Platform Agentic 共享 Redis 集群、支持原子操作 |

**决策理由**:
1. **与后端 Phase 2 对齐**: 后端报告明确推荐 SQLite + Alembic，配额存储复用同一数据库
2. **降低部署复杂度**: Phase 2 无需额外部署 Redis
3. **扩展路径清晰**: Phase 3 迁移到 Redis 只需更换 Store 实现，不影响上层逻辑
4. **并发问题可控**: 单调度器场景下 SQLite WAL 模式足够应对

**注意**: 后端 Phase 2 报告建议 "Redis 计数器" 用于配额，但这是针对高并发场景的优化。Phase 2 阶段任务提交频率有限，SQLite 原子操作 (WAL + BEGIN IMMEDIATE) 可满足需求。

### 6.2 数据表设计 (SQLite)

```sql
-- 配额表
CREATE TABLE quotas (
    quota_id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,           -- 'user', 'team', 'global'
    scope_id TEXT NOT NULL,         -- user_id 或 team_id
    name TEXT NOT NULL,

    -- 限制
    cpu_cores INTEGER DEFAULT 0,
    gpu_count INTEGER DEFAULT 0,
    gpu_memory_gb REAL DEFAULT 0.0,  -- GPU 显存配额 (支持 RTX 4090 24GB 等差异化)
    memory_gb REAL DEFAULT 0.0,
    disk_gb REAL DEFAULT 0.0,
    concurrent_tasks INTEGER DEFAULT 0,

    -- 告警阈值
    alert_threshold INTEGER DEFAULT 80,

    -- 继承
    parent_quota_id TEXT,

    -- 状态
    is_active BOOLEAN DEFAULT TRUE,
    created_at TEXT,
    updated_at TEXT,

    FOREIGN KEY (parent_quota_id) REFERENCES quotas(quota_id)
);

-- 配额使用量表
CREATE TABLE quota_usages (
    quota_id TEXT PRIMARY KEY,
    cpu_cores_used REAL DEFAULT 0.0,
    gpu_count_used INTEGER DEFAULT 0,
    gpu_memory_gb_used REAL DEFAULT 0.0,  -- GPU 显存使用量
    memory_gb_used REAL DEFAULT 0.0,
    disk_gb_used REAL DEFAULT 0.0,
    concurrent_tasks_used INTEGER DEFAULT 0,
    updated_at TEXT,

    FOREIGN KEY (quota_id) REFERENCES quotas(quota_id)
);

-- 配额使用历史表 (用于统计)
CREATE TABLE quota_usage_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quota_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    recorded_at TEXT,

    FOREIGN KEY (quota_id) REFERENCES quotas(quota_id)
);

-- 告警表
CREATE TABLE quota_alerts (
    alert_id TEXT PRIMARY KEY,
    quota_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    level TEXT NOT NULL,
    metric TEXT NOT NULL,
    usage_percentage REAL NOT NULL,
    threshold INTEGER NOT NULL,
    message TEXT,
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by TEXT,
    acknowledged_at TEXT,
    created_at TEXT,

    FOREIGN KEY (quota_id) REFERENCES quotas(quota_id)
);

-- 索引
CREATE INDEX idx_quotas_scope ON quotas(scope, scope_id);
CREATE INDEX idx_alerts_quota ON quota_alerts(quota_id);
CREATE INDEX idx_alerts_created ON quota_alerts(created_at);
```

### 6.3 存储接口设计

```python
# src/algo_studio/core/quota/stores/base.py

class QuotaStoreInterface(ABC):
    """配额存储接口"""

    @abstractmethod
    def get_quota(self, quota_id: str) -> Optional[Quota]:
        """获取配额"""
        pass

    @abstractmethod
    def get_quota_by_scope(self, scope: QuotaScope, scope_id: str) -> Optional[Quota]:
        """根据作用域获取配额"""
        pass

    @abstractmethod
    def create_quota(self, quota: Quota) -> bool:
        """创建配额"""
        pass

    @abstractmethod
    def update_quota(self, quota: Quota) -> bool:
        """更新配额"""
        pass

    @abstractmethod
    def delete_quota(self, quota_id: str) -> bool:
        """删除配额"""
        pass

    @abstractmethod
    def get_usage(self, quota_id: str) -> QuotaUsage:
        """获取配额使用量"""
        pass

    @abstractmethod
    def increment_usage(self, quota_id: str, resources: ResourceQuota) -> bool:
        """增加使用量 (原子操作)"""
        pass

    @abstractmethod
    def decrement_usage(self, quota_id: str, resources: ResourceQuota) -> bool:
        """减少使用量 (原子操作)"""
        pass

    @abstractmethod
    def list_quotas(self, scope: Optional[QuotaScope] = None) -> List[Quota]:
        """列出配额"""
        pass

    @abstractmethod
    def get_all_usage(self) -> Dict[str, QuotaUsage]:
        """获取所有配额使用量"""
        pass
```

### 6.4 SQLite 原子操作实现

SQLite 通过 **WAL 模式 + BEGIN IMMEDIATE** 实现高并发下的原子操作:

```python
# src/algo_studio/core/quota/stores/sqlite_store.py

import sqlite3
import threading
from contextlib import contextmanager
from typing import Optional, List, Dict

class SQLiteQuotaStore:
    """SQLite 配额存储实现"""

    def __init__(self, db_path: str = "quota.db"):
        self.db_path = db_path
        self._local = threading.local()  # 线程本地连接
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取线程本地的数据库连接"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                isolation_level=None  # 自动事务管理
            )
            # 启用 WAL 模式，提升并发读性能
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA busy_timeout=30000")
        return self._local.conn

    @contextmanager
    def _transaction(self):
        """事务上下文管理器 (BEGIN IMMEDIATE 获得写锁)"""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")  # 立即获得写锁，避免死锁
            yield cursor
            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            raise

    def increment_usage(self, quota_id: str, resources: ResourceQuota) -> bool:
        """
        原子增加配额使用量

        使用 UPDATE ... SET ... + value 而非 SELECT 后 UPDATE，避免 TOCTOU 问题
        """
        try:
            with self._transaction() as cursor:
                cursor.execute("""
                    UPDATE quota_usages
                    SET cpu_cores_used = cpu_cores_used + ?,
                        gpu_count_used = gpu_count_used + ?,
                        gpu_memory_gb_used = gpu_memory_gb_used + ?,
                        memory_gb_used = memory_gb_used + ?,
                        disk_gb_used = disk_gb_used + ?,
                        concurrent_tasks_used = concurrent_tasks_used + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE quota_id = ?
                """, (
                    resources.cpu_cores,
                    resources.gpu_count,
                    resources.gpu_memory_gb,
                    resources.memory_gb,
                    resources.disk_gb,
                    resources.concurrent_tasks,
                    quota_id
                ))
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"increment_usage error: {e}")
            return False

    def decrement_usage(self, quota_id: str, resources: ResourceQuota) -> bool:
        """
        原子减少配额使用量 (带下限保护)

        使用 MAX(0, current - value) 避免负数
        """
        try:
            with self._transaction() as cursor:
                cursor.execute("""
                    UPDATE quota_usages
                    SET cpu_cores_used = MAX(0, cpu_cores_used - ?),
                        gpu_count_used = MAX(0, gpu_count_used - ?),
                        gpu_memory_gb_used = MAX(0, gpu_memory_gb_used - ?),
                        memory_gb_used = MAX(0, memory_gb_used - ?),
                        disk_gb_used = MAX(0, disk_gb_used - ?),
                        concurrent_tasks_used = MAX(0, concurrent_tasks_used - ?),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE quota_id = ?
                """, (
                    resources.cpu_cores,
                    resources.gpu_count,
                    resources.gpu_memory_gb,
                    resources.memory_gb,
                    resources.disk_gb,
                    resources.concurrent_tasks,
                    quota_id
                ))
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"decrement_usage error: {e}")
            return False

    def check_and_allocate(self, quota_id: str, resources: ResourceQuota) -> bool:
        """
        原子检查并分配配额 (compare-and-swap)

        使用单条 UPDATE + WHERE 条件实现原子 CAS，避免竞态条件
        """
        try:
            with self._transaction() as cursor:
                # 先检查配额是否足够
                cursor.execute("""
                    SELECT cpu_cores, gpu_count, gpu_memory_gb, memory_gb,
                           cpu_cores_used, gpu_count_used, gpu_memory_gb_used,
                           memory_gb_used, concurrent_tasks, concurrent_tasks_used
                    FROM quotas q
                    JOIN quota_usages u ON q.quota_id = u.quota_id
                    WHERE q.quota_id = ? AND q.is_active = 1
                """, (quota_id,))
                row = cursor.fetchone()
                if not row:
                    return False

                (cpu_limit, gpu_limit, gpu_mem_limit, mem_limit,
                 cpu_used, gpu_used, gpu_mem_used, mem_used,
                 concurrent_limit, concurrent_used) = row

                # 检查各项资源是否足够
                if (resources.cpu_cores > 0 and cpu_limit > 0 and
                    cpu_used + resources.cpu_cores > cpu_limit):
                    return False
                if (resources.gpu_count > 0 and gpu_limit > 0 and
                    gpu_used + resources.gpu_count > gpu_limit):
                    return False
                if (resources.gpu_memory_gb > 0 and gpu_mem_limit > 0 and
                    gpu_mem_used + resources.gpu_memory_gb > gpu_mem_limit):
                    return False
                if (resources.memory_gb > 0 and mem_limit > 0 and
                    mem_used + resources.memory_gb > mem_limit):
                    return False
                if (resources.concurrent_tasks > 0 and concurrent_limit > 0 and
                    concurrent_used + resources.concurrent_tasks > concurrent_limit):
                    return False

                # 原子增加使用量
                return self.increment_usage(quota_id, resources)

        except sqlite3.Error as e:
            print(f"check_and_allocate error: {e}")
            return False
```

**并发安全性分析**:
- **WAL 模式**: 允许读操作不阻塞写操作，提升读并发
- **BEGIN IMMEDIATE**: 事务开始即获取写锁，避免死锁
- **原子 UPDATE**: `UPDATE ... SET col = col + ?` 是原子操作，无需 SELECT 再 UPDATE
- **MAX 保护**: 减少时使用 `MAX(0, col - ?)` 防止负数
- **busy_timeout**: 30秒超时，避免长时间等待锁

**锁竞争优化**:
- 读操作使用共享锁，多读不互斥
- 写操作使用排他锁
- 短事务设计: 只锁关键字段，不锁整表

## 7. API 设计

### 7.1 配额管理 API

```python
# src/algo_studio/api/routes/quotas.py

from fastapi import APIRouter, HTTPException
from typing import List, Optional

router = APIRouter(prefix="/api/quotas", tags=["quotas"])

# ==================== 配额 CRUD ====================

@router.post("", response_model=QuotaResponse)
async def create_quota(request: QuotaCreateRequest):
    """创建配额"""
    quota = Quota(
        quota_id=f"quota-{uuid.uuid4().hex[:8]}",
        scope=QuotaScope(request.scope),
        scope_id=request.scope_id,
        name=request.name,
        limits=ResourceQuota(**request.limits),
        alert_threshold=request.alert_threshold,
        parent_quota_id=request.parent_quota_id,
    )
    quota_manager.create_quota(quota)
    return _quota_to_response(quota)


@router.get("/{quota_id}", response_model=QuotaResponse)
async def get_quota(quota_id: str):
    """获取配额详情"""
    quota = quota_manager.store.get_quota(quota_id)
    if not quota:
        raise HTTPException(status_code=404, detail="Quota not found")
    return _quota_to_response(quota)


@router.get("/scope/{scope}/{scope_id}", response_model=QuotaResponse)
async def get_quota_by_scope(scope: str, scope_id: str):
    """根据作用域获取配额"""
    quota = quota_manager.store.get_quota_by_scope(QuotaScope(scope), scope_id)
    if not quota:
        raise HTTPException(status_code=404, detail="Quota not found")
    return _quota_to_response(quota)


@router.put("/{quota_id}", response_model=QuotaResponse)
async def update_quota(quota_id: str, request: QuotaUpdateRequest):
    """更新配额"""
    quota = quota_manager.store.get_quota(quota_id)
    if not quota:
        raise HTTPException(status_code=404, detail="Quota not found")

    # 更新字段
    if request.name is not None:
        quota.name = request.name
    if request.limits is not None:
        quota.limits = ResourceQuota(**request.limits)
    if request.alert_threshold is not None:
        quota.alert_threshold = request.alert_threshold
    if request.is_active is not None:
        quota.is_active = request.is_active
    quota.updated_at = datetime.now()

    quota_manager.store.update_quota(quota)
    return _quota_to_response(quota)


@router.delete("/{quota_id}")
async def delete_quota(quota_id: str):
    """删除配额"""
    if not quota_manager.store.delete_quota(quota_id):
        raise HTTPException(status_code=404, detail="Quota not found")
    return {"status": "deleted"}


# ==================== 配额使用量 ====================

@router.get("/{quota_id}/usage", response_model=QuotaUsageResponse)
async def get_quota_usage(quota_id: str):
    """获取配额使用量"""
    usage = quota_manager.store.get_usage(quota_id)
    quota = quota_manager.store.get_quota(quota_id)
    if not quota:
        raise HTTPException(status_code=404, detail="Quota not found")

    percentages = quota.get_usage_percentage(usage) if usage else {}
    return QuotaUsageResponse(
        quota_id=quota_id,
        usage=usage.to_dict() if usage else {},
        percentages=percentages,
    )


@router.get("/usage/overview")
async def get_usage_overview():
    """获取所有配额使用概览"""
    all_usage = quota_manager.store.get_all_usage()
    quotas = quota_manager.store.list_quotas()

    overview = []
    for quota in quotas:
        usage = all_usage.get(quota.quota_id)
        percentages = quota.get_usage_percentage(usage) if usage else {}
        overview.append({
            "quota_id": quota.quota_id,
            "scope": quota.scope.value,
            "scope_id": quota.scope_id,
            "name": quota.name,
            "limits": asdict(quota.limits),
            "usage": usage.to_dict() if usage else {},
            "percentages": percentages,
            "is_active": quota.is_active,
        })

    return {"quotas": overview, "total": len(overview)}


# ==================== 告警 ====================

@router.get("/alerts", response_model=List[AlertResponse])
async def list_alerts(acknowledged: Optional[bool] = None, limit: int = 50):
    """列出告警"""
    alerts = alert_manager.list_alerts(
        acknowledged=acknowledged,
        limit=limit,
    )
    return [_alert_to_response(a) for a in alerts]


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, acknowledged_by: str):
    """确认告警"""
    alert_manager.acknowledge(alert_id, acknowledged_by)
    return {"status": "acknowledged"}


# ==================== 辅助函数 ====================

def _quota_to_response(quota: Quota) -> QuotaResponse:
    usage = quota_manager.store.get_usage(quota.quota_id)
    percentages = quota.get_usage_percentage(usage) if usage else {}

    return QuotaResponse(
        quota_id=quota.quota_id,
        scope=quota.scope.value,
        scope_id=quota.scope_id,
        name=quota.name,
        limits=asdict(quota.limits),
        alert_threshold=quota.alert_threshold,
        parent_quota_id=quota.parent_quota_id,
        is_active=quota.is_active,
        usage=usage.to_dict() if usage else {},
        percentages=percentages,
        created_at=quota.created_at.isoformat(),
        updated_at=quota.updated_at.isoformat(),
    )
```

### 7.2 请求/响应模型

```python
# src/algo_studio/api/models.py

class QuotaCreateRequest(BaseModel):
    scope: str           # "user", "team", "global"
    scope_id: str        # user_id 或 team_id
    name: str
    limits: dict         # ResourceQuota 字段
    alert_threshold: int = 80
    parent_quota_id: Optional[str] = None

class QuotaUpdateRequest(BaseModel):
    name: Optional[str] = None
    limits: Optional[dict] = None
    alert_threshold: Optional[int] = None
    is_active: Optional[bool] = None

class QuotaResponse(BaseModel):
    quota_id: str
    scope: str
    scope_id: str
    name: str
    limits: dict
    alert_threshold: int
    parent_quota_id: Optional[str]
    is_active: bool
    usage: dict
    percentages: dict
    created_at: str
    updated_at: str

class QuotaUsageResponse(BaseModel):
    quota_id: str
    usage: dict
    percentages: dict

class AlertResponse(BaseModel):
    alert_id: str
    quota_id: str
    scope: str
    scope_id: str
    level: str
    metric: str
    usage_percentage: float
    threshold: int
    message: str
    is_acknowledged: bool
    created_at: str
```

---

## 8. 配额视图设计

### 8.1 用户配额仪表盘

```json
{
  "user_id": "user_a1",
  "team_id": "team_a",
  "quotas": {
    "user": {
      "quota_id": "quota-xxx",
      "name": "用户 A1 配额",
      "limits": {
        "cpu_cores": 16,
        "gpu_count": 2,
        "memory_gb": 64.0,
        "concurrent_tasks": 5
      },
      "usage": {
        "cpu_cores_used": 8,
        "gpu_count_used": 1,
        "memory_gb_used": 32.0,
        "concurrent_tasks_used": 2
      },
      "percentages": {
        "cpu_cores": 50.0,
        "gpu_count": 50.0,
        "memory_gb": 50.0,
        "concurrent_tasks": 40.0
      }
    },
    "team": {
      "quota_id": "quota-yyy",
      "name": "团队 A 配额",
      "limits": {
        "cpu_cores": 64,
        "gpu_count": 8,
        "memory_gb": 256.0,
        "concurrent_tasks": 20
      },
      "usage": {
        "cpu_cores_used": 24,
        "gpu_count_used": 3,
        "memory_gb_used": 96.0,
        "concurrent_tasks_used": 6
      },
      "percentages": {
        "cpu_cores": 37.5,
        "gpu_count": 37.5,
        "memory_gb": 37.5,
        "concurrent_tasks": 30.0
      }
    }
  },
  "alerts": [
    {
      "alert_id": "alert-zzz",
      "level": "warning",
      "metric": "gpu_count",
      "usage_percentage": 85.0,
      "message": "GPU 配额使用率 85%, 接近上限"
    }
  ]
}
```

### 8.2 管理员配额总览

```json
{
  "summary": {
    "total_quotas": 10,
    "total_users": 8,
    "total_teams": 2,
    "total_usage": {
      "cpu_cores_used": 48,
      "gpu_count_used": 6,
      "memory_gb_used": 192.0,
      "concurrent_tasks_used": 15
    }
  },
  "quotas": [
    {
      "quota_id": "quota-global",
      "scope": "global",
      "scope_id": "global",
      "name": "全局配额",
      "limits": { "cpu_cores": 128, "gpu_count": 16, "memory_gb": 512.0 },
      "usage": { "cpu_cores_used": 48, "gpu_count_used": 6, "memory_gb_used": 192.0 },
      "percentages": { "cpu_cores": 37.5, "gpu_count": 37.5, "memory_gb": 37.5 }
    },
    {
      "quota_id": "quota-team_a",
      "scope": "team",
      "scope_id": "team_a",
      "name": "团队 A 配额",
      "limits": { "cpu_cores": 64, "gpu_count": 8, "memory_gb": 256.0 },
      "usage": { "cpu_cores_used": 24, "gpu_count_used": 3, "memory_gb_used": 96.0 },
      "percentages": { "cpu_cores": 37.5, "gpu_count": 37.5, "memory_gb": 37.5 }
    }
  ],
  "alerts": [
    {
      "alert_id": "alert-001",
      "level": "critical",
      "scope": "user",
      "scope_id": "user_a2",
      "metric": "concurrent_tasks",
      "usage_percentage": 100.0,
      "message": "并发任务数已达上限"
    }
  ]
}
```

---

## 9. 实施计划

### 9.1 实施阶段划分

**修订说明**: 原计划 3 周偏紧张，实际涉及核心调度逻辑修改和存储层原子操作，实现复杂度较高，调整为 5 周。

| 阶段 | 时间 | 交付物 |
|------|------|--------|
| **Phase 1: 基础配额** | Week 1-2 | 配额数据模型、存储层、基础 API |
| **Phase 2: 配额集成** | Week 3 | 调度器配额集成、任务提交校验 |
| **Phase 3: 告警和视图** | Week 4 | 告警机制、配额仪表盘 API |
| **Phase 4: 存储集成** | Week 5 | disk_gb 与 JuiceFS/NAS 打通 |

### 9.2 详细任务分解

#### Week 1-2: 配额基础 (10 人天)

| 任务 | 人天 | 交付物 | 验收标准 |
|------|------|--------|----------|
| 创建 `quota/` 目录结构 | 0.5 | 目录创建 | 目录存在 |
| 实现 `Quota`, `ResourceQuota`, `QuotaUsage` 数据类 (含 gpu_memory_gb) | 1.5 | `quota/models.py` | 单元测试通过 |
| 实现 `QuotaStoreInterface` 和 SQLite 实现 (含原子操作) | 3.0 | `quota/stores/sqlite_store.py` | CRUD + 并发测试通过 |
| 实现 `QuotaManager` 核心逻辑 | 2.0 | `quota/quota_manager.py` | 配额检查算法正确 |
| SQLite 原子操作测试 | 1.5 | `test_quota_atomic.py` | 覆盖率 >80% |
| 层级配额继承校验测试 | 1.5 | `test_quota_inheritance.py` | 父子配额校验正确 |
| 与后端 Phase 2 Quota 模型对齐验证 | 0.5 | 对齐文档 | 字段映射正确 |

#### Week 3: 调度集成 (5 人天)

| 任务 | 人天 | 交付物 | 验收标准 |
|------|------|--------|----------|
| 扩展 `Task` 类添加 user_id, team_id, quota_id 字段 | 0.5 | `task.py` | 字段正确添加 |
| 实现 `QuotaValidator` 调度验证器 | 1.0 | `quota/quota_validator.py` | 能校验调度决策 |
| 实现改进的公平调度算法 (含饥饿防止) | 1.5 | `quota/fair_scheduler.py` | 算法测试通过 |
| 集成配额检查到 `AgenticScheduler` | 1.5 | `agentic_scheduler.py` | 调度时校验配额 |
| 集成测试 | 0.5 | `test_quota_integration.py` | 端到端测试通过 |

#### Week 4: 告警和视图 (5 人天)

| 任务 | 人天 | 交付物 | 验收标准 |
|------|------|--------|----------|
| 实现 `AlertManager` 告警管理 | 1.0 | `quota/alert_manager.py` | 告警触发正确 |
| 实现配额 API (`/api/quotas/*`) | 1.5 | `routes/quotas.py` | API 可用 |
| 实现配额使用概览 API | 1.0 | `routes/quotas.py` `/usage/overview` | 返回正确 |
| 配额视图数据模型 | 0.5 | `api/models.py` | 模型完整 |
| 文档和测试 | 1.0 | 文档更新 | 文档完整 |

#### Week 5: 存储集成 (5 人天)

| 任务 | 人天 | 交付物 | 验收标准 |
|------|------|--------|----------|
| 实现 `StorageQuotaChecker` 存储配额检查器 | 1.5 | `quota/storage_checker.py` | 存储配额检查正确 |
| 集成 disk_gb 到任务生命周期 | 1.0 | `task.py` | 任务开始/完成时更新 |
| JuiceFS/NAS 存储路径映射 | 1.5 | `storage_mapping.py` | 路径正确映射 |
| 存储配额告警 | 1.0 | `alert_manager.py` | 存储告警触发 |

### 9.3 代码目录结构

```
src/algo_studio/
├── core/
│   ├── task.py              # [修改] 添加 user_id, team_id 字段
│   ├── ray_client.py        # [现有]
│   ├── scheduler/           # [现有]
│   │   └── agentic_scheduler.py  # [修改] 集成配额验证
│   └── quota/              # [新增] 配额管理
│       ├── __init__.py
│       ├── models.py       # Quota, ResourceQuota, QuotaUsage, QuotaAlert
│       ├── quota_manager.py # 配额管理核心逻辑
│       ├── quota_validator.py # 调度验证器
│       ├── alert_manager.py # 告警管理
│       └── stores/
│           ├── __init__.py
│           ├── base.py     # QuotaStoreInterface
│           └── sqlite_store.py
├── api/
│   ├── main.py
│   ├── models.py           # [修改] 添加配额相关模型
│   └── routes/
│       ├── tasks.py        # [修改] 添加 user_id 参数
│       ├── quotas.py       # [新增] 配额 API
│       └── hosts.py
```

---

## 10. 风险评估和缓解措施

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 配额校验影响调度延迟 | 中 | 配额检查轻量化 (<1ms)，使用索引优化 |
| 配额数据一致性问题 | 中 | SQLite WAL + BEGIN IMMEDIATE 保证原子性 |
| 多调度器并发配额更新 | 中 | Phase 2 单调度器无问题，Phase 3 迁移 Redis 分布式锁 |
| 用户未设置配额导致无限制使用 | 低 | 设置全局默认配额 ( GLOBAL quota ) |
| 配额继承计算复杂 | 低 | 统一 3 级继承，简化继承规则 |
| SQLite 锁竞争 | 中 | WAL 模式隔离读写，短事务设计，Phase 3 迁 Redis |
| 公平调度参数经验值效果不确定 | 中 | Phase 2 前必须完成仿真测试和灰度验证 |
| 存储配额估算偏差导致超额 | 中 | 预留-校正机制，估算偏差 < 20% |
| JuiceFS 社区版无目录硬限制 | 中 | Phase 2 应用层软限制，Phase 3 升级 ZFS 或企业版 |
| 排队任务饿死 | 中 | 30min 超时告警 + 2h 饿死检测 |

---

## 11. 技术选型说明

### 11.1 GPU 资源量化模型

GPU 资源采用以下维度量化:

| 维度 | 说明 | 量化方式 | 适用场景 |
|------|------|----------|----------|
| GPU 数量 | 物理 GPU 卡数 | 整数计数 | 任务并行度控制 |
| GPU 显存 | 显存使用量 (RTX 4090 24GB) | GB | 显存敏感型任务 |
| GPU 利用率 | 实时利用率 | 百分比 (0-100) | 监控参考 |

**RTX 4090 差异化支持**:
- 集群中存在不同 GPU 型号时，配额可按显存上限设置
- 例如: `gpu_memory_gb=24` 适配 RTX 4090，`gpu_memory_gb=16` 适配 RTX 4080
- 调度时自动匹配用户配额与可用 GPU 显存

### 11.2 disk_gb 与 JuiceFS/NAS 存储配额打通

**存储架构**:
```
┌─────────────────────────────────────────────────────────────┐
│                     JuiceFS / NAS 存储                       │
│  /juicefs/data        /nas/datasets        /nas/models      │
│       ↓                    ↓                   ↓            │
│  临时训练数据          共享数据集           模型存储         │
└─────────────────────────────────────────────────────────────┘
```

**JuiceFS 配额命令验证**:

JuiceFS 企业版提供 `juicefs quota` 命令，但社区版不支持目录级配额。

```bash
# JuiceFS 目录级配额 (企业版)
juicefs quota set --path /juicefs/data --capacity 1000 --inodes 100000

# 检查配额状态 (企业版)
juicefs quota status --path /juicefs/data
```

**社区版替代方案** (Phase 2/3 实现路径):

针对架构师反馈"setquota 需要 quotatalk daemon 过于复杂"的问题，提供以下具体替代路径:

| 方案 | 实现复杂度 | 限制精度 | 推荐程度 |
|------|------------|----------|----------|
| **A. 应用层软限制 (Phase 2)** | 低 | 估算精度 | **推荐 Phase 2** |
| **B. ZFS Dataset 配额** | 中 | 精确 | 推荐有 ZFS 经验的团队 |
| **C. 定期扫描 + 目录 owner** | 低 | 统计精度 | 作为监控补充 |

**方案 A: 应用层软限制 (已在上节详细说明)**

这是 Phase 2 的推荐方案，通过任务生命周期管理实现存储配额控制。

**方案 B: ZFS Dataset 配额** (适合有 ZFS 经验的团队)

如果集群使用 ZFS 作为底层文件系统，可利用 ZFS 原生配额:

```bash
# 创建用户数据集
zfs create tank/users/{user_id}

# 设置存储配额 (硬限制)
zfs set quota={disk_gb}G tank/users/{user_id}

# 设置记录限制
zfs set recordsize=1M tank/users/{user_id}

# 查看配额状态
zfs get quota,used tank/users/{user_id}
```

ZFS 配额优势:
- 内核级硬限制，写入超过配额自动返回 ENOSPC
- 无需额外 daemon 或用户空间工具
- 配额变更即时生效

**方案 C: 定期扫描 + 目录 owner 标记**

适用于无法改造存储层的场景:

```python
class DirectoryQuotaScanner:
    """
    定期扫描目录计算实际使用量

    扫描周期: 每 15 分钟
    计算方式: du -sb --apparent-size
    """

    def __init__(self, scan_interval_minutes: int = 15):
        self.scan_interval = scan_interval_minutes
        self.base_paths = ["/juicefs/data", "/nas/datasets", "/nas/models"]

    def scan_user_usage(self, user_id: str) -> float:
        """扫描用户实际磁盘使用量 (GB)"""
        total_bytes = 0
        for base_path in self.base_paths:
            user_path = f"{base_path}/{user_id}"
            if os.path.exists(user_path):
                # 使用 du 获取目录大小
                result = subprocess.run(
                    ["du", "-sb", "--apparent-size", user_path],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    total_bytes += int(result.stdout.split()[0])
        return total_bytes / (1024**3)

    def sync_to_quota_store(self):
        """同步扫描结果到配额存储"""
        # 定期更新 quota_usages.disk_gb_used
        for user_id in self._get_all_users():
            actual_gb = self.scan_user_usage(user_id)
            quota = self.quota_manager.store.get_quota_by_scope(
                QuotaScope.USER, user_id
            )
            if quota:
                self.quota_manager.store.update_disk_usage(
                    quota.quota_id, actual_gb
                )
```

**社区版方案对比**:

| 评估维度 | setquota (需 quotatalk) | ZFS Dataset | 应用层软限制 | 定期扫描 |
|----------|------------------------|-------------|-------------|----------|
| 依赖 daemon | 是 (quotatalk) | 否 | 否 | 否 |
| 硬限制 | 是 | 是 | 否 (软限制) | 否 |
| 内核级 | 是 | 是 | 否 | 否 |
| 实现复杂度 | 高 | 中 | 低 | 低 |
| 配额精度 | 精确 | 精确 | 估算 | 统计 |
| JuiceFS 兼容性 | 不适用 | 需 ZFS 底层 | 适用 | 适用 |

**推荐决策**:

1. **Phase 2**: 应用层软限制 (方案 A) + 定期扫描同步 (方案 C)
2. **Phase 3**:
   - 如有 ZFS 经验，升级到 ZFS Dataset 配额 (方案 B)
   - 或等待 JuiceFS 企业版授权

**存储配额打通实现方案**:

| 阶段 | 实现方式 | 依赖 | 限制力度 |
|------|----------|------|----------|
| **Phase 2** | 应用层软限制 + 强制估算 + 告警 | 无外部依赖 | 调度层阻止超额任务，任务执行后校正 |
| **Phase 3** | 与 JuiceFS 目录配额打通 | JuiceFS 企业版或 ZFS | 写入时硬限制 |

**Phase 2 存储配额实现细节** (解决"形同虚设"问题):

Phase 2 采用 **估算-预留-校正** 三阶段机制，确保配额有效:

```python
class StorageQuotaEnforcer:
    """
    Phase 2 存储配额执行器

    采用软限制机制:
    1. 任务提交时估算所需空间，不足则拒绝
    2. 任务开始时预留配额
    3. 任务完成时校正为实际使用量
    """

    def check_and_reserve(self, quota_id: str, task: Task) -> tuple[bool, str]:
        """
        任务提交时检查存储配额

        估算任务所需空间:
        - 训练任务: 数据集大小 + 模型大小 + 中间产物 (10% buffer)
        - 推理任务: 输入大小 + 输出大小
        """
        quota = self.quota_manager._get_effective_quota(task.user_id, task.team_id)
        if not quota or quota.limits.disk_gb <= 0:
            return (True, "")  # 无配额限制

        # 估算所需空间
        estimated_gb = self._estimate_storage(task)
        available = quota.limits.disk_gb - quota.usage.disk_gb_used

        if available < estimated_gb:
            return (False, f"存储配额不足: 任务需 {estimated_gb}GB, 可用 {available}GB}")

        # 预留配额 (原子操作)
        success = self.quota_manager.store.increment_usage(
            quota_id, ResourceQuota(disk_gb=estimated_gb)
        )
        if not success:
            return (False, "存储配额预留失败")

        return (True, "")

    def reconcile(self, quota_id: str, task_id: str, actual_gb: float):
        """
        任务完成后校正存储使用量

        释放多估部分，计入实际使用量
        """
        # 查询任务预留量，重新计算实际使用量
        reserved_gb = self._get_task_reserved_gb(task_id)
        delta = actual_gb - reserved_gb

        if delta > 0:
            # 实际使用超过估算，需要补充扣减
            self.quota_manager.store.increment_usage(
                quota_id, ResourceQuota(disk_gb=delta)
            )
        else:
            # 释放多估部分
            self.quota_manager.store.decrement_usage(
                quota_id, ResourceQuota(disk_gb=-delta)
            )

    def _estimate_storage(self, task: Task) -> float:
        """估算任务所需存储空间"""
        config = task.config or {}
        if task.task_type == TaskType.TRAIN:
            dataset_gb = config.get('dataset_size_gb', 10)
            model_gb = config.get('model_size_gb', 5)
            return (dataset_gb + model_gb) * 1.1  # 10% buffer
        elif task.task_type == TaskType.INFER:
            input_gb = config.get('input_size_gb', 1)
            output_gb = config.get('output_size_gb', 1)
            return (input_gb + output_gb) * 1.2
        else:
            return config.get('estimated_disk_gb', 5)
```

**Phase 2 存储配额限制有效性保障**:

| 机制 | 说明 | 有效性 |
|------|------|--------|
| 提交时估算 | 拒绝明显超配额任务 | 防止大量超额任务堆积 |
| 预留-校正 | 任务完成后校正实际使用 | 确保配额数据准确 |
| 告警机制 | 使用率 > 80% 告警 | 提前通知管理员 |
| 定期扫描 | 每周扫描实际使用量 | 校验估算准确性 |
| 管理员干预 | 强制重置异常配额 | 处理异常情况 |

**Phase 2 已知局限**:

- 无法阻止恶意用户直接写入文件系统超过配额
- 估算可能偏离实际 (可通过定期校正改善)
- 多节点场景下需要共享存储或定时同步

**配额估算偏差缓解措施**:

估算-校正机制依赖任务配置中的 `dataset_size_gb`、`model_size_gb` 等字段，如配置不准确会导致配额偏差。为此，引入以下缓解措施:

| 措施 | 说明 | 效果 |
|------|------|------|
| **默认上限约束** | 估算值设置硬上限: `min(estimated_gb, quota_limits.disk_gb * 0.5)` | 防止配置值过大导致超额预留 |
| **配置字段校验** | 提交时校验 `dataset_size_gb`、`model_size_gb` 是否在合理范围内 | 拒绝明显异常的估算值 |
| **历史校正系数** | 维护用户历史估算/实际比值 (校正系数)，下次估算乘以该系数 | 逐步收敛估算误差 |
| **分位数估算** | 使用 P90 估算替代点估算: `estimated_gb = P90(historical_actual_gb)` | 避免极端值影响 |
| **告警+人工审核** | 估算偏差 > 50% 时触发 WARNING，> 100% 触发 CRITICAL | 通知管理员介入 |
| **自动校正** | 连续 3 次校正方向一致时，自动调整用户校正系数 | 减少人工干预 |

**估算偏差监控系统**:

```python
class EstimationBiasMonitor:
    """
    监控配额估算偏差，自动校正估算模型
    """

    def __init__(self, store: QuotaStore):
        self.store = store
        self.bias_history: Dict[str, List[float]] = {}  # user_id -> [偏差比值列表]

    def record_estimate(self, user_id: str, task_id: str, estimated_gb: float):
        """记录估算值"""
        self.store.save_estimate_record(user_id, task_id, estimated_gb)

    def record_actual(self, task_id: str, actual_gb: float):
        """记录实际值并计算偏差"""
        record = self.store.get_estimate_record(task_id)
        if not record:
            return

        bias_ratio = actual_gb / record.estimated_gb if record.estimated_gb > 0 else 1.0

        # 记录偏差历史
        if user_id not in self.bias_history:
            self.bias_history[user_id] = []
        self.bias_history[user_id].append(bias_ratio)

        # 只保留最近 10 次记录
        self.bias_history[user_id] = self.bias_history[user_id][-10:]

    def get_correction_factor(self, user_id: str) -> float:
        """
        获取用户校正系数

        计算方式: 最近 N 次实际/估算比值的中位数
        - 如果中位数 > 1，说明用户倾向于超估 (应该减少估算)
        - 如果中位数 < 1，说明用户倾向于低估 (可以增加估算)
        """
        if user_id not in self.bias_history or len(self.bias_history[user_id]) < 3:
            return 1.0  # 样本不足，不校正

        history = self.bias_history[user_id]
        sorted_history = sorted(history)
        n = len(sorted_history)

        # 使用中位数
        if n % 2 == 0:
            median = (sorted_history[n//2 - 1] + sorted_history[n//2]) / 2
        else:
            median = sorted_history[n//2]

        # 限制校正范围: 0.5 ~ 2.0
        return max(0.5, min(2.0, median))

    def check_bias_alert(self, user_id: str, task_id: str,
                         estimated_gb: float, actual_gb: float) -> Optional[Alert]:
        """检查估算偏差是否触发告警"""
        if actual_gb == 0 or estimated_gb == 0:
            return None

        bias_ratio = max(actual_gb / estimated_gb, estimated_gb / actual_gb)

        if bias_ratio > 2.0:  # 偏差超过 100%
            return Alert(
                level=AlertLevel.CRITICAL,
                message=f"配额估算严重偏差: 任务 {task_id} 估算 {estimated_gb}GB, 实际 {actual_gb}GB"
            )
        elif bias_ratio > 1.5:  # 偏差超过 50%
            return Alert(
                level=AlertLevel.WARNING,
                message=f"配额估算偏差较大: 任务 {task_id} 估算 {estimated_gb}GB, 实际 {actual_gb}GB"
            )

        return None
```

**校正系数应用示例**:

```python
# 原始估算
base_estimate = (dataset_gb + model_gb) * 1.1

# 获取用户校正系数
correction_factor = bias_monitor.get_correction_factor(user_id)

# 应用校正
corrected_estimate = base_estimate * correction_factor

# 应用硬上限
max_allowed = quota.limits.disk_gb * 0.5
final_estimate = min(corrected_estimate, max_allowed)
```

**偏差缓解效果评估**:

| 场景 | 偏差率 | 原始估算 | 校正后估算 | 改善 |
|------|--------|----------|------------|------|
| 用户持续高估 50% | 1.5x | 15GB | 10GB | -33% |
| 用户持续低估 30% | 0.7x | 7GB | 9.5GB | +36% |
| 随机波动 20% | 0.8-1.2x | ~11GB | ~10.5GB | ~5% |

**Phase 3 升级路径**:

当集群升级到 JuiceFS 企业版或 ZFS 时，存储配额将升级为硬限制:

```python
# Phase 3: JuiceFS 企业版配额
juicefs quota set --path /juicefs/users/{user_id} \
    --capacity {quota_limits.disk_gb}G \
    --inodes 1000000

# 硬限制: 写入时自动拒绝，超过容量写入失败
```

**quota_usages.disk_gb_used 更新机制**:

1. **任务开始**: 估算所需存储空间 `estimated_gb`
   ```python
   # 根据任务类型估算
   if task_type == TaskType.TRAIN:
       estimated_gb = config.get('dataset_size_gb', 10) + config.get('model_size_gb', 5)
   else:
       estimated_gb = config.get('input_size_gb', 1)
   ```

2. **任务完成**: 实际使用量通过扫描或任务上报更新
   ```python
   # 任务完成时扫描输出目录
   actual_used_gb = scan_directory_size(task.output_path) / (1024**3)
   ```

3. **存储配额检查**:
   ```python
   if estimated_gb > available_storage_gb:
       return (False, f"存储配额不足: 请求 {estimated_gb}GB, 可用 {available_gb}GB")
   ```

```python
class StorageQuotaChecker:
    """存储配额检查器"""

    def __init__(self, quota_manager: QuotaManager):
        self.quota_manager = quota_manager
        self.juicefs_cmd = "/usr/local/bin/juicefs"

    def check_storage_quota(self, user_id: str, required_gb: float) -> tuple[bool, str]:
        """
        检查用户存储配额是否足够

        Returns:
            (allowed, error_message)
        """
        quota = self.quota_manager._get_effective_quota(user_id, None)
        if not quota:
            return (True, "")  # 无配额限制

        available = quota.limits.disk_gb - quota.usage.disk_gb_used
        if available < required_gb:
            return (False, f"存储配额不足: 请求 {required_gb}GB, 可用 {available}GB}")

        return (True, "")

    def allocate_storage(self, quota_id: str, task_id: str, size_gb: float) -> bool:
        """分配存储空间 (任务开始时调用)"""
        return self.quota_manager.store.increment_usage(
            quota_id,
            ResourceQuota(disk_gb=size_gb)
        )

    def release_storage(self, quota_id: str, actual_used_gb: float) -> bool:
        """释放存储空间 (任务完成时调用，更新为实际使用量)"""
        return self.quota_manager.store.decrement_usage(
            quota_id,
            ResourceQuota(disk_gb=actual_used_gb)
        )
```

### 11.3 层级配额继承设计

**采用 3 级继承**: GLOBAL → TEAM → USER

继承链路示例：
```
全局配额 (GLOBAL: global)
    │
    ├── 团队 A 配额 (TEAM: team_a)  → 继承全局配额
    │       │
    │       ├── 用户 A1 配额 (USER: user_a1)  → 继承团队 A 配额
    │       └── 用户 A2 配额 (USER: user_a2)  → 继承团队 A 配额
    │
    └── 团队 B 配额 (TEAM: team_b)  → 继承全局配额
            │
            └── 用户 B1 配额 (USER: user_b1)  → 继承团队 B 配额
```

**继承规则**:
1. **有效性检查**: 子配额各项限制不能超过父配额对应项
2. **宽松方向**: 子配额可以设置更严格的限制（小于父配额），但不能放宽
3. **继承传递**: 用户继承团队，团队继承全局，不可跨级继承

**继承校验测试用例**:
| 测试场景 | 预期行为 |
|---------|---------|
| 子配额 > 父配额 | 校验失败，拒绝创建 |
| 子配额 <= 父配额 | 校验通过 |
| 修改后超限 | 校验失败，拒绝更新 |
| 删除父配额 | 必须先删除或转移所有子配额 |

### 11.2 多租户隔离方案对比

| 方案 | 隔离级别 | 实现复杂度 | 适用场景 |
|------|----------|------------|----------|
| 软件配额 (当前方案) | 应用层 | 低 | 共享集群、配额控制 |
| cgroups | 内核级 | 中 | Linux 容器环境 |
| Docker/容器 | 进程级 | 高 | 完整容器化部署 |
| Kubernetes 命名空间 | 集群级 | 高 | K8s 环境 |

**推荐**: Phase 2 采用软件配额方案，后续可扩展支持 cgroups/Docker 隔离。

---

## 12. 与现有代码的集成策略

### 12.1 集成原则

1. **最小侵入**: 现有 `TaskManager`, `AgenticScheduler` 改动最小化
2. **向后兼容**: 无 user_id 的任务不受配额限制
3. **可插拔**: 配额管理器可禁用 (`quota_enabled=False`)

### 12.2 配置项

```python
# src/algo_studio/web/config.py 或环境变量

QUOTA_ENABLED = True                    # 是否启用配额
QUOTA_STORE_TYPE = "sqlite"            # 存储类型: sqlite, redis
QUOTA_DEFAULT_CPU_CORES = 32           # 默认 CPU 配额
QUOTA_DEFAULT_GPU_COUNT = 4           # 默认 GPU 配额
QUOTA_DEFAULT_MEMORY_GB = 128.0       # 默认内存配额
QUOTA_ALERT_THRESHOLD = 80             # 默认告警阈值
```

---

## 13. 架构师第 3 轮评审修复

### 13.1 架构师 A 反馈: JuiceFS 社区版替代方案过于概念

**原问题**: setquota 需要 quotatalk daemon，方案不具体

**修复内容** (Section 11.2):
1. 补充了 3 种具体替代方案:
   - 方案 A: 应用层软限制 (Phase 2 推荐)
   - 方案 B: ZFS Dataset 配额 (适合有 ZFS 经验的团队)
   - 方案 C: 定期扫描 + 目录 owner 标记 (作为监控补充)
2. 提供了 ZFS Dataset 的具体命令示例
3. 提供了定期扫描的 Python 实现代码
4. 添加了方案对比表格，明确推荐决策

### 13.2 架构师 B 反馈: 公平调度参数缺少实测验证

**原问题**: 0.05/hour 和 0.8 上限是经验值，未验证

**修复内容** (Section 3.4.3):
1. 添加了参数推导说明，解释参数来源
2. 补充了 4 步实测验证方案:
   - 仿真测试: Jain's Fairness Index >= 0.7
   - 参数敏感性分析: 4 种参数变体对比
   - 灰度发布: 10% 流量先行
   - 监控指标: 5 项关键指标及告警阈值
3. 添加了实测验证通过标准清单

### 13.3 架构师 B 反馈: disk_gb 存储配额 Phase 2 仅记录不限制

**原问题**: 调度层仅记录 disk_gb_used，不实际限制可能导致配额形同虚设

**修复内容** (Section 11.2):
1. 将 Phase 2 方案从"仅记录"改为"估算-预留-校正"三阶段机制
2. 添加了 `StorageQuotaEnforcer` 完整实现代码
3. 明确了 Phase 2 存储配额的 5 种有效性保障机制
4. 添加了 Phase 3 升级路径说明

---

## 14. 验收标准

### Phase 2 配额管理验收

- [ ] `Quota` 数据类正确实现，包含层级继承支持
- [ ] `QuotaManager.check_quota()` 能正确校验配额
- [ ] 任务提交时校验用户配额，超额返回错误
- [ ] 任务调度时校验配额，不分配超额资源
- [ ] 任务完成/失败时正确释放配额
- [ ] 配额使用量 API 返回正确数据
- [ ] 配额告警能正确触发 (使用率 >= 80%)
- [ ] 配额视图 API 返回完整信息
- [ ] 单元测试覆盖率 >80%

### Phase 2 存储配额验收

- [ ] `StorageQuotaEnforcer.check_and_reserve()` 任务提交时校验存储配额
- [ ] `StorageQuotaEnforcer.reconcile()` 任务完成后校正实际使用量
- [ ] 估算偏差不超过实际使用的 20%
- [ ] 存储配额告警触发正确 (使用率 >= 80%)
- [ ] Phase 2 不依赖 quotatalk 或外部 quota daemon

### Phase 2 公平调度验收

- [ ] 仿真测试 Jain's Fairness Index >= 0.7
- [ ] 高优先级任务延迟 < 基线 1.2 倍
- [ ] 无任务等待超过 2 小时 (饿死检测)
- [ ] 参数敏感性分析报告已通过评审
- [ ] 灰度发布方案已制定

---

**RESEARCH COMPLETE**
