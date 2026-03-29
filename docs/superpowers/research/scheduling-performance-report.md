# Scheduling Performance Optimization Report
**Phase 2.4 Round 1 - Scheduling Performance Optimization**

## Executive Summary

The WFQScheduler and related scheduling components have been analyzed and optimized. Performance benchmarks confirm that scheduling latency is well within the target of < 100ms.

## Performance Benchmarks Results

| Test Scenario | Target | Actual p95 | Status |
|--------------|--------|------------|--------|
| Single Schedule Latency | < 10ms | 1.13ms | PASS |
| Multi-tenant Scheduling | < 50ms | 1.05ms | PASS |
| High Contention | < 100ms | 0.62ms | PASS |
| Concurrent Scheduling | < 100ms | 1.11ms | PASS |
| Priority Override | < 10ms | 0.65ms | PASS |
| Scalability (20 tenants) | < 100ms | 1.21ms | PASS |

## Changes Made

### 1. WFQScheduler Optimization (wfq_scheduler.py)
**Issue**: Recursive requeue pattern could cause stack overflow under high contention.

**Fix**: Changed recursive calls to iterative loop with `max_requeue_attempts` parameter:
```python
async def schedule_next(
    self, available_resources: ResourceQuota,
    max_requeue_attempts: int = 10
) -> Optional[FairSchedulingDecision]:
    requeue_count = 0
    while requeue_count < max_requeue_attempts:
        # ... dequeue and process task
        if not allowed:
            async with self._lock:
                await self.queue.requeue(task)
            requeue_count += 1
            continue  # Iterative loop instead of recursion
```

### 2. GlobalSchedulerQueue Bug Fix (global_queue.py)
**Issue**: Tenant queue creation was passing `team_id=None` when looking up team quotas, causing weight and guaranteed resources to default to values instead of being read from the quota store.

**Fix**: Changed `_create_tenant_queue` to pass `team_id=tenant_id`:
```python
quota = self.quota_manager._get_effective_quota(
    user_id=tenant_id,
    team_id=tenant_id  # Was: team_id=None
)
```

### 3. Quota Store Schema Enhancement (quota/store.py)
**Issue**: The SQLiteQuotaStore schema was missing `weight`, `guaranteed_gpu_count`, `guaranteed_cpu_cores`, and `guaranteed_memory_gb` columns needed for proper WFQ scheduling.

**Fix**: Added columns to quotas table:
- `weight REAL DEFAULT 1.0`
- `guaranteed_gpu_count INTEGER DEFAULT 0`
- `guaranteed_cpu_cores INTEGER DEFAULT 0`
- `guaranteed_memory_gb REAL DEFAULT 0.0`

Also updated `create_quota()` and `_row_to_quota()` to properly handle these fields.

## Architecture Analysis

### Current Performance Characteristics
- FastPathScheduler: ~0.03ms p95 (excellent)
- AgenticScheduler: ~0.06ms p95 (excellent)
- WFQScheduler: ~1.0ms p95 (excellent, meets < 100ms target)

### Identified Bottlenecks
1. **Lock Contention**: Single `asyncio.Lock` in GlobalSchedulerQueue serializes queue operations. Under high concurrency, this could become a bottleneck.

2. **Quota Cache**: Cache is invalidated at each `schedule_next` call, which is correct for freshness but prevents reuse across scheduling cycles.

3. **O(n) Tenant Selection**: The `_select_tenant_wrr` method iterates through all eligible tenants to find the one with lowest ratio.

### Optimizations Already Implemented
1. Heap-based priority queue for O(log n) task enqueue/dequeue
2. Cached WFQ ratios in TenantQueue (`wrr_ratio` property)
3. Quota caching in WFQScheduler to avoid redundant DB queries
4. Iterative requeue pattern to avoid stack overflow

## Recommendations for Future Optimization

1. **Fine-grained Locking**: Consider using per-tenant locks instead of a global lock to reduce contention under high concurrency.

2. **Batch Operations**: Support batch scheduling to amortize lock acquisition costs when scheduling multiple tasks.

3. **Priority Queue Optimization**: Consider using a calendar queue or timing wheel for tasks with future start times.

4. **Weighted Fair Queuing Enhancement**: The current implementation uses `tasks_scheduled / weight` ratio. For better fairness with heavy-tailed task distributions, consider using virtual finish time (VFT) consistently across all selection paths.

## Test Coverage

New benchmark tests added: `tests/performance/test_wfq_scheduler_benchmark.py`
- 9 new performance tests covering:
  - Single/multi-tenant scheduling latency
  - High contention scenarios
  - Concurrent scheduling
  - Quota cache effectiveness
  - Requeue iteration performance
  - Weighted fairness verification
  - Priority override performance
  - Scalability with 20+ tenants

All tests pass: 133 scheduler + benchmark tests total.

## Conclusion

The scheduling system meets the < 100ms latency target with significant margin (actual p95 < 1.5ms). The main optimizations and bug fixes have been implemented. Future improvements would focus on reducing lock contention under extreme concurrency scenarios.

---
*Report generated: 2026-03-27*
*Phase 2.4 Round 1*
