'use client';

import { useQuery, useMutation } from '@tanstack/react-query';
import { DatasetResponse, CreateDatasetRequest, UpdateDatasetRequest } from '@/types/dataset';

export interface BrowseResponse {
  path: string;
  folders: string[];
  exists: boolean;
}

export function useBrowseDatasets(path?: string) {
  const queryPath = path || '/mnt/VtrixDataset/data/';
  return useQuery<BrowseResponse>({
    queryKey: ['datasets-browse', queryPath],
    queryFn: async () => {
      const res = await fetch(`/api/proxy/datasets/browse?path=${encodeURIComponent(queryPath)}`, {
        cache: 'no-store',
      });
      if (!res.ok) throw new Error('Failed to browse datasets');
      return res.json();
    },
    // Don't retry often - directory scans should be cheap but not hammering
    retry: 2,
    staleTime: 30000, // Consider stale after 30 seconds
  });
}

export function useDatasets() {
  return useQuery<DatasetResponse[]>({
    queryKey: ['datasets'],
    queryFn: async () => {
      const res = await fetch('/api/proxy/datasets', {
        cache: 'no-store',
      });
      if (!res.ok) throw new Error('Failed to fetch datasets');
      const data = await res.json();
      // Handle both array and { items: [] } response formats
      if (Array.isArray(data)) return data;
      return data.items || [];
    },
    refetchInterval: 60000, // Refresh every minute
  });
}

export function useDataset(id: string) {
  return useQuery<DatasetResponse>({
    queryKey: ['dataset', id],
    queryFn: async () => {
      const res = await fetch(`/api/proxy/datasets/${id}`, {
        cache: 'no-store',
      });
      if (!res.ok) throw new Error('Failed to fetch dataset');
      return res.json();
    },
    enabled: !!id,
  });
}

export function useCreateDataset() {
  return useMutation({
    mutationFn: async (request: CreateDatasetRequest) => {
      const res = await fetch('/api/proxy/datasets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Failed to create dataset');
      }
      return res.json();
    },
  });
}

export function useUpdateDataset() {
  return useMutation({
    mutationFn: async ({ id, ...request }: UpdateDatasetRequest & { id: string }) => {
      const res = await fetch(`/api/proxy/datasets/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Failed to update dataset');
      }
      return res.json();
    },
  });
}

export function useDeleteDataset() {
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`/api/proxy/datasets/${id}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Failed to delete dataset');
      }
      return res.json();
    },
  });
}

export function useRestoreDataset() {
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`/api/proxy/datasets/${id}/restore`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Failed to restore dataset');
      }
      return res.json();
    },
  });
}
