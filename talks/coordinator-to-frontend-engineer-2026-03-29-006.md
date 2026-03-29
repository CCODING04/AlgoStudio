# Phase 3.5 R4 任务派发: 任务节点分配前端

**From:** Coordinator
**Date:** 2026-03-29
**To:** @frontend-engineer
**Topic:** R4 Sprint 3 任务节点分配前端

---

## 任务背景

Phase 3.5 第 4 轮迭代 (R4)，Sprint 3 阶段。

### 功能 4: 任务节点分配

**参考**: `docs/superpowers/plans/2026-03-29-phase3-5-unified-plan.md` Section 3.4

---

## 任务清单

### Task 1: TaskWizard 节点选择步骤

**要求**:
1. 在 TaskWizard 添加节点选择步骤 (Step 3 或 4)
2. 显示可用节点列表 (从 hosts API)
3. 支持两种模式:
   - 自动选择 (默认)
   - 手动选择 (用户指定节点)
4. 节点列表显示 role badge

### Task 2: 分配结果通知 (Sonner)

**要求**:
1. 监听 SSE `allocated` 事件
2. 任务分配成功后显示 toast 通知:
   - "任务已分配到 {node_name}"
3. 分配失败显示错误 toast

**参考**:
- `src/frontend/src/components/ui/sonner.tsx` (如存在)
- `src/frontend/src/hooks/use-event-source.ts`

---

## 交付要求

1. 完成上述任务，代码提交到 master
2. 回复到 `talks/frontend-engineer-to-coordinator-2026-03-29-006.md`
3. 更新 `docs/superpowers/schedule/schedule.md` 任务状态

---

**截止**: 2026-03-30