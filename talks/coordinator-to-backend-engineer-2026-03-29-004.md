# Phase 3.5 R2 任务派发: 数据集后端

**From:** Coordinator
**Date:** 2026-03-29
**To:** @backend-engineer
**Topic:** R2 Sprint 2 数据集后端实现

---

## 任务背景

Phase 3.5 第 2 轮迭代 (R2)，Sprint 2 阶段。

### 详细设计文档
- 后端设计: `talks/backend-engineer-to-coordinator-2026-03-29-002.md`

---

## 任务清单

### Task 1: Dataset Model + Migration

**要求**:
1. 创建 `src/algo_studio/db/models/dataset.py`
   - `Dataset` model: dataset_id (PK), name, path, storage_type, size_gb, version, is_active, deleted_at, etc.
   - `DatasetAccess` model: user_id, team_id, access_level, granted_at, granted_by
2. 创建 Alembic 迁移 `alembic/versions/002_add_datasets.py`
3. 更新 `src/algo_studio/db/models/__init__.py` 导出

### Task 2: CRUD API

**要求**:
1. 创建 `src/algo_studio/api/models/dataset.py` (Pydantic)
2. 创建 `src/algo_studio/api/routes/datasets.py`
3. 实现端点:
   - `GET /api/datasets` - 列表 (分页、搜索)
   - `POST /api/datasets` - 创建
   - `GET /api/datasets/{id}` - 详情
   - `PUT /api/datasets/{id}` - 更新
   - `DELETE /api/datasets/{id}` - 软删除
   - `POST /api/datasets/{id}/restore` - 恢复
   - `POST /api/datasets/{id}/upload` - 上传 (<5GB)
4. 注册路由到 `main.py`

### Task 3: RBAC 权限

**要求**:
1. 扩展 `Permission` 枚举添加 `dataset.read/create/write/delete/admin`
2. 更新 `PROTECTED_ROUTES`
3. 实现数据集级权限检查函数

### Task 4: Task 关联

**要求**:
1. Task model 添加 `dataset_id` 外键
2. 创建任务时验证 dataset_id 存在
3. 更新 `last_accessed_at`

---

## 交付要求

1. 完成上述任务，代码提交到 master
2. 回复到 `talks/backend-engineer-to-coordinator-2026-03-29-004.md`
3. 更新 `docs/superpowers/schedule/schedule.md` 任务状态

---

**截止**: 2026-03-30