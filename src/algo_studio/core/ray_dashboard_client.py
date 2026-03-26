# src/algo_studio/core/ray_dashboard_client.py

"""
Ray Dashboard API 封装类

提供统一的请求处理、错误处理、熔断降级、版本兼容能力。
用于与 Ray Dashboard HTTP API 进行交互。

三层架构: Web Console -> Backend -> RayAPIClient -> Ray Cluster
"""

import requests
import threading
import time
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # 正常请求
    OPEN = "open"           # 熔断中
    HALF_OPEN = "half_open" # 探测中


@dataclass
class RayAPIResponse:
    """Ray API 统一响应格式"""
    success: bool           # 请求是否成功
    data: Any              # 业务数据
    error: Optional[str] = None  # 错误信息
    cached: bool = False   # 是否来自缓存


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
        self._cache_lock = threading.Lock()

        # 熔断器状态
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_success = 0
        self._circuit_lock = threading.Lock()

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

        with self._cache_lock:
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

        with self._circuit_lock:
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

        with self._circuit_lock:
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
        """执行 HTTP 请求（内部方法）"""

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

    # ==================== Utility Methods ====================

    def invalidate_cache(self, endpoint: Optional[str] = None) -> None:
        """清除缓存

        Args:
            endpoint: 如果指定，只清除该端点的缓存；否则清除所有
        """
        with self._cache_lock:
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
        with self._cache_lock:
            self._cache.clear()
            self._cache_timestamps.clear()