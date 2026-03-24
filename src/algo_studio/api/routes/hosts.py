# src/algo_studio/api/routes/hosts.py
from fastapi import APIRouter
from algo_studio.core.ray_client import RayClient
from algo_studio.monitor.host_monitor import HostMonitor

router = APIRouter(prefix="/api/hosts", tags=["hosts"])
ray_client = RayClient()
local_monitor = HostMonitor()

@router.get("/status")
async def get_host_status():
    """获取所有集群主机状态"""
    try:
        # 获取 Ray 集群节点列表
        nodes = ray_client.get_nodes()

        # 获取本机详细信息
        local_info = local_monitor.get_host_info()

        return {
            "cluster_nodes": [
                {
                    "node_id": n.node_id,
                    "ip": n.ip,
                    "status": n.status,
                    "resources": {
                        "cpu": {"total": n.cpu_total, "used": n.cpu_used, "available": n.cpu_available},
                        "gpu": {"total": n.gpu_total, "used": n.gpu_used, "available": n.gpu_available},
                        "memory": {"total": f"{n.memory_total_gb}Gi", "used": f"{n.memory_used_gb}Gi", "available": f"{n.memory_available_gb}Gi"},
                        "disk": {"total": f"{n.disk_total_gb}G", "used": f"{n.disk_used_gb}G"},
                        "swap": {"total": f"{n.swap_total_gb}Gi", "used": f"{n.swap_used_gb}Gi"}
                    }
                }
                for n in nodes
            ],
            "local_host": {
                "hostname": local_info.hostname,
                "ip": local_info.ip,
                "resources": {
                    "cpu": {"total": local_info.cpu_count, "used": local_info.cpu_used},
                    "gpu": {"total": local_info.gpu_count, "used": local_info.gpu_used, "name": local_info.gpu_name},
                    "memory": {"total": f"{local_info.memory_total_gb}Gi", "used": f"{local_info.memory_used_gb}Gi"},
                    "disk": {"total": f"{local_info.disk_total_gb}G", "used": f"{local_info.disk_used_gb}G"},
                    "swap": {"total": f"{local_info.swap_total_gb}Gi", "used": f"{local_info.swap_used_gb}Gi"}
                }
            }
        }
    except Exception as e:
        # 如果 Ray 未初始化，返回本地状态
        return {
            "cluster_nodes": [],
            "local_host": local_monitor.to_dict(),
            "error": str(e)
        }