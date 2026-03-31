# Phase 3.6 R12 - 测试工程师任务

**日期:** 2026-03-30
**轮次:** R12
**目标:** 扩展 E2E 测试覆盖用户操作场景

---

## 当前状态

E2E 测试已覆盖:
- hosts 页面: 主机状态显示、刷新按钮
- task 页面: 任务向导、创建/编辑/删除任务
- dataset 页面: 数据集选择、筛选、创建

### 待扩展 E2E 场景

**任务 1: Deploy 页面 E2E 测试**
- DeployWizard 完整流程测试
- 部署状态显示验证
- 回滚操作测试 (如 UI 支持)

**任务 2: Dashboard E2E 测试**
- ResourceChart 渲染验证
- GPU 使用率热力图交互

**任务 3: 跨页面流程测试**
- 完整用户流程: 主机状态 → 创建任务 → 查看任务进度 → 查看结果

---

## 执行步骤

1. 运行 E2E 测试服务器:
   ```bash
   cd /home/admin02/Code/Dev/AlgoStudio/src/frontend && npm run dev &
   cd /home/admin02/Code/Dev/AlgoStudio && PYTHONPATH=src .venv/bin/uvicorn algo_studio.api.main:app --host 0.0.0.0 --port 8000 &
   ```

2. 执行现有 E2E 测试 `pytest tests/e2e/web/ -v --tb=short`

3. 分析覆盖率缺口，添加新测试

4. 报告 E2E 测试结果

---

## 报告内容

1. 当前 E2E 测试数量
2. 新增测试用例列表
3. E2E 覆盖率改善情况
