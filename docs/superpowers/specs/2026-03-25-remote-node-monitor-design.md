# 远端节点监控收集方案

> **目标：** 通过 Ray Actor 实现按需查询 Worker 节点的系统信息（CPU、GPU、内存、磁盘等）

## 架构

```
┌──────────────────────────────────────────────────────┐
│                     Head 节点                         │
│   ┌─────────────────┐    ┌─────────────────────┐    │
│   │  RayClient     │    │  NodeMonitorActor   │    │
│   │  (本地节点)     │    │  (本地Actor)        │    │
│   └────────┬────────┘    └──────────┬──────────┘    │
│            │                        │                 │
│            │   ray.nodes()         │                 │
│            │   + 远程 Actor 调用   │                 │
└────────────┼────────────────────────┼────────────────┘
             │                        │
             ▼                        ▼
┌─────────────────────────┐  ┌─────────────────────────┐
│   Worker 192.168.0.130 │  │   Worker 192.168.0.xx  │
│   NodeMonitorActor      │  │   NodeMonitorActor      │
│   (远端Actor调用)       │  │   (远端Actor调用)       │
└─────────────────────────┘  └─────────────────────────┘
```

## 核心组件

### 1. NodeMonitorActor

Ray Actor，部署在每个 Worker 节点上，提供本地系统信息查询。

```python
@ray.remote
class NodeMonitorActor:
    def get_host_info(self) -> dict:
        """收集本地节点系统信息，与 HostMonitor.get_host_info() 相同格式"""
        ...

    def get_node_ip(self) -> str:
        """返回本节点 IP"""
        ...
```

**部署方式：** 使用 `@ray.remote` 装饰器，Head 节点调用 `NodeMonitorActor.options(lifetime="detached").remote()` 会在各 Worker 节点自动调度。

### 2. RayClient 改造

```python
class RayClient:
    def get_nodes(self) -> List[NodeStatus]:
        # 1. ray.nodes() 获取所有节点 IP 和状态
        # 2. 本机节点：直接调用 HostMonitor.get_host_info()
        # 3. 远端节点：遍历 ray.nodes()，对每个 alive 节点
        #    → 获取或创建 NodeMonitorActor（通过 NodeName 索引）
        #    → 远程调用 actor.get_host_info()
        # 4. 合并结果返回
```

### 3. Actor 生命周期管理

- **Detached Actor**：使用 `name=<node_ip>` 创建具名 Actor，确保同一节点只有一个 Actor 实例
- **复用**：已存在的 Actor 直接获取引用调用，避免重复创建

## 数据模型

远端节点返回的 `HostInfo` 格式与本地完全一致：

```python
@dataclass
class RemoteHostInfo:
    hostname: str       # 节点主机名
    ip: str            # 节点 IP
    cpu_count: int
    cpu_physical_cores: int
    cpu_used: int
    cpu_model: str
    cpu_freq_current_mhz: float
    memory_total_gb: float
    memory_used_gb: float
    gpu_name: Optional[str]
    gpu_count: int
    gpu_utilization: int
    gpu_memory_used_gb: float
    gpu_memory_total_gb: float
    disk_total_gb: float
    disk_used_gb: float
    swap_total_gb: float
    swap_used_gb: float
```

## 实现步骤

### Step 1: 创建 NodeMonitorActor
- 文件：`src/algo_studio/monitor/node_monitor.py`
- 复用 `HostMonitor` 的系统信息收集逻辑
- 添加 `@ray.remote` 装饰器

### Step 2: 改造 RayClient.get_nodes()
- 判断节点是否为本机（IP 匹配）
- 本机：调用 HostMonitor
- 远端 alive：获取或创建 NodeMonitorActor，调用 get_host_info()
- 远端 offline：返回有限信息（仅 IP 和状态）

### Step 3: 异常处理
- Actor 调用超时：返回 null 并标记 "获取失败"
- Worker 未部署 Actor：捕获异常，返回 null

## 文件变更

- **新建**：`src/algo_studio/monitor/node_monitor.py` — NodeMonitorActor
- **修改**：`src/algo_studio/core/ray_client.py` — get_nodes() 逻辑
- **修改**：`src/algo_studio/api/routes/hosts.py` — API 路由（已有结构不变）
- **修改**：`src/algo_studio/web/pages/hosts.py` — UI 显示（已有结构不变）
