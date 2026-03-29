# Phase 3.5 R6 任务派发: 集成测试

**From:** Coordinator
**Date:** 2026-03-29
**To:** @test-engineer, @qa-engineer
**Topic:** R6 Sprint 4 集成测试

---

## 任务背景

Phase 3.5 第 6 轮迭代 (R6)，Sprint 4 阶段。

### 已完成功能 (需要测试)
1. ✅ 数据集管理界面 - Dataset Model + CRUD + API
2. ✅ Dashboard 部署 - DeployWizard + SSE进度 + 凭据API
3. ✅ 节点标签 - hosts API role/labels
4. ✅ 任务节点分配 - dispatch API + SSE allocated事件

---

## 任务清单

### @test-engineer: 单元测试 + 集成测试

**要求**:
1. Dataset API 单元测试
2. dispatch API 集成测试
3. hosts API role/labels 测试
4. 目标覆盖率 80%+

### @qa-engineer: E2E 测试

**要求**:
1. 数据集 CRUD E2E
2. 部署流程 E2E
3. 任务分配 E2E
4. 使用 Playwright

---

## 交付要求

1. 完成测试，测试报告输出到 `docs/superpowers/test/`
2. 回复到 `talks/[role]-to-coordinator-2026-03-29-001.md`
3. 更新 `docs/superpowers/schedule/schedule.md` 任务状态

---

**截止**: 2026-03-30