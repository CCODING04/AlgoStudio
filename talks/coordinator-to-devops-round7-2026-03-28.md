# from: @coordinator
# to: @devops-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 7

## 任务: Redis Sentinel 故障转移验证

### 背景
Sentinel 3 节点已部署:
- Head: 26380, 26381
- Worker: 26380

需要验证 Sentinel 故障转移功能。

### 具体任务

1. **验证 Sentinel 集群状态**
   ```bash
   redis-cli -p 26380 SENTINEL masters
   redis-cli -p 26380 SENTINEL SENTINELS mymaster
   ```

2. **模拟主节点故障测试**
   ```bash
   # 停止 Head 节点 Redis
   redis-cli -p 6380 DEBUG SLEEP 30 &

   # 观察 Sentinel 是否触发故障转移
   sleep 10
   redis-cli -p 26380 SENTINEL GET-MASTER-ADDR-BY-NAME mymaster
   ```

3. **恢复主节点**
   ```bash
   redis-cli -p 6380 DEBUG SLEEP 0
   ```

### 输出
完成后在 `talks/devops-to-coordinator-round7-2026-03-28.md` 汇报：
- Sentinel 集群状态
- 故障转移测试结果
