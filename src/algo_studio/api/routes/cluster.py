# src/algo_studio/api/routes/cluster.py

"""
Ray 集群状态 API 路由

提供 Ray 集群的节点状态、Actor、Task 等信息的查询接口。
三层架构: Web Console -> Backend -> RayAPIClient -> Ray Cluster
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cluster", tags=["cluster"])

# 全局 Ray API Client 实例（延迟初始化）
_ray_client: Optional["RayAPIClient"] = None


def get_ray_client() -> "RayAPIClient":
    """获取 Ray API Client 单例"""
    global _ray_client
    if _ray_client is None:
        # 从配置或环境变量获取 Head 地址
        head_address = os.getenv("RAY_HEAD_ADDRESS", "localhost")
        dashboard_port = int(os.getenv("RAY_DASHBOARD_PORT", "8265"))
        _ray_client = RayAPIClient(
            head_address=head_address,
            dashboard_port=dashboard_port,
            enable_cache=True,
            enable_circuit_breaker=True
        )
    return _ray_client


# Import at module level for type hints
from algo_studio.core.ray_dashboard_client import RayAPIClient
from algo_studio.core.ray_compat import detect_ray_version, RayAPICompat


# ==================== Request/Response Models ====================

class NodeInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    node_id: str
    ip: str
    hostname: Optional[str] = None
    status: str  # "alive" | "dead"
    cpu_count: int = 0
    memory_total_gb: float = 0
    memory_used_gb: float = 0
    gpu_count: int = 0
    gpu_utilization: Optional[int] = None


class ActorInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    actor_id: str
    class_name: str
    state: str  # "ALIVE" | "DEAD" | "PENDING"
    job_id: Optional[str] = None
    node_ip_address: Optional[str] = None
    num_restarts: int = 0
    timestamp: Optional[int] = None


class TaskInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    func_name: str
    state: str
    node_ip_address: Optional[str] = None
    actor_id: Optional[str] = None
    submitted_at: Optional[int] = None


class ClusterStatusResponse(BaseModel):
    connected: bool
    ray_version: Optional[str] = None
    cluster_status: Optional[Dict[str, Any]] = None
    nodes: List[NodeInfo] = []
    actors_count: int = 0
    tasks_count: int = 0
    error: Optional[str] = None


class NodeDetailResponse(BaseModel):
    node_id: str
    ip: str
    hostname: Optional[str] = None
    status: str
    resources: Dict[str, Any]
    log_count: int = 0


class HealthCheckResponse(BaseModel):
    status: str  # "healthy" | "degraded" | "unhealthy"
    ray_dashboard: bool
    gcs: bool
    circuit_breaker: str
    cache_stats: Dict[str, int]


# ==================== API Endpoints ====================

@router.get("/status", response_model=ClusterStatusResponse)
async def get_cluster_status():
    """获取集群综合状态

    整合 Ray Dashboard 的多个 API，返回集群全景状态。
    包含缓存机制，5秒内重复请求返回缓存数据。
    """
    import asyncio
    client = get_ray_client()

    # 并行调用多个 API
    async def fetch_all():
        health_task = asyncio.to_thread(client.health_check)
        cluster_task = asyncio.to_thread(client.get_cluster_status)
        nodes_task = asyncio.to_thread(client.list_nodes)
        actors_task = asyncio.to_thread(client.list_actors)
        tasks_task = asyncio.to_thread(client.list_tasks)

        return await asyncio.gather(
            health_task, cluster_task, nodes_task,
            actors_task, tasks_task,
            return_exceptions=True
        )

    health_resp, cluster_resp, nodes_resp, actors_resp, tasks_resp = await fetch_all()

    # 检测 Ray 版本
    ray_version = detect_ray_version()

    # 构建响应
    if isinstance(health_resp, Exception):
        return ClusterStatusResponse(
            connected=False,
            ray_version=ray_version,
            error=f"Failed to connect to Ray Dashboard: {str(health_resp)}"
        )

    nodes = []
    if not isinstance(nodes_resp, Exception) and nodes_resp.success:
        compat = RayAPICompat(ray_version or "2.5.0")
        node_data = nodes_resp.data

        # 统一处理不同版本的数据格式
        if isinstance(node_data, dict) and "nodes" in node_data:
            for node in node_data["nodes"]:
                nodes.append(NodeInfo(
                    node_id=node.get("node_id", ""),
                    ip=node.get("ip", ""),
                    hostname=node.get("hostname"),
                    status=node.get("status", "unknown"),
                    cpu_count=node.get("resources", {}).get("CPU", 0),
                    memory_total_gb=0,  # 需要额外查询
                    memory_used_gb=0,
                    gpu_count=int(node.get("resources", {}).get("GPU", 0)),
                ))

    actors_count = 0
    if not isinstance(actors_resp, Exception) and actors_resp.success:
        actors_count = len(actors_resp.data.get("actors", []))

    tasks_count = 0
    if not isinstance(tasks_resp, Exception) and tasks_resp.success:
        tasks_count = len(tasks_resp.data.get("tasks", []))

    return ClusterStatusResponse(
        connected=health_resp.success if not isinstance(health_resp, Exception) else False,
        ray_version=ray_version,
        cluster_status=cluster_resp.data if not isinstance(cluster_resp, Exception) else None,
        nodes=nodes,
        actors_count=actors_count,
        tasks_count=tasks_count,
        error=health_resp.error if not isinstance(health_resp, Exception) and not health_resp.success else None
    )


@router.get("/nodes", response_model=List[NodeInfo])
async def list_nodes():
    """获取集群节点列表"""
    client = get_ray_client()
    resp = await asyncio.to_thread(client.list_nodes)

    if not resp.success:
        raise HTTPException(status_code=503, detail=resp.error)

    nodes = []
    data = resp.data
    if isinstance(data, dict) and "nodes" in data:
        for node in data["nodes"]:
            nodes.append(NodeInfo(
                node_id=node.get("node_id", ""),
                ip=node.get("ip", ""),
                hostname=node.get("hostname"),
                status=node.get("status", "unknown"),
                cpu_count=int(node.get("resources", {}).get("CPU", 0)),
                gpu_count=int(node.get("resources", {}).get("GPU", 0)),
            ))

    return nodes


@router.get("/nodes/{node_id}", response_model=NodeDetailResponse)
async def get_node_detail(node_id: str):
    """获取节点详细信息"""
    client = get_ray_client()
    resp = await asyncio.to_thread(client.get_node, node_id)

    if not resp.success:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")

    data = resp.data
    if isinstance(data, dict):
        return NodeDetailResponse(
            node_id=data.get("node_id", node_id),
            ip=data.get("ip", ""),
            hostname=data.get("hostname"),
            status=data.get("status", "unknown"),
            resources=data.get("resources", {}),
            log_count=0
        )

    raise HTTPException(status_code=500, detail="Invalid response format")


@router.get("/actors", response_model=List[ActorInfo])
async def list_actors(limit: int = Query(default=100, le=1000)):
    """获取 Actor 列表"""
    client = get_ray_client()
    resp = await asyncio.to_thread(client.list_actors, limit=limit)

    if not resp.success:
        raise HTTPException(status_code=503, detail=resp.error)

    actors = []
    data = resp.data
    if isinstance(data, dict) and "actors" in data:
        for actor in data["actors"]:
            actors.append(ActorInfo(
                actor_id=actor.get("actor_id", ""),
                class_name=actor.get("class_name", "Unknown"),
                state=actor.get("state", "UNKNOWN"),
                job_id=actor.get("job_id"),
                node_ip_address=actor.get("node_ip_address"),
                num_restarts=actor.get("num_restarts", 0),
                timestamp=actor.get("timestamp"),
            ))

    return actors


@router.get("/actors/{actor_id}", response_model=ActorInfo)
async def get_actor_detail(actor_id: str):
    """获取 Actor 详细信息"""
    client = get_ray_client()
    resp = await asyncio.to_thread(client.get_actor, actor_id)

    if not resp.success:
        raise HTTPException(status_code=404, detail=f"Actor not found: {actor_id}")

    data = resp.data
    if isinstance(data, dict):
        return ActorInfo(
            actor_id=data.get("actor_id", actor_id),
            class_name=data.get("class_name", "Unknown"),
            state=data.get("state", "UNKNOWN"),
            job_id=data.get("job_id"),
            node_ip_address=data.get("node_ip_address"),
            num_restarts=data.get("num_restarts", 0),
            timestamp=data.get("timestamp"),
        )

    raise HTTPException(status_code=500, detail="Invalid response format")


@router.get("/tasks", response_model=List[TaskInfo])
async def list_tasks(limit: int = Query(default=100, le=1000)):
    """获取 Task 列表"""
    client = get_ray_client()
    resp = await asyncio.to_thread(client.list_tasks, limit=limit)

    if not resp.success:
        raise HTTPException(status_code=503, detail=resp.error)

    tasks = []
    data = resp.data
    if isinstance(data, dict) and "tasks" in data:
        for task in data["tasks"]:
            tasks.append(TaskInfo(
                task_id=task.get("task_id", ""),
                func_name=task.get("func_name", "Unknown"),
                state=task.get("state", "NIL"),
                node_ip_address=task.get("node_ip_address"),
                actor_id=task.get("actor_id"),
                submitted_at=task.get("submitted_ts"),
            ))

    return tasks


@router.get("/jobs")
async def list_jobs():
    """获取 Job 列表"""
    client = get_ray_client()
    resp = await asyncio.to_thread(client.list_jobs)

    if not resp.success:
        raise HTTPException(status_code=503, detail=resp.error)

    return resp.data


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """健康检查端点

    检查 Ray Dashboard 连接状态、熔断器状态、缓存状态。
    用于负载均衡器和监控系统的健康探测。
    """
    import asyncio
    client = get_ray_client()

    # 并行检查
    async def check_all():
        health_task = asyncio.to_thread(client.health_check)
        cluster_task = asyncio.to_thread(client.get_cluster_status)

        return await asyncio.gather(
            health_task, cluster_task,
            return_exceptions=True
        )

    health_resp, cluster_resp = await check_all()

    # 确定健康状态
    if isinstance(health_resp, Exception):
        status = "unhealthy"
    elif isinstance(cluster_resp, Exception):
        status = "degraded"
    elif health_resp.success and cluster_resp.success:
        status = "healthy"
    else:
        status = "degraded"

    return HealthCheckResponse(
        status=status,
        ray_dashboard=health_resp.success if not isinstance(health_resp, Exception) else False,
        gcs=cluster_resp.success if not isinstance(cluster_resp, Exception) else False,
        circuit_breaker=client.get_circuit_state(),
        cache_stats=client.get_cache_stats()
    )


@router.post("/cache/invalidate")
async def invalidate_cache(endpoint: Optional[str] = None):
    """手动清除缓存

    Args:
        endpoint: 可选，指定要清除的端点缓存
    """
    client = get_ray_client()
    client.invalidate_cache(endpoint)
    return {"message": "Cache invalidated", "endpoint": endpoint}


@router.get("/circuit-breaker")
async def get_circuit_breaker_status():
    """获取熔断器状态

    用于调试和监控熔断器工作状态。
    """
    client = get_ray_client()
    return {
        "state": client.get_circuit_state(),
        "cache_stats": client.get_cache_stats()
    }


# ==================== SSE Endpoint ====================

@router.get("/events")
async def cluster_events():
    """SSE 实时事件流端点

    提供 Ray 集群的实时事件推送。
    注意: 当前实现需要 sse-starlette 包。
    如未安装，将返回 501 错误。
    """
    try:
        from sse_starlette.sse import EventSourceResponse
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="SSE not available. Please install sse-starlette: pip install sse-starlette"
        )

    async def ray_event_generator():
        """Ray 集群事件流生成器"""
        import asyncio
        import ray.util.state as state_api

        client = get_ray_client()
        last_event_id = 0

        while True:
            try:
                # 获取 Ray 事件（通过 StateAPIClient）
                # 注意：需要 Ray 2.54+ 的 State API 支持
                try:
                    events = state_api.list_events(
                        limit=100,
                        filters={"timestamp": {"gt": last_event_id}}
                    )

                    for event in events:
                        last_event_id = event.get("timestamp", 0)
                        yield {
                            "event": event.get("type", "message"),
                            "data": event
                        }
                except Exception as e:
                    logger.warning(f"Failed to fetch Ray events: {e}")

                # 获取集群状态变化
                status = client.get_cluster_status()
                if status.success:
                    yield {
                        "event": "cluster_status",
                        "data": status.data
                    }

                # 获取 Actor 变化
                actors = client.list_actors(limit=10)
                if actors.success:
                    yield {
                        "event": "actors_update",
                        "data": actors.data
                    }

            except Exception as e:
                yield {
                    "event": "error",
                    "data": {"message": str(e)}
                }

            # 推送间隔（可配置）
            await asyncio.sleep(2)

    return EventSourceResponse(ray_event_generator())


# Add asyncio import at module level
import asyncio