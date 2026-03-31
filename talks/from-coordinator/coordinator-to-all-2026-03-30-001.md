# Phase 3.6 R11 - 任务分派

**日期:** 2026-03-30
**轮次:** R11
**目标:** 提高覆盖率至 75%+，E2E 测试验证

---

## 当前状态

### 单元测试覆盖率 (R10)
| Metric | Value | Status |
|--------|-------|--------|
| Statements | 72.16% | PASS |
| Branches | 48.54% | PASS |
| Functions | 58% | PASS |
| Lines | 70.84% | PASS |

### 待改进项
1. `components/datasets`: 12.35% statements (需要测试)
2. `components/tasks/TaskWizard.tsx`: 53.96% statements
3. `components/deploy/DeployWizard.tsx`: 55.1% statements
4. Branches 覆盖率偏低 (48.54%)

---

## 任务分派

### @frontend-engineer (R11)

**任务 1: 继续扩展覆盖率**
- 添加 `components/datasets/` 测试文件 (DatasetSelector, DatasetFilter, DatasetForm)
- 改进 TaskWizard 和 DeployWizard 的分支覆盖率
- 目标: 覆盖率提升至 75%+

**任务 2: E2E 测试运行**
- 运行 `cd /home/admin02/Code/Dev/AlgoStudio/src/frontend && npm run dev &`
- 运行后端 `cd /home/admin02/Code/Dev/AlgoStudio && PYTHONPATH=src .venv/bin/uvicorn algo_studio.api.main:app --host 0.0.0.0 --port 8000 &`
- 执行 E2E 测试 `cd /home/admin02/Code/Dev/AlgoStudio && PYTHONPATH=src pytest tests/e2e/web/ -v --tb=short 2>&1 | head -100`

---

## 执行后报告内容

1. 覆盖率数据 (before/after)
2. 添加的测试文件列表
3. E2E 测试运行结果
4. 发现的问题和改进建议
