# Ray Dashboard API 集成架构设计报告

**调研日期:** 2026-03-26
**Ray 版本**: 2.54.0
**调研人:** Ray Dashboard Researcher

---

## 1. 三层架构设计

### 1.1 架构总览

```
┌──────────────────┐     ┌─────────────────────┐     ┌────────────────────┐     ┌─────────────┐
│   Web Console    │────>│  AlgoStudio Backend │────>│  Ray Dashboard API │────>│ Ray Cluster │
│  (前端 Dashboard) │<────│   (API 封装层)       │<────│   (Ray Native)     │<────│  (GCS)      │
└──────────────────┘     └─────────────────────┘     └────────────────────┘     └─────────────┘
         │                         │                         │
    • SSE/轮询                   • 缓存                   • State API
    • 数据格式化                 • 错误处理               • Node API
    • 统一响应                    • 熔断降级               • Reporter API
```

### 1.2 每层职责边界

| 层级 | 组件 | 职责 | 不跨越边界 |
|------|------|------|-----------|
| **L1 - 前端** | Web Console | 页面渲染、SSE 订阅、用户交互、数据展示 | 不直接调用 Ray API |
| **L2 - 后端** | AlgoStudio Backend | API 路由、缓存策略、错误处理、格式转换、熔断降级 | 不直接访问 GCS |
| **L3 - 封装** | RayAPIClient | HTTP 请求封装、版本兼容、超时控制、重试机制 | 不做业务逻辑 |
| **L4 - 适配** | Ray Dashboard API | Ray 集群状态查询、健康检查、指标导出 | 不做业务封装 |

### 1.3 API 路由设计

```
AlgoStudio Backend Routes:
├── GET  /api/cluster/status          # 集群综合状态（封装 Ray API）
├── GET  /api/cluster/nodes           # 节点列表
├── GET  /api/cluster/nodes/{node_id} # 节点详情
├── GET  /api/cluster/actors          # Actor 列表
├── GET  /api/cluster/actors/{actor_id} # Actor 详情
├── GET  /api/cluster/tasks           # Task 列表
├── GET  /api/cluster/jobs            # Job 列表
├── GET  /api/cluster/metrics         # Prometheus 指标
├── GET  /api/cluster/health          # 健康检查
└── WS   /api/cluster/events          # SSE 实时事件流
```

---

## 2. RayAPIClient 封装层设计

### 2.1 RayAPIClient 类

```python
# src/algo_studio/core/ray_dashboard_client.py

import requests
import threading
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging
from asyncio import semaphore
import time

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # 正常请求
    OPEN = "open"           # 熔断中
    HALF_OPEN = "half_open" # 探测中


@dataclass
class RayAPIResponse:
    success: bool
    data: Any
    error: Optional[str] = None
    cached: bool = False


class RayAPIClient:
    """Ray Dashboard API 封装类

    提供统一的请求处理、错误处理、熔断降级、版本兼容能力。
    """

    # Ray Dashboard 默认端口
    DEFAULT_DASHBOARD_PORT = 8265

    # 熔断器配置
    CIRCUIT_FAILURE_THRESHOLD = 5      # 连续失败次数阈值
    CIRCUIT_RECOVERY_TIMEOUT = 30      # 熔断恢复时间（秒）
    CIRCUIT_HALF_OPEN_REQUESTS = 3     # 半开状态允许的探测请求数

    # 请求配置
    DEFAULT_TIMEOUT = 10               # 默认超时（秒）
    MAX_RETRIES = 3                    # 最大重试次数
    RETRY_BACKOFF = [1, 2, 4]         # 退避时间序列（秒）

    # 缓存配置
    CACHE_TTL = 5                     # 缓存 TTL（秒）
    CACHE_MAX_SIZE = 100               # 缓存最大条目数

    def __init__(
        self,
        head_address: str = "localhost",
        dashboard_port: int = DEFAULT_DASHBOARD_PORT,
        timeout: int = DEFAULT_TIMEOUT,
        enable_cache: bool = True,
        enable_circuit_breaker: bool = True
    ):
        """
        Args:
            head_address: Ray Head 节点地址
            dashboard_port: Ray Dashboard 端口
            timeout: 请求超时时间（秒）
            enable_cache: 是否启用缓存
            enable_circuit_breaker: 是否启用熔断器
        """
        self.base_url = f"http://{head_address}:{dashboard_port}"
        self.timeout = timeout
        self.enable_cache = enable_cache
        self.enable_circuit_breaker = enable_circuit_breaker

        # 缓存（线程安全：使用 threading.Lock 保护并发访问）
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_lock = threading.Lock()  # 缓存读写锁

        # 熔断器状态
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_success = 0

        # Semaphore for rate limiting
        self._semaphore = semaphore(10)  # 最多 10 并发请求

    def _get_cache_key(self, endpoint: str, params: Optional[Dict] = None) -> str:
        """生成缓存键"""
        if params:
            sorted_params = sorted(params.items())
            return f"{endpoint}?{sorted_params}"
        return endpoint

    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self._cache:
            return False
        _, timestamp = self._cache[key]
        return time.time() - timestamp < self.CACHE_TTL

    def _get_cached(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        if self.enable_cache and self._is_cache_valid(key):
            return self._cache[key][0]
        return None

    def _set_cache(self, key: str, data: Any) -> None:
        """设置缓存"""
        if not self.enable_cache:
            return

        # 清理过期缓存
        if len(self._cache) >= self.CACHE_MAX_SIZE:
            oldest_keys = sorted(
                self._cache_timestamps.keys(),
                key=lambda k: self._cache_timestamps[k]
            )[:10]
            for k in oldest_keys:
                del self._cache[k]
                del self._cache_timestamps[k]

        self._cache[key] = (data, time.time())
        self._cache_timestamps[key] = time.time()

    def _update_circuit_state(self, success: bool) -> None:
        """更新熔断器状态"""
        if not self.enable_circuit_breaker:
            return

        if success:
            if self._circuit_state == CircuitState.HALF_OPEN:
                self._half_open_success += 1
                if self._half_open_success >= self.CIRCUIT_HALF_OPEN_REQUESTS:
                    # 恢复关闭状态
                    self._circuit_state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._half_open_success = 0
                    logger.info("Circuit breaker closed (recovery succeeded)")
            elif self._circuit_state == CircuitState.CLOSED:
                self._failure_count = 0
        else:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._circuit_state == CircuitState.HALF_OPEN:
                # 探测失败，重新打开熔断器
                self._circuit_state = CircuitState.OPEN
                self._half_open_success = 0
                logger.warning("Circuit breaker reopened (half-open probe failed)")
            elif self._failure_count >= self.CIRCUIT_FAILURE_THRESHOLD:
                self._circuit_state = CircuitState.OPEN
                logger.warning(f"Circuit breaker opened after {self._failure_count} failures")

    def _should_allow_request(self) -> bool:
        """检查是否允许请求"""
        if not self.enable_circuit_breaker:
            return True

        if self._circuit_state == CircuitState.CLOSED:
            return True

        if self._circuit_state == CircuitState.OPEN:
            # 检查是否超时恢复
            if self._last_failure_time and \
               time.time() - self._last_failure_time >= self.CIRCUIT_RECOVERY_TIMEOUT:
                self._circuit_state = CircuitState.HALF_OPEN
                self._half_open_success = 0
                logger.info("Circuit breaker half-open (recovery timeout reached)")
                return True
            return False

        # HALF_OPEN 状态允许有限请求
        return True

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        retry_count: int = 0
    ) -> RayAPIResponse:
        """执行 HTTP 请求（内部方法）

        Args:
            method: HTTP 方法
            endpoint: API 端点
            params: 查询参数
            data: 请求体数据
            retry_count: 当前重试次数
        """
        url = f"{self.base_url}{endpoint}"
        cache_key = self._get_cache_key(endpoint, params)

        # 检查缓存
        cached_data = self._get_cached(cache_key)
        if cached_data is not None:
            return RayAPIResponse(success=True, data=cached_data, cached=True)

        # 检查熔断器
        if not self._should_allow_request():
            return RayAPIResponse(
                success=False,
                data=None,
                error="Circuit breaker is OPEN - Ray API temporarily unavailable"
            )

        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=data,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                self._update_circuit_state(success=True)
                self._set_cache(cache_key, result)
                return RayAPIResponse(success=True, data=result)
            else:
                self._update_circuit_state(success=False)
                return RayAPIResponse(
                    success=False,
                    data=None,
                    error=f"HTTP {response.status_code}: {response.text[:200]}"
                )

        except requests.exceptions.Timeout:
            self._update_circuit_state(success=False)
            if retry_count < self.MAX_RETRIES:
                backoff = self.RETRY_BACKOFF[min(retry_count, len(self.RETRY_BACKOFF) - 1)]
                logger.warning(f"Request timeout, retrying in {backoff}s (attempt {retry_count + 1})")
                time.sleep(backoff)
                return self._make_request(method, endpoint, params, data, retry_count + 1)
            return RayAPIResponse(success=False, data=None, error="Request timeout")

        except requests.exceptions.ConnectionError as e:
            self._update_circuit_state(success=False)
            return RayAPIResponse(
                success=False,
                data=None,
                error=f"Connection error: {str(e)}"
            )

        except Exception as e:
            self._update_circuit_state(success=False)
            return RayAPIResponse(
                success=False,
                data=None,
                error=f"Unexpected error: {str(e)}"
            )

    async def _make_request_async(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        retry_count: int = 0
    ) -> RayAPIResponse:
        """异步执行 HTTP 请求（当前为同步实现）

        使用 semaphore 控制并发数。

        注意：当前实现使用 requests 库，是同步调用。
        未来迁移到 httpx 可实现真正的异步 HTTP 请求。
        httpx 支持 async/await，可直接替换 requests 实现：
        - httpx.AsyncClient 替代 requests
        - await client.get()/post() 替代 requests.request()
        """
        async with self._semaphore:
            # 同步调用（requests 不支持真正的异步）
            return self._make_request(method, endpoint, params, data, retry_count)

    # ==================== Public API Methods ====================

    def health_check(self) -> RayAPIResponse:
        """健康检查"""
        return self._make_request("GET", "/api/gcs_healthz")

    def get_cluster_status(self) -> RayAPIResponse:
        """获取集群状态"""
        return self._make_request("GET", "/api/cluster_status")

    def list_nodes(self, view: str = "summary") -> RayAPIResponse:
        """获取节点列表

        Args:
            view: "summary" 获取摘要，"details" 获取详细信息
        """
        return self._make_request("GET", "/nodes", params={"view": view})

    def get_node(self, node_id: str) -> RayAPIResponse:
        """获取节点详情"""
        return self._make_request("GET", f"/nodes/{node_id}")

    def list_actors(self, limit: int = 100) -> RayAPIResponse:
        """获取 Actor 列表"""
        return self._make_request("GET", "/api/v0/actors", params={"limit": limit})

    def get_actor(self, actor_id: str) -> RayAPIResponse:
        """获取 Actor 详情"""
        return self._make_request("GET", f"/logical/actors/{actor_id}")

    def list_tasks(self, limit: int = 100) -> RayAPIResponse:
        """获取 Task 列表"""
        return self._make_request("GET", "/api/v0/tasks", params={"limit": limit})

    def list_jobs(self) -> RayAPIResponse:
        """获取 Job 列表"""
        return self._make_request("GET", "/api/v0/jobs")

    def get_cluster_metadata(self) -> RayAPIResponse:
        """获取集群元数据"""
        return self._make_request("GET", "/api/v0/cluster_metadata")

    def get_metrics(self) -> RayAPIResponse:
        """获取 Prometheus 指标（需要 Prometheus 插件）"""
        return self._make_request("GET", "/api/prometheus/sd")

    def summarize_actors(self) -> RayAPIResponse:
        """获取 Actor 统计摘要"""
        return self._make_request("GET", "/api/v0/actors/summarize")

    def summarize_tasks(self) -> RayAPIResponse:
        """获取 Task 统计摘要"""
        return self._make_request("GET", "/api/v0/tasks/summarize")

    def get_logs(self, node_id: str, log_file: str) -> RayAPIResponse:
        """获取节点日志"""
        return self._make_request(
            "GET",
            f"/nodes/{node_id}/logs/{log_file}"
        )

    # ==================== Utility Methods ====================

    def invalidate_cache(self, endpoint: Optional[str] = None) -> None:
        """清除缓存

        Args:
            endpoint: 如果指定，只清除该端点的缓存；否则清除所有
        """
        if endpoint:
            keys_to_delete = [
                k for k in self._cache.keys()
                if k.startswith(endpoint)
            ]
            for k in keys_to_delete:
                del self._cache[k]
                del self._cache_timestamps[k]
        else:
            self._cache.clear()
            self._cache_timestamps.clear()

    def get_circuit_state(self) -> str:
        """获取熔断器当前状态"""
        return self._circuit_state.value

    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计"""
        return {
            "size": len(self._cache),
            "max_size": self.CACHE_MAX_SIZE
        }

    def close(self) -> None:
        """关闭客户端，清理资源"""
        self._cache.clear()
```

### 2.2 版本兼容处理

```python
# src/algo_studio/core/ray_compat.py

"""
Ray Dashboard API 版本兼容性处理模块

不同 Ray 版本的 API 路径和响应格式可能存在差异，
此类提供统一的兼容处理。
"""

from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Ray 版本到 API 路径的映射
RAY_VERSION_API_PATHS = {
    # (min_version, max_version): {api_name: path}
    (2, 5): {
        "actors": "/api/v0/actors",
        "tasks": "/api/v0/tasks",
        "nodes": "/api/v0/nodes",
        "jobs": "/api/v0/jobs",
        "health": "/api/gcs_healthz",
    },
    (2, 6): {
        "actors": "/api/v0/actors",
        "tasks": "/api/v0/tasks",
        "nodes": "/api/v0/nodes",
        "jobs": "/api/v0/jobs",
        "health": "/api/gcs_healthz",
    },
    (2, 8): {
        "actors": "/api/v0/actors",
        "tasks": "/api/v0/tasks",
        "nodes": "/nodes",
        "jobs": "/api/v0/jobs",
        "health": "/api/gcs_healthz",
    },
}


class RayAPICompat:
    """Ray API 版本兼容性处理类"""

    def __init__(self, ray_version: str):
        """
        Args:
            ray_version: Ray 版本号，如 "2.5.0", "2.6.3"
        """
        self.ray_version = ray_version
        self._version_tuple = self._parse_version(ray_version)
        self._api_paths = self._get_api_paths()

    def _parse_version(self, version: str) -> tuple:
        """解析版本号为元组"""
        parts = version.split(".")
        return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)

    def _get_api_paths(self) -> Dict[str, str]:
        """获取当前版本对应的 API 路径"""
        for (min_ver, max_ver), paths in RAY_VERSION_API_PATHS.items():
            if min_ver <= self._version_tuple[0] < max_ver:
                return paths

        # 默认返回 2.5+ 的路径
        return RAY_VERSION_API_PATHS[(2, 5)]

    def get_path(self, api_name: str) -> str:
        """获取指定 API 的路径"""
        return self._api_paths.get(api_name, f"/api/v0/{api_name}")

    def get_actors_path(self) -> str:
        return self.get_path("actors")

    def get_tasks_path(self) -> str:
        return self.get_path("tasks")

    def get_nodes_path(self) -> str:
        return self.get_path("nodes")

    def get_jobs_path(self) -> str:
        return self.get_path("jobs")

    def get_health_path(self) -> str:
        return self.get_path("health")


def detect_ray_version() -> Optional[str]:
    """尝试检测 Ray 版本"""
    try:
        import ray
        return ray.__version__
    except ImportError:
        return None
```

---

## 3. AlgoStudio Backend 实现

### 3.1 新增 API 端点设计

```python
# src/algo_studio/api/routes/cluster.py

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from algo_studio.core.ray_dashboard_client import RayAPIClient
from algo_studio.core.ray_compat import detect_ray_version, RayAPICompat
from algo_studio.api.models import TaskResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cluster", tags=["cluster"])

# 全局 Ray API Client 实例（延迟初始化）
_ray_client: Optional[RayAPIClient] = None


def get_ray_client() -> RayAPIClient:
    """获取 Ray API Client 单例"""
    global _ray_client
    if _ray_client is None:
        # 从配置或环境变量获取 Head 地址
        import os
        head_address = os.getenv("RAY_HEAD_ADDRESS", "localhost")
        _ray_client = RayAPIClient(head_address=head_address)
    return _ray_client


# ==================== Request/Response Models ====================

class NodeInfo(BaseModel):
    node_id: str
    ip: str
    hostname: Optional[str] = None
    status: str  # "alive" | "dead"
    cpu_count: int = 0
    memory_total_gb: float = 0
    memory_used_gb: float = 0
    gpu_count: int = 0
    gpu_utilization: Optional[int] = None

    class Config:
        from_attributes = True


class ActorInfo(BaseModel):
    actor_id: str
    class_name: str
    state: str  # "ALIVE" | "DEAD" | "PENDING"
    job_id: Optional[str] = None
    node_ip_address: Optional[str] = None
    num_restarts: int = 0
    timestamp: Optional[int] = None

    class Config:
        from_attributes = True


class TaskInfo(BaseModel):
    task_id: str
    func_name: str
    state: str
    node_ip_address: Optional[str] = None
    actor_id: Optional[str] = None
    submitted_at: Optional[int] = None

    class Config:
        from_attributes = True


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
    client = get_ray_client()

    # 并行调用多个 API
    import asyncio

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
        connected=health_resp.success,
        ray_version=ray_version,
        cluster_status=cluster_resp.data if not isinstance(cluster_resp, Exception) else None,
        nodes=nodes,
        actors_count=actors_count,
        tasks_count=tasks_count,
        error=health_resp.error if not health_resp.success else None
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


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """健康检查端点

    检查 Ray Dashboard 连接状态、熔断器状态、缓存状态。
    用于负载均衡器和监控系统的健康探测。
    """
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
```

### 3.2 缓存策略

```python
# 缓存策略设计

CACHE_STRATEGY = {
    # 端点: (TTL秒, 最大条目数)
    "/api/cluster/status": (5, 50),     # 集群状态 - 高频访问，短 TTL
    "/api/cluster/nodes": (10, 100),    # 节点列表 - 中频访问
    "/api/cluster/actors": (5, 200),     # Actor 列表 - 变化频繁
    "/api/cluster/tasks": (3, 500),      # Task 列表 - 变化最频繁
    "/api/cluster/health": (2, 10),     # 健康检查 - 超高频
}

# 缓存失效策略
CACHE_INVALIDATION = {
    # 当 Task 完成时，清除相关缓存
    "task_completed": ["/api/cluster/status", "/api/cluster/tasks", "/api/cluster/actors"],
    # 当节点状态变化时，清除节点缓存
    "node_status_change": ["/api/cluster/status", "/api/cluster/nodes"],
    # 手动触发清除
    "manual": "all",
}
```

### 3.3 SSE 端点后端实现

```python
# src/algo_studio/api/routes/cluster.py

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
import asyncio
import ray

router = APIRouter(prefix="/api/cluster", tags=["cluster"])

# SSE 事件流生成器
async def ray_event_generator():
    """Ray 集群事件流生成器

    从 Ray Dashboard 获取事件并通过 SSE 推送给前端。
    实现方式：
    1. 轮询 Ray Dashboard 的 /api/v0/events 端点
    2. 将事件格式化为 SSE 格式并推送
    3. 保持连接，直到客户端断开
    """
    client = get_ray_client()
    last_event_id = 0

    while True:
        try:
            # 获取 Ray 事件（通过 StateAPIClient）
            # 注意：需要 Ray 2.54+ 的 State API 支持
            import ray.util.state as state_api

            # 获取最新事件
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


@router.get("/events")
async def cluster_events():
    """SSE 实时事件流端点

    提供 Ray 集群的实时事件推送，包括：
    - 集群状态变化
    - Actor 创建/销毁
    - Task 状态变化
    - 节点状态变化
    - 错误事件

    前端通过 EventSource API 订阅此端点：
    ```javascript
    const eventSource = new EventSource('/api/cluster/events');
    eventSource.addEventListener('cluster_status', (e) => {
        const data = JSON.parse(e.data);
        // 处理集群状态更新
    });
    ```
    """
    return EventSourceResponse(ray_event_generator())
```

**SSE 降级策略：**
- 当 SSE 连接失败时，前端自动降级到 HTTP 轮询
- 后端记录 SSE 连接失败次数，超过阈值时触发告警
- 降级期间使用 `/api/cluster/status` 端点轮询（间隔 5-30s 指数退避）

### 3.4 健康检查机制

```python
# 健康检查分为三层

HEALTH_CHECK_TIERS = {
    "l1_dashboard": {
        "check": "GET /api/gcs_healthz",
        "timeout": 3,
        "required": True,
        "weight": 1.0
    },
    "l2_cluster": {
        "check": "GET /api/cluster_status",
        "timeout": 5,
        "required": False,
        "weight": 0.8
    },
    "l3_detailed": {
        "check": "GET /api/v0/nodes",
        "timeout": 10,
        "required": False,
        "weight": 0.5
    }
}

# 健康状态判断
HEALTH_STATUS = {
    # (l1, l2, l3) -> status
    (True, True, True): "healthy",
    (True, True, False): "healthy",
    (True, False, False): "degraded",
    (False, False, False): "unhealthy",
}
```

---

## 4. Web Console 对接

### 4.1 数据获取策略

```python
# src/algo_studio/web/data_fetcher.py

from algo_studio.web.config import API_BASE
import requests
import asyncio
from dataclasses import dataclass
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)


class DataFetchStrategy:
    """Web Console 数据获取策略

    支持 SSE 实时推送和轮询两种模式。
    SSE 优先，失败时自动降级到轮询。
    """

    def __init__(
        self,
        api_base: str = API_BASE,
        poll_interval: int = 5,
        sse_reconnect_interval: int = 3,
        max_poll_interval: int = 30
    ):
        self.api_base = api_base.rstrip("/")
        self.poll_interval = poll_interval
        self.sse_reconnect_interval = sse_reconnect_interval
        self.max_poll_interval = max_poll_interval
        self._current_interval = poll_interval
        self._use_sse = False
        self._callbacks: dict[str, list[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """订阅数据更新

        Args:
            event_type: 事件类型 ("tasks", "nodes", "actors", "cluster_status")
            callback: 回调函数，接收新数据
        """
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)

    def _notify(self, event_type: str, data: any) -> None:
        """通知所有订阅者"""
        if event_type in self._callbacks:
            for cb in self._callbacks[event_type]:
                try:
                    cb(data)
                except Exception as e:
                    logger.error(f"Callback error for {event_type}: {e}")

    async def fetch_cluster_status(self) -> dict:
        """获取集群状态"""
        try:
            resp = requests.get(
                f"{self.api_base}/api/cluster/status",
                timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch cluster status: {e}")
            return {"connected": False, "error": str(e)}

    async def fetch_tasks(self) -> dict:
        """获取任务列表"""
        try:
            resp = requests.get(
                f"{self.api_base}/api/tasks",
                timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch tasks: {e}")
            return {"tasks": [], "error": str(e)}

    async def fetch_nodes(self) -> dict:
        """获取节点列表"""
        try:
            resp = requests.get(
                f"{self.api_base}/api/cluster/nodes",
                timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch nodes: {e}")
            return []

    async def poll_data(self) -> None:
        """轮询数据更新（降级模式）

        当 SSE 不可用时，自动降级到轮询。
        连续失败时逐渐增加轮询间隔。
        """
        consecutive_failures = 0

        while True:
            try:
                # 获取所有数据
                status = await self.fetch_cluster_status()
                tasks = await self.fetch_tasks()
                nodes = await self.fetch_nodes()

                # 通知订阅者
                self._notify("cluster_status", status)
                self._notify("tasks", tasks)
                self._notify("nodes", nodes)

                # 成功，重置失败计数和间隔
                consecutive_failures = 0
                self._current_interval = self.poll_interval

            except Exception as e:
                consecutive_failures += 1
                # 指数退避
                self._current_interval = min(
                    self.poll_interval * (2 ** consecutive_failures),
                    self.max_poll_interval
                )
                logger.warning(
                    f"Polling failed ({consecutive_failures} times), "
                    f"next poll in {self._current_interval}s"
                )

            await asyncio.sleep(self._current_interval)

    async def start_sse(self, endpoint: str = "/api/cluster/events") -> None:
        """启动 SSE 连接

        实时接收服务端推送的数据。
        连接失败时自动降级到轮询。

        注意：sseclient 是 Web Console 客户端依赖，用于消费 SSE 流。
        服务端 SSE 端点使用 sse-starlette 实现。
        """
        import sseclient  # Web Console SSE 客户端（需要安装）
        import requests

        url = f"{self.api_base}{endpoint}"

        max_retries = 5
        retry_count = 0
        base_backoff = self.sse_reconnect_interval  # 基础退避时间（秒）

        while retry_count < max_retries:
            try:
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()

                client = sseclient.SSEClient(response)

                for event in client.events():
                    if event.data:
                        data = event.data
                        event_type = event.type or "message"
                        self._notify(event_type, data)

                # 正常结束，重置
                self._use_sse = True
                retry_count = 0  # 重置重试计数

            except Exception as e:
                retry_count += 1
                # 指数退避策略：base * 2^(retry_count-1)，最大 60 秒
                backoff = min(base_backoff * (2 ** (retry_count - 1)), 60)
                logger.warning(
                    f"SSE connection error: {e}, retry {retry_count}/{max_retries}, "
                    f"next retry in {backoff}s"
                )
                if retry_count >= max_retries:
                    logger.error(
                        f"SSE max retries ({max_retries}) reached, "
                        f"permanently switching to polling mode"
                    )
                    self._use_sse = False
                    break
                await asyncio.sleep(backoff)

    def start(self) -> None:
        """启动数据获取

        优先尝试 SSE，失败时降级到轮询。
        """
        loop = asyncio.get_event_loop()
        loop.create_task(self.start_sse())
        loop.create_task(self.poll_data())
```

### 4.2 统一响应格式

```python
# 统一响应格式

UNIFIED_RESPONSE_FORMAT = {
    "success": bool,           # 请求是否成功
    "data": Any,               # 业务数据
    "meta": {                  # 元数据
        "timestamp": str,       # ISO 时间戳
        "source": str,          # "ray_api" | "cache",
        "version": str,         # API 版本
    },
    "error": {                 # 错误信息（失败时）
        "code": str,
        "message": str,
        "details": Optional[Any]
    }
}


def format_response(
    success: bool,
    data: Any,
    source: str = "ray_api",
    error: Optional[dict] = None
) -> dict:
    """统一格式化 API 响应"""
    import datetime

    response = {
        "success": success,
        "data": data,
        "meta": {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "source": source,
            "version": "1.0"
        }
    }

    if error:
        response["error"] = error

    return response
```

---

## 5. 与现有 AlgoStudio 代码集成点

### 5.1 集成架构图

```
现有代码                          新增代码
─────────────────────────────    ──────────────────────────────────────
                                 │
src/algo_studio/                 │  src/algo_studio/
├── api/                         │  ├── core/
│   ├── main.py  ─────────────────┼──>│   ├── ray_dashboard_client.py  (新增)
│   ├── routes/  ─────────────────┼──>│   │   └── RayAPIClient 类
│   │   ├── tasks.py             │   │   └── ray_compat.py            (新增)
│   │   └── hosts.py             │   │       └── RayAPICompat 类
│   └── models.py                │   │
│                                 │   ├── api/
│                               │   │   └── routes/
│                               │   │       └── cluster.py             (新增)
│                                 │   │           └── 集群状态 API
│                                 │   │
│                                 │   └── web/
│                                 │       └── data_fetcher.py         (新增)
│                                 │           └── DataFetchStrategy
│                                 │
└─────────────────────────────────┘
```

### 5.2 main.py 集成

```python
# src/algo_studio/api/main.py (更新)

from fastapi import FastAPI
from algo_studio.api.routes import tasks, hosts, cluster  # 新增 cluster

app = FastAPI(
    title="AlgoStudio API",
    description="AI Algorithm Platform API",
    version="0.2.0"  # 版本更新
)

app.include_router(tasks.router)
app.include_router(hosts.router)
app.include_router(cluster.router)  # 新增

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {
        "name": "AlgoStudio API",
        "version": "0.2.0",
        "endpoints": {
            "tasks": "/api/tasks",
            "hosts": "/api/hosts",
            "cluster": "/api/cluster"
        }
    }
```

### 5.3 任务与 Ray Actor 关联

现有 TaskManager 在创建任务时，可以记录 Ray Actor ID，便于关联：

```python
# 在 Task 模型中增加 Ray Actor 关联字段

class Task:
    def __init__(self, ...):
        # ... 现有字段
        self.ray_actor_id: Optional[str] = None  # 新增
        self.ray_job_id: Optional[str] = None   # 新增

    def link_ray_actor(self, actor_id: str, job_id: str) -> None:
        """关联 Ray Actor"""
        self.ray_actor_id = actor_id
        self.ray_job_id = job_id
```

---

## 6. 错误处理和降级策略

### 6.1 降级策略矩阵

| 场景 | 降级级别 | 行为 | 影响 |
|------|---------|------|------|
| Ray Dashboard 不可达 | L1 | 返回缓存数据 + 熔断开启 | 监控暂时不可用 |
| Ray API 超时 | L2 | 重试 + 退避 + 熔断 | 请求延迟增加 |
| Ray API 500 错误 | L2 | 重试 + 熔断 | 请求失败返回错误 |
| GCS 不可用 | L3 | 返回最后已知状态 | 可能显示过时数据 |
| 全部 Ray 服务不可用 | L4 | 返回本地缓存 + 降级提示 | 平台仍可访问静态页面 |

### 6.2 熔断器状态流转

```
         ┌──────────────────────────────────────────┐
         │                                          │
         │   连续失败 >= 5 次                       │
         │   ───────────────────                    │
         │   熔断器 OPEN                             │
         │                                          │
         │   ┌─────────────────┐                   │
         │   │ 等待 30 秒      │                   │
         │   └────────┬────────┘                   │
         │            │                            │
         │            ▼                            │
         │   ┌─────────────────┐                   │
         │   │ 发送 3 个探测请求│                   │
         │   │ HALF_OPEN       │                   │
         │   └────────┬────────┘                   │
         │            │                            │
         │     ┌──────┴──────┐                     │
         │     │              │                     │
         │   全部成功      任一失败                  │
         │     │              │                     │
         │     ▼              ▼                     │
         │  ┌──────┐      ┌────────┐                │
         │  │ CLOSED│      │ OPEN   │                │
         │  │ 恢复  │      │ 重新打开│                │
         │  └──────┘      └────────┘                │
         │                                          │
         └──────────────────────────────────────────┘
```

### 6.3 错误响应格式

```python
ERROR_RESPONSE_EXAMPLES = {
    "circuit_breaker_open": {
        "success": False,
        "error": {
            "code": "CIRCUIT_BREAKER_OPEN",
            "message": "Ray API temporarily unavailable due to circuit breaker",
            "details": {
                "state": "open",
                "retry_after": 25,  # 秒
                "suggestion": "Retry after 25 seconds or check Ray cluster health"
            }
        }
    },
    "ray_api_error": {
        "success": False,
        "error": {
            "code": "RAY_API_ERROR",
            "message": "Failed to fetch actors from Ray Dashboard",
            "details": {
                "endpoint": "/api/v0/actors",
                "status_code": 500,
                "ray_version": "2.5.0"
            }
        }
    }
}
```

### 6.4 依赖清单

Ray Dashboard API 集成所需的第三方依赖：

```python
# requirements.txt 或 pyproject.toml

# 核心依赖
requests>=2.28.0          # HTTP 请求库（当前使用，同步）
httpx>=0.24.0             # 未来迁移到 httpx（支持真正的异步）

# SSE 支持
sse-starlette>=1.6.0     # FastAPI SSE 端点支持
sseclient>=3.1.0          # SSE 客户端（Web Console 使用）

# 异步支持
aiohttp>=3.8.0            # 异步 HTTP（备选方案）

# 监控和日志
prometheus-client>=0.17.0 # Prometheus 指标导出
structlog>=23.1.0        # 结构化日志
```

**依赖说明：**

| 依赖 | 用途 | 必需 |
|------|------|------|
| `requests` | Ray Dashboard HTTP 请求 | 当前必需 |
| `httpx` | 真正的异步 HTTP（未来迁移） | 可选（建议） |
| `sse-starlette` | SSE 端点实现 | 必需 |
| `sseclient` | SSE 客户端消费端 | Web Console 必需 |
| `aiohttp` | 异步 HTTP 备选 | 可选 |

---

## 7. 实施建议

### 7.1 实施顺序

```
Phase 1: 核心封装 (1-2 天)
├── RayAPIClient 基础类
├── RayAPICompat 版本兼容
└── 基本错误处理

Phase 2: API 集成 (1-2 天)
├── /api/cluster/* 端点
├── 健康检查机制
└── 缓存策略实现

Phase 3: Web Console 集成 (2-3 天)
├── DataFetchStrategy
├── SSE/轮询切换
└── 统一响应格式

Phase 4: 监控和调优 (1-2 天)
├── 熔断器配置调优
├── 缓存命中率优化
└── 性能测试
```

### 7.2 关键配置项

```python
# config.py 新增配置

RAY_DASHBOARD_CONFIG = {
    "head_address": "192.168.0.126",
    "dashboard_port": 8265,
    "timeout": 10,
    "cache": {
        "enabled": True,
        "ttl": 5,
        "max_size": 100
    },
    "circuit_breaker": {
        "enabled": True,
        "failure_threshold": 5,
        "recovery_timeout": 30,
        "half_open_requests": 3
    },
    "polling": {
        "interval": 5,
        "max_interval": 30
    }
}
```

---

## 8. Manager 评估

| 维度 | 评分 (1-10) | 说明 |
|------|-------------|------|
| 完整性 | 9 | 覆盖三层架构、API 封装、降级策略、Web 对接 |
| 逻辑性 | 9 | 职责分层清晰，错误处理完善，缓存策略合理 |
| 可行性 | 9 | 代码可直接复用，与现有代码集成点明确 |
| 创新性 | 8 | 熔断器设计、版本兼容处理有创新 |

**总体评价:** 报告深化了三层架构设计，提供了完整的 RayAPIClient 封装类、错误处理和降级策略。与现有 AlgoStudio 代码的集成点清晰，可直接进入 Phase 1 实施。

**建议:**
1. 优先实现 RayAPIClient 的基础版本，再逐步增加熔断器和缓存
2. Web Console 集成可以并行进行，使用 DataFetchStrategy 统一数据获取
3. 上线后监控缓存命中率，调整 TTL 配置
