/**
 * Shared constants for the AlgoStudio frontend.
 * Extracted from duplicated definitions across multiple components.
 */

// --- Task Status ---

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface StatusConfigEntry {
  label: string;
  variant: 'default' | 'secondary' | 'destructive' | 'success';
}

export const statusConfig: Record<TaskStatus, StatusConfigEntry> = {
  pending: { label: '待处理', variant: 'secondary' },
  running: { label: '运行中', variant: 'default' },
  completed: { label: '已完成', variant: 'success' },
  failed: { label: '失败', variant: 'destructive' },
  cancelled: { label: '已取消', variant: 'destructive' },
};

export function getStatusConfig(status: string): StatusConfigEntry {
  return statusConfig[status as TaskStatus] || statusConfig.pending;
}

// --- Task Type ---

export type TaskType = 'train' | 'infer' | 'verify';

export const taskTypeLabels: Record<TaskType, string> = {
  train: '训练',
  infer: '推理',
  verify: '验证',
};

export function getTaskTypeLabel(type: string): string {
  return taskTypeLabels[type as TaskType] || type;
}

// --- Host Status ---

export type HostStatus = 'online' | 'offline' | 'idle' | 'busy';

export interface HostStatusConfigEntry {
  label: string;
  variant: 'success' | 'secondary' | 'warning' | 'outline';
}

export const hostStatusConfig: Record<HostStatus, HostStatusConfigEntry> = {
  online: { label: '在线', variant: 'success' },
  offline: { label: '离线', variant: 'secondary' },
  idle: { label: '空闲', variant: 'success' },
  busy: { label: '忙碌', variant: 'warning' },
};

export function getHostStatusConfig(status: string): HostStatusConfigEntry {
  return hostStatusConfig[status as HostStatus] || hostStatusConfig.offline;
}

// --- Pagination ---

export const DEFAULT_PAGE_SIZE = 10;
