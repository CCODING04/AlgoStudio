#!/bin/bash
#
# check_cluster.sh - 集群健康检查脚本
#
# 用法:
#   ./check_cluster.sh              # 检查所有项目
#   ./check_cluster.sh --ray        # 仅检查 Ray
#   ./check_cluster.sh --redis      # 仅检查 Redis
#   ./check_cluster.sh --alert      # 启用告警 (发送 Webhook)
#
# 退出码:
#   0 - 所有检查通过
#   1 - 存在警告
#   2 - 存在错误

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

HEAD_IP="${HEAD_IP:-192.168.0.126}"
REDIS_PORT="${REDIS_PORT:-6380}"
SENTINEL_PORT="${SENTINEL_PORT:-26380}"
PROJECT_DIR="/home/admin02/Code/Dev/AlgoStudio"
VENV_DIR="$PROJECT_DIR/.venv"
CONFIG_FILE="$PROJECT_DIR/scripts/monitoring/alert_config.yaml"

CHECK_RAY=true
CHECK_REDIS=true
CHECK_GPU=true
CHECK_DISK=true
CHECK_JUICEFS=true
SEND_ALERT=false

EXIT_CODE=0

log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --ray) CHECK_REDIS=false; CHECK_GPU=false; CHECK_DISK=false; CHECK_JUICEFS=false; shift ;;
        --redis) CHECK_RAY=false; CHECK_GPU=false; CHECK_DISK=false; CHECK_JUICEFS=false; shift ;;
        --gpu) CHECK_RAY=false; CHECK_REDIS=false; CHECK_DISK=false; CHECK_JUICEFS=false; shift ;;
        --alert) SEND_ALERT=true; shift ;;
        --help) echo "用法: $0 [选项]"; exit 0 ;;
        *) shift ;;
    esac
done

# 检查 Ray 集群
check_ray() {
    echo ""
    echo "=== Ray 集群检查 ==="

    local status_output
    status_output=$("$VENV_DIR/bin/ray status" 2>&1) || {
        log_error "Ray 状态获取失败"
        EXIT_CODE=2
        return
    }

    # 解析存活节点数
    if echo "$status_output" | grep -q "1 nodes"; then
        log_ok "Ray 集群正常 (1 节点)"
    elif echo "$status_output" | grep -q "2 nodes"; then
        log_ok "Ray 集群正常 (2 节点)"
    elif echo "$status_output" | grep -q "0 nodes"; then
        log_error "Ray 集群无节点"
        EXIT_CODE=2
    else
        log_warn "Ray 集群状态异常"
        echo "$status_output" | head -10
        EXIT_CODE=1
    fi
}

# 检查 Redis
check_redis() {
    echo ""
    echo "=== Redis 检查 ==="

    # 检查 Master
    if redis-cli -p ${REDIS_PORT} PING > /dev/null 2>&1; then
        log_ok "Redis Master 正常"
    else
        log_error "Redis Master 不可用"
        EXIT_CODE=2
        return
    fi

    # 检查复制状态
    local replication_info
    replication_info=$(redis-cli -p ${REDIS_PORT} INFO replication 2>/dev/null) || {
        log_warn "无法获取复制状态"
        return
    }

    if echo "$replication_info" | grep -q "role:master"; then
        local slaves=$(echo "$replication_info" | grep "connected_slaves" | awk '{print $2}')
        if [[ "$slaves" -gt 0 ]]; then
            log_ok "Redis 复制正常 ($slaves 个从节点)"
        else
            log_warn "Redis 无从节点"
            EXIT_CODE=1
        fi
    fi
}

# 检查 Sentinel
check_sentinel() {
    echo ""
    echo "=== Sentinel 检查 ==="

    if ! redis-cli -p ${SENTINEL_PORT} PING > /dev/null 2>&1; then
        log_error "Sentinel 不可用"
        EXIT_CODE=2
        return
    fi

    local sentinel_info
    sentinel_info=$(redis-cli -p ${SENTINEL_PORT} SENTINEL master mymaster 2>/dev/null) || {
        log_error "无法获取 Sentinel 状态"
        EXIT_CODE=2
        return
    }

    local status=$(echo "$sentinel_info" | grep "master_status" | cut -d: -f2 | tr -d ' ')
    if [[ "$status" == "connected" ]]; then
        log_ok "Sentinel 正常"
    else
        log_error "Sentinel 状态异常: $status"
        EXIT_CODE=2
    fi
}

# 检查 GPU
check_gpu() {
    echo ""
    echo "=== GPU 检查 ==="

    local gpu_info
    gpu_info=$("$VENV_DIR/bin/python" - << 'PYTHON'
import ray
import json

ray.init(address='auto', namespace='algo_studio', ignore_reinit_error=True)

try:
    total_gpu = 0
    available_gpu = 0

    for node in ray.nodes():
        if node['Alive']:
            total = node['Resources'].get('GPU', 0)
            avail = int(total)
            total_gpu += int(total)
            available_gpu += avail

    print(json.dumps({'total': total_gpu, 'available': available_gpu}))
except Exception as e:
    print(json.dumps({'error': str(e)}))
PYTHON
) || {
        log_warn "无法获取 GPU 信息"
        return
    }

    if echo "$gpu_info" | grep -q "error"; then
        log_warn "GPU 检查失败"
        return
    fi

    local total=$(echo "$gpu_info" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total',0))")
    local available=$(echo "$gpu_info" | python3 -c "import sys,json; print(json.load(sys.stdin).get('available',0))")

    if [[ "$total" -gt 0 ]]; then
        log_ok "GPU 正常 ($available/$total 可用)"
    else
        log_warn "未检测到 GPU"
        EXIT_CODE=1
    fi
}

# 检查磁盘空间
check_disk() {
    echo ""
    echo "=== 磁盘空间检查 ==="

    local disk_usage=$(df -h / | tail -1 | awk '{print $5}' | tr -d '%')
    local home_usage=$(df -h /home | tail -1 | awk '{print $5}' | tr -d '%')

    if [[ "$disk_usage" -gt 90 ]]; then
        log_error "根分区使用率: ${disk_usage}% (超过 90%)"
        EXIT_CODE=2
    elif [[ "$disk_usage" -gt 80 ]]; then
        log_warn "根分区使用率: ${disk_usage}%"
        EXIT_CODE=1
    else
        log_ok "根分区使用率: ${disk_usage}%"
    fi

    if [[ "$home_usage" -gt 90 ]]; then
        log_error "/home 使用率: ${home_usage}%"
        EXIT_CODE=2
    elif [[ "$home_usage" -gt 80 ]]; then
        log_warn "/home 使用率: ${home_usage}%"
    else
        log_ok "/home 使用率: ${home_usage}%"
    fi
}

# 检查 JuiceFS
check_juicefs() {
    echo ""
    echo "=== JuiceFS 检查 ==="

    if mount | grep -q "juicefs"; then
        log_ok "JuiceFS 已挂载"
    else
        log_warn "JuiceFS 未挂载"
        EXIT_CODE=1
    fi
}

# 发送告警
send_alert() {
    local severity="$1"
    local message="$2"

    echo ""
    log_warn "[ALERT] $severity: $message"

    # 如果配置了 Webhook URL，发送告警
    local webhook_url=$(grep "url:" "$CONFIG_FILE" 2>/dev/null | awk '{print $2}' || echo "")

    if [[ -n "$webhook_url" ]]; then
        curl -s -X POST "$webhook_url" \
            -H "Content-Type: application/json" \
            -d "{\"severity\":\"$severity\",\"message\":\"$message\",\"cluster\":\"AlgoStudio\",\"timestamp\":\"$(date -Iseconds)\"}" \
            || log_warn "告警发送失败"
    fi
}

# 主检查流程
echo "============================================"
echo "  AlgoStudio 集群健康检查"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

$CHECK_RAY && check_ray
$CHECK_REDIS && check_redis
$CHECK_SENTINEL && check_sentinel 2>/dev/null || true
$CHECK_GPU && check_gpu
$CHECK_DISK && check_disk
$CHECK_JUICEFS && check_juicefs

echo ""
echo "============================================"

if [[ $EXIT_CODE -eq 0 ]]; then
    log_ok "所有检查通过"
elif [[ $EXIT_CODE -eq 1 ]]; then
    log_warn "存在警告，请检查"
else
    log_error "存在错误，请立即处理"
fi

exit $EXIT_CODE
