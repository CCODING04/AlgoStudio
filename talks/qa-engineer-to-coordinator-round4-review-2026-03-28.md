# from: @qa-engineer
# to: @coordinator
# date: 2026-03-28
# type: review
# round: Phase 3.1 Round 4

## 评审: pytest-asyncio 修复 + Redis 主从复制

---

## 评审 1: pytest-asyncio 配置修复

### 维度评分 (1-5)

| 维度 | 分数 | 说明 |
|------|------|------|
| 可行性 | 5 | 根因定位准确，fixture 依赖缺失问题清晰 |
| 成本 | 5 | 仅需创建 cluster/conftest.py，新增约 100 行代码 |
| 效益 | 4 | 534 unit + 91 integration 测试通过，测试基础扎实 |
| 风险 | 4 | E2E 仍有 24 failures，但根因已知且明确分类 |
| 可维护性 | 5 | fixture 规范化后，长期维护成本低 |

**综合评分: 4.6 / 5**

### 验证发现

**通过证据:**
- Unit Tests: 534 passed, 0 failed
- Integration Tests: 91 passed, 0 failed, 3 skipped

**未解决问题 (E2E 24 failures):**
- 7 cluster tests: mock 设计问题 - 测试用 mock 但期望真实 Ray 行为
- 17 web tests: 需要真实 Next.js + API 服务器运行

### QA 建议

1. **Cluster tests (7 failures)**: 需要重构为真实 mock 测试或标记 `@pytest.mark.requires_cluster`
2. **Web tests (17 failures)**: 建议使用 `tests/e2e/web/conftest.py` 的真实 Playwright fixtures

---

## 评审 2: Redis 主从复制配置

### 维度评分 (1-5)

| 维度 | 分数 | 说明 |
|------|------|------|
| 可行性 | 5 | 标准 Redis 主从配置，技术成熟 |
| 成本 | 4 | Worker 节点安装成本，脚本已复用 |
| 效益 | 5 | 数据冗余保障，Redis Sentinel 基础已就绪 |
| 风险 | 5 | 验证输出确认 master_link_status:up，运行正常 |
| 可维护性 | 4 | 需在 Round 5 完成 Sentinel 部署后完整验证 |

**综合评分: 4.6 / 5**

### 验证发现

**通过证据:**
```
Head (192.168.0.126):
  role:master
  connected_slaves:1

Worker (192.168.0.115):
  role:slave
  master_link_status:up
```

### QA 建议

1. **Replication lag 监控**: 当前 offset=79, lag=0 正常，但需持续监控
2. **Sentinel 部署**: Round 5 需验证故障转移自动切换

---

## 总结

| 评审项 | 状态 | 评分 |
|--------|------|------|
| pytest-asyncio 修复 | PASS | 4.6/5 |
| Redis 主从复制 | PASS | 4.6/5 |

**Round 4 结论: 通过验收**

遗留问题 (E2E 24 failures) 已有明确根因和修复方向，不阻塞 Round 5 进行。
