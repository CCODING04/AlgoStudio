# Phase 3.5 Web Console 功能增强 - 完整实施计划

**日期**: 2026-03-29
**协调**: @coordinator
**状态**: 已确认，待实施

---

## 一、功能概述

Phase 3.5 包含以下4个功能增强：

| # | 功能 | 优先级 | 目标 |
|---|------|--------|------|
| 1 | 数据集管理界面 | P1 | 集中管理数据集，选择而非手动输入 |
| 2 | Dashboard 部署功能 | **P0** | 修复bug，实现真实进度和凭据管理 |
| 3 | 节点标签显示 | P1 | 区分 Head/Worker 节点角色 |
| 4 | 任务节点分配 | P1 | 支持手动/自动分配，实时通知 |

**特别说明**：
- ✅ 数据集支持一定大小（<5GB）的文件上传，5GB以上建议通过其他工具
- ✅ 数据集支持软删除+撤回（时间限制，如7天）
- ✅ **算法同步到 Worker 纳入本阶段**，保证集群内算法一致
- ✅ Head 节点可以参与任务调度

---

## 二、团队成员与职责

| 角色 | 负责功能 |
|------|----------|
| @frontend-engineer | 前端组件、页面、API 集成 |
| @backend-engineer | API、数据库、RBAC |
| @ai-scheduling-engineer | 节点标签、调度逻辑 |
| @devops-engineer | 部署脚本、SSE、凭据管理 |
| @test-engineer | 单元测试、集成测试、E2E |

---

## 三、功能详细方案

### 功能 1: 数据集管理界面

#### 3.1.1 方案说明

**范围**: 数据集管理 + 支持上传 + 软删除撤回

- 5GB以下数据集可通过 Web Console 直接上传
- 5GB以上数据集建议通过 rsync/NFS/JuiceFS 等专业工具
- Web Console 记录：名称、路径、大小、版本(DVC)、创建时间
- 创建任务时从列表选择数据集，而非手动输入路径
- 删除后 7 天内可撤回，7 天后物理删除

#### 3.1.2 后端设计

**数据库模型** (`src/algo_studio/db/models/dataset.py`):

```python
class Dataset(Base, TimestampMixin):
    dataset_id: str (PK, UUID)
    name: str (unique)
    description: Optional[str]
    path: str  # /nas/datasets/xxx
    storage_type: str  # dvc/nas/raw
    size_gb: Optional[float]
    file_count: Optional[int]
    version: Optional[str]  # DVC commit hash
    dvc_path: Optional[str]
    metadata: Optional[Dict]  # JSON
    tags: Optional[List[str]]  # JSON
    is_public: bool
    owner_id: FK(user_id)
    team_id: FK(team_id)
    is_active: bool  # 软删除
    is_deleted: bool  # 删除标记
    deleted_at: Optional[datetime]  # 删除时间（用于计算撤回期限）
    last_accessed_at: Optional[datetime]

class DatasetAccess(Base):
    """细粒度权限控制"""
    id: int (PK)
    dataset_id: FK
    user_id: FK (nullable)
    team_id: FK (nullable)
    access_level: str  # read/write/admin
    granted_at: datetime
    granted_by: str
```

**API 端点**:

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /api/datasets | 列表（分页、搜索） |
| POST | /api/datasets | 创建数据集 |
| GET | /api/datasets/{id} | 详情 |
| PUT | /api/datasets/{id} | 更新 |
| DELETE | /api/datasets/{id} | 删除（软删除，7天可撤回） |
| POST | /api/datasets/{id}/restore | 恢复已删除的数据集 |
| POST | /api/datasets/{id}/upload | 上传数据集文件（<5GB） |
| POST | /api/datasets/{id}/refresh | 刷新元数据 |
| GET | /api/datasets/{id}/access | 权限列表 |
| POST | /api/datasets/{id}/access | 授予权限 |
| DELETE | /api/datasets/{id}/access/{id} | 撤销权限 |
| GET | /api/datasets/{id}/tasks | 关联任务列表 |

**Task 关联**: Task 模型添加 `dataset_id` 外键

**RBAC 权限**:
- `dataset.read` / `dataset.create` / `dataset.write` / `dataset.delete` / `dataset.admin`

#### 3.1.3 前端设计

**页面结构**:
```
/datasets                    # 列表页
/datasets/[id]             # 详情页
```

**组件清单**:
| 组件 | 类型 | 说明 |
|------|------|------|
| DatasetTable | component | 列表 Table |
| DatasetCard | component | 卡片（选择器用） |
| DatasetSelector | component | TaskWizard 内置选择器 |
| DatasetForm | component | 创建/编辑表单 |
| DatasetFilter | component | 筛选栏 |
| useDatasets | hook | React Query hook |

**TaskWizard 集成**:
```tsx
// Step 2 中替换数据路径输入
<DatasetSelector
  value={dataPath}
  onChange={setDataPath}
  placeholder="/mnt/VtrixDataset/data/train"
/>
<span>或手动输入路径: <Input /></span>
```

#### 3.1.4 工作量估算

| 阶段 | 任务 | 负责人 | 工作量 |
|------|------|--------|--------|
| **后端** | | | **14h** |
| Phase 1 | Dataset Model + DatasetAccess Model | @backend | 2h |
| Phase 2 | CRUD API (10个端点，含upload/restore) | @backend | 4h |
| Phase 3 | Task 关联 + RBAC | @backend | 3h |
| Phase 4 | Alembic 迁移 | @backend | 1h |
| Phase 5 | 文件上传服务 | @backend | 2h |
| Phase 6 | 单元测试 | @backend | 2h |
| **前端** | | | **26h (~3.5d)** |
| Phase 1 | 类型定义 + Proxy Routes | @frontend | 4h |
| Phase 2 | DatasetTable + DatasetFilter | @frontend | 4h |
| Phase 3 | 数据集列表页 | @frontend | 3h |
| Phase 4 | DatasetForm (创建/编辑+上传) | @frontend | 5h |
| Phase 5 | 数据集详情页 + 撤回功能 | @frontend | 4h |
| Phase 6 | DatasetSelector + Wizard集成 | @frontend | 6h |
| Phase 7 | use-datasets hook | @frontend | 2h |

---

### 功能 2: Dashboard 部署功能 (P0)

#### 3.2.1 问题分析

| 问题 | 严重度 | 说明 |
|------|--------|------|
| 算法版本硬编码 | **P0** | DeployWizard 里的版本是 v1/v2，未对接 API |
| 部署进度是假数据 | **P0** | setInterval 模拟，与实际状态无关 |
| SSH 密码无法配置 | **P0** | NEXT_PUBLIC_DEPLOY_SSH_PASSWORD 为空 |
| 算法/配置参数被忽略 | P1 | DeployWizard 传参但脚本未使用 |
| 无预部署验证 | P1 | 可能部署到离线节点 |

#### 3.2.2 方案说明

**部署内容**: 部署 Ray Worker 节点加入集群 + **同步算法到 Worker**

**关键改进**:

1. **凭据管理 (Redis)**:
   ```python
   # API 端点
   POST /api/deploy/credential      # 存储加密凭据
   GET  /api/deploy/credentials      # 列出用户凭据
   DELETE /api/deploy/credential/{id} # 删除凭据
   ```
   - 前端传入 `credential_id` 而非明文密码
   - 密码加密存储在 Redis

2. **SSE 真实进度**:
   - 前端连接 `/api/deploy/worker/{task_id}/progress`
   - 显示真实部署步骤和日志

3. **算法同步**:
   - 部署时同步算法目录到 Worker
   - 通过共享存储路径或 rsync

4. **预部署验证**:
   ```python
   GET /api/deploy/nodes/validate/{node_ip}
   # 验证: Ping + SSH 连接 + Ray 状态
   ```

#### 3.2.3 工作量估算

| 阶段 | 任务 | 负责人 | 工作量 |
|------|------|--------|--------|
| **后端** | | | **8h** |
| Phase 1 | Redis 凭据管理 API | @devops | 3h |
| Phase 2 | 预部署节点验证 API | @devops | 2h |
| Phase 3 | 算法同步脚本扩展 | @devops | 3h |
| **前端** | | | **12h** |
| Phase 1 | DeployWizard 版本动态化 | @frontend | 2h |
| Phase 2 | SSE 进度连接 | @frontend | 3h |
| Phase 3 | CredentialModal 组件 | @frontend | 3h |
| Phase 4 | 节点选择卡片列表 | @frontend | 2h |
| Phase 5 | 部署状态 step 集成 | @frontend | 2h |

---

### 功能 3: 节点标签显示

#### 3.3.1 方案说明

**节点角色识别**:
- Head/Worker 通过 Ray Head IP 自动识别
- `role`: "head" | "worker"
- `labels[]`: 自定义标签列表

**Head 节点**: 可以参与任务调度（用户明确指定时）

#### 3.3.2 后端设计

**hosts API 扩展**:
```python
{
    "node_id": "...",
    "ip": "192.168.0.126",
    "role": "head",  # 新增
    "labels": ["training", "gpu"],  # 新增
    "is_local": true,
    "status": "idle",
    ...
}
```

**自动识别逻辑**:
```python
def determine_node_role(node_ip: str, ray_head_ip: str) -> str:
    if node_ip == ray_head_ip:
        return "head"
    return "worker"
```

#### 3.3.3 工作量估算

| 阶段 | 任务 | 负责人 | 工作量 |
|------|------|--------|--------|
| **后端** | | | **4h** |
| Phase 1 | hosts API role/labels 扩展 | @backend | 2h |
| Phase 2 | Head/Worker 识别逻辑 | @ai-scheduling | 2h |
| **前端** | | | **4h** |
| Phase 1 | HostCard role badge | @frontend | 2h |
| Phase 2 | hosts 页面分组展示 | @frontend | 2h |

---

### 功能 4: 任务节点分配

#### 3.4.1 方案说明

**两种分配模式**:
- `scheduling_mode: "auto"` - 调度器自动选择节点
- `scheduling_mode: "manual"` - 用户指定节点

**API 扩展**:
```python
POST /api/tasks/{task_id}/dispatch
Body: { node_id?: string }  # 指定节点，为空则自动分配
```

**分配结果通知**: SSE `allocated` 事件

#### 3.4.2 工作量估算

| 阶段 | 任务 | 负责人 | 工作量 |
|------|------|--------|--------|
| **后端** | | | **8h** |
| Phase 1 | dispatch API node_id 支持 | @backend | 3h |
| Phase 2 | SSE 分配通知事件 | @backend | 3h |
| Phase 3 | 手动分配校验逻辑 | @ai-scheduling | 2h |
| **前端** | | | **6h** |
| Phase 1 | TaskWizard 节点选择步骤 | @frontend | 4h |
| Phase 2 | 分配结果通知 (Sonner) | @frontend | 2h |

---

## 四、Sprint 实施计划

### Sprint 1 (3天) - P0 Bug 修复

| 任务 | 负责人 | 依赖 | 状态 |
|------|--------|------|------|
| DeployWizard 版本硬编码修复 | @frontend | 无 | 待开始 |
| DeployWizard SSE 进度连接 | @frontend | DevOps SSE端点 | 待开始 |
| Redis 凭据管理 API | @devops | Redis | 待开始 |

### Sprint 2 (4天) - 基础设施 + P1功能

| 任务 | 负责人 | 依赖 | 状态 |
|------|--------|------|------|
| Dataset Model + Migration | @backend | Alembic | 待开始 |
| Dataset CRUD API | @backend | Model | 待开始 |
| Redis 预部署验证 API | @devops | Redis | 待开始 |
| 算法同步脚本扩展 | @devops | 无 | 待开始 |
| hosts API role/labels | @backend + @ai-scheduling | 无 | 待开始 |
| dispatch API node_id | @backend | 无 | 待开始 |

### Sprint 3 (3天) - 前端 + 集成

| 任务 | 负责人 | 依赖 | 状态 |
|------|--------|------|------|
| Dataset 列表页 + 详情页 | @frontend | Dataset API | 待开始 |
| DatasetSelector + Wizard | @frontend | Dataset API | 待开始 |
| HostCard role badge | @frontend | hosts API | 待开始 |
| TaskWizard 节点选择 | @frontend | dispatch API | 待开始 |
| SSE 分配通知 | @backend | dispatch API | 待开始 |

### Sprint 4 (2天) - 测试 + 收尾

| 任务 | 负责人 | 依赖 | 状态 |
|------|--------|------|------|
| 单元测试 | @test | 各功能完成 | 待开始 |
| E2E 测试 | @test | 前端完成 | 待开始 |
| 集成测试 | @test | API 完成 | 待开始 |

---

## 五、工作量总览

| 功能 | 后端 | 前端 | 测试 | 合计 |
|------|------|------|------|------|
| 数据集管理 | 14h | 26h | - | 40h |
| Dashboard部署 | 8h | 12h | - | 20h |
| 节点标签 | 4h | 4h | - | 8h |
| 任务分配 | 8h | 6h | - | 14h |
| **合计** | **34h** | **48h** | **~30h** | **~112h** |

**约 16 person-days** (3人并行约5-6天)

---

## 六、测试安排

| 功能 | 单元测试 | 集成测试 | E2E | 总计 |
|------|----------|----------|-----|------|
| 数据集管理 | 15 | 8 | 5 | 28 |
| Dashboard部署 | 10 | 10 | 8 | 28 |
| 节点标签 | 8 | 5 | 3 | 16 |
| 任务分配 | 12 | 10 | 8 | 30 |
| **总计** | **45** | **33** | **24** | **~100** |

**Test Engineer 建议**: 从功能3（节点标签）开始测试，作为最低风险切入点

---

## 七、决策记录

| # | 问题 | 决策 |
|---|------|------|
| 1 | 数据集管理范围 | ✅ 支持上传(<5GB)，支持软删除撤回(7天) |
| 2 | 算法同步 | ✅ 纳入本阶段，保证集群算法一致 |
| 3 | 凭据管理 | ✅ 使用 Redis 存储加密凭据 |
| 4 | Head节点调度 | ✅ 可以参与调度 |

---

## 八、文档索引

| 文档 | 位置 |
|------|------|
| 数据集后端详细设计 | `talks/backend-engineer-to-coordinator-2026-03-29-002.md` |
| 数据集前端详细设计 | `talks/frontend-engineer-to-coordinator-2026-03-29-002.md` |
| Dashboard部署分析 | `talks/devops-engineer-to-coordinator-2026-03-29-001.md` |
| 节点标签方案 | `talks/ai-scheduling-engineer-to-coordinator-2026-03-29-001.md` |
| 测试策略 | `talks/test-engineer-to-coordinator-2026-03-29-001.md` |

---

## 九、执行流程（10轮迭代）

### 9.1 迭代流程总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        10轮迭代流程 (R1 - R10)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Coordinator 制定本轮计划并派发任务                                      │
│  2. Subagent 执行任务 (frontend/backend/ai-scheduling/devops)              │
│  3. Test Engineer 和 QA Engineer 添加/更新测试案例                            │
│  4. User Agent 模拟操作 Web Console (参考用户手册)                           │
│  5. Review Team 评审 (6个subagent)                                         │
│  6. 更新文档 (任务完成情况 + 改进意见)                                      │
│  7. 进入下一轮迭代                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 每轮迭代详细步骤

#### Step 1: Coordinator 制定计划并派发任务

- 根据本轮目标，从 Sprint 计划中选取任务
- 创建任务派发文件到 `talks/` 目录
- 派发给对应的 subagent
- 更新本轮状态到文档

#### Step 2: Subagent 执行任务

**执行顺序**:
1. @frontend-engineer - 前端组件、页面开发
2. @backend-engineer - API、数据库开发
3. @ai-scheduling-engineer - 调度逻辑
4. @devops-engineer - 部署脚本、SSE

**要求**:
- 按任务清单执行，不增减范围
- 完成后更新任务状态
- 通过 talks/ 目录报告结果

#### Step 3: 测试案例更新

**@test-engineer** 和 **@qa-engineer** 负责:
- 根据完成的功能添加测试案例
- 更新单元测试、集成测试、E2E 测试
- 确认测试覆盖是否满足要求
- 如需新增测试，报告给 Coordinator

#### Step 4: User Agent 模拟操作

**@user-agent** (使用 Playwright):
- 参考 `docs/USER_MANUAL.md` 对 Web Console 进行操作
- 测试所有功能流程
- 记录发现的问题
- 输出用户体验报告

#### Step 5: Review Team 评审

**评审团成员**:
- @architect-alpha - 系统架构评审
- @architect-beta - API/安全评审
- @architect-gamma - 调度/性能评审
- @frontend-engineer - 前端评审
- @backend-engineer - 后端评审
- @performance-engineer - 性能评审

**评审内容**:
- 功能完成度
- 代码质量
- 测试覆盖率
- 用户体验
- 改进建议

#### Step 6: 文档更新

**更新文件**:
- `docs/superpowers/plans/2026-03-29-phase3-5-unified-plan.md`
- `docs/superpowers/schedule/schedule.md`
- `talks/[role]-round[N]-[date].md` (汇报文件)

**更新内容**:
- 任务完成情况
- 发现的问题
- 改进和修复意见
- 下一轮计划

### 9.3 迭代安排

| Round | 重点 | Sprint | 任务 |
|-------|------|--------|------|
| R1 | P0 Bug修复 | Sprint 1 | DeployWizard版本、SSE进度、凭据API |
| R2 | 数据集后端 | Sprint 2 | Dataset Model、CRUD API、Migration |
| R3 | 数据集前端 | Sprint 2-3 | Dataset页面、Selector、Wizard集成 |
| R4 | 节点标签 | Sprint 2-3 | hosts API扩展、HostCard标签 |
| R5 | 任务分配后端 | Sprint 2-3 | dispatch API、SSE通知 |
| R6 | 任务分配前端 | Sprint 3 | TaskWizard节点选择、通知 |
| R7 | 算法同步 | Sprint 2-3 | 部署脚本扩展 |
| R8 | 集成测试 | Sprint 4 | 单元测试、E2E测试 |
| R9 | 用户验收 | Sprint 4 | User Agent全面测试 |
| R10 | 最终评审 | Sprint 4 | Review Team评审、收尾 |

### 9.4 评审标准

| 评分项 | 满分 | 要求 |
|--------|------|------|
| 功能完成度 | 30 | 所有计划功能已实现 |
| 代码质量 | 20 | 无critical bug、无security issue |
| 测试覆盖率 | 20 | 达到80%+覆盖率 |
| 用户体验 | 15 | User Agent能完整操作所有功能 |
| 文档完整度 | 15 | 用户手册已更新、API文档完整 |

**及格线**: 70分
**优秀**: 90分+

### 9.5 成功标准

**Round 10 结束时，必须满足**:

1. ✅ User Agent 可完整操作用户手册所有功能
2. ✅ 所有 E2E 测试通过
3. ✅ 测试覆盖率 80%+
4. ✅ 评审评分 90+

### 9.6 角色职责

| 角色 | 迭代中职责 |
|------|-----------|
| @coordinator | 制定计划、派发任务、协调、文档更新 |
| @frontend-engineer | 前端开发、修复 |
| @backend-engineer | 后端API开发、修复 |
| @ai-scheduling-engineer | 调度逻辑、节点标签 |
| @devops-engineer | 部署脚本、SSE、凭据管理 |
| @test-engineer | 单元测试、集成测试 |
| @qa-engineer | E2E测试、验收测试 |
| @performance-engineer | 性能测试、基准测试 |
| @user-agent | Playwright模拟操作、用户体验报告 |
| @architect-alpha/beta/gamma | 架构评审、API评审、性能评审 |

---

**状态**: 执行流程已制定，必须严格按照此流程执行10轮迭代
