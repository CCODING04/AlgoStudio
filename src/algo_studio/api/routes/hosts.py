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

        # 获取本机所有 IP（用于匹配 head node）
        import psutil
        local_ips = set()
        for addrs in psutil.net_if_addrs().values():
            for addr in addrs:
                if addr.family.name == "AF_INET":
                    local_ips.add(addr.address)
        # 包含 127.0.0.1 和 LAN IP

        # 将 local_host 的详细信息合并到对应的 cluster node
        cluster_nodes = []
        for idx, n in enumerate(nodes):
            # 判断是否是本机（head node）：Ray 第一个节点为 head，也在本机
            is_local = (idx == 0) or (n.ip in local_ips)

            node = {
                "node_id": n.node_id,
                "ip": n.ip,
                "status": n.status,
                "is_local": is_local,
                "hostname": local_info.hostname if is_local else None,
                "resources": {
                    "cpu": {
                        "total": n.cpu_total if not is_local else local_info.cpu_count,
                        "used": n.cpu_used if not is_local else local_info.cpu_used,
                    },
                    "gpu": {
                        "total": n.gpu_total if not is_local else local_info.gpu_count,
                        "used": n.gpu_used if not is_local else local_info.gpu_used,
                        "name": local_info.gpu_name if is_local else None,
                    },
                    "memory": {
                        "total": f"{n.memory_total_gb}Gi" if not is_local else f"{local_info.memory_total_gb}Gi",
                        "used": f"{n.memory_used_gb}Gi" if not is_local else f"{local_info.memory_used_gb}Gi",
                    },
                    "disk": {
                        "total": f"{n.disk_total_gb}G" if not is_local else f"{local_info.disk_total_gb}G",
                        "used": f"{n.disk_used_gb}G" if not is_local else f"{local_info.disk_used_gb}G",
                    },
                    "swap": {
                        "total": f"{n.swap_total_gb}Gi" if not is_local else f"{local_info.swap_total_gb}Gi",
                        "used": f"{n.swap_used_gb}Gi" if not is_local else f"{local_info.swap_used_gb}Gi",
                    }
                }
            }
            cluster_nodes.append(node)

        return {
            "cluster_nodes": cluster_nodes,
        }
    except Exception as e:
        # 如果 Ray 未初始化，返回仅本地状态
        local_dict = local_monitor.to_dict()
        return {
            "cluster_nodes": [{
                "node_id": "local",
                "ip": local_info.ip,
                "status": "online",
                "is_local": True,
                "hostname": local_info.hostname,
                "resources": {
                    "cpu": {"total": local_info.cpu_count, "used": local_info.cpu_used},
                    "gpu": {"total": local_info.gpu_count, "used": local_info.gpu_used, "name": local_info.gpu_name},
                    "memory": {"total": f"{local_info.memory_total_gb}Gi", "used": f"{local_info.memory_used_gb}Gi"},
                    "disk": {"total": f"{local_info.disk_total_gb}G", "used": f"{local_info.disk_used_gb}G"},
                    "swap": {"total": f"{local_info.swap_total_gb}Gi", "used": f"{local_info.swap_used_gb}Gi"}
                }
            }],
            "error": str(e)
        }