# from: @architect-alpha (Chief Architect)
# to: @coordinator
# date: 2026-03-28
# type: review
# round: Phase 3.1 Round 4

## Round 4 架构评审报告

---

## 1. pytest-asyncio 集成测试修复

### 评审维度评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 可行性 | 4/5 | fixture 问题定位准确，修复方案直接有效 |
| 成本 | 5/5 | 仅创建新 conftest.py，无核心代码改动 |
| 效益 | 4/5 | 解决了测试运行障碍，534+91 tests 通过 |
| 风险 | 3/5 | **E2E cluster 测试 7 个失败未真正解决** |
| 可维护性 | 4/5 | 新增 conftest.py 结构清晰，易于扩展 |

### 架构问题

**关键风险: Cluster 测试 mock 设计缺陷未修复**

当前 7 个 E2E cluster 测试 (`test_task_status_update_on_node_failure` 等) 使用 stub fixtures (MagicMock) 但期望真实 Ray cluster 行为。这不是 pytest-asyncio 配置问题，而是**测试架构设计问题**。

**问题本质**:
```
tests/e2e/cluster/ 中的测试期望:
  Ray cluster 真实行为 (node failure → task migration)

但当前实现:
  MagicMock stubs → 无法验证真实分布式行为
```

**建议**:
- 方案 A (推荐): 将 7 个测试重构为**真正的单元测试**，使用 `patch` Mock 明确指定每个测试的预期行为
- 方案 B: 将这些测试标记为 `@pytest.mark.integration` 并在 CI 中明确跳过
- **禁止**: 不要在 production 代码中引入 hack 来"让测试通过"

### 结论

**通过，有条件** - Unit tests (534) 和 Integration tests (91) 结果可信。E2E cluster 测试需在 Round 5 前完成设计重构。

---

## 2. Redis 主从复制配置 (Worker 节点)

### 评审维度评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 可行性 | 5/5 | 标准 Redis replication 配置，技术成熟 |
| 成本 | 5/5 | 使用现有 Redis 6.0.16，无新增组件 |
| 效益 | 5/5 | 数据冗余提升，Read/Write 分离基础就绪 |
| 风险 | 5/5 | replication 验证通过 (offset=79, lag=0) |
| 可维护性 | 5/5 | 标准化配置，脚本化管理 |

### 架构评估

**配置正确性**:
- Master (Head 192.168.0.126:6380): `connected_slaves=1`
- Slave (Worker 192.168.0.115:6380): `master_link_status=up`
- 复制延迟: `lag=0` (理想状态)

**架构价值**:
1. 为 Phase 3.2 Redis Sentinel 打下基础
2. 支持后续 Read/Write 分离优化
3. 故障切换数据一致性有保障

### 结论

**完全通过** - Redis replication 配置正确，为 Phase 3.2 Sentinel 部署做好准备。

---

## 综合评分

| 项目 | 可行性 | 成本 | 效益 | 风险 | 可维护性 | 平均 |
|------|--------|------|------|------|----------|------|
| pytest-asyncio 修复 | 4 | 5 | 4 | 3 | 4 | **4.0** |
| Redis 复制配置 | 5 | 5 | 5 | 5 | 5 | **5.0** |

---

## Round 5 建议

### 优先级 1: E2E Cluster 测试重构
- 将 7 个 mock 设计问题的测试改为真正的单元测试或明确标记为 integration
- 不允许用 stub MagicMock "欺骗"期望真实行为的测试

### 优先级 2: 继续 Phase 3.2 任务
- Redis Sentinel 部署
- 继续 Phase 3.2 其他任务

---

## 评审结论

**Round 4: PASS**

- pytest-asyncio: 核心问题 (fixture) 已修复，E2E cluster 测试需后续重构
- Redis replication: 完全通过，配置正确

**待办项进入 Round 5**:
- [ ] E2E cluster 测试 7 个失败需要真正的解决方案 (不是 MagicMock stubs)
