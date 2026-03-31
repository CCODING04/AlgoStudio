'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useTask } from '@/hooks/use-tasks';
import { useTaskSSE } from '@/hooks/use-sse';
import { Progress } from '@/components/ui/progress';
import {
  ArrowLeft,
  Clock,
  Server,
  Cpu,
  AlertCircle,
  CheckCircle,
  XCircle,
  Loader2,
} from 'lucide-react';
import { useParams, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';

const statusConfig: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'success'; icon: typeof CheckCircle }> = {
  pending: { label: '待处理', variant: 'secondary', icon: Clock },
  running: { label: '运行中', variant: 'default', icon: Loader2 },
  completed: { label: '已完成', variant: 'success', icon: CheckCircle },
  failed: { label: '失败', variant: 'destructive', icon: XCircle },
  cancelled: { label: '已取消', variant: 'destructive', icon: XCircle },
};

const taskTypeLabels: Record<string, string> = {
  train: '训练',
  infer: '推理',
  verify: '验证',
};

export default function TaskDetailPage() {
  const params = useParams();
  const router = useRouter();
  const taskId = params.taskId as string;
  const { data: task, isLoading, error } = useTask(taskId);

  useTaskSSE(taskId);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push('/tasks')}
            className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 hover:bg-accent hover:text-accent-foreground h-10 w-10"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
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
          <button
            onClick={() => router.push('/tasks')}
            className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 hover:bg-accent hover:text-accent-foreground h-10 w-10"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
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

  const status = statusConfig[task.status] || statusConfig.pending;
  const StatusIcon = status.icon;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button
            onClick={() => router.push('/tasks')}
            className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 hover:bg-accent hover:text-accent-foreground h-10 w-10"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
        <div className="flex-1">
          <h1 className="text-3xl font-bold">任务详情</h1>
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

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">基本信息</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">任务类型</p>
                <p className="font-medium">{taskTypeLabels[task.task_type] || task.task_type}</p>
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
            <div className="flex items-center gap-3">
              <Server className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">分配节点</p>
                <p className="font-medium">{task.assigned_node || '未分配'}</p>
              </div>
            </div>
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
