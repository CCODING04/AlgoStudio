# from: @architect-beta
# to: @coordinator
# date: 2026-03-28
# type: debate-score
# role: API/Security Architect

---

## Architect Beta 评分表

### 问题 1: Redis 高可用方案

| 维度 | Sentinel | 保持单点 | Redis Cluster |
|------|---------|----------|---------------|
| 可行性 | 4 | 5 | 2 |
| 成本 | 3 | 5 | 1 |
| 效益 | 4 | 2 | 5 |
| 风险 | 3 | 4 | 2 |
| 可维护性 | 4 | 5 | 2 |

**推荐**: Sentinel
**理由**:
1. **API 客户端兼容性**: redis-py 成熟支持 Sentinel 协议，无需额外开发
2. **连接池设计**: Sentinel + 连接池可实现自动故障转移，API 层改动最小
3. **安全边界**: Sentinel 端口 (26380) 需严格防火墙，仅允许内网访问
4. **风险关注**: Worker 节点部署 Redis 从节点需评估资源竞争，特别是 GPU 任务调度时的内存压力

**潜在问题**:
- 故障转移时可能有短暂不可用 (秒级)，需 API 层实现重试逻辑
- Sentinel 本身无分片，数据量受单节点限制 (~50GB 预估够用)

---

### 问题 2: JuiceFS 缓存大小配置

| 维度 | 固定 100GB | 动态调整 |
|------|-----------|----------|
| 可行性 | 5 | 3 |
| 成本 | 5 | 2 |
| 效益 | 4 | 3 |
| 风险 | 5 | 2 |
| 可维护性 | 5 | 2 |

**推荐**: 固定 100GB
**理由**:
1. **API/存储层无关**: 此配置对 API 层透明，不影响接口设计
2. **运维可预测性**: 固定大小便于监控脚本和告警阈值设定
3. **安全隔离**: 1.8TB NVMe 分配 100GB 缓存，保留足够空间避免磁盘满风险

**潜在问题**:
- 超大数据集 (500GB-1TB) 首次训练会有缓存未命中，需 NAS 读取
- 建议配合缓存预热策略 (`juicefs warmup`) 作为补充

---

### 问题 3: 测试覆盖率目标

| 维度 | 70% | 分阶段 80% | 90% |
|------|-----|-----------|-----|
| 可行性 | 5 | 4 | 2 |
| 成本 | 5 | 3 | 1 |
| 效益 | 3 | 5 | 4 |
| 风险 | 5 | 4 | 2 |
| 可维护性 | 4 | 5 | 3 |

**推荐**: 分阶段 80%
**理由**:
1. **API Routes 必须 80%+**: 作为用户-facing 接口，稳定性至关重要
2. **安全关键模块 (RBAC/Permission) 必须 90%+**: 权限问题可能引发数据泄露
3. **分支覆盖必须启用**: 当前 0% 是重大隐患，无法发现边界条件 bug
4. **LLM/Agent 模块 60-70% 可接受**: 外部依赖多，高覆盖浪费资源

**分阶段评分建议**:

| 阶段 | 目标 | API 层重点 |
|------|------|------------|
| Phase 2.5 | 65% | api.routes 47% -> 70% |
| Phase 3.0 | 75% | api.routes -> 80% |
| Phase 3.1 | 80% | 全模块达标 |

**API 安全相关建议**:
- `core.auth` 已 100%，需保持
- `api.middleware` 87.3% 良好，继续维护
- 新增 API endpoints 必须 TDD，确保不拉低覆盖率

---

### 问题 4: 存储抽象层重构

| 维度 | Repository Pattern | 保持现状 | 完整重写 |
|------|-------------------|----------|----------|
| 可行性 | 4 | 5 | 2 |
| 成本 | 3 | 5 | 1 |
| 效益 | 5 | 2 | 4 |
| 风险 | 3 | 5 | 2 |
| 可维护性 | 5 | 2 | 4 |

**推荐**: Repository Pattern + Abstract Base Class
**理由**:
1. **与现有模式一致**: QuotaStoreInterface 已验证此模式可行
2. **API 层测试友好**: 可注入 InMemorySnapshotStore 进行集成测试，无需 mock redis
3. **依赖注入降低耦合**: RollbackService 不直接依赖 Redis 实现
4. **安全性提升**: 通过接口约束操作，避免直接暴露 Redis 操作

**关键设计建议**:
```python
# API 层使用依赖注入
class RollbackService:
    def __init__(self, snapshot_store: SnapshotStoreInterface):
        self.snapshot_store = snapshot_store

# 不应暴露实现细节
class RedisSnapshotStore(SnapshotStoreInterface):
    # Redis 特定操作封装在实现层
    pass
```

**迁移风险**:
- Phase 1 创建接口不修改现有代码，风险可控
- 异步接口需注意异常处理一致性
- 建议保留旧类作为别名，逐步迁移

---

## 总结评分

| 问题 | 推荐方案 | 评分 (1-5) | 关键理由 |
|------|----------|-----------|----------|
| Redis HA | Sentinel | 4 | API 兼容性、成熟稳定 |
| JuiceFS 缓存 | 固定 100GB | 5 | 运维简单、可预测 |
| 测试覆盖率 | 分阶段 80% | 4 | 分层目标、安全模块优先 |
| 存储抽象层 | Repository Pattern | 4 | 模式一致、测试友好 |

**综合评价**: 所有推荐方案均合理，与项目当前阶段匹配。Phase 2.5 应聚焦 API Routes 覆盖率提升和存储抽象层 P0 实现。

---

*Architect Beta - 2026-03-28*
