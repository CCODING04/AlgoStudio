'use client';

import { useQuery } from '@tanstack/react-query';
import { getHostStatus } from '@/lib/api';

export function useHosts() {
  return useQuery({
    queryKey: ['hosts'],
    queryFn: getHostStatus,
    refetchInterval: 10000,
  });
}
