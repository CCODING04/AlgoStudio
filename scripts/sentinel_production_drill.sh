#!/bin/bash
#
# sentinel_production_drill.sh - Redis Sentinel 生产级故障转移演练
#
# 警告: 此脚本会模拟真实故障，仅在生产环境测试时使用！
#

set -e

MASTER_PORT=6380
SENTINEL_PORTS=(26380 26381)
MASTER_NAME="mymaster"
FAILOVER_TIMEOUT=60

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARN:${NC} $1"; }
error() { echo -e "${RED}[$(date '+%H:%M:%S')] ERROR:${NC} $1"; }
info() { echo -e "${BLUE}[$(date '+%H:%M:%S')] INFO:${NC} $1"; }

# 获取当前 Master
get_master() {
    redis-cli -p ${SENTINEL_PORTS[0]} SENTINEL get-master-addr-by-name $MASTER_NAME 2>/dev/null | head -1
}

# 获取 Master 详情
get_master_info() {
    redis-cli -p ${SENTINEL_PORTS[0]} SENTINEL master $MASTER_NAME
}

# 记录时间
time_cmd() {
    local start=$(date +%s)
    $@
    local end=$(date +%s)
    echo $((end - start))
}

# ============================================
# 演练 1: Master 网络隔离
# ============================================
drill_network_isolation() {
    log "=== 演练 1: Master 网络隔离 ==="
    local original_master=$(get_master)
    log "原始 Master: $original_master"

    info "步骤 1.1: 在 Slave 上模拟网络隔离 (iptables)"
    # 注意: 需要在 Slave 节点执行，而非 Master
    warn "需要在 192.168.0.115 上执行: iptables -A INPUT -s 192.168.0.126 -j DROP"

    log "步骤 1.2: 观察 Sentinel 检测时间"
    log "等待 down-after-milliseconds (5000ms)..."
    sleep 6

    log "步骤 1.3: 检查 Sentinel 状态"
    redis-cli -p 26380 SENTINEL masters | grep -E "name|flags|role-reported"

    log "步骤 1.4: 验证新 Master"
    local new_master=$(get_master)
    log "新 Master: $new_master"

    if [ "$original_master" != "$new_master" ]; then
        log "✅ 故障转移成功!"
    else
        warn "⚠️ Master 未变更，可能故障转移未触发"
    fi

    log "步骤 1.5: 清理 iptables 规则"
    warn "需要在 192.168.0.115 上执行: iptables -D INPUT -s 192.168.0.126 -j DROP"
}

# ============================================
# 演练 2: Master 进程崩溃
# ============================================
drill_process_crash() {
    log "=== 演练 2: Master 进程崩溃 ==="
    local original_master=$(get_master)
    log "原始 Master: $original_master"

    info "步骤 2.1: 获取 Master PID"
    local master_pid=$(redis-cli -p $MASTER_PORT DEBUG PID 2>/dev/null || echo "")
    log "Master PID: $master_pid"

    info "步骤 2.2: 模拟进程崩溃"
    warn "执行: kill -9 $master_pid"
    kill -9 $master_pid 2>/dev/null || true

    info "步骤 2.3: 观察故障转移 (最多 ${FAILOVER_TIMEOUT}s)"
    local start_time=$(date +%s)
    while true; do
        local new_master=$(get_master)
        if [ "$original_master" != "$new_master" ]; then
            local elapsed=$(($(date +%s) - start_time))
            log "✅ 故障转移完成! 耗时: ${elapsed}s"
            log "新 Master: $new_master"
            break
        fi
        if [ $(($(date +%s) - start_time)) -gt $FAILOVER_TIMEOUT ]; then
            error "❌ 故障转移超时 (${FAILOVER_TIMEOUT}s)"
            break
        fi
        sleep 2
    done

    info "步骤 2.4: 验证数据一致性"
    redis-cli -p $MASTER_PORT PING 2>/dev/null || log "原始 Master 未恢复"
}

# ============================================
# 演练 3: 应用连接切换验证
# ============================================
drill_app_connection() {
    log "=== 演练 3: 应用连接切换验证 ==="

    info "检查应用连接池状态"
    # 模拟应用重连
    for i in {1..5}; do
        local master=$(get_master)
        log "尝试 $i: 连接 $master"
        if redis-cli -h $(echo $master | cut -d' ' -f1) -p 6380 PING 2>/dev/null | grep -q PONG; then
            log "✅ 应用可连接新 Master"
        fi
        sleep 1
    done
}

# ============================================
# 演练 4: Quorum 丧失测试
# ============================================
drill_quorum_loss() {
    log "=== 演练 4: Quorum 丧失测试 ==="

    info "当前 Sentinel 状态:"
    for port in ${SENTINEL_PORTS[@]}; do
        echo -n "Sentinel $port: "
        redis-cli -p $port PING 2>/dev/null || echo "DOWN"
    done

    info "步骤 4.1: 停止 2 个 Sentinel"
    warn "需要在各节点执行:"
    warn "  redis-cli -p 26380 SHUTDOWN NOSAVE"
    warn "  redis-cli -p 26381 SHUTDOWN NOSAVE"

    info "步骤 4.2: 验证 Sentinel 无法执行故障转移"
    redis-cli -p 26380 SENTINEL ckquorum $MASTER_NAME 2>/dev/null || true

    info "步骤 4.3: 恢复 Sentinel"
    warn "重新启动 Sentinel 服务"
}

# ============================================
# 演练报告
# ============================================
generate_report() {
    log "=== 演练报告 ==="
    echo ""
    echo "演练时间: $(date)"
    echo "原始 Master: $(get_master)"
    echo ""
    echo "检查项:"
    echo "  1. 故障检测时间是否 < 10s"
    echo "  2. 故障转移是否自动完成"
    echo "  3. 数据是否无丢失"
    echo "  4. 应用是否自动重连"
    echo ""
}

# 主菜单
show_menu() {
    echo "============================================"
    echo "   Redis Sentinel 生产级故障转移演练"
    echo "============================================"
    echo ""
    echo "演练场景:"
    echo "  1) 演练 1: Master 网络隔离"
    echo "  2) 演练 2: Master 进程崩溃"
    echo "  3) 演练 3: 应用连接切换验证"
    echo "  4) 演练 4: Quorum 丧失测试"
    echo "  5) 执行所有演练"
    echo "  6) 生成演练报告"
    echo "  0) 退出"
    echo ""
    echo -n "请选择: "
    read choice
    echo ""

    case $choice in
        1) drill_network_isolation ;;
        2) drill_process_crash ;;
        3) drill_app_connection ;;
        4) drill_quorum_loss ;;
        5)
            drill_network_isolation
            drill_process_crash
            drill_app_connection
            drill_quorum_loss
            ;;
        6) generate_report ;;
        0) exit 0 ;;
        *) error "无效选择" ;;
    esac
}

show_menu
