'use client';

import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useTask } from '@/hooks/use-tasks';
import { useTaskSSE } from '@/hooks/use-sse';
import { dispatchTask } from '@/lib/api';
import { Progress } from '@/components/ui/progress';
import {
  ArrowLeft,
  Clock,
  Server,
  AlertCircle,
  CheckCircle,
  XCircle,
  Loader2,
  Wifi,
  Play,
} from 'lucide-react';
import { useParams, useRouter } from 'next/navigation';
import { getStatusConfig, getTaskTypeLabel } from '@/lib/constants';
import { cn } from '@/lib/utils';

const statusIconMap: Record<string, typeof CheckCircle> = {
  pending: Clock,
  running: Loader2,
  completed: CheckCircle,
  failed: XCircle,
  cancelled: XCircle,
};

interface LogEntry {
  timestamp: Date;
  message: string;
}

export default function TaskDetailPage() {
  const params = useParams();
  const router = useRouter();
  const taskId = params.taskId as string;
  const { data: task, isLoading, error, refetch } = useTask(taskId);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [sseConnected, setSseConnected] = useState(false);
  const [isDispatching, setIsDispatching] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const handleDispatch = async () => {
    if (!task || isDispatching) return;
    setIsDispatching(true);
    try {
      await dispatchTask(task.task_id);
      // Refresh task data
      await refetch();
    } catch (err) {
      console.error('Failed to dispatch task:', err);
    } finally {
      setIsDispatching(false);
    }
  };

  // Track SSE connection
  useEffect(() => {
    if (!taskId) return;

    const eventSource = new EventSource(`/api/proxy/tasks/${taskId}/events`);

    eventSource.onopen = () => {
      setSseConnected(true);
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.task_id === taskId && data.description) {
          setLogs((prev) => [
            ...prev.slice(-49), // Keep last 50 entries
            { timestamp: new Date(), message: data.description },
          ]);
        }
        if (data.task_id === taskId && (data.progress !== undefined || data.status)) {
          setSseConnected(true);
        }
      } catch {
        // Ignore parse errors
      }
    };

    eventSource.onerror = () => {
      setSseConnected(false);
    };

    return () => {
      eventSource.close();
    };
  }, [taskId]);

  // Auto-scroll to latest log
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.push('/tasks')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-3xl font-bold">任务详情</h1>
        </div>
        <Card>
          <CardContent className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error || !task) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.push('/tasks')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-3xl font-bold">任务详情</h1>
        </div>
        <Card>
          <CardContent className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
            <AlertCircle className="h-5 w-5" />
            <span>任务不存在或加载失败</span>
          </CardContent>
        </Card>
      </div>
    );
  }

  const status = getStatusConfig(task.status);
  const StatusIcon = statusIconMap[task.status] || Clock;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.push('/tasks')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold">任务详情</h1>
            {(task.status === 'running' || task.status === 'pending') && (
              <div className="flex items-center gap-1.5">
                <div
                  className={cn(
                    'w-2 h-2 rounded-full transition-colors',
                    sseConnected ? 'bg-green-500 animate-pulse' : 'bg-muted'
                  )}
                />
                <span className="text-xs text-muted-foreground">
                  {sseConnected ? '实时同步' : '连接中...'}
                </span>
              </div>
            )}
          </div>
          <p className="text-muted-foreground font-mono text-sm">{task.task_id}</p>
        </div>
        <Badge variant={status.variant} className="text-sm px-3 py-1">
          <StatusIcon className="h-4 w-4 mr-1" />
          {status.label}
        </Badge>
      </div>

      {task.status === 'running' && task.progress !== null && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">进度</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">当前进度</span>
              <span className="font-medium">{task.progress}%</span>
            </div>
            <Progress value={task.progress} className="h-2" />
          </CardContent>
        </Card>
      )}

      {/* Real-time Logs */}
      {(task.status === 'running' || task.status === 'pending') && (
        <Card className="border-muted-foreground/20">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <Wifi className="h-4 w-4" />
                实时日志
              </CardTitle>
              <span className="text-xs text-muted-foreground">{logs.length} 条</span>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="bg-black/90 rounded-b-lg max-h-[300px] overflow-y-auto font-mono text-sm">
              {logs.length === 0 ? (
                <div className="p-4 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin inline mr-2" />
                  等待日志输出...
                </div>
              ) : (
                <div className="p-3 space-y-1">
                  {logs.map((log, i) => (
                    <div key={i} className="flex gap-3 text-green-400">
                      <span className="text-muted-foreground text-xs shrink-0">
                        {log.timestamp.toLocaleTimeString('zh-CN', {
                          hour12: false,
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </span>
                      <span>{log.message}</span>
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">基本信息</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">任务类型</p>
                <p className="font-medium">{getTaskTypeLabel(task.task_type)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">算法</p>
                <p className="font-medium">
                  {task.algorithm_name} {task.algorithm_version}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">创建时间</p>
                <p className="font-medium">
                  {task.created_at ? new Date(task.created_at).toLocaleString('zh-CN') : '-'}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">开始时间</p>
                <p className="font-medium">
                  {task.started_at ? new Date(task.started_at).toLocaleString('zh-CN') : '-'}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">完成时间</p>
                <p className="font-medium">
                  {task.completed_at ? new Date(task.completed_at).toLocaleString('zh-CN') : '-'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">执行信息</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Server className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">分配节点</p>
                  <p className="font-medium">{task.assigned_node || '未分配'}</p>
                </div>
              </div>
              {task.status === 'pending' && (
                <Button
                  size="sm"
                  onClick={handleDispatch}
                  disabled={isDispatching}
                >
                  {isDispatching ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                      分发中...
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-1" />
                      立即分发
                    </>
                  )}
                </Button>
              )}
            </div>
            {task.status === 'pending' && !task.assigned_node && (
              <p className="text-xs text-muted-foreground">
                任务等待调度中。点击"立即分发"手动分配到可用节点。
              </p>
            )}
            {task.error && (
              <div className="flex items-start gap-3 p-3 rounded-lg bg-destructive/10">
                <AlertCircle className="h-5 w-5 text-destructive mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-destructive">错误信息</p>
                  <p className="text-sm text-destructive/80 mt-1">{task.error}</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
