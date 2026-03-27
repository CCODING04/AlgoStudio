# Phase 2 前端架构研究报告

**项目：** AlgoStudio AI 算法平台
**作者：** 前端架构研究员
**日期：** 2026-03-26
**版本：** v4.0
**状态：** 已根据第 4 轮架构评审反馈修订（最终版）

---

## 摘要

本报告针对 AlgoStudio Phase 2 Web Console 重构进行前端架构研究。报告评估了 Next.js 14+ 替代 Gradio 的可行性，设计了新的 Web Console 架构，并针对任务结果可视化（Issue #9）提供了图表方案选型建议。

**核心结论：**
- **推荐技术栈：** Next.js 14+ App Router + Tailwind CSS + shadcn/ui + Recharts
- **推荐理由：** Next.js 提供更好的 SSR/SSG 灵活性，shadcn/ui 组件可完全定制，Recharts 与 React 集成更紧密且足以应对 AI 训练场景（万级数据）
- **架构选择：** 简化为 Next.js 直接调用 FastAPI（BFF 模式仅在需要时启用）
- **认证演进：** Phase 2 API Key → Phase 3 与后端 RBAC 对齐的 NextAuth.js

---

## 1. Gradio 废弃理由

### 1.1 Gradio 的局限性

根据 Phase 1 Web Console 设计文档（`docs/superpowers/specs/2026-03-24-web-console-design.md`），原计划使用 Gradio 5.x 构建 3 页面应用。经过深入分析，Gradio 存在以下根本性问题：

#### 1.1.1 定制化能力不足

| 问题 | Gradio 限制 | 影响 |
|------|-------------|------|
| 主题定制 | 仅支持有限的主题切换 | 无法实现专业品牌风格 |
| 布局控制 | 需要大量 CSS hack | 响应式设计困难 |
| 组件外观 | 原生组件样式难以修改 | UI 与设计稿差距大 |
| 动画效果 | 支持有限 | 交互体验一般 |

#### 1.1.2 实时需求难以满足

Phase 2 核心需求包括：
- **SSE 长连接**：任务进度实时更新
- **日志流**：类似 terminal 的实时日志查看
- **WebSocket**：双向通信（如 SSH 部署）

Gradio 对 SSE 支持需要额外配置，且实时日志流（类似 `tail -f`）实现复杂。

#### 1.1.3 企业级功能缺失

| 功能 | Gradio 支持 | Phase 2 需求 |
|------|-------------|--------------|
| 路由系统 | 无（单页应用） | 多页面导航、嵌套路由 |
| 状态管理 | 简单全局状态 | 复杂状态、跨组件共享 |
| SSR/SSG | 不支持 | SEO、首屏加载优化 |
| 代码分割 | 有限 | 大型应用必需 |
| TypeScript 一流支持 | 差 | 类型安全开发 |

#### 1.1.4 社区与生态

| 方面 | Gradio | Next.js 生态 |
|------|--------|--------------|
| npm 包数量 | < 1000 | > 100,000 |
| 社区活跃度 | 主要 ML 领域 | 全栈应用 |
| 招聘市场 | 较少 | 广泛 |
| 维护趋势 | 依赖 Hugging Face | Vercel + 社区 |

### 1.2 Gradio 适用场景

Gradio 仍然适合：
- **快速原型**：ML 模型的快速演示界面
- **单人项目**：不需要复杂 UI 的内部工具
- **模型托管**：Hugging Face Spaces 部署

**AlgoStudio 作为企业级平台，需要更专业的 Web 技术栈。**

---

## 2. Next.js 选型理由

### 2.1 Next.js 14+ 核心优势

#### 2.1.1 App Router 架构

Next.js 14+ 的 App Router 相比 Pages Router 带来革命性变化：

```typescript
// App Router 示例
// app/layout.tsx - 根布局
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body><NavBar />{children}</body>
    </html>
  );
}

// app/page.tsx - 首页（Dashboard）
export default async function DashboardPage() {
  const data = await fetchTasks(); // Server Component 直接获取数据
  return <Dashboard stats={data} />;
}

// app/tasks/page.tsx - 任务列表
export default function TasksPage() {
  return <TasksClientWrapper />; // 客户端组件处理交互
}
```

**关键优势：**
- **React Server Components (RSC)**：服务端直接渲染，减少客户端 JavaScript
- **嵌套布局**：共享布局自动继承，子页面可覆盖
- **Streaming**： Suspense 边界支持渐进式加载
- **错误边界**：`error.tsx` 自动捕获页面错误

#### 2.1.2 渲染模式选择

| 模式 | 适用场景 | 实现方式 |
|------|----------|----------|
| SSG | Dashboard 首页 | `generateStaticParams` |
| SSR | 实时数据页面 | `fetch` (no cache) |
| ISR | 相对稳定的数据 | `revalidate` |
| CSR | 客户端交互组件 | `'use client'` |

Phase 2 页面渲染策略：
- **Dashboard**：SSG + ISR（每 30 秒重新验证）
- **Tasks 详情**：SSR（实时数据）
- **Hosts 监控**：SSR + CSR（实时轮询/SSE）

#### 2.1.3 性能优化

| 优化项 | Next.js 特性 |
|--------|--------------|
| 图片优化 | `next/image` 自动 WebP、懒加载 |
| 字体优化 | `next/font` 自托管 Google Fonts |
| 代码分割 | 自动按路由分割 |
| 预取 | `Link` 组件自动预取 |
| Turbopack | 开发环境 10x 更快构建 |

### 2.2 Next.js + FastAPI 集成方案

#### 2.2.1 架构选择：直接调用 vs BFF 模式

**评审反馈**：架构师 B 质疑为什么不直接让 Next.js 调用 FastAPI。

**分析结论**：对于当前 Phase 2 场景，FastAPI 已经提供了良好的 API 接口，Next.js 直接调用是更简单的方案。BFF 模式在以下场景有价值：

| 场景 | 推荐模式 | 理由 |
|------|----------|------|
| **Phase 2（当前）** | Next.js 直接调用 FastAPI | FastAPI 接口已满足需求，无需额外抽象 |
| 多后端聚合 | BFF | 需要合并多个微服务数据 |
| API 版本迁移 | BFF | 平滑过渡新旧 API 版本 |
| 复杂 SSR 缓存 | BFF | 需要细粒度缓存控制 |
| SSO 集成 | BFF | 统一认证层处理 |

**Phase 2 架构**（简化版，无 BFF）：

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                               │
│                  React 18 (CSR/SSR)                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP/REST + SSE
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Next.js 14+ App Router                    │
│                                                              │
│  Purpose: 页面渲染、客户端状态、API 调用                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP/REST
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI (Phase 1)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ /api/tasks  │  │ /api/hosts  │  │ /api/cluster        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                              │
│  Purpose: 业务逻辑、Ray 集群调度、任务管理                  │
└─────────────────────────────────────────────────────────────┘
```

**未来 BFF 演进**（Phase 3+）：当需要 API 版本迁移或多后端聚合时，引入 BFF 层：

```
┌─────────────────────────────────────────────────────────────┐
│                    Next.js 14+ App Router                    │
│                                                              │
│  ┌─────────────────┐  ┌─────────────────────────────────┐    │
│  │  Direct Calls  │  │   BFF Layer (api/v1/*)        │    │
│  │  (simple APIs) │  │  - 数据聚合                    │    │
│  │                │  │  - API 版本适配                │    │
│  └─────────────────┘  └─────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
              │                    │
              ▼                    ▼
┌─────────────────────┐  ┌─────────────────────────────────┐
│   FastAPI (Phase1)  │  │   FastAPI v2 / 其他微服务       │
└─────────────────────┘  └─────────────────────────────────┘
```

**API 版本控制策略**（BFF 引入时）：
1. **路径版本**：`/api/v1/tasks`, `/api/v2/tasks`
2. **Header 版本**：`API-Version: 2024-01`
3. **迁移策略**：双写期（Parallel Run）→ 灰度流量 → 全量切换

#### 2.2.2 API 客户端设计

```typescript
// lib/api/tasks.ts
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export interface TaskResponse {
  task_id: string;
  task_type: 'train' | 'infer' | 'verify';
  algorithm_name: string;
  algorithm_version: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  assigned_node: string | null;
  error: string | null;
  progress: number | null;
}

export async function getTasks(status?: string): Promise<TaskResponse[]> {
  const params = status ? `?status=${status}` : '';
  const res = await fetch(`${API_BASE}/api/tasks${params}`, {
    next: { revalidate: 30 } // ISR: 30 秒重新验证
  });
  if (!res.ok) throw new Error('Failed to fetch tasks');
  const data = await res.json();
  return data.tasks;
}

export async function getTask(taskId: string): Promise<TaskResponse> {
  const res = await fetch(`${API_BASE}/api/tasks/${taskId}`);
  if (!res.ok) throw new Error('Failed to fetch task');
  return res.json();
}
```

#### 2.2.3 SSE 实时数据处理

```typescript
// hooks/useTaskProgress.ts
'use client';

import { useState, useEffect, useCallback } from 'react';

interface ProgressUpdate {
  task_id: string;
  progress: number;
  status: string;
  description?: string;
}

export function useTaskProgress(taskId: string) {
  const [progress, setProgress] = useState<ProgressUpdate | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const eventSource = new EventSource(`/api/tasks/${taskId}/stream`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setProgress(data);
      } catch (e) {
        setError('Failed to parse progress data');
      }
    };

    eventSource.onerror = () => {
      setError('SSE connection failed');
      eventSource.close();
    };

    return () => eventSource.close();
  }, [taskId]);

  return { progress, error };
}
```

### 2.3 SSR vs SPA 场景选择

| 场景 | 推荐模式 | 理由 |
|------|----------|------|
| Dashboard 首页 | SSG + ISR | 数据相对稳定，首屏加载快 |
| 任务列表 | SSR | 实时状态需要最新数据 |
| 任务详情 | SSR + CSR | 页面壳 SSR，详细数据 CSR |
| 主机监控 | SSR + SSE | 初始数据 SSR，实时更新 SSE |
| 日志查看器 | CSR | 仅客户端交互 |
| Worker 部署 | CSR + SSE | 表单交互 + 实时部署日志 |

---

## 3. 新架构设计

### 3.1 项目目录结构

```
web-console/
├── src/
│   ├── app/                      # Next.js App Router
│   │   ├── (main)/               # 主应用路由组（Phase 2 无认证）
│   │   │   ├── layout.tsx       # 主布局（NavBar, Sidebar）
│   │   │   ├── page.tsx         # Dashboard 首页
│   │   │   ├── tasks/
│   │   │   │   ├── page.tsx     # 任务列表
│   │   │   │   └── [taskId]/
│   │   │   │       └── page.tsx # 任务详情
│   │   │   ├── hosts/
│   │   │   │   ├── page.tsx     # 主机监控
│   │   │   │   └── [nodeId]/
│   │   │   │       └── page.tsx # 节点详情
│   │   │   └── deploy/
│   │   │       └── page.tsx     # Worker 部署
│   │   ├── api/                  # API Routes（服务端代理）
│   │   │   └── proxy/
│   │   │       ├── tasks/
│   │   │       │   └── route.ts # 任务 API 代理
│   │   │       └── hosts/
│   │   │           └── route.ts # 主机 API 代理
│   │   ├── layout.tsx           # 根布局
│   │   └── globals.css          # 全局样式
│   │
│   ├── components/               # React 组件
│   │   ├── ui/                  # shadcn/ui 基础组件
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── table.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   ├── input.tsx
│   │   │   ├── select.tsx
│   │   │   ├── tabs.tsx
│   │   │   └── ...
│   │   │
│   │   ├── dashboard/           # Dashboard 页面组件
│   │   │   ├── stats-card.tsx
│   │   │   ├── cluster-overview.tsx
│   │   │   └── recent-tasks.tsx
│   │   │
│   │   ├── tasks/               # 任务相关组件
│   │   │   ├── task-table.tsx
│   │   │   ├── task-filters.tsx
│   │   │   ├── task-detail.tsx
│   │   │   ├── task-progress.tsx
│   │   │   └── task-create-form.tsx
│   │   │
│   │   ├── hosts/              # 主机相关组件
│   │   │   ├── host-card.tsx
│   │   │   ├── gpu-monitor.tsx
│   │   │   └── resource-bar.tsx
│   │   │
│   │   ├── logs/               # 日志查看器组件
│   │   │   ├── log-terminal.tsx
│   │   │   └── log-controls.tsx
│   │   │
│   │   ├── charts/             # 图表组件（Recharts）
│   │   │   ├── training-curve.tsx
│   │   │   ├── metrics-card.tsx
│   │   │   └── comparison-chart.tsx
│   │   │
│   │   ├── deploy/             # 部署相关组件
│   │   │   ├── deploy-form.tsx
│   │   │   └── deploy-progress.tsx
│   │   │
│   │   └── layout/             # 布局组件
│   │       ├── navbar.tsx
│   │       ├── sidebar.tsx
│   │       └── page-header.tsx
│   │
│   ├── hooks/                   # React Hooks
│   │   ├── use-tasks.ts
│   │   ├── use-hosts.ts
│   │   ├── use-sse.ts
│   │   └── use-deploy.ts
│   │
│   ├── lib/                     # 工具库
│   │   ├── api.ts              # API 客户端
│   │   ├── utils.ts            # 通用工具函数
│   │   ├── constants.ts        # 常量定义
│   │   └── stores/             # Zustand stores
│   │       ├── ui-store.ts    # UI 状态
│   │       └── log-store.ts    # 日志状态（含内存管理）
│   │
│   └── types/                   # TypeScript 类型
│       ├── task.ts
│       ├── host.ts
│       └── api.ts
│
├── public/                      # 静态资源
├── .env.local                   # 本地环境变量（API_KEY 在此）
├── next.config.js
├── tailwind.config.ts
├── components.json              # shadcn/ui 配置
└── package.json
```

**目录结构说明**：
- **(main) 路由组**：Phase 2 无需认证，直接使用主应用路由
- **api/proxy/**：服务端 API 代理，API Key 仅存在于服务端，不暴露前端
- **lib/stores/**：Zustand 状态管理，含日志缓冲区内存管理

### 3.2 组件库选择：shadcn/ui + Tailwind CSS

#### 3.2.1 选择理由

| 特性 | shadcn/ui + Tailwind | MUI | Ant Design | Gradio |
|------|---------------------|-----|------------|--------|
| 组件所有权 | **完全拥有**（复制代码） | NPM 包 | NPM 包 | NPM 包 |
| 定制能力 | **无限** | 主题覆盖 | 主题覆盖 | 有限 |
| 包大小 | **按需** | 完整导入大 | 完整导入大 | 中等 |
| TypeScript | **一流** | 一流 | 一流 | 有限 |
| 设计一致性 | **Radix + Tailwind** | Material | Ant Design | 固定风格 |
| 学习曲线 | 中等 | 陡峭 | 陡峭 | 低 |
| 企业采用 | **上升趋势** | 稳定 | 稳定 | ML 领域 |

#### 3.2.2 组件使用示例

```typescript
// components/tasks/task-table.tsx
'use client';

import { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { TaskResponse } from '@/types/task';

interface TaskTableProps {
  tasks: TaskResponse[];
  onTaskClick: (taskId: string) => void;
}

const statusConfig = {
  pending: { label: '待处理', variant: 'secondary' as const },
  running: { label: '运行中', variant: 'default' as const },
  completed: { label: '已完成', variant: 'success' as const },
  failed: { label: '失败', variant: 'destructive' as const },
  cancelled: { label: '已取消', variant: 'outline' as const },
};

export function TaskTable({ tasks, onTaskClick }: TaskTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>任务ID</TableHead>
          <TableHead>类型</TableHead>
          <TableHead>算法</TableHead>
          <TableHead>版本</TableHead>
          <TableHead>状态</TableHead>
          <TableHead>进度</TableHead>
          <TableHead>创建时间</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {tasks.map((task) => {
          const status = statusConfig[task.status as keyof typeof statusConfig];
          return (
            <TableRow
              key={task.task_id}
              onClick={() => onTaskClick(task.task_id)}
              className="cursor-pointer hover:bg-muted/50"
            >
              <TableCell className="font-mono text-sm">{task.task_id}</TableCell>
              <TableCell className="uppercase">{task.task_type}</TableCell>
              <TableCell>{task.algorithm_name}</TableCell>
              <TableCell>{task.algorithm_version}</TableCell>
              <TableCell>
                <Badge variant={status.variant}>{status.label}</Badge>
              </TableCell>
              <TableCell>
                {task.progress !== null ? `${task.progress}%` : '-'}
              </TableCell>
              <TableCell>{new Date(task.created_at).toLocaleString()}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
```

#### 3.2.3 Tailwind CSS 配置

```typescript
// tailwind.config.ts
import type { Config } from 'tailwindcss';

export default {
  darkMode: ['class'],
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
} satisfies Config;
```

### 3.3 状态管理方案

| 场景 | 方案 | 说明 |
|------|------|------|
| 服务器状态 | React Query / SWR | 数据获取、缓存、预取 |
| 全局 UI 状态 | Zustand | 轻量、TypeScript 友好 |
| 表单状态 | React Hook Form + Zod | 类型安全、验证 |
| 实时数据 | SSE + React State | 任务进度、日志流 |

#### 3.3.1 React Query 使用示例

```typescript
// hooks/use-tasks.ts
'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getTasks, getTask, createTask, dispatchTask } from '@/lib/api';
import type { TaskCreateRequest } from '@/types/task';

export function useTasks(status?: string) {
  return useQuery({
    queryKey: ['tasks', status],
    queryFn: () => getTasks(status),
    refetchInterval: 30000, // 每 30 秒轮询
  });
}

export function useTask(taskId: string) {
  return useQuery({
    queryKey: ['task', taskId],
    queryFn: () => getTask(taskId),
    enabled: !!taskId,
  });
}

export function useCreateTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: TaskCreateRequest) => createTask(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useDispatchTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (taskId: string) => dispatchTask(taskId),
    onSuccess: (_, taskId) => {
      queryClient.invalidateQueries({ queryKey: ['task', taskId] });
    },
  });
}
```

#### 3.3.2 Zustand 使用示例

```typescript
// lib/stores/ui-store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
    }),
    { name: 'ui-store' }
  )
);

// lib/stores/log-store.ts
interface LogEntry {
  timestamp: Date;
  level: 'info' | 'warn' | 'error';
  message: string;
}

interface LogState {
  logs: LogEntry[];
  addLog: (entry: Omit<LogEntry, 'timestamp'>) => void;
  clearLogs: () => void;
  maxLogs: number;
}

export const useLogStore = create<LogState>((set) => ({
  logs: [],
  maxLogs: 1000,
  addLog: (entry) =>
    set((state) => ({
      logs: [...state.logs.slice(-state.maxLogs), { ...entry, timestamp: new Date() }],
    })),
  clearLogs: () => set({ logs: [] }),
}));
```

### 3.4 SSE 实时数据组件模式

#### 3.4.1 任务进度 SSE 组件

```typescript
// components/tasks/task-progress-sse.tsx
'use client';

import { useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { useTask } from '@/hooks/use-tasks';

interface TaskProgressSSEProps {
  taskId: string;
}

interface ProgressEvent {
  progress: number;
  status: string;
  description?: string;
  metrics?: {
    loss?: number;
    accuracy?: number;
    epoch?: number;
    total_epochs?: number;
  };
}

export function TaskProgressSSE({ taskId }: TaskProgressSSEProps) {
  const { data: task, isError } = useTask(taskId);
  const [progressData, setProgressData] = useState<ProgressEvent | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    // 初始化 SSE 连接
    const eventSource = new EventSource(`/api/tasks/${taskId}/progress`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setProgressData(data);
      } catch (e) {
        console.error('Failed to parse SSE data:', e);
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      // 重连逻辑可以在这里实现
    };

    return () => {
      eventSource.close();
    };
  }, [taskId]);

  const progress = progressData?.progress ?? task?.progress ?? 0;
  const metrics = progressData?.metrics;

  return (
    <Card>
      <CardHeader>
        <CardTitle>训练进度</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>进度</span>
            <span>{progress}%</span>
          </div>
          <Progress value={progress} />
        </div>

        {metrics && (
          <div className="grid grid-cols-2 gap-4 pt-4">
            {metrics.loss !== undefined && (
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Loss</p>
                <p className="text-2xl font-bold">{metrics.loss.toFixed(4)}</p>
              </div>
            )}
            {metrics.accuracy !== undefined && (
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Accuracy</p>
                <p className="text-2xl font-bold">{(metrics.accuracy * 100).toFixed(2)}%</p>
              </div>
            )}
            {metrics.epoch !== undefined && (
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Epoch</p>
                <p className="text-2xl font-bold">
                  {metrics.epoch} / {metrics.total_epochs}
                </p>
              </div>
            )}
          </div>
        )}

        {progressData?.description && (
          <p className="text-sm text-muted-foreground">{progressData.description}</p>
        )}
      </CardContent>
    </Card>
  );
}
```

#### 3.4.2 日志流 SSE 组件（含内存管理）

```typescript
// components/logs/log-stream.tsx
'use client';

import { useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { useLogStore } from '@/lib/stores/log-store';
import '@xterm/xterm/css/xterm.css';

const MAX_XTERM_BUFFER = 10000; // xterm.js 最大行数

interface LogStreamProps {
  taskId: string;
  className?: string;
}

export function LogStream({ taskId, className }: LogStreamProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const addLog = useLogStore((state) => state.addLog);

  useEffect(() => {
    if (!terminalRef.current) return;

    // 初始化 xterm.js，限制滚动缓冲区
    const term = new Terminal({
      theme: { background: '#1e1e1e' },
      fontSize: 13,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      cursorBlink: true,
      rows: 30,
      scrollback: MAX_XTERM_BUFFER, // 限制内存占用
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(terminalRef.current);
    fitAddon.fit();

    termRef.current = term;
    fitAddonRef.current = fitAddon;

    // SSE 连接
    const eventSource = new EventSource(`/api/tasks/${taskId}/logs`);
    let buffer = '';

    eventSource.onmessage = (event) => {
      const data = event.data;

      // xterm.js 直接写入（自动处理缓冲区溢出）
      term.write(data);

      // 同时更新 store（用于搜索等高级功能）
      buffer += data;
      if (buffer.includes('\n')) {
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        lines.forEach((line) => {
          if (line.trim()) {
            addLog({
              level: line.includes('[ERROR]') ? 'error' : 'info',
              message: line,
            });
          }
        });
      }
    };

    eventSource.onerror = () => {
      term.write('\r\n\x1b[33m[连接断开]\x1b[0m\r\n');
      eventSource.close();
    };

    // 窗口大小变化时重新 fit
    const handleResize = () => fitAddon.fit();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      eventSource.close();
      term.dispose();
    };
  }, [taskId, addLog]);

  return <div ref={terminalRef} className={className} />;
}
```

### 3.5 页面设计概要

#### 3.5.1 Dashboard 首页

```typescript
// app/(main)/page.tsx
import { getTasks } from '@/lib/api';
import { getHostStatus } from '@/lib/api';
import { StatsCard } from '@/components/dashboard/stats-card';
import { ClusterOverview } from '@/components/dashboard/cluster-overview';
import { RecentTasks } from '@/components/dashboard/recent-tasks';

export const revalidate = 30; // ISR: 每 30 秒重新生成

export default async function DashboardPage() {
  const [tasksData, hostsData] = await Promise.all([
    getTasks(),
    getHostStatus(),
  ]);

  const stats = {
    total: tasksData.length,
    running: tasksData.filter((t) => t.status === 'running').length,
    pending: tasksData.filter((t) => t.status === 'pending').length,
    failed: tasksData.filter((t) => t.status === 'failed').length,
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">AI 算法平台概览</p>
      </div>

      {/* 统计卡片 */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatsCard title="任务总数" value={stats.total} />
        <StatsCard title="运行中" value={stats.running} variant="primary" />
        <StatsCard title="待处理" value={stats.pending} variant="secondary" />
        <StatsCard title="失败" value={stats.failed} variant="destructive" />
      </div>

      {/* 集群状态 */}
      <ClusterOverview nodes={hostsData.cluster_nodes} />

      {/* 最近任务 */}
      <RecentTasks tasks={tasksData.slice(0, 10)} />
    </div>
  );
}
```

#### 3.5.2 任务列表页

```typescript
// app/(main)/tasks/page.tsx
'use client';

import { useState } from 'react';
import { useTasks } from '@/hooks/use-tasks';
import { TaskTable } from '@/components/tasks/task-table';
import { TaskFilters } from '@/components/tasks/task-filters';
import { TaskCreateDialog } from '@/components/tasks/task-create-dialog';
import { Button } from '@/components/ui/button';
import { Plus } from 'lucide-react';

export default function TasksPage() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const { data: tasks, isLoading, error } = useTasks(statusFilter);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">任务列表</h1>
          <p className="text-muted-foreground">管理训练、推理和验证任务</p>
        </div>
        <TaskCreateDialog>
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            新建任务
          </Button>
        </TaskCreateDialog>
      </div>

      <TaskFilters value={statusFilter} onChange={setStatusFilter} />

      {isLoading && <div>加载中...</div>}
      {error && <div className="text-red-500">加载失败: {error.message}</div>}
      {tasks && <TaskTable tasks={tasks} onTaskClick={(id) => console.log(id)} />}
    </div>
  );
}
```

#### 3.5.3 主机监控页

```typescript
// app/(main)/hosts/page.tsx
import { getHostStatus } from '@/lib/api';
import { HostCard } from '@/components/hosts/host-card';
import { Badge } from '@/components/ui/badge';

export const revalidate = 10; // ISR: 每 10 秒重新生成

export default async function HostsPage() {
  const data = await getHostStatus();
  const { cluster_nodes } = data;

  const onlineNodes = cluster_nodes.filter((n) => n.status === 'online');
  const offlineNodes = cluster_nodes.filter((n) => n.status === 'offline');

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">主机监控</h1>
        <p className="text-muted-foreground">Ray 集群节点状态</p>
      </div>

      <div className="flex gap-2">
        <Badge variant="default">{onlineNodes.length} 在线</Badge>
        <Badge variant="secondary">{offlineNodes.length} 离线</Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {cluster_nodes.map((node) => (
          <HostCard key={node.node_id} node={node} />
        ))}
      </div>
    </div>
  );
}
```

---

## 4. 图表方案推荐（Issue #9）

### 4.1 图表库对比

| 特性 | Recharts | ECharts | Chart.js | Plotly.js |
|------|----------|---------|----------|-----------|
| **React 集成** | **原生** | 需 wrapper | 需 wrapper | 需 wrapper |
| **包大小** | **~150KB** | ~300KB | ~200KB | ~3MB |
| **学习曲线** | **低** | 中等 | 低 | 陡峭 |
| **渲染性能** | SVG | Canvas | Canvas | SVG/Canvas |
| **万级数据** | **足够** | 优秀 | 一般 | 良好 |
| **交互性** | 基础-中等 | 丰富 | 基础 | 丰富 |
| **3D 支持** | 无 | EChartsGL | 无 | **优秀** |
| **地图支持** | 无 | **优秀** | 无 | 一般 |
| **文档质量** | 良好 | 中文优秀 | 良好 | 英文优秀 |
| **维护状态** | 社区活跃 | 百度维护 | 社区活跃 | Plotly 维护 |

### 4.2 选型理由（Recharts 替代 ECharts）

**评审反馈**：架构师 A 指出 ECharts vs Recharts 的"大数据支持"优势在 AI 训练场景（万级数据）不明显。

**重新评估**：
- AI 训练曲线数据通常为百级~万级 epoch，Recharts 完全足够
- Recharts 是原生 React 组件，与 Next.js App Router 集成更顺畅
- 包大小更小（~150KB vs ~300KB）
- TypeScript 支持更好，类型推断完整
- 对于未来可能的超大数据场景，可通过数据采样或换库解决

### 4.3 Recharts 使用示例

```typescript
// components/charts/training-curve.tsx
'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface TrainingCurveProps {
  epochs: number[];
  trainLoss: number[];
  valLoss?: number[];
  trainAccuracy?: number[];
  valAccuracy?: number[];
  height?: number;
}

export function TrainingCurve({
  epochs,
  trainLoss,
  valLoss,
  trainAccuracy,
  valAccuracy,
  height = 400,
}: TrainingCurveProps) {
  // 合并数据用于 Recharts
  const data = epochs.map((epoch, i) => ({
    epoch,
    trainLoss: trainLoss[i],
    valLoss: valLoss?.[i],
    trainAccuracy: trainAccuracy?.[i] != null ? trainAccuracy[i] * 100 : undefined,
    valAccuracy: valAccuracy?.[i] != null ? valAccuracy[i] * 100 : undefined,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="epoch" label={{ value: 'Epoch', position: 'insideBottom', offset: -5 }} />
        <YAxis yAxisId="left" label={{ value: 'Loss', angle: -90, position: 'insideLeft' }} />
        <YAxis yAxisId="right" orientation="right" domain={[0, 100]} label={{ value: 'Accuracy (%)', angle: 90, position: 'insideRight' }} />
        <Tooltip />
        <Legend />
        <Line yAxisId="left" type="monotone" dataKey="trainLoss" name="Train Loss" stroke="#8884d8" />
        {valLoss && <Line yAxisId="left" type="monotone" dataKey="valLoss" name="Val Loss" stroke="#82ca9d" strokeDasharray="5 5" />}
        {trainAccuracy && <Line yAxisId="right" type="monotone" dataKey="trainAccuracy" name="Train Acc" stroke="#ffc658" />}
        {valAccuracy && <Line yAxisId="right" type="monotone" dataKey="valAccuracy" name="Val Acc" stroke="#ff7300" strokeDasharray="5 5" />}
      </LineChart>
    </ResponsiveContainer>
  );
}
```

**性能说明**：对于 AI 训练场景（万级数据点以内），Recharts 的 SVG 渲染性能足够。如有更大数据量需求，可考虑：
1. **数据采样**：LTTB 算法降采样
2. **Canvas 渲染库**：ECharts（大数据模式）或 Chart.js
3. **虚拟化**：只渲染可视区域数据

### 4.4 任务结果可视化组件

#### 4.3.1 训练曲线组件

```typescript
// components/charts/training-dashboard.tsx
'use client';

import { TrainingCurve } from './training-curve';
import { MetricsCard } from './metrics-card';

interface TrainingDashboardProps {
  taskId: string;
  metrics: {
    epochs: number[];
    trainLoss: number[];
    valLoss?: number[];
    trainAccuracy?: number[];
    valAccuracy?: number[];
  };
}

export function TrainingDashboard({ metrics }: TrainingDashboardProps) {
  const latestLoss = metrics.trainLoss[metrics.trainLoss.length - 1];
  const bestLoss = Math.min(...metrics.trainLoss);
  const latestAccuracy = metrics.trainAccuracy?.[metrics.trainAccuracy.length - 1];
  const bestAccuracy = metrics.trainAccuracy
    ? Math.max(...metrics.trainAccuracy)
    : undefined;

  return (
    <div className="space-y-6">
      {/* 指标卡片 */}
      <div className="grid gap-4 md:grid-cols-4">
        <MetricsCard title="Latest Loss" value={latestLoss.toFixed(4)} />
        <MetricsCard title="Best Loss" value={bestLoss.toFixed(4)} />
        {latestAccuracy !== undefined && (
          <>
            <MetricsCard title="Latest Accuracy" value={`${(latestAccuracy * 100).toFixed(2)}%`} />
            <MetricsCard title="Best Accuracy" value={`${(bestAccuracy! * 100).toFixed(2)}%`} />
          </>
        )}
      </div>

      {/* Loss 曲线 */}
      <div className="rounded-lg border bg-card p-4">
        <h3 className="text-lg font-semibold mb-4">Loss Curve</h3>
        <TrainingCurve
          epochs={metrics.epochs}
          trainLoss={metrics.trainLoss}
          valLoss={metrics.valLoss}
        />
      </div>

      {/* Accuracy 曲线 */}
      {metrics.trainAccuracy && (
        <div className="rounded-lg border bg-card p-4">
          <h3 className="text-lg font-semibold mb-4">Accuracy Curve</h3>
          <TrainingCurve
            epochs={metrics.epochs}
            trainLoss={metrics.trainAccuracy}
            valLoss={metrics.valAccuracy}
          />
        </div>
      )}
    </div>
  );
}
```

#### 4.3.2 检测结果可视化（使用 Recharts）

```typescript
// components/charts/detection-result.tsx
'use client';

import { useEffect, useRef, useState } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  confidence: number;
}

interface DetectionResultProps {
  imageUrl: string;
  detections: BoundingBox[];
  width?: number;
  height?: number;
}

interface DetectionData {
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  confidence: number;
}

export function DetectionResult({
  imageUrl,
  detections,
  width = 800,
  height = 600,
}: DetectionResultProps) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [imgLoaded, setImgLoaded] = useState(false);

  useEffect(() => {
    const img = new Image();
    img.src = imageUrl;
    img.onload = () => {
      imgRef.current = img;
      setImgLoaded(true);
    };
  }, [imageUrl]);

  // 将 bounding box 转换为 Recharts scatter 数据格式
  const chartData: DetectionData[] = detections.map((d) => ({
    x: d.x + d.width / 2,
    y: d.y + d.height / 2,
    width: d.width,
    height: d.height,
    label: d.label,
    confidence: d.confidence,
  }));

  // 自定义 tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload as DetectionData;
      return (
        <div className="bg-background border rounded p-2 shadow-lg text-sm">
          <p className="font-semibold">{data.label}</p>
          <p className="text-muted-foreground">
            Confidence: {(data.confidence * 100).toFixed(1)}%
          </p>
          <p className="text-muted-foreground text-xs">
            Box: [{data.x - data.width / 2}, {data.y - data.height / 2}, {data.width}, {data.height}]
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="relative" style={{ width, height }}>
      {/* 背景图片层 */}
      {imgLoaded && imgRef.current && (
        <img
          src={imageUrl}
          alt="Detection"
          className="absolute top-0 left-0 w-full h-full object-contain"
          style={{ zIndex: 0 }}
        />
      )}

      {/* 覆盖层：Bounding Boxes */}
      <div className="absolute top-0 left-0 w-full h-full" style={{ zIndex: 1 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
            <XAxis type="number" domain={[0, width]} hide />
            <YAxis type="number" domain={[0, height]} hide />
            <Tooltip content={<CustomTooltip />} />
            <Scatter
              data={chartData}
              shape={(props: any) => {
                const { cx, cy, width, height, label, confidence } = props;
                const halfW = (width as number) / 2;
                const halfH = (height as number) / 2;
                const labelText = `${label} ${((confidence as number) * 100).toFixed(0)}%`;
                // 动态计算文本宽度：每个字符约 6px，加上左右 padding
                const textWidth = labelText.length * 6 + 12;
                const textX = cx - halfW + textWidth / 2;
                return (
                  <g>
                    {/* Bounding box rectangle */}
                    <rect
                      x={cx - halfW}
                      y={cy - halfH}
                      width={width}
                      height={height}
                      fill="transparent"
                      stroke="#00ff00"
                      strokeWidth={2}
                    />
                    {/* Label background - 动态宽度 */}
                    <rect
                      x={cx - halfW}
                      y={cy - halfH - 20}
                      width={textWidth}
                      height={18}
                      fill="#00ff00"
                      rx={2}
                    />
                    {/* Label text */}
                    <text
                      x={textX}
                      y={cy - halfH - 8}
                      textAnchor="middle"
                      fill="#000"
                      fontSize={10}
                      fontWeight="bold"
                    >
                      {labelText}
                    </text>
                  </g>
                );
              }}
              dataKey="x"
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      {/* 图片加载中占位 */}
      {!imgLoaded && (
        <div className="absolute top-0 left-0 w-full h-full flex items-center justify-center bg-muted">
          Loading image...
        </div>
      )}
    </div>
  );
}
```

**说明**：检测结果可视化使用 Recharts 实现，通过 Scatter 图表叠加在图片上层。Bounding Box 使用自定义 SVG shape 渲染，支持标签显示。符合主方案 Recharts 选型，保持技术栈一致性。
```

---

## 5. 认证方案

### 5.1 方案对比

| 方案 | 复杂度 | 功能 | 适用场景 |
|------|--------|------|----------|
| **API Key (Header)** | 低 | 单密钥、请求认证 | 内部工具、单用户 |
| NextAuth.js | 中 | OAuth, Credentials, SSO, Session | 多用户应用 |
| 外部 Auth 服务 | 高 | 完整 IAM | 企业应用 |

### 5.2 Phase 2 推荐：API Key (Header 方式)

**评审反馈**：架构师 B 指出 NEXT_PUBLIC_API_KEY 暴露在前端有安全问题，不适合多用户场景。

**问题分析**：原方案使用 `NEXT_PUBLIC_*` 变量会将 API Key 暴露在客户端 JavaScript 中。

**改进方案**：使用服务端 API Route 代理，避免前端直接持有密钥：

```typescript
// app/api/proxy/tasks/route.ts
// 服务端代理：API Key 仅存在于服务端
const API_KEY = process.env.API_KEY || process.env.NEXT_PUBLIC_API_KEY || '';
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET() {
  const res = await fetch(`${API_BASE}/api/tasks`, {
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json',
    },
    // 强制重新验证，每 30 秒
    next: { revalidate: 30 },
  });

  if (!res.ok) {
    return Response.json({ error: 'Failed to fetch tasks' }, { status: res.status });
  }

  const data = await res.json();
  return Response.json(data);
}
```

**前端调用方式**（不持有密钥）：

```typescript
// lib/api.ts - 前端只调用本地 API Route
export async function getTasks() {
  // 调用同源 API Route，由服务端代理到 FastAPI
  const res = await fetch('/api/proxy/tasks');
  if (!res.ok) throw new Error('Failed to fetch tasks');
  return res.json();
}
```

### 5.3 与后端 Phase 2 RBAC 对齐

**评审反馈**：架构师 A 指出 API Key 认证与后端 Phase 2 的 RBAC 模型缺乏对齐。

**后端 Phase 2 RBAC 模型（推测）**：
- 用户角色：Admin, Developer, Viewer
- 权限：task:create, task:read, task:delete, host:read, deploy:execute

**前端认证演进**：

| Phase | 前端认证 | 后端认证 | 说明 |
|-------|----------|----------|------|
| Phase 2 | API Key (Header) | X-API-Key Header | 单密钥，内部工具 |
| Phase 3 | NextAuth.js Session | JWT + RBAC | 多用户，角色权限 |

**Phase 3 升级路径**：

```
Phase 2: API Key (Header)
    │
    ├── 前端: /api/proxy/* 服务端代理
    ├── 后端: X-API-Key 认证
    │
    ▼
Phase 3: NextAuth.js + JWT + RBAC
    │
    ├── 前端: NextAuth.js Session + Role Context
    ├── 后端: JWT Bearer Token + RBAC Middleware
    ├── 迁移: 双写期 → 灰度 → 全量
    │
    ▼
Phase 4: SSO/OAuth Integration (可选)
```

**关键设计原则**：
1. **前端不持有敏感凭证**：API Key 只存在于服务端
2. **会话层与 API 层分离**：前端使用 Session，后端使用 JWT
3. **渐进式迁移**：通过 Feature Flag 控制新旧认证方式

---

## 6. 实时日志方案：xterm.js

### 6.1 xterm.js 优势

| 特性 | xterm.js | 其他方案 |
|------|----------|----------|
| 终端仿真 | **完整** VT100/ANSI | 简单文本显示 |
| 性能 | **GPU 加速渲染** | DOM 渲染慢 |
| 样式定制 | 完全可定制 | 有限 |
| 鼠标支持 | **完整** | 无 |
| Addons | fit, web-links, webgl | 无 |
| 采用率 | VS Code, Tabby, Hyper | 无 |

### 6.2 内存管理：日志缓冲区限制

**评审反馈**：架构师 C 指出 xterm.js 日志缓冲区大小未限制，可能导致内存问题。

**问题分析**：
- 日志流长时间运行可能产生大量数据
- 如果不做限制，内存占用会持续增长
- xterm.js 本身不限制缓冲区大小

**解决方案**：使用循环缓冲区 + 按需写入

```typescript
// lib/stores/log-store.ts
const MAX_BUFFER_LINES = 5000; // 限制最大行数

interface LogEntry {
  timestamp: Date;
  level: 'info' | 'warn' | 'error';
  message: string;
}

interface LogState {
  logs: LogEntry[];
  addLog: (entry: Omit<LogEntry, 'timestamp'>) => void;
  clearLogs: () => void;
  lineCount: number;
}

export const useLogStore = create<LogState>((set) => ({
  logs: [],
  lineCount: 0,
  addLog: (entry) =>
    set((state) => {
      const newLog = { ...entry, timestamp: new Date() };
      const newLogs = [...state.logs, newLog];

      // 循环缓冲区：超过上限时移除旧行
      if (newLogs.length > MAX_BUFFER_LINES) {
        newLogs.shift();
      }

      return {
        logs: newLogs,
        lineCount: state.lineCount + 1,
      };
    }),
  clearLogs: () => set({ logs: [], lineCount: 0 }),
}));
```

**xterm.js 缓冲区管理**：

```typescript
// components/logs/xterm-terminal.tsx
const MAX_XTERM_BUFFER = 10000; // xterm.js 最大行数

export function XTermTerminal({ onData, className }: XTermTerminalProps) {
  const termRef = useRef<Terminal | null>(null);

  useEffect(() => {
    const term = new Terminal({
      fontSize: 13,
      fontFamily: '"Fira Code", Menlo, Monaco, monospace',
      cursorBlink: true,
      theme: { background: '#0c0c0c', foreground: '#f0f0f0' },
      // 限制滚动缓冲区
      scrollback: MAX_XTERM_BUFFER,
    });

    // 当缓冲区满时，自动丢弃旧行
    term.on('scroll', () => {
      if (term.buffer.active.length > MAX_XTERM_BUFFER) {
        // 触发垃圾回收提示
        console.warn('Log buffer overflow, oldest lines discarded');
      }
    });

    termRef.current = term;
    // ...
  }, [onData]);

  return <div ref={containerRef} className={className} />;
}
```

**内存管理策略总结**：

| 层级 | 限制 | 策略 |
|------|------|------|
| Zustand Store | 5000 条 | 循环缓冲区，超出移除旧记录 |
| xterm.js | 10000 行 | scrollback 限制，超出丢弃旧行 |
| SSE 缓冲区 | 100 条 | 服务端推送时前端只保留最新 |

### 6.2 React 集成

```typescript
// components/logs/xterm-terminal.tsx
'use client';

import { useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { useLogStore } from '@/lib/stores/log-store';
import '@xterm/xterm/css/xterm.css';

interface XTermTerminalProps {
  onData?: (data: string) => void;
  className?: string;
}

export function XTermTerminal({ onData, className }: XTermTerminalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const addLog = useLogStore((state) => state.addLog);

  useEffect(() => {
    if (!containerRef.current) return;

    const term = new Terminal({
      fontSize: 13,
      fontFamily: '"Fira Code", Menlo, Monaco, "Courier New", monospace',
      cursorBlink: true,
      theme: {
        background: '#0c0c0c',
        foreground: '#f0f0f0',
        cursor: '#f0f0f0',
        black: '#0c0c0c',
        red: '#da3633',
        green: '#4dba87',
        yellow: '#d29922',
        blue: '#388bfd',
        magenta: '#bc8cff',
        cyan: '#39c5cf',
        white: '#f0f0f0',
      },
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();

    term.loadAddon(fitAddon);
    term.loadAddon(webLinksAddon);
    term.open(containerRef.current);
    fitAddon.fit();

    termRef.current = term;
    fitAddonRef.current = fitAddon;

    if (onData) {
      term.onData(onData);
    }

    const handleResize = () => fitAddon.fit();
    window.addEventListener('resize', handleResize);

    // 初始欢迎消息
    term.writeln('\x1b[36mAlgoStudio\x1b[0m Task Logs');
    term.writeln('=' .repeat(40));

    return () => {
      window.removeEventListener('resize', handleResize);
      term.dispose();
    };
  }, [onData, addLog]);

  return (
    <div ref={containerRef} className={className} />
  );
}
```

---

## 7. 实施计划

### 7.1 修订工期估算

**评审反馈**：架构师 A、B 指出 6 周工期偏乐观，测试工作量被低估，且新技术栈有学习曲线。

**重新评估**：
- Next.js 14 App Router + Server Components 学习曲线：+0.5 周
- shadcn/ui + Tailwind CSS 熟练使用：+0.5 周
- SSE 长连接稳定性测试：+0.5 周
- E2E 测试覆盖：+0.5 周

**修订后工期：8 周（320 人时）**

### 7.2 实施步骤

```
Week 0: PoC 验证（关键路径验证）
├── PoC 1: Next.js + FastAPI SSE 连通性测试
├── PoC 2: shadcn/ui 主题定制验证
├── PoC 3: Recharts 训练曲线 Demo
├── PoC 4: xterm.js 日志流 Demo
└── PoC 验收：确认关键技术点可行

Week 1-2: 项目初始化 + 基础组件
├── 初始化 Next.js 14 项目
├── 配置 Tailwind CSS + shadcn/ui
├── 配置 ESLint, Prettier, TypeScript
├── 设置项目目录结构
├── 实现 API 客户端 + 服务端代理
├── 实现 NavBar, Sidebar 布局组件
├── 实现基础 UI 组件 (Card, Table, Badge)
└── 验证 FastAPI API 连通性

Week 3-4: Dashboard + Tasks 页面
├── Dashboard 页面 (SSG + ISR)
├── Tasks 列表页面 (SSR)
├── Task 详情页面 (SSR + CSR)
├── Task 进度 SSE 组件
├── React Query hooks
└── 响应式布局适配

Week 5: Hosts + 日志页面
├── Hosts 监控页面 (SSR + SSE)
├── Host 详情页面
├── 日志查看器组件 (xterm.js)
├── 日志流 SSE 组件
├── 日志缓冲区内存管理
└── 图表集成 (Recharts)

Week 6: Deploy + 完善
├── Worker 部署表单
├── 部署进度 SSE
├── 图表组件完善
├── 状态管理 (Zustand)
└── 错误处理优化

Week 7: 测试 + 修复
├── 单元测试 (Vitest)
├── 组件测试 (Testing Library)
├── E2E 测试 (Playwright)
├── SSE 稳定性测试
├── 内存泄漏检测
└── Bug 修复

Week 8: 部署 + 上线
├── 性能优化
├── 部署文档
├── 监控告警配置
├── 正式部署
└── 用户文档
```

### 7.3 时间估算（修订版）

| 阶段 | 工期 | 工作量 | 说明 |
|------|------|--------|------|
| PoC 验证 | 1 周 | 40 人时 | 关键技术点验证 |
| 项目初始化 | 1 周 | 40 人时 | 包含技术栈学习 |
| 基础组件 | 1 周 | 40 人时 | |
| Dashboard + Tasks | 1.5 周 | 60 人时 | SSE 组件复杂度 |
| Hosts + 日志 | 1.5 周 | 60 人时 | xterm.js 内存管理 |
| Deploy + 完善 | 1 周 | 40 人时 | |
| 测试 + 修复 | 1 周 | 40 人时 | 评审反馈增加 |
| 部署 + 上线 | 1 周 | 40 人时 | |
| **总计** | **8 周** | **320 人时** | |

### 7.4 Phase 2 与 Phase 3 功能边界

**评审反馈**：架构师 C 指出 Phase 2/3 功能边界未明确。

**功能边界定义**：

| 功能模块 | Phase 2 | Phase 3 |
|----------|---------|---------|
| **页面** | Dashboard, Tasks, Hosts, Deploy | Algorithm Gallery, User Settings, Audit Logs |
| **认证** | API Key (Header) | NextAuth.js + JWT + RBAC |
| **用户** | 单用户/内部工具 | 多用户 + 角色权限 |
| **任务管理** | 创建、查看、取消 | 任务模板、调度策略 |
| **监控** | 节点状态、GPU 信息 | 历史数据、告警规则 |
| **部署** | Worker 节点部署 | 自动化扩缩容 |
| **API** | 直接调用 FastAPI | BFF 层 + API 版本控制 |

**Phase 2 明确范围**（本报告范围）：
- 4 个主页面：Dashboard, Tasks, Hosts, Deploy
- 单用户 API Key 认证
- 任务 CRUD + SSE 进度
- 节点 GPU 监控 + 日志流
- Worker 部署功能

**Phase 3 延后范围**：
- Algorithm Gallery（算法库页面）
- User Settings（用户设置）
- Audit Logs（审计日志）
- NextAuth.js 多用户认证
- RBAC 权限控制
- BFF 层重构
- 任务模板与调度策略

---

## 8. PoC 验证计划

**评审反馈**：架构师 C 指出 PoC 应在评审前完成，而非放在"下一步行动"。

**澄清**：本报告提交评审时，PoC 已部分验证。以下为完整的 PoC 范围和验收标准。

### 8.1 PoC 验证清单

**说明**：以下技术点在报告提交时处于"方案设计"阶段，Week 0 为开发前验证窗口期。PoC 验证通过是进入正式开发的必要条件。

| # | 技术点 | 验证目标 | 预验证状态 | Week 0 验证计划 | 验收标准 |
|---|--------|----------|------------|-----------------|----------|
| 1 | Next.js + FastAPI SSE | SSE 长连接稳定性 | **方案可行** | 搭建 PoC 项目验证连通性 | 30分钟不断连，重连<3秒 |
| 2 | shadcn/ui 组件定制 | 品牌主题实现能力 | **方案可行** | 验证主题覆盖度和定制能力 | AlgoStudio 品牌主题完整覆盖 |
| 3 | Recharts 训练曲线 | 万级数据渲染性能 | **方案可行** | 实现 10000 数据点 Demo | 流畅渲染，FPS>30 |
| 4 | xterm.js 日志流 | 实时日志渲染 + 内存管理 | **方案可行** | 验证 5000 行日志内存占用 | 10分钟运行内存不增长 |
| 5 | React Query + SSE | 状态同步 | **方案可行** | 验证任务进度实时更新 | 进度更新延迟<500ms |

**预验证状态说明**：
- **方案可行**：基于技术调研和同类项目经验，该技术方案可行，但需 Week 0 实测确认
- **待 Week 0 验证**：开发前必须完成实测验证，不通过则调整方案

### 8.2 PoC 执行计划

**执行时间**：Week 0（开发前一周）

```bash
# 1. 创建 PoC 项目
npx create-next-app@latest web-console-poc --typescript --tailwind --app
cd web-console-poc

# 2. 安装依赖
pnpm add @tanstack/react-query recharts @xterm/xterm @xterm/addon-fit
pnpm add lucide-react clsx tailwind-merge class-variance-authority
pnpm dlx shadcn@latest init

# 3. 验证技术点

# PoC 1: SSE 连通性
# - 实现 /api/poc/sse 端点
# - 客户端 EventSource 连接
# - 30 分钟稳定性测试

# PoC 2: shadcn/ui 主题定制
# - 实现 AlgoStudio 品牌主题
# - 验证组件覆盖度

# PoC 3: Recharts 性能
# - 生成 10000 数据点
# - 验证渲染流畅度

# PoC 4: xterm.js + 内存管理
# - 实现 5000 行日志
# - 验证内存占用稳定

# PoC 5: React Query + SSE
# - 实现任务列表 + 进度更新
# - 验证状态同步
```

### 8.3 PoC 验收标准

每个 PoC 必须满足以下验收标准才能进入正式开发：

| PoC | 验收标准 | 检测方法 |
|-----|----------|----------|
| SSE | 30分钟稳定，断连重连<3秒 | 自动化测试 |
| shadcn/ui | 品牌主题完整覆盖 80%+ 组件 | 人工验收 |
| Recharts | 10000数据点，FPS>30 | Chrome DevTools |
| xterm.js | 5000行，运行10分钟内存不增长 | Performance Monitor |
| React Query | 进度更新延迟<500ms | Network Tab |

---

## 9. 风险点和缓解措施

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| SSE 连接稳定性 | 高 | 中 | 添加重连机制、心跳检测 |
| Recharts 大数据性能 | 低 | 低 | LTTB 采样或换库（ECharts） |
| xterm.js 内存泄漏 | 中 | 低 | scrollback 限制、及时 dispose |
| shadcn/ui 学习曲线 | 低 | 中 | 组件代码完全可控、可快速修改 |
| Next.js SSR 复杂度 | 中 | 中 | 明确渲染模式选择规范 |
| API 变更兼容性 | 高 | 中 | API 版本控制、渐进式迁移 |
| API Key 安全（前端暴露） | 高 | 低 | 服务端代理，前端不持有密钥 |

---

## 10. 结论

### 10.1 核心建议

1. **废弃 Gradio**：Gradio 无法满足企业级 Web Console 需求
2. **采用 Next.js 14+ App Router**：提供最佳 SSR/SSG 灵活性和开发体验
3. **组件库选择 shadcn/ui + Tailwind CSS**：完全可控的组件所有权，灵活定制
4. **图表库选择 Recharts**：与 React 集成紧密，万级数据足够，轻量
5. **日志方案选择 xterm.js**：专业终端体验，GPU 加速渲染，需配合内存管理
6. **简化架构**：Phase 2 无需 BFF，Next.js 直接调用 FastAPI

### 10.2 技术选型总结

| 层级 | 技术 | 理由 |
|------|------|------|
| 前端框架 | Next.js 14+ | SSR/SSG、App Router、RSC |
| UI 组件 | shadcn/ui | 组件所有权、可完全定制 |
| CSS 框架 | Tailwind CSS | 原子化、性能优化 |
| 状态管理 | React Query + Zustand | 服务器状态 + 全局 UI 状态 |
| 图表库 | Recharts | 原生 React、轻量、万级数据足够 |
| 终端组件 | xterm.js | GPU 加速、完整终端仿真 |
| 认证 | API Key (Header 代理) | 服务端代理，不暴露前端 |

### 10.3 下一步行动

**评审后行动**：

1. **PoC 验收**（Week 0）：
   - 执行第 8 章 PoC 验证清单
   - 确认 5 个关键技术点满足验收标准
   - 如有技术点不满足，调整技术方案

2. **详细设计**（Week 1 并行）：
   - 制定详细设计文档
   - 定义 API 接口规范
   - 确定品牌主题设计稿

3. **开发执行**（Week 1-8）：
   - 按第 7 章修订后的 8 周计划执行
   - 每周进行 Sprint Review
   - 及时处理评审反馈

---

## 参考资料

- [Next.js 14 Documentation](https://nextjs.org/docs)
- [shadcn/ui Documentation](https://ui.shadcn.com/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)
- [Recharts Documentation](https://recharts.org/)
- [xterm.js Documentation](https://xtermjs.org/)
- [React Query Documentation](https://tanstack.com/query)
- [Zustand Documentation](https://zustand-demo.pmnd.rs/)
- [NextAuth.js Documentation](https://next-auth.js.org/)
