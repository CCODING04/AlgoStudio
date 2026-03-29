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

export interface TaskCreateRequest {
  task_type: 'train' | 'infer' | 'verify';
  algorithm_name: string;
  algorithm_version: string;
  config?: Record<string, unknown>;
  data_path?: string;
}

export interface ProgressUpdate {
  task_id: string;
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
