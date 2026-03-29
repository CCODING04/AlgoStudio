# from: @coordinator
# to: @devops-engineer
# date: 2026-03-28
# type: task
# round: Phase 3.1 Round 1

## 任务: Redis Sentinel 部署准备

### 背景
评审团决策：Sentinel (1主+1从+3节点)
实施优先级: 中 (Round 5-6 执行)

### 具体任务

1. **研究 Redis Sentinel 部署方案**
   - 当前 Redis 运行在端口 6380
   - Head 节点: 192.168.0.126 (主)
   - Worker 节点: 192.168.0.115 (从)
   - 需要 3 个 Sentinel 节点

2. **制定部署计划**
   - Sentinel 端口: 26380
   - 主从复制配置
   - 故障转移验证步骤

3. **准备部署脚本**
   - Sentinel 启动脚本
   - 故障转移测试脚本

### 输出
完成后在 `talks/devops-to-coordinator-round1-2026-03-28.md` 汇报：
- Sentinel 部署方案
- 节点分配计划
- 时间安排 (Round 5-6)
