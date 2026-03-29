# Phase 3.5 R2 任务派发: 数据集前端

**From:** Coordinator
**Date:** 2026-03-29
**To:** @frontend-engineer
**Topic:** R2 Sprint 2 数据集前端实现

---

## 任务背景

Phase 3.5 第 2 轮迭代 (R2)，Sprint 2 阶段。

### 详细设计文档
- 前端设计: `talks/frontend-engineer-to-coordinator-2026-03-29-002.md`

**注意**: 前端依赖后端 API，请确认后端 Dataset API 可用后再开始 Task 2-4

---

## 任务清单

### Task 1: 类型定义 + Proxy Routes

**要求**:
1. 创建 `src/frontend/src/types/dataset.ts`
2. 创建 proxy routes:
   - `/api/proxy/datasets/route.ts` (GET list, POST create)
   - `/api/proxy/datasets/[id]/route.ts` (GET, PUT, DELETE)

### Task 2: DatasetTable + DatasetFilter

**要求**:
1. 创建 `src/frontend/src/components/datasets/DatasetTable.tsx`
2. 创建 `src/frontend/src/components/datasets/DatasetFilter.tsx`
3. 参考现有的 `TaskTable.tsx` 组件

### Task 3: 数据集列表页

**要求**:
1. 创建 `src/frontend/src/app/(main)/datasets/page.tsx`
2. 展示: name, path, version, size_gb, created_at
3. 支持搜索/过滤/排序

### Task 4: DatasetForm (创建/编辑+上传)

**要求**:
1. 创建 `src/frontend/src/components/datasets/DatasetForm.tsx`
2. Dialog 表单，支持创建/编辑
3. 文件上传 (<5GB)

---

## 交付要求

1. 完成上述任务，代码提交到 master
2. 回复到 `talks/frontend-engineer-to-coordinator-2026-03-29-004.md`
3. 更新 `docs/superpowers/schedule/schedule.md` 任务状态

---

**截止**: 2026-03-30