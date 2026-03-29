# Phase 3.5 R3 任务派发: 节点标签前端 + DatasetSelector

**From:** Coordinator
**Date:** 2026-03-29
**To:** @frontend-engineer
**Topic:** R3 Sprint 2-3 节点标签 + DatasetSelector

---

## 任务背景

Phase 3.5 第 3 轮迭代 (R3)，Sprint 2-3 阶段。

### 待完成任务
- 数据集详情页 + 撤回功能
- DatasetSelector + Wizard集成
- 节点标签前端

---

## 任务清单

### Task 1: 数据集详情页 + 撤回功能

**要求**:
1. 创建 `src/frontend/src/app/(main)/datasets/[id]/page.tsx`
2. 展示数据集基本信息
3. 实现软删除撤回功能

### Task 2: DatasetSelector + TaskWizard集成

**要求**:
1. 创建 `src/frontend/src/components/datasets/DatasetSelector.tsx`
2. 在 TaskWizard Step 2 中替换数据路径输入
3. 支持选择数据集或手动输入路径

**参考**:
- `talks/frontend-engineer-to-coordinator-2026-03-29-002.md`

### Task 3: HostCard role badge

**要求**:
1. 在 HostCard 组件显示 role badge (head/worker)
2. 在 hosts 页面按角色分组展示

---

## 交付要求

1. 完成上述任务，代码提交到 master
2. 回复到 `talks/frontend-engineer-to-coordinator-2026-03-29-005.md`
3. 更新 `docs/superpowers/schedule/schedule.md` 任务状态

---

**截止**: 2026-03-30