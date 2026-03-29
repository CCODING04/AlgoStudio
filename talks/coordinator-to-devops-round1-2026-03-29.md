# from: @coordinator
# to: @devops-engineer
# date: 2026-03-29
# type: task
# round: Phase 3.2 Round 1

## 任务: Sentinel 配置审计 + 故障转移测试准备

### 背景
评审发现 Sentinel 存在问题:
1. sentinel.conf 未提交，难以审计复现
2. Sentinel 报告 master 为 DOWN 但实际正常
3. 秘钥认证未验证

### 具体任务

**1. 提交 sentinel.conf 配置**

创建配置文件:
```bash
# Head 节点
mkdir -p /home/admin02/Code/Dev/AlgoStudio/configs/sentinel/

# Sentinel 1 配置
cat > configs/sentinel/sentinel-26380.conf << EOF
port 26380
sentinel monitor mymaster 192.168.0.126 6380 2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 10000
sentinel parallel-syncs mymaster 1
EOF
```

**2. 诊断 Sentinel 监控问题**

```bash
# 检查 Sentinel 与 Master 通信
redis-cli -p 26380 SENTINEL masters
redis-cli -p 26380 SENTINEL GET-MASTER-ADDR-BY-NAME mymaster
redis-cli -p 6380 ping  # 直接测试 Master

# 检查权限问题
redis-cli -p 6380 INFO replication
```

**3. 准备故障转移测试脚本**

创建 `scripts/test_sentinel_failover.sh`:
```bash
#!/bin/bash
# 模拟 Master 故障
redis-cli -p 6380 DEBUG SLEEP 30 &

# 观察 Sentinel 行为
sleep 10
redis-cli -p 26380 SENTINEL GET-MASTER-ADDR-BY-NAME mymaster

# 恢复
redis-cli -p 6380 DEBUG SLEEP 0
```

### 输出
完成后在 `talks/devops-to-coordinator-round1-2026-03-29.md` 汇报：
- sentinel.conf 配置内容
- 监控问题诊断结果
- 故障转移测试脚本
