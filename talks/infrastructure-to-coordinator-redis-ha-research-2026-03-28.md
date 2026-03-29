# Redis 高可用方案研究报告

**From:** @infrastructure-engineer
**To:** @coordinator
**Date:** 2026-03-28
**Subject:** Redis 高可用方案调研

---

## 背景

当前 AlgoStudio 使用单点 Redis (端口 6380) 作为缓存和消息队列。当前方案无高可用保护，需要评估合适的 Redis 高可用方案。

---

## 方案对比

| 特性 | Redis Sentinel | Redis Cluster | Redis Fabrics |
|------|-----------------|---------------|---------------|
| **架构复杂度** | 低 | 中 | 高 |
| **数据分片** | 无 (主从复制) | 有 (16384 slots) | 有 |
| **自动故障转移** | 是 | 是 | 是 |
| **客户端支持** | 需支持 Sentinel 协议 | 需 Cluster 协议 | 需特定驱动 |
| **节点数量** | 1 主 + N 从 + N Sentinel | 至少 6 节点 (3 主 x 2 从) | 至少 6 节点 |
| **Redis 版本** | 2.8+ | 3.0+ | 6.0+ (experimental) |
| **水平扩展** | 受限 (只读从节点) | 好 (分片) | 好 |
| **配置难度** | 低 | 中 | 高 |
| **社区活跃度** | 高 | 高 | 低 (experimental) |

---

## 各方案详解

### 1. Redis Sentinel

**优点:**
- 部署简单，配置友好
- 自动故障检测和 failover
- 客户端无需特殊支持 (主流客户端均支持)
- 支持多哨兵协作，避免脑裂
- 成熟稳定，生产环境广泛验证

**缺点:**
- 无数据分片，存储受单节点限制
- 主从复制有延迟，可能丢少量数据
- 从节点仅做只读/备份，不分担写入压力

**适用场景:**
- 数据量 < 100GB
- 只需主从复制，不需要分片
- 需要简单可靠的故障转移

### 2. Redis Cluster

**优点:**
- 自动分片，数据分布存储
- 高可用 (每个主节点有从节点)
- 水平扩展能力强
- 无中心架构，无单点瓶颈

**缺点:**
- 需要至少 6 个节点 (生产环境)
- 客户端需要支持 Cluster 协议
- 不支持跨 slot 的多键操作
- 运维复杂度较高

**适用场景:**
- 数据量 > 100GB
- 需要水平扩展
- 高并发读写

### 3. Redis Fabrics

**优点:**
- 增强的分片和复制功能
- 更好的跨数据中心支持
- ACID 事务支持

**缺点:**
- 实验性功能，文档少
- 社区支持薄弱
- 生产环境不推荐

**适用场景:** 不推荐生产使用

---

## AlgoStudio 场景分析

### 当前使用情况
- Redis 端口 6380
- 用于缓存和消息队列
- 单节点部署

### 关键考量

| 因素 | 分析 |
|------|------|
| **数据量** | AlgoStudio 的任务队列、缓存数据量预计中等 (< 50GB)，不需要分片 |
| **可用性** | 需要自动故障转移，确保任务队列不中断 |
| **运维能力** | 团队规模有限，优先考虑简单可靠的方案 |
| **扩展需求** | 当前阶段以功能开发为主，扩展性需求不高 |
| **成本** | Cluster 至少需要 6 节点，成本较高 |

### 结论

**推荐方案: Redis Sentinel**

理由:
1. **场景匹配**: AlgoStudio 当前数据量不需要分片，Sentinel 足以覆盖需求
2. **运维简单**: 只需 3 哨兵 + 1 主 + 1 从，部署维护成本低
3. **可靠性**: Sentinel 经过广泛验证，故障转移机制成熟
4. **成本效益**: 无需增加太多节点即可实现高可用
5. **渐进扩展**: 如未来数据量增长，可平滑迁移到 Cluster

---

## 实施建议

### Phase 1: Sentinel 部署 (推荐)

```
架构: 1 主节点 + 1 从节点 + 3 Sentinel
- 主节点: 192.168.0.126:6380 (当前节点)
- 从节点: 192.168.0.115:6380 (Worker 节点)
- Sentinel 节点: 192.168.0.126:26380, 192.168.0.115:26380, 第三节点
```

**实施步骤:**
1. 在 Worker 节点部署 Redis 从节点
2. 部署 3 个 Sentinel 实例
3. 配置 Sentinel 监控当前主节点
4. 更新应用 Redis 连接字符串使用 Sentinel
5. 测试故障转移

### Phase 2: Cluster 迁移 (如需)

如未来数据量超过 100GB 或需要水平扩展:
1. 评估数据量和增长预期
2. 规划 Cluster 节点布局
3. 使用 Redis Migrate 工具迁移数据
4. 逐步切换客户端到 Cluster 模式

---

## 参考资料

> 注: 以下为基于知识的参考资料，建议后续补充实际搜索的博客链接

| 资料 | 描述 |
|------|------|
| [Redis Sentinel Documentation](https://redis.io/docs/management/sentinel/) | 官方 Sentinel 文档 |
| [Redis Cluster Documentation](https://redis.io/docs/management/scaling/) | 官方 Cluster 文档 |
| [Redis High Availability Patterns](https://redis.io/docs/management/optimization/redis-oe/) | Redis 高可用模式 |
| [Sentinel vs Cluster](https://redis.io/docs/management/scaling/#redis-cluster-and-sentinel-together) | Sentinel 与 Cluster 对比 |

---

## 待决策问题

1. **Worker 节点是否部署 Redis 从节点?**
   - 需要确认 Worker 节点 (192.168.0.115) 的资源情况
   - 如果部署，是否影响 GPU 调度任务?

2. **是否需要持久化 Redis 数据?**
   - 当前场景下，Redis 主要作为缓存和队列
   - 任务状态存储在数据库中

3. **是否需要跨网络高可用?**
   - 当前 Head 和 Worker 在同一网络 (192.168.0.x)
   - 如需异地灾备，方案需调整

---

## 下一步行动

1. Coordinator 确认是否同意采用 Sentinel 方案
2. 确认 Worker 节点资源情况
3. 制定详细部署计划
4. 安排实施时间窗口

---

**请 @coordinator 审阅并决策**
