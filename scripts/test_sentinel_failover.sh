#!/bin/bash
#
# test_sentinel_failover.sh - Redis Sentinel Failover Test Script
# Purpose: Test Sentinel failover behavior without actual downtime
#
# WARNING: This script simulates master failure using DEBUG SLEEP.
#          Only run on test/development environments!
#
# Usage: ./test_sentinel_failover.sh [--recover] [--monitor]
#

set -e

MASTER_PORT=6380
SENTINEL_PORT=26380
MASTER_NAME="mymaster"
CHECK_INTERVAL=2

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v redis-cli &> /dev/null; then
        log_error "redis-cli not found. Please install Redis tools."
        exit 1
    fi

    if ! redis-cli -p $MASTER_PORT ping > /dev/null 2>&1; then
        log_error "Master Redis at port $MASTER_PORT is not reachable"
        exit 1
    fi

    if ! redis-cli -p $SENTINEL_PORT ping > /dev/null 2>&1; then
        log_error "Sentinel at port $SENTINEL_PORT is not reachable"
        exit 1
    fi

    log_info "Prerequisites check passed"
}

# Get current master from Sentinel
get_sentinel_master() {
    redis-cli -p $SENTINEL_PORT SENTINEL get-master-addr-by-name $MASTER_NAME 2>/dev/null | tr -d '\r\n' | tr '\n' ':'
}

# Get master from Sentinel with details
get_master_details() {
    local master_info=$(redis-cli -p $SENTINEL_PORT SENTINEL masters 2>/dev/null)
    echo "$master_info"
}

# Check master status
check_master_status() {
    log_info "=== Master Status Check ==="

    echo "--- Direct Redis Ping ---"
    redis-cli -p $MASTER_PORT ping

    echo "--- Replication Info ---"
    redis-cli -p $MASTER_PORT INFO replication | grep -E "role|master_link|connected_slaves"

    echo "--- Sentinel Master Info ---"
    get_master_details

    echo "--- Current Master from Sentinel ---"
    get_sentinel_master
}

# Simulate master failure (DEBUG SLEEP)
simulate_master_failure() {
    local sleep_duration=${1:-30}

    log_warn "=== SIMULATING MASTER FAILURE ==="
    log_warn "Master Redis will be unresponsive for ${sleep_duration} seconds"
    log_warn "Press Ctrl+C to abort within 5 seconds..."

    sleep 5

    log_info "Executing: redis-cli -p $MASTER_PORT DEBUG SLEEP $sleep_duration &"
    redis-cli -p $MASTER_PORT DEBUG SLEEP $sleep_duration &
    local pid=$!

    log_info "Master failure simulation started (PID: $pid)"

    # Monitor Sentinel behavior during failure
    local attempt=1
    while kill -0 $pid 2>/dev/null; do
        log_info "--- Observation $attempt ---"
        get_sentinel_master
        redis-cli -p $MASTER_PORT ping 2>/dev/null || echo "Master not responding"
        sleep $CHECK_INTERVAL
        ((attempt++))
    done

    log_info "Failure simulation completed"
}

# Monitor Sentinel continuously
monitor_sentinel() {
    log_info "=== Monitoring Sentinel (Press Ctrl+C to stop) ==="

    while true; do
        clear
        echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="
        echo ""
        check_master_status
        echo ""
        echo "--- Sentinel CKQUORUM ---"
        redis-cli -p $SENTINEL_PORT SENTINEL ckquorum $MASTER_NAME
        echo ""
        sleep $CHECK_INTERVAL
    done
}

# Test key authentication (if configured)
test_authentication() {
    log_info "=== Testing Authentication ==="

    # Check if master requires auth
    if redis-cli -p $MASTER_PORT DEBUG OBJECT ENCODING "" > /dev/null 2>&1; then
        log_info "Master does not require authentication"
    else
        log_warn "Master may require authentication - test skipped"
    fi

    # Test Sentinel auth if configured
    log_info "Sentinel auth test: Checking if Sentinel requires credentials..."
    if redis-cli -p $SENTINEL_PORT SENTINEL masters | grep -q "auth-pass"; then
        log_info "Sentinel authentication is configured"
    else
        log_info "Sentinel is running without authentication"
    fi
}

# Quick failover test (non-destructive)
quick_test() {
    log_info "=== Quick Sentinel Health Check ==="

    echo "1. Checking Sentinel quorum..."
    redis-cli -p $SENTINEL_PORT SENTINEL ckquorum $MASTER_NAME

    echo ""
    echo "2. Checking master availability..."
    get_sentinel_master

    echo ""
    echo "3. Checking Sentinel visibility of slaves..."
    redis-cli -p $SENTINEL_PORT SENTINEL masters | grep -E "num-slaves|num-other-sentinels"

    echo ""
    echo "4. Testing master ping..."
    redis-cli -p $MASTER_PORT ping

    echo ""
    log_info "Quick test completed"
}

# Recovery test after simulated failure
recovery_test() {
    log_info "=== Testing Recovery Mechanism ==="

    log_info "Checking if master recovered automatically..."
    sleep 2

    if redis-cli -p $MASTER_PORT ping > /dev/null 2>&1; then
        log_info "Master is back online"
        get_sentinel_master
    else
        log_error "Master did not recover - manual intervention may be required"
    fi
}

# Print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --quick          Run quick health check (default)"
    echo "  --monitor        Continuous monitoring mode"
    echo "  --failover       Simulate master failure for 30 seconds"
    echo "  --failover N     Simulate master failure for N seconds"
    echo "  --recover        Test recovery after failure"
    echo "  --status         Show detailed master status"
    echo "  --auth           Test authentication settings"
    echo "  --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --quick              # Quick health check"
    echo "  $0 --monitor            # Continuous monitoring"
    echo "  $0 --failover 60        # Simulate 60-second failure"
    echo "  $0 --failover --recover # Failover test with recovery"
}

# Main
main() {
    case "${1:-}" in
        --quick|-q)
            quick_test
            ;;
        --monitor|-m)
            monitor_sentinel
            ;;
        --failover|-f)
            check_prerequisites
            check_master_status
            simulate_master_failure "${2:-30}"
            ;;
        --recover|-r)
            recovery_test
            ;;
        --status|-s)
            check_master_status
            ;;
        --auth|-a)
            test_authentication
            ;;
        --help|-h)
            usage
            ;;
        *)
            # Default: quick test
            check_prerequisites
            quick_test
            ;;
    esac
}

main "$@"
