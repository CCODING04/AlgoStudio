# from: @coordinator
# to: @devops-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 4

## 任务: Q1 Redis Sentinel 部署 - Worker 节点 Redis 安装

### 背景
Round 1 准备方案已完成。现在需要开始执行。
关键发现: Worker 节点 (192.168.0.115) 目前没有运行 Redis。

### 具体任务

1. **在 Worker 节点安装 Redis Server**
   ```bash
   ssh admin10@192.168.0.115
   # 安装 Redis
   sudo apt-get install redis-server
   # 配置 Redis 端口
   sudo sed -i 's/port 6379/port 6380/' /etc/redis/redis.conf
   # 启动 Redis
   sudo systemctl restart redis-server
   ```

2. **配置 Redis 为 Head 节点的从节点**
   ```bash
   # 在 Worker 节点执行
   redis-cli -p 6380 REPLICAOF 192.168.0.126 6380
   ```

3. **验证主从复制状态**
   ```bash
   # 在 Worker 节点
   redis-cli -p 6380 INFO replication

   # 预期输出:
   # role:slave
   # master_host:192.168.0.126
   # master_port:6380
   ```

4. **更新部署脚本**
   - 更新 `/home/admin02/Code/Dev/AlgoStudio/scripts/redis_sentinel_deploy.py`

### 输出
完成后在 `talks/devops-to-coordinator-round4-2026-03-28.md` 汇报：
- Redis 安装结果
- 主从复制配置结果
