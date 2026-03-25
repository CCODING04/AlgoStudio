# Ray 集群部署指南

本文档说明如何将多台机器添加到 AlgoStudio 平台组成 Ray 集群。

## 集群架构

```
┌─────────────────────────────────────────────────────┐
│                    Head 节点                        │
│              (平台主服务器，已运行)                   │
│         IP: 192.168.0.126  Port: 6379              │
│         运行: API 服务 + Web Console                 │
└─────────────────────────────────────────────────────┘
          ↕ 连接
┌─────────────────────────────────────────────────────┐
│                   Worker 节点 1                     │
│              IP: 192.168.0.xxx                      │
│         自动注册到 Head，接收调度任务                  │
└─────────────────────────────────────────────────────┘
          ↕ 连接
┌─────────────────────────────────────────────────────┐
│                   Worker 节点 N                     │
│              IP: 192.168.0.yyy                      │
└─────────────────────────────────────────────────────┘
```

## 前置要求

每台 Worker 节点需要满足：

1. **网络互通** — Worker 能访问 Head 节点的 6379 端口
2. **Python 3.10+** — 建议使用系统自带或 conda 管理
3. **GPU 驱动** — 如需 GPU 任务，需安装 nvidia-driver + nvidia-container-runtime
4. **Ray** — Worker 通过脚本自动安装，不污染系统环境

## Head 节点（已配置）

Head 节点已在平台部署时启动，运行以下命令查看状态：

```bash
ray status
```

## 添加 Worker 节点（推荐方式）

在 Worker 节点上执行以下命令，一键部署：

```bash
# 下载算法工作室代码
git clone https://github.com/CCODING04/AlgoStudio.git
cd AlgoStudio

# 运行部署脚本，参数为 Head 节点 IP
bash scripts/join_cluster.sh 192.168.0.126
```

脚本会自动完成：
1. 创建 `.venv-ray` 隔离虚拟环境（使用 uv，不污染系统 Python）
2. 安装 ray、psutil、pynvml、requests 依赖
3. 启动 Ray Worker 连接到 Head 节点
4. 验证集群连接

### 验证部署成功

在 Head 节点上执行：

```bash
ray status
```

应看到新节点出现在列表中，状态为 `alive`。

### 停止 Worker

```bash
ray stop
```

重启后需要重新运行 `bash scripts/join_cluster.sh <HEAD_IP>`

## 手动部署（备选方式）

如果不使用自动脚本，手动部署步骤如下：

### 1. 创建隔离环境

```bash
# 使用 uv 创建独立虚拟环境
uv venv .venv-ray --python 3.10
source .venv-ray/bin/activate

# 或使用标准 venv
python3 -m venv .venv-ray
source .venv-ray/bin/activate
```

### 2. 安装依赖

```bash
pip install ray python-dotenv psutil pynvml requests
```

### 3. 启动 Worker

```bash
ray start --address="192.168.0.126:6379" --object-store-memory=5GB
```

参数说明：
- `--address` — Head 节点地址和端口
- `--object-store-memory` — Ray 对象存储内存，建议 5-10GB

### 4. 验证

```bash
ray status
```

## 常见问题

### Q: Worker 启动失败，提示 "Connection refused"

Head 节点未启动或网络不通。先在 Head 节点确认 Ray 服务正常运行：

```bash
ray status
```

确认防火墙允许 6379 端口入站。

### Q: 不想用 uv，能用标准 Python 吗？

可以，跳过 uv venv 步骤，直接用 `python3 -m venv` 创建虚拟环境即可。

### Q: 如何查看 Worker 资源使用情况？

通过平台 Web Console 的「主机监控」页面查看所有节点 CPU/GPU/内存状态。

### Q: 多网卡机器 IP 检测不准确怎么办？

确保 Ray 检测到的 IP 与 Head 节点网络互通。脚本使用 `psutil.net_if_addrs()` 获取本机所有 IP，如需指定可用：

```bash
ray start --address="192.168.0.126:6379" --node-ip-address="192.168.0.xxx"
```

### Q: 如何完全移除 Worker？

```bash
ray stop            # 停止 Ray Worker
rm -rf .venv-ray    # 删除隔离环境（可选）
```

## Web Console 监控

所有节点加入集群后，在平台 Web Console（http://localhost:7860）中打开「主机监控」页面：

- **宿主机 (Head)** — 蓝色边框标识，显示 Head 节点详情
- **其他节点** — 白色边框，显示各 Worker 资源状态

所有节点会实时显示：
- CPU 型号、物理核心数、线程数、当前频率
- GPU 型号、利用率、显存使用量
- 内存、磁盘、Swap 使用情况
