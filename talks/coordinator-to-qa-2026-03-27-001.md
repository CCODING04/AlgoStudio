# 任务分配：QA 策略 Round 2 完善

**from:** @coordinator
**to:** @qa-engineer
**date:** 2026-03-27
**type:** task
**priority:** P0
**ref:** round1-review

---

## 任务背景

Round 1 QA 评审发现以下问题需要修复：

### 必须修复

1. **Playwright/Python 配置不一致 (严重)**
   - 问题: `conftest.py` 使用 Python 但 `playwright.config.ts` 是 TypeScript
   - 修复: 统一技术栈，建议全 Python 方案

2. **TC-CLUSTER-002 故障恢复测试不完整**
   - 问题: 只验证任务状态更新，未验证故障恢复
   - 补充: 增加故障节点任务迁移验证

3. **SSE 测试可靠性风险**
   - 问题: CI 环境无法访问真实 Ray 集群
   - 建议: 添加 Mock/Fake 方案

### 建议改进

4. **缺陷跟踪索引**
   - 完善 `SUMMARY.md` 或使用 SQLite

## 任务内容

1. 统一 Playwright 技术栈
2. 补充故障恢复测试
3. SSE 测试 Mock 方案
4. 缺陷索引完善

## 输入

- Round 1 评审报告: `docs/superpowers/schedule/round1-review.md`
- E2E 规划: `docs/superpowers/testing/PHASE2_E2E_PLAN.md`

## 输出

- 统一的 Playwright 配置
- 补充的 E2E 测试用例
- 缺陷管理索引

## 截止日期

Week 2 结束前 (2026-03-28)

## 状态

- [x] 任务已接收
- [x] Playwright 配置统一
- [x] 故障恢复测试补充
- [x] SSE Mock 方案

## 完成情况

### 1. Playwright 配置统一 ✅
- 删除了 TypeScript `playwright.config.ts`
- 创建了 Python `tests/e2e/playwright.config.py`
- 统一使用 Python Playwright (`playwright.sync_api`)
- 更新了 `TOOL_CONFIG.md`

### 2. TC-CLUSTER-002 故障恢复测试补充 ✅
- 创建了 `tests/e2e/cluster/test_failure_recovery.py`
- 新增测试用例:
  - `test_task_status_update_on_node_failure`: 验证节点离线时任务状态更新
  - `test_task_migration_to_available_node`: **关键** - 验证任务迁移到其他节点
  - `test_task_state_preservation_on_failure`: 验证任务配置在故障后保留
  - `test_concurrent_task_failure_handling`: 验证多节点同时故障处理

### 3. SSE Mock 方案 ✅
- 在 `tests/e2e/conftest.py` 中实现了 `SSEMockServer` 类
- 支持 CI 环境的 Mock SSE 服务器
- 支持 `USE_MOCK_SERVER=true` 环境变量激活
- 为 `test_sse_progress.py` 提供 Mock 支持

### 4. 缺陷索引完善 ✅
- 更新了 `docs/superpowers/testing/defects/SUMMARY.md`
- 添加了 Round 2 完成工作记录
- 添加了缺陷趋势和分布统计
- 添加了按状态/模块索引
