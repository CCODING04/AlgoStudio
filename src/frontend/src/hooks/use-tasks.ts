'use client';

import { useQuery } from '@tanstack/react-query';
import { getTasks, getTask } from '@/lib/api';

export function useTasks(status?: string) {
  return useQuery({
    queryKey: ['tasks', status],
    queryFn: () => getTasks(status),
    refetchInterval: 30000,
  });
}

export function useTask(taskId: string) {
  return useQuery({
    queryKey: ['task', taskId],
    queryFn: () => getTask(taskId),
    enabled: !!taskId,
  });
}
