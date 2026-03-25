from dataclasses import dataclass
from typing import Any, List, Optional
import ray
from algo_studio.monitor.node_monitor import NodeMonitorActor

# ActorNotFoundError was added in Ray 2.9.0
try:
    from ray.exceptions import ActorNotFoundError
except ImportError:
    ActorNotFoundError = ValueError  # Fallback for older Ray versions

# GPU 可用性检测
try:
    import pynvml
    pynvml.nvmlInit()
    GPU_AVAILABLE = True
except:
    GPU_AVAILABLE = False

@dataclass
class NodeStatus:
    node_id: str
    ip: str
    status: str  # "idle" | "busy" | "offline"
    cpu_used: int
    cpu_total: int
    gpu_used: int
    gpu_total: int
    memory_used_gb: float
    memory_total_gb: float
    disk_used_gb: float
    disk_total_gb: float
    swap_used_gb: float = 0.0
    swap_total_gb: float = 0.0

    @property
    def cpu_available(self) -> int:
        return self.cpu_total - self.cpu_used

    @property
    def gpu_available(self) -> int:
        return self.gpu_total - self.gpu_used

    @property
    def memory_available_gb(self) -> float:
        return self.memory_total_gb - self.memory_used_gb

class RayClient:
    def __init__(self, head_address: Optional[str] = None):
        self.head_address = head_address
        if head_address:
            ray.init(address=head_address)
        else:
            ray.init()

    def get_nodes(self) -> List[NodeStatus]:
        """获取所有节点状态"""
        import psutil
        from algo_studio.monitor.host_monitor import HostMonitor

        nodes = []
        local_ips = set()
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family.name == "AF_INET":
                    local_ips.add(addr.address)

        for node in ray.nodes():
            node_ip = node.get("NodeName") or node.get("node_ip_address") or "unknown"
            resources = node.get("resources", {})
            is_alive = node.get("Alive", False)

            if not is_alive:
                # Offline node - return null/0 for unavailable fields
                status = NodeStatus(
                    node_id=node["NodeID"],
                    ip=node_ip,
                    status="offline",
                    cpu_used=0,
                    cpu_total=0,
                    gpu_used=0,
                    gpu_total=0,
                    memory_used_gb=0.0,
                    memory_total_gb=0.0,
                    disk_used_gb=0.0,
                    disk_total_gb=0.0,
                    swap_used_gb=0.0,
                    swap_total_gb=0.0
                )
                nodes.append(status)
                continue

            # Alive node - get host info either locally or via actor
            if node_ip in local_ips:
                # Local node - use HostMonitor directly
                host_info = HostMonitor().get_host_info()
                cpu_used = host_info.cpu_used
                cpu_total = host_info.cpu_count
                gpu_used = 1 if host_info.gpu_utilization > 0 else 0
                gpu_total = host_info.gpu_count
                memory_used_gb = host_info.memory_used_gb
                memory_total_gb = host_info.memory_total_gb
                disk_used_gb = host_info.disk_used_gb
                disk_total_gb = host_info.disk_total_gb
                swap_used_gb = host_info.swap_used_gb
                swap_total_gb = host_info.swap_total_gb
            else:
                # Remote node - use NodeMonitorActor
                try:
                    actor_name = f"node_monitor_{node_ip}"
                    try:
                        actor = ray.get_actor(actor_name, namespace="algo_studio")
                    except ActorNotFoundError:
                        # Actor doesn't exist, create it
                        actor = NodeMonitorActor.options(
                            name=actor_name,
                            namespace="algo_studio",
                            lifetime="detached",
                            resources={f"node:{node_ip}": 0.001}
                        ).remote()
                    except Exception:
                        # Other errors - skip this node
                        continue

                    host_info = ray.get(actor.get_host_info.remote(), timeout=5)
                    cpu_used = host_info.get("cpu_used", 0)
                    cpu_total = host_info.get("cpu_count", 0)
                    gpu_util = host_info.get("gpu_utilization", 0)
                    gpu_used = 1 if gpu_util > 0 else 0
                    gpu_total = host_info.get("gpu_count", 0)
                    memory_used_gb = host_info.get("memory_used_gb", 0.0)
                    memory_total_gb = host_info.get("memory_total_gb", 0.0)
                    disk_used_gb = host_info.get("disk_used_gb", 0.0)
                    disk_total_gb = host_info.get("disk_total_gb", 0.0)
                    swap_used_gb = host_info.get("swap_used_gb", 0.0)
                    swap_total_gb = host_info.get("swap_total_gb", 0.0)
                except Exception:
                    # Actor call failed - return minimal info
                    cpu_used = int(resources.get("CPU", 0))
                    cpu_total = 0
                    gpu_used = int(resources.get("GPU", 0))
                    gpu_total = int(resources.get("GPU", 0))
                    memory_used_gb = 0.0
                    memory_total_gb = 0.0
                    disk_used_gb = 0.0
                    disk_total_gb = 0.0
                    swap_used_gb = 0.0
                    swap_total_gb = 0.0

            status = NodeStatus(
                node_id=node["NodeID"],
                ip=node_ip,
                status="idle",
                cpu_used=cpu_used,
                cpu_total=cpu_total,
                gpu_used=gpu_used,
                gpu_total=gpu_total,
                memory_used_gb=memory_used_gb,
                memory_total_gb=memory_total_gb,
                disk_used_gb=disk_used_gb,
                disk_total_gb=disk_total_gb,
                swap_used_gb=swap_used_gb,
                swap_total_gb=swap_total_gb
            )
            nodes.append(status)
        return nodes

    def submit_task(self, func, *args, **kwargs):
        """提交任务到 Ray 集群"""
        return func.options(
            num_cpus=kwargs.get("num_cpus", 1),
            num_gpus=kwargs.get("num_gpus", 0),
            resources=kwargs.get("resources", {})
        ).remote(*args)

    def shutdown(self):
        """关闭 Ray 连接"""
        ray.shutdown()