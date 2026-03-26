# 数据集分布式存储方案深化报告

**调研日期：** 2026-03-26
**调研人：** Dataset Storage Researcher
**状态：** 深化版（第三轮 - 实测更新）

---

## 1. 设备信息清单

### 1.1 Head 节点 (192.168.0.126) [已实测]

| 项目 | 配置 | 说明 |
|------|------|------|
| **主机名** | admin02-System-Product-Name | 已验证 |
| **IP 地址** | 192.168.0.126 | 已验证 |
| **CPU** | Intel i9-14900KF (24 核) | 高性能桌面处理器 |
| **GPU** | NVIDIA RTX 4090 24GB | 已验证 - 24564 MiB |
| **内存** | 31GB DDR5 | 已验证 |
| **系统盘** | 1.8TB NVMe SSD, 1.4TB 可用 (19%) | 已验证 |
| **Docker** | **未安装** | 需要安装 |
| **NAS 挂载** | `/mnt/VtrixDataset` | 已挂载 |
| **操作系统** | Ubuntu 22.04 | |
| **Python 环境** | `~/.venv/bin/python` (3.10.12) | Ray 2.54.0 |

### 1.2 Worker 节点 (192.168.0.115) [已实测]

| 项目 | 配置 | 说明 |
|------|------|------|
| **主机名** | admin10 | 已验证 |
| **IP 地址** | 192.168.0.115 | 已验证 |
| **CPU** | Intel i9-14900KF (24 核) | 已确认 |
| **GPU** | NVIDIA RTX 4090 24GB | 已验证 - 24564 MiB |
| **内存** | 31GB DDR5 | 已验证 |
| **本地 NVMe SSD** | 1.8TB NVMe SSD, 1.4TB 可用 (23%) | 已验证 |
| **/data 分区** | **不存在** | 缓存目录需改用 `/mnt/juicefs-cache` |
| **NAS 挂载** | **未挂载** | 需要配置 |
| **Python 环境** | `~/Code/AlgoStudio/.venv-ray/bin/ray` | Ray 2.54.0 + Python 3.10 |

### 1.3 NAS 存储 [已实测]

| 项目 | 配置 | 说明 |
|------|------|------|
| **NAS 地址** | `//192.168.1.70/VtrixDataset` | CIFS/SMB 3.1.1 |
| **协议** | SMB/CIFS 3.1.1 | |
| **Head 挂载点** | `/mnt/VtrixDataset` | 已挂载 |
| **总容量** | 14TB | |
| **已用** | 3TB (22%) | |
| **可用** | 11TB | |
| **用户名** | caoc | |
| **目录结构** | 极柱2代机打标训练/, 金属表面瑕疵@移远/, 内焊缝历史数据/, 芯片表面字符@腾达/, 宜宾电池壳现场数据/, 注射器薄膜瑕疵@凯力特/, others/ | |
| **Worker 挂载** | **未挂载** | 需要配置 |

### 1.4 网络拓扑

```
┌─────────────────────────────────────────────────────────────────┐
│                        交换机 (同一网段)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────┐          ┌─────────────────────┐       │
│   │   Head 节点         │          │   Worker 节点       │       │
│   │   192.168.0.126    │◄───────►│   192.168.0.115    │       │
│   │   (Ray Head)       │          │   (Ray Worker)     │       │
│   │   + API 服务        │          │                    │       │
│   │   /mnt/VtrixDataset │          │                    │       │
│   └──────────┬──────────┘          └──────────┬──────────┘       │
│              │                                │                   │
│              │         ↑                       │                   │
│              │         │                       │                   │
│              ▼         │                       │                   │
│   ┌─────────────────────┴───────────────────────┐               │
│   │              NAS (192.168.1.70)               │               │
│   │   //192.168.1.70/VtrixDataset (CIFS)         │               │
│   │   挂载点: /mnt/VtrixDataset                  │               │
│   └───────────────────────────────────────────────┘               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.5 待配置事项

| 项目 | 状态 | 说明 |
|------|------|------|
| Docker 安装 (Head) | 待完成 | Head 节点未安装 Docker |
| Worker NAS 挂载 | 待完成 | Worker 节点需挂载 `/mnt/VtrixDataset` |
| Redis 部署 | 待完成 | 依赖 Docker |
| JuiceFS 配置 | 待完成 | |

### 1.6 实测验证记录

| 验证项目 | 日期 | 结果 | 备注 |
|----------|------|------|------|
| Head 主机名 | 2026-03-26 | admin02-System-Product-Name | |
| Head IP | 2026-03-26 | 192.168.0.126 | |
| Head GPU | 2026-03-26 | RTX 4090 24564 MiB | |
| Head 内存 | 2026-03-26 | 31GB DDR5 | |
| Head 磁盘 | 2026-03-26 | 1.8TB NVMe, 1.4TB 可用 | |
| Head Docker | 2026-03-26 | 未安装 | 需安装 |
| Head NAS 挂载 | 2026-03-26 | /mnt/VtrixDataset 已挂载 | |
| Worker 主机名 | 2026-03-26 | admin10 | |
| Worker IP | 2026-03-26 | 192.168.0.115 | |
| Worker GPU | 2026-03-26 | RTX 4090 24564 MiB | |
| Worker 内存 | 2026-03-26 | 31GB DDR5 | |
| Worker 磁盘 | 2026-03-26 | 1.8TB NVMe, 1.4TB 可用 | |
| Worker /data 分区 | 2026-03-26 | 不存在 | 使用 /mnt/juicefs-cache |
| Worker NAS 挂载 | 2026-03-26 | 未挂载 | 需配置 |
| NAS 地址 | 2026-03-26 | //192.168.1.70/VtrixDataset | |
| NAS 容量 | 2026-03-26 | 14TB 总计, 11TB 可用 | 22% 已用 |

---

## 2. JuiceFS 详细配置方案

### 2.1 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                      JuiceFS 分布式存储                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────┐          ┌─────────────────┐            │
│   │  Redis (Head)   │          │   NAS (后端)     │            │
│   │   192.168.0.126 │          │  192.168.1.70   │            │
│   │   :6380         │          │  (SMB 共享)     │            │
│   └────────┬────────┘          └────────┬────────┘            │
│            │                            │                       │
│            │    JuiceFS Metadata        │                       │
│            │◄──────────────────────────►│                       │
│            │                            │                       │
│            ▼                            ▼                       │
│   ┌─────────────────────────────────────────────┐              │
│   │              JuiceFS FUSE                   │              │
│   │         (POSIX 兼容接口)                     │              │
│   └─────────────────────────────────────────────┘              │
│                            │                                    │
│            ┌───────────────┴───────────────┐                   │
│            ▼                               ▼                   │
│   ┌─────────────────┐             ┌─────────────────┐          │
│   │  Head 节点缓存   │             │  Worker 节点缓存 │          │
│   │  /mnt/juicefs   │             │  /mnt/juicefs   │          │
│   │  100GB NVMe     │             │  100GB NVMe     │          │
│   └─────────────────┘             └─────────────────┘          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Redis 部署方案

#### 方案 A：Docker 部署（推荐）

```bash
# 在 Head 节点执行
# 安装 Docker（如果未安装）
ssh admin02@192.168.0.126 "curl -fsSL https://get.docker.com | sh"

# 创建 Redis 容器
ssh admin02@192.168.0.126 "docker run -d \
  --name juicefs-redis \
  --restart unless-stopped \
  -p 6380:6379 \
  -v /home/admin02/data/redis-data:/data \
  redis:7-alpine \
  redis-server --appendonly yes"
```

**优点：**
- 部署简单，一行命令
- 隔离性好，不影响系统环境
- 便于升级和迁移

**缺点：**
- 需要 Docker 运行时
- 额外的资源开销（~50MB 内存）

#### 方案 B：原生部署

```bash
# 安装 Redis
ssh admin02@192.168.0.126 "apt-get install redis-server -y"

# 配置 Redis
ssh admin02@192.168.0.126 "cat > /etc/redis/redis.conf << 'EOF'
bind 0.0.0.0
protected-mode no
appendonly yes
dir /home/admin02/data/redis-data
maxmemory 2gb
maxmemory-policy allkeys-lru
EOF"

# 启动 Redis
ssh admin02@192.168.0.126 "mkdir -p /home/admin02/data/redis-data"
ssh admin02@192.168.0.126 "systemctl enable redis-server && systemctl start redis-server"
```

### 2.3 JuiceFS Client 安装配置

#### Head 节点安装

```bash
# 下载 JuiceFS CLI
ssh admin02@192.168.0.126 "cd /tmp && \
  curl -sSL https://github.com/juicedata/juicefs/releases/download/v1.1.5/juicefs-1.1.5-linux-amd64.tar.gz | tar xz && \
  mv juicefs /usr/local/bin/ && chmod +x /usr/local/bin/juicefs && \
  /usr/local/bin/juicefs version"
```

#### Worker 节点安装

```bash
# 在 Worker 节点安装 JuiceFS CLI
ssh admin10@192.168.0.115 "cd /tmp && \
  curl -sSL https://github.com/juicedata/juicefs/releases/download/v1.1.5/juicefs-1.1.5-linux-amd64.tar.gz | tar xz && \
  mv juicefs ~/.local/bin/ && chmod +x ~/.local/bin/juicefs && \
  ~/.local/bin/juicefs version"
```

### 2.4 JuiceFS 文件系统创建

```bash
# 在 Head 节点执行
# 格式化和挂载 JuiceFS
ssh admin02@192.168.0.126 "juicefs format \
  --storage nas \
  --bucket /mnt/VtrixDataset/juicefs-backend \
  --access-key localhost \
  --secret-key localhost \
  redis://192.168.0.126:6380/0 \
  algo-studio"
```

**参数说明：**

| 参数 | 值 | 说明 |
|------|-----|------|
| `--storage` | nas | 使用 NAS 作为后端存储 |
| `--bucket` | `/mnt/VtrixDataset/juicefs-backend` | JuiceFS 数据存储路径 |
| `--access-key` | localhost | SMB 共享不需要认证 |
| `--secret-key` | localhost | SMB 共享不需要认证 |
| `redis://` | `192.168.0.126:6380/0` | Redis 元数据地址 |
| `algo-studio` | 文件系统名称 | |

### 2.5 本地缓存配置

#### 缓存目录设置

```bash
# Head 节点 - 创建缓存目录
ssh admin02@192.168.0.126 "mkdir -p /mnt/juicefs-cache /mnt/juicefs-mount"
ssh admin02@192.168.0.126 "chmod 777 /mnt/juicefs-cache"

# Worker 节点 - 创建缓存目录
ssh admin10@192.168.0.115 "mkdir -p /mnt/juicefs-cache /mnt/juicefs-mount"
ssh admin10@192.168.0.115 "chmod 777 /mnt/juicefs-cache"
```

#### 缓存大小分配

根据可用空间（1.8TB NVMe SSD）：

| 用途 | 大小 | 说明 |
|------|------|------|
| 系统预留 | 100GB | 防止磁盘满 |
| JuiceFS 缓存 | 100GB | 热数据缓存 |
| 训练数据 Working Set | 200GB | 频繁访问的数据 |
| 临时文件 | 50GB | 训练中间产物 |
| **可用总计** | ~450GB | 保留约 1.3TB 给其他用途 |

#### 挂载 JuiceFS（带缓存）

**Head 节点：**

```bash
ssh admin02@192.168.0.126 "cat >> /etc/fstab << 'EOF'
juicefs redis://192.168.0.126:6380/0 /mnt/juicefs-mount \
  -d \
  --cache-size 102400 \
  --free-space-ratio 0.1 \
  --cache-dir /mnt/juicefs-cache
EOF"

ssh admin02@192.168.0.126 "mount -a"
```

**Worker 节点：**

```bash
ssh admin10@192.168.0.115 "cat >> /etc/fstab << 'EOF'
juicefs redis://192.168.0.126:6380/0 /mnt/juicefs-mount \
  -d \
  --cache-size 102400 \
  --free-space-ratio 0.1 \
  --cache-dir /mnt/juicefs-cache
EOF"

ssh admin10@192.168.0.115 "mount -a"
```

### 2.6 与 Ray 训练任务的数据路径集成

训练任务通过标准 POSIX 路径访问 JuiceFS 挂载点下的数据集：

```python
# 训练任务中数据路径配置示例
DATA_PATH = "/mnt/juicefs-mount/datasets"

# 训练代码中使用该路径
dataset = load_dataset(f"{DATA_PATH}/train")
model = train(dataset, config)
```

**路径设计原则：**
- JuiceFS 挂载点统一为 `/mnt/juicefs-mount`
- 数据集目录结构：`/mnt/juicefs-mount/datasets/{algorithm_name}/{split}`
- 训练任务通过环境变量或配置文件指定数据路径，无需感知底层存储细节
- Worker 节点执行训练任务时，通过本地 JuiceFS 缓存加速数据读取

**与 Ray Actor 的集成：**
```python
# 在 Ray 训练 Actor 中使用
class TrainingActor:
    def __init__(self, data_path="/mnt/juicefs-mount/datasets"):
        self.data_path = data_path

    def train(self, config):
        # 通过 JuiceFS POSIX 路径读取训练数据
        train_data = load_from_path(f"{self.data_path}/train")
        # 训练逻辑...
```

### 2.7 与现有 DVC 的集成方式

#### DVC 远程配置冲突问题

**潜在冲突：** 现有 DVC 仓库可能已配置了远程存储（如 NAS 上的 DVC cache），直接迁移到 JuiceFS 可能导致：
1. `.dvc/config` 中远程地址与新路径不一致
2. 已有 `.dvc/cache` 与 JuiceFS 数据不同步
3. 多节点使用时远程配置不一致

#### 方案一：软链接集成（推荐）

保持现有 DVC 配置不变，通过软链接让 DVC 访问 JuiceFS 数据：

```bash
# 1. 迁移 DVC cache 到 JuiceFS（耗时操作，建议在低峰期执行）
ssh admin02@192.168.0.126 "cp -r /mnt/VtrixDataset/.dvc /mnt/juicefs-mount/.dvc.bak"
ssh admin02@192.168.0.126 "mv /mnt/VtrixDataset/.dvc /mnt/VtrixDataset/.dvc.nasbackup"

# 2. 创建软链接指向 JuiceFS
ssh admin02@192.168.0.126 "ln -sfn /mnt/juicefs-mount/.dvc /mnt/VtrixDataset/.dvc"

# 3. 迁移数据集到 JuiceFS
ssh admin02@192.168.0.126 "cp -r /mnt/VtrixDataset/datasets /mnt/juicefs-mount/datasets"
ssh admin02@192.168.0.126 "mv /mnt/VtrixDataset/datasets /mnt/VtrixDataset/datasets.nasbackup"
ssh admin02@192.168.0.126 "ln -sfn /mnt/juicefs-mount/datasets /mnt/VtrixDataset/datasets"

# 4. 验证 DVC 操作
cd /path/to/dvc/repo
dvc pull  # 应从 JuiceFS 读取
```

**优点：** 训练代码无需修改路径，保持向后兼容
**缺点：** 需要迁移数据，有停机窗口

#### 方案二：DVC 远程配置重定向

修改 DVC 配置指向 JuiceFS 路径：

```bash
# 1. 检查现有 DVC 配置
cd /path/to/dvc/repo
cat .dvc/config

# 2. 添加 JuiceFS 远程（不删除原有远程）
dvc remote add juicefs /mnt/juicefs-mount/dvc-cache
dvc remote default juicefs  # 设置为默认远程

# 3. 推送数据到 JuiceFS 远程
dvc push -r juicefs

# 4. 验证多节点访问
# 在 Worker 节点
ssh admin10@192.168.0.115 "cd /path/to/dvc/repo && dvc pull -r juicefs"
```

**DVC 配置冲突处理：**

| 场景 | 处理方式 |
|------|----------|
| 原有远程不可访问 | 先 `dvc remote remove old_remote` 再添加新远程 |
| 担心数据丢失 | 保留原有远程作为备份 `dvc remote add -f backup /mnt/VtrixDataset/.dvc-cache` |
| 多节点配置同步 | 将 `.dvc/config` 加入 Git 版本控制并同步到所有节点 |

#### 方案三：独立 DVC 仓库（适合新项目）

为新算法项目创建独立的 DVC 仓库，指向 JuiceFS：

```bash
# 创建新项目 DVC 仓库
mkdir -p /mnt/juicefs-mount/projects/new-algo
cd /mnt/juicefs-mount/projects/new-algo
git init
dvc init

# 配置 DVC 远程
dvc remote add -d juicefs /mnt/juicefs-mount/dvc-cache
dvc remote add -f nas /mnt/VtrixDataset/.dvc-cache  # 备份远程

# 后续在 Worker 节点克隆并使用
ssh admin10@192.168.0.115 "cd /mnt/juicefs-mount/projects && git clone ... && dvc pull"
```

### 2.8 JuiceFS 关键配置参数

```yaml
# /etc/juicefs/juicefs.conf
[juicefs]
# 元数据引擎
meta=redis://192.168.0.126:6380/0

# 存储后端
storage=nas
bucket=/mnt/VtrixDataset/juicefs-backend

# 缓存配置
cache-size=102400          # 100GB 缓存
cache-dir=/mnt/juicefs-cache
free-space-ratio=0.1       # 保留 10% 磁盘空间

# 性能调优
buffer-size=300           # 读写缓冲区 300MB
prefetch=10               # 预读取 10 个 block
```

---

## 3. 实施详细规划

### 3.1 Week 1: 环境准备与基础部署

#### Day 1-2: 设备信息收集与确认 [已完成实测]

| 时间 | 任务 | 命令/操作 | 预期结果 | 实际结果 |
|------|------|----------|----------|----------|
| D1 AM | SSH 连通性测试 | `ssh admin02@192.168.0.126` / `ssh admin10@192.168.0.115` | 能正常登录 | 已确认 |
| D1 PM | 收集 Head 节点信息 | `lsblk; df -h; free -h; nvidia-smi` | 获取完整硬件信息 | 已确认 |
| D2 AM | 收集 Worker 节点信息 | `lsblk; df -h; free -h; nvidia-smi` | 获取完整硬件信息 | 已确认 |
| D2 PM | 确认 NAS 挂载点 | `mount \| grep nas; df -h /mnt/VtrixDataset` | 确认 NAS 路径和可用空间 | 已确认 |

**实测结论：**
- Head 节点：主机名 admin02-System-Product-Name, GPU RTX 4090 24GB, 内存 31GB, 磁盘 1.4TB 可用, Docker 未安装, NAS 已挂载
- Worker 节点：主机名 admin10, GPU RTX 4090 24GB, 内存 31GB, 磁盘 1.4TB 可用, /data 分区不存在, NAS 未挂载
- NAS：`//192.168.1.70/VtrixDataset`, 挂载点 `/mnt/VtrixDataset`, 11TB 可用

**交付物：** 已更新本文档 Section 1.1, 1.2, 1.3 和 1.6

#### Day 3-4: Redis 部署

| 时间 | 任务 | 命令/操作 | 验证方法 |
|------|------|----------|----------|
| D3 AM | 安装 Docker（如需要） | `docker --version` 或安装脚本 | Docker 可用 |
| D3 PM | 启动 Redis 容器 | `docker run -d --name juicefs-redis ...` | `docker ps` 确认运行 |
| D4 AM | 配置 Redis 持久化 | 检查 `/home/admin02/data/redis-data` | 数据文件存在 |
| D4 PM | 测试 Redis 连接 | `redis-cli -h 192.168.0.126 ping` | 返回 `PONG` |

**验证命令：**

```bash
# 测试 Redis 连接
ssh admin02@192.168.0.126 "redis-cli -h 192.168.0.126 ping"
# 预期输出: PONG

# 检查 Redis 状态
ssh admin02@192.168.0.126 "docker exec juicefs-redis redis-cli INFO"
```

#### Day 5: JuiceFS Client 安装

| 时间 | 任务 | 命令/操作 | 验证方法 |
|------|------|----------|----------|
| D5 AM | Head 节点安装 JuiceFS | 下载并安装 CLI | `juicefs version` |
| D5 PM | Worker 节点安装 JuiceFS | 下载并安装 CLI | `juicefs version` |

**安装命令：**

```bash
# Head 和 Worker 节点都需要执行
cd /tmp
curl -sSL https://github.com/juicedata/juicefs/releases/download/v1.1.5/juicefs-1.1.5-linux-amd64.tar.gz | tar xz
mv juicefs /usr/local/bin/  # 或 ~/.local/bin/
chmod +x /usr/local/bin/juicefs
juicefs version
```

### 3.2 Week 2: JuiceFS 配置与调试

#### Day 6-7: JuiceFS 文件系统创建

| 时间 | 任务 | 命令/操作 | 验证方法 |
|------|------|----------|----------|
| D6 AM | 格式化 JuiceFS | `juicefs format --storage nas ...` | 无错误 |
| D6 PM | 手动挂载测试 | `juicefs mount redis://... /mnt/test -d` | `df -h` 确认 |
| D7 AM | 创建缓存目录 | `mkdir -p /mnt/juicefs-cache` | 目录存在 |
| D7 PM | 验证 POSIX 兼容性 | `touch; rm; ls; cat` | 基本操作正常 |

#### Day 8-9: 缓存配置与优化

| 时间 | 任务 | 命令/操作 | 验证方法 |
|------|------|----------|----------|
| D8 AM | 配置 FUSE 自动挂载 | 编辑 `/etc/fstab` | 重启后自动挂载 |
| D8 PM | Worker 节点挂载 | 相同配置 | `df -h` 两节点都显示 |
| D9 AM | 性能基准测试 | `fio --name=seqread ...` | 记录基准数据 |
| D9 PM | 缓存效果验证 | 重复读取同一文件 | 第二次明显更快 |

#### Day 10: 与 DVC 集成

| 时间 | 任务 | 命令/操作 | 验证方法 |
|------|------|----------|----------|
| D10 AM | 迁移 DVC 缓存 | `cp -r /mnt/VtrixDataset/.dvc /mnt/juicefs-mount/` | 迁移完成 |
| D10 PM | 软链接配置 | `ln -sfn ...` | `ls -la /mnt/VtrixDataset/.dvc` 确认 |

### 3.3 实施任务分解表

```
Week 1: 环境准备
├── Day 1: 设备信息收集
│   ├── [ ] SSH 连通性测试 (Head + Worker)
│   ├── [ ] 收集 Head 节点硬件信息
│   └── [ ] 收集 Worker 节点硬件信息
├── Day 2: 存储规划
│   ├── [ ] 确认 NAS 挂载点和可用空间
│   ├── [ ] 规划缓存目录大小
│   └── [ ] 更新设备信息清单
├── Day 3: Redis 部署
│   ├── [ ] 安装 Docker（如需要）
│   └── [ ] 启动 Redis 容器
├── Day 4: Redis 配置
│   ├── [ ] 配置 Redis 持久化
│   └── [ ] 测试 Redis 连接
└── Day 5: JuiceFS 安装
    ├── [ ] Head 节点安装 JuiceFS CLI
    └── [ ] Worker 节点安装 JuiceFS CLI

Week 2: JuiceFS 配置
├── Day 6: 文件系统创建
│   ├── [ ] 格式化 JuiceFS
│   └── [ ] 手动挂载测试
├── Day 7: 缓存配置
│   ├── [ ] 创建缓存目录
│   └── [ ] 验证 POSIX 兼容性
├── Day 8: 自动挂载
│   ├── [ ] 配置 FUSE 自动挂载 (Head)
│   └── [ ] 配置 FUSE 自动挂载 (Worker)
├── Day 9: 性能验证
│   ├── [ ] 性能基准测试
│   └── [ ] 缓存效果验证
└── Day 10: DVC 集成
    ├── [ ] 迁移 DVC 缓存到 JuiceFS
    └── [ ] 配置软链接

Week 3: 生产验证 (可选)
├── Day 11-12: 小规模训练测试
├── Day 13: 性能对比分析
└── Day 14: 文档完善与交接
```

---

## 4. 验证方案

### 4.1 功能验证清单

| 编号 | 测试项 | 验证方法 | 预期结果 |
|------|--------|----------|----------|
| V1 | Redis 连接 | `redis-cli -h 192.168.0.126 ping` | 返回 PONG |
| V2 | JuiceFS CLI | `juicefs version` | 显示版本号 |
| V3 | Head 节点挂载 | `df -h /mnt/juicefs-mount` | 显示文件系统 |
| V4 | Worker 节点挂载 | `df -h /mnt/juicefs-mount` | 两节点都成功 |
| V5 | 跨节点文件共享 | Head 写文件，Worker 读文件 | 文件一致 |
| V6 | 缓存命中 | 重复读取同一文件 | 第二次更快 |
| V7 | DVC 基本操作 | `dvc add; dvc push; dvc pull` | 正常工作 |
| V8 | 训练任务测试 | 运行简单训练任务 | 正常完成 |

### 4.2 性能基准测试

```bash
# 1. 顺序读取测试
fio --name=seqread --filename=/mnt/juicefs-mount/test.seqread \
  --rw=read --size=1G --bs=1M --direct=1 --numjobs=4 --runtime=60

# 2. 随机读取测试
fio --name=randread --filename=/mnt/juicefs-mount/test.randread \
  --rw=randread --size=500M --bs=4K --direct=1 --numjobs=8 --runtime=60

# 3. 写入测试
fio --name=write --filename=/mnt/juicefs-mount/test.write \
  --rw=write --size=1G --bs=1M --direct=1 --numjobs=4 --runtime=60

# 4. 缓存效果对比
# 第一次读取（无缓存）
time cat /mnt/juicefs-mount/largefile.dat > /dev/null
# 第二次读取（有缓存）
time cat /mnt/juicefs-mount/largefile.dat > /dev/null
```

### 4.3 验收标准

| 指标 | 目标值 | 测量方法 |
|------|--------|----------|
| 缓存读取延迟 | < 1ms | `iostat -x 1` + `time` |
| 跨节点文件一致性 | 100% | md5sum 对比 |
| 缓存命中率 | > 80%（热数据） | JuiceFS 监控面板 |
| 训练数据加载时间 | 减少 > 50% | 训练日志时间戳 |

---

## 5. 回滚方案

### 5.1 回滚触发条件

| 条件 | 说明 |
|------|------|
| 性能下降 > 30% | 与基准对比 |
| 文件丢失/损坏 | 数据完整性检查失败 |
| DVC 操作失败 | `dvc pull` 无法正常工作 |
| Redis 不可用 > 1 小时 | 服务可用性 |

### 5.2 分级回滚策略

#### Level 1: 缓存回滚（不停服）

如果缓存导致问题，先禁用缓存：

```bash
# 临时禁用缓存（无需卸载）
juicefs config redis://192.168.0.126:6380/0 --cache-size 0

# 或者修改缓存目录权限
chmod 000 /mnt/juicefs-cache
```

#### Level 2: JuiceFS 卸载（需停服）

```bash
# 在所有节点执行
umount /mnt/juicefs-mount

# 从 fstab 移除
sed -i '/juicefs/d' /etc/fstab

# 恢复 DVC 软链接到 NAS
ln -sfn /mnt/VtrixDataset/.dvc.bak /mnt/VtrixDataset/.dvc
```

#### Level 3: 完全清理

```bash
# 删除 JuiceFS 数据（保留 NAS 数据）
juicefs destroy redis://192.168.0.126:6380/0

# 停止 Redis
docker stop juicefs-redis && docker rm juicefs-redis

# 清理缓存目录
rm -rf /mnt/juicefs-cache/*
```

### 5.3 数据恢复

```bash
# 如果需要从备份恢复 DVC
cp -r /mnt/VtrixDataset/.dvc.backup /mnt/VtrixDataset/.dvc
cp -r /mnt/VtrixDataset/datasets.backup /mnt/VtrixDataset/datasets

# JuiceFS 有自己的回收站机制
juicefs gc redis://192.168.0.126:6380/0 --compact --delete
```

### 5.4 回滚检查清单

- [ ] NAS 数据完整性（md5sum 抽样）
- [ ] DVC 操作正常
- [ ] 训练任务正常
- [ ] Head/Worker 节点服务正常

---

## 6. 依赖清单

### 6.1 软件依赖

| 软件 | 版本 | 安装节点 | 安装方式 | 状态 |
|------|------|----------|----------|------|
| Docker | Latest | Head | `curl -fsSL https://get.docker.com \| sh` | **待安装** |
| Redis | 7-alpine | Head | Docker 容器（端口 6380，避免与 Ray 6379 冲突） | 依赖 Docker |
| JuiceFS CLI | 1.1.5 | Head + Worker | 下载压缩包 | |
| FUSE | 2.9+ | Head + Worker | `apt-get install fuse` | |

**Docker 安装步骤（Head 节点）：**

```bash
# 1. 安装 Docker
ssh admin02@192.168.0.126
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 2. 配置 Docker 开机自启
sudo systemctl enable docker

# 3. 添加当前用户到 docker 组（避免每次用 sudo）
sudo usermod -aG docker $USER

# 4. 验证安装
docker --version

# 5. 启动 Redis 容器（后续步骤）
docker run -d \
  --name juicefs-redis \
  --restart unless-stopped \
  -p 6380:6379 \
  -v /home/admin02/data/redis-data:/data \
  redis:7-alpine \
  redis-server --appendonly yes
```

### 6.2 系统依赖

```bash
# Ubuntu 系统包
apt-get update && apt-get install -y \
  fuse \
  libfuse2 \
  curl \
  redis-tools \
  fio
```

### 6.3 网络要求

| 端口 | 用途 | 节点 |
|------|------|------|
| 6380 | Redis（JuiceFS 元数据） | Head 节点 |
| 6380 | Redis 访问 | Worker 节点（客户端） |
| 111 | RPC（JuiceFS） | 所有节点 |

---

## 7. 风险评估与缓解

### 7.1 风险矩阵

| 风险 | 概率 | 影响 | 风险值 | 缓解措施 |
|------|------|------|--------|----------|
| Redis 单点故障 | 中 | 高 | 中 | Docker 重启策略 + 数据持久化 |
| NAS 带宽瓶颈 | 低 | 中 | 低 | 缓存机制缓解 |
| 缓存空间不足 | 中 | 低 | 低 | 监控 + 及时清理 |
| FUSE 性能开销 | 低 | 低 | 低 | 监控 GPU 利用率 |
| Worker 节点磁盘满 | 低 | 高 | 中 | `free-space-ratio=0.1` 保护 |

### 7.2 监控指标

```bash
# JuiceFS 监控
juicefs status redis://192.168.0.126:6380/0

# 缓存使用情况
juicefs stats /mnt/juicefs-mount

# 磁盘空间监控
df -h /mnt/juicefs-cache
```

---

## 8. 后续优化建议

### 8.1 短期优化（1 个月内）

1. **缓存预热脚本**
   ```bash
   # 创建预热脚本
   juicefs warmup /mnt/juicefs-mount/datasets -p 4
   ```

2. **缓存大小动态调整**
   - 根据训练任务模式调整 `--cache-size`
   - 训练期间增大，训练结束后缩小

3. **JuiceFS 监控面板**
   - 部署 Grafana + Prometheus
   - 监控缓存命中率、延迟等指标

### 8.2 长期优化（3-6 个月）

1. **Redis Sentinel 高可用**
   - 主从复制
   - 自动故障切换

2. **多 NAS 后端**
   - 如果有多个 NAS
   - 负载均衡

3. **NVMe over Fabrics**
   - 如果未来升级网络到 100Gbps
   - 可考虑 NVMe-oF 进一步提升性能

---

## 9. 附录

### 9.1 常用命令速查

```bash
# JuiceFS 状态
juicefs status redis://192.168.0.126:6380/0

# 挂载
juicefs mount redis://192.168.0.126:6380/0 /mnt/juicefs-mount -d

# 卸载
umount /mnt/juicefs-mount

# 清理缓存
juicefs gc redis://192.168.0.126:6380/0 --delete

# 预热缓存
juicefs warmup /mnt/juicefs-mount/datasets

# 查看统计
juicefs stats /mnt/juicefs-mount

# 修改配置
juicefs config redis://192.168.0.126:6380/0 --cache-size 204800
```

### 9.2 参考文档

- [JuiceFS 官方文档](https://juicefs.com/docs/zh/getting-started/)
- [JuiceFS 部署指南](https://juicefs.com/docs/zh/deployment/)
- [JuiceFS 缓存配置](https://juicefs.com/docs/zh/cache/)
- [Redis Docker 部署](https://redis.io/docs/management/install/install-stack/docker/)

---

**报告完成时间：** 2026-03-26
**状态：** 已深化，实测完成，待实施
**下一步：** Docker 安装 (Head) -> Redis 部署 -> Week 1 实施
