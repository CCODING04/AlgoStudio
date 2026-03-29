# Phase 3.5 R4 任务派发: 任务节点分配后端

**From:** Coordinator
**Date:** 2026-03-29
**To:** @backend-engineer
**Topic:** R4 Sprint 3 任务节点分配后端

---

## 任务背景

Phase 3.5 第 4 轮迭代 (R4)，Sprint 3 阶段。

### 功能 4: 任务节点分配

**参考**: `docs/superpowers/plans/2026-03-29-phase3-5-unified-plan.md` Section 3.4

---

## 任务清单

### Task 1: dispatch API node_id 支持

**要求**:
1. 扩展 `POST /api/tasks/{task_id}/dispatch` 支持 `node_id` 参数
2. 两种调度模式:
   - `scheduling_mode: "auto"` - 调度器自动选择节点
   - `scheduling_mode: "manual"` - 用户指定节点
3. 验证指定节点可用性

**Request Body**:
```json
{
  "node_id": "optional-specified-node-id",
  "scheduling_mode": "auto|manual"
}
```

### Task 2: SSE 分配通知事件

**要求**:
1. Task SSE 端点发送 `allocated` 事件
2. 包含分配的节点信息:
```json
{
  "event": "allocated",
  "task_id": "...",
  "node_id": "...",
  "node_ip": "...",
  "assigned_at": "..."
}
```

### Task 3: 手动分配校验逻辑

**要求**:
1. 检查节点状态是否为 `idle`
2. 检查节点是否有足够资源
3. 检查 Head 节点是否可用于调度

---

## 交付要求

1. 完成上述任务，代码提交到 master
2. 回复到 `talks/backend-engineer-to-coordinator-2026-03-29-006.md`
3. 更新 `docs/superpowers/schedule/schedule.md` 任务状态

---

**截止**: 2026-03-30