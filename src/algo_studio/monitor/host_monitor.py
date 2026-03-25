# src/algo_studio/monitor/host_monitor.py
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

@dataclass
class HostInfo:
    hostname: str
    ip: str
    cpu_count: int  # logical cores (threads)
    cpu_physical_cores: int  # physical cores (P-cores)
    cpu_used: int
    cpu_model: str
    cpu_freq_current_mhz: float
    memory_total_gb: float
    memory_used_gb: float
    gpu_name: Optional[str]
    gpu_count: int
    gpu_utilization: int  # 0-100 percent
    gpu_memory_used_gb: float
    gpu_memory_total_gb: float
    disk_total_gb: float
    disk_used_gb: float
    swap_total_gb: float
    swap_used_gb: float

    @property
    def cpu_available(self) -> int:
        return self.cpu_count - self.cpu_used

    @property
    def memory_available_gb(self) -> float:
        return self.memory_total_gb - self.memory_used_gb

    @property
    def gpu_available(self) -> int:
        return self.gpu_count - 1 if self.gpu_utilization > 0 else self.gpu_count

class HostMonitor:
    """主机状态监控"""

    def get_host_info(self) -> HostInfo:
        """获取本机状态信息"""
        cpu_count = psutil.cpu_count()  # logical cores (threads)
        cpu_physical_cores = psutil.cpu_count(logical=False)  # physical cores
        cpu_used = psutil.cpu_percent(interval=1)

        # CPU 型号和频率
        cpu_model = "Unknown"
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        cpu_model = line.split(":", 1)[1].strip()
                        break
        except:
            pass
        cpu_freq = psutil.cpu_freq()  # current freq in MHz

        memory = psutil.virtual_memory()
        memory_total_gb = memory.total / (1024**3)
        memory_used_gb = memory.used / (1024**3)

        disk = psutil.disk_usage("/")
        disk_total_gb = disk.total / (1024**3)
        disk_used_gb = disk.used / (1024**3)

        swap = psutil.swap_memory()
        swap_total_gb = swap.total / (1024**3)
        swap_used_gb = swap.used / (1024**3)

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
                    # GPU 利用率（0-100%）
                    utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu_utilization = int(utilization.gpu)
                    # GPU 显存（GB）
                    memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    gpu_memory_used_gb = round(memory_info.used / (1024**3), 1)
                    gpu_memory_total_gb = round(memory_info.total / (1024**3), 1)
            except:
                pass

        return HostInfo(
            hostname=socket.gethostname(),
            ip=socket.gethostbyname(socket.gethostname()),
            cpu_count=cpu_count,
            cpu_physical_cores=cpu_physical_cores,
            cpu_used=int(cpu_used * cpu_count / 100),
            cpu_model=cpu_model,
            cpu_freq_current_mhz=round(cpu_freq.current, 0) if cpu_freq else 0.0,
            memory_total_gb=round(memory_total_gb, 1),
            memory_used_gb=round(memory_used_gb, 1),
            gpu_name=gpu_name,
            gpu_count=gpu_count,
            gpu_utilization=gpu_utilization,
            gpu_memory_used_gb=gpu_memory_used_gb,
            gpu_memory_total_gb=gpu_memory_total_gb,
            disk_total_gb=round(disk_total_gb, 1),
            disk_used_gb=round(disk_used_gb, 1),
            swap_total_gb=round(swap_total_gb, 1),
            swap_used_gb=round(swap_used_gb, 1)
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        info = self.get_host_info()
        return {
            "hostname": info.hostname,
            "ip": info.ip,
            "status": "online",
            "resources": {
                "cpu": {
                    "total": info.cpu_count,
                    "used": info.cpu_used,
                    "physical_cores": info.cpu_physical_cores,
                    "model": info.cpu_model,
                    "freq_mhz": info.cpu_freq_current_mhz,
                },
                "gpu": {
                    "total": info.gpu_count,
                    "utilization": info.gpu_utilization,
                    "memory_used": f"{info.gpu_memory_used_gb}Gi",
                    "memory_total": f"{info.gpu_memory_total_gb}Gi",
                    "name": info.gpu_name,
                },
                "memory": {"total": f"{info.memory_total_gb}Gi", "used": f"{info.memory_used_gb}Gi"},
                "disk": {"total": f"{info.disk_total_gb}G", "used": f"{info.disk_used_gb}G"},
                "swap": {"total": f"{info.swap_total_gb}Gi", "used": f"{info.swap_used_gb}Gi"}
            }
        }