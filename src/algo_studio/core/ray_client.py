from dataclasses import dataclass
from typing import Any, List, Optional
import ray

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
        nodes = []

        for node in ray.nodes():
            resources = node.get("resources", {})
            is_alive = node.get("Alive", False)

            # 获取本机硬件信息用于补充 Ray 节点信息
            cpu_count = psutil.cpu_count()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            status = NodeStatus(
                node_id=node["NodeID"],
                ip=node.get("node_ip_address", node.get("NodeName", "unknown")),
                status="idle" if is_alive else "offline",
                cpu_used=int(resources.get("CPU", 0)),
                cpu_total=cpu_count,
                gpu_used=int(resources.get("GPU", 0)),
                gpu_total=1 if GPU_AVAILABLE else 0,  # 简化假设每机单卡
                memory_used_gb=round(memory.used / (1024**3), 1),
                memory_total_gb=round(memory.total / (1024**3), 1),
                disk_used_gb=round(disk.used / (1024**3), 1),
                disk_total_gb=round(disk.total / (1024**3), 1),
                swap_used_gb=round(psutil.swap_memory().used / (1024**3), 1),
                swap_total_gb=round(psutil.swap_memory().total / (1024**3), 1)
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