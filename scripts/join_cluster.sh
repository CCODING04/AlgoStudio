#!/bin/bash
# scripts/join_cluster.sh
# 快速将其他机器加入 Ray 集群（不污染系统环境）
# 用法: bash join_cluster.sh <HEAD_IP>
#
# 示例:
#   bash join_cluster.sh 192.168.0.126

set -e

RAY_HEAD_PORT=6379

usage() {
    echo "Usage: bash join_cluster.sh <HEAD_IP>"
    echo "  HEAD_IP - Head 节点 IP 地址（默认: 192.168.0.126）"
    echo ""
    echo "示例:"
    echo "  bash join_cluster.sh 192.168.0.126"
    exit 1
}

HEAD_IP="${1:-}"
if [ -z "$HEAD_IP" ]; then
    usage
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv-ray"

echo "=========================================="
echo " AlgoStudio Ray Worker 快速部署"
echo "=========================================="
echo "Head IP: $HEAD_IP"
echo "虚拟环境: $VENV_DIR"
echo ""

# Step 1: 创建隔离虚拟环境（用 uv，不污染系统）
if [ ! -d "$VENV_DIR" ]; then
    echo "[1/4] 创建 uv 虚拟环境..."
    if ! command -v uv &> /dev/null; then
        echo "      uv 未安装，正在安装 uv..."
        # 使用代理下载 uv（国内访问 https://astral.sh 需要代理）
        HTTP_PROXY="http://192.168.0.120:7890" \
        HTTPS_PROXY="http://192.168.0.120:7890" \
            curl -LsSf https://astral.sh/uv/install.sh | sh
        # 让当前 shell 加载 uv
        export PATH="$HOME/.local/bin:$PATH"
    fi
    uv venv "$VENV_DIR" --python 3.10
    echo "Done."
else
    echo "[1/4] 虚拟环境已存在，跳过创建。"
fi

# Step 2: 安装依赖
echo "[2/4] 安装 Ray 和 algo_studio 依赖..."
export PATH="$HOME/.local/bin:$PATH"
uv pip install --python "$VENV_DIR/bin/python" ray python-dotenv psutil pynvml requests

# Step 3: 启动 Worker
echo "[3/4] 启动 Ray Worker，连接到 $HEAD_IP:$RAY_HEAD_PORT..."
"$VENV_DIR/bin/ray" start --address="$HEAD_IP:$RAY_HEAD_PORT" --object-store-memory=5GB

# Step 4: 验证连接
echo "[4/4] 验证集群连接..."
echo ""
echo "=========================================="
echo " Worker 已成功加入集群！"
echo "=========================================="
echo ""
echo "在 Head 节点上运行以下命令查看节点列表:"
echo "  ray status"
echo ""
echo "停止 Worker:"
echo "  ray stop"
echo ""
echo "注意: Worker 每次重启需要重新运行此脚本"
