# Phase 3.5 R8 任务派发: E2E Test Selector 修复

**From:** Coordinator
**Date:** 2026-03-29
**To:** @qa-engineer
**Topic:** R8 Sprint 4 E2E Selector 修复

---

## 任务背景

Phase 3.5 R7 UAT 发现 16 个测试失败，都是 selector 不匹配问题。

**参考**: `docs/superpowers/test/PHASE35_R7_ISSUE_REPORT.md`

---

## 任务清单

### Task 1: 修复 E2E Test Selectors

与 @frontend-engineer 协调，同时修复:

1. `test_refresh_button_exists` - 修复 SVG class selector
2. `test_add_node_form_fields` - 修复 `data-testid="deploy-node-select"`
3. `test_deployed_node_shows_status` - API 307 redirect 处理
4. `test_hosts_page_loads` - 修复 text selector
5. 其他 selector 问题

### Task 2: 验证修复

修复后重新运行测试，确保通过率提升

---

## 交付要求

1. 修复 E2E test selectors
2. 回复到 `talks/qa-engineer-to-coordinator-2026-03-29-002.md`
3. 更新 `docs/superpowers/schedule/schedule.md`

---

**截止**: 2026-03-30