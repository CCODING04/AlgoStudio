# Phase 3.5 R7 任务派发: 用户验收测试

**From:** Coordinator
**Date:** 2026-03-29
**To:** @user-agent
**Topic:** R7 Sprint 4 用户验收测试

---

## 任务背景

Phase 3.5 第 7 轮迭代 (R7)，Sprint 4 阶段。

### 用户手册
`docs/USER_MANUAL.md`

### Phase 3.5 实现的功能
1. 数据集管理界面 - 创建/编辑/删除/恢复数据集
2. Dashboard 部署 - DeployWizard 真实进度 + 凭据管理
3. 节点标签显示 - Head/Worker 角色标识
4. 任务节点分配 - 手动/自动选择节点

---

## 任务清单

### Task 1: 用户验收测试

使用 Playwright 按照用户手册操作 Web Console:

1. **数据集管理**
   - 创建数据集
   - 编辑数据集
   - 删除并恢复数据集
   - 在 TaskWizard 中选择数据集

2. **部署功能**
   - 打开部署向导
   - 选择算法和版本
   - 选择目标节点
   - 查看真实部署进度

3. **节点标签**
   - 查看 hosts 页面
   - 验证 Head/Worker 标签显示

4. **任务分配**
   - 创建任务
   - 手动选择节点
   - 验证分配通知 toast

### Task 2: 问题报告

如发现问题:
1. 记录问题到 `docs/superpowers/test/PHASE35_R7_ISSUE_REPORT.md`
2. 包括: 操作步骤、预期结果、实际结果、截图

---

## 交付要求

1. 完成验收测试，报告输出到 `docs/superpowers/test/PHASE35_R7_ISSUE_REPORT.md`
2. 如有问题，派发修复任务给相关工程师
3. 更新 `docs/superpowers/schedule/schedule.md`

---

**截止**: 2026-03-30