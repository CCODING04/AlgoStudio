export interface DatasetResponse {
  id?: string;
  name: string;
  path: string;
  version: string | null;
  size_gb: number | null;
  created_at?: string;
}

export interface CreateDatasetRequest {
  name: string;
  path: string;
}

export interface UpdateDatasetRequest {
  name?: string;
  path?: string;
}
