// API client that routes through Next.js proxy to avoid exposing API key
// All calls go to /api/proxy/* which adds authentication headers server-side

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

export interface TaskPaginatedResponse {
  items: TaskResponse[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface HostResource {
  cpu: {
    total: number;
    used: number;
    physical_cores?: number;
    model?: string;
    freq_mhz?: number;
  };
  gpu: {
    total: number;
    utilization: number;
    memory_used: string;
    memory_total: string;
    name?: string;
  };
  memory: {
    total: string;
    used: string;
  };
  disk?: {
    total: string;
    used: string;
  };
  swap?: {
    total: string;
    used: string;
  };
}

export interface HostInfo {
  node_id: string;
  ip: string;
  status: 'online' | 'offline' | 'idle' | 'busy';
  is_local: boolean;
  hostname: string;
  role?: 'head' | 'worker';
  labels?: string[];
  resources: HostResource;
}

export interface HostStatusResponse {
  cluster_nodes: HostInfo[];
  error?: string;
}

export async function getTasks(status?: string): Promise<TaskResponse[]> {
  const params = status ? `?status=${status}` : '';
  const res = await fetch(`/api/proxy/tasks${params}`, {
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to fetch tasks');
  const data: TaskPaginatedResponse = await res.json();
  return data.items || [];
}

export async function getTask(taskId: string): Promise<TaskResponse> {
  const res = await fetch(`/api/proxy/tasks/${taskId}`, {
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to fetch task');
  return res.json();
}

export interface CreateTaskRequest {
  task_type: 'train' | 'infer' | 'verify';
  algorithm_name: string;
  algorithm_version: string;
  data_path?: string;
  inputs?: string[];
  config?: Record<string, unknown>;
}

export async function createTask(request: CreateTaskRequest): Promise<TaskResponse> {
  const res = await fetch('/api/proxy/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error('Failed to create task');
  return res.json();
}

export async function dispatchTask(taskId: string, nodeId?: string): Promise<TaskResponse> {
  const res = await fetch(`/api/proxy/tasks/${taskId}/dispatch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ node_id: nodeId || null }),
  });
  if (!res.ok) throw new Error('Failed to dispatch task');
  return res.json();
}

export async function getHostStatus(): Promise<HostStatusResponse> {
  const res = await fetch('/api/proxy/hosts', {
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to fetch hosts');
  return res.json();
}

// Deploy API functions
export interface DeployProgress {
  task_id: string;
  status: string;
  step: string;
  step_index: number;
  total_steps: number;
  progress: number;
  message?: string;
  error?: string;
  node_ip?: string;
  started_at?: string;
  completed_at?: string;
}

export async function getDeployWorkers(): Promise<{ items: DeployProgress[]; total: number }> {
  const res = await fetch('/api/proxy/deploy/workers', {
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to fetch deploy workers');
  return res.json();
}

export async function getDeployWorker(taskId: string): Promise<DeployProgress> {
  const res = await fetch(`/api/proxy/deploy/worker/${taskId}`, {
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to fetch deploy worker');
  return res.json();
}

export async function createDeployWorker(request: {
  node_ip: string;
  username?: string;
  password: string;
  head_ip: string;
  ray_port?: number;
  proxy_url?: string;
}): Promise<{ task_id: string; message: string; node_ip: string }> {
  const res = await fetch('/api/proxy/deploy/worker', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    // Extract meaningful error message from backend
    const errorDetail = errorData?.detail?.error?.message || errorData?.detail?.error || errorData?.detail || errorData?.error || 'Failed to create deploy worker';
    throw new Error(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail));
  }
  return res.json();
}
