#!/bin/bash
#
# setup_worker_redis.sh - Worker 节点 Redis 配置脚本
#
# 用法: ./setup_worker_redis.sh <HEAD_IP>
# 示例: ./setup_worker_redis.sh 192.168.0.126
#

set -e

HEAD_IP=${1:-192.168.0.126}
REDIS_PORT=6380
SENTINEL_PORT=26380
WORKER_IP=$(hostname -I | awk '{print $1}')

echo "=== Worker Redis 安装脚本 ==="
echo "Head IP: $HEAD_IP"
echo "Worker IP: $WORKER_IP"
echo ""

# 创建 Redis 配置
echo "1. 创建 Redis 配置..."
sudo tee /etc/redis/redis-worker.conf > /dev/null << EOF
# Worker Redis Configuration
port ${REDIS_PORT}
bind 0.0.0.0
protected-mode no
replicaof ${HEAD_IP} ${REDIS_PORT}
replica-read-only yes
save ""
maxmemory 2gb
maxmemory-policy allkeys-lru
dir /tmp
EOF

echo "2. 停止现有 Redis..."
sudo redis-cli -p ${REDIS_PORT} SHUTDOWN NOSAVE 2>/dev/null || true
sleep 1

echo "3. 启动新 Redis..."
sudo redis-server /etc/redis/redis-worker.conf --daemonize yes --logfile /var/log/redis/worker.log
sleep 2

echo "4. 验证..."
if redis-cli -p ${REDIS_PORT} PING | grep -q PONG; then
    echo "   Redis 启动成功"
else
    echo "   Redis 启动失败"
    exit 1
fi

# 创建 Sentinel 配置
echo "5. 创建 Sentinel 配置..."
sudo tee /etc/redis/sentinel-worker.conf > /dev/null << EOF
# Worker Sentinel Configuration
port ${SENTINEL_PORT}
sentinel monitor mymaster ${HEAD_IP} ${REDIS_PORT} 2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 10000
sentinel parallel-syncs mymaster 1
sentinel deny-scripts-reconfig yes
protected-mode no
EOF

echo "6. 启动 Sentinel..."
sudo redis-server /etc/redis/sentinel-worker.conf --sentinel --daemonize yes --logfile /var/log/redis/sentinel-worker.log
sleep 2

echo "7. 验证..."
if redis-cli -p ${SENTINEL_PORT} PING | grep -q PONG; then
    echo "   Sentinel 启动成功"
else
    echo "   Sentinel 启动失败"
fi

echo ""
echo "=== 验证复制状态 ==="
redis-cli -p ${REDIS_PORT} INFO replication | grep -E "role|master"

echo ""
echo "=== 完成 ==="
echo "Worker Redis: ${WORKER_IP}:${REDIS_PORT}"
echo "Worker Sentinel: ${WORKER_IP}:${SENTINEL_PORT}"
