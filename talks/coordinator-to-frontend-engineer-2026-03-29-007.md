# Phase 3.5 R8 任务派发: Selector 问题修复

**From:** Coordinator
**Date:** 2026-03-29
**To:** @frontend-engineer
**Topic:** R8 Sprint 4 Selector 问题修复

---

## 任务背景

Phase 3.5 R7 UAT 发现 16 个测试失败，都是 selector 不匹配问题，非功能问题。

### 需要修复的问题

**参考**: `docs/superpowers/test/PHASE35_R7_ISSUE_REPORT.md`

| 问题 | 严重度 |
|------|--------|
| SVG class `lucide-refresh` not found | LOW |
| `data-testid="deploy-node-select"` not present | LOW |
| Deploy button disabled until form complete | LOW |
| `data-testid` not present for deployed nodes | LOW |
| API 307 redirect (需要 -L flag) | MEDIUM |
| Step text rendered differently | LOW |
| Button selector mismatch | LOW |
| SSH key option not implemented | LOW |

---

## 任务清单

### Task 1: 修复 E2E Selector 问题

1. 确保 `data-testid` 属性存在
2. 确保 SVG class 名称正确
3. 确保按钮 selector 正确

### Task 2: API Redirect 问题

1. 检查 hosts API proxy route 是否正确处理 307 redirect
2. 可能需要在 fetch 时添加 `{ redirect: 'follow' }`

---

## 交付要求

1. 修复上述问题
2. 回复到 `talks/frontend-engineer-to-coordinator-2026-03-29-007.md`
3. 更新 `docs/superpowers/schedule/schedule.md`

---

**截止**: 2026-03-30