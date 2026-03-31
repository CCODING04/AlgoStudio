'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useTasks } from '@/hooks/use-tasks';
import { ListTodo, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { getStatusConfig, getTaskTypeLabel } from '@/lib/constants';

export function RecentTasks() {
  const { data: tasks, isLoading } = useTasks();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ListTodo className="h-5 w-5" />
            最近任务
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">加载中...</p>
        </CardContent>
      </Card>
    );
  }

  const recentTasks = tasks?.slice(0, 5) || [];

  if (recentTasks.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ListTodo className="h-5 w-5" />
            最近任务
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">暂无任务记录</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <ListTodo className="h-5 w-5" />
          最近任务
        </CardTitle>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/tasks">
            查看全部 <ExternalLink className="ml-1 h-3 w-3" />
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {recentTasks.map((task) => {
            const status = getStatusConfig(task.status);
            return (
              <Link
                key={task.task_id}
                href={`/tasks/${task.task_id}`}
                className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">
                      {getTaskTypeLabel(task.task_type)}
                    </span>
                    <Badge variant={status.variant} className="text-xs">
                      {status.label}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {task.algorithm_name} {task.algorithm_version}
                  </p>
                </div>
                {task.progress !== null && (
                  <div className="text-sm font-medium">{task.progress}%</div>
                )}
              </Link>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
