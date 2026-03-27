# Phase 2.3 Hosts/Deploy Pages Architecture

**项目：** AlgoStudio AI 算法平台
**任务：** Phase 2.3 Hosts/Deploy 页面设计
**日期：** 2026-03-27
**版本：** v1.0
**负责人：** Frontend Engineer

---

## 1. 概述

### 1.1 任务范围

Phase 2.3 包含以下三个页面的完整前端实现：

| 页面 | 路由 | 功能 |
|------|------|------|
| Host List | `/hosts` | 主机列表 + 实时 GPU 状态 |
| Deploy | `/deploy` | 部署向导 |
| Deployment History | `/hosts/[hostId]/history` | 部署历史 + 日志查看 |

### 1.2 技术栈

基于 `web-console-frontend-architecture-report.md` 定义的技术栈：

- **框架：** Next.js 14+ App Router
- **UI 组件：** shadcn/ui + Tailwind CSS
- **状态管理：** React Query + Zustand
- **实时通信：** SSE (Server-Sent Events)
- **终端组件：** xterm.js

---

## 2. Page Layouts (ASCII Mockups)

### 2.1 Host List Page (`/hosts`)

```
+-----------------------------------------------------------------------+
|  [AlgoStudio Logo]                    [User] [Settings]              |
+-----------------------------------------------------------------------+
|  +------------------+                                               |
|  | Dashboard        |   Hosts List Page                              |
|  | Tasks            |   +------------------------------------------+ |
|  | [>] Hosts        |   | Page Header                              | |
|  |   - All Hosts    |   | Title: Host Monitoring                   | |
|  |   - 192.168.0.126|   | Subtitle: Ray cluster node status        | |
|  |   - 192.168.0.115|   +------------------------------------------+ |
|  | Deploy           |                                               |
|  |                  |   +----------------+ +----------------+        |
|  |                  |   | 2 Online       | | 0 Offline      |        |
|  |                  |   +----------------+ +----------------+        |
|  |                  |                                               |
|  |                  |   +------------------------------------------+ |
|  |                  |   | Filter: [All v] [GPU Status v] [Search] | |
|  |                  |   +------------------------------------------+ |
|  |                  |                                               |
|  |                  |   +------------------------------------------+ |
|  |                  |   | Host Cards Grid (2-col on desktop)      | |
|  |                  |   | +----------------+ +----------------+    | |
|  |                  |   | | RTX 4090       | | RTX 4090       |    | |
|  |                  |   | | 192.168.0.126  | | 192.168.0.115  |    | |
|  |                  |   | | Status: Online | | Status: Online |    | |
|  |                  |   | | GPU: 45°C 60%  | | GPU: 52°C 80%  |    | |
|  |                  |   | | RAM: 18GB/31GB | | RAM: 22GB/31GB |    | |
|  |                  |   | |                | |                |    | |
|  |                  |   | | [Deploy] [Log] | | [Deploy] [Log] |    | |
|  |                  |   | +----------------+ +----------------+    | |
|  |                  |   +------------------------------------------+ |
|  +------------------+                                               |
+-----------------------------------------------------------------------+
```

**SSE Real-time Updates:**
- GPU temperature, utilization, memory
- Ray worker status (running/stopped)
- Network connectivity status

### 2.2 Deploy Page (`/deploy`)

```
+-----------------------------------------------------------------------+
|  [AlgoStudio Logo]                    [User] [Settings]              |
+-----------------------------------------------------------------------+
|  +------------------+                                               |
|  | Dashboard        |   Deploy Page (Wizard)                         |
|  | Tasks            |   +------------------------------------------+ |
|  | Hosts            |   | Step Indicator: [1] --> [2] --> [3]      | |
|  | [>] Deploy       |   +------------------------------------------+ |
|  |                  |                                               |
|  |                  |   +------------------------------------------+ |
|  |                  |   | Step 1: Select Algorithm                | |
|  |                  |   | +--------------------------------------+ | |
|  |                  |   | | Algorithm: [simple_classifier v1 v] | | |
|  |                  |   | | +----------------------------------+ | | |
|  |                  |   | | | simple_classifier               | | | |
|  |                  |   | | | simple_detector                  | | | |
|  |                  |   | | | yolo_model                       | | | |
|  |                  |   | | +----------------------------------+ | | |
|  |                  |   | +--------------------------------------+ | |
|  |                  |   +------------------------------------------+ |
|  |                  |                                               |
|  |                  |   +------------------------------------------+ |
|  |                  |   | Step 2: Select Target Host              | |
|  |                  |   | +--------------------------------------+ | |
|  |                  |   | | Host: [192.168.0.115 (RTX 4090) v]  | | |
|  |                  |   | | +----------------------------------+ | | |
|  |                  |   | | | 192.168.0.126 (admin02) - Head   | | | |
|  |                  |   | | | 192.168.0.115 (admin10) - Worker | | | |
|  |                  |   | | +----------------------------------+ | | |
|  |                  |   | +--------------------------------------+ | |
|  |                  |   +------------------------------------------+ |
|  |                  |                                               |
|  |                  |   +------------------------------------------+ |
|  |                  |   | Step 3: Configure & Deploy              | |
|  |                  |   | +--------------------------------------+ | |
|  |                  |   | | [x] Start Ray Worker                 | | |
|  |                  |   | | [ ] Auto-restart on failure         | | |
|  |                  |   | |                                      | | |
|  |                  |   | | GPU Memory Limit: [24] GB            | | |
|  |                  |   | +--------------------------------------+ | |
|  |                  |   |                                      | | |
|  |                  |   | [Cancel]                    [Deploy]   | | |
|  |                  |   +------------------------------------------+ |
|  +------------------+                                               |
+-----------------------------------------------------------------------+
```

### 2.3 Deployment Progress (Modal)

```
+-----------------------------------------------------------------------+
|  Deployment Progress                                            [X]  |
+-----------------------------------------------------------------------+
|                                                                       |
|  Deploying simple_classifier v1 to 192.168.0.115                      |
|                                                                       |
|  +---------------------------------------------------------------+   |
|  | [=====================>                                ] 65% |   |
|  +---------------------------------------------------------------+   |
|                                                                       |
|  Current Step: Installing dependencies...                              |
|                                                                       |
|  +---------------------------------------------------------------+   |
|  | [2026-03-27 10:30:15] Starting deployment...                 |   |
|  | [2026-03-27 10:30:16] Connecting to 192.168.0.115...         |   |
|  | [2026-03-27 10:30:17] Syncing algorithm files...              |   |
|  | [2026-03-27 10:30:18] Installing dependencies...              |   |
|  | [2026-03-27 10:30:20] Starting Ray worker...                 |   |
|  +---------------------------------------------------------------+   |
|                                                                       |
|                              [Cancel] [View Logs]                      |
|                                                                       |
+-----------------------------------------------------------------------+
```

### 2.4 Deployment History Page (`/hosts/[hostId]/history`)

```
+-----------------------------------------------------------------------+
|  [AlgoStudio Logo]                    [User] [Settings]              |
+-----------------------------------------------------------------------+
|  +------------------+                                               |
|  | Dashboard        |   Deployment History                           |
|  | Tasks            |   Host: 192.168.0.115                          |
|  | Hosts            |   +------------------------------------------+ |
|  | [>] 192.168.0.115|   | [Back to Hosts]                          | |
|  |   - History      |   +------------------------------------------+ |
|  |                  |                                               |
|  | Deploy           |   +------------------------------------------+ |
|  |                  |   | Tabs: [History] [Logs]                    | |
|  |                  |   +------------------------------------------+ |
|  |                  |                                               |
|  |                  |   History Tab:                                |
|  |                  |   +------------------------------------------+ |
|  |                  |   | Deployment History Table                 | |
|  |                  |   | +-------------------------------------+  | |
|  |                  |   | | Time       | Algorithm   | Status |  | |
|  |                  |   | |-----------|-------------|--------|  | |
|  |                  |   | | 2026-03-27| simple_clas.|   OK   |  | |
|  |                  |   | | 10:30:15  | v1          |        |  | |
|  |                  |   | |-----------|-------------|--------|  | |
|  |                  |   | | 2026-03-26| yolo_model  |   OK   |  | |
|  |                  |   | | 14:22:30  | v2          |        |  | |
|  |                  |   | |-----------|-------------|--------|  | |
|  |                  |   | | 2026-03-25| simple_detec|  FAIL  |  | |
|  |                  |   | | 09:15:00  | v1          |        |  | |
|  |                  |   | +-------------------------------------+  | |
|  |                  |   +------------------------------------------+ |
|  |                  |                                               |
|  |                  |   Logs Tab:                                   |
|  |                  |   +------------------------------------------+ |
|  |                  |   | [Auto-scroll ON] [Clear] [Download]      | |
|  |                  |   +------------------------------------------+ |
|  |                  |   +------------------------------------------+ |
|  |                  |   | xterm.js Terminal                       | |
|  |                  |   | $ ray status                            | |
|  |                  |   | Node 192.168.0.115:                     | |
|  |                  |   |   - CPU: 8 cores                         | |
|  |                  |   |   - Memory: 31GB                         | |
|  |                  |   |   - GPU: RTX 4090 24GB                   | |
|  |                  |   +------------------------------------------+ |
|  +------------------+                                               |
+-----------------------------------------------------------------------+
```

---

## 3. Component Inventory

### 3.1 Host List Components

| Component | File | Description |
|-----------|------|-------------|
| `HostCard` | `components/hosts/host-card.tsx` | Card displaying single host info with GPU, status |
| `HostCardSkeleton` | `components/hosts/host-card-skeleton.tsx` | Loading skeleton for HostCard |
| `HostFilters` | `components/hosts/host-filters.tsx` | Filter dropdowns (status, GPU) |
| `GPU utilization bar` | `components/hosts/gpu-monitor.tsx` | GPU usage visualization |
| `ResourceBar` | `components/hosts/resource-bar.tsx` | Reusable RAM/Storage bar |
| `StatusBadge` | `components/ui/badge.tsx` | Online/Offline/Error status |
| `HostActions` | `components/hosts/host-actions.tsx` | Quick action buttons |

### 3.2 Deploy Components

| Component | File | Description |
|-----------|------|-------------|
| `DeployWizard` | `components/deploy/deploy-wizard.tsx` | Multi-step wizard container |
| `AlgorithmSelect` | `components/deploy/algorithm-select.tsx` | Algorithm dropdown with search |
| `HostSelect` | `components/deploy/host-select.tsx` | Target host selection |
| `DeployConfig` | `components/deploy/deploy-config.tsx` | Configuration checkboxes/inputs |
| `DeployProgress` | `components/deploy/deploy-progress.tsx` | Deployment progress modal |
| `StepIndicator` | `components/deploy/step-indicator.tsx` | Wizard step visualization |
| `DeployButton` | `components/deploy/deploy-button.tsx` | Primary deploy action |

### 3.3 History Components

| Component | File | Description |
|-----------|------|-------------|
| `HistoryTable` | `components/deploy/history-table.tsx` | Deployment history data table |
| `HistoryRow` | `components/deploy/history-row.tsx` | Single history entry |
| `LogViewer` | `components/logs/log-viewer.tsx` | Tab container for logs |
| `LogTerminal` | `components/logs/log-terminal.tsx` | xterm.js terminal wrapper |
| `LogControls` | `components/logs/log-controls.tsx` | Auto-scroll, clear, download |
| `LogFilter` | `components/logs/log-filter.tsx` | Log level filter |

### 3.4 Shared Components

| Component | File | Description |
|-----------|------|-------------|
| `PageHeader` | `components/layout/page-header.tsx` | Page title + subtitle |
| `Card` | `components/ui/card.tsx` | shadcn/ui Card |
| `Button` | `components/ui/button.tsx` | shadcn/ui Button |
| `Badge` | `components/ui/badge.tsx` | shadcn/ui Badge |
| `Tabs` | `components/ui/tabs.tsx` | shadcn/ui Tabs |
| `Progress` | `components/ui/progress.tsx` | shadcn/ui Progress |
| `Select` | `components/ui/select.tsx` | shadcn/ui Select |
| `Checkbox` | `components/ui/checkbox.tsx` | shadcn/ui Checkbox |
| `Input` | `components/ui/input.tsx` | shadcn/ui Input |
| `ScrollArea` | `components/ui/scroll-area.tsx` | shadcn/ui ScrollArea |
| `Dialog` | `components/ui/dialog.tsx` | shadcn/ui Dialog |
| `Sheet` | `components/ui/sheet.tsx` | shadcn/ui Sheet (side panel) |

---

## 4. State Management

### 4.1 Server State (React Query)

```typescript
// hooks/use-hosts.ts
'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getHosts, getHost, getHostHistory, deployToHost } from '@/lib/api';

// Get all hosts with real-time status
export function useHosts() {
  return useQuery({
    queryKey: ['hosts'],
    queryFn: () => getHosts(),
    refetchInterval: 10000, // 10s polling for GPU updates
  });
}

// Get single host details
export function useHost(hostId: string) {
  return useQuery({
    queryKey: ['host', hostId],
    queryFn: () => getHost(hostId),
    enabled: !!hostId,
    refetchInterval: 5000, // 5s for active monitoring
  });
}

// Get deployment history for host
export function useHostHistory(hostId: string) {
  return useQuery({
    queryKey: ['host', hostId, 'history'],
    queryFn: () => getHostHistory(hostId),
    enabled: !!hostId,
  });
}

// Deploy algorithm to host
export function useDeployToHost() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: DeployRequest) => deployToHost(data),
    onSuccess: (_, variables) => {
      // Invalidate host data to refresh status
      queryClient.invalidateQueries({ queryKey: ['host', variables.hostId] });
      queryClient.invalidateQueries({ queryKey: ['hosts'] });
    },
  });
}
```

### 4.2 UI State (Zustand)

```typescript
// lib/stores/ui-store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface HostUIState {
  // Host list filters
  statusFilter: 'all' | 'online' | 'offline';
  gpuFilter: 'all' | 'available' | 'busy';
  searchQuery: string;

  // Deploy wizard state
  deployWizardOpen: boolean;
  deployStep: number;
  selectedAlgorithm: string | null;
  selectedHost: string | null;

  // Actions
  setStatusFilter: (filter: 'all' | 'online' | 'offline') => void;
  setGpuFilter: (filter: 'all' | 'available' | 'busy') => void;
  setSearchQuery: (query: string) => void;
  openDeployWizard: () => void;
  closeDeployWizard: () => void;
  setDeployStep: (step: number) => void;
  setSelectedAlgorithm: (algo: string | null) => void;
  setSelectedHost: (host: string | null) => void;
  resetDeployWizard: () => void;
}

export const useHostUIStore = create<HostUIState>()(
  persist(
    (set) => ({
      statusFilter: 'all',
      gpuFilter: 'all',
      searchQuery: '',
      deployWizardOpen: false,
      deployStep: 1,
      selectedAlgorithm: null,
      selectedHost: null,

      setStatusFilter: (filter) => set({ statusFilter: filter }),
      setGpuFilter: (filter) => set({ gpuFilter: filter }),
      setSearchQuery: (query) => set({ searchQuery: query }),
      openDeployWizard: () => set({ deployWizardOpen: true, deployStep: 1 }),
      closeDeployWizard: () => set({ deployWizardOpen: false }),
      setDeployStep: (step) => set({ deployStep: step }),
      setSelectedAlgorithm: (algo) => set({ selectedAlgorithm: algo }),
      setSelectedHost: (host) => set({ selectedHost: host }),
      resetDeployWizard: () => set({
        deployWizardOpen: false,
        deployStep: 1,
        selectedAlgorithm: null,
        selectedHost: null,
      }),
    }),
    { name: 'host-ui-store' }
  )
);
```

### 4.3 SSE State (Local Component State)

```typescript
// hooks/use-host-sse.ts
'use client';

import { useEffect, useRef, useState } from 'react';

interface GPUMetrics {
  temperature: number;
  utilization: number;  // 0-100
  memoryUsed: number;   // GB
  memoryTotal: number;  // GB
}

interface HostStatusUpdate {
  hostId: string;
  status: 'online' | 'offline' | 'error';
  gpu: GPUMetrics;
  rayWorkers: number;
  lastSeen: string;
}

export function useHostSSE(hostId: string) {
  const [status, setStatus] = useState<HostStatusUpdate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!hostId) return;

    const eventSource = new EventSource(`/api/hosts/${hostId}/stream`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setStatus(data);
      } catch (e) {
        setError('Failed to parse status update');
      }
    };

    eventSource.onerror = () => {
      setError('SSE connection lost');
      // Auto-reconnect handled by browser
    };

    return () => {
      eventSource.close();
    };
  }, [hostId]);

  return { status, error };
}
```

---

## 5. API Integration Points

### 5.1 Backend API Endpoints

Based on existing FastAPI routes:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/hosts` | List all cluster nodes |
| GET | `/api/hosts/{node_id}` | Get single node details |
| GET | `/api/hosts/{node_id}/history` | Get deployment history |
| POST | `/api/deploy` | Deploy algorithm to host |
| GET | `/api/hosts/{node_id}/stream` | SSE for real-time status |

### 5.2 API Client Implementation

```typescript
// lib/api/hosts.ts
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export interface HostResponse {
  node_id: string;
  hostname: string;
  ip_address: string;
  status: 'online' | 'offline' | 'error';
  cpu_cores: number;
  memory_total: number;
  gpu: {
    name: string;
    memory_total: number;
    memory_used: number;
    utilization: number;
    temperature: number;
  } | null;
  ray_workers: number;
  last_heartbeat: string;
}

export interface DeploymentHistoryResponse {
  deployments: {
    id: string;
    algorithm_name: string;
    algorithm_version: string;
    status: 'success' | 'failed' | 'cancelled';
    started_at: string;
    completed_at: string | null;
    logs: string;
  }[];
}

export interface DeployRequest {
  host_id: string;
  algorithm_name: string;
  algorithm_version: string;
  config?: {
    gpu_memory_limit?: number;
    auto_restart?: boolean;
  };
}

export async function getHosts(): Promise<HostResponse[]> {
  const res = await fetch(`${API_BASE}/api/hosts`);
  if (!res.ok) throw new Error('Failed to fetch hosts');
  const data = await res.json();
  return data.nodes;
}

export async function getHost(nodeId: string): Promise<HostResponse> {
  const res = await fetch(`${API_BASE}/api/hosts/${nodeId}`);
  if (!res.ok) throw new Error('Failed to fetch host');
  return res.json();
}

export async function getHostHistory(nodeId: string): Promise<DeploymentHistoryResponse> {
  const res = await fetch(`${API_BASE}/api/hosts/${nodeId}/history`);
  if (!res.ok) throw new Error('Failed to fetch history');
  return res.json();
}

export async function deployToHost(data: DeployRequest): Promise<{ task_id: string }> {
  const res = await fetch(`${API_BASE}/api/deploy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to deploy');
  return res.json();
}
```

### 5.3 SSE Endpoint Proxy (Next.js API Route)

```typescript
// app/api/proxy/hosts/[hostId]/stream/route.ts
export async function GET(
  request: Request,
  { params }: { params: { hostId: string } }
) {
  const hostId = params.hostId;
  const apiBase = process.env.API_BASE_URL || 'http://localhost:8000';

  // Create SSE connection to backend
  const response = await fetch(`${apiBase}/api/hosts/${hostId}/stream`, {
    headers: {
      'Accept': 'text/event-stream',
      'Cache-Control': 'no-cache',
    },
  });

  // Stream the response to client
  return new Response(response.body, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
```

---

## 6. Page Implementations

### 6.1 Host List Page

```typescript
// app/(main)/hosts/page.tsx
import { getHosts } from '@/lib/api';
import { HostCard } from '@/components/hosts/host-card';
import { HostFilters } from '@/components/hosts/host-filters';
import { PageHeader } from '@/components/layout/page-header';
import { Badge } from '@/components/ui/badge';

export const revalidate = 10; // ISR: 10s

export default async function HostsPage() {
  const hosts = await getHosts();

  const onlineCount = hosts.filter((h) => h.status === 'online').length;
  const offlineCount = hosts.filter((h) => h.status === 'offline').length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Host Monitoring"
        subtitle="Ray cluster node status"
      />

      {/* Status Summary */}
      <div className="flex gap-4">
        <Badge variant="default" className="text-base px-4 py-2">
          {onlineCount} Online
        </Badge>
        <Badge variant="secondary" className="text-base px-4 py-2">
          {offlineCount} Offline
        </Badge>
      </div>

      {/* Filters */}
      <HostFilters />

      {/* Host Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {hosts.map((host) => (
          <HostCard key={host.node_id} host={host} />
        ))}
      </div>
    </div>
  );
}
```

### 6.2 Deploy Page

```typescript
// app/(main)/deploy/page.tsx
'use client';

import { useState } from 'react';
import { useHosts } from '@/hooks/use-hosts';
import { useAlgorithms } from '@/hooks/use-algorithms';
import { useDeployToHost } from '@/hooks/use-hosts';
import { useHostUIStore } from '@/lib/stores/ui-store';
import { DeployWizard } from '@/components/deploy/deploy-wizard';
import { AlgorithmSelect } from '@/components/deploy/algorithm-select';
import { HostSelect } from '@/components/deploy/host-select';
import { DeployConfig } from '@/components/deploy/deploy-config';
import { DeployProgress } from '@/components/deploy/deploy-progress';
import { StepIndicator } from '@/components/deploy/step-indicator';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/layout/page-header';

export default function DeployPage() {
  const {
    deployWizardOpen,
    deployStep,
    selectedAlgorithm,
    selectedHost,
    setDeployStep,
    resetDeployWizard,
  } = useHostUIStore();

  const { data: hosts } = useHosts();
  const { data: algorithms } = useAlgorithms();
  const deployMutation = useDeployToHost();
  const [deployTaskId, setDeployTaskId] = useState<string | null>(null);

  const canProceed = () => {
    switch (deployStep) {
      case 1:
        return !!selectedAlgorithm;
      case 2:
        return !!selectedHost;
      case 3:
        return true;
      default:
        return false;
    }
  };

  const handleNext = async () => {
    if (deployStep === 3) {
      // Execute deployment
      const result = await deployMutation.mutateAsync({
        host_id: selectedHost!,
        algorithm_name: selectedAlgorithm!,
        algorithm_version: 'v1',
      });
      setDeployTaskId(result.task_id);
    } else {
      setDeployStep(deployStep + 1);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Deploy Algorithm"
        subtitle="Deploy algorithms to Ray cluster nodes"
      />

      {/* Show progress modal if deploying */}
      {deployTaskId ? (
        <DeployProgress taskId={deployTaskId} onClose={resetDeployWizard} />
      ) : (
        <>
          <StepIndicator currentStep={deployStep} totalSteps={3} />

          <div className="bg-card rounded-lg border p-6">
            {deployStep === 1 && (
              <AlgorithmSelect
                algorithms={algorithms || []}
                selected={selectedAlgorithm}
                onSelect={(algo) => useHostUIStore.getState().setSelectedAlgorithm(algo)}
              />
            )}

            {deployStep === 2 && (
              <HostSelect
                hosts={hosts || []}
                selected={selectedHost}
                onSelect={(host) => useHostUIStore.getState().setSelectedHost(host)}
              />
            )}

            {deployStep === 3 && (
              <DeployConfig
                selectedHost={selectedHost}
                selectedAlgorithm={selectedAlgorithm}
              />
            )}
          </div>

          <div className="flex justify-between">
            <Button
              variant="outline"
              onClick={deployStep === 1 ? () => resetDeployWizard() : () => setDeployStep(deployStep - 1)}
            >
              {deployStep === 1 ? 'Cancel' : 'Back'}
            </Button>
            <Button
              onClick={handleNext}
              disabled={!canProceed() || deployMutation.isPending}
            >
              {deployStep === 3 ? 'Deploy' : 'Next'}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
```

### 6.3 Deployment History Page

```typescript
// app/(main)/hosts/[hostId]/history/page.tsx
'use client';

import { useState } from 'react';
import { useHostHistory } from '@/hooks/use-hosts';
import { useHost } from '@/hooks/use-hosts';
import { PageHeader } from '@/components/layout/page-header';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { HistoryTable } from '@/components/deploy/history-table';
import { LogViewer } from '@/components/logs/log-viewer';
import { Button } from '@/components/ui/button';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function HostHistoryPage({ params }: { params: { hostId: string } }) {
  const hostId = params.hostId;
  const { data: host, isLoading: hostLoading } = useHost(hostId);
  const { data: history, isLoading: historyLoading } = useHostHistory(hostId);
  const [activeTab, setActiveTab] = useState<'history' | 'logs'>('history');
  const [selectedDeploymentLogs, setSelectedDeploymentLogs] = useState<string | null>(null);

  if (hostLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/hosts">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <PageHeader
          title={`Deployment History - ${host?.hostname || hostId}`}
          subtitle={`Host: ${host?.ip_address}`}
        />
      </div>

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'history' | 'logs')}>
        <TabsList>
          <TabsTrigger value="history">History</TabsTrigger>
          <TabsTrigger value="logs">Live Logs</TabsTrigger>
        </TabsList>

        <TabsContent value="history" className="space-y-4">
          <HistoryTable
            history={history?.deployments || []}
            onViewLogs={(deployment) => {
              setSelectedDeploymentLogs(deployment.logs);
              setActiveTab('logs');
            }}
            isLoading={historyLoading}
          />
        </TabsContent>

        <TabsContent value="logs">
          <LogViewer
            hostId={hostId}
            initialLogs={selectedDeploymentLogs}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

---

## 7. Component Details

### 7.1 HostCard Component

```typescript
// components/hosts/host-card.tsx
'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ResourceBar } from './resource-bar';
import { GPUUtilization } from './gpu-monitor';
import { HostStatusUpdate } from '@/hooks/use-host-sse';
import { useHostSSE } from '@/hooks/use-host-sse';
import { Play, FileText, RefreshCw } from 'lucide-react';
import Link from 'next/link';

interface HostCardProps {
  host: {
    node_id: string;
    hostname: string;
    ip_address: string;
    status: 'online' | 'offline' | 'error';
    gpu: {
      name: string;
      memory_total: number;
      memory_used: number;
      utilization: number;
      temperature: number;
    } | null;
    memory_total: number;
    ray_workers: number;
  };
}

export function HostCard({ host }: HostCardProps) {
  const { status: realtimeStatus } = useHostSSE(host.node_id);

  // Merge static data with real-time updates
  const displayStatus = realtimeStatus?.status || host.status;
  const gpu = realtimeStatus?.gpu || host.gpu;

  const statusConfig = {
    online: { label: 'Online', variant: 'success' as const },
    offline: { label: 'Offline', variant: 'secondary' as const },
    error: { label: 'Error', variant: 'destructive' as const },
  };

  const status = statusConfig[displayStatus];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-lg font-medium">
          {host.gpu?.name || 'No GPU'}
        </CardTitle>
        <Badge variant={status.variant}>{status.label}</Badge>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Host Info */}
        <div className="text-sm text-muted-foreground">
          <p className="font-mono">{host.ip_address}</p>
          <p>{host.hostname}</p>
        </div>

        {/* GPU Section */}
        {gpu && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>GPU</span>
              <span>{gpu.temperature}C / {gpu.utilization}%</span>
            </div>
            <GPUUtilization value={gpu.utilization} />

            <ResourceBar
              label="GPU Memory"
              used={gpu.memory_used}
              total={gpu.memory_total}
              unit="GB"
            />
          </div>
        )}

        {/* RAM Section */}
        <ResourceBar
          label="RAM"
          used={host.memory_total - (realtimeStatus ? host.memory_total * 0.4 : host.memory_total * 0.6)}
          total={host.memory_total}
          unit="GB"
        />

        {/* Ray Workers */}
        <div className="flex justify-between text-sm">
          <span>Ray Workers</span>
          <span className="font-medium">{realtimeStatus?.rayWorkers || host.ray_workers}</span>
        </div>

        {/* Actions */}
        <div className="flex gap-2 pt-2">
          <Link href={`/deploy?host=${host.node_id}`} className="flex-1">
            <Button variant="outline" className="w-full">
              <Play className="mr-2 h-4 w-4" />
              Deploy
            </Button>
          </Link>
          <Link href={`/hosts/${host.node_id}/history`} className="flex-1">
            <Button variant="outline" className="w-full">
              <FileText className="mr-2 h-4 w-4" />
              Logs
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
```

### 7.2 LogViewer Component

```typescript
// components/logs/log-viewer.tsx
'use client';

import { useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { LogControls } from './log-controls';
import { useLogStore } from '@/lib/stores/log-store';
import '@xterm/xterm/css/xterm.css';

interface LogViewerProps {
  hostId: string;
  initialLogs?: string | null;
}

export function LogViewer({ hostId, initialLogs }: LogViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const addLog = useLogStore((state) => state.addLog);

  useEffect(() => {
    if (!containerRef.current) return;

    // Initialize xterm.js
    const term = new Terminal({
      theme: { background: '#0c0c0c', foreground: '#f0f0f0' },
      fontSize: 13,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      cursorBlink: true,
      rows: 30,
      scrollback: 10000,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(containerRef.current);
    fitAddon.fit();

    termRef.current = term;
    fitAddonRef.current = fitAddon;

    // Display initial logs if provided
    if (initialLogs) {
      term.write(initialLogs);
    }

    // SSE connection for live logs
    const eventSource = new EventSource(`/api/hosts/${hostId}/logs`);
    let buffer = '';

    eventSource.onmessage = (event) => {
      const data = event.data;
      term.write(data);

      // Update store for search
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

      // Auto-scroll
      if (autoScroll) {
        term.scrollToBottom();
      }
    };

    eventSource.onerror = () => {
      term.write('\r\n\x1b[33m[Connection Lost]\x1b[0m\r\n');
    };

    // Resize handler
    const handleResize = () => fitAddon.fit();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      eventSource.close();
      term.dispose();
    };
  }, [hostId, initialLogs, autoScroll, addLog]);

  return (
    <div className="space-y-2">
      <LogControls
        autoScroll={autoScroll}
        onAutoScrollChange={setAutoScroll}
        onClear={() => termRef.current?.clear()}
        onDownload={() => {
          const content = useLogStore.getState().logs.map((l) => l.message).join('\n');
          const blob = new Blob([content], { type: 'text/plain' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `host-${hostId}-logs-${Date.now()}.txt`;
          a.click();
        }}
      />
      <div
        ref={containerRef}
        className="h-[500px] rounded-lg border bg-black p-2"
      />
    </div>
  );
}
```

### 7.3 DeployProgress Component

```typescript
// components/deploy/deploy-progress.tsx
'use client';

import { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { useTaskSSE } from '@/hooks/use-tasks';
import { X, FileText } from 'lucide-react';
import Link from 'next/link';

interface DeployProgressProps {
  taskId: string;
  onClose: () => void;
}

interface DeployLog {
  timestamp: string;
  message: string;
}

export function DeployProgress({ taskId, onClose }: DeployProgressProps) {
  const { progress, status, logs } = useTaskSSE(taskId);
  const [deployLogs, setDeployLogs] = useState<DeployLog[]>([]);

  useEffect(() => {
    if (logs) {
      setDeployLogs((prev) => [...prev.slice(-100), { timestamp: new Date().toISOString(), message: logs }]);
    }
  }, [logs]);

  const isComplete = status === 'completed' || status === 'failed';

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Deployment Progress</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Progress Bar */}
          <div className="space-y-2">
            <Progress value={progress || 0} />
            <p className="text-sm text-muted-foreground text-center">
              {progress || 0}%
            </p>
          </div>

          {/* Status */}
          <p className="text-sm">
            Status: <span className="font-medium capitalize">{status}</span>
          </p>

          {/* Logs */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium">Deployment Logs</h4>
            <div className="max-h-[300px] overflow-y-auto rounded border bg-muted p-3 font-mono text-xs">
              {deployLogs.map((log, i) => (
                <div key={i} className="text-muted-foreground">
                  [{log.timestamp}] {log.message}
                </div>
              ))}
              {!deployLogs.length && <p className="text-muted-foreground">Waiting for logs...</p>}
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              {isComplete ? 'Close' : 'Cancel'}
            </Button>
            {isComplete && (
              <Link href="/hosts">
                <Button>View Hosts</Button>
              </Link>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

---

## 8. Directory Structure

```
web-console/
├── src/
│   ├── app/
│   │   └── (main)/
│   │       ├── hosts/
│   │       │   ├── page.tsx                    # Host list page
│   │       │   └── [hostId]/
│   │       │       └── history/
│   │       │           └── page.tsx            # Deployment history
│   │       ├── deploy/
│   │       │   └── page.tsx                    # Deploy wizard
│   │       └── api/
│   │           └── proxy/
│   │               └── hosts/
│   │                   └── [hostId]/
│   │                       ├── route.ts        # GET /api/hosts/:id
│   │                       └── stream/
│   │                           └── route.ts    # SSE proxy
│   │
│   ├── components/
│   │   ├── hosts/
│   │   │   ├── host-card.tsx
│   │   │   ├── host-card-skeleton.tsx
│   │   │   ├── host-filters.tsx
│   │   │   ├── gpu-monitor.tsx
│   │   │   ├── resource-bar.tsx
│   │   │   └── host-actions.tsx
│   │   │
│   │   ├── deploy/
│   │   │   ├── deploy-wizard.tsx
│   │   │   ├── algorithm-select.tsx
│   │   │   ├── host-select.tsx
│   │   │   ├── deploy-config.tsx
│   │   │   ├── deploy-progress.tsx
│   │   │   ├── deploy-button.tsx
│   │   │   ├── step-indicator.tsx
│   │   │   └── history-table.tsx
│   │   │
│   │   └── logs/
│   │       ├── log-viewer.tsx
│   │       ├── log-terminal.tsx
│   │       ├── log-controls.tsx
│   │       └── log-filter.tsx
│   │
│   ├── hooks/
│   │   ├── use-hosts.ts
│   │   ├── use-host-sse.ts
│   │   ├── use-deploy.ts
│   │   └── use-task-sse.ts
│   │
│   └── lib/
│       ├── api/
│       │   └── hosts.ts
│       └── stores/
│           └── ui-store.ts
```

---

## 9. Implementation Order

### Phase 2.3 (Week 5-6)

| Order | Task | Components | Duration |
|-------|------|------------|----------|
| 1 | Host List Page | `HostCard`, `HostFilters`, `useHostSSE` | 2 days |
| 2 | Deploy Page (Wizard) | `DeployWizard`, `AlgorithmSelect`, `HostSelect`, `DeployConfig` | 2 days |
| 3 | Deploy Progress | `DeployProgress`, `StepIndicator` | 1 day |
| 4 | History Page | `HistoryTable`, `LogViewer` | 2 days |
| 5 | Integration + SSE | Connect all components with SSE | 1 day |
| 6 | Testing | Unit tests, manual testing | 2 days |

---

## 10. Dependencies on Backend

| Backend Endpoint | Status | Required By |
|-------------------|--------|-------------|
| `GET /api/hosts` | Available | HostCard, HostFilters |
| `GET /api/hosts/{id}` | Available | HostCard (detail) |
| `GET /api/hosts/{id}/history` | **Needed** | HistoryTable |
| `GET /api/hosts/{id}/stream` | **Needed** | useHostSSE |
| `GET /api/hosts/{id}/logs` | **Needed** | LogViewer |
| `POST /api/deploy` | **Needed** | DeployProgress |
| `GET /api/algorithms` | **Needed** | AlgorithmSelect |

**Note:** Backend endpoints marked as "Needed" should be implemented in parallel by Backend Engineer.
