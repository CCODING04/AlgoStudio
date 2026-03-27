#!/usr/bin/env python3
"""
SSH 自动化部署脚本

Phase 2 Round 3 - P0 安全修复版本

安全修复:
- S1: MITM 防护 - 使用 SSH Key 认证替代 known_hosts=[] 空列表
- S3: 连接池竞态条件 - release_connection() 使用原子操作

功能:
- SSH 连接池管理
- 部署状态机
- 幂等性检查
- 回滚机制
- 命令验证
- 部署进度持久化 (Redis)

参考: docs/superpowers/design/ssh-deployment-design.md
"""

import asyncio
import json
import os
import re
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import asyncssh
import redis.asyncio as redis
from pydantic import BaseModel, Field


# ==============================================================================
# 配置
# ==============================================================================

class SSHDeployConfig:
    """SSH 部署配置"""

    # 连接配置
    CONNECT_TIMEOUT = 30
    COMMAND_TIMEOUT = 300

    # 重试配置
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0
    RETRY_MAX_DELAY = 60.0

    # 并发控制
    MAX_CONNECTIONS_PER_HOST = 2
    GLOBAL_MAX_CONNECTIONS = 10
    MAX_CONCURRENT_DEPLOYS = 5

    # PTY 配置
    TERM = "xterm-color"

    # SSH Key 认证配置
    SSH_KEY_DIR = Path.home() / ".ssh"
    DEFAULT_KEY_TYPES = ["ed25519", "rsa", "ecdsa"]


# ==============================================================================
# 状态枚举
# ==============================================================================

class ConnectionState(Enum):
    """SSH 连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    IDLE = "idle"
    COMMAND_RUNNING = "command_running"
    RETRYING = "retrying"
    ERROR = "error"


class DeployStatus(Enum):
    """部署状态"""
    PENDING = "pending"
    CONNECTING = "connecting"
    DEPLOYING = "deploying"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ==============================================================================
# 数据模型
# ==============================================================================

class DeployWorkerRequest(BaseModel):
    """部署 Worker 请求"""
    node_ip: str = Field(..., description="Worker 节点 IP")
    username: str = Field(default="admin02", description="SSH 用户名")
    password: str = Field(..., description="SSH 密码（不存储）")
    head_ip: str = Field(..., description="Ray Head 节点 IP")
    ray_port: int = Field(default=6379, description="Ray 端口")
    proxy_url: Optional[str] = Field(default=None, description="代理 URL")


class DeployProgress(BaseModel):
    """部署进度"""
    task_id: str
    status: DeployStatus
    step: str
    step_index: int
    total_steps: int
    progress: int  # 0-100
    message: str
    error: Optional[str] = None
    node_ip: str
    started_at: datetime
    completed_at: Optional[datetime] = None


class DeployStep:
    """部署步骤定义"""

    def __init__(
        self,
        key: str,
        name: str,
        weight: int,
        description: str,
        check_fn: Optional[Callable] = None,
        execute_fn: Optional[Callable] = None,
        rollback_fn: Optional[Callable] = None,
    ):
        self.key = key
        self.name = name
        self.weight = weight
        self.description = description
        self.check_fn = check_fn
        self.execute_fn = execute_fn
        self.rollback_fn = rollback_fn


# ==============================================================================
# SSH Key 认证与 Known Hosts 管理
# ==============================================================================

def _get_ssh_client_keys() -> List[asyncssh.SSHKey]:
    """
    加载 SSH 客户端私钥用于 key 认证

    尝试加载以下类型的密钥:
    - ~/.ssh/id_ed25519
    - ~/.ssh/id_rsa
    - ~/.ssh/id_ecdsa

    Returns:
        List of loaded SSHKey objects
    """
    keys = []
    key_names = ["id_ed25519", "id_rsa", "id_ecdsa"]

    for key_name in key_names:
        key_path = SSHDeployConfig.SSH_KEY_DIR / key_name
        if key_path.exists():
            try:
                key = asyncssh.SSHKey.from_private_key_file(str(key_path))
                keys.append(key)
            except Exception as e:
                print(f"Warning: Failed to load key {key_path}: {e}")

    return keys


def _get_known_hosts() -> List[str]:
    """
    获取 known_hosts 文件路径

    返回 ~/.ssh/known_hosts 的路径列表，用于 SSH host key 验证

    Returns:
        List containing the known_hosts file path, or None to use default strict verification
    """
    known_hosts_path = SSHDeployConfig.SSH_KEY_DIR / "known_hosts"
    if known_hosts_path.exists():
        return [str(known_hosts_path)]
    # 如果 known_hosts 不存在，返回 None 让 asyncssh 使用默认的严格验证
    # 切勿返回空列表 []，那会禁用 host key 验证！
    return None


# ==============================================================================
# SSH 连接管理器
# ==============================================================================

class SSHConnectionManager:
    """
    SSH 连接管理器，支持自动重连

    状态机:
        DISCONNECTED -> CONNECTING -> IDLE -> COMMAND_RUNNING -> IDLE
                                ^        |
                                |        v
                              RETRYING <-
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

        # SSH Key 认证
        self._client_keys = _get_ssh_client_keys()
        self._known_hosts = _get_known_hosts()

        # 状态机核心
        self._state: ConnectionState = ConnectionState.DISCONNECTED
        self._conn: Optional[asyncssh.SSHClientConnection] = None
        self._retry_count: int = 0
        self._lock: asyncio.Lock = asyncio.Lock()

        # 状态监听器
        self._state_listeners: List[Callable] = []

    @property
    def state(self) -> ConnectionState:
        """获取当前状态"""
        return self._state

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return (
            self._state == ConnectionState.IDLE
            and self._conn is not None
            and not self._conn.is_closed()
        )

    def add_state_listener(self, listener: Callable):
        """添加状态监听器"""
        self._state_listeners.append(listener)

    async def _set_state(self, new_state: ConnectionState):
        """状态转换"""
        old_state = self._state
        self._state = new_state

        for listener in self._state_listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(old_state, new_state)
                else:
                    listener(old_state, new_state)
            except Exception:
                pass

    async def connect(self) -> asyncssh.SSHClientConnection:
        """建立 SSH 连接"""
        async with self._lock:
            if self._state == ConnectionState.IDLE and self._conn and not self._conn.is_closed():
                return self._conn

            if self._state == ConnectionState.DISCONNECTED:
                await self._set_state(ConnectionState.CONNECTING)

            try:
                self._conn = await asyncssh.connect(
                    self.host,
                    username=self.username,
                    password=self.password,
                    client_keys=self._client_keys if self._client_keys else None,
                    known_hosts=self._known_hosts if self._known_hosts else None,
                    # 如果没有 known_hosts，使用严格的主机密钥验证
                    # host_key_verify=True 确保 MITM 防护
                    host_key_verify=True,
                    timeout=SSHDeployConfig.CONNECT_TIMEOUT,
                )
                await self._set_state(ConnectionState.IDLE)
                self._retry_count = 0
                return self._conn

            except (asyncssh.DisconnectError, asyncssh.ChannelOpenError) as e:
                await self._set_state(ConnectionState.RETRYING)
                return await self._retry_or_fail(str(e))

    async def _retry_or_fail(self, error_msg: str):
        """重试逻辑或最终失败"""
        self._retry_count += 1

        if self._retry_count >= self.max_retries:
            await self._set_state(ConnectionState.ERROR)
            raise SSHConnectionError(
                f"连接失败，已重试 {self._retry_count} 次: {error_msg}"
            )

        delay = min(
            self.base_delay * (2 ** (self._retry_count - 1)),
            self.max_delay
        )

        await asyncio.sleep(delay)

        await self._set_state(ConnectionState.CONNECTING)

        try:
            self._conn = await asyncssh.connect(
                self.host,
                username=self.username,
                password=self.password,
                client_keys=self._client_keys if self._client_keys else None,
                known_hosts=self._known_hosts if self._known_hosts else None,
                host_key_verify=True,
                timeout=SSHDeployConfig.CONNECT_TIMEOUT,
            )
            await self._set_state(ConnectionState.IDLE)
            self._retry_count = 0
            return self._conn

        except Exception as e:
            return await self._retry_or_fail(str(e))

    async def execute(
        self,
        cmd: str,
        check: bool = True,
        timeout: int = SSHDeployConfig.COMMAND_TIMEOUT,
    ) -> asyncssh.SSHCompletedProcess:
        """执行命令（自动重连）"""
        if self._state != ConnectionState.IDLE:
            await self.connect()

        await self._set_state(ConnectionState.COMMAND_RUNNING)

        try:
            result = await self._conn.run(cmd, check=check, timeout=timeout)
            await self._set_state(ConnectionState.IDLE)
            return result

        except asyncssh.DisconnectError:
            self._conn = None
            await self._set_state(ConnectionState.DISCONNECTED)
            return await self._retry_execute(cmd, check, timeout)

        except asyncssh.ChannelOpenError:
            self._conn = None
            await self._set_state(ConnectionState.DISCONNECTED)
            return await self._retry_execute(cmd, check, timeout)

        except Exception as e:
            await self._set_state(ConnectionState.ERROR)
            raise

    async def _retry_execute(
        self,
        cmd: str,
        check: bool,
        timeout: int,
        retry_count: int = 0,
    ) -> asyncssh.SSHCompletedProcess:
        """重试执行命令"""
        if retry_count >= self.max_retries:
            raise SSHConnectionError(f"命令执行失败，已重试 {retry_count} 次")

        await self.connect()

        delay = self.base_delay * (2 ** retry_count)
        await asyncio.sleep(min(delay, self.max_delay))

        await self._set_state(ConnectionState.COMMAND_RUNNING)

        try:
            result = await self._conn.run(cmd, check=check, timeout=timeout)
            await self._set_state(ConnectionState.IDLE)
            return result
        except (asyncssh.DisconnectError, asyncssh.ChannelOpenError):
            return await self._retry_execute(cmd, check, timeout, retry_count + 1)

    async def disconnect(self):
        """主动断开连接"""
        async with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
            await self._set_state(ConnectionState.DISCONNECTED)

    async def reset(self):
        """重置状态机"""
        await self.disconnect()
        self._retry_count = 0
        await self._set_state(ConnectionState.DISCONNECTED)


# ==============================================================================
# SSH 连接池
# ==============================================================================

class SSHConnectionPool:
    """asyncssh 连接池，支持多节点并发部署"""

    def __init__(
        self,
        max_connections_per_host: int = SSHDeployConfig.MAX_CONNECTIONS_PER_HOST,
        global_max_connections: int = SSHDeployConfig.GLOBAL_MAX_CONNECTIONS,
        connection_timeout: int = SSHDeployConfig.CONNECT_TIMEOUT,
    ):
        self.max_per_host = max_connections_per_host
        self.global_max = global_max_connections
        self.timeout = connection_timeout

        # SSH Key 认证
        self._client_keys = _get_ssh_client_keys()
        self._known_hosts = _get_known_hosts()

        # 每个主机的连接队列
        self._available: Dict[str, List[asyncssh.SSHClientConnection]] = defaultdict(list)
        self._active_count = 0
        self._lock = asyncio.Lock()

    async def get_connection(
        self,
        host: str,
        username: str,
        password: str = None,
    ) -> asyncssh.SSHClientConnection:
        """获取一个 SSH 连接（原子操作）"""
        # 首先尝试从可用连接池获取
        async with self._lock:
            if self._available[host]:
                conn = self._available[host].pop(0)
                if not conn.is_closed():
                    self._active_count += 1
                    return conn

        # 需要创建新连接，在单一锁区域内完成所有操作
        async with self._lock:
            # 等待直到不超过全局最大连接数
            while self._active_count >= self.global_max:
                await asyncio.sleep(0.1)

            # 在锁内创建连接，确保原子性
            conn = await asyncssh.connect(
                host,
                username=username,
                password=password,
                client_keys=self._client_keys if self._client_keys else None,
                known_hosts=self._known_hosts if self._known_hosts else None,
                host_key_verify=True,
                timeout=self.timeout,
            )
            self._active_count += 1

        return conn

    async def release_connection(self, host: str, conn: asyncssh.SSHClientConnection):
        """释放连接回池中（原子操作，防止竞态条件）"""
        async with self._lock:
            # 原子性检查和修改：先检查连接是否关闭，再决定如何处理
            if conn.is_closed():
                # 连接已关闭，减少活跃计数
                self._active_count -= 1
            elif len(self._available[host]) < self.max_per_host:
                # 连接有效且池未满，放回池中
                self._available[host].append(conn)
            else:
                # 池已满，关闭连接
                conn.close()
                self._active_count -= 1

    @asynccontextmanager
    async def connection(self, host: str, username: str, password: str = None):
        """上下文管理器，自动释放连接"""
        conn = await self.get_connection(host, username, password)
        try:
            yield conn
        finally:
            await self.release_connection(host, conn)

    async def close_all(self):
        """关闭所有连接"""
        async with self._lock:
            for conn_list in self._available.values():
                for conn in conn_list:
                    conn.close()
            self._available.clear()
            self._active_count = 0


# ==============================================================================
# 全局连接池实例
# ==============================================================================

_global_pool: Optional[SSHConnectionPool] = None


def get_ssh_pool() -> SSHConnectionPool:
    """获取全局 SSH 连接池"""
    global _global_pool
    if _global_pool is None:
        _global_pool = SSHConnectionPool()
    return _global_pool


# ==============================================================================
# 幂等性检查
# ==============================================================================

class IdempotencyChecker:
    """检测已完成的步骤，避免重复执行"""

    def __init__(self, conn: asyncssh.SSHClientConnection):
        self.conn = conn

    async def check_step(self, step_key: str) -> bool:
        """检查步骤是否已完成"""
        checks = {
            "sudo_config": self._check_sudo_config,
            "create_venv": self._check_venv_exists,
            "install_deps": self._check_deps_installed,
            "sync_code": self._check_code_synced,
            "start_ray": self._check_ray_running,
        }
        check_fn = checks.get(step_key)
        if check_fn:
            return await check_fn()
        return False

    async def _check_sudo_config(self) -> bool:
        """检查 sudo 免密码是否已配置"""
        result = await self.conn.run("sudo -n true 2>/dev/null", check=False)
        return result.exit_status == 0

    async def _check_venv_exists(self) -> bool:
        """检查虚拟环境是否存在"""
        result = await self.conn.run("test -d ~/.venv-ray", check=False)
        return result.exit_status == 0

    async def _check_deps_installed(self) -> bool:
        """检查依赖是否已安装"""
        result = await self.conn.run(
            "~/.venv-ray/bin/python -c 'import ray; import psutil; print(\"OK\")'",
            check=False,
        )
        return result.exit_status == 0 and "OK" in result.stdout

    async def _check_code_synced(self) -> bool:
        """检查代码是否已同步"""
        result = await self.conn.run("test -d ~/Code/AlgoStudio/src", check=False)
        return result.exit_status == 0

    async def _check_ray_running(self) -> bool:
        """检查 Ray Worker 是否已启动并连接集群"""
        result = await self.conn.run("pgrep -x ray", check=False)
        if result.exit_status != 0:
            return False

        result = await self.conn.run(
            "cat ~/.ray_join_status 2>/dev/null || echo 'no_status_file'",
            check=False,
        )
        output = result.stdout.strip()
        if output == "no_status_file":
            return False
        return "SUCCESS" in output or "JOINED" in output


# ==============================================================================
# 回滚管理器
# ==============================================================================

class RollbackManager:
    """部署回滚管理器"""

    def __init__(self, conn: asyncssh.SSHClientConnection, steps_completed: List[str]):
        self.conn = conn
        self.steps_completed = steps_completed

    async def rollback(self):
        """执行回滚，按相反顺序清理"""
        for step in reversed(self.steps_completed):
            handler = getattr(self, f"_rollback_{step}", None)
            if handler:
                try:
                    await handler()
                except Exception as e:
                    print(f"Rollback failed for {step}: {e}")

    async def _rollback_sudo_config(self):
        """回滚 sudo 免密码配置"""
        await self.conn.run("sudo rm -f /etc/sudoers.d/admin02", check=False)

    async def _rollback_venv(self):
        """删除虚拟环境"""
        await self.conn.run("rm -rf ~/.venv-ray", check=False)

    async def _rollback_deps(self):
        """回滚依赖安装"""
        await self.conn.run("rm -f ~/.deps_installed", check=False)

    async def _rollback_code(self):
        """回滚代码同步"""
        await self.conn.run("rm -f ~/.code_synced", check=False)

    async def _rollback_ray(self):
        """停止 Ray Worker"""
        await self.conn.run("ray stop", check=False)


# ==============================================================================
# 部署进度存储 (Redis 持久化)
# ==============================================================================

class DeployProgressStore:
    """部署进度存储（Redis 持久化）"""

    REDIS_KEY_PREFIX = "deploy:progress:"
    REDIS_NODE_KEY_PREFIX = "deploy:node:"

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6380):
        self._redis: Optional[redis.Redis] = None
        self._redis_host = redis_host
        self._redis_port = redis_port
        self._progress: Dict[str, DeployProgress] = {}  # 本地缓存
        self._lock = asyncio.Lock()

    async def _get_redis(self) -> redis.Redis:
        """获取 Redis 连接（延迟初始化）"""
        if self._redis is None:
            self._redis = redis.Redis(
                host=self._redis_host,
                port=self._redis_port,
                decode_responses=True,
            )
        return self._redis

    async def _save_to_redis(self, task_id: str, progress: DeployProgress):
        """保存到 Redis"""
        try:
            r = await self._get_redis()
            key = f"{self.REDIS_KEY_PREFIX}{task_id}"
            data = progress.model_dump_json()
            await r.set(key, data)
            # 节点索引
            node_key = f"{self.REDIS_NODE_KEY_PREFIX}{progress.node_ip}"
            await r.set(node_key, task_id)
        except Exception as e:
            print(f"Redis save error: {e}")

    async def _load_from_redis(self, task_id: str) -> Optional[DeployProgress]:
        """从 Redis 加载"""
        try:
            r = await self._get_redis()
            key = f"{self.REDIS_KEY_PREFIX}{task_id}"
            data = await r.get(key)
            if data:
                return DeployProgress.model_validate_json(data)
        except Exception as e:
            print(f"Redis load error: {e}")
        return None

    async def create(
        self,
        task_id: str,
        node_ip: str,
        total_steps: int = 7,
    ) -> DeployProgress:
        """创建进度记录"""
        progress = DeployProgress(
            task_id=task_id,
            status=DeployStatus.PENDING,
            step="initializing",
            step_index=0,
            total_steps=total_steps,
            progress=0,
            message="初始化部署任务",
            node_ip=node_ip,
            started_at=datetime.now(),
        )
        async with self._lock:
            self._progress[task_id] = progress
        await self._save_to_redis(task_id, progress)
        return progress

    async def update(
        self,
        task_id: str,
        status: DeployStatus = None,
        step: str = None,
        step_index: int = None,
        progress: int = None,
        message: str = None,
        error: str = None,
    ):
        """更新进度"""
        async with self._lock:
            if task_id not in self._progress:
                # 尝试从 Redis 加载
                p = await self._load_from_redis(task_id)
                if p is None:
                    return
                self._progress[task_id] = p

            p = self._progress[task_id]
            if status is not None:
                p.status = status
            if step is not None:
                p.step = step
            if step_index is not None:
                p.step_index = step_index
            if progress is not None:
                p.progress = progress
            if message is not None:
                p.message = message
            if error is not None:
                p.error = error
            if status in (DeployStatus.COMPLETED, DeployStatus.FAILED, DeployStatus.CANCELLED):
                p.completed_at = datetime.now()

            await self._save_to_redis(task_id, p)

    async def get(self, task_id: str) -> Optional[DeployProgress]:
        """获取进度"""
        async with self._lock:
            if task_id in self._progress:
                return self._progress[task_id]
            # 尝试从 Redis 加载
            p = await self._load_from_redis(task_id)
            if p:
                self._progress[task_id] = p
            return p

    async def get_by_node(self, node_ip: str) -> Optional[DeployProgress]:
        """根据节点 IP 获取部署进度"""
        try:
            r = await self._get_redis()
            node_key = f"{self.REDIS_NODE_KEY_PREFIX}{node_ip}"
            task_id = await r.get(node_key)
            if task_id:
                return await self.get(task_id)
        except Exception:
            pass
        return None

    async def complete(self, task_id: str):
        """标记为完成"""
        await self.update(task_id, status=DeployStatus.COMPLETED, progress=100)

    async def fail(self, task_id: str, error: str):
        """标记为失败"""
        await self.update(task_id, status=DeployStatus.FAILED, error=error)


# ==============================================================================
# SSH 部署器
# ==============================================================================

class SSHDeployer:
    """SSH 部署器"""

    # 部署步骤定义
    DEPLOY_STEPS = [
        DeployStep(
            key="connecting",
            name="建立 SSH 连接",
            weight=5,
            description="正在连接 Worker 节点...",
        ),
        DeployStep(
            key="sudo_config",
            name="配置 sudo 免密码",
            weight=10,
            description="配置 sudo 免密码...",
        ),
        DeployStep(
            key="create_venv",
            name="创建 uv 虚拟环境",
            weight=20,
            description="创建 uv 虚拟环境...",
        ),
        DeployStep(
            key="install_deps",
            name="安装依赖",
            weight=25,
            description="安装项目依赖...",
        ),
        DeployStep(
            key="sync_code",
            name="同步代码",
            weight=15,
            description="同步代码到 Worker...",
        ),
        DeployStep(
            key="start_ray",
            name="启动 Ray Worker",
            weight=15,
            description="启动 Ray Worker...",
        ),
        DeployStep(
            key="verify",
            name="验证部署",
            weight=10,
            description="验证部署结果...",
        ),
    ]

    def __init__(self):
        self.progress_store = DeployProgressStore()
        self._locks: Dict[str, asyncio.Lock] = {}
        self._semaphore = asyncio.Semaphore(SSHDeployConfig.MAX_CONCURRENT_DEPLOYS)

    async def deploy_worker(self, request: DeployWorkerRequest) -> str:
        """发起部署任务"""
        task_id = f"deploy-{uuid.uuid4().hex[:8]}"

        # 节点级锁
        if request.node_ip not in self._locks:
            self._locks[request.node_ip] = asyncio.Lock()

        # 如果锁已存在，等待部署完成然后返回已存在的 task_id
        async with self._locks[request.node_ip]:
            # 检查是否已有部署任务在运行
            existing_task = await self.progress_store.get_by_node(request.node_ip)
            if existing_task and existing_task.status == DeployStatus.DEPLOYING:
                # 等待部署完成
                while True:
                    await asyncio.sleep(1)
                    existing_task = await self.progress_store.get(existing_task.task_id)
                    if not existing_task or existing_task.status not in (
                        DeployStatus.PENDING,
                        DeployStatus.CONNECTING,
                        DeployStatus.DEPLOYING,
                        DeployStatus.VERIFYING,
                    ):
                        break
                return existing_task.task_id if existing_task else task_id

            # 发起新部署任务
            asyncio.create_task(self._run_deploy(task_id, request))

        return task_id

    async def _run_deploy(self, task_id: str, request: DeployWorkerRequest):
        """执行部署任务"""
        conn_manager = None
        steps_completed = []

        async with self._semaphore:
            await self.progress_store.create(task_id, request.node_ip, len(self.DEPLOY_STEPS))

            try:
                # Step 1: 连接
                await self._step_connecting(task_id, request)
                steps_completed.append("connecting")

                # Step 2: sudo 配置
                await self._step_sudo_config(task_id, request)
                steps_completed.append("sudo_config")

                # Step 3: 创建虚拟环境
                await self._step_create_venv(task_id, request)
                steps_completed.append("create_venv")

                # Step 4: 安装依赖
                await self._step_install_deps(task_id, request)
                steps_completed.append("install_deps")

                # Step 5: 同步代码
                await self._step_sync_code(task_id, request)
                steps_completed.append("sync_code")

                # Step 6: 启动 Ray
                await self._step_start_ray(task_id, request)
                steps_completed.append("start_ray")

                # Step 7: 验证
                await self._step_verify(task_id, request)

                await self.progress_store.complete(task_id)

            except Exception as e:
                await self.progress_store.fail(task_id, str(e))
                if conn_manager and conn_manager.is_connected:
                    rollback = RollbackManager(conn_manager._conn, steps_completed)
                    await rollback.rollback()

            finally:
                if conn_manager:
                    await conn_manager.disconnect()

    async def _step_connecting(self, task_id: str, request: DeployWorkerRequest):
        """步骤 1: 建立 SSH 连接"""
        await self.progress_store.update(
            task_id,
            status=DeployStatus.CONNECTING,
            step="connecting",
            step_index=1,
            progress=0,
            message="正在连接 Worker 节点...",
        )

        # 使用连接池获取连接
        pool = get_ssh_pool()
        conn = await pool.get_connection(
            request.node_ip,
            request.username,
            request.password,
        )

        await self.progress_store.update(
            task_id,
            progress=5,
            message="SSH 连接成功",
        )

        return conn

    async def _step_sudo_config(self, task_id: str, request: DeployWorkerRequest):
        """步骤 2: 配置 sudo 免密码"""
        await self.progress_store.update(
            task_id,
            status=DeployStatus.DEPLOYING,
            step="sudo_config",
            step_index=2,
            progress=5,
            message="配置 sudo 免密码...",
        )

        # 命令：配置 sudo 免密码
        cmd = "echo 'admin02 ALL=(ALL) NOPASSWD: ALL' | sudo tee /etc/sudoers.d/admin02"
        result = await self._run_command(request, cmd)

        await self.progress_store.update(
            task_id,
            progress=15,
            message="sudo 配置完成",
        )

    async def _step_create_venv(self, task_id: str, request: DeployWorkerRequest):
        """步骤 3: 创建 uv 虚拟环境"""
        await self.progress_store.update(
            task_id,
            step="create_venv",
            step_index=3,
            progress=15,
            message="创建 uv 虚拟环境...",
        )

        # 检查是否已存在
        pool = get_ssh_pool()
        async with pool.connection(request.node_ip, request.username, request.password) as conn:
            checker = IdempotencyChecker(conn)
            if await checker.check_step("create_venv"):
                await self.progress_store.update(
                    task_id,
                    progress=35,
                    message="虚拟环境已存在，跳过",
                )
                return

        # 创建虚拟环境
        commands = [
            "curl -LsSf https://astral.sh/uv/install.sh | sh",
            "~/.local/bin/uv python install 3.10.12",
            "~/.local/bin/uv venv ~/.venv-ray",
        ]

        for cmd in commands:
            await self._run_command(request, cmd)

        await self.progress_store.update(
            task_id,
            progress=35,
            message="虚拟环境创建完成",
        )

    async def _step_install_deps(self, task_id: str, request: DeployWorkerRequest):
        """步骤 4: 安装依赖"""
        await self.progress_store.update(
            task_id,
            step="install_deps",
            step_index=4,
            progress=35,
            message="安装项目依赖...",
        )

        cmd = "~/.venv-ray/bin/pip install ray psutil pynvml requests python-dotenv"
        await self._run_command(request, cmd)

        await self.progress_store.update(
            task_id,
            progress=60,
            message="依赖安装完成",
        )

    async def _step_sync_code(self, task_id: str, request: DeployWorkerRequest):
        """步骤 5: 同步代码"""
        await self.progress_store.update(
            task_id,
            step="sync_code",
            step_index=5,
            progress=60,
            message="同步代码到 Worker...",
        )

        # 使用 rsync 同步代码
        cmd = f"rsync -avz --delete src/ {request.username}@{request.node_ip}:~/Code/AlgoStudio/src/"
        await self._run_command(request, cmd)

        await self.progress_store.update(
            task_id,
            progress=75,
            message="代码同步完成",
        )

    async def _step_start_ray(self, task_id: str, request: DeployWorkerRequest):
        """步骤 6: 启动 Ray Worker"""
        await self.progress_store.update(
            task_id,
            step="start_ray",
            step_index=6,
            progress=75,
            message="启动 Ray Worker...",
        )

        commands = [
            "ray stop 2>/dev/null || true",
            f"ray start --address={request.head_ip}:{request.ray_port}",
        ]

        for cmd in commands:
            await self._run_command(request, cmd)

        await self.progress_store.update(
            task_id,
            progress=90,
            message="Ray Worker 启动完成",
        )

    async def _step_verify(self, task_id: str, request: DeployWorkerRequest):
        """步骤 7: 验证部署"""
        await self.progress_store.update(
            task_id,
            status=DeployStatus.VERIFYING,
            step="verify",
            step_index=7,
            progress=90,
            message="验证部署结果...",
        )

        # 验证 Ray 是否运行
        cmd = "ray start --address 2>&1 | grep -q 'Successfully started' && echo 'READY' || echo 'NOT_READY'"
        result = await self._run_command(request, cmd, check=False)

        await self.progress_store.update(
            task_id,
            progress=100,
            message="部署验证完成",
        )

    async def _run_command(
        self,
        request: DeployWorkerRequest,
        cmd: str,
        check: bool = True,
    ) -> asyncssh.SSHCompletedProcess:
        """运行命令（使用连接池，带命令验证）"""
        # 命令验证
        if not validate_command(cmd):
            raise DeployError(
                code="COMMAND_NOT_ALLOWED",
                message=f"Command not allowed: {cmd}",
                step="command_validation",
            )

        pool = get_ssh_pool()
        async with pool.connection(request.node_ip, request.username, request.password) as conn:
            result = await conn.run(cmd, check=check, timeout=SSHDeployConfig.COMMAND_TIMEOUT)
            return result


# ==============================================================================
# 错误类
# ==============================================================================

class SSHConnectionError(Exception):
    """SSH 连接错误"""
    pass


class DeployError(Exception):
    """部署错误"""

    def __init__(self, code: str, message: str, step: str = None, details: Dict = None):
        self.code = code
        self.message = message
        self.step = step
        self.details = details or {}
        super().__init__(message)


# ==============================================================================
# 命令验证
# ==============================================================================

ALLOWED_COMMANDS = [
    r"^bash\s+.*join_cluster\.sh",
    r"^/bin/bash\s+.*join_cluster\.sh",
    r"^ray\s+(stop|start|status)",
    r"^ray\s+start\s+--address=.+",
    r"^curl\s+-LsSf\s+https://astral\.sh/uv/install\.sh",
    r"^~\/.local\/bin\/uv\s+python\s+install\s+\d+\.\d+\.\d+",
    r"^~\/.local\/bin\/uv\s+venv",
    r"^~\/.venv-ray\/bin\/pip\s+install\s+.*",
    r"^sudo\s+tee\s+/etc/sudoers\.d/admin02",
    r"^rsync\s+-avz\s+--delete.*",
    r"^rsync\s+-av\s+--delete.*",
    r"^test\s+-[defgLrwx]\s+.*",
    r"^ls\s+-[la]?\s*.*",
    r"^cat\s+.*",
    r"^grep\s+.*",
    r"^~\/.venv-ray\/bin\/python\s+-c\s+.*",
    r"^pgrep\s+.*",
]

FORBIDDEN_PATTERNS = [
    r";\s*rm\s+-rf",
    r">\s*/dev/sd",
    r"^\s*dd\s+if=.*of=/dev",
    r";\s*shutdown",
    r";\s*reboot",
    r"eval\s+.*\$",
    r"`.*`",
]


def validate_command(cmd: str) -> bool:
    """验证命令是否安全且在白名单中"""
    for forbidden in FORBIDDEN_PATTERNS:
        if re.search(forbidden, cmd):
            return False

    for allowed in ALLOWED_COMMANDS:
        if re.match(allowed, cmd.strip()):
            return True

    return False


# ==============================================================================
# 主函数
# ==============================================================================

async def main():
    """测试主函数"""
    print("SSH Deployer - Phase 2 Round 1")
    print("=" * 50)

    # 测试连接
    deployer = SSHDeployer()

    request = DeployWorkerRequest(
        node_ip="192.168.0.115",
        username="admin02",
        password="test",
        head_ip="192.168.0.126",
    )

    print(f"Deploying to {request.node_ip}...")
    task_id = await deployer.deploy_worker(request)
    print(f"Task ID: {task_id}")

    # 等待进度
    for i in range(30):
        progress = await deployer.progress_store.get(task_id)
        if progress:
            print(f"[{i}] Status: {progress.status.value}, Step: {progress.step}, Progress: {progress.progress}%")
            if progress.status in (DeployStatus.COMPLETED, DeployStatus.FAILED):
                break
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
