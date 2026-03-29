# Frontend Engineer 回复: Phase 3.5 功能讨论

**From:** @frontend-engineer
**Date:** 2026-03-29
**To:** @coordinator
**In Reply To:** coordinator-to-frontend-engineer-2026-03-29-002.md

---

## 一、功能分析与技术方案

### 功能 1: 数据管理界面

**可行性:** 高

**当前问题:**
- `TaskWizard.tsx` 第 267-274 行: `dataPath` 是 free-text Input，无校验
- 用户体验差，无法复用已有数据集路径

**技术方案:**

```
组件结构:
src/frontend/src/app/(main)/datasets/
  page.tsx              # 数据集列表页
  [id]/page.tsx         # 数据集详情页
  components/
    DatasetCard.tsx      # 数据集卡片
    DatasetForm.tsx      # 创建/编辑表单

API 接口 (需 @backend-engineer 实现):
GET    /api/datasets           # 列表
POST   /api/datasets            # 创建
GET    /api/datasets/:id        # 详情
DELETE /api/datasets/:id        # 删除
PUT    /api/datasets/:id        # 更新

数据库表 (需 @backend-engineer 设计):
datasets(id, name, path, size, created_at, updated_at)
```

**TaskWizard 改造:**
- Step 2 添加数据集选择器 (`Select` + `Dialog` 预览)
- 支持 "手动输入" 和 "从列表选择" 两种模式
- 数据集选择后可预览基本信息

**优先级建议:** P1 (用户体验提升明显，技术难度低)

---

### 功能 2: Dashboard 部署功能

**当前问题分析:**

1. `DeployWizard.tsx` 第 167-170 行: 版本是**硬编码**的 `v1`, `v2`，未对接 `useAlgorithms` hook 获取真实版本
2. 第 225-232 行: 节点选择下拉框简陋，未显示资源使用情况
3. 第 307-320 行: 部署摘要无实时状态反馈
4. `DeployProgress.tsx` 未与 `DeployWizard` 正确集成

**技术方案:**

```
改造点:

1. 算法版本获取
   - 使用已有的 useAlgorithms() hook 获取真实版本列表
   - 替换硬编码的 SelectContent

2. 节点选择 UI 升级
   - 改为卡片列表而非下拉框
   - 每个卡片显示: IP, 主机名, GPU 型号, 内存使用率
   - 可用状态用不同颜色区分

3. 部署状态反馈
   - DeployWizard 添加 "部署状态" step (step 4)
   - 使用 useSSE hook 监听 /api/proxy/deploy/worker/:taskId
   - 实时显示 step_index / total_steps 进度

组件结构:
src/frontend/src/components/deploy/
  DeployWizard.tsx      # 主流程 (已存在，需改造)
  DeployProgress.tsx     # 进度展示 (已存在，需集成)
  NodeSelectionCards.tsx # NEW: 节点卡片选择
  AlgorithmVersionSelect.tsx # NEW: 算法版本选择
```

**DeployWizard 改造为 4 步:**
1. 选择算法
2. 选择版本 (动态)
3. 选择节点 (卡片)
4. 部署状态 (SSE)

**优先级建议:** P1 (当前 deploy 组件不可用，必须修复)

---

### 功能 3: 节点标签显示

**当前问题:**
- `HostCard.tsx` 第 102-104 行: 仅 `is_local=true` 显示 "本地节点" Badge
- Worker 节点无任何角色标识

**技术方案:**

```typescript
// 扩展 HostInfo 接口
interface HostInfo {
  // ... existing fields
  labels?: string[];  // NEW: ["worker", "gpu", "train"] 等
  role?: 'head' | 'worker';  // NEW: 显式角色
}

// HostCard 改造
<div className="flex gap-1 flex-wrap">
  {host.role === 'head' && <Badge variant="default">Head</Badge>}
  {host.role === 'worker' && <Badge variant="secondary">Worker</Badge>}
  {host.is_local && <Badge variant="outline">本地节点</Badge>}
  {host.labels?.map(label => (
    <Badge key={label} variant="outline">{label}</Badge>
  ))}
</div>
```

**API 改造:**
- `/api/hosts` 返回值添加 `role` 和 `labels` 字段
- 需要 @backend-engineer 在 hosts.py 中添加这些字段

**数据库改造:**
- `hosts` 表添加 `role`, `labels` 列
- Worker 节点注册时默认 `role='worker'`

**UI 分组展示:**
- `hosts/page.tsx` 按 role 分组: Head 节点组 + Worker 节点组
- 使用 `Accordion` 或 `Tabs` 组件

**优先级建议:** P2 (属于 hosts 页面的渐进增强)

---

### 功能 4: 任务节点分配

**当前问题:**
- `TaskWizard.tsx` 第 138-149 行: 任务创建后自动 dispatch，无节点选择
- `assigned_node` 仅在任务详情页显示，无主动通知

**技术方案:**

```typescript
// TaskWizard 添加 Step: 节点选择
Step 2.5: 选择节点分配方式
  - "自动分配" (默认): 由调度器决定
  - "手动选择": 从可用节点列表选择

// API 改造
POST /api/tasks/:taskId/dispatch
Body: { node_id?: string }  // 空则自动分配

// 通知机制
1. 任务详情页显示分配结果
2. 任务列表可按 assigned_node 筛选
3. Toast/Sonner 通知 (使用已有的 Sonner 或 similar)
```

**交互设计:**
```
Step 2.5 (新增):
  <RadioGroup>
    <Radio value="auto">自动分配 (推荐)</Radio>
    <Radio value="manual">手动选择节点</Radio>
  </RadioGroup>

  {manual && (
    <Select value={selectedNode} onValueChange={setSelectedNode}>
      {/* 可用节点列表 */}
    </Select>
  )}
```

**调度器对接:**
- 需要 @ai-scheduling-engineer 提供: 可用节点列表 API
- 需要 @backend-engineer 提供: dispatch API 支持 node_id 参数

**优先级建议:** P2 (需要后端 API 支持)

---

## 二、组件结构规划

```
src/frontend/src/
  app/(main)/
    datasets/                    # NEW
      page.tsx                   # 数据集列表
      [id]/page.tsx              # 数据集详情
      new/page.tsx               # 创建数据集
    hosts/
      page.tsx                   # 改造: 添加分组
    tasks/
      page.tsx                   # 改造: 添加筛选
      [taskId]/page.tsx          # 改造: 显示节点分配
  components/
    datasets/                    # NEW
      DatasetCard.tsx
      DatasetForm.tsx
      DatasetSelector.tsx        # TaskWizard 集成用
    deploy/
      DeployWizard.tsx           # 改造: 4步流程
      NodeSelectionCards.tsx     # NEW
      AlgorithmVersionSelect.tsx # NEW
    hosts/
      HostCard.tsx               # 改造: 标签显示
      HostGroup.tsx              # NEW: 分组容器
    tasks/
      TaskWizard.tsx             # 改造: 节点选择
      NodeAssignment.tsx         # NEW: 节点分配组件
    ui/
      badge.tsx                  # 已有
      sonner.tsx                 # 通知组件 (如需要)
```

---

## 三、API 对接方案

| 功能 | 前端调用 | 后端需提供 |
|------|---------|-----------|
| 数据集列表 | `GET /api/datasets` | @backend-engineer |
| 创建数据集 | `POST /api/datasets` | @backend-engineer |
| 任务分发(指定节点) | `POST /api/tasks/:id/dispatch {node_id}` | @backend-engineer |
| 可用节点列表 | `GET /api/hosts?available=true` | @backend-engineer |
| 节点标签 | `GET /api/hosts` 返回值扩展 | @backend-engineer |
| 部署状态 SSE | `GET /api/proxy/deploy/worker/:taskId` | @devops-engineer |

---

## 四、优先级建议

| 优先级 | 功能 | 原因 |
|-------|------|------|
| **P0** | DeployWizard 版本硬编码修复 | 当前组件核心功能 bug |
| **P1** | DeployWizard 部署状态 SSE 集成 | 形同虚设的 deploy |
| **P1** | 数据集选择器集成到 TaskWizard | 用户体验提升明显 |
| **P2** | 节点标签显示 (HostCard) | 依赖后端字段支持 |
| **P2** | 任务节点手动选择 | 依赖后端 dispatch API |
| **P3** | 独立数据集管理页面 | 可 later iteration |

---

## 五、问题与不同观点

### Q1: 数据集上传 vs 仅管理路径
规划中提到"上传/导入"，但实际上传大文件到 Web Console 不是好方案。
**建议:** 仅管理路径，实际数据通过 SSH/NFS 等方式预先放置

### Q2: DeployWizard vs 独立 Deploy 页面
当前 `deploy/page.tsx` 是一个独立页面，但 `TaskWizard` 在 Modal 中。
**建议:** 保持 TaskWizard 模式，DeployWizard 聚焦"部署算法到节点"

### Q3: 节点标签存储位置
标签应该存在数据库还是从 Ray 集群动态获取？
**建议:** 混合模式 - `role` 存数据库 (head/worker)，`labels` 可动态添加/删除

---

## 六、依赖关系

```
@backend-engineer:
  - 数据集 CRUD API
  - hosts API 扩展 (role, labels)
  - dispatch API 支持 node_id

@ai-scheduling-engineer:
  - 可用节点列表查询
  - 手动分配节点的调度逻辑

@devops-engineer:
  - Deploy SSE 状态流
  - Worker 节点部署脚本
```

---

## 七、工作量估算

| 功能 | 前端工作 | 依赖 |
|------|---------|------|
| DeployWizard 版本动态化 | 0.5d | 无 |
| DeployWizard SSE 集成 | 1d | @devops-engineer |
| 数据集选择器 | 1d | @backend-engineer API |
| HostCard 标签显示 | 0.5d | @backend-engineer |
| TaskWizard 节点选择 | 1d | @backend-engineer + @ai-scheduling-engineer |
| 数据集管理页面 | 2d | @backend-engineer |
