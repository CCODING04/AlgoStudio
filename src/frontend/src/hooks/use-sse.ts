'use client';

import { useEffect, useCallback, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';

interface SSEProgressUpdate {
  task_id: string;
  progress: number;
  status: string;
  description?: string;
}

const MAX_RECONNECT_ATTEMPTS = 5;
const INITIAL_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 30000;

export function useTaskSSE(taskId: string | null, onProgress?: (update: SSEProgressUpdate) => void) {
  const queryClient = useQueryClient();
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data) as SSEProgressUpdate;
      if (data.task_id === taskId) {
        // Update React Query cache
        queryClient.setQueryData(['task', taskId], (old: unknown) => {
          if (old && typeof old === 'object') {
            return { ...old, progress: data.progress, status: data.status };
          }
          return old;
        });

        // Update tasks list cache
        queryClient.setQueryData(['tasks', undefined], (old: { tasks?: unknown[] } | undefined) => {
          if (old?.tasks) {
            return {
              ...old,
              tasks: old.tasks.map((task: unknown) => {
                if ((task as { task_id?: string })?.task_id === taskId) {
                  return { ...(task as object), progress: data.progress, status: data.status };
                }
                return task;
              }),
            };
          }
          return old;
        });

        onProgress?.(data);
      }
    } catch {
      // Ignore parse errors
    }
  }, [taskId, queryClient, onProgress]);

  const connect = useCallback(() => {
    if (!taskId) return;

    // Clean up existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = new EventSource(`/api/proxy/tasks/${taskId}/events`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = handleMessage;

    eventSource.onerror = () => {
      eventSource.close();

      // Don't reconnect if we've exceeded max attempts
      if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
        return;
      }

      // Calculate exponential backoff delay
      const delay = Math.min(
        INITIAL_RECONNECT_DELAY_MS * Math.pow(2, reconnectAttemptsRef.current),
        MAX_RECONNECT_DELAY_MS
      );

      reconnectAttemptsRef.current += 1;

      // Schedule reconnection
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, delay);
    };
  }, [taskId, handleMessage]);

  useEffect(() => {
    if (!taskId) return;

    // Reset state on new taskId
    reconnectAttemptsRef.current = 0;
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    connect();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      reconnectAttemptsRef.current = 0;
    };
  }, [taskId, connect]);
}
