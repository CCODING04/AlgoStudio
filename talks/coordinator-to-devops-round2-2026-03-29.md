# from: @coordinator
# to: @devops-engineer
# date: 2026-03-29
# type: task
# round: Phase 3.2 Round 2

## 任务: Sentinel Quorum 配置修复

### 背景
评审发现 Sentinel 配置问题：
- 当前 quorum=2，但只有 1 个 Sentinel 节点在运行
- 没有配置 replicaof（从节点复制）

### 具体任务

**1. 诊断 Sentinel 状态**

```bash
redis-cli -p 26380 SENTINEL masters
redis-cli -p 26380 SENTINEL get-master-addr-by-name mymaster
redis-cli -p 26380 SENTINEL slaves mymaster
```

**2. 修复 sentinel-26380.conf**

当前只有 1 个 Sentinel，需要确认 quorum 设置：
```bash
# 检查当前 Sentinel 数量
redis-cli -p 26380 SENTINEL masters
redis-cli -p 26380 SENTINEL slaves mymaster

# 如果只有 1 个 Sentinel，quorum 应该改为 1
# 如果有 2 个 Sentinel，quorum 应该是 2
```

**3. 添加第二个 Sentinel 配置（如果需要）**

创建 `configs/sentinel/sentinel-26381.conf`：
```bash
port 26381
sentinel monitor mymaster 192.168.0.126 6380 2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 10000
sentinel parallel-syncs mymaster 1
```

**4. 验证故障转移**

使用 `scripts/test_sentinel_failover.sh --quick` 验证。

### 输出
完成后在 `talks/devops-to-coordinator-round2-2026-03-29.md` 汇报：
- 当前 Sentinel 状态
- 配置修复情况
- 验证结果
