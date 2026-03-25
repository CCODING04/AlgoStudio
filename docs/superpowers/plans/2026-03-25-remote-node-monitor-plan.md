# 远端节点监控收集实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 通过 Ray Actor 实现按需查询 Worker 节点的系统信息，替代当前 fallback 到本机数据的假数据问题

**Architecture:** 在每个 Worker 节点部署 NodeMonitorActor（Ray Actor），Head 节点调用 ray.nodes() 获取节点列表后，对远端节点通过 Actor 远程调用获取系统信息

**Tech Stack:** Ray Actor, psutil, pynvml

---

## Task 1: 创建 NodeMonitorActor

**Files:**
- Create: `src/algo_studio/monitor/node_monitor.py`

### 步骤 1.1: 创建 NodeMonitorActor 类

在 `src/algo_studio/monitor/node_monitor.py` 中创建：

```python
import ray
import socket
import psutil
from dataclasses import dataclass
from typing import Optional

try:
    import pynvml
    pynvml.nvmlInit()
    GPU_AVAILABLE = True
except:
    GPU_AVAILABLE = False

@ray.remote
class NodeMonitorActor:
    """Ray Actor，在每个节点上收集本地系统信息"""

    def get_node_ip(self) -> str:
        """返回本节点 IP"""
        # 优先使用 Ray 分配的节点 IP
        import ray._private.node as node_module
        try:
            return ray._private.worker.global_worker.node_ip_address
        except:
            return socket.gethostbyname(socket.gethostname())

    def get_host_info(self) -> dict:
        """收集本地节点完整系统信息，与 HostMonitor.get_host_info() 格式一致"""
        cpu_count = psutil.cpu_count()
        cpu_physical_cores = psutil.cpu_count(logical=False)
        cpu_used = psutil.cpu_percent(interval=0.5)  # 缩短等待时间

        cpu_model = "Unknown"
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        cpu_model = line.split(":", 1)[1].strip()
                        break
        except:
            pass
        cpu_freq = psutil.cpu_freq()

        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        swap = psutil.swap_memory()

        gpu_name = None
        gpu_count = 0
        gpu_utilization = 0
        gpu_memory_used_gb = 0.0
        gpu_memory_total_gb = 0.0

        if GPU_AVAILABLE:
            try:
                gpu_count = pynvml.nvmlDeviceGetCount()
                if gpu_count > 0:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    gpu_name = pynvml.nvmlDeviceGetName(handle)
                    utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu_utilization = int(utilization.gpu)
                    memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    gpu_memory_used_gb = round(memory_info.used / (1024**3), 1)
                    gpu_memory_total_gb = round(memory_info.total / (1024**3), 1)
            except:
                pass

        return {
            "hostname": socket.gethostname(),
            "ip": self.get_node_ip(),
            "cpu_count": cpu_count,
            "cpu_physical_cores": cpu_physical_cores,
            "cpu_used": int(cpu_used * cpu_count / 100),
            "cpu_model": cpu_model,
            "cpu_freq_current_mhz": round(cpu_freq.current, 0) if cpu_freq else 0.0,
            "memory_total_gb": round(memory.total / (1024**3), 1),
            "memory_used_gb": round(memory.used / (1024**3), 1),
            "gpu_name": gpu_name,
            "gpu_count": gpu_count,
            "gpu_utilization": gpu_utilization,
            "gpu_memory_used_gb": gpu_memory_used_gb,
            "gpu_memory_total_gb": gpu_memory_total_gb,
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "disk_used_gb": round(disk.used / (1024**3), 1),
            "swap_total_gb": round(swap.total / (1024**3), 1),
            "swap_used_gb": round(swap.used / (1024**3), 1),
        }
```

### 步骤 1.2: 提交

```bash
git add src/algo_studio/monitor/node_monitor.py
git commit -m "feat: add NodeMonitorActor for remote node info collection

NodeMonitorActor is a Ray actor that runs on each worker node
and collects local system info (CPU, GPU, memory, disk).
Exposes get_host_info() and get_node_ip() methods.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: 改造 RayClient.get_nodes() 使用 Actor

**Files:**
- Modify: `src/algo_studio/core/ray_client.py:49-80`

### 步骤 2.1: 修改 get_nodes() 逻辑

读取当前 `ray_client.py` 的完整内容，替换 `get_nodes()` 方法：

```python
from algo_studio.monitor.node_monitor import NodeMonitorActor

def get_nodes(self) -> List[NodeStatus]:
    """获取所有节点状态"""
    import psutil
    nodes = []
    all_actors = {}

    # 获取所有本地 IP
    local_ips = set()
    for addrs in psutil.net_if_addrs().values():
        for addr in addrs:
            if addr.family.name == "AF_INET":
                local_ips.add(addr.address)

    # 收集所有 alive 节点的 Actor 引用
    for node in ray.nodes():
        is_alive = node.get("Alive", False)
        if not is_alive:
            continue

        node_ip = node.get("NodeName") or node.get("node_ip_address")
        if not node_ip:
            continue

        # 尝试获取已存在的 Actor
        try:
            actor_handle = ray.get_actor(f"node_monitor_{node_ip}", namespace="algo_studio")
            all_actors[node_ip] = actor_handle
        except:
            # Actor 不存在，在该节点创建
            try:
                actor_handle = NodeMonitorActor.options(
                    name=f"node_monitor_{node_ip}",
                    namespace="algo_studio",
                    lifetime="detached",
                    resources={f"node:{node_ip}": 0.001}  # 调度到指定节点
                ).remote()
                all_actors[node_ip] = actor_handle
            except:
                pass

    # 遍历所有节点获取状态
    for node in ray.nodes():
        resources = node.get("resources", {})
        is_alive = node.get("Alive", False)
        node_ip = node.get("NodeName") or node.get("node_ip_address") or "unknown"
        is_local = node_ip in local_ips

        cpu_count = psutil.cpu_count() if is_local else 0
        memory_total_gb = 0.0
        memory_used_gb = 0.0
        disk_total_gb = 0.0
        disk_used_gb = 0.0
        swap_total_gb = 0.0
        swap_used_gb = 0.0
        cpu_model = None
        cpu_physical_cores = None
        cpu_freq_current_mhz = None
        gpu_name = None
        gpu_count = 0
        gpu_utilization = 0
        gpu_memory_used_gb = 0.0
        gpu_memory_total_gb = 0.0

        if is_alive:
            if is_local:
                # 本机：使用 HostMonitor
                from algo_studio.monitor.host_monitor import HostMonitor
                monitor = HostMonitor()
                info = monitor.get_host_info()
                cpu_count = info.cpu_count
                cpu_physical_cores = info.cpu_physical_cores
                cpu_model = info.cpu_model
                cpu_freq_current_mhz = info.cpu_freq_current_mhz
                memory_total_gb = info.memory_total_gb
                memory_used_gb = info.memory_used_gb
                disk_total_gb = info.disk_total_gb
                disk_used_gb = info.disk_used_gb
                swap_total_gb = info.swap_total_gb
                swap_used_gb = info.swap_used_gb
                gpu_name = info.gpu_name
                gpu_count = info.gpu_count
                gpu_utilization = info.gpu_utilization
                gpu_memory_used_gb = info.gpu_memory_used_gb
                gpu_memory_total_gb = info.gpu_memory_total_gb
            elif node_ip in all_actors:
                # 远端 alive：通过 Actor 获取
                try:
                    actor = all_actors[node_ip]
                    info = ray.get(actor.get_host_info.remote(), timeout=5)
                    cpu_count = info.get("cpu_count", 0)
                    cpu_physical_cores = info.get("cpu_physical_cores")
                    cpu_model = info.get("cpu_model")
                    cpu_freq_current_mhz = info.get("cpu_freq_current_mhz")
                    memory_total_gb = info.get("memory_total_gb", 0)
                    memory_used_gb = info.get("memory_used_gb", 0)
                    disk_total_gb = info.get("disk_total_gb", 0)
                    disk_used_gb = info.get("disk_used_gb", 0)
                    swap_total_gb = info.get("swap_total_gb", 0)
                    swap_used_gb = info.get("swap_used_gb", 0)
                    gpu_name = info.get("gpu_name")
                    gpu_count = info.get("gpu_count", 0)
                    gpu_utilization = info.get("gpu_utilization", 0)
                    gpu_memory_used_gb = info.get("gpu_memory_used_gb", 0)
                    gpu_memory_total_gb = info.get("gpu_memory_total_gb", 0)
                except Exception as e:
                    # Actor 调用失败，保留 null 值
                    pass

        status = NodeStatus(
            node_id=node["NodeID"],
            ip=node_ip,
            status="idle" if is_alive else "offline",
            cpu_used=int(resources.get("CPU", 0)),
            cpu_total=cpu_count,
            gpu_used=int(resources.get("GPU", 0)),
            gpu_total=gpu_count,
            memory_used_gb=memory_used_gb,
            memory_total_gb=memory_total_gb,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
            swap_used_gb=swap_used_gb,
            swap_total_gb=swap_total_gb,
        )
        nodes.append(status)

    return nodes
```

### 步骤 2.2: 提交

```bash
git add src/algo_studio/core/ray_client.py
git commit -m "feat: use NodeMonitorActor for remote node info in get_nodes()

- RayClient.get_nodes() now uses Actor for remote node info collection
- Local nodes continue to use HostMonitor directly
- Remote alive nodes: ray.get(actor.get_host_info.remote(), timeout=5)
- Remote offline nodes: return null for unavailable fields
- Actors are named by IP for singleton per-node management

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: 验证实现

### 步骤 3.1: 测试本机节点

```bash
curl -s http://localhost:8000/api/hosts/status | python -m json.tool
```

验证：
- Head 节点（192.168.0.126）显示完整信息：CPU 型号、GPU 型号等
- 远端离线节点显示 null 而非假数据

### 步骤 3.2: Worker 节点加入测试

```bash
# 在 Worker 节点执行
cd /home/gr/Code/AlgoStudio
git pull
bash scripts/join_cluster.sh 192.168.0.126
```

验证：
- `curl http://localhost:8000/api/hosts/status` 显示 Worker 节点完整信息
- Worker 的 CPU 型号、GPU 型号、内存等信息正确显示

### 步骤 3.3: 提交

```bash
git add -A
git commit -m "chore: verify remote node monitor works end-to-end"
```
