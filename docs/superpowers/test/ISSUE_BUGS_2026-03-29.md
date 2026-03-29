# Phase 3.4 Web Console Bug 记录

**日期**: 2026-03-29
**阶段**: Phase 3.4 Web Console 迭代完成后发现

---

## Bug 1: 主机状态显示不正确

### 描述
Web Console 的 /hosts 页面一直显示节点为"离线"状态，但后端 API 返回节点状态为 `idle`。

### 根本原因
前端和后端状态值不匹配：

| 组件 | 状态值 |
|------|--------|
| 后端 API (ray_client.py) | `idle`, `busy`, `offline` |
| 前端 (hosts/page.tsx) | `online`, `offline` |

### 影响
- 主机列表页面错误显示所有节点为离线
- 用户无法区分在线/离线节点

### 修复方案
修改 `src/frontend/src/app/(main)/hosts/page.tsx`:
- 将 `status === 'online'` 改为 `status === 'idle'`
- 或添加映射: `idle` → 在线, `busy` → 繁忙

---

## Bug 2: 任务分发问题（需进一步确认）

### 描述
待处理(pending)状态的任务一直没有被分配节点执行。

### 分析
- 后端调度器和 Ray 集群正常工作
- 手动调用 `POST /api/tasks/{taskId}/dispatch` 后任务正常运行
- 任务分配到了 `admin10-System-Product-Name` 节点
- 任务进度正常更新

### 可能原因
1. 自动分发未启用
2. 调度器轮询间隔太长
3. 调度器内部问题

### 需确认
- 调度器是否应该自动分发 pending 任务？
- 自动分发的时间间隔是多少？

---

## 相关文件

### Bug 1 相关
- `src/frontend/src/app/(main)/hosts/page.tsx` (前端)
- `src/algo_studio/core/ray_client.py` (后端 NodeStatus)

### Bug 2 相关
- `src/algo_studio/core/task.py` (TaskManager)
- `src/algo_studio/core/scheduler/wfq_scheduler.py` (调度器)
- `src/algo_studio/api/routes/tasks.py` (API)

---

## 优先级

| Bug | 优先级 | 负责人 | 状态 |
|-----|--------|--------|------|
| Bug 1: 主机状态显示 | P1 | @frontend-engineer | ✅ 已修复 (2026-03-29) |
| Bug 2: 任务分发确认 | P2 | @ai-scheduling-engineer | ✅ 已确认 (2026-03-29) |

## 修复结果

### Bug 1: 主机状态显示 - ✅ 已修复

**修复内容**:
- `src/frontend/src/components/hosts/HostCard.tsx` - 更新 status 映射
- `src/frontend/src/app/(main)/hosts/page.tsx` - 添加 busy 状态显示
- `src/frontend/src/app/(main)/hosts/[nodeId]/page.tsx` - 更新 Badge 组件

**修复后状态映射**:
| 后端状态 | 前端显示 |
|----------|----------|
| `idle` | 在线 (绿色) |
| `busy` | 繁忙 (黄色) |
| `offline` | 离线 (灰色) |

---

### Bug 2: 任务分发问题 - ✅ 已确认 (非Bug)

**调查结论**: 这是 **BY DESIGN** (设计如此)，不是Bug。

**原因**:
1. 任务创建后状态为 `PENDING`，**不会自动分发**
2. 必须手动调用 `POST /api/tasks/{taskId}/dispatch` 才能分发任务
3. TaskManager 没有后台轮询机制
4. WFQScheduler 是独立库组件，不会自动触发调度

**当前设计**:
```
用户创建任务 → status=PENDING
      ↓
[无自动流程]
      ↓
用户手动调用 dispatch API → status=RUNNING
```

**如需自动分发**: 需要实现后台 asyncio 任务轮询 pending 任务，或在任务创建时触发 webhook。

---

## 任务派发记录

| 日期 | Bug | 派发文件 | 结果 |
|------|-----|----------|------|
| 2026-03-29 | Bug 1 | `talks/coordinator-to-frontend-engineer-2026-03-29-001.md` | ✅ 已修复 |
| 2026-03-29 | Bug 2 | `talks/coordinator-to-ai-scheduling-engineer-2026-03-29-001.md` | ✅ 已确认 |
