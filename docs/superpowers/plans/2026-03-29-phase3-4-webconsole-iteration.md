# Phase 3.4 Web Console 迭代优化计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** 通过 10 轮迭代优化，使 User Agent 能完整按照用户手册操作 Web Console

**Architecture:** 多角色协作迭代流程：Coordinator 调度改进 → Test Agent 添加测试 → User Agent 模拟操作 → Review Team 评审评分 → 下一轮迭代

**Tech Stack:** Playwright (E2E 测试), React (Next.js), FastAPI, Ray

---

## 迭代流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        迭代循环 (R1 - R10)                       │
├─────────────────────────────────────────────────────────────────┤
│  1. Coordinator 调度团队成员实施改进                            │
│  2. Frontend Engineer 修复问题/实现功能                         │
│  3. Test Engineer 添加单元/E2E 测试                             │
│  4. User Agent 使用 Playwright 模拟操作                         │
│  5. Review Team 评审 (评分 + 改进建议)                          │
│  6. 更新 USER_EXPERIENCE_REPORT.md                              │
│  7. 进入下一轮迭代                                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 用户手册功能清单

根据 `docs/USER_MANUAL.md`，以下功能必须可用：

| # | 功能 | 路径 | 优先级 |
|---|------|------|--------|
| 1 | Dashboard 统计卡片 | `/` | P0 |
| 2 | Dashboard 集群状态 | `/` | P0 |
| 3 | Dashboard 资源图表 | `/` | P1 |
| 4 | Dashboard 最近任务 | `/` | P1 |
| 5 | 任务列表查看 | `/tasks` | P0 |
| 6 | 任务搜索 | `/tasks` | P0 |
| 7 | 任务状态筛选 | `/tasks` | P0 |
| 8 | 新建任务 | `/tasks` | P0 |
| 9 | 任务详情 SSE | `/tasks/[taskId]` | P0 |
| 10 | 主机列表查看 | `/hosts` | P0 |
| 11 | 主机状态显示 | `/hosts` | P0 |
| 12 | 主机详情 | `/hosts/[nodeId]` | P1 |
| 13 | 部署向导 | `/deploy` | P1 |
| 14 | 部署进度 | `/deploy` | P1 |

---

## 当前状态基线

### 已修复 (Round 0)
- ✅ 新建任务按钮无反应 → TaskWizard 组件已添加
- ✅ 自动分发任务 → TaskWizard 已实现

### 待验证/修复
- ❌ 任务详情页 → API 重启后任务丢失
- ❌ 部署算法功能 → 待测试
- ❌ 主机详情页 → 待测试
- ❌ SSE 进度推送 → 待验证

### 测试覆盖
- 单元测试: `tests/unit/`
- E2E 测试: `tests/e2e/web/`
- 覆盖率目标: 80%+

---

## Round 1: 基础功能验证

### 任务分配

| 角色 | 负责人 | 任务 |
|------|--------|------|
| Coordinator | @coordinator | 调度任务分配 |
| Frontend Engineer | @frontend-engineer | 修复任务详情页 404 |
| Test Engineer | @test-engineer | 添加任务相关 E2E 测试 |
| User Agent | user-test | 验证任务创建流程 |

### 需要修复的问题

1. **任务详情页 404**
   - 原因: API 重启后内存任务丢失 + 前端 API 调用失败
   - 修复: 确保 API 和前端使用正确的 RBAC_SECRET_KEY

2. **Dashboard 统计卡片**
   - 需要验证数据是否正确显示

### User Agent 测试任务

使用 Playwright 测试以下流程：

```
1. 访问 http://localhost:3000
2. 检查 Dashboard 显示
3. 进入 /tasks 页面
4. 点击新建任务
5. 选择算法 simple_classifier v1
6. 提交任务
7. 检查任务是否出现在列表
8. 点击任务查看详情
```

### 评审标准

| 评分项 | 满分 | 要求 |
|--------|------|------|
| 任务创建流程 | 25 | 完整流程无报错 |
| 任务列表显示 | 25 | 数据显示正确 |
| 任务详情页 | 25 | 页面正常加载 |
| 用户手册匹配度 | 25 | 与文档描述一致 |

**及格线: 70分**

---

## Round 2: 主机监控功能

### 需要验证的功能

1. **主机列表页面** (`/hosts`)
   - 显示节点 IP、状态
   - 在线/离线状态正确

2. **主机详情页** (`/hosts/[nodeId]`)
   - 显示 CPU/GPU/内存信息
   - 点击卡片可进入详情

### User Agent 测试任务

```
1. 访问 /hosts 页面
2. 检查节点列表是否显示 (应有 2 个节点)
3. 检查节点状态是否正确 (Head + Worker)
4. 点击某个主机卡片
5. 进入主机详情页
6. 验证资源信息显示
```

### 评审标准

| 评分项 | 满分 |
|--------|------|
| 主机列表显示 | 30 |
| 主机状态正确 | 30 |
| 主机详情页 | 40 |

---

## Round 3: 部署算法功能

### 需要验证的功能

1. **部署向导** (`/deploy`)
   - 选择算法步骤
   - 选择主机步骤
   - 配置部署步骤

2. **部署进度**
   - SSH 连接
   - 文件同步
   - 依赖安装

### User Agent 测试任务

```
1. 访问 /deploy 页面
2. 选择算法 (simple_classifier v1)
3. 选择目标主机
4. 配置部署选项
5. 点击开始部署
6. 观察部署进度对话框
```

---

## Round 4-Round 10: 迭代优化

每轮迭代根据评审结果制定改进计划：

| Round | 评审重点 | 预期改进 |
|-------|----------|----------|
| R4 | 错误处理 | 添加错误提示、失败恢复 |
| R5 | 性能优化 | 减少加载时间、增加缓存 |
| R6 | UI/UX 改进 | 改善交互体验 |
| R7 | SSE 实时更新 | 验证进度推送 |
| R8 | 边界情况 | 空列表、长时间任务 |
| R9 | 完整流程 | 端到端测试 |
| R10 | 最终验收 | 所有功能可用 |

---

## 角色职责

### Coordinator
- 调度团队成员任务
- 跟踪迭代进度
- 更新 schedule.md

### Frontend Engineer
- 修复发现的问题
- 实现缺失的功能
- 确保 UI 与用户手册一致

### Test Engineer
- 添加单元测试
- 添加 E2E Playwright 测试
- 验证修复没有引入新问题

### User Agent
- 按照用户手册操作
- 记录发现的问题
- 评估用户体验

### Review Team
- @architect-alpha: 架构评审
- @architect-beta: API/安全评审
- @architect-gamma: 调度/性能评审
- @test-engineer: 测试工程评审
- @performance-engineer: 性能基准评审

---

## 输出文件

| 文件 | 位置 | 说明 |
|------|------|------|
| 用户体验报告 | `docs/superpowers/test/USER_EXPERIENCE_REPORT.md` | 每轮更新 |
| E2E 测试报告 | `docs/superpowers/test/E2E_TEST_REPORT.md` | 测试结果 |
| 评审报告 | `docs/superpowers/test/REVIEW_REPORT_R*.md` | 每轮评审 |
| 改进计划 | `docs/superpowers/plans/改进措施-R*.md` | 下轮改进 |

---

## 执行流程

### 每轮迭代步骤

1. **Coordinator 分派任务** (TaskCreate)
2. **Frontend Engineer 修复** (Frontend Engineer agent)
3. **Test Engineer 添加测试** (Test Engineer agent)
4. **User Agent 模拟操作** (General Purpose agent)
5. **Review Team 评审** (Review agents)
6. **更新报告** (更新文档)
7. **进入下一轮**

### 启动命令

```bash
# 确保服务运行
curl -s http://localhost:8000/health && echo "API OK"
curl -s http://localhost:3000 > /dev/null && echo "Web Console OK"

# 运行 E2E 测试
cd /home/admin02/Code/Dev/AlgoStudio
PLAYWRIGHT_BROWSERS_PATH=0 pytest tests/e2e/web/ -v

# 运行单元测试
PYTHONPATH=src pytest tests/unit/ -v --cov=src --cov-report=html
```

---

## 成功标准

**Round 10 结束时，必须满足:**

1. ✅ User Agent 可完整操作用户手册所有功能
2. ✅ 所有 E2E 测试通过
3. ✅ 测试覆盖率 80%+
4. ✅ 评审评分 90+

---

## 当前 Round 状态

| Round | 状态 | 评分 | 主要问题 |
|-------|------|------|----------|
| R1 | ✅ 完成 | 75 | 任务创建modal overlay阻塞、Deploy表单缺少data-testid |
| R2 | ✅ 完成 | 78 | Radix UI data-testid未传递、SSE 401、Hosts API 307 |
| R3 | ✅ 完成 | 80 | SSE修复但test断言问题、Hosts 307、wrapper渲染 |
| R4 | ✅ 完成 | 82 | 修复完成但test infrastructure问题 |
| R5 | ✅ 完成 | 90 | **所有USER_MANUAL操作验证通过** |
| R6-R10 | ⏳ 可跳过 | - | 核心功能已完整 |

### Round 1 评审详情

| 评分项 | 得分 | 说明 |
|--------|------|------|
| 任务创建流程 | 10/25 | modal overlay阻塞task type选择 |
| 任务列表显示 | 25/25 | 完整功能正常 |
| 任务详情页 | 25/25 | 页面正常加载 |
| 用户手册匹配度 | 15/25 | Dashboard stats cards选择器缺失 |

### Round 2 待修复问题

1. **Critical**: TaskWizard modal overlay阻塞交互 - ✅ z-index已修复，data-testid已添加
2. **Critical**: Deploy表单缺少data-testid属性 - ⚠️ 部分添加，deployed-nodes缺失
3. **High**: Dashboard stats cards选择器 - ✅ data-testid已添加
4. **Medium**: SSE endpoint认证401错误 - ❌ 仍需修复

### Round 3 E2E测试结果

| 指标 | R1 | R2 | R3 |
|------|----|----|-----|
| 通过 | 58 | 61 | 63 |
| 失败 | 24 | 22 | 29 |
| 跳过 | 27 | 26 | 17 |

**R3主要改进**:
- SSE 401错误 → 修复为200 (但test assertion问题)
- Dashboard stats cards → 全部通过

**R3仍需修复**:
- Hosts API 307重定向 (redirect: follow未生效)
- Task type options: wrapper data-testid条件渲染
- SSE test: Cache-Control断言/SSEClient迭代器问题
