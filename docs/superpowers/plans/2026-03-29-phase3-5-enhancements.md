# Phase 3.5 Web Console 功能增强规划

**日期**: 2026-03-29
**状态**: 讨论中
**目标**: 团队讨论后确定实施计划

---

## 待讨论功能清单

### 功能 1: 数据管理界面

**问题**: 建立任务阶段只能手动输入数据集地址，用户体验差

**需求**:
- 集中管理数据集（上传/导入/删除）
- 数据集列表展示（名称、路径、大小、创建时间）
- 创建任务时可以选择已有数据集而非手动输入
- 支持数据集预览或基本信息查看

**涉及组件**:
- Frontend: 新建数据集管理页面
- Backend: 数据集 CRUD API
- Database: 数据集表设计

**负责人讨论**: @frontend-engineer + @backend-engineer

---

### 功能 2: Dashboard 部署功能

**问题**: Dashboard 的 deploy 形同虚设，无法操作

**需求**:
- Dashboard 快捷部署入口
- 快速选择算法和目标节点
- 部署状态实时反馈
- 一键部署到可用节点

**涉及组件**:
- Frontend: Dashboard 部署组件
- Backend: Deploy API 集成
- Deploy: 部署流程优化

**负责人讨论**: @frontend-engineer + @devops-engineer

---

### 功能 3: 节点标签显示

**问题**: Hosts 页面本地节点有标注，Worker 节点没有标签

**需求**:
- 区分 Head 节点 / Worker 节点
- Worker 节点显示角色标签
- 可自定义节点标签（用途：训练/推理/存储等）
- 节点分组展示

**涉及组件**:
- Frontend: Hosts 页面标签显示
- Backend: 节点标签 API
- Database: 节点标签存储

**负责人讨论**: @frontend-engineer + @ai-scheduling-engineer

---

### 功能 4: 任务节点分配

**问题**: 任务分发无法手动设置节点，没有动态分配提醒

**需求**:
- 手动选择目标节点（从可用节点列表）
- 或者选择"自动分配"由调度器决定
- 任务分配时有通知/确认
- 动态分配后显示分配结果（哪个节点）

**涉及组件**:
- Frontend: 任务分发界面 + 通知
- Backend: 任务分配 API
- Scheduler: 节点选择逻辑

**负责人讨论**: @frontend-engineer + @ai-scheduling-engineer + @backend-engineer

---

## 团队讨论安排

### 讨论议程

1. **功能优先级排序** - 哪些功能先做？
2. **技术方案初步讨论** - 实现思路
3. **任务分配** - 谁负责哪个功能
4. **时间估算** - 各功能预计工作量
5. **依赖关系** - 功能间的依赖

### 参与角色

| 角色 | 参与讨论 |
|------|----------|
| @coordinator | 主持讨论 |
| @frontend-engineer | 功能1, 2, 3, 4 |
| @backend-engineer | 功能1, 4 |
| @ai-scheduling-engineer | 功能3, 4 |
| @devops-engineer | 功能2 |
| @test-engineer | 测试规划 |

---

## 下一步

1. 各 subagent 阅读本规划文档
2. 通过 talks/ 目录提交各自功能的技术方案或问题
3. Coordinator 汇总后制定实施计划
4. 进入 Phase 3.5 迭代实施
