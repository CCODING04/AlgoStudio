'use client';

import { useEffect, useRef, useCallback } from 'react';
import { toast } from 'sonner';

interface SSEAllocatedEvent {
  task_id: string;
  node_id: string;
  node_name: string;
  status: 'allocated';
}

interface SSEProgressUpdate {
  task_id: string;
  progress: number;
  status: string;
  description?: string;
}

type SSEMessage = SSEAllocatedEvent | SSEProgressUpdate;

const MAX_RECONNECT_ATTEMPTS = 5;
const INITIAL_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 30000;

export function useTaskSSEWithToast(taskId: string | null, enabled: boolean = true) {
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const hasShownAllocatedToastRef = useRef<Set<string>>(new Set());

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!taskId || !enabled) {
      cleanup();
      return;
    }

    // Reset state on new taskId
    reconnectAttemptsRef.current = 0;
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    const eventSource = new EventSource(`/api/proxy/tasks/${taskId}/events`);
    eventSourceRef.current = eventSource;

    // Handle named 'allocated' event
    eventSource.addEventListener('allocated', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as SSEAllocatedEvent;
        // Prevent duplicate toasts for the same task
        if (data.task_id === taskId && !hasShownAllocatedToastRef.current.has(taskId)) {
          hasShownAllocatedToastRef.current.add(taskId);
          toast.success(`任务已分配到 ${data.node_name || data.node_id}`, {
            description: `任务ID: ${data.task_id}`,
            duration: 5000,
          });
        }
      } catch {
        // Ignore parse errors
      }
    });

    // Handle default messages (progress updates)
    eventSource.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as SSEMessage;
        // Only process if it's a progress update for this task
        if ('progress' in data && data.task_id === taskId) {
          // Progress updates are handled by useTaskSSE hook
          // This hook only handles allocated events
        }
      } catch {
        // Ignore parse errors
      }
    };

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
        cleanup();
        // Reconnect by triggering useEffect re-run
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
      }, delay);
    };

    return cleanup;
  }, [taskId, enabled, cleanup]);

  // Reset the toast flag when taskId changes
  useEffect(() => {
    if (taskId) {
      hasShownAllocatedToastRef.current.delete(taskId);
    }
  }, [taskId]);
}
