#!/bin/bash
#
# worker_deploy.sh - Worker 节点一键部署脚本 (增强版)
#
# 功能:
#   1. 单个或批量 Worker 节点部署
#   2. Redis Sentinel 复制配置
#   3. JuiceFS 挂载
#   4. 代码/算法同步
#   5. Ray Worker 重启
#   6. 回滚功能
#
# 用法:
#   # 单个 Worker
#   ./worker_deploy.sh 192.168.0.115
#
#   # 多个 Worker (逗号分隔)
#   ./worker_deploy.sh 192.168.0.115,192.168.0.120
#
#   # 使用 Worker 列表文件
#   ./worker_deploy.sh --file workers.txt
#
#   # 带 Redis 配置
#   ./worker_deploy.sh --with-redis 192.168.0.115
#
#   # 仅同步算法
#   ./worker_deploy.sh --sync-algos 192.168.0.115
#
#   # 回滚 Worker 代码
#   ./worker_deploy.sh --rollback 192.168.0.115 --to v1.0.0
#
# 选项:
#   --file <file>          Worker IP 列表文件 (每行一个IP)
#   --with-redis           配置 Worker Redis 主从复制
#   --sync-algos           仅同步算法到 Worker
#   --sync-code            仅同步代码到 Worker
#   --rollback             回滚模式
#   --to <version>         回滚目标版本 (与 --rollback 配合)
#   --parallel             并行执行 (多 Worker 时)
#   --dry-run              模拟运行，不实际执行

set -e

# 默认配置
HEAD_IP="${HEAD_IP:-192.168.0.126}"
REDIS_PORT="${REDIS_PORT:-6380}"
SENTINEL_PORT="${SENTINEL_PORT:-26380}"
JUICEFS_VERSION="1.1.5"
PROXY="http://192.168.0.120:7890"
PROJECT_DIR="/home/admin02/Code/Dev/AlgoStudio"
WORKER_VENV_DIR="/home/admin02/Code/AlgoStudio/.venv-ray"

# 操作模式
MODE="deploy"  # deploy, sync_algos, sync_code, rollback
PARALLEL=false
DRY_RUN=false
WITH_REDIS=false
WORKER_FILE=""
WORKERS=""
ROLLBACK_TO=""

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo "用法: $0 [选项] [WORKER_IP[,WORKER_IP2,...]]"
    echo ""
    echo "选项:"
    echo "  --file <file>          Worker IP 列表文件"
    echo "  --with-redis           配置 Worker Redis 主从复制"
    echo "  --sync-algos           仅同步算法"
    echo "  --sync-code            仅同步代码"
    echo "  --rollback             回滚模式"
    echo "  --to <version>         回滚目标版本"
    echo "  --parallel             并行执行 (多 Worker 时)"
    echo "  --dry-run              模拟运行"
    echo "  --help                 显示帮助"
    echo ""
    echo "环境变量:"
    echo "  HEAD_IP                Head 节点 IP (默认: 192.168.0.126)"
    echo "  REDIS_PORT             Redis 端口 (默认: 6380)"
    echo ""
    echo "示例:"
    echo "  $0 192.168.0.115                    # 部署到单个 Worker"
    echo "  $0 192.168.0.115,192.168.0.120    # 部署到多个 Worker"
    echo "  $0 --file workers.txt              # 使用列表文件"
    echo "  $0 --with-redis 192.168.0.115     # 部署并配置 Redis"
    echo "  $0 --sync-algos 192.168.0.115     # 仅同步算法"
    echo "  $0 --rollback 192.168.0.115 --to v1.0.0  # 回滚到指定版本"
    exit 1
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --file)
            WORKER_FILE="$2"
            shift 2
            ;;
        --with-redis)
            WITH_REDIS=true
            shift
            ;;
        --sync-algos)
            MODE="sync_algos"
            shift
            ;;
        --sync-code)
            MODE="sync_code"
            shift
            ;;
        --rollback)
            MODE="rollback"
            shift
            ;;
        --to)
            ROLLBACK_TO="$2"
            shift 2
            ;;
        --parallel)
            PARALLEL=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            usage
            ;;
        -*)
            log_error "未知选项: $1"
            usage
            ;;
        *)
            WORKERS="$1"
            shift
            ;;
    esac
done

# 获取 Worker IP 列表
get_worker_ips() {
    local ips=""

    if [[ -n "$WORKER_FILE" ]]; then
        if [[ ! -f "$WORKER_FILE" ]]; then
            log_error "Worker 文件不存在: $WORKER_FILE"
            exit 1
        fi
        ips=$(grep -v '^#' "$WORKER_FILE" | grep -v '^[[:space:]]*$' | tr '\n' ',')
    elif [[ -n "$WORKERS" ]]; then
        ips="$WORKERS"
    else
        log_error "必须指定 Worker IP"
        usage
    fi

    # 去除末尾逗号
    ips="${ips%,}"
    echo "$ips"
}

# 部署单个 Worker
deploy_worker() {
    local worker_ip="$1"
    local step=1
    local total=7

    [[ "$MODE" == "sync_algos" ]] && total=2
    [[ "$MODE" == "sync_code" ]] && total=2
    [[ "$MODE" == "rollback" ]] && total=3

    echo ""
    log_info "========== 部署 Worker: $worker_ip =========="
    echo "Head IP:   $HEAD_IP"
    echo "Redis:     $REDIS_PORT"
    echo "模式:      $MODE"
    echo ""

    # 检查是否为 head 节点
    if [[ "$(hostname -I 2>/dev/null | awk '{print $1}')" == "$worker_ip" ]]; then
        log_warn "跳过自身节点: $worker_ip"
        return 0
    fi

    # 前置检查
    if ! $DRY_RUN; then
        echo "[$step/$total] 前置检查..."
        if ! ssh -o ConnectTimeout=5 "$worker_ip" "echo ok" > /dev/null 2>&1; then
            log_error "无法连接到 $worker_ip"
            return 1
        fi
        echo "  ✓ 连接正常"
    fi
    step=$((step + 1))

    case "$MODE" in
        sync_algos)
            echo "[$step/$total] 同步算法..."
            if ! $DRY_RUN; then
                rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='*.egg-info' \
                    "$PROJECT_DIR/algorithms/" \
                    "$worker_ip:$PROJECT_DIR/algorithms/" 2>/dev/null
            fi
            echo "  ✓ 算法同步完成"
            ;;

        sync_code)
            echo "[$step/$total] 同步代码..."
            if ! $DRY_RUN; then
                rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='*.egg-info' \
                    "$PROJECT_DIR/src/" \
                    "$worker_ip:$PROJECT_DIR/src/" 2>/dev/null
            fi
            echo "  ✓ 代码同步完成"
            ;;

        rollback)
            echo "[$step/$total] 准备回滚..."
            if [[ -z "$ROLLBACK_TO" ]]; then
                log_error "回滚需要指定 --to <version>"
                return 1
            fi
            if ! $DRY_RUN; then
                # 查找备份目录
                local backup_dir="$PROJECT_DIR/.backups/$ROLLBACK_TO"
                if [[ ! -d "$backup_dir" ]]; then
                    log_error "备份版本不存在: $backup_dir"
                    return 1
                fi
                echo "  备份目录: $backup_dir"
            fi
            step=$((step + 1))

            echo "[$step/$total] 同步回滚代码..."
            if ! $DRY_RUN; then
                rsync -avz --exclude='__pycache__' \
                    "$backup_dir/src/" \
                    "$worker_ip:$PROJECT_DIR/src/" 2>/dev/null
            fi
            echo "  ✓ 回滚同步完成"
            step=$((step + 1))

            echo "[$step/$total] 重启 Ray Worker..."
            if ! $DRY_RUN; then
                ssh "$worker_ip" "ray stop 2>/dev/null || true"
                ssh "$worker_ip" "cd $PROJECT_DIR && source .venv-ray/bin/activate && ray start --address='$HEAD_IP:6379' --node-ip-address=$worker_ip 2>&1"
            fi
            echo "  ✓ Ray Worker 重启完成"
            ;;

        deploy|*)
            # 1. Redis 配置
            if $WITH_REDIS; then
                echo "[$step/$total] 配置 Redis 主从复制..."
                if ! $DRY_RUN; then
                    ssh "$worker_ip" bash << 'REDIS_SCRIPT'
                        set -e
                        REDIS_PORT=6380
                        HEAD_IP=${1:-192.168.0.126}

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

                        echo "  验证复制状态..."
                        redis-cli -p ${REDIS_PORT} INFO replication | grep role
REDIS_SCRIPT
                fi
                echo "  ✓ Redis 配置完成"
                step=$((step + 1))
            fi

            # 2. 安装 JuiceFS
            echo "[$step/$total] 安装 JuiceFS..."
            if ! $DRY_RUN; then
                ssh "$worker_ip" "curl -L --proxy $PROXY -o /tmp/juicefs https://github.com/juicedata/juicefs/releases/download/v$JUICEFS_VERSION/juicefs-$JUICEFS_VERSION-linux-amd64.tar.gz 2>/dev/null" || true
                ssh "$worker_ip" "cd /tmp && tar -xzf juicefs && sudo cp juicefs /usr/local/bin/ && sudo chmod +x /usr/local/bin/juicefs" || true
                echo "  ✓ JuiceFS 安装完成"
            fi
            step=$((step + 1))

            # 3. 挂载 JuiceFS
            echo "[$step/$total] 挂载 JuiceFS..."
            if ! $DRY_RUN; then
                ssh "$worker_ip" "sudo mkdir -p /mnt/VtrixDataset && sudo juicefs mount redis://$HEAD_IP:$REDIS_PORT/0 /mnt/VtrixDataset -d 2>&1" &
                sleep 3
                echo "  ✓ JuiceFS 挂载完成"
            fi
            step=$((step + 1))

            # 4. 同步代码
            echo "[$step/$total] 同步代码到 Worker..."
            if ! $DRY_RUN; then
                rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='*.egg-info' \
                    "$PROJECT_DIR/src/" \
                    "$worker_ip:$PROJECT_DIR/src/" 2>/dev/null
            fi
            echo "  ✓ 代码同步完成"
            step=$((step + 1))

            # 5. 同步算法
            echo "[$step/$total] 同步算法到 Worker..."
            if ! $DRY_RUN; then
                rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='*.egg-info' \
                    "$PROJECT_DIR/algorithms/" \
                    "$worker_ip:$PROJECT_DIR/algorithms/" 2>/dev/null
            fi
            echo "  ✓ 算法同步完成"
            step=$((step + 1))

            # 6. 安装依赖
            echo "[$step/$total] 安装项目依赖..."
            if ! $DRY_RUN; then
                ssh "$worker_ip" "cd $PROJECT_DIR && source .venv-ray/bin/activate && ~/.local/bin/uv pip install -e . --no-deps 2>/dev/null" || true
                echo "  ✓ 依赖安装完成"
            fi
            step=$((step + 1))

            # 7. 重启 Ray Worker
            echo "[$step/$total] 重启 Ray Worker..."
            if ! $DRY_RUN; then
                ssh "$worker_ip" "ray stop 2>/dev/null || true"
                ssh "$worker_ip" "cd $PROJECT_DIR && source .venv-ray/bin/activate && ray start --address='$HEAD_IP:6379' --node-ip-address=$worker_ip 2>&1"
                sleep 2
                echo "  ✓ Ray Worker 重启完成"
            fi
            ;;
    esac

    echo ""
    log_info "========== Worker 部署完成: $worker_ip =========="
}

# 主函数
main() {
    local worker_ips=$(get_worker_ips)
    local IFS=','
    local count=0
    local total=$(echo "$worker_ips" | tr ',' '\n' | wc -l)

    echo "============================================"
    echo "  AlgoStudio Worker 部署脚本 (增强版)"
    echo "============================================"
    echo "Worker IPs: ${worker_ips}"
    echo "Head IP:    $HEAD_IP"
    echo "模式:       $MODE"
    echo "并行:       $PARALLEL"
    echo "模拟运行:   $DRY_RUN"
    echo "============================================"

    if $DRY_RUN; then
        log_warn "=== 模拟运行模式 ==="
    fi

    for worker_ip in $worker_ips; do
        count=$((count + 1))
        [[ -z "$worker_ip" ]] && continue

        echo ""
        echo ">>> [$count/$total] 处理 Worker: $worker_ip"

        if $PARALLEL && [[ $total -gt 1 ]]; then
            deploy_worker "$worker_ip" &
        else
            deploy_worker "$worker_ip"
        fi
    done

    if $PARALLEL && [[ $total -gt 1 ]]; then
        log_info "等待所有 Worker 部署完成..."
        wait
    fi

    echo ""
    log_info "============================================"
    log_info "  全部部署完成!"
    log_info "============================================"

    # 验证集群状态
    if ! $DRY_RUN; then
        echo ""
        echo "集群状态:"
        "$PROJECT_DIR/.venv/bin/ray status" 2>/dev/null || echo "  (ray status 失败，请手动检查)"
    fi
}

main
