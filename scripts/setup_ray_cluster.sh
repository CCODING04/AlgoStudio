#!/bin/bash
# scripts/setup_ray_cluster.sh
# Ray 集群初始化脚本

set -e

RAY_HEAD_PORT=6379
OBJECT_STORE_MEMORY=5368709120  # 5GB in bytes

usage() {
    echo "Usage: $0 {head|worker|stop}"
    echo "  head    - 初始化 Head 节点"
    echo "  worker  - 以 Worker 身份加入集群（需要 HEAD_IP）"
    echo "  stop    - 停止 Ray 集群"
    exit 1
}

init_head() {
    echo "Initializing Ray Head node..."
    ray start --head --port=$RAY_HEAD_PORT --object-store-memory=$OBJECT_STORE_MEMORY
    echo "Ray Head node initialized."
    echo "Run 'ray status' to check cluster status."
}

init_worker() {
    if [ -z "$HEAD_IP" ]; then
        echo "Error: HEAD_IP environment variable not set"
        echo "Usage: HEAD_IP=192.168.0.100 $0 worker"
        exit 1
    fi

    echo "Initializing Ray Worker node, connecting to $HEAD_IP..."
    ray start --address="$HEAD_IP:$RAY_HEAD_PORT" --object-store-memory=$OBJECT_STORE_MEMORY
    echo "Ray Worker node initialized."
}

stop_ray() {
    echo "Stopping Ray..."
    ray stop
    echo "Ray stopped."
}

case "$1" in
    head)
        init_head
        ;;
    worker)
        init_worker
        ;;
    stop)
        stop_ray
        ;;
    *)
        usage
        ;;
esac