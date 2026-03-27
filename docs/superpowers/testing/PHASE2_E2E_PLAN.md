# Phase 2 E2E 测试规划

**版本:** v1.0
**创建日期:** 2026-03-26
**角色:** QA Engineer
**状态:** 设计完成

---

## 1. E2E 测试概览

### 1.1 测试目标

验证 AlgoStudio Phase 2 核心功能的端到端业务流程，确保：
- SSH 部署流程自动化完成
- Web Console 所有页面功能正常
- 多节点集群调度和任务执行正确

### 1.2 测试环境

| 组件 | 地址 | 用途 |
|------|------|------|
| Head Node | 192.168.0.126 | Ray head, API server |
| Worker Node | 192.168.0.115 | Ray worker |
| Web Console | http://localhost:3000 | 前端 |
| API | http://localhost:8000 | 后端 |

### 1.3 工具选型

| 工具 | 用途 | 版本 |
|------|------|------|
| Playwright | E2E 测试框架 | >= 1.40 |
| pytest | 测试运行器 | >= 7.0 |
| Allure | 测试报告 | 2.20 |

---

## 2. SSH 部署流程 E2E

### 2.1 测试场景

#### TC-SSH-001: Worker 节点自动部署

```gherkin
场景: Worker 节点自动化部署
  假设系统中有 1 个 Head 节点
  当用户在 Deploy 页面添加新 Worker 节点
  且填写正确的 SSH 连接信息
  当点击部署按钮
  那么系统应自动执行以下步骤:
    - SSH 连接到 Worker 节点
    - 安装项目依赖
    - 配置 Ray worker
    - 重启 Ray 集群
    - Worker 节点成功加入集群
```

#### TC-SSH-002: SSH 连接失败处理

```gherkin
场景: SSH 连接失败时正确报错
  当用户输入错误的 SSH 凭证
  当点击部署按钮
  那么系统应显示连接失败错误
  且不阻塞其他操作
```

#### TC-SSH-003: 部署状态实时显示

```gherkin
场景: 部署过程状态实时更新
  当用户发起部署
  那么页面应显示部署进度
  且完成后显示成功状态
```

### 2.2 验证点

| 验证点 | 检查方式 | 预期结果 |
|--------|----------|----------|
| SSH 连接 | ray status | Worker 显示 alive |
| 依赖安装 | ray exec | torch 导入成功 |
| Ray 配置 | ray nodes | Worker 正确配置 |
| 集群状态 | API /api/hosts | 节点状态准确 |

### 2.3 测试数据

```yaml
worker_nodes:
  - hostname: "192.168.0.115"
    ssh_user: "admin10"
    ssh_password: "${SSH_PASSWORD}"  # from env
  - hostname: "192.168.0.120"
    ssh_user: "admin20"
    ssh_password: "${SSH_PASSWORD}"
```

---

## 3. Web Console E2E

### 3.1 测试场景

#### TC-WEB-001: Dashboard 页面

```gherkin
场景: Dashboard 显示集群概览
  当用户打开 Dashboard 页面
  那么应显示:
    - 集群节点总数
    - 活跃任务数
    - GPU 使用率图表
    - 最近任务列表
```

#### TC-WEB-002: Tasks 页面 - 任务列表

```gherkin
场景: Tasks 页面显示任务列表
  当用户打开 Tasks 页面
  那么应显示所有任务的:
    - 任务 ID
    - 任务类型
    - 状态 (pending/running/completed/failed)
    - 创建时间
```

#### TC-WEB-003: Tasks 页面 - 创建任务

```gherkin
场景: 创建新的训练任务
  当用户点击 "新建任务"
  且选择算法 simple_classifier v1
  且配置训练参数 (epochs: 10, batch_size: 32)
  当点击提交
  那么任务应成功创建
  且页面跳转到任务详情
  且任务状态为 pending
```

#### TC-WEB-004: Tasks 页面 - SSE 进度更新

```gherkin
场景: 任务进度实时更新
  当用户创建训练任务
  且任务开始运行
  那么页面应通过 SSE 接收进度更新
  且进度条实时更新
  且完成后显示 completed 状态
```

#### TC-WEB-005: Hosts 页面 - 节点列表

```gherkin
场景: Hosts 页面显示集群节点
  当用户打开 Hosts 页面
  那么应显示所有节点的:
    - 主机名
    - IP 地址
    - 状态 (alive/dead)
    - GPU 信息
    - 资源使用率
```

#### TC-WEB-006: Hosts 页面 - 节点详情

```gherkin
场景: 查看节点详细信息
  当用户点击节点
  那么应显示:
    - CPU/内存/磁盘使用率
    - GPU 型号和利用率
    - 当前运行的任务
```

#### TC-WEB-007: Deploy 页面 - 添加节点

```gherkin
场景: 添加新 Worker 节点
  当用户打开 Deploy 页面
  且点击 "添加节点"
  且填写 SSH 信息和节点地址
  当点击部署
  那么节点应开始部署流程
  且完成后出现在 Hosts 页面
```

### 3.2 验证点矩阵

| 页面 | 验证点 | 检查方式 |
|------|--------|----------|
| Dashboard | 集群概览数据 | API 数据一致性 |
| Dashboard | 图表渲染 | 无 JS 错误 |
| Tasks | 任务列表 | 数据完整性 |
| Tasks | 新建任务 | 后端 API 验证 |
| Tasks | SSE 更新 | 实时性 < 1s |
| Hosts | 节点列表 | 与 ray nodes 一致 |
| Hosts | 节点详情 | GPU 数据准确 |
| Deploy | 添加节点 | SSH 部署成功 |
| Deploy | 部署状态 | 进度实时更新 |

### 3.3 跨浏览器测试矩阵

| 浏览器 | TC-SSH | TC-WEB-001~003 | TC-WEB-004 | TC-WEB-005~007 |
|--------|--------|----------------|------------|----------------|
| Chrome | P0 | P0 | P0 | P0 |
| Firefox | P1 | P1 | P1 | P1 |
| Safari | P2 | P2 | P2 | P2 |

---

## 4. 多节点集群 E2E

### 4.1 测试场景

#### TC-CLUSTER-001: 任务分发到多个节点

```gherkin
场景: 训练任务自动分配到最优节点
  假设集群有 2 个 Worker 节点
  且节点 1 GPU 占用 80%
  且节点 2 GPU 占用 20%
  当用户提交训练任务
  那么任务应分配到节点 2 (负载更低)
```

#### TC-CLUSTER-002: 节点故障时任务迁移

**Round 2 补充:** 增加了任务迁移验证

```gherkin
场景: Worker 节点离线时任务状态更新
  假设有任务在节点 1 运行
  当节点 1 突然离线
  那么该任务状态应更新为 failed
  且错误信息应记录

场景: 任务应迁移到其他可用节点
  假设有任务在节点 1 运行
  当节点 1 突然离线
  那么任务应:
    - 被标记为 pending (等待重新调度)
    - 配置参数应保留
    - 错误信息应记录节点离线原因
```

**验证点:**
| 验证点 | 检查方式 | 预期结果 |
|--------|----------|----------|
| 任务状态更新 | API 查询 | 30s 内状态更新为 failed/pending |
| 任务迁移 | 重新调度 | 任务可迁移到其他节点 |
| 配置保留 | API 查询 | epochs, batch_size 等参数保留 |
| 错误记录 | API error 字段 | 包含节点离线原因 |

**实现文件:** `tests/e2e/cluster/test_failure_recovery.py`

#### TC-CLUSTER-003: 多任务并发调度

```gherkin
场景: 多个任务同时提交时正确调度
  当用户同时提交 5 个训练任务
  且集群有 2 个 GPU 节点
  那么调度器应:
    - 公平分配任务到节点
    - 保持 GPU 不超额分配
    - 按提交顺序处理
```

#### TC-CLUSTER-004: 调度优先级验证

```gherkin
场景: 调度器按优先级处理任务
  假设有 3 个任务:
    - 任务 A: 优先级 high
    - 任务 B: 优先级 normal
    - 任务 C: 优先级 low
  当集群资源不足
  那么任务应按优先级顺序调度
```

#### TC-CLUSTER-005: 配额管理集成

```gherkin
场景: 配额限制下任务提交
  假设用户配额为 2 个并发任务
  当用户已运行 2 个任务
  且尝试提交第 3 个任务
  那么第 3 个任务应:
    - 被拒绝并提示配额不足
    - 或进入等待队列
```

### 4.2 验证点

| 验证点 | 检查方式 | 预期结果 |
|--------|----------|----------|
| 任务分发 | ray.get_runtime_context().node_id | 任务在预期节点 |
| 节点故障 | 任务状态 | 30s 内状态更新 |
| 并发调度 | 任务分配均匀度 | 负载差异 < 20% |
| 优先级调度 | 任务执行顺序 | 符合优先级 |
| 配额限制 | API 响应/任务状态 | 正确拒绝/排队 |

### 4.3 测试数据

```yaml
cluster_config:
  head: 192.168.0.126
  workers:
    - 192.168.0.115
    - 192.168.0.120

tasks:
  concurrent_train:
    count: 5
    algorithm: simple_classifier
    config:
      epochs: 5
      batch_size: 16

  priority_test:
    - priority: high
      task_type: train
    - priority: normal
      task_type: train
    - priority: low
      task_type: train
```

---

## 5. E2E 测试用例清单

### 5.1 测试用例汇总

| ID | 优先级 | 类型 | 估计工时 |
|----|--------|------|----------|
| TC-SSH-001 | P0 | SSH | 2h |
| TC-SSH-002 | P1 | SSH | 1h |
| TC-SSH-003 | P1 | SSH | 1h |
| TC-WEB-001 | P0 | Web | 1h |
| TC-WEB-002 | P0 | Web | 2h |
| TC-WEB-003 | P0 | Web | 2h |
| TC-WEB-004 | P0 | Web | 3h |
| TC-WEB-005 | P0 | Web | 1h |
| TC-WEB-006 | P0 | Web | 1h |
| TC-WEB-007 | P0 | Web | 3h |
| TC-CLUSTER-001 | P0 | Cluster | 3h |
| TC-CLUSTER-002 | P1 | Cluster | 2h |
| TC-CLUSTER-003 | P0 | Cluster | 3h |
| TC-CLUSTER-004 | P1 | Cluster | 2h |
| TC-CLUSTER-005 | P0 | Cluster | 2h |

**总计:** P0: 10 cases, 24h
        P1: 5 cases, 8h

### 5.2 测试用例执行顺序

```
Phase 1: 环境验证 (30min)
  └─ TC-SSH-001 (基础 SSH 部署)

Phase 2: Web Console 基础功能 (6h)
  ├─ TC-WEB-001 (Dashboard)
  ├─ TC-WEB-002 (Tasks 列表)
  ├─ TC-WEB-003 (创建任务)
  └─ TC-WEB-005 (Hosts 列表)

Phase 3: Web Console 高级功能 (6h)
  ├─ TC-WEB-004 (SSE 进度)
  ├─ TC-WEB-006 (Hosts 详情)
  └─ TC-WEB-007 (Deploy 添加节点)

Phase 4: 多节点集群 (10h)
  ├─ TC-CLUSTER-001 (任务分发)
  ├─ TC-CLUSTER-003 (并发调度)
  ├─ TC-CLUSTER-005 (配额管理)
  ├─ TC-CLUSTER-002 (故障处理)
  └─ TC-CLUSTER-004 (优先级)

Phase 5: 异常场景 (4h)
  ├─ TC-SSH-002 (SSH 失败)
  └─ TC-SSH-003 (状态更新)
```

---

## 6. 测试脚本结构

```
tests/
  e2e/
    conftest.py                 # pytest fixtures
    playwright.config.ts        # Playwright 配置
    ssh/
      test_deploy_flow.py       # SSH 部署测试
      test_deploy_status.py     # 部署状态测试
    web/
      test_dashboard.py         # Dashboard 测试
      test_tasks.py            # Tasks 测试
      test_hosts.py            # Hosts 测试
      test_deploy.py           # Deploy 测试
    cluster/
      test_task_dispatch.py     # 任务分发测试
      test_concurrent.py        # 并发测试
      test_quota.py            # 配额测试
      test_failure.py          # 故障测试
    pages/                      # Page Object 模型
      dashboard_page.py
      tasks_page.py
      hosts_page.py
      deploy_page.py
```

---

## 7. 执行计划

### 7.1 Week 2 执行计划

| 日期 | 任务 | 负责人 |
|------|------|--------|
| Day 1 | 环境搭建 + TC-SSH-001 | @qa |
| Day 2 | TC-WEB-001 ~ TC-WEB-003 | @qa |
| Day 3 | TC-WEB-004 ~ TC-WEB-007 | @qa |
| Day 4 | TC-CLUSTER-001, 003, 005 | @qa |
| Day 5 | TC-CLUSTER-002, 004 + 异常场景 | @qa |

### 7.2 每日检查点

- 每日站会前完成测试用例执行
- 缺陷及时记录到 JIRA
- 测试报告更新到 `tests/reports/`

---

**文档状态:** 正式版
**下一步:** 开始实现 E2E 测试脚本
