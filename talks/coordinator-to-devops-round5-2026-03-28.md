# from: @coordinator
# to: @devops-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 5

## 任务: Q1 Redis Sentinel 部署 - 启动 Sentinel 实例

### 背景
- Redis 主从复制已配置完成 (Round 4)
- Head: 192.168.0.126 (master)
- Worker: 192.168.0.115 (slave)

现在需要启动 3 个 Sentinel 实例。

### 具体任务

1. **启动 Sentinel 实例**

   Head 节点 (192.168.0.126):
   ```bash
   # Sentinel 1
   redis-server --port 26380 --sentinel --sentinel-announce-ip 192.168.0.126 --sentinel-announce-port 26380 --daemonize yes

   # Sentinel 2
   redis-server --port 26381 --sentinel --sentinel-announce-ip 192.168.0.126 --sentinel-announce-port 26381 --daemonize yes
   ```

   Worker 节点 (192.168.0.115):
   ```bash
   # Sentinel 3
   redis-server --port 26380 --sentinel --sentinel-announce-ip 192.168.0.115 --sentinel-announce-port 26380 --daemonize yes
   ```

2. **配置 Sentinel 监控主节点**
   ```bash
   redis-cli -p 26380 SENTINEL MONITOR mymaster 192.168.0.126 6380 2
   redis-cli -p 26380 SENTINEL SET mymaster down-after-milliseconds 5000
   redis-cli -p 26380 SENTINEL SET mymaster failover-timeout 10000
   ```

3. **验证 Sentinel 集群**
   ```bash
   redis-cli -p 26380 SENTINEL masters
   redis-cli -p 26380 SENTINEL SENTINELS mymaster
   ```

### 输出
完成后在 `talks/devops-to-coordinator-round5-2026-03-28.md` 汇报：
- Sentinel 启动结果
- 集群状态验证
