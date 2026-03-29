# from: @architect-gamma (Scheduling/Performance Architecture Review)
# to: @coordinator
# date: 2026-03-28
# type: review
# round: Phase 3.1 Round 4

## 评审概要

| 任务 | 可行性 | 成本 | 效益 | 风险 | 可维护性 | 平均 |
|------|--------|------|------|------|----------|------|
| pytest-asyncio 集成测试修复 | 5 | 5 | 4 | 4 | 4 | 4.4 |
| Redis 主从复制配置 | 5 | 4 | 5 | 4 | 4 | 4.4 |

**综合评分: 4.4/5 - PASS**

---

## 任务 1: pytest-asyncio 集成测试修复

### 评分详情

| 维度 | 评分 | 说明 |
|------|------|------|
| 可行性 | 5/5 | Stub fixture 方案简单、低风险、易实现 |
| 成本 | 5/5 | 仅添加 `tests/e2e/cluster/conftest.py`，改动极小 |
| 效益 | 4/5 | 534 unit + 91 integration 测试通过，测试基础设施改善 |
| 风险 | 4/5 | Mock 设计问题导致 24 E2E 失败，但不影响 unit/integration |
| 可维护性 | 4/5 | Fixture 隔离良好，结构清晰 |

### 优点

1. **根因分析准确** - 正确识别 fixture 依赖缺失而非 event loop 问题
2. **修复方案轻量化** - 新增 conftest.py 而非修改现有测试
3. **测试结果显著改善** - Unit 534 passed, Integration 91 passed

### 问题与风险

**重要 (Important):**
- **24 E2E 测试失败** - Cluster 测试使用 mock 但期望真实 Ray cluster 行为
  - 这些测试需要重构为真正的 mock 测试或标记为需要真实环境
  - 当前 mock 无法验证实际调度决策

**建议 (Minor):**
- E2E 测试应明确标注 `pytest.mark.skip(reason="requires_real_cluster")` 而非让它们失败

### 性能影响

无直接影响。但测试基础设施改善间接支持:
- 未来 WFQScheduler 变更能更快验证
- QuotaManager 回归测试覆盖更全

### 建议行动

1. **High Priority**: Cluster E2E 测试重构 - 分离 mock 测试和真实集群测试
2. **Medium Priority**: 添加 `@pytest.mark.integration` 标记，便于分层执行

---

## 任务 2: Redis 主从复制配置

### 评分详情

| 维度 | 评分 | 说明 |
|------|------|------|
| 可行性 | 5/5 | 标准 Redis replication，文档完善 |
| 成本 | 4/5 | 需要节点配置，但流程清晰 |
| 效益 | 5/5 | Q1 Redis Sentinel 部署的关键前置条件 |
| 风险 | 4/5 | 复制延迟或脑裂可能导致数据不一致 |
| 可维护性 | 4/5 | 标准 Redis 运维；Sentinel 增加运维复杂度 |

### 优点

1. **配置正确** - Master-Slave 关系正确建立
2. **复制状态健康** - `master_link_status:up`，offset 同步正常
3. **基础设施就绪** - 为 Sentinel 自动故障转移奠定基础

### 问题与风险

**重要 (Important):**
- **无自动故障转移** - 当前主从复制需要手动切换；Sentinel 尚未部署
- **复制延迟监控缺失** - 没有监控 `slave_lag` 或 `master_repl_offset` 差异

**建议 (Minor):**
- 下一步 Round 5 应尽快部署 Sentinel 实现自动 failover
- 建议添加 Redis replication lag 监控告警

### 对调度系统的影响

Redis 主从复制对 AI 调度系统至关重要:

1. **QuotaManager 依赖 Redis** - 配额数据需要高可用
2. **Memory Layer 可选 Redis** - 当前支持 SQLite 回退，但分布式场景需要 Redis
3. **任务状态存储** - 调度决策依赖 Redis 中的实时状态

当前复制架构满足 Phase 3.1 Q1 目标的**前置条件**，但需 Sentinel 完成才能算**高可用**。

### 建议行动

1. **High Priority**: Round 5 部署 Sentinel，实现自动故障转移
2. **Medium Priority**: 添加 replication lag 监控

---

## 综合建议

### Round 5 优先任务

1. **Q1 Redis Sentinel 部署** - 完成 Q1 目标的关键
2. **Q4 存储抽象层 Phase 1** - 接口设计审查
3. **Q3 测试覆盖率** - 继续提升，向 65% 目标迈进

### 风险提示

1. **E2E 测试债务** - 24 个 cluster 测试失败不应长期搁置
2. **Redis 可用性** - 无 Sentinel 配置的单点故障风险

---

## 结论

**Round 4 评审结果: PASS (4.4/5)**

两个任务均按计划完成：
- pytest-asyncio 修复建立了更健壮的测试基础设施
- Redis 主从复制为 Q1 高可用目标奠定基础

建议进入 Round 5，优先完成 Sentinel 部署和存储抽象层 Phase 1 接口设计。
