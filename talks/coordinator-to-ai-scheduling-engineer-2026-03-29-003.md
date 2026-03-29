# Phase 3.5 R3 任务派发: 节点标签 + 调度集成

**From:** Coordinator
**Date:** 2026-03-29
**To:** @ai-scheduling-engineer
**Topic:** R3 Sprint 2-3 节点标签后端 + 调度逻辑

---

## 任务背景

Phase 3.5 第 3 轮迭代 (R3)，Sprint 2-3 阶段。

### 功能 3: 节点标签显示

**参考**: `docs/superpowers/plans/2026-03-29-phase3-5-unified-plan.md` Section 3.3

### 任务清单

### Task 1: Head/Worker 识别逻辑

**要求**:
1. 实现 `determine_node_role(node_ip, ray_head_ip)` 函数
2. Head 节点可以参与任务调度（用户明确指定时）
3. 与 hosts API 集成

**参考**:
- `src/algo_studio/core/ray_client.py`
- `src/algo_studio/api/routes/hosts.py`

### Task 2: 调度器支持角色感知

**要求**:
1. WFQScheduler 支持 `head` 节点参与调度
2. 任务分发时可指定目标节点角色
3. 调度时考虑节点标签

---

## 交付要求

1. 完成上述任务，代码提交到 master
2. 回复到 `talks/ai-scheduling-engineer-to-coordinator-2026-03-29-003.md`
3. 更新 `docs/superpowers/schedule/schedule.md` 任务状态

---

**截止**: 2026-03-30