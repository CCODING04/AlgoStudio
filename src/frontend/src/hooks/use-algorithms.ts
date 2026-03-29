'use client';

import { useQuery } from '@tanstack/react-query';

export interface Algorithm {
  name: string;
  version: string;
}

async function fetchAlgorithms(): Promise<Algorithm[]> {
  const res = await fetch('/api/proxy/algorithms', {
    cache: 'no-store',
  });
  if (!res.ok) {
    throw new Error('Failed to fetch algorithms');
  }
  const data = await res.json();
  return data.items || data.algorithms || data;
}

export function useAlgorithms() {
  return useQuery({
    queryKey: ['algorithms'],
    queryFn: fetchAlgorithms,
    staleTime: 5 * 60 * 1000, // 5 minutes - algorithms don't change often
  });
}
