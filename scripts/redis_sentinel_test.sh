#!/bin/bash
# Redis Sentinel 验证脚本
# Phase 3.1 Round 1

set -e

# 配置
SENTINEL_PORT=26380
REDIS_PORT=6380
MASTER_IP="192.168.0.126"
SLAVE_IP="192.168.0.115"
QUORUM=2

echo "=== Redis Sentinel 验证脚本 ==="
echo "验证时间: $(date)"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 函数定义
pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# 1. 检查 Master Redis
echo "[1] 检查 Master Redis (${MASTER_IP}:${REDIS_PORT})..."
if redis-cli -h ${MASTER_IP} -p ${REDIS_PORT} ping > /dev/null 2>&1; then
    pass "Master Redis 响应正常"
else
    fail "Master Redis 无响应"
fi

# 2. 检查 Slave Redis
echo "[2] 检查 Slave Redis (${SLAVE_IP}:${REDIS_PORT})..."
if redis-cli -h ${SLAVE_IP} -p ${REDIS_PORT} ping > /dev/null 2>&1; then
    pass "Slave Redis 响应正常"
else
    fail "Slave Redis 无响应"
fi

# 3. 检查主从复制状态
echo "[3] 检查主从复制状态..."
MASTER_ROLE=$(redis-cli -h ${MASTER_IP} -p ${REDIS_PORT} info replication | grep "role:" | cut -d: -f2 | tr -d '\r')
SLAVE_MASTER_LINK=$(redis-cli -h ${SLAVE_IP} -p ${REDIS_PORT} info replication | grep "master_link_status:" | cut -d: -f2 | tr -d '\r')

if [ "$MASTER_ROLE" = "master" ]; then
    pass "Master 角色正确"
else
    fail "Master 角色错误: $MASTER_ROLE"
fi

if [ "$SLAVE_MASTER_LINK" = "up" ]; then
    pass "Slave 复制链路正常"
else
    fail "Slave 复制链路断开: $SLAVE_MASTER_LINK"
fi

# 4. 检查 Sentinel 进程
echo "[4] 检查 Sentinel 进程..."

# Head 节点 Sentinel
for port in 26380 26381; do
    if pgrep -f "redis-sentinel.*${port}" > /dev/null 2>&1; then
        pass "Sentinel on ${MASTER_IP}:${port} 运行中"
    else
        warn "Sentinel on ${MASTER_IP}:${port} 未运行"
    fi
done

# Worker 节点 Sentinel
if ssh -o ConnectTimeout=5 admin10@${SLAVE_IP} "pgrep -f 'redis-sentinel.*${SENTINEL_PORT}'" > /dev/null 2>&1; then
    pass "Sentinel on ${SLAVE_IP}:${SENTINEL_PORT} 运行中"
else
    warn "Sentinel on ${SLAVE_IP}:${SENTINEL_PORT} 未运行"
fi

# 5. 检查 Sentinel 连接
echo "[5] 检查 Sentinel 连接..."
for ip in ${MASTER_IP}; do
    for port in 26380 26381; do
        if redis-cli -h ${ip} -p ${port} ping > /dev/null 2>&1; then
            pass "Sentinel ${ip}:${port} 响应正常"
        else
            fail "Sentinel ${ip}:${port} 无响应"
        fi
    done
done

# Worker Sentinel
if redis-cli -h ${SLAVE_IP} -p ${SENTINEL_PORT} ping > /dev/null 2>&1; then
    pass "Sentinel ${SLAVE_IP}:${SENTINEL_PORT} 响应正常"
else
    fail "Sentinel ${SLAVE_IP}:${SENTINEL_PORT} 无响应"
fi

# 6. 验证 Sentinel 监控状态
echo "[6] 验证 Sentinel 监控状态..."
MASTER_NAME=$(redis-cli -h ${MASTER_IP} -p ${SENTINEL_PORT} sentinel get-master-addr-by-name algo-studio-master 2>/dev/null | head -1)
if [ -n "$MASTER_NAME" ]; then
    pass "Sentinel 监控主节点: ${MASTER_NAME}"
else
    warn "Sentinel 未监控到主节点 (可能尚未选举)"
fi

echo ""
echo "=== 验证完成 ==="