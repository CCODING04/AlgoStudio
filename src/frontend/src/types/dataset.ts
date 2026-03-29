export interface DatasetResponse {
  dataset_id: string;
  name: string;
  description: string | null;
  path: string;
  storage_type: string;
  size_gb: number | null;
  file_count: number | null;
  version: string | null;
  metadata: Record<string, unknown> | null;
  tags: string[] | null;
  is_public: boolean;
  owner_id: string | null;
  team_id: string | null;
  is_active: boolean;
  last_accessed_at: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface CreateDatasetRequest {
  name: string;
  path: string;
  description?: string;
  storage_type?: string;
  metadata?: Record<string, unknown>;
  tags?: string[];
  is_public?: boolean;
  team_id?: string;
}

export interface UpdateDatasetRequest {
  name?: string;
  description?: string;
  metadata?: Record<string, unknown>;
  tags?: string[];
  is_public?: boolean;
}
