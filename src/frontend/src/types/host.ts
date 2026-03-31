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
  resources: HostResource;
}

export interface ClusterStatus {
  cluster_nodes: HostInfo[];
  error?: string;
}
