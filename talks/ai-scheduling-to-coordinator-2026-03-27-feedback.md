# Phase 2.3 反馈

## 公平调度算法

### 设计评估

**总体评价：设计完整，覆盖主要需求**

设计文档结构清晰，包含：
- WFQ 核心算法与虚拟完成时间计算
- Reservation 保障机制
- Priority Override 优先级抢占
- 与 QuotaManager 的集成架构

**已确认集成点可用：**
- `QuotaManager._get_effective_quota(user_id, team_id)` - 存在
- `QuotaManager.allocate_resources(quota_id, resources)` - 存在
- `QuotaManager.release_resources(quota_id, resources)` - 存在

### 实现建议

**1. VFT 公式需验证 (Line 80)**
```
VFT = (weight_sum_so_far / tenant_weight) + (task_resources / tenant_allocation_share)
```
当前公式使用除以 `allocation_share`，当 `allocation_share` 很小时会导致 VFT 很大。建议确认这是否符合预期行为，或应使用类似 `VFT += task_resources * weight` 的递增方式。

**2. 资源归一化权重应可配置**
`_normalize_resources` 中硬编码的权重 (GPU=10.0, CPU=1.0) 应提取到配置中，便于调优。

**3. 饥饿预防机制需加强**
当前设计仅在等待超过 2 小时后触发预防措施。建议增加渐进式优先级提升：任务等待每超过 N 分钟，优先级 boost 逐渐增加，而非等到 2 小时才处理。

**4. 队列操作需考虑并发安全**
`GlobalSchedulerQueue.enqueue/dequeue` 在 FastAPI 并发环境下可能存在竞态条件。建议使用 `asyncio.Lock` 或线程安全队列。

**5. reservation_timeout 未被实际使用**
Line 895 定义了 `reservation_timeout_minutes = 60`，但 `ReservationManager` 中没有定期清理超时 reservation 的机制。

### 依赖关系

**无阻塞依赖。** 所有集成点已在 QuotaManager (Phase 2.2 完成) 中存在。

建议 Phase 2.4 的"调度性能优化"任务关注：
- 锁竞争优化
- 大规模 tenant 队列下的 WFQ 性能

### 甘特图调整建议

**无需调整。** Phase 2.3 按计划 Week 5-6 开始实现是合理的。

### 其他

**TaskOrderer 权重分配 (Line 404-439)：**
- Priority 40%, Wait time 30%, Resource efficiency 20%, Age 10%
- 建议在配置中暴露这些权重，便于不同时期调整调度策略

**建议增加两个验收测试场景：**
1. 多 tenant 并发提交时，WFQ 正确分配带宽
2. 高优先级任务到达时，立即抢占低优先级任务

---
**状态：** 设计可接受，实现条件已具备
**预计开始：** Week 5 按计划执行
