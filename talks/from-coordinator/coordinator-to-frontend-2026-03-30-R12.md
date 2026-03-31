# Phase 3.6 R12 - 任务分派

**日期:** 2026-03-30
**轮次:** R12
**目标:** 提高覆盖率至 97%+，完成剩余覆盖缺口

---

## 当前状态

### 单元测试覆盖率 (R11 完成后)
| Metric | Value | Status |
|--------|-------|--------|
| Statements | 95.6% | 979/1024 | PASS |
| Branches | 87.99% | 667/758 | PASS |
| Functions | 94.5% | 189/200 | PASS |
| Lines | 95.39% | 890/933 | PASS |

### 待改进项
1. `components/datasets/DatasetSelector.tsx`: 76.92% statements (40/52)
2. `components/tasks/TaskWizard.tsx`: 86.5% statements (109/126)
3. `components/datasets/DatasetTable.tsx`: 93.93% statements (62/66)

---

## 任务分派

### @frontend-engineer (R12)

**任务 1: DatasetSelector 覆盖率提升至 90%+**
- 当前: 76.92% (40/52 statements)
- 目标: 90%+ (至少 47/52 statements)
- 重点覆盖: createDataset, onDatasetSelect, refreshDatasets 回调分支

**任务 2: TaskWizard 覆盖率提升至 92%+**
- 当前: 86.5% (109/126 statements)
- 目标: 92%+ (至少 116/126 statements)
- 重点覆盖: 所有算法类型分支、错误处理分支

**任务 3: DatasetTable 覆盖率提升至 100%**
- 当前: 93.93% (62/66 statements)
- 目标: 100% (66/66 statements)

---

## 执行步骤

1. 运行 `npm test -- --coverage --testPathPattern="components/datasets|components/tasks"`
2. 分析 lcov-report 中剩余未覆盖行
3. 添加针对性测试
4. 重新运行测试验证覆盖率提升
5. 报告 before/after 数据

---

## 报告内容

1. 覆盖率数据 (before/after)
2. 添加的测试用例列表
3. 剩余未覆盖行的原因分析
