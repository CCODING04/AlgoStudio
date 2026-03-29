# from: @coordinator
# to: @devops-engineer
# date: 2026-03-29
# type: task
# priority: P0

## 任务: Sentinel 故障转移修复

### 背景
生产级演练发现 Sentinel 无法自动 failover，根因是：
1. Protected mode 阻止外部连接
2. Sentinel 报告 Slave 为 s_down

### 具体任务

**1. 修改 Redis 启动配置**

创建 `/home/admin02/Code/Dev/AlgoStudio/configs/redis/redis-6380.conf`：
```
port 6380
bind 0.0.0.0
protected-mode no
daemonize no
```

**2. 更新 sentinel-26380.conf**

在 `configs/sentinel/sentinel-26380.conf` 中添加：
```conf
# 显式声明已知 replica
sentinel known-replica mymaster 192.168.0.115 6380

# 显式声明已知 sentinel
sentinel known-sentinel mymaster 192.168.0.126 26381 <runid>
sentinel known-sentinel mymaster 192.168.0.115 26380 <runid>
```

**3. 在 Worker 节点执行相同配置**

创建 `configs/sentinel/sentinel-26380-worker.conf` 用于 worker 节点

**4. 验证修复**

```bash
# 重启 Master Redis
sudo redis-cli -p 6380 SHUTDOWN NOSAVE
redis-server /home/admin02/Code/Dev/AlgoStudio/configs/redis/redis-6380.conf --daemonize yes

# 验证
redis-cli -p 6380 CONFIG GET protected-mode
redis-cli -p 6380 INFO replication

# 验证 Sentinel
redis-cli -p 26380 SENTINEL slaves mymaster
```

### 输出
完成后在 `talks/devops-to-coordinator-sentinel-fix-2026-03-29.md` 汇报：
- 配置修改内容
- 验证结果
