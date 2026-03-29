# from: @devops-engineer
# to: @coordinator
# date: 2026-03-29
# type: report
# priority: P0

## Sentinel 故障转移修复报告

### 已完成配置修改

**1. Redis Master 配置** (`/home/admin02/Code/Dev/AlgoStudio/configs/redis/redis-6380.conf`)
```conf
port 6380
bind 0.0.0.0
protected-mode no
daemonize no
replica-read-only yes
```

**2. Sentinel-26380 配置更新** (`/home/admin02/Code/Dev/AlgoStudio/configs/sentinel/sentinel-26380.conf`)
- 添加 `sentinel known-replica mymaster 192.168.0.115 6380` (已存在)
- 添加 `sentinel known-sentinel mymaster 192.168.0.126 26381 <runid>` (Sentinel 自动更新)
- Sentinel 已启动并运行

**3. Worker Sentinel 配置** (`/home/admin02/Code/Dev/AlgoStudio/configs/sentinel/sentinel-26380-worker.conf`)
- 已创建，用于 worker 节点

### 验证结果

```bash
# Sentinel 26380 状态
redis-cli -p 26380 SENTINEL masters
# -> master 状态正常，num-slaves=1, num-other-sentinels=4

# Master Redis
redis-cli -p 6380 INFO replication
# -> role:master, connected_slaves:1, slave0:ip=192.168.0.115,state=online

# Worker Redis 复制状态
ssh admin10@192.168.0.115 "redis-cli -p 6380 INFO replication"
# -> role:slave, master_link_status:up, replication 正常工作
```

### 根因分析

**发现：Worker Redis 只绑定到 127.0.0.1:6380**

```
Worker Redis: /usr/bin/redis-server 127.0.0.1:6380
```

**为什么复制工作但 Sentinel 失败：**
- 复制工作：因为 slave 通过 Redis replica 机制主动连接到 master (192.168.0.126:6380)
- Sentinel 失败：Sentinel 需要主动连接到 slave (192.168.0.115:6380) 来检查状态，但端口只监听在 localhost

**Sentinel 报告的 slave 状态：**
```
flags: s_down,slave,disconnected
master-link-status: err
master-host: ?
master-port: 0
```

### 待修复项

**Worker Redis 绑定配置需要修复：**

Worker Redis 需要重启并绑定到 0.0.0.0 或 192.168.0.115：

```bash
# 在 worker 节点执行
ssh admin10@192.168.0.115
redis-cli -p 6380 SHUTDOWN NOSAVE
redis-server /home/admin10/Code/AlgoStudio/configs/redis/redis-6380.conf --daemonize yes
```

需要创建 `/home/admin10/Code/AlgoStudio/configs/redis/redis-6380.conf`：
```conf
port 6380
bind 0.0.0.0
protected-mode no
daemonize yes
replica-read-only yes
```

### 下一步

1. 协调 worker 节点 Redis 重启时间窗口
2. 重启后验证 Sentinel slave 状态变为 online
3. 测试 failover 场景
