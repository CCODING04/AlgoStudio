# from: @devops-engineer
# to: @coordinator
# date: 2026-03-28
# type: report
# round: Phase 3.1 Round 1

## 任务: Redis Sentinel 部署准备 - 完成汇报

### 执行摘要

已完成 Redis Sentinel 部署方案研究和脚本准备。**新发现: Worker 节点需要先安装 Redis 作为 Slave**。

---

## 1. 当前环境状态

| 节点 | IP | Redis 状态 | 说明 |
|------|-----|-----------|------|
| Head | 192.168.0.126 | **运行中** (端口 6380) | Master |
| Worker | 192.168.0.115 | **未安装** | 需安装并配置为 Slave |

### 验证结果
```
Head Redis (192.168.0.126:6380): 正常运行, role=master, connected_slaves=0
Worker Redis (192.168.0.115:6380): Connection refused - Redis 未运行
```

---

## 2. Redis Sentinel 部署方案

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    Redis Sentinel Cluster                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────────────┐        ┌─────────────────┐             │
│   │  Head 节点      │        │  Worker 节点    │             │
│   │  192.168.0.126 │        │  192.168.0.115 │             │
│   │                 │        │                 │             │
│   │  ┌───────────┐  │◄─────►│  ┌───────────┐  │             │
│   │  │ Redis     │  │ 复制   │  │ Redis     │  │             │
│   │  │ Master    │  │        │  │ Slave     │  │             │
│   │  │ :6380     │  │        │  │ :6380     │  │             │
│   │  └───────────┘  │        │  └───────────┘  │             │
│   │                 │        │                 │             │
│   │  ┌───────────┐  │        │  ┌───────────┐  │             │
│   │  │ Sentinel1 │  │        │  │ Sentinel2 │  │             │
│   │  │ :26380    │  │        │  │ :26380    │  │             │
│   │  └───────────┘  │        │  └───────────┘  │             │
│   │                 │        │                 │             │
│   │  ┌───────────┐  │        │                 │             │
│   │  │ Sentinel3 │  │        │                 │             │
│   │  │ :26381    │  │        │                 │             │
│   │  └───────────┘  │        │                 │             │
│   └─────────────────┘        └─────────────────┘             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 节点分配计划

| 节点 | IP | 角色 | Redis 端口 | Sentinel 端口 |
|------|-----|------|-----------|--------------|
| Head | 192.168.0.126 | Master | 6380 | Sentinel1: 26380, Sentinel3: 26381 |
| Worker | 192.168.0.115 | Slave | 6380 | Sentinel2: 26380 |

### Sentinel 配置参数

```conf
port 26380
sentinel monitor algo-studio-master 192.168.0.126 6380 2
sentinel down-after-milliseconds algo-studio-master 5000
sentinel parallel-syncs algo-studio-master 1
sentinel failover-timeout algo-studio-master 10000
sentinel deny-scripts-reconfig yes
```

| 参数 | 值 | 说明 |
|------|-----|------|
| quorum | 2 | 3个节点中至少2个同意才执行故障转移 |
| down-after-milliseconds | 5000 | 5秒无响应则认为主观下线 |
| parallel-syncs | 1 | 故障转移后1个slave并行同步 |
| failover-timeout | 10000 | 故障转移超时 10秒 |

---

## 3. 部署脚本

### 位置
- `/home/admin02/Code/Dev/AlgoStudio/scripts/redis_sentinel_deploy.py` - Python 部署脚本
- `/home/admin02/Code/Dev/AlgoStudio/scripts/redis_sentinel_test.sh` - 验证脚本

### 使用方法

```bash
# 部署 Sentinel
python scripts/redis_sentinel_deploy.py

# 验证部署
bash scripts/redis_sentinel_test.sh

# 故障转移测试
python scripts/redis_sentinel_deploy.py test
```

---

## 4. 部署步骤 (Round 5-6 执行)

### Step 1: Worker 节点安装 Redis (Round 5)
- [ ] 在 Worker 节点安装 Redis Server
- [ ] 配置 Worker Redis 为 Slave ( replicaof 192.168.0.126 6380 )
- [ ] 验证主从复制状态

### Step 2: 启动 Sentinel 实例 (Round 5)
- [ ] Head 节点启动 Sentinel1 (26380)
- [ ] Head 节点启动 Sentinel3 (26381)
- [ ] Worker 节点启动 Sentinel2 (26380)

### Step 3: 验证 Sentinel 集群 (Round 6)
- [ ] 验证 3 个 Sentinel 进程运行
- [ ] 验证 Sentinel 能感知 Master/Slave
- [ ] 执行故障转移测试

### Step 4: 更新应用配置 (Round 6)
- [ ] 更新 RedisQuotaStore 连接字符串
- [ ] 使用 Sentinel 发现主节点
- [ ] 验证应用功能正常

---

## 5. 时间安排

| Round | 时间 | 任务 |
|-------|------|------|
| Round 1 | 2026-03-28 | **已完成** - 方案设计、脚本准备 |
| Round 5 | 待定 | Step 1: Worker 安装 Redis + 主从配置 |
| Round 5 | 待定 | Step 2: 启动 Sentinel 实例 |
| Round 6 | 待定 | Step 3-4: 验证和切换 |

---

## 6. Worker 节点 Redis 安装命令

```bash
# 在 Worker 节点执行
ssh admin10@192.168.0.115

# 安装 Redis (如果未安装)
sudo apt-get update && sudo apt-get install -y redis-server

# 配置 Redis (作为 Slave)
sudo sed -i 's/bind 127.0.0.1/bind 0.0.0.0/' /etc/redis/redis.conf
echo "replicaof 192.168.0.126 6380" | sudo tee -a /etc/redis/redis.conf

# 重启 Redis
sudo systemctl restart redis-server

# 验证
redis-cli ping  # 应返回 PONG
redis-cli info replication  # 应显示 role:slave
```

---

## 7. 注意事项

### 当前问题
1. **Worker Redis 未安装** - 需要先安装并配置为 Slave
2. **只有 2 个物理节点** - 第 3 个 Sentinel 运行在 Head 节点不同端口 (26381)，这是开发/测试环境的常见做法

### 建议
1. 在 Round 5 执行前，确保 Worker 节点 Redis 已正确配置
2. 生产环境建议使用 3 个独立节点
3. 部署前备份现有 Redis 数据

---

## 8. 依赖项

- Redis Server 安装 (Worker 节点)
- SSH 访问 Head 和 Worker 节点
- redis-sentinel 命令可用

---

## 状态: 准备完成，等待 Round 5 执行