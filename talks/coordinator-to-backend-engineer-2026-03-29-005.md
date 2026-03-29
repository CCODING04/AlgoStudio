# Phase 3.5 R3 任务派发: 数据集后端 + 节点标签

**From:** Coordinator
**Date:** 2026-03-29
**To:** @backend-engineer
**Topic:** R3 Sprint 2-3 数据集后端完善 + 节点标签后端

---

## 任务背景

Phase 3.5 第 3 轮迭代 (R3)，Sprint 2-3 阶段。

### 已完成
- R1: DeployWizard P0 修复 ✅
- R2: 数据集前端 ✅

### 待完成
- 数据集后端 API (R3)
- 节点标签后端 (R4)

---

## 任务清单

### Task 1: 数据集后端完善

**参考**: `talks/backend-engineer-to-coordinator-2026-03-29-002.md`

**要求**:
1. Dataset Model + Migration (如果R2未完成)
2. CRUD API endpoints:
   - `GET /api/datasets` - 列表
   - `POST /api/datasets` - 创建
   - `GET /api/datasets/{id}` - 详情
   - `PUT /api/datasets/{id}` - 更新
   - `DELETE /api/datasets/{id}` - 软删除
   - `POST /api/datasets/{id}/restore` - 恢复
3. RBAC 权限
4. Task 关联

### Task 2: 节点标签后端

**参考**: `docs/superpowers/plans/2026-03-29-phase3-5-unified-plan.md` Section 3.3

**要求**:
1. hosts API 扩展 `role` 和 `labels` 字段
2. 实现 Head/Worker 识别逻辑:
   ```python
   def determine_node_role(node_ip: str, ray_head_ip: str) -> str:
       if node_ip == ray_head_ip:
           return "head"
       return "worker"
   ```
3. API 响应格式:
   ```json
   {
       "node_id": "...",
       "ip": "192.168.0.126",
       "role": "head",
       "labels": ["training", "gpu"],
       "status": "idle",
       ...
   }
   ```

---

## 交付要求

1. 完成上述任务，代码提交到 master
2. 回复到 `talks/backend-engineer-to-coordinator-2026-03-29-005.md`
3. 更新 `docs/superpowers/schedule/schedule.md` 任务状态

---

**截止**: 2026-03-30