# AlgoStudio 部署脚本

## 目录

| 脚本 | 说明 |
|------|------|
| `setup_ray_cluster.sh` | Head 节点 Ray 集群初始化 |
| `join_cluster.sh` | Worker 节点加入集群 |
| `worker_deploy.sh` | **Worker 节点一键部署（推荐）** |

---

## 快速开始

### 1. Head 节点初始化

```bash
# 在 Head 节点 (192.168.0.126) 上执行
cd ~/Code/Dev/AlgoStudio
./scripts/setup_ray_cluster.sh
```

### 2. 添加 Worker 节点

```bash
# 在 Head 节点上执行 (推荐方式)
cd ~/Code/Dev/AlgoStudio
./scripts/worker_deploy.sh [WORKER_IP]

# 示例: 添加 192.168.0.115
./scripts/worker_deploy.sh 192.168.0.115
```

---

## worker_deploy.sh 详细说明

### 功能
1. 配置 sudo 免密码
2. 安装 JuiceFS 1.1.5
3. 禁用 Redis protected mode
4. 挂载 JuiceFS 到 `/mnt/VtrixDataset`
5. 同步源代码到 Worker
6. 同步算法到 Worker
7. 重启 Ray Worker

### 参数
```bash
./worker_deploy.sh [WORKER_IP] [HEAD_IP] [REDIS_PORT]

# 默认值:
# WORKER_IP  = 192.168.0.115
# HEAD_IP    = 192.168.0.126
# REDIS_PORT = 6380
```

### 前置要求
- Head 节点已运行 Redis (端口 6380)
- Head 节点已配置 JuiceFS
- 可以 SSH 到 Worker 节点
- Worker 节点已配置 sudo 权限

---

## 验证部署

```bash
# 查看集群状态
ray status

# 应该显示 2 个节点 (1 head + 1 worker)

# 验证 API
curl http://localhost:8000/api/hosts/status

# 验证 Worker 数据访问
ssh admin10@192.168.0.115 "ls /mnt/VtrixDataset/"
```

---

## 故障排查

### Redis 连接失败
```bash
# 检查 Redis 是否运行
redis-cli -p 6380 ping

# 如果失败，启动 Redis
redis-server --port 6380 --daemonize yes
```

### JuiceFS 挂载失败
```bash
# 检查 Redis protected mode
redis-cli -p 6380 CONFIG GET protected-mode

# 禁用 protected mode
redis-cli -p 6380 CONFIG SET protected-mode no
```

### Ray Worker 无法连接
```bash
# 在 Worker 上检查
ssh admin10@192.168.0.115 "ray status"

# 重启 Worker
ssh admin10@192.168.0.115 "ray stop && ray start --address='192.168.0.126:6379'"
```
