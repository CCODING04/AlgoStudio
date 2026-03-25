# src/algo_studio/monitor/node_monitor.py
import socket
import ray
import psutil
from typing import Optional, Dict, Any

try:
    import pynvml
    pynvml.nvmlInit()
    GPU_AVAILABLE = True
except:
    GPU_AVAILABLE = False


@ray.remote
class NodeMonitorActor:
    """Ray Actor for collecting remote node system information"""

    def get_node_ip(self) -> str:
        """Return the IP address of this node using Ray Worker's node_ip_address"""
        try:
            return ray._private.worker.global_worker.node_ip_address
        except Exception:
            return socket.gethostbyname(socket.gethostname())

    def get_host_info(self) -> Dict[str, Any]:
        """Collect and return local system information as a dict"""
        cpu_count = psutil.cpu_count()  # logical cores (threads)
        cpu_physical_cores = psutil.cpu_count(logical=False)  # physical cores
        cpu_used = psutil.cpu_percent(interval=1)

        # CPU model from /proc/cpuinfo
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

        # Try to initialize pynvml in case it failed at module import
        _gpu_available = GPU_AVAILABLE
        if not _gpu_available:
            try:
                pynvml.nvmlInit()
                _gpu_available = True
            except:
                pass

        if _gpu_available:
            try:
                gpu_count = pynvml.nvmlDeviceGetCount()
                if gpu_count > 0:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    gpu_name = pynvml.nvmlDeviceGetName(handle)
                    # GPU utilization (0-100%)
                    utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu_utilization = int(utilization.gpu)
                    # GPU memory (GB)
                    memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    gpu_memory_used_gb = round(memory_info.used / (1024**3), 1)
                    gpu_memory_total_gb = round(memory_info.total / (1024**3), 1)
            except:
                pass

        return {
            "hostname": socket.gethostname(),
            "ip": socket.gethostbyname(socket.gethostname()),
            "cpu_count": cpu_count,
            "cpu_physical_cores": cpu_physical_cores,
            "cpu_used": int(cpu_used * cpu_count / 100),
            "cpu_model": cpu_model,
            "cpu_freq_current_mhz": round(cpu_freq.current, 0) if cpu_freq else 0.0,
            "memory_total_gb": round(memory_total_gb, 1),
            "memory_used_gb": round(memory_used_gb, 1),
            "gpu_name": gpu_name,
            "gpu_count": gpu_count,
            "gpu_utilization": gpu_utilization,
            "gpu_memory_used_gb": gpu_memory_used_gb,
            "gpu_memory_total_gb": gpu_memory_total_gb,
            "disk_total_gb": round(disk_total_gb, 1),
            "disk_used_gb": round(disk_used_gb, 1),
            "swap_total_gb": round(swap_total_gb, 1),
            "swap_used_gb": round(swap_used_gb, 1)
        }