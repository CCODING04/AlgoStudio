# TaskWizard 测试覆盖率分析

**日期:** 2026-03-31
**组件:** TaskWizard
**当前覆盖率:** 65.87% (Statements)
**目标覆盖率:** 85%+

---

## 覆盖率现状

| 指标 | 数值 |
|------|------|
| Statements | 65.87% (85/129) |
| Branches | 50.35% |
| Functions | 71.42% |
| Lines | 65.85% |

### 未覆盖行分析

| 行号 | 函数/逻辑 | 原因 |
|------|----------|------|
| 84-85 | `handleProceedToStep2` 错误处理 | Mock 无法触发 React 状态更新 |
| 92-93 | `handleBack` | 同上 |
| 97-98 | `handleProceedToStep3` | 同上 |
| 129-184 | `handleSubmit` (async) | 需要完整多步流程 |
| 326-413 | Step 2/3 内容渲染 | 依赖前置状态 |

---

## 根本原因：Radix UI Portal 渲染

### 问题描述

Radix UI 的 Select、Dialog 等组件使用 React Portal 将 Dropdown/DialogContent 渲染到 `document.body` 下，而不是组件树内部：

```
真实 DOM 结构:
<body>
  <div id="__next">           ← Next.js 应用根
    <Dialog>
      <DialogContent>
        <SelectTrigger />      ← 组件树中
      </DialogContent>
    </Dialog>
  </div>
  <div id="radix-select-portal">  ← Portal 渲染到这里！
    <SelectContent>
      <SelectItem />          ← 实际点击的 DOM
    </SelectContent>
  </div>
</body>
```

### Jest Mock 的局限性

Jest 测试中的 Mock 只返回 JSX，不创建真实 DOM：

```typescript
// Mock Select - 问题所在
SelectItem: ({ children, value, onClick }) => {
  // 这个 onClick 调用是假的
  // 真实的 React useState 更新不会被触发
  return <div onClick={() => { onClick?.(value); }}>{children}</div>;
}
```

### React 状态流断裂

```typescript
// 真实的点击流程（正常工作）：
User Click → DOM Event → React onClick → useState setter → Re-render

// Mock 的流程（状态断裂）：
User Click → Mock onClick → 直接调用回调 → 状态不更新
```

---

## 已尝试的解决方案

### 1. 回调捕获模式
```typescript
// 捕获 Select 的 onValueChange 回调
const selectCallbacks: Record<string, { onValueChange?: Function }> = {};

Select: ({ onValueChange, 'data-testid': testId }) => {
  if (onValueChange) selectCallbacks[testId] = { onValueChange };
  return <div ...>{children}</div>;
}

// 通过 __getSelectCallback 手动触发
act(() => { callback.onValueChange('train'); });
```

**结果:** 覆盖率提升 56% → 65.87%，但仍无法触发完整状态流。

### 2. Playwright E2E 测试
```python
# test_task_wizard_playwright.py - 已有 9 个测试
def test_task_wizard_opens_from_tasks_page(self, page):
    page.goto("/tasks")
    page.wait_for_load_state("networkidle")
    create_button.click()
```

**结果:** 注释说明 `Due to React hydration issues`，只验证基础 UI。

---

## 建议方案

### 方案 1：组件重构（推荐）

提取可测试逻辑为纯函数：

```typescript
// src/components/tasks/TaskWizard/utils.ts
export function validateStep1(algorithmName: string, version: string): string | null {
  if (!algorithmName || !version) {
    return '请选择算法和版本';
  }
  return null;
}

export function parseConfig(configStr: string): object | null {
  try {
    return JSON.parse(configStr);
  } catch {
    return null;
  }
}

export function buildTaskRequest(taskType: TaskType, ...): CreateTaskRequest {
  // 纯函数，易于测试
}
```

### 方案 2：接受现状

TaskWizard 的 65.87% 是 Jest mock 架构的理论上限。

**当前整体前端测试状态:**
- 877 个测试通过
- 92.67% 语句覆盖率
- TaskWizard 是唯一低于 85% 的主要组件

### 方案 3：Integration Test

使用 `@testing-library/react` 的 `renderHook` + 手动状态管理测试，但收益有限。

---

## 测试套件结构

```
src/frontend/src/components/tasks/__test__/
├── TaskWizard.test.tsx     # 32 tests, 65.87% coverage
└── (其他)

tests/e2e/web/
├── test_task_wizard_playwright.py  # 9 tests, 基础 UI 验证
├── test_task_creation.py           # 任务创建 E2E
└── test_task_detail.py             # 任务详情 E2E
```

---

## 结论

TaskWizard 的多步表单 + Radix UI Portal 组合导致 Jest 单元测试无法达到 85%+ 覆盖率。

**建议:**
1. 重构组件，提取纯函数进行单元测试
2. 依赖 Playwright E2E 测试覆盖完整用户流程
3. 接受 TaskWizard 单元测试上限约 65-70%

**最终决策:** 保持当前状态，TaskWizard 以 E2E 测试为主，单元测试覆盖基础渲染和交互。
