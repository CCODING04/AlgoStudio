from dataclasses import dataclass, field
from typing import Any, List, Optional
import socket
import time
import threading
import ray
from algo_studio.monitor.node_monitor import NodeMonitorActor

# ActorNotFoundError was added in Ray 2.9.0
try:
    from ray.exceptions import ActorNotFoundError
except ImportError:
    ActorNotFoundError = ValueError  # Fallback for older Ray versions

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
    # Optional fields for detailed info from NodeMonitorActor
    cpu_model: Optional[str] = None
    cpu_physical_cores: Optional[int] = None
    cpu_freq_current_mhz: Optional[float] = None
    gpu_utilization: Optional[int] = None
    gpu_memory_used_gb: Optional[float] = None
    gpu_memory_total_gb: Optional[float] = None
    gpu_name: Optional[str] = None
    hostname: Optional[str] = None

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
    def __init__(self, head_address: Optional[str] = None, cache_ttl: float = 5.0):
        """Initialize RayClient.

        Args:
            head_address: Ray head node address (e.g., '192.168.0.126:6379')
            cache_ttl: Time-to-live for node cache in seconds (default 5s)
        """
        self.head_address = head_address
        self._ray_initialized = False
        self._ray_available = False  # Track if Ray connection is actually working
        self._cache_ttl = cache_ttl
        self._nodes_cache = None  # (timestamp, nodes_list)
        self._cache_lock = threading.Lock()

    def _check_ray_available(self) -> bool:
        """Check if Ray head node is reachable via socket connection.

        This provides a fast check before attempting ray.init() which can
        take a very long time to timeout when the head is unreachable.
        """
        if self.head_address:
            host_port = self.head_address.split(':')
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 6379
        else:
            # Default Ray port
            host = '127.0.0.1'
            port = 6379

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)  # 2 second timeout for quick check
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _ensure_ray_init(self):
        """Lazily initialize Ray only when needed."""
        if self._ray_initialized:
            return

        # Fast check: if head is not reachable, skip ray.init()
        if not self._check_ray_available():
            self._ray_available = False
            self._ray_initialized = True
            return

        try:
            if self.head_address:
                ray.init(address=self.head_address, ignore_reinit_error=True, dashboard_port=None)
            else:
                ray.init(ignore_reinit_error=True, dashboard_port=None)
            self._ray_available = True
        except Exception:
            # Ray connection failed - mark as unavailable
            self._ray_available = False
        finally:
            self._ray_initialized = True

    def _get_host_info_from_actor(self, node_ip: str, resources: dict) -> dict:
        """Fetch host info from a remote NodeMonitorActor with reduced timeout.

        Returns:
            Dict with host info, or minimal info on failure.
        """
        actor_name = f"node_monitor_{node_ip}"
        try:
            actor = ray.get_actor(actor_name, namespace="algo_studio")
        except ActorNotFoundError:
            try:
                actor = NodeMonitorActor.options(
                    name=actor_name,
                    namespace="algo_studio",
                    lifetime="detached",
                    resources={f"node:{node_ip}": 0.001}
                ).remote()
            except Exception:
                return None  # Cannot create actor
        except Exception:
            return None  # Other errors getting actor

        try:
            # Reduced timeout from 5s to 2s for faster fallback
            host_info = ray.get(actor.get_host_info.remote(), timeout=2)
            return host_info
        except Exception:
            # Timeout or other error - return None to use fallback
            return None

    def _fetch_all_remote_nodes(self, ray_nodes: List[dict], local_ips: set) -> dict:
        """Fetch host info from all remote nodes in parallel using ThreadPoolExecutor.

        Args:
            ray_nodes: List of Ray node dictionaries
            local_ips: Set of local IP addresses

        Returns:
            Dict mapping node_ip -> host_info (or None if failed)
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Build list of (node_ip, resources) for remote nodes only
        remote_work = []
        for node in ray_nodes:
            node_ip = node.get("NodeName") or node.get("node_ip_address") or "unknown"
            if node.get("Alive", False) and node_ip not in local_ips:
                remote_work.append((node_ip, node.get("resources", {})))

        if not remote_work:
            return {}

        results = {}
        # Use ThreadPoolExecutor for parallel actor calls
        # Limit workers to avoid overwhelming the system
        with ThreadPoolExecutor(max_workers=min(len(remote_work), 4)) as executor:
            futures = {
                executor.submit(self._get_host_info_from_actor, ip, res): ip
                for ip, res in remote_work
            }
            for future in as_completed(futures, timeout=3):
                ip = futures[future]
                try:
                    results[ip] = future.result()
                except Exception:
                    results[ip] = None

        return results

    def get_nodes(self) -> List[NodeStatus]:
        """获取所有节点状态 (with caching and parallel fetching).

        Returns:
            List of NodeStatus for all cluster nodes.

        Raises:
            RuntimeError: If Ray is not available or connection fails.
        """
        # Check cache first
        with self._cache_lock:
            if self._nodes_cache is not None:
                cached_time, cached_nodes = self._nodes_cache
                if time.time() - cached_time < self._cache_ttl:
                    return cached_nodes

        self._ensure_ray_init()

        # Check if Ray connection was successful
        if not self._ray_available:
            raise RuntimeError("Ray is not available")

        import psutil
        from algo_studio.monitor.host_monitor import HostMonitor

        local_ips = set()
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family.name == "AF_INET":
                    local_ips.add(addr.address)

        try:
            ray_nodes = ray.nodes()
        except Exception as e:
            raise RuntimeError(f"Failed to get Ray nodes: {e}") from e

        # Deduplicate nodes by IP - ray.nodes() can return duplicate entries
        # for the same node. Keep only the first alive entry per IP.
        seen_ips = {}
        unique_nodes = []
        for node in ray_nodes:
            node_ip = node.get("NodeName") or node.get("node_ip_address") or "unknown"
            if node_ip not in seen_ips:
                seen_ips[node_ip] = node
                unique_nodes.append(node)
            elif not node.get("Alive", False) and seen_ips[node_ip].get("Alive", False):
                # Replace offline with offline entry only if we haven't seen an alive one
                seen_ips[node_ip] = node

        # Prefetch all remote nodes in parallel (only unique IPs)
        remote_host_info = self._fetch_all_remote_nodes(unique_nodes, local_ips)

        nodes = []
        for node in unique_nodes:
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
                # Local node - use HostMonitor directly with cached CPU
                # (avoid 1s blocking call for faster response)
                host_info = HostMonitor().get_host_info(use_cached_cpu=True)
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
                cpu_model = host_info.cpu_model
                cpu_physical_cores = host_info.cpu_physical_cores
                cpu_freq_current_mhz = host_info.cpu_freq_current_mhz
                gpu_utilization = host_info.gpu_utilization
                gpu_memory_used_gb = host_info.gpu_memory_used_gb
                gpu_memory_total_gb = host_info.gpu_memory_total_gb
                gpu_name = host_info.gpu_name
                hostname = host_info.hostname
            else:
                # Remote node - use pre-fetched info (from cache or fallback)
                host_info = remote_host_info.get(node_ip)
                if host_info is None:
                    # Actor call failed or timed out - return minimal info from resources
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
                    cpu_model = None
                    cpu_physical_cores = None
                    cpu_freq_current_mhz = None
                    gpu_utilization = None
                    gpu_memory_used_gb = None
                    gpu_memory_total_gb = None
                    gpu_name = None
                    hostname = None
                else:
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
                    cpu_model = host_info.get("cpu_model")
                    cpu_physical_cores = host_info.get("cpu_physical_cores")
                    cpu_freq_current_mhz = host_info.get("cpu_freq_current_mhz")
                    gpu_utilization = host_info.get("gpu_utilization")
                    gpu_memory_used_gb = host_info.get("gpu_memory_used_gb")
                    gpu_memory_total_gb = host_info.get("gpu_memory_total_gb")
                    gpu_name = host_info.get("gpu_name")
                    hostname = host_info.get("hostname")

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
                swap_total_gb=swap_total_gb,
                cpu_model=cpu_model,
                cpu_physical_cores=cpu_physical_cores,
                cpu_freq_current_mhz=cpu_freq_current_mhz,
                gpu_utilization=gpu_utilization,
                gpu_memory_used_gb=gpu_memory_used_gb,
                gpu_memory_total_gb=gpu_memory_total_gb,
                gpu_name=gpu_name,
                hostname=hostname
            )
            nodes.append(status)

        # Update cache
        with self._cache_lock:
            self._nodes_cache = (time.time(), nodes)

        return nodes

    def submit_task(self, func, *args, **kwargs):
        """提交任务到 Ray 集群

        Args:
            func: Ray remote function
            *args: positional args for the function
            **kwargs:
                - num_cpus: CPU count
                - num_gpus: GPU count
                - resources: custom resources dict
                - node_ip: specific node IP to run on
        """
        self._ensure_ray_init()
        node_ip = kwargs.pop("node_ip", None)
        options = {
            "num_cpus": kwargs.get("num_cpus", 1),
            "num_gpus": kwargs.get("num_gpus", 0),
            "resources": kwargs.get("resources", {}),
        }

        # Add node affinity if node_ip is specified
        if node_ip:
            options["resources"][f"node:{node_ip}"] = 0.001

        return func.options(**options).remote(*args)

    def shutdown(self):
        """关闭 Ray 连接"""
        if self._ray_initialized:
            ray.shutdown()
            self._ray_initialized = False

    def clear_cache(self):
        """Clear the nodes cache to force a fresh fetch on next call."""
        with self._cache_lock:
            self._nodes_cache = None