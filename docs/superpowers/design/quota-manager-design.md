# QuotaManager 架构设计文档

**任务:** Phase 2 Round 1 - 配额管理器架构设计
**负责人:** @ai-scheduling-engineer
**日期:** 2026-03-26
**版本:** v1.0

---

## 1. QuotaManager 概述

### 1.1 职责

```
QuotaManager 核心职责:
1. 配额校验 (提交时、调度时)
2. 配额占用量跟踪
3. 配额告警触发
4. 层级配额继承计算
```

### 1.2 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      TaskManager                                │
│  create_task() → dispatch_task() → 任务完成回调                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      QuotaManager                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  check_quota() - 配额检查                                │    │
│  │  allocate_resources() - 资源分配                        │    │
│  │  release_resources() - 资源释放                         │    │
│  │  _get_effective_quota() - 获取有效配额 (含继承)          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                             │                                   │
│                             ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  QuotaStore (Interface)                                 │    │
│  │  ├── SQLiteQuotaStore (Phase 2)                        │    │
│  │  └── RedisQuotaStore (Phase 3)                         │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AlertManager                               │
│  check_quota_alerts() - 检查并触发告警                           │
│  send_alert() - 发送告警通知                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 配额检查时机

### 2.1 检查点

| 阶段 | 检查点 | 操作 |
|------|--------|------|
| 任务提交 | `TaskManager.create_task()` | 校验配额是否允许创建新任务 |
| 任务调度 | `AgenticScheduler.schedule()` | 校验配额是否有足够资源 |
| 任务派发 | `TaskManager.dispatch_task()` | 最终资源预留确认 |
| 任务完成 | 任务完成回调 | 释放资源使用量 |

### 2.2 集成流程图

```
任务提交 (create_task)
    │
    ├── [集成点 1] QuotaManager.check_quota() → 校验用户配额
    │
    ▼
AgenticScheduler.schedule()
    │
    ├── [集成点 2] QuotaValidator → 校验调度决策不超配额
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

---

## 3. QuotaManager 核心实现

### 3.1 核心方法

```python
class QuotaManager:
    """配额管理器"""

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
            return (True, None, QuotaUsage(), [])

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
        """分配资源 (原子操作，增加使用量)"""
        return self.store.increment_usage(quota_id, resources)

    def release_resources(self, quota_id: str, resources: ResourceQuota) -> bool:
        """释放资源 (原子操作，减少使用量)"""
        return self.store.decrement_usage(quota_id, resources)
```

### 3.2 任务提交检查

```python
def check_task_submission(self, user_id: str, team_id: Optional[str],
                          task_type: TaskType) -> tuple[bool, Optional[str]]:
    """
    任务提交时的配额检查

    Returns:
        (allowed, error_message)
    """
    requested = ResourceQuota(
        concurrent_tasks=1,
        cpu_cores=1 if task_type != TaskType.TRAIN else 4,
        gpu_count=1 if task_type == TaskType.TRAIN else 0,
        memory_gb=4.0 if task_type == TaskType.TRAIN else 1.0,
    )

    allowed, quota, usage, reasons = self.check_quota(user_id, team_id, requested)
    if not allowed:
        return (False, f"配额不足: {'; '.join(reasons)}")

    return (True, None)
```

### 3.3 任务调度检查

```python
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
```

---

## 4. QuotaValidator 调度验证器

### 4.1 设计目的

集成到 `AgenticScheduler.schedule()` 流程中，验证调度决策是否符合配额约束。

### 4.2 实现

```python
class QuotaValidator:
    """调度过程中的配额验证器"""

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

        user_id = getattr(task, 'user_id', None)
        team_id = getattr(task, 'team_id', None)

        if not user_id:
            return ValidationResult(is_valid=True, errors=[], warnings=[])

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

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
```

---

## 5. 存储层设计

### 5.1 存储接口

```python
class QuotaStoreInterface(ABC):
    """配额存储接口"""

    @abstractmethod
    def get_quota(self, quota_id: str) -> Optional[Quota]: ...

    @abstractmethod
    def get_quota_by_scope(self, scope: QuotaScope, scope_id: str) -> Optional[Quota]: ...

    @abstractmethod
    def create_quota(self, quota: Quota) -> bool: ...

    @abstractmethod
    def update_quota(self, quota: Quota) -> bool: ...

    @abstractmethod
    def delete_quota(self, quota_id: str) -> bool: ...

    @abstractmethod
    def get_usage(self, quota_id: str) -> QuotaUsage: ...

    @abstractmethod
    def increment_usage(self, quota_id: str, resources: ResourceQuota) -> bool: ...

    @abstractmethod
    def decrement_usage(self, quota_id: str, resources: ResourceQuota) -> bool: ...

    @abstractmethod
    def list_quotas(self, scope: Optional[QuotaScope] = None) -> List[Quota]: ...

    @abstractmethod
    def get_all_usage(self) -> Dict[str, QuotaUsage]: ...
```

### 5.2 SQLite 实现要点

```python
class SQLiteQuotaStore:
    """SQLite 配额存储实现"""

    def increment_usage(self, quota_id: str, resources: ResourceQuota) -> bool:
        """原子增加配额使用量"""
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
            """, (resources.cpu_cores, resources.gpu_count, ...))
            return cursor.rowcount > 0

    def decrement_usage(self, quota_id: str, resources: ResourceQuota) -> bool:
        """原子减少配额使用量 (带下限保护)"""
        with self._transaction() as cursor:
            cursor.execute("""
                UPDATE quota_usages
                SET cpu_cores_used = MAX(0, cpu_cores_used - ?),
                    gpu_count_used = MAX(0, gpu_count_used - ?),
                    ...
                WHERE quota_id = ?
            """, (...))
            return cursor.rowcount > 0
```

### 5.3 并发安全机制

| 机制 | 说明 |
|------|------|
| WAL 模式 | 允许读操作不阻塞写操作 |
| BEGIN IMMEDIATE | 事务开始即获取写锁 |
| 原子 UPDATE | `col = col + ?` 是原子操作 |
| MAX 保护 | 减少时使用 `MAX(0, col - ?)` |

---

## 6. 告警机制

### 6.1 告警触发条件

| 条件 | 阈值 | 告警级别 |
|------|------|----------|
| 配额使用率 >= 80% | alert_threshold | WARNING |
| 配额使用率 >= 95% | 固定阈值 | CRITICAL |
| 配额使用率 == 100% | 固定阈值 | BLOCKED |
| 并发任务数达到上限 | concurrent_tasks | WARNING |
| 任务排队超时 | queue_timeout_minutes (默认 30) | WARNING |
| 任务排队超长等待 | queue_max_wait_hours (默认 2) | CRITICAL |

### 6.2 AlertManager 实现

```python
class AlertManager:
    """配额告警管理器"""

    def check_quota_alerts(self, quota: Quota, usage: QuotaUsage,
                          pending_tasks: List[Dict] = None) -> List[QuotaAlert]:
        """检查配额是否触发告警"""
        alerts = []
        usage_percentages = quota.get_usage_percentage(usage)

        for metric, percentage in usage_percentages.items():
            if percentage >= 100:
                alerts.append(self._create_alert(quota, metric, percentage, 100,
                                                 AlertLevel.CRITICAL,
                                                 f"配额已用尽: {metric} 使用率 {percentage:.1f}%"))
            elif percentage >= quota.alert_threshold:
                alerts.append(self._create_alert(quota, metric, percentage,
                                                 quota.alert_threshold, AlertLevel.WARNING,
                                                 f"配额接近上限: {metric} 使用率 {percentage:.1f}%"))

        if pending_tasks:
            for task in pending_tasks:
                wait_minutes = task.get('wait_time_minutes', 0)
                if wait_minutes >= 120:
                    alerts.append(self._create_queue_alert(...))
                elif wait_minutes >= 30:
                    alerts.append(self._create_queue_alert(...))

        return alerts
```

---

## 7. 与现有代码集成

### 7.1 Task 扩展

```python
# src/algo_studio/core/task.py

@dataclass
class Task:
    # ... existing fields ...
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    quota_id: Optional[str] = None
    allocated_resources: Optional[ResourceQuota] = None
```

### 7.2 TaskManager 集成

```python
# src/algo_studio/core/task.py

class TaskManager:
    def __init__(self, quota_manager: QuotaManager = None):
        self._tasks: Dict[str, Task] = {}
        self.quota_manager = quota_manager

    def create_task(self, task_type: TaskType, algorithm_name: str,
                   algorithm_version: str, config: Dict,
                   user_id: Optional[str] = None, team_id: Optional[str] = None) -> Task:
        # 检查配额
        if self.quota_manager:
            allowed, error = self.quota_manager.check_task_submission(
                user_id, team_id, task_type
            )
            if not allowed:
                raise QuotaExceededError(...)

        task = Task.create(task_type, algorithm_name, algorithm_version,
                          config, user_id, team_id)
        self._tasks[task.task_id] = task
        return task
```

---

## 8. 实施任务

### 8.1 Week 1-2 任务

| 任务 | 人天 | 交付物 | 验收标准 |
|------|------|--------|----------|
| 创建 quota/ 目录结构 | 0.5 | 目录创建 | 目录存在 |
| 实现数据模型 | 1.5 | models.py | 单元测试通过 |
| 实现存储层 | 3.0 | sqlite_store.py | CRUD + 并发测试通过 |
| 实现 QuotaManager | 2.0 | quota_manager.py | 配额检查正确 |
| 层级配额测试 | 1.5 | test_quota_inheritance.py | 继承校验正确 |

---

## 9. 验收标准

- [ ] QuotaManager.check_quota() 能正确校验配额
- [ ] 任务提交时校验用户配额，超额返回错误
- [ ] 任务调度时校验配额，不分配超额资源
- [ ] 任务完成/失败时正确释放配额
- [ ] 配额使用量 API 返回正确数据
- [ ] 配额告警能正确触发

---

**文档状态:** 设计完成
**下一步:** 公平调度算法实现
