# Sentinel 故障转移问题修复

## 问题

演练发现 Sentinel 无法自动 failover，报错 `NOGOODSLAVE No suitable replica to promote`。

## 根因分析

### 1. Worker Redis 绑定问题（主要问题）
- Worker Redis 默认只绑定到 `127.0.0.1`
- Master 无法通过 TCP 连接 Worker Redis
- 导致 Worker 无法作为 Slave 连接到 Master

### 2. Protected Mode 问题
- Master Redis 默认开启 protected mode
- 导致 Worker 无法从外部连接

### 3. Sentinel 配置问题
- Sentinel 报告 Slave 为 `s_down`
- 即使网络正常，Sentinel 也无法检测到 Slave

## 完整修复方案

### 第一部分：Head 节点 Redis 配置

Head Redis 必须绑定到所有接口并关闭 protected mode：

```conf
# /etc/redis/redis-6380.conf
port 6380
bind 0.0.0.0
protected-mode no
```

### 第二部分：Worker 节点配置（关键！）

**每个 Worker 节点必须执行以下操作：**

1. 创建 Redis 配置 `/etc/redis/redis-worker.conf`：
```conf
port 6380
bind 0.0.0.0
protected-mode no
replicaof <HEAD_IP> 6380
replica-read-only yes
save ""
```

2. 停止现有 Redis 并启动新配置：
```bash
sudo redis-cli -p 6380 SHUTDOWN NOSAVE
sudo redis-server /etc/redis/redis-worker.conf --daemonize yes
```

3. 验证：
```bash
redis-cli -p 6380 INFO replication | grep role
# 应该显示: role:slave
```

### 第三部分：Worker 安装脚本

对于新加入的 Worker，使用 `scripts/setup_worker_redis.sh`：

```bash
./scripts/setup_worker_redis.sh 192.168.0.126
```

### 第四部分：Sentinel 配置

Head 节点 `configs/sentinel/sentinel-26380.conf` 已包含：
```conf
sentinel known-replica mymaster 192.168.0.115 6380
sentinel known-sentinel mymaster 192.168.0.126 26381 <runid>
sentinel known-sentinel mymaster 192.168.0.115 26380 <runid>
```

## 验证步骤

```bash
# 1. 检查 Master Replication
redis-cli -p 6380 INFO replication | grep connected_slaves
# 应该显示: connected_slaves:1

# 2. 检查 Slave 状态
redis-cli -p 6380 INFO replication | grep slave0
# 应该显示: ip=<WORKER_IP>,port=6380,state=online

# 3. 检查 Sentinel Quorum
redis-cli -p 26380 SENTINEL ckquorum mymaster
# 应该显示: OK 3 usable Sentinels

# 4. 测试故障转移
redis-cli -p 26380 SENTINEL failover mymaster
```

## 添加新 Worker 步骤

1. 在新 Worker 上执行：
```bash
./scripts/setup_worker_redis.sh <HEAD_IP>
```

2. 在 Head 节点更新 Sentinel 配置：
```bash
redis-cli -p 26380 SENTINEL SET mymaster known-replica <NEW_WORKER_IP> 6380
```

3. 验证：
```bash
redis-cli -p 26380 SENTINEL slaves mymaster
```

## 当前状态

| 组件 | 状态 |
|------|------|
| Head Redis 6380 | ✅ 绑定 0.0.0.0, protected-mode no |
| Head Sentinel 26380 | ✅ 运行中 |
| Head Sentinel 26381 | ✅ 运行中 |
| Worker Redis 6380 | ⚠️ 绑定 127.0.0.1 (需修复) |
| Worker Sentinel 26380 | ✅ 运行中 |
