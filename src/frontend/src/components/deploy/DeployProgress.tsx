'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { X, FileText, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import Link from 'next/link';

interface DeployProgressProps {
  taskId: string;
  hostId: string;
  algorithmName: string;
  onClose: () => void;
}

interface DeployLog {
  timestamp: string;
  message: string;
}

interface DeployProgressUpdate {
  task_id: string;
  status: string;
  step: string;
  step_index: number;
  total_steps: number;
  progress: number;
  message?: string;
  error?: string;
  node_ip?: string;
  started_at?: string;
  completed_at?: string;
}

const MAX_RECONNECT_ATTEMPTS = 5;
const INITIAL_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 30000;

export function DeployProgress({ taskId, hostId, algorithmName, onClose }: DeployProgressProps) {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<'pending' | 'running' | 'completed' | 'failed'>('pending');
  const [logs, setLogs] = useState<DeployLog[]>([]);
  const [currentStep, setCurrentStep] = useState('');
  const [error, setError] = useState<string | null>(null);

  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const handleSSEMessage = useCallback((event: MessageEvent) => {
    try {
      const data: DeployProgressUpdate = JSON.parse(event.data);

      setProgress(data.progress);
      setCurrentStep(data.step);
      setStatus(
        data.status === 'completed' ? 'completed' :
        data.status === 'failed' ? 'failed' :
        data.status === 'cancelled' ? 'failed' :
        'running'
      );

      if (data.message) {
        setLogs((prev) => [
          ...prev,
          { timestamp: new Date().toISOString(), message: data.message || '' },
        ]);
      }

      if (data.error) {
        setError(data.error);
        setLogs((prev) => [
          ...prev,
          { timestamp: new Date().toISOString(), message: `错误: ${data.error}` },
        ]);
      }
    } catch {
      // Ignore parse errors
    }
  }, []);

  const connect = useCallback(() => {
    // Clean up existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = new EventSource(`/api/proxy/deploy/worker/${taskId}/progress`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = handleSSEMessage;

    eventSource.onerror = () => {
      eventSource.close();

      // Don't reconnect if we've exceeded max attempts or terminal state
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
  }, [taskId, handleSSEMessage]);

  useEffect(() => {
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

  const isComplete = status === 'completed' || status === 'failed';

  return (
    <Dialog open onOpenChange={(open: boolean) => !open && onClose()}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {status === 'completed' && (
              <CheckCircle className="h-5 w-5 text-green-500" />
            )}
            {status === 'failed' && (
              <XCircle className="h-5 w-5 text-destructive" />
            )}
            {status === 'running' && (
              <Loader2 className="h-5 w-5 animate-spin" />
            )}
            部署进度
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Deployment Info */}
          <div className="text-sm">
            <p>
              正在部署 <span className="font-medium">{algorithmName}</span> 到{' '}
              <span className="font-medium">{hostId}</span>
            </p>
          </div>

          {/* Progress Bar */}
          <div className="space-y-2">
            <Progress value={progress} />
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">{currentStep}</span>
              <span className="font-medium">{progress}%</span>
            </div>
          </div>

          {/* Status */}
          <div className="flex items-center gap-2">
            <span className="text-sm">状态:</span>
            <span className={`text-sm font-medium capitalize ${
              status === 'completed' && 'text-green-500'
            } ${
              status === 'failed' && 'text-destructive'
            } ${
              status === 'running' && 'text-blue-500'
            }`}>
              {status === 'pending' && '等待中'}
              {status === 'running' && '部署中'}
              {status === 'completed' && '已完成'}
              {status === 'failed' && '失败'}
            </span>
          </div>

          {/* Logs */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium">部署日志</h4>
            <div className="max-h-[300px] overflow-y-auto rounded border bg-muted p-3 font-mono text-xs">
              {logs.map((log, i) => (
                <div key={i} className="text-muted-foreground">
                  [{new Date(log.timestamp).toLocaleTimeString('zh-CN')}] {log.message}
                </div>
              ))}
              {logs.length === 0 && (
                <p className="text-muted-foreground">等待日志...</p>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              {isComplete ? '关闭' : '取消'}
            </Button>
            {isComplete && status === 'completed' && (
              <Link href="/hosts">
                <Button>查看主机</Button>
              </Link>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
