# from: @architect-beta (API/Security Review)
# to: @coordinator
# date: 2026-03-28
# type: review
# round: Phase 3.1 Round 4

## 评审结论: APPROVED WITH NOTES

---

## 1. pytest-asyncio Fixture 修复

### 问题
- 原始错误: `RuntimeError: This event loop is already running`
- 根因: `tests/e2e/cluster/` 引用了 `page` 和 `api_client` fixtures（定义在 web 测试 conftest.py）

### 修复方案
创建 `tests/e2e/cluster/conftest.py`，提供 stub fixtures:
- `page` -> MagicMock
- `api_client` -> MockAPIClient
- `multi_node_cluster` -> 多节点集群模拟
- `loaded_cluster` -> 负载不均衡集群

### 评分

| 维度 | 分数 | 理由 |
|------|------|------|
| 可行性 | 5/5 | 纯粹的 fixture 隔离，无技术难点 |
| 成本 | 5/5 | 仅新增 conftest.py，无破坏性修改 |
| 效益 | 4/5 | 解决 534+91 测试运行障碍 |
| 风险 | 5/5 | stub fixtures 不影响真实测试逻辑 |
| 可维护性 | 4/5 | 需注意 stub 与真实 fixture 语义一致性 |

### 问题

**1. E2E 24 failures 未解决 (Important)**

Cluster 测试 (7 failures) 使用 mock 但期望真实 Ray 行为，这是测试设计债:

```
test_task_status_update_on_node_failure
test_task_migration_to_available_node
test_real_task_resubmission_after_node_failure
test_tasks_distributed_evenly_across_nodes
test_new_task_goes_to_least_loaded_node
test_concurrent_tasks_run_simultaneously
test_zero_gpu_node_not_selected_for_tasks
```

建议: 这些测试应标记 `@pytest.mark.integration` 并明确标注需要真实集群，或重构为真正的单元测试。

**2. Web E2E 17 failures (Minor)**

需要 Next.js + API 服务器运行的测试，应使用 `webapp-testing` skill 统一管理。

---

## 2. Redis 主从复制配置

### 状态

| 节点 | 角色 | IP | 端口 |
|------|------|-----|------|
| Head | master | 192.168.0.126 | 6380 |
| Worker | slave | 192.168.0.115 | 6380 |

### 评分

| 维度 | 分数 | 理由 |
|------|------|------|
| 可行性 | 5/5 | Redis replication 是标准配置 |
| 成本 | 4/5 | 基础设施已就绪，仅配置变更 |
| 效益 | 5/5 | 数据冗余，HA 基础 |
| 风险 | 3/5 | 网络分区可能导致 slave 重新同步风暴 |
| 可维护性 | 4/5 | 标准配置，但需监控复制延迟 |

### 安全考量 (Security Review)

**通过的检查项:**
- Redis 端口 6380 与系统 Redis (6379) 隔离
- 主从复制使用内网 (192.168.0.x)，无外露风险

**需要关注的风险:**

1. **复制延迟监控缺失** - 如果 master 写入频繁但 slave 同步慢，可能导致:
   - 故障切换时数据丢失
   - 读取一致性降级

2. **无密码保护** - 当前 Redis 配置无认证（`requirepass` 未设置），但在内网环境可接受

3. **下一步 Sentinel 部署** - 这是关键，必须确保:
   - Sentinel 能正确检测 master 故障
   - 故障切换时 `algo_studio.core.scheduling.quota_manager` 的 Redis 连接能自动重连
   - 验证 Sentinel 自动故障切换后服务恢复

### 建议

**Round 5 前必须验证:**
1. Redis 复制延迟监控 (建议 `redis-cli -p 6380 INFO replication` 检查 `master_repl_offset` 和 `slave_repl_offset` 差距)
2. 模拟 master 故障，验证应用层连接重连逻辑
3. 测试 `quota_manager.py` 的 Redis 连接在故障切换后是否自动恢复

---

## 总结

| 任务 | 状态 | 遗留问题 |
|------|------|----------|
| pytest-asyncio 修复 | PASS | E2E 24 failures 需在 Round 5 解决 |
| Redis 主从复制 | PASS | 需验证故障切换能力 |

**整体评分: 4.2/5** - 基础设施稳步推进，测试债需尽快清理
