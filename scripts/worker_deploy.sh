#!/bin/bash
# worker_deploy.sh - Worker 节点一键部署脚本
# 用法: ./worker_deploy.sh [WORKER_IP]
# 默认 WORKER_IP=192.168.0.115

set -e

WORKER_IP="${1:-192.168.0.115}"
HEAD_IP="${2:-192.168.0.126}"
REDIS_PORT="${3:-6380}"
JUICEFS_VERSION="1.1.5"
PROXY="http://192.168.0.120:7890"

echo "============================================"
echo "  AlgoStudio Worker 一键部署脚本"
echo "============================================"
echo "Worker IP: $WORKER_IP"
echo "Head IP:   $HEAD_IP"
echo "Redis:     $REDIS_PORT"
echo "JuiceFS:   $JUICEFS_VERSION"
echo "============================================"

# 检查是否为 head 节点
if [ "$(hostname)" = "$WORKER_IP" ]; then
    echo "错误: 请在 head 节点 (192.168.0.126) 上运行此脚本"
    exit 1
fi

echo ""
echo "[1/7] 配置 sudo 免密码..."
ssh $WORKER_IP "echo 'admin02 ALL=(ALL) NOPASSWD: ALL' | sudo tee /etc/sudoers.d/admin02 && sudo chmod 440 /etc/sudoers.d/admin02"
echo "  ✓ sudo 配置完成"

echo ""
echo "[2/7] 安装 JuiceFS..."
ssh $WORKER_IP "curl -L --proxy $PROXY -o /tmp/juicefs https://github.com/juicedata/juicefs/releases/download/v$JUICEFS_VERSION/juicefs-$JUICEFS_VERSION-linux-amd64.tar.gz 2>/dev/null"
ssh $WORKER_IP "cd /tmp && mv juicefs juicefs.tar.gz && tar -xzf juicefs.tar.gz && sudo cp juicefs /usr/local/bin/ && sudo chmod +x /usr/local/bin/juicefs"
echo "  ✓ JuiceFS 安装完成 ($(ssh $WORKER_IP 'juicefs version') )"

echo ""
echo "[3/7] 禁用 Redis protected mode..."
redis-cli -p $REDIS_PORT CONFIG SET protected-mode no 2>/dev/null || echo "  ⚠ Redis 可能不在 head 节点上"
echo "  ✓ Redis protected mode 已禁用"

echo ""
echo "[4/7] 挂载 JuiceFS..."
ssh $WORKER_IP "sudo mkdir -p /mnt/VtrixDataset && sudo juicefs mount redis://$HEAD_IP:$REDIS_PORT/0 /mnt/VtrixDataset -d 2>&1" &
sleep 3
echo "  ✓ JuiceFS 挂载完成"

echo ""
echo "[5/7] 同步代码到 Worker..."
rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='*.egg-info' \
    ~/Code/Dev/AlgoStudio/src/ \
    $WORKER_IP:~/Code/AlgoStudio/src/ 2>/dev/null
echo "  ✓ 代码同步完成"

echo ""
echo "[6/7] 同步算法到 Worker..."
rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='*.egg-info' \
    ~/Code/Dev/AlgoStudio/algorithms/ \
    $WORKER_IP:~/Code/AlgoStudio/algorithms/ 2>/dev/null
echo "  ✓ 算法同步完成"

echo ""
echo "[7/7] 重启 Ray Worker..."
ssh $WORKER_IP "ray stop 2>/dev/null; cd ~/Code/AlgoStudio && source .venv-ray/bin/activate && ~/.local/bin/uv pip install -e . --no-deps 2>/dev/null"
ssh $WORKER_IP "cd ~/Code/AlgoStudio && source .venv-ray/bin/activate && ray start --address='$HEAD_IP:6379' --node-ip-address=$WORKER_IP 2>&1"
sleep 2
echo "  ✓ Ray Worker 重启完成"

echo ""
echo "============================================"
echo "  部署完成!"
echo "============================================"
echo ""
echo "验证集群状态:"
~/Code/Dev/AlgoStudio/.venv/bin/ray status
echo ""
echo "验证 Worker 数据访问:"
ssh $WORKER_IP "ls -la /mnt/VtrixDataset/"
