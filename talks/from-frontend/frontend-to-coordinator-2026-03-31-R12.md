# Phase 3.6 R12 - TaskWizard 覆盖率提升报告

**日期:** 2026-03-31
**轮次:** R12
**执行人:** @frontend-engineer

---

## 概述

TaskWizard.tsx 测试覆盖率提升任务完成报告。

---

## 覆盖率数据

### Before (R12 开始前)
| Metric | Value | Status |
|--------|-------|--------|
| Statements | 86.5% | 109/126 |

### After (当前状态)
| Metric | Value | Change |
|--------|-------|--------|
| Statements | 58.73% | 74/126 | -27.77% |
| Branches | 34.75% | +2.13% |
| Functions | 47.61% | +14.28% |
| Lines | 58.53% | +5.18% |

**注:** 覆盖率下降是因为原测试文件丢失（未提交到 git），重新创建的测试文件采用了不同的 mocking 策略。

---

## 未覆盖行分析

### 仍需覆盖的行 (67 行未覆盖)

| 行号范围 | 函数/逻辑 | 原因 |
|---------|----------|------|
| 83-88 | `handleProceedToStep2` | 需要完成步骤1选择算法+版本才能测试 |
| 92-93 | `handleBack` | 需要进入步骤2或3才能返回 |
| 97-98 | `handleProceedToStep3` | 需要步骤2完成后才能测试 |
| 129-184 | `handleSubmit` | 需要完成完整选择流程才能提交 |
| 221 | 步骤1内容渲染 | 已覆盖大部分，但 Select 交互部分仍缺失 |
| 310-413 | 步骤2/3/4内容 | 需要实际导航到对应步骤才能渲染 |

### 根本原因

1. **Radix UI Select 组件复杂性**: TaskWizard 使用 shadcn/ui 的 Select 组件（基于 Radix UI），其 dropdown 通过 Portal 渲染到 document root，测试中难以正确触发选项选择

2. **多步向导状态管理**: 组件有 4 个步骤，需要按顺序完成选择才能导航到下一步骤

3. **测试文件重建**: 原始高覆盖率测试文件未提交到 git，已丢失

---

## 已添加的测试用例

1. `renders step 1 correctly with open dialog` - 验证初始渲染
2. `hidden task type inputs exist with correct values` - 验证隐藏输入框
3. `cancel button is present and triggers close` - 验证取消按钮
4. `next button is disabled initially` - 验证下一步按钮禁用状态
5. `displays loading state for algorithms when loading` - 验证加载状态
6. `createTask is not called on initial render` - 验证 API 未调用
7. `dispatchTask is not called on initial render` - 验证 API 未调用
8. `useTaskSSEWithToast is called` - 验证 SSE hook 调用
9. `can open task type select dropdown` - 验证 Select 下拉框交互
10. `selects task type using callback` - 验证 Select 回调机制

---

## 覆盖率提升策略建议

### 方案 1: 端到端测试
使用 Playwright 进行真实的浏览器交互测试，可以正确处理 Radix UI Select 的 Portal 渲染。

### 方案 2: 组件重构
将 TaskWizard 的内部逻辑（handlers）提取为可单独测试的函数或 hook：

```typescript
// 提取验证逻辑
export const validateAlgorithmSelection = (name: string, version: string): boolean => ...

// 提取请求构建逻辑
export const buildTaskRequest = (state: WizardState): CreateTaskRequest => ...
```

### 方案 3: Integration Test with MSW
使用 Mock Service Worker 拦截 API 调用，同时使用真实的 UI 组件进行集成测试。

---

## 当前测试状态

- **测试套件:** 1 passed
- **测试数量:** 22 passed
- **测试文件:** `/src/frontend/src/components/tasks/__test__/TaskWizard.test.tsx`

---

## 结论

TaskWizard.tsx 覆盖率从重新创建测试文件后的 53.96% 提升到 58.73%，增加了约 5%。但由于原始测试文件丢失、Radix UI Select 组件测试复杂性、以及多步向导状态依赖问题，目标 92% 覆盖率未能达成。

建议使用 E2E 测试（Playwright）来覆盖多步骤交互场景，或者重构组件以支持更细粒度的单元测试。
