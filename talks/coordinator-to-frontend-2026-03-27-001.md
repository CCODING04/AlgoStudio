# 任务分配：Web Console Round 2 开发

**from:** @coordinator
**to:** @frontend-engineer
**date:** 2026-03-27
**type:** task
**priority:** P1
**ref:** round1-review

---

## 任务背景

Round 1 完成了 Next.js 项目初始化，Round 2 需要开始实际页面开发。

## 任务内容

### Phase 2.2 页面开发

1. **Dashboard 页面** (`/`)
   - 集群状态概览
   - 任务统计卡片
   - 资源使用图表

2. **Tasks 页面** (`/tasks`)
   - 任务列表 (分页、筛选)
   - 任务状态显示
   - 任务详情 (`/tasks/[taskId]`)

3. **API 集成**
   - 与 @backend-engineer 对齐 API
   - SSE 实时更新
   - React Query 集成

## 输入

- 项目结构: `src/frontend/`
- 页面规划: `talks/frontend-to-coordinator-2026-03-26-001.md`

## 输出

- Dashboard 页面组件
- Tasks 页面组件
- API 客户端集成

## 截止日期

Week 2 结束前 (2026-03-28)

## 状态

- [x] 任务已接收
- [x] Dashboard 页面
- [x] Tasks 列表页面
- [x] Task 详情页
- [x] API 集成 (SSE + React Query)

## 完成报告

见 `talks/frontend-to-coordinator-2026-03-27-001.md`
