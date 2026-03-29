# from: @backend-engineer
# to: @coordinator
# date: 2026-03-29
# type: report
# round: Phase 3.2 Round 3

## 任务完成报告: core/task.py 和 core/ray_client.py 分析

### 1. core/task.py 分析

#### TaskManager 类结构

| 组件 | 类型 | 说明 |
|------|------|------|
| `ProgressStore` | Ray Actor | 共享进度存储，跨进程/跨任务共享 |
| `ProgressReporter` | Ray Actor | 向 TaskManager 报告进度的 per-task actor |
| `TaskType` | Enum | TRAIN, INFER, VERIFY |
| `TaskStatus` | Enum | PENDING, RUNNING, COMPLETED, FAILED, CANCELLED |
| `Task` | Dataclass | 任务数据模型 |
| `TaskManager` | Class | 任务生命周期管理 |
| `RayProgressCallback` | Class | Ray 分布式进度回调 |
| `run_training/inference/verification` | Ray Remote Functions | 分布式任务执行函数 |

#### 任务状态机

```
PENDING -> RUNNING -> COMPLETED
                   -> FAILED
                   -> CANCELLED
```

关键转换逻辑:
- `update_status(RUNNING)` 时设置 `started_at`
- `update_status(COMPLETED/FAILED)` 时设置 `completed_at`

#### Ray 任务分发逻辑 (`dispatch_task`)

1. 获取空闲节点（优先 GPU idle 节点）
2. 创建 `ProgressReporter` Actor
3. 根据 `task_type` 提交到 Ray（使用 `node_ip` 亲和性）
4. `ray.get()` 等待结果并更新状态
5. 清理 `ProgressReporter` Actor

---

### 2. core/ray_client.py 分析

#### RayClient 类结构

| 组件 | 类型 | 说明 |
|------|------|------|
| `NodeStatus` | Dataclass | 节点状态数据模型 |
| `RayClient` | Class | Ray 集群客户端 |

#### NodeStatus 关键字段

- 基本信息: `node_id`, `ip`, `hostname`, `status` (idle/busy/offline)
- CPU: `cpu_used`, `cpu_total`, `cpu_available`
- GPU: `gpu_used`, `gpu_total`, `gpu_available`, `gpu_utilization`, `gpu_name`
- Memory: `memory_used_gb`, `memory_total_gb`, `memory_available_gb`
- Disk: `disk_used_gb`, `disk_total_gb`
- 可选详情: `cpu_model`, `cpu_physical_cores`, `cpu_freq_current_mhz`, `gpu_memory_used_gb`, `gpu_memory_total_gb`

#### RayClient 关键方法

| 方法 | 说明 |
|------|------|
| `get_nodes()` | 获取所有节点状态（带 5s 缓存） |
| `submit_task()` | 提交任务到 Ray 集群，支持 CPU/GPU/节点亲和性 |
| `shutdown()` | 关闭 Ray 连接 |
| `clear_cache()` | 清除节点缓存 |
| `_ensure_ray_init()` | 延迟初始化 Ray |
| `_check_ray_available()` | Socket 连通性快速检查 |

#### 节点查询流程 (`get_nodes`)

1. 检查缓存（TTL 5s）
2. `_ensure_ray_init()` 初始化 Ray
3. 获取 `ray.nodes()` 列表并去重
4. 并行获取远程节点信息（ThreadPoolExecutor，最多 4 workers）
5. 本地节点使用 `HostMonitor`，远程节点使用 `NodeMonitorActor`
6. 返回 `List[NodeStatus]`

---

### 3. 测试辅助 fixtures

已创建 `tests/unit/core/conftest.py`，包含以下 fixtures:

#### Task 相关
- `task_factory` / `TaskFactory` - 任务工厂
- `task_manager` - 干净 TaskManager 实例
- `task_manager_with_tasks` - 预置 3 个任务的 TaskManager
- `ray_progress_callback` - 带 mock reporter 的进度回调

#### NodeStatus 相关
- `node_status_factory` / `NodeStatusFactory` - 节点工厂
- `mock_node_status` - 示例节点
- `mock_idle_gpu_node` - 空闲 GPU 节点
- `mock_busy_gpu_node` - 忙碌 GPU 节点
- `mock_nodes_list` - 3 个节点的列表（idle/busy/offline）

#### Ray Client Mock
- `mock_ray_client` - 基本 mock
- `mock_ray_client_with_nodes` - 带示例节点
- `mock_ray_client_with_idle_gpu_node` - 带空闲 GPU 节点

#### Progress Actor Mock
- `mock_progress_store` - ProgressStore mock
- `mock_progress_reporter` - ProgressReporter mock

---

### 4. 覆盖率建议

基于分析，以下场景需要测试覆盖:

| 模块 | 建议测试场景 |
|------|-------------|
| TaskManager | `dispatch_task` 失败处理（无节点）、分页查询 |
| RayClient | `get_nodes` 缓存、节点去重、远程节点信息获取 |
| ProgressReporter | 多任务进度更新 |
| RayProgressCallback | `update` 和 `set_description` 调用 |

---

### 文件变更

- **新增**: `tests/unit/core/conftest.py` (169 行)
