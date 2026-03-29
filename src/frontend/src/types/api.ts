export interface ApiResponse<T> {
  data?: T;
  error?: string;
}

export interface TaskListResponse {
  tasks: import('./task').TaskResponse[];
  total: number;
}

export interface HostStatusResponse {
  cluster_nodes: import('./host').HostInfo[];
  total_nodes: number;
  online_nodes: number;
}
