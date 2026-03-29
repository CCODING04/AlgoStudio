#!/bin/bash
#
# cluster_status.sh - Ray 集群状态检查脚本
#
# 用法:
#   ./cluster_status.sh              # 检查集群状态
#   ./cluster_status.sh --watch     # 持续监控
#   ./cluster_status.sh --json      # JSON 格式输出
#   ./cluster_status.sh --detail    # 详细输出
#
# 检查项目:
#   1. Ray 集群状态
#   2. 节点数量
#   3. GPU 可用性
#   4. Redis Sentinel 状态
#   5. 任务队列状态

set -e

HEAD_IP="${HEAD_IP:-192.168.0.126}"
REDIS_PORT="${REDIS_PORT:-6380}"
SENTINEL_PORT="${SENTINEL_PORT:-26380}"
PROJECT_DIR="/home/admin02/Code/Dev/AlgoStudio"
VENV_DIR="$PROJECT_DIR/.venv"
INTERVAL=5

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

FORMAT="text"
WATCH=false
DETAILED=false

usage() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --watch      持续监控 (每 ${INTERVAL}s 刷新)"
    echo "  --json       JSON 格式输出"
    echo "  --detail     详细输出 (包含 GPU 信息)"
    echo "  --help       显示帮助"
    echo ""
    echo "环境变量:"
    echo "  HEAD_IP      Head 节点 IP (默认: 192.168.0.126)"
    echo "  REDIS_PORT   Redis 端口 (默认: 6380)"
    exit 1
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --watch) WATCH=true; shift ;;
        --json) FORMAT="json"; shift ;;
        --detail) DETAILED=true; shift ;;
        --help) usage ;;
        *) shift ;;
    esac
done

log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }

# 获取 Ray 集群状态
check_ray_status() {
    if [[ "$FORMAT" == "json" ]]; then
        "$VENV_DIR/bin/ray status" --json 2>/dev/null || echo '{"error": "ray status failed"}'
    else
        "$VENV_DIR/bin/ray status" 2>/dev/null || echo "Ray 状态获取失败"
    fi
}

# 获取节点列表
get_nodes() {
    "$VENV_DIR/bin/python" - << 'PYTHON'
import ray
import sys

ray.init(address='auto', namespace='algo_studio', ignore_reinit_error=True)

try:
    nodes = ray.nodes()
    head_node = None
    workers = []

    for node in nodes:
        info = {
            'node_id': node['NodeID'][:8],
            'ip': node['NodeName'],
            'alive': node['Alive'],
            'resources': node['Resources'],
            'labels': node.get('Labels', {})
        }

        # 判断是 Head 还是 Worker
        if 'head' in node.get('NodeName', '').lower() or '126' in node.get('NodeName', ''):
            head_node = info
        else:
            workers.append(info)

    import json
    result = {
        'head': head_node,
        'workers': workers,
        'total': len(nodes),
        'alive': sum(1 for n in nodes if n['Alive'])
    }
    print(json.dumps(result))
except Exception as e:
    print(json.dumps({'error': str(e)}))
PYTHON
}

# 检查 Redis Sentinel
check_sentinel() {
    local sentinel_info

    sentinel_info=$(redis-cli -p ${SENTINEL_PORT} SENTINEL masters 2>/dev/null) || {
        echo '{"error": "Sentinel 不可用"}'
        return
    }

    if [[ "$FORMAT" == "json" ]]; then
        redis-cli -p ${SENTINEL_PORT} SENTINEL master mymaster 2>/dev/null | python3 -c "
import sys, json
lines = sys.stdin.read().strip().split('\n')
data = {}
for line in lines:
    if ':' in line:
        k, v = line.split(':', 1)
        data[k.strip()] = v.strip()
print(json.dumps(data))
" 2>/dev/null || echo '{"error": "解析失败"}'
    else
        echo "=== Redis Sentinel 状态 ==="
        redis-cli -p ${SENTINEL_PORT} SENTINEL master mymaster 2>/dev/null | grep -E "name|ip|port|role"
        echo ""
        echo "Slaves:"
        redis-cli -p ${SENTINEL_PORT} SENTINEL slaves mymaster 2>/dev/null || echo "  无"
        echo ""
        echo "Sentinels:"
        redis-cli -p ${SENTINEL_PORT} SENTINEL sentinels mymaster 2>/dev/null || echo "  无"
    fi
}

# 检查 GPU 状态
check_gpu() {
    if [[ "$FORMAT" == "json" ]]; then
        "$VENV_DIR/bin/python" - << 'PYTHON'
import ray
import json

ray.init(address='auto', namespace='algo_studio', ignore_reinit_error=True)

try:
    gpus = []
    for node in ray.nodes():
        if node['Alive']:
            resources = node['Resources']
            if 'GPU' in resources:
                gpus.append({
                    'node': node['NodeName'],
                    'available': int(resources.get('GPU', 0)),
                    'total': node['Resources'].get('GPU', 0)
                })
    print(json.dumps({'gpus': gpus}))
except Exception as e:
    print(json.dumps({'error': str(e)}))
PYTHON
    else
        echo "=== GPU 状态 ==="
        "$VENV_DIR/bin/python" - << 'PYTHON'
import ray

ray.init(address='auto', namespace='algo_studio', ignore_reinit_error=True)

for node in ray.nodes():
    if node['Alive']:
        name = node['NodeName']
        gpu = int(node['Resources'].get('GPU', 0))
        cpu = int(node['Resources'].get('CPU', 0))
        memory = node['Resources'].get('memory', 0) / (1024**3)

        print(f"  {name}:")
        print(f"    CPU: {cpu}")
        print(f"    GPU: {gpu}")
        print(f"    Memory: {memory:.1f} GB")
        print()
PYTHON
    fi
}

# 检查任务状态
check_tasks() {
    if [[ "$FORMAT" == "json" ]]; then
        echo '{"tasks": "not implemented"}'
    else
        echo "=== 任务队列 ==="
        # 可以通过 API 检查任务队列状态
        curl -s "http://localhost:8000/api/tasks" 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tasks = data if isinstance(data, list) else data.get('tasks', [])
    print(f'  总任务数: {len(tasks)}')
    statuses = {}
    for t in tasks:
        s = t.get('status', 'unknown')
        statuses[s] = statuses.get(s, 0) + 1
    for s, c in statuses.items():
        print(f'    {s}: {c}')
except:
    print('  (无法获取任务状态)')
" 2>/dev/null || echo "  (API 不可用)"
    fi
}

# 输出头部
print_header() {
    if [[ "$FORMAT" != "json" ]]; then
        echo ""
        echo "============================================"
        echo "  AlgoStudio 集群状态"
        echo "  $(date '+%Y-%m-%d %H:%M:%S')"
        echo "============================================"
    fi
}

# 主检查函数
do_check() {
    print_header

    if [[ "$FORMAT" == "json" ]]; then
        local node_info=$(get_nodes 2>/dev/null)
        local sentinel_info=$(check_sentinel 2>/dev/null)

        python3 -c "
import json
print(json.dumps({
    'timestamp': '$(date -Iseconds)',
    'nodes': $node_info,
    'sentinel': $sentinel_info
}, indent=2))
" 2>/dev/null || echo '{"error": "JSON 格式化失败"}'
    else
        # Ray 集群状态
        echo ""
        log_info "Ray 集群"
        echo ""
        check_ray_status
        echo ""

        # 节点信息
        log_info "节点信息"
        get_nodes 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"  总节点数: {data.get('total', '?')}\")
    print(f\"  存活节点: {data.get('alive', '?')}\")

    head = data.get('head')
    if head:
        print(f\"  Head: {head['ip']} ({'存活' if head['alive'] else '离线'})\")

    workers = data.get('workers', [])
    if workers:
        print(f\"  Workers: {len(workers)}\")
        for w in workers:
            status = '存活' if w['alive'] else '离线'
            print(f\"    - {w['ip']} ({status})\")

    if data.get('error'):
        print(f\"  错误: {data['error']}\")
except Exception as e:
    print(f'  解析错误: {e}')
" 2>/dev/null
        echo ""

        # GPU 状态
        if $DETAILED; then
            log_info "GPU 状态"
            check_gpu
            echo ""
        fi

        # Sentinel 状态
        log_info "Redis Sentinel"
        check_sentinel
        echo ""

        # 任务状态
        if $DETAILED; then
            check_tasks
            echo ""
        fi
    fi
}

# 主循环
if $WATCH; then
    echo "持续监控模式 (Ctrl+C 退出)"
    echo "刷新间隔: ${INTERVAL}s"
    while true; do
        clear
        do_check
        sleep $INTERVAL
    done
else
    do_check
fi
