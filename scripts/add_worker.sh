#!/bin/bash
#
# add_worker.sh - 添加新 Worker 到 Ray 集群
#
# 用法:
#   ./add_worker.sh <WORKER_IP> [HEAD_IP]
#
# 示例:
#   ./add_worker.sh 192.168.0.120
#   ./add_worker.sh 192.168.0.120 192.168.0.126
#
# 此脚本在 Head 节点运行，执行以下操作:
#   1. SSH 连接验证
#   2. 创建必要目录
#   3. 同步代码和算法
#   4. 配置 Worker Ray
#   5. 加入集群
#   6. 更新 Sentinel 配置 (可选)
#   7. 验证集群状态

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

WORKER_IP="${1:-}"
HEAD_IP="${2:-192.168.0.126}"
PROJECT_DIR="/home/admin02/Code/Dev/AlgoStudio"
WORKER_DIR="/home/admin02/Code/AlgoStudio"
REDIS_PORT=6380
SENTINEL_PORT=26380

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
    echo "用法: $0 <WORKER_IP> [HEAD_IP]"
    echo ""
    echo "参数:"
    echo "  WORKER_IP   新 Worker 节点 IP (必需)"
    echo "  HEAD_IP     Head 节点 IP (默认: 192.168.0.126)"
    echo ""
    echo "示例:"
    echo "  $0 192.168.0.120"
    echo "  $0 192.168.0.120 192.168.0.126"
    exit 1
}

# 检查参数
if [[ -z "$WORKER_IP" ]]; then
    log_error "必须指定 Worker IP"
    usage
fi

# 检查是否是自己
if [[ "$(hostname -I 2>/dev/null | awk '{print $1}')" == "$WORKER_IP" ]]; then
    log_error "不能将自身添加为 Worker"
    exit 1
fi

echo "============================================"
echo "  AlgoStudio 添加新 Worker"
echo "============================================"
echo "Worker IP: $WORKER_IP"
echo "Head IP:   $HEAD_IP"
echo "============================================"

# Step 1: SSH 连接验证
echo ""
echo "[1/8] 验证 SSH 连接..."
if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$WORKER_IP" "echo ok" > /dev/null 2>&1; then
    log_error "无法连接到 $WORKER_IP"
    exit 1
fi
log_info "SSH 连接正常"

# Step 2: 检查 Worker 目录结构
echo ""
echo "[2/8] 准备 Worker 目录..."
ssh "$WORKER_IP" "mkdir -p $WORKER_DIR/{src,algorithms,.venv-ray}"
log_info "目录创建完成"

# Step 3: 检查 Worker Python 环境
echo ""
echo "[3/8] 检查 Worker Python 环境..."
if ssh "$WORKER_IP" "test -f $WORKER_DIR/.venv-ray/bin/python" 2>/dev/null; then
    log_info "虚拟环境已存在"
else
    log_warn "虚拟环境不存在，请先运行 join_cluster.sh"
fi

# Step 4: 同步代码
echo ""
echo "[4/8] 同步代码到 Worker..."
rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='*.egg-info' \
    --exclude='.venv/' --exclude='node_modules/' \
    "$PROJECT_DIR/src/" \
    "$WORKER_IP:$WORKER_DIR/src/" 2>/dev/null
log_info "代码同步完成"

# Step 5: 同步算法
echo ""
echo "[5/8] 同步算法到 Worker..."
if [[ -d "$PROJECT_DIR/algorithms" ]]; then
    rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='*.egg-info' \
        "$PROJECT_DIR/algorithms/" \
        "$WORKER_IP:$WORKER_DIR/algorithms/" 2>/dev/null
    log_info "算法同步完成"
else
    log_warn "algorithms 目录不存在，跳过"
fi

# Step 6: 配置 Worker Redis (可选)
echo ""
echo "[6/8] 配置 Worker Redis..."
read -p "是否配置 Redis 主从复制? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "配置 Redis 主从复制..."
    ssh "$WORKER_IP" bash << REDIS_SCRIPT
        set -e
        echo "  创建 Redis 配置..."
        sudo tee /etc/redis/redis-worker.conf > /dev/null << EOF
port ${REDIS_PORT}
bind 0.0.0.0
protected-mode no
replicaof ${HEAD_IP} ${REDIS_PORT}
replica-read-only yes
save ""
dir /tmp
EOF

        echo "  停止现有 Redis..."
        sudo redis-cli -p ${REDIS_PORT} SHUTDOWN NOSAVE 2>/dev/null || true
        sleep 1

        echo "  启动新 Redis..."
        sudo redis-server /etc/redis/redis-worker.conf --daemonize yes --logfile /var/log/redis/worker.log
        sleep 2

        if redis-cli -p ${REDIS_PORT} PING | grep -q PONG; then
            echo "  ✓ Redis 启动成功"
        else
            echo "  ✗ Redis 启动失败"
            exit 1
        fi

        redis-cli -p ${REDIS_PORT} INFO replication | grep role
REDIS_SCRIPT
    log_info "Redis 配置完成"

    # 更新 Sentinel 配置
    echo ""
    echo "  更新 Head 节点 Sentinel 配置..."
    redis-cli -p ${SENTINEL_PORT} SENTINEL SET mymaster known-replica "$WORKER_IP" ${REDIS_PORT} 2>/dev/null || true
    log_info "Sentinel 配置已更新"
fi

# Step 7: 加入 Ray 集群
echo ""
echo "[7/8] 加入 Ray 集群..."
ssh "$WORKER_IP" "ray stop 2>/dev/null || true"
ssh "$WORKER_IP" "cd $WORKER_DIR && source .venv-ray/bin/activate && ray start --address='$HEAD_IP:6379' --node-ip-address=$WORKER_IP 2>&1"
sleep 2
log_info "Ray Worker 已启动"

# Step 8: 验证
echo ""
echo "[8/8] 验证集群状态..."
echo ""
echo "============================================"
"$PROJECT_DIR/.venv/bin/ray status"
echo "============================================"

# 验证 Worker 数据访问
echo ""
echo "验证 Worker 数据访问..."
ssh "$WORKER_IP" "ls -la /mnt/VtrixDataset/" 2>/dev/null || log_warn "无法访问 /mnt/VtrixDataset"

echo ""
log_info "============================================"
log_info "  Worker 添加完成!"
log_info "============================================"
echo ""
echo "后续步骤:"
echo "  1. 验证集群状态: ray status"
echo "  2. 测试任务提交: 通过 Web Console 提交训练任务"
echo "  3. 如需配置 JuiceFS 挂载，请运行:"
echo "     ssh $WORKER_IP 'sudo juicefs mount redis://$HEAD_IP:$REDIS_PORT/0 /mnt/VtrixDataset -d'"
