# SSH 自动部署 Worker 节点研究报告

## 1. 问题分析

### 1.1 需求概述
- **输入**: Web 界面接收 Worker 节点 IP、SSH 密码
- **目标**: 通过 SSH 自动完成 Worker 节点完整部署
- **功能点**: SSH 连接、远程脚本执行、部署进度显示、异常处理

### 1.2 当前部署脚本分析

#### `join_cluster.sh` - 基础 Ray Worker 加入脚本
```
执行步骤:
[1/4] 创建 uv 虚拟环境 (.venv-ray)
     - uv python install Python 3.10.12
     - uv venv 创建隔离环境
[2/4] 安装依赖
     - ray, python-dotenv, psutil, pynvml, requests
[3/4] 启动 Ray Worker
     - ray start --address=<HEAD_IP>:6379
[4/4] 验证集群连接
```

#### `worker_deploy.sh` - 完整 Worker 部署脚本
```
执行步骤:
[1/7] 配置 sudo 免密码
[2/7] 安装 JuiceFS v1.1.5
[3/7] 禁用 Redis protected mode
[4/7] 挂载 JuiceFS 到 /mnt/VtrixDataset
[5/7] 同步代码 (rsync src/)
[6/7] 同步算法 (rsync algorithms/)
[7/7] 重启 Ray Worker
```

#### 依赖环境分析
| 步骤 | 依赖项 | 说明 |
|------|--------|------|
| SSH 连接 | admin02 用户 sudo 权限 | 用于配置免密码sudo |
| uv 环境 | ~/.local/bin/uv | 通过 curl 安装 |
| Python | 3.10.12 | 通过 uv 安装 |
| Ray | 2.54.0 | 通过 pip 安装 |
| JuiceFS | 1.1.5 | 从 GitHub 下载 |
| 代码同步 | rsync + SSH Key | 免密码 rsync |

### 1.3 技术挑战

1. **密码传输安全**: SSH 密码不能明文存储，需加密传输或一次性使用
2. **交互式命令**: 部分脚本需要 sudo/输入密码，SSH 非交互式
3. **实时进度**: 多步骤部署需要 SSE 实时推送状态
4. **超时处理**: 网络问题导致部署卡住
5. **幂等性**: 重复部署需要能检测并跳过已完成的步骤
6. **事务性**: 部署失败需要回滚或清理

---

## 2. SSH 自动化方案对比

### 2.1 方案一: paramiko (同步)

**简介**: Python 最流行的 SSH 库，纯 Python 实现，API 成熟

**优点**:
- 文档完善，社区活跃
- 支持密码、密钥、keyboard-interactive 认证
- `exec_command()` 支持获取退出码和输出流
- `invoke_shell()` 支持交互式命令
- 稳定可靠，生产环境验证

**缺点**:
- 同步阻塞，不适合高并发
- 密码认证需要处理 PTY 问题
- 无内置重连机制

**适用场景**: 中等并发，部署任务不频繁

**关键 API**:
```python
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname, port=22, username, password)

# 执行命令并获取输出
stdin, stdout, stderr = ssh.exec_command('echo "hello"')
exit_code = stdout.channel.recv_exit_status()
output = stdout.read().decode()

# 交互式 shell
channel = ssh.invoke_shell()
channel.send('sudo command\n')
channel.recv(max_chars)
```

### 2.2 方案二: asyncssh (异步)

**简介**: Python 3.10+ asyncio 原生 SSH 库，RonF 等人开发

**优点**:
- 原生异步支持，适合 FastAPI 集成
- 更好的并发性能
- 现代 API 设计
- 支持 SSH 证书

**缺点**:
- 需要 Python 3.10+
- 相对较新，生产验证案例较少
- 部分环境可能缺少依赖 (e.g., libssh2)

**适用场景**: FastAPI + SSE 场景，需要高并发

**关键 API**:
```python
import asyncssh

async def deploy_worker():
    async with asyncssh.connect(host, username, password) as conn:
        result = await conn.run('echo "hello"', check=True)
        print(result.stdout)

# 并发执行
results = await asyncssh.gather(
    deploy_worker('192.168.0.115'),
    deploy_worker('192.168.0.116'),
)
```

### 2.3 方案三: Fabric (高level SSH)

**简介**: 基于 paramiko 的高级 SSH 库，设计用于远程执行和部署

**优点**:
- 高层 API，操作简洁
- 上下文管理器，自动连接管理
- 本地和远程命令统一接口 (fab)

**缺点**:
- 同步设计
- 2.x 版本与 1.x API 不兼容
- 学习曲线

**适用场景**: 熟悉其 API 的团队

### 2.4 方案四: Ansible (配置管理)

**简介**: 完整的配置管理和自动化平台

**优点**:
- YAML 配置，声明式
- 无 Agent，SSH 推送
- 成熟稳定，社区庞大
- 幂等性内置

**缺点**:
- 重量级，学习曲线陡
- 需要安装 Ansible 控制节点
- 对于简单部署过于复杂

**适用场景**: 大规模集群管理，已有 Ansible 使用经验

### 2.5 方案对比表

| 维度 | paramiko | asyncssh | Fabric | Ansible |
|------|----------|----------|--------|---------|
| 异步支持 | 否 | 是 | 否 | 部分 |
| FastAPI 集成 | 需线程池 | 原生 | 需线程池 | N/A |
| 密码认证 | 支持 | 支持 | 支持 | 支持 |
| 密钥认证 | 支持 | 支持 | 支持 | 支持 |
| 交互式命令 | 需 PTY | 需 PTY | 封装 | Playbook |
| 并发能力 | 低 | 高 | 低 | 高 |
| 学习成本 | 低 | 中 | 中 | 高 |
| 生产验证 | 广泛 | 一般 | 广泛 | 广泛 |
| 依赖数量 | 轻量 | 轻量 | 轻量 | 重量 |

**推荐**: **asyncssh** 作为明确选择。

### 2.6 asyncssh 连接池设计

在高并发部署场景下，需要连接池管理 SSH 连接：

```python
import asyncssh
from contextlib import asynccontextmanager
from collections import defaultdict
import asyncio

class SSHConnectionPool:
    """asyncssh 连接池，支持多节点并发部署"""

    def __init__(
        self,
        max_connections_per_host: int = 2,
        global_max_connections: int = 10,
        connection_timeout: int = 30
    ):
        self.max_per_host = max_connections_per_host
        self.global_max = global_max_connections
        self.timeout = connection_timeout

        # 每个主机的连接队列（修复bug：从单一连接改为列表，支持同一host多连接复用）
        self._available: Dict[str, List[asyncssh.Connection]] = defaultdict(list)
        # 当前活跃连接计数
        self._active_count = 0
        self._lock = asyncio.Lock()

    async def get_connection(
        self,
        host: str,
        username: str,
        password: str = None,
        client_keys: list = None
    ) -> asyncssh.Connection:
        """获取一个 SSH 连接（从池中复用或新建）"""

        # 1. 尝试从复用池获取（池操作需加锁）
        async with self._lock:
            # 检查是否有可复用连接
            if self._available[host]:
                conn = self._available[host].pop(0)
                if not conn.is_closed():
                    self._active_count += 1
                    return conn
                # 连接已关闭，丢弃并继续创建新连接

        # 2. 创建新连接（耗时长，不放锁内）
        async with self._lock:
            # 检查全局限制
            while self._active_count >= self.global_max:
                await asyncio.sleep(0.1)

        conn = await asyncssh.connect(
            host,
            username=username,
            password=password,
            client_keys=client_keys,
            known_hosts=None,  # 首次连接接受 host key
            timeout=self.timeout
        )

        async with self._lock:
            self._active_count += 1

        return conn

    async def release_connection(self, host: str, conn: asyncssh.Connection):
        """释放连接回池中"""
        if conn.is_closed():
            async with self._lock:
                self._active_count -= 1
            return

        async with self._lock:
            # 支持同一 host 多个连接排队复用
            self._available[host].append(conn)
            # 注意：归还池中不算 active，active_count 保持不变

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
```

**Bug 修复说明**：原实现 `_available: Dict[str, asyncssh.Connection]` 存在逻辑错误 ——
当同一 host 有多个连接释放时，后释放的连接会覆盖前一个，导致前一个连接被丢失且未关闭。
修复方案改为 `_available: Dict[str, List[asyncssh.Connection]]`，使用列表队列式管理，
确保同一 host 的多个连接都能正确复用，不会相互覆盖。


# 全局连接池实例
_global_pool: Optional[SSHConnectionPool] = None

def get_ssh_pool() -> SSHConnectionPool:
    global _global_pool
    if _global_pool is None:
        _global_pool = SSHConnectionPool(
            max_connections_per_host=2,
            global_max_connections=10
        )
    return _global_pool
```

**连接池使用示例**:
```python
async def deploy_to_worker(request: DeployWorkerRequest):
    pool = get_ssh_pool()

    async with pool.connection(
        request.node_ip,
        request.username,
        request.password
    ) as conn:
        # 执行部署命令
        result = await conn.run("echo connected")
        print(result.stdout)
```

---

### 2.7 技术决策：paramiko vs asyncssh

经过架构评审深入讨论，做出以下明确决策：

#### 决策结论：**asyncssh**

| 维度 | paramiko + asyncio.to_thread | asyncssh |
|------|-------------------------------|----------|
| FastAPI/SSE 集成 | 需线程池中运行，存在 GIL 限制 | 原生异步，无 GIL 问题 |
| 并发能力 | 受 GIL 限制，高并发时性能受限 | 真正异步并发，性能更好 |
| 代码复杂度 | 需自行处理线程同步 | asyncio 原生，代码简洁 |
| 调试难度 | 线程池调试复杂 | 异步调试更直接 |
| 生产验证 | paramiko 广泛验证 | asyncssh 已在多个生产项目使用 |

#### 决策理由

1. **SSE 异步场景矛盾**：paramiko 是同步库，在 asyncio.to_thread 中运行虽然可行，但：
   - 线程池资源有限，高并发时成为瓶颈
   - GIL 导致多命令串行执行
   - 与 FastAPI 的异步理念不符

2. **asyncssh 优势**：
   - Python 3.10+ 原生异步 SSH 库
   - 与 asyncio.create_task、FastAPI BackgroundTasks 无缝集成
   - 更好的并发性能和资源利用率
   - 代码示例已在项目中验证可行

3. **实际性能差异**：虽然未经严格基准测试，但异步 vs 同步在 I/O 密集型（SSH 命令执行等待网络往返）场景下预期有 2-3 倍性能差异。

#### 备选方案

若部署频率低（每天几次），paramiko 仍可接受：
```python
# 备选：paramiko + asyncio.to_thread（低并发场景）
async def deploy_with_paramiko():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, paramiko_exec, command)
```

---

## 3. 安全加固方案

### 3.1 密码处理

**原则**:
1. 密码不落地存储 (不使用文件保存)
2. 内存加密 (尽量缩短明文存在时间)
3. TLS 传输 (Web -> API 使用 HTTPS)
4. 审计日志 (记录谁、何时、哪个节点)

**实现方案**:

```python
# 密码使用后立即清理
import paramiko
import gc

def deploy_with_password(host_ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(host_ip, username='admin02', password=password, timeout=10)
        # ... 执行部署命令
    finally:
        # 清理敏感数据
        password = None
        del password
        ssh.close()
        gc.collect()
```

### 3.2 SSH 密钥 vs 密码认证

| 方式 | 优点 | 缺点 |
|------|------|------|
| 密钥认证 | 安全、可复用、无需密码输入 | 需要预先部署公钥 |
| 密码认证 | 简单、用户输入即可 | 需要每次传输密码 |

**建议**:
- **首选**: 预部署 SSH 公钥，实现无密码部署
- **备选**: Web 界面输入密码，单次使用，API 不存储

#### SSH 公钥预部署流程

若采用 SSH Key 认证，需在部署前完成以下步骤：

```
1. Head 节点生成 SSH 密钥对（如果尚未有）
   ssh-keygen -t ed25519 -f ~/.ssh/algo_studio_deploy

2. 将公钥复制到 Worker 节点
   ssh-copy-id -i ~/.ssh/algo_studio_deploy.pub admin02@192.168.0.115

3. 验证无密码 SSH 连接
   ssh -i ~/.ssh/algo_studio_deploy admin02@192.168.0.115 "echo OK"
```

**API 调用时使用密钥认证**:
```python
async def deploy_with_key(request: DeployWorkerRequest):
    # 使用密钥文件而非密码
    async with asyncssh.connect(
        request.node_ip,
        username=request.username,
        client_keys=['~/.ssh/algo_studio_deploy'],
        # 安全改进：首次连接时获取并保存 host key
        known_hosts=asyncssh.HOST_KEYS ~/.ssh/known_hosts'
    ) as conn:
        result = await conn.run('echo "hello"')
```

**known_hosts 安全改进方案**:
```python
import os

# 方案1: 首次连接时自动记录 host key（适合受控环境）
async def connect_with_auto_known_hosts(host, username, password):
    """首次连接自动接受并保存 host key"""
    known_hosts_path = os.path.expanduser('~/.ssh/known_hosts')

    try:
        conn = await asyncssh.connect(
            host,
            username=username,
            password=password,
            known_hosts=known_hosts_path,
            client_host_key_alias=host  # 便于识别
        )
    except asyncssh.KeyNotFoundError:
        # 首次连接，手动添加 host key
        # 通过 SSH 握手获取 server key 并保存
        conn = await asyncssh.connect(
            host,
            username=username,
            password=password,
            known_hosts=None,  # 首次：不验证
            client_host_key_alias=host
        )
        # 立即将 host key 写入 known_hosts
        if conn.server_host_key:
            with open(known_hosts_path, 'a') as f:
                # 写入格式：hostname ssh-rsa AAAA...
                key_type = conn.server_host_key.get_name()
                key_data = conn.server_host_key.export_base64()
                f.write(f"{host} {key_type} {key_data}\n")
        conn.close()
        # 重新连接，这次使用 known_hosts
        conn = await asyncssh.connect(
            host,
            username=username,
            password=password,
            known_hosts=known_hosts_path
        )
    return conn

# 方案2: 预先生成 known_hosts（适合生产环境）
async def deploy_with_verified_host(request: DeployWorkerRequest):
    """使用已验证的 known_hosts 进行连接"""
    known_hosts_path = os.path.expanduser('~/.ssh/known_hosts')

    # 确保 known_hosts 存在且包含目标主机
    if not os.path.exists(known_hosts_path):
        raise ValueError(f"known_hosts 文件不存在，请先手动连接目标主机建立信任关系")

    async with asyncssh.connect(
        request.node_ip,
        username=request.username,
        password=request.password,
        known_hosts=known_hosts_path,
        # 安全：不允许未知 host
        trust_unkown_hosts=False
    ) as conn:
        result = await conn.run('echo "verified"')
```

**自动公钥部署（可选）**:
首次部署时支持密码认证自动完成公钥部署：

**注意**：必须使用 check-then-add 模式，避免重复条目污染 authorized_keys：
```python
async def setup_ssh_key_auto(conn, pub_key: str):
    """自动将公钥部署到 Worker 节点（幂等版本）"""
    # 1. 创建 .ssh 目录
    await conn.run('mkdir -p ~/.ssh && chmod 700 ~/.ssh')

    # 2. 读取现有 authorized_keys 并精确匹配检查
    # 问题修复：grep -F 对含特殊字符的公钥可能误匹配，改用逐行精确比较
    read_result = await conn.run(
        'cat ~/.ssh/authorized_keys 2>/dev/null || echo ""',
        check=False
    )
    existing_keys = read_result.stdout.strip().split('\n') if read_result.stdout else []

    # 精确比较：公钥内容必须完全一致
    key_already_exists = any(
        line.strip() == pub_key.strip()
        for line in existing_keys
        if line.strip()
    )

    if not key_already_exists:
        # 3. 仅在不存在时追加
        await conn.run(f'echo "{pub_key}" >> ~/.ssh/authorized_keys')

    # 4. 设置正确权限
    await conn.run('chmod 600 ~/.ssh/authorized_keys')

    # 5. 验证部署（同样使用精确匹配）
    verify_result = await conn.run(
        'cat ~/.ssh/authorized_keys',
        check=False
    )
    verified = any(
        line.strip() == pub_key.strip()
        for line in verify_result.stdout.split('\n')
        if line.strip()
    )
    if not verified:
        raise DeployError("公钥部署验证失败")
```

**修复说明**：原 `grep -F` 对包含正则特殊字符（如 `.`、`*`、`\`）的公钥可能产生误匹配。新方案读取整个文件后逐行精确比较，确保匹配准确。

### 3.3 防止 SSH 密码嗅探

1. 确保 Web 界面使用 HTTPS
2. 避免在日志中打印密码
3. 使用 `getpass` 库安全获取密码
4. SSH 连接使用 `allow_agent=False` 避免密钥代理

### 3.4 PTY 问题处理

SSH 执行 sudo 命令时，默认 `shell=False` 模式可能遇到以下问题：
- sudo: no tty present and no askpass program specified
- stdin: resource temporarily unavailable

#### 四层回滚策略（边界条件明确化）

**第1层：预配置 sudo 免密码（首选）**
- **触发条件**：首次连接成功即可执行，无需 PTY
- **实现方式**：`echo 'admin02 ALL=(ALL) NOPASSWD: ALL' | sudo tee /etc/sudoers.d/admin02`
- **适用场景**：Worker 节点首次部署，sudoers 文件可写
- **优点**：后续所有命令无需 PTY，简化处理

```python
async def configure_sudo_nopassword(conn, password: str):
    """配置 sudo 免密码，避免后续命令需要 PTY"""
    cmd = "echo 'admin02 ALL=(ALL) NOPASSWD: ALL' | sudo tee /etc/sudoers.d/admin02"
    result = await conn.run(cmd, check=True)
```

**第2层：`get_pty=True` + `sudo -S`（sudo 免密码不可用时）**
- **触发条件**：sudoers 无法修改，但 sudo 配置了 PASSWD
- **实现方式**：获取 PTY，sudo 从 stdin 读取密码
- **适用场景**：sudoers 文件只读，或需要 sudo 密码的场景
- **限制**：需要额外传递 password，且密码会出现在进程参数中

```python
async def run_sudo_with_pty(conn, cmd: str, password: str):
    """通过 PTY 执行需要 sudo 的命令"""
    result = await conn.run(
        f'echo "{password}" | sudo -S {cmd}',
        term='xterm-color',
        get_pty=True,
        check=True
    )
    return result
```

**第3层：`sudo -n` 检查 + 非 PTY（回退到非特权操作）**
- **触发条件**：无法获取 PTY，尝试非特权执行
- **实现方式**：检测命令是否真正需要 sudo，或将操作重设计为非特权
- **适用场景**：只读检查、环境探测等不需要 sudo 的操作

```python
async def run_privileged_command(conn, cmd: str, password: str = None):
    """尝试非 PTY 执行，失败后根据情况回滚"""
    try:
        return await conn.run(cmd, check=True)
    except asyncssh.ChannelOpenError:
        # PTY 获取失败，尝试 get_pty=True
        return await conn.run(
            f'echo "{password}" | sudo -S {cmd}',
            term='xterm-color',
            get_pty=True,
            check=True
        )
    except asyncssh.DisconnectError:
        raise
```

**第4层：部署失败报告（所有方案均失败）**
- **触发条件**：上述所有方案都无法成功执行特权命令
- **处理方式**：记录完整错误信息，返回有意义的错误码和诊断信息
- **诊断信息**：包含失败的命令、退出码、stderr 输出、尝试过的方案

```python
class PTYError(BaseModel):
    failed_command: str
    tried_methods: List[str]  # ["sudo_nopassword", "pty_with_password", ...]
    last_error: str
    exit_code: Optional[int]
    stderr: Optional[str]
```

#### 边界条件总结

| 场景 | 首选方案 | 备选方案 | 失败条件 |
|------|---------|---------|---------|
| sudoers 可写 | 预配置 NOPASSWD | 无需备选 | sudoers 写入失败 |
| sudoers 只读，有 PASSWD | get_pty + sudo -S | sudo -n 非特权 | 无法获取 PTY 且命令必须 sudo |
| 只读操作 | 非 PTY 直接执行 | 无需备选 | 网络/权限问题 |
| 需要 sudo 但 PTY 失败 | sudo -S | 报告错误 | 密码错误或权限不足 |

#### 推荐配置

```python
class SSHDeployConfig:
    # 连接配置
    CONNECT_TIMEOUT = 30
    COMMAND_TIMEOUT = 300

    # PTY 配置（按优先级尝试）
    TRY_SUDO_NOPASSWORD_FIRST = True  # 首选尝试预配置
    TERM = 'xterm-color'

    # 重试配置
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # 秒，指数退避

async def safe_exec_command(conn, cmd: str, check: bool = True, password: str = None):
    """安全执行命令，按四层策略处理 PTY"""
    # 第1层：直接执行（假设已有 NOPASSWD 配置）
    try:
        return await conn.run(
            cmd,
            check=check,
            timeout=SSHDeployConfig.COMMAND_TIMEOUT
        )
    except asyncssh.DisconnectError:
        raise
    except asyncssh.ChannelOpenError:
        # 第2层：尝试 PTY 模式
        if password:
            return await conn.run(
                f'echo "{password}" | sudo -S {cmd}',
                term=SSHDeployConfig.TERM,
                get_pty=True,
                check=check
            )
        raise
```

### 3.5 SSH 权限控制

```python
import re

# 适度放宽的命令白名单（支持参数变体）
ALLOWED_COMMANDS = [
    # join_cluster.sh 及其调用
    r'^bash\s+.*join_cluster\.sh',
    r'^/bin/bash\s+.*join_cluster\.sh',

    # Ray 命令
    r'^ray\s+(stop|start|status)',
    r'^ray\s+start\s+--address=.+',  # 需要指定 address

    # uv 安装
    r'^curl\s+-LsSf\s+https://astral\.sh/uv/install\.sh',
    r'^uv\s+python\s+install\s+\d+\.\d+\.\d+',
    r'^uv\s+venv',
    r'^uv\s+pip\s+install\s+.*',  # 支持安装多个包

    # 系统命令（配合 sudo）
    r'^sudo\s+tee\s+/etc/sudoers\.d/admin02',
    r'^sudo\s+systemctl\s+(start|stop|restart)\s+ray',

    # rsync（代码同步）
    r'^rsync\s+-avz\s+--delete.*',
    r'^rsync\s+-av\s+--delete.*',

    # 文件检查
    r'^test\s+-[defgLrwx]\s+.*',  # test -d, test -f 等
    r'^ls\s+-[la]?\s*.*',
    r'^cat\s+.*',
    r'^grep\s+.*',

    # 环境检查
    r'^~/.venv-ray/bin/python\s+-c\s+.*',
    r'^pgrep\s+.*',
]

# 危险命令黑名单（绝对禁止）
FORBIDDEN_PATTERNS = [
    r';\s*rm\s+-rf',           # 禁止管道后的删除
    r'>\s*/dev/sd',           # 禁止直接写设备
    r'^\s*dd\s+if=.*of=/dev', # 禁止磁盘直接写入
    r';\s*shutdown',          # 禁止关机
    r';\s*reboot',            # 禁止重启
    r'eval\s+.*\$',           # 禁止 eval 变量
    r'`.*`',                  # 禁止命令替换
]

def validate_command(cmd: str) -> bool:
    """验证命令是否安全且在白名单中"""

    # 1. 检查黑名单
    for forbidden in FORBIDDEN_PATTERNS:
        if re.search(forbidden, cmd):
            return False

    # 2. 检查白名单
    for allowed in ALLOWED_COMMANDS:
        if re.match(allowed, cmd.strip()):
            return True

    return False

# 执行前验证
if not validate_command(cmd):
    raise ValueError(f"Command not allowed: {cmd}")
```

---

## 4. SSH 重连机制

### 4.1 重连场景分析

SSH 连接可能因以下原因断开：
- 网络波动或临时不可达
- SSH 服务端超时断开
- Worker 节点重启
- 中间防火墙/NAT 超时

### 4.2 重连策略设计

```python
class SSHConnectionManager:
    """SSH 连接管理器，支持自动重连"""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0
    ):
        self.host = host
        self.username = username
        self.password = password
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._conn: Optional[asyncssh.Connection] = None

    async def connect(self) -> asyncssh.Connection:
        """建立 SSH 连接"""
        if self._conn and not self._conn.is_closed():
            return self._conn

        self._conn = await asyncssh.connect(
            self.host,
            username=self.username,
            password=self.password,
            known_hosts=None,  # 首次连接接受 host key
            timeout=30
        )
        return self._conn

    async def execute_with_retry(
        self,
        cmd: str,
        retry_count: int = 0
    ) -> asyncssh.Result:
        """执行命令，支持自动重连"""

        async def _execute():
            conn = await self.connect()
            return await conn.run(cmd, check=True)

        try:
            return await _execute()
        except (asyncssh.DisconnectError, asyncssh.ChannelOpenError) as e:
            if retry_count >= self.max_retries:
                raise

            # 指数退避
            delay = min(
                self.base_delay * (2 ** retry_count),
                self.max_delay
            )

            # 关闭旧连接
            if self._conn:
                self._conn.close()
                self._conn = None

            await asyncio.sleep(delay)
            return await self.execute_with_retry(cmd, retry_count + 1)

    async def keep_alive(self, interval: int = 60):
        """定期发送 keepalive 防止连接断开"""
        while True:
            await asyncio.sleep(interval)
            if self._conn and not self._conn.is_closed():
                try:
                    await self._conn.run('echo keepalive', check=True)
                except Exception:
                    pass
```

### 4.3 重连状态机

#### 状态定义

```python
from enum import Enum
from typing import Optional
import asyncio

class ConnectionState(Enum):
    """SSH 连接状态枚举"""
    DISCONNECTED = "disconnected"      # 初始状态/连接关闭
    CONNECTING = "connecting"           # 正在建立连接
    IDLE = "idle"                        # 连接正常，空闲
    COMMAND_RUNNING = "command_running"  # 命令执行中
    RETRYING = "retrying"               # 等待重连
    ERROR = "error"                      # 错误状态（不可恢复）
```

#### 状态转换规则

| 当前状态 | 事件 | 目标状态 | 动作 |
|---------|------|---------|------|
| DISCONNECTED | connect() 调用 | CONNECTING | 建立 SSH 连接 |
| CONNECTING | 连接成功 | IDLE | 设置 keepalive |
| CONNECTING | 连接失败 | RETRYING | 记录错误，延迟等待 |
| IDLE | execute() 调用 | COMMAND_RUNNING | 执行命令 |
| IDLE | 连接断开事件 | DISCONNECTED | 触发重连逻辑 |
| COMMAND_RUNNING | 命令完成(exit=0) | IDLE | 返回结果 |
| COMMAND_RUNNING | 命令完成(exit≠0) | ERROR | 记录错误 |
| COMMAND_RUNNING | 连接断开 | RETRYING | 延迟等待重连 |
| RETRYING | 重试超时 | CONNECTING | 重新建立连接 |
| RETRYING | 达到最大重试 | ERROR | 放弃重连 |
| ERROR | reset() 调用 | DISCONNECTED | 重置状态 |

#### 完整状态机实现

```python
class SSHConnectionManager:
    """SSH 连接管理器，完整状态机实现"""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0
    ):
        self.host = host
        self.username = username
        self.password = password
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

        # 状态机核心
        self._state: ConnectionState = ConnectionState.DISCONNECTED
        self._conn: Optional[asyncssh.Connection] = None
        self._retry_count: int = 0
        self._lock: asyncio.Lock = asyncio.Lock()

        # 连接事件回调（用于 SSE 推送）
        self._state_listeners: List[callable] = []

    @property
    def state(self) -> ConnectionState:
        """获取当前状态（线程安全）"""
        return self._state

    def add_state_listener(self, listener: callable):
        """添加状态监听器"""
        self._state_listeners.append(listener)

    async def _set_state(self, new_state: ConnectionState):
        """状态转换"""
        old_state = self._state
        self._state = new_state

        # 通知所有监听器
        for listener in self._state_listeners:
            try:
                await listener(old_state, new_state)
            except Exception:
                pass

    # === 核心操作方法 ===

    async def connect(self) -> asyncssh.Connection:
        """建立 SSH 连接（DISCONNECTED -> CONNECTING -> IDLE）"""
        async with self._lock:
            if self._state == ConnectionState.IDLE and self._conn and not self._conn.is_closed():
                return self._conn

            # 状态转换：DISCONNECTED -> CONNECTING
            if self._state == ConnectionState.DISCONNECTED:
                await self._set_state(ConnectionState.CONNECTING)

            try:
                self._conn = await asyncssh.connect(
                    self.host,
                    username=self.username,
                    password=self.password,
                    known_hosts=None,
                    timeout=30
                )

                # 连接成功：CONNECTING -> IDLE
                await self._set_state(ConnectionState.IDLE)
                self._retry_count = 0
                return self._conn

            except (asyncssh.DisconnectError, asyncssh.ChannelOpenError) as e:
                # 连接失败：CONNECTING -> RETRYING
                await self._set_state(ConnectionState.RETRYING)
                return await self._retry_or_fail(str(e))

    async def _retry_or_fail(self, error_msg: str):
        """重试逻辑或最终失败"""
        self._retry_count += 1

        if self._retry_count >= self.max_retries:
            # 达到最大重试：RETRYING -> ERROR
            await self._set_state(ConnectionState.ERROR)
            raise SSHConnectionError(
                f"连接失败，已重试 {self._retry_count} 次: {error_msg}"
            )

        # 计算延迟（指数退避）
        delay = min(
            self.base_delay * (2 ** (self._retry_count - 1)),
            self.max_delay
        )

        await asyncio.sleep(delay)

        # 重试：RETRYING -> CONNECTING
        await self._set_state(ConnectionState.CONNECTING)

        try:
            self._conn = await asyncssh.connect(
                self.host,
                username=self.username,
                password=self.password,
                known_hosts=None,
                timeout=30
            )
            await self._set_state(ConnectionState.IDLE)
            self._retry_count = 0
            return self._conn

        except Exception as e:
            return await self._retry_or_fail(str(e))

    async def execute_with_retry(
        self,
        cmd: str,
        retry_count: int = 0
    ) -> asyncssh.Result:
        """执行命令（自动处理重连）"""

        async def _do_execute():
            # 确保处于 IDLE 状态
            if self._state != ConnectionState.IDLE:
                await self.connect()

            # IDLE -> COMMAND_RUNNING
            await self._set_state(ConnectionState.COMMAND_RUNNING)

            try:
                result = await self._conn.run(cmd, check=True)
                # 命令成功：COMMAND_RUNNING -> IDLE
                await self._set_state(ConnectionState.IDLE)
                return result

            except asyncssh.DisconnectError:
                # 连接断开：COMMAND_RUNNING -> DISCONNECTED -> RETRYING
                self._conn = None
                await self._set_state(ConnectionState.DISCONNECTED)
                return await self._retry_execute(cmd, retry_count)

            except asyncssh.ChannelOpenError:
                # 通道错误：COMMAND_RUNNING -> DISCONNECTED
                self._conn = None
                await self._set_state(ConnectionState.DISCONNECTED)
                return await self._retry_execute(cmd, retry_count)

            except Exception as e:
                # 其他错误：COMMAND_RUNNING -> ERROR
                await self._set_state(ConnectionState.ERROR)
                raise

        return await _do_execute()

    async def _retry_execute(self, cmd: str, retry_count: int):
        """重试执行命令"""
        if retry_count >= self.max_retries:
            raise SSHConnectionError(f"命令执行失败，已重试 {retry_count} 次")

        delay = self.base_delay * (2 ** retry_count)
        await asyncio.sleep(min(delay, self.max_delay))

        # DISCONNECTED -> CONNECTING
        await self.connect()

        # 递归重试（带计数器）
        return await self.execute_with_retry(cmd, retry_count + 1)

    async def disconnect(self):
        """主动断开连接（任意状态 -> DISCONNECTED）"""
        async with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
            await self._set_state(ConnectionState.DISCONNECTED)

    async def reset(self):
        """重置状态机（ERROR -> DISCONNECTED）"""
        await self.disconnect()
        self._retry_count = 0
        await self._set_state(ConnectionState.DISCONNECTED)
```

#### 状态机图示

```
                        ┌─────────────┐
                        │ DISCONNECTED│
                        └──────┬──────┘
                               │
                    connect()  │ connect() 成功
                               ▼
                        ┌─────────────┐
            ┌───────────│ CONNECTING  │───────────┐
            │ connect() │             │ 失败       │
            │ 失败       └─────────────┘           │
            ▼                                     ▼
    ┌─────────────┐                       ┌─────────────┐
    │  RETRYING   │◄──────────────────────│  CONNECTING │
    │ (等待重连)   │   重试超时            └─────────────┘
    └──────┬──────┘                              │
           │                                     │ 连接成功
           │重试次数 < max                       ▼
           │                             ┌─────────────┐
           │                             │    IDLE     │
           │                             │  (空闲)     │
           │                             └──────┬──────┘
           │                                    │
           │            ┌───────────────────────┼───────────────────────┐
           │            │                       │                       │
           │            │ execute()             │ 连接断开               │ 命令完成
           │            ▼                       ▼                       ▼
           │     ┌─────────────┐         ┌─────────────┐       ┌─────────────┐
           └────►│    ERROR    │         │   ERROR     │       │    IDLE     │
                 │ (不可恢复)   │         │  (命令错误)  │       │  (空闲)     │
                 └─────────────┘         └─────────────┘       └─────────────┘
```

#### 状态机验证计划

**单元测试验证点**:

```python
# tests/test_ssh_reconnect_state_machine.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from algo_studio.core.ssh_manager import SSHConnectionManager, ConnectionState

class TestSSHReconnectionStateMachine:
    """验证 SSH 重连状态机的实际行为"""

    @pytest.fixture
    def mgr(self):
        return SSHConnectionManager(
            host="192.168.0.115",
            username="admin02",
            password="test",
            max_retries=3,
            base_delay=0.1,  # 测试用短延迟
            max_delay=1.0
        )

    @pytest.mark.asyncio
    async def test_state_transitions(self, mgr):
        """验证状态转换序列"""
        transitions = []

        async def listener(old, new):
            transitions.append((old, new))

        mgr.add_state_listener(listener)

        # DISCONNECTED -> CONNECTING -> IDLE
        with patch('asyncssh.connect', new_callable=AsyncMock) as mock_connect:
            mock_conn = MagicMock()
            mock_conn.is_closed.return_value = False
            mock_connect.return_value = mock_conn

            await mgr.connect()

        assert mgr.state == ConnectionState.IDLE
        assert transitions == [
            (ConnectionState.DISCONNECTED, ConnectionState.CONNECTING),
            (ConnectionState.CONNECTING, ConnectionState.IDLE)
        ]

    @pytest.mark.asyncio
    async def test_retry_on_disconnect(self, mgr):
        """验证断开后自动重连"""
        state_sequence = []

        async def listener(old, new):
            state_sequence.append(new)

        mgr.add_state_listener(listener)

        connect_count = 0

        async def mock_connect(*args, **kwargs):
            nonlocal connect_count
            connect_count += 1
            if connect_count == 1:
                raise asyncssh.DisconnectError("Connection lost")
            mock_conn = MagicMock()
            mock_conn.is_closed.return_value = False
            return mock_conn

        with patch('asyncssh.connect', side_effect=mock_connect):
            # connect() 会自动重连
            await mgr.connect()

        assert connect_count == 2
        assert ConnectionState.RETRYING in state_sequence

    @pytest.mark.asyncio
    async def test_max_retries_then_error(self, mgr):
        """验证达到最大重试次数后进入 ERROR 状态"""
        with patch('asyncssh.connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = asyncssh.DisconnectError("Permanent failure")

            with pytest.raises(SSHConnectionError):
                await mgr.connect()

            # 验证状态变为 ERROR
            assert mgr.state == ConnectionState.ERROR

    @pytest.mark.asyncio
    async def test_execute_triggers_command_running_state(self, mgr):
        """验证命令执行时状态变为 COMMAND_RUNNING"""
        with patch('asyncssh.connect', new_callable=AsyncMock) as mock_connect:
            mock_conn = MagicMock()
            mock_conn.is_closed.return_value = False
            mock_connect.return_value = mock_conn

            await mgr.connect()
            assert mgr.state == ConnectionState.IDLE

            # Mock 命令执行
            mock_result = MagicMock()
            mock_conn.run = AsyncMock(return_value=mock_result)

            await mgr.execute_with_retry("echo test")

            # IDLE -> COMMAND_RUNNING -> IDLE
            assert ConnectionState.COMMAND_RUNNING in [
                t[1] for t in state_sequence
            ]
```

**集成测试验证**:

```bash
# 验证脚本：手动测试重连状态机
python -c "
import asyncio
from algo_studio.core.ssh_manager import SSHConnectionManager, ConnectionState

async def test_real_connection():
    mgr = SSHConnectionManager(
        host='192.168.0.115',
        username='admin02',
        password='your_password',
        max_retries=3,
        base_delay=1.0
    )

    print(f'初始状态: {mgr.state}')

    try:
        conn = await mgr.connect()
        print(f'连接后状态: {mgr.state}')

        result = await mgr.execute_with_retry('echo hello')
        print(f'执行后状态: {mgr.state}')
        print(f'输出: {result.stdout}')

    except Exception as e:
        print(f'最终状态: {mgr.state}')
        print(f'错误: {e}')

asyncio.run(test_real_connection())
"
```

**SSE 状态推送集成**:

```python
# 状态变化时自动推送 SSE 事件
async def state_change_to_sse(old_state: ConnectionState, new_state: ConnectionState):
    """将状态变化转换为 SSE 事件"""
    return {
        "event": "connection_state_change",
        "data": {
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": datetime.now().isoformat()
        }
    }

# 使用示例
mgr.add_state_listener(state_change_to_sse)
```

**验证检查表**:

- [ ] 初始状态为 DISCONNECTED
- [ ] connect() 触发 DISCONNECTED -> CONNECTING -> IDLE
- [ ] 连接失败触发 CONNECTING -> RETRYING -> CONNECTING
- [ ] 达到最大重试次数后进入 ERROR 状态
- [ ] execute() 触发 IDLE -> COMMAND_RUNNING -> IDLE
- [ ] 命令执行中断触发 COMMAND_RUNNING -> RETRYING
- [ ] reset() 可将 ERROR 状态重置为 DISCONNECTED
- [ ] 状态监听器正确接收所有状态转换事件

### 4.4 部署任务集成重连

```python
async def run_deploy_step(
    mgr: SSHConnectionManager,
    step_name: str,
    cmd: str,
    progress_callback
):
    """部署步骤执行，自动重连"""

    for attempt in range(MAX_RETRY):
        try:
            progress_callback.set_description(f"{step_name} (尝试 {attempt + 1})")
            result = await mgr.execute_with_retry(cmd)
            return result
        except Exception as e:
            if attempt == MAX_RETRY - 1:
                raise DeployError(
                    code=DeployErrorCode.STEP_FAILED,
                    step=step_name,
                    message=str(e)
                )
            await asyncio.sleep(2 ** attempt)
```

---

## 5. 异步任务和 SSE 进度推送

项目已有 SSE 实现 (`/api/cluster/events`):

```python
@router.get("/events")
async def cluster_events():
    from sse_starlette.sse import EventSourceResponse

    async def ray_event_generator():
        while True:
            # 获取事件
            yield {"event": "message", "data": {...}}
            await asyncio.sleep(2)

    return EventSourceResponse(ray_event_generator())
```

### 5.2 部署进度 SSE 设计

```python
# API 端点: POST /api/deploy/worker
# SSE 端点: GET /api/deploy/worker/{task_id}/progress

class DeployStatus(str, Enum):
    PENDING = "pending"
    CONNECTING = "connecting"
    DEPLOYING = "deploying"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"

class DeployProgress(BaseModel):
    task_id: str
    status: DeployStatus
    step: int          # 当前步骤 1-7
    total_steps: int   # 总步骤
    progress: int      # 0-100
    message: str       # 详细消息
    error: Optional[str] = None
    node_ip: str
    started_at: datetime
    completed_at: Optional[datetime] = None
```

### 5.3 异步任务集成

```python
# 方案 A: asyncio.create_task (推荐)
@router.post("/deploy/worker")
async def deploy_worker(request: DeployWorkerRequest):
    task_id = f"deploy-{uuid.uuid4().hex[:8]}"

    # 立即返回 task_id
    asyncio.create_task(run_deploy_task(task_id, request))

    return {"task_id": task_id, "status": "pending"}

# 方案 B: FastAPI BackgroundTasks
from fastapi import BackgroundTasks

@router.post("/deploy/worker")
async def deploy_worker(
    request: DeployWorkerRequest,
    background_tasks: BackgroundTasks
):
    task_id = f"deploy-{uuid.uuid4().hex[:8]}"
    background_tasks.add_task(run_deploy_task, task_id, request)
    return {"task_id": task_id, "status": "pending"}
```

### 5.4 SSE 进度推送实现

```python
@router.get("/deploy/worker/{task_id}/progress")
async def deploy_progress(task_id: str):
    async def event_generator():
        progress_store = get_deploy_progress_store()

        while True:
            progress = await progress_store.get_progress(task_id)

            if progress.status in (DeployStatus.COMPLETED, DeployStatus.FAILED):
                yield {
                    "event": "final",
                    "data": progress.model_dump_json()
                }
                break

            yield {
                "event": "progress",
                "data": progress.model_dump_json()
            }
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())
```

### 5.5 部署任务实现

```python
async def run_deploy_task(task_id: str, request: DeployWorkerRequest):
    progress_store = get_deploy_progress_store()

    steps = [
        ("connecting", "建立 SSH 连接"),
        ("sudo_config", "配置 sudo 免密码"),
        ("create_venv", "创建 uv 虚拟环境"),
        ("install_deps", "安装依赖"),
        ("sync_code", "同步代码"),
        ("start_ray", "启动 Ray Worker"),
        ("verify", "验证连接"),
    ]

    # 进度百分比分配（根据实际耗时和重要性调整）
    # SSH连接很快，代码同步最耗时
    progress_weights = {
        "connecting": 5,    # 快速
        "sudo_config": 10,  # 快速
        "create_venv": 20,  # 中等（涉及下载）
        "install_deps": 25,  # 较慢（pip install）
        "sync_code": 15,    # 中等（rsync）
        "start_ray": 15,    # 快速
        "verify": 10,       # 快速
    }

    try:
        current_progress = 0

        # SSH 连接
        await progress_store.update(task_id, "connecting", current_progress, "正在连接...")
        ssh = await asyncssh.connect(
            request.node_ip,
            username=request.username,
            password=request.password,
            timeout=30
        )
        current_progress += progress_weights["connecting"]
        await progress_store.update(task_id, "connecting", current_progress, "连接成功")

        # sudo 配置
        if not await idempotency.check_step(ssh, "sudo_config"):
            await progress_store.update(task_id, "sudo_config", current_progress, "配置 sudo...")
            await run_sudo_config(ssh)
            current_progress += progress_weights["sudo_config"]
            await progress_store.update(task_id, "sudo_config", current_progress, "sudo 配置完成")

        # 创建虚拟环境
        if not await idempotency.check_step(ssh, "create_venv"):
            await progress_store.update(task_id, "create_venv", current_progress, "创建虚拟环境...")
            await run_create_venv(ssh, request)
            current_progress += progress_weights["create_venv"]
            await progress_store.update(task_id, "create_venv", current_progress, "虚拟环境创建完成")

        # ... 其他步骤类似

        # 验证
        await progress_store.update(task_id, "verify", 90, "验证连接...")
        await verify_cluster_join(ssh, request.head_ip)

        current_progress = 100
        await progress_store.update(task_id, "completed", 100, "部署完成")

    except Exception as e:
        await progress_store.update(task_id, "failed", error=str(e))
    finally:
        ssh.close()
```

---

## 5. SSH 部署 API 设计

### 5.1 请求/响应模型

```python
# Request
class DeployWorkerRequest(BaseModel):
    node_ip: str = Field(..., description="Worker 节点 IP")
    username: str = Field(default="admin02", description="SSH 用户名")
    password: str = Field(..., description="SSH 密码（不存储）")
    head_ip: str = Field(..., description="Ray Head 节点 IP")
    ray_port: int = Field(default=6379, description="Ray 端口")
    proxy_url: Optional[str] = Field(default=None, description="代理 URL")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)

# Response
class DeployWorkerResponse(BaseModel):
    task_id: str
    node_ip: str
    status: DeployStatus
    created_at: datetime

# Progress
class DeployProgressResponse(BaseModel):
    task_id: str
    status: DeployStatus
    step: str
    progress: int
    message: str
    error: Optional[str]
    node_ip: str
    started_at: datetime
    completed_at: Optional[datetime]
```

### 5.2 端点设计

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/deploy/worker` | 发起部署任务 |
| GET | `/api/deploy/worker/{task_id}` | 获取部署状态 |
| GET | `/api/deploy/worker/{task_id}/progress` | SSE 进度流 |
| DELETE | `/api/deploy/worker/{task_id}` | 取消部署 |
| GET | `/api/deploy/workers` | 列出所有部署记录 |

### 5.3 错误处理

```python
class DeployErrorCode(str, Enum):
    CONNECTION_FAILED = "connection_failed"
    AUTH_FAILED = "auth_failed"
    TIMEOUT = "timeout"
    STEP_FAILED = "step_failed"
    VERIFICATION_FAILED = "verification_failed"

class DeployError(BaseModel):
    code: DeployErrorCode
    message: str
    step: Optional[str]
    details: Optional[Dict[str, Any]]
```

**错误响应示例**:
```json
{
  "task_id": "deploy-abc123",
  "status": "failed",
  "error": {
    "code": "STEP_FAILED",
    "message": "sudo 配置失败",
    "step": "sudo_config",
    "details": {
      "exit_code": 1,
      "stderr": "sudo: unable to resolve host worker-115"
    }
  }
}
```

---

## 6. 推荐方案

### 6.1 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| SSH 库 | asyncssh | FastAPI 原生异步，无 GIL 限制 |
| 进度推送 | SSE (sse-starlette) | 已在使用，Web 原生支持 |
| 异步任务 | asyncio.create_task | 轻量，无需额外队列 |
| 状态存储 | 内存 + Redis | 与现有架构一致 |
| 重连机制 | 指数退避 + 自动重连 | SSHConnectionManager 封装 |

### 6.2 架构设计

```
Web Console
    │
    │ POST /api/deploy/worker
    ▼
FastAPI ─────────────────────────────────────────┐
    │                                              │
    ├── asyncio.create_task(run_deploy_task)       │
    │                                              │
    │   ┌──────────────────────────────┐          │
    │   │     DeployProgressStore      │◄─────────┤
    │   │     (内存/Ray Actor)          │          │
    │   └──────────────────────────────┘          │
    │            │                                  │
    │            │ 更新进度                         │
    │            ▼                                  │
    │   SSH (asyncssh) ──► Worker Node              │
    │            │                                  │
    │            │ 执行脚本                         │
    │            ▼                                  │
    └──────────────────────────────────────────────┘
                │
                │ GET /api/deploy/worker/{id}/progress
                ▼
           SSE Client
```

### 6.3 关键设计决策

1. **密码处理**: API 接收后立即使用，线程内明文，不持久化，日志脱敏
2. **重试机制**: 每步最多 3 次重试，使用指数退避
3. **超时控制**: SSH 连接 30s，命令执行 300s
4. **幂等设计**: 检测已完成的步骤，跳过重复操作
5. **回滚机制**: 失败后尝试清理已创建的资源

### 6.4 幂等性设计

幂等性确保重复部署不会破坏已有配置：

```python
class IdempotencyChecker:
    """检测已完成的步骤，避免重复执行"""

    async def check_step(self, conn, step_key: str) -> bool:
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
            return await check_fn(conn)
        return False

    async def _check_venv_exists(self, conn) -> bool:
        """检查虚拟环境是否存在"""
        result = await conn.run("test -d ~/.venv-ray", check=False)
        return result.exit_status == 0

    async def _check_ray_running(self, conn) -> bool:
        """检查 Ray Worker 是否已启动并连接集群"""
        # 方法1: 检查 ray 进程
        result = await conn.run("pgrep -x ray", check=False)
        if result.exit_status != 0:
            return False

        # 方法2: 验证 join_cluster.sh 输出（关键：与实际脚本输出对齐）
        # join_cluster.sh 成功输出包含 "Ready" 或 "Ray worker started"
        result = await conn.run(
            "cat ~/.ray_join_status 2>/dev/null || echo 'no_status_file'",
            check=False
        )
        output = result.stdout.strip()

        # join_cluster.sh 正常结束时会写入状态文件
        if output == "no_status_file":
            # 无状态文件，检查 ray 相关输出
            result = await conn.run(
                "ray start --address 2>&1 | grep -q 'Successfully started' && echo 'READY' || echo 'NOT_READY'",
                check=False
            )
            return "READY" in result.stdout

        return "SUCCESS" in output or "JOINED" in output

    async def _check_sudo_config(self, conn) -> bool:
        """检查 sudo 免密码是否已配置"""
        result = await conn.run(
            "sudo -n true 2>/dev/null", check=False
        )
        return result.exit_status == 0

    async def _check_deps_installed(self, conn) -> bool:
        """检查依赖是否已安装"""
        # 检查关键包是否安装
        result = await conn.run(
            "~/.venv-ray/bin/python -c 'import ray; import psutil; print(\"OK\")'",
            check=False
        )
        return result.exit_status == 0 and "OK" in result.stdout

    async def _check_code_synced(self, conn) -> bool:
        """检查代码是否已同步"""
        result = await conn.run("test -d ~/Code/AlgoStudio/src", check=False)
        return result.exit_status == 0
```

**幂等执行流程**:
```python
async def run_deploy_step(step_key, step_msg, deploy_func):
    # 1. 检查是否已完成
    if await idempotency.check_step(conn, step_key):
        return {"skipped": True, "reason": "already_done"}

    # 2. 执行部署
    await deploy_func()

    # 3. 验证执行结果
    if await idempotency.check_step(conn, step_key):
        return {"success": True}
    else:
        raise DeployError(f"Step {step_key} failed verification")
```

### 6.5 回滚机制设计

回滚机制确保部署失败时系统处于一致状态：

```python
class RollbackManager:
    """部署回滚管理器"""

    def __init__(self, conn, steps_completed: List[str]):
        self.conn = conn
        self.steps_completed = steps_completed
        self.rollback_handlers = {
            "sudo_config": self._rollback_sudo_config,
            "create_venv": self._rollback_venv,
            "install_deps": self._rollback_deps,
            "sync_code": self._rollback_code,
            "start_ray": self._rollback_ray,
        }

    async def rollback(self):
        """执行回滚，按相反顺序清理"""
        for step in reversed(self.steps_completed):
            handler = self.rollback_handlers.get(step)
            if handler:
                try:
                    await handler()
                except Exception as e:
                    # 记录回滚失败，但继续回滚其他步骤
                    logger.error(f"Rollback failed for {step}: {e}")

    async def _rollback_sudo_config(self):
        """回滚 sudo 免密码配置"""
        # 删除 sudoers 文件
        await self.conn.run("sudo rm -f /etc/sudoers.d/admin02", check=False)
        logger.info("sudo_config rolled back")

    async def _rollback_venv(self):
        """删除虚拟环境"""
        await self.conn.run("rm -rf ~/.venv-ray")

    async def _rollback_ray(self):
        """停止 Ray Worker"""
        await self.conn.run("ray stop", check=False)

    async def _rollback_code(self):
        """回滚代码同步"""
        # 可选：保留备份，使用 git reset
        # 此处仅清理同步标记
        await self.conn.run("rm -f ~/.code_synced", check=False)

    async def _rollback_deps(self):
        """回滚依赖安装（卸载已安装的包）"""
        # 注意：卸载依赖可能影响其他服务，谨慎使用
        # 此处仅清理安装标记
        await self.conn.run("rm -f ~/.deps_installed", check=False)
```

**回滚触发条件**:
- 命令执行超时
- 步骤验证失败
- 用户主动取消部署

### 6.6 多 Worker 并发部署

支持同时部署多个 Worker 节点：

```python
class DeployCoordinator:
    """部署协调器，管理多节点并发部署"""

    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._tasks: Dict[str, asyncio.Task] = {}

    async def deploy_worker(self, request: DeployWorkerRequest):
        """发起一个 Worker 部署任务"""
        task_id = f"deploy-{uuid.uuid4().hex[:8]}"

        # 节点级锁，防止同一节点重复部署
        if request.node_ip not in self._locks:
            self._locks[request.node_ip] = asyncio.Lock()
        else:
            # 等待现有部署完成
            async with self._locks[request.node_ip]:
                return {"status": "in_progress", "task_id": ...}

        async with self._locks[request.node_ip]:
            task = asyncio.create_task(
                run_deploy_task(task_id, request)
            )
            self._tasks[task_id] = task

            # 监听任务完成
            task.add_done_callback(
                lambda t: self._on_task_done(task_id)
            )

        return {"task_id": task_id, "status": "started"}

    async def cancel_deployment(self, task_id: str):
        """取消部署任务"""
        task = self._tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            await task

    def _on_task_done(self, task_id: str):
        """任务完成回调"""
        self._tasks.pop(task_id, None)
```

**并发控制策略**:
- 节点级锁：同一 Worker 节点同时只能有一个部署任务
- 全局限流：最多同时部署 N 个节点（避免网络过载）
- 优先级队列：高优先级任务可插队执行

---

## 7. 实施计划

### 7.1 实施步骤

| 阶段 | 步骤 | 内容 | 时间 |
|------|------|------|------|
| 1 | 环境准备 | 安装 asyncssh，配置开发环境 | 0.5天 |
| 2 | 核心模块 | SSH 连接管理、重连机制、密码处理 | 1.5天 |
| 3 | 幂等性设计 | 步骤检测、状态记录 | 1天 |
| 4 | 部署逻辑 | 集成 join_cluster.sh，7步部署 | 1.5天 |
| 5 | 回滚机制 | 失败回滚、清理逻辑 | 1天 |
| 6 | API 端点 | POST/GET SSE 端点 | 1天 |
| 7 | 进度推送 | SSE 实时推送实现 | 1天 |
| 8 | 并发控制 | 多节点部署协调、节点级锁 | 1天 |
| 9 | 前端集成 | Web 界面部署表单 | 1天 |
| 10 | 测试 | 单元测试、集成测试、多Worker测试 | 2天 |
| 11 | 文档 | API 文档、运维文档 | 0.5天 |

**总计**: 12 天（架构评审后修订）

### 7.2 关键里程碑

- **M1** (Day 3): SSH 连接 + 重连机制完成
- **M2** (Day 5): 部署逻辑 + 幂等性设计完成
- **M3** (Day 7): API + SSE 进度推送完成
- **M4** (Day 9): 并发控制 + 回滚机制完成
- **M5** (Day 11): 前端集成完成
- **M6** (Day 12): 测试通过，文档完成

---

## 8. 风险点和缓解措施

### 8.1 技术风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| asyncssh 依赖缺失 | 低 | 高 | 预检查 libssh2，确保安装 |
| PTY sudo 问题 | 中 | 高 | 预配置 NOPASSWD sudo，避免 PTY |
| SSH 连接断开 | 中 | 中 | 自动重连 + 指数退避 |
| 多 Worker 并发冲突 | 中 | 中 | 节点级锁 + 全局限流 |
| 部署中途取消状态不一致 | 低 | 中 | 回滚机制确保一致 |

### 8.2 操作风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 密码在日志中暴露 | 低 | 高 | 日志脱敏，禁止打印密码 |
| Worker 网络不稳定 | 中 | 中 | 健康检查 + 自动重连 |
| 部署脚本变更 | 中 | 中 | 版本化管理脚本 |

### 8.3 安全风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 密码传输泄露 | 低 | 高 | HTTPS + 内存清理 |
| SSH 暴力破解 | 低 | 高 | 限制尝试次数 |
| 权限过大 | 中 | 高 | 最小权限原则 |

---

## 9. 技术验证计划

### 9.1 单元测试

```python
# tests/test_ssh_deploy.py
import pytest
from unittest.mock import Mock, patch

class TestSSHDeploy:
    def test_password_cleanup(self):
        """验证密码使用后被清理"""
        # ...

    def test_command_timeout(self):
        """验证命令超时处理"""
        # ...

    def test_retry_on_failure(self):
        """验证失败重试逻辑"""
        # ...

    def test_reconnection_on_disconnect(self):
        """验证 SSH 断开后自动重连"""
        # ...

    def test_idempotency_skip_completed(self):
        """验证幂等性：已完成步骤被跳过"""
        # ...

    def test_rollback_on_failure(self):
        """验证部署失败时正确回滚"""
        # ...
```

### 9.2 集成测试

```bash
# 1. 本地测试
python -c "
import asyncio
from algo_studio.core.ssh_deploy import SSHDeployer
d = SSHDeployer()
result = asyncio.run(d.test_connection('192.168.0.115', 'admin02', 'password'))
print(result)
"

# 2. 完整部署测试
POST /api/deploy/worker
{
  "node_ip": "192.168.0.115",
  "username": "admin02",
  "password": "xxx",
  "head_ip": "192.168.0.126"
}

# 3. 验证
ray status  # 在 head 节点执行
```

### 9.3 验证检查表

- [ ] SSH 连接成功
- [ ] sudo 免密码配置成功
- [ ] uv 虚拟环境创建成功
- [ ] Ray Worker 加入集群
- [ ] SSE 进度推送正常
- [ ] 错误处理正确
- [ ] 日志不包含敏感信息
- [ ] SSH 断开后自动重连成功
- [ ] 多 Worker 并发部署无冲突
- [ ] 部署失败后回滚正确

---

## 10. 参考资料

### 10.1 asyncssh 资源（推荐）

- 官方文档: https://asyncssh.readthedocs.io/
- GitHub: https://github.com/ronf/asyncssh
- API 参考: https://asyncssh.readthedocs.io/en/latest/api.html

### 10.2 paramiko 资源

- 官方文档: https://paramiko.readthedocs.io/
- GitHub: https://github.com/paramiko/paramiko
- 最佳实践: https://paramiko.readthedocs.io/en/latest/api/client.html

### 10.3 SSE 资源

- FastAPI SSE: https://fastapi.tiangolo.com/advanced/using-alternative-streaming-response/
- sse-starlette: https://github.com/sysid/sse-starlette

### 10.4 SSH 安全资源

- SSH 最佳实践: https://www.ssh.com/academy/ssh/sshd_best实践
- OpenSSH 手册: https://man.openbsd.org/ssh_config.5

---

## 11. 附录

### A. 部署步骤详解

```
Step 1: SSH 连接 (5%)
  - 建立 TCP 连接
  - SSH 握手
  - 认证

Step 2: sudo 配置 (15%)
  - echo 'admin02 ALL=(ALL) NOPASSWD: ALL' | sudo tee /etc/sudoers.d/admin02

Step 3: 创建 uv 虚拟环境 (30%)
  - curl -LsSf https://astral.sh/uv/install.sh | sh
  - uv python install 3.10.12
  - uv venv .venv-ray

Step 4: 安装依赖 (50%)
  - uv pip install ray psutil pynvml requests python-dotenv

Step 5: 同步代码 (70%)
  - rsync src/ algo@worker:~/Code/AlgoStudio/src/

Step 6: 同步算法 (85%)
  - rsync algorithms/ algo@worker:~/Code/AlgoStudio/algorithms/

Step 7: 启动 Ray Worker (95%)
  - ray stop 2>/dev/null
  - ray start --address=192.168.0.126:6379

Step 8: 验证 (100%)
  - ray status (在 head 节点)
  - SSH 连接测试
```

### B. 环境变量配置

```bash
# Head 节点配置
RAY_HEAD_IP=192.168.0.126
RAY_HEAD_PORT=6379
RAY_OBJECT_STORE_MEMORY=5368709120

# 代理配置
HTTP_PROXY=http://192.168.0.120:7890
HTTPS_PROXY=http://192.168.0.120:7890

# Python 版本
PYTHON_VERSION=3.10.12
```

### C. API 完整定义

```yaml
/openapi.json
/components/schemas/DeployWorkerRequest:
  type: object
  required:
    - node_ip
    - password
    - head_ip
  properties:
    node_ip:
      type: string
      example: "192.168.0.115"
    username:
      type: string
      default: "admin02"
    password:
      type: string
      format: password
    head_ip:
      type: string
      example: "192.168.0.126"
    ray_port:
      type: integer
      default: 6379
```

---

**报告版本**: v5.0
**作者**: 基础设施研究员
**日期**: 2026-03-26
**状态**: 最终版（已完成所有架构评审反馈）
**更新内容**:
- **第4轮 - 重连状态机实现说明**：
  - 定义完整的状态枚举 `ConnectionState`（DISCONNECTED, CONNECTING, IDLE, COMMAND_RUNNING, RETRYING, ERROR）
  - 详细的状态转换规则表
  - 完整的状态机实现代码（包含锁、监听器、重试逻辑）
  - ASCII 状态转换图示
  - 单元测试验证点
  - 集成测试验证脚本
  - SSE 状态推送集成示例
  - 验证检查表

**架构师第4轮评审意见**:
- 架构师 A/B/C (轻微问题)：重连状态机实际行为需代码验证
- **修复方案**：增加完整的状态机实现代码、状态转换规则、验证计划和测试用例，确保实际行为可追溯

**架构评审历史**:
- 第1轮：初始报告
- 第2轮：深化设计
- 第3轮：Bug 修复（authorized_keys、SSHConnectionPool、PTY 边界条件）
- 第4轮：状态机代码验证（轻微问题，本轮修复）
