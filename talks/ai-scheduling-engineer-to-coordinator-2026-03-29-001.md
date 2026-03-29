# AI Scheduling Engineer 回复: Phase 3.5 功能讨论

**日期**: 2026-03-29
**回复**: 功能 3 (节点标签) 和 功能 4 (任务调度逻辑)
**状态**: 初步技术方案

---

## 功能 3: 节点标签设计方案

### 当前状态

目前 `hosts.py` API 返回:
- `is_local`: 布尔值，标识本地节点
- 无 Head/Worker 角色区分
- 无自定义标签功能

### 推荐方案

#### 1. 节点角色标签设计

建议采用 **Ray Node IP 匹配 + 配置** 的方式自动识别 Head:

```python
# hosts.py 扩展
{
    "node_id": "...",
    "ip": "192.168.0.126",
    "role": "head",  # 新增: head | worker
    "is_local": true,
    "labels": ["training", "inference"],  # 新增: 自定义标签列表
    "hostname": "admin02",
    "status": "alive",
    ...
}
```

#### 2. Head vs Worker 自动识别逻辑

```python
def determine_node_role(node_ip: str, ray_head_ip: str = None) -> str:
    """根据 Ray 集群配置自动识别节点角色"""
    if ray_head_ip is None:
        ray_head_ip = os.environ.get("RAY_HEAD_IP", "192.168.0.126")

    # Head 节点 IP 匹配
    if node_ip == ray_head_ip:
        return "head"
    return "worker"
```

#### 3. 自定义标签存储

**方案 A**: 在 hosts API 返回时从配置读取
- 优点: 简单，无数据库改动
- 缺点: 标签需在配置中静态定义

**方案 B**: 新建 `node_labels` 表存储
- 优点: 动态管理标签
- 缺点: 需要新增 API 和数据库迁移

**建议**: Phase 3.5 采用方案 A (静态配置)，后续迭代再考虑方案 B

#### 4. 标签在调度中的作用

```python
# 调度器节点选择逻辑 (scorers/multi_dim_scorer.py)
def score_node(self, node: NodeInfo, task_profile: TaskProfile) -> float:
    # 节点标签匹配加分
    if task_profile.required_labels:
        if not all(label in node.labels for label in task_profile.required_labels):
            return -1000  # 标签不匹配直接排除
```

---

## 功能 4: 任务调度逻辑调整方案

### 当前状态

`dispatch_task()` 逻辑:
1. 获取所有 idle 节点
2. 选择第一个空闲节点 (FIFO)
3. 无用户干预

### 手动分配 vs 自动分配

#### API 扩展建议

**TaskCreateRequest 扩展**:
```python
class TaskCreateRequest:
    # 现有字段...
    target_node: Optional[str] = None  # 指定节点 (IP/hostname)
    scheduling_mode: str = "auto"      # "auto" | "manual"
```

#### 调度器决策流程

```
创建任务
    │
    ├─ scheduling_mode == "manual" AND target_node:
    │       └─► 直接分配到指定节点
    │           (验证节点可用性，如不可用则报错)
    │
    └─ scheduling_mode == "auto" (默认):
            └─► WFQScheduler/FastScheduler 决定
                ├─ 有 preferred_nodes → 优先调度
                └─ 无 → 选择最优节点
```

### 节点选择逻辑

```python
# 新增: node_selector.py
class NodeSelector:
    def select_node(self, task: Task, nodes: list[NodeInfo]) -> Optional[NodeInfo]:
        """
        选择最优节点:
        1. 验证 target_node 是否可用
        2. 检查节点 GPU/资源是否满足
        3. 如不可用，返回 None 或错误
        """
        if task.target_node:
            # 手动模式: 精确匹配
            for n in nodes:
                if n.ip == task.target_node or n.hostname == task.target_node:
                    if n.status == "alive" and n.gpu_available > 0:
                        return n
            return None  # 指定节点不可用
        else:
            # 自动模式: 使用调度器
            return self.scheduler.schedule(task, nodes)
```

---

## 分配通知机制建议

### 方案: SSE 实时推送

当前已有 SSE progress 机制，可扩展为分配事件通知:

```python
# tasks.py SSE 事件类型
class TaskEvent:
    ALLOCATED = "allocated"      # 节点分配
    STARTED = "started"          # 开始执行
    PROGRESS = "progress"         # 进度更新
    COMPLETED = "completed"       # 完成
    FAILED = "failed"            # 失败

# SSE 消息格式
{
    "event": "allocated",
    "task_id": "train-abc123",
    "assigned_node": "192.168.0.115",
    "node_hostname": "admin10",
    "timestamp": "2026-03-29T10:00:00Z"
}
```

### 前端处理

```typescript
// tasks 页面 SSE 监听
const eventSource = new EventSource(`/api/tasks/events?task_id=${taskId}`);
eventSource.addEventListener('allocated', (e) => {
    const data = JSON.parse(e.data);
    showNotification(`Task assigned to ${data.node_hostname}`);
    updateTaskUI(data);
});
```

---

## 问题与不同观点

### 1. 手动分配的局限性

**问题**: 用户选择节点后，该节点资源可能已被其他任务占用

**建议**:
- 添加节点实时资源状态显示 (GPU 利用率、内存)
- 手动分配时做预校验，返回警告而非阻止
- 使用"软锁定"机制 (30秒内保留给该任务)

### 2. 标签与调度的优先级

**当前调度器**已支持 `preferred_nodes` 亲和性:
```python
# scorers/multi_dim_scorer.py
if task_profile.preferred_nodes:
    if hostname in task_profile.preferred_nodes or ip in task_profile.preferred_nodes:
        score += 100  # 亲和性加分
```

**新标签系统**应与 `preferred_nodes` 协同:
- `required_labels`: 硬性要求 (节点必须具有这些标签)
- `preferred_labels`: 软性偏好 (有则加分)

### 3. Head 节点调度限制

**建议**: Head 节点默认 **不参与任务调度** (仅运行 Ray dashboard/API)

```python
# 调度器过滤
available_nodes = [n for n in nodes if n.role != "head"]
```

除非:
- 任务明确指定 `target_node=head_ip`
- 系统资源严重不足时

### 4. 分配通知的必要性

**权衡**:
- **必要场景**: 用户手动选择节点、任务队列较长
- **冗余场景**: 自动分配且队列短 (几乎立即执行)

**建议**: 默认启用分配通知，但可通过 API 关闭:
```python
TaskCreateRequest(notify_on_assign: bool = True)
```

---

## 实施工作量估算

| 功能 | 组件 | 工作量 |
|------|------|--------|
| Head/Worker 自动识别 | hosts.py | 0.5 天 |
| 节点标签返回 | hosts.py | 0.5 天 |
| target_node 校验 | task.py + API | 1 天 |
| 手动分配调度逻辑 | scheduler | 1 天 |
| SSE 分配通知 | tasks.py SSE | 1 天 |
| 前端节点选择器 | frontend | 1.5 天 |
| **合计** | | **5.5 天** |

---

## 待确认问题

1. **标签存储**: 静态配置 (方案 A) 还是数据库 (方案 B)?
2. **Head 节点调度**: 是否默认排除 Head 节点?
3. **手动分配校验**: 节点不可用时是报错还是自动切换到自动模式?
4. **通知粒度**: 是否所有任务都发送分配通知?

---

## 下一步

确认以上方案后，我可以:
1. 编写节点标签 API 详细设计
2. 更新 TaskCreateRequest 模型
3. 实现 NodeSelector 类
4. 扩展 SSE 事件类型

等待 @coordinator 和团队讨论确认。
