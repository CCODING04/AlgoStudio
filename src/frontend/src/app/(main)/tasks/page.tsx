'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useTasks } from '@/hooks/use-tasks';
import { TaskWizard } from '@/components/tasks/TaskWizard';
import { Plus, Search, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';
import Link from 'next/link';

const statusConfig: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'success' }> = {
  pending: { label: '待处理', variant: 'secondary' },
  running: { label: '运行中', variant: 'default' },
  completed: { label: '已完成', variant: 'success' },
  failed: { label: '失败', variant: 'destructive' },
  cancelled: { label: '已取消', variant: 'destructive' },
};

const taskTypeLabels: Record<string, string> = {
  train: '训练',
  infer: '推理',
  verify: '验证',
};

const PAGE_SIZE = 10;

export default function TasksPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showTaskWizard, setShowTaskWizard] = useState(false);

  const { data: tasks, isLoading, refetch, isFetching } = useTasks(statusFilter || undefined);

  const filteredTasks = tasks?.filter((task) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      task.task_id.toLowerCase().includes(query) ||
      task.algorithm_name.toLowerCase().includes(query)
    );
  }) || [];

  const totalPages = Math.ceil(filteredTasks.length / PAGE_SIZE);
  const paginatedTasks = filteredTasks.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">任务列表</h1>
          <p className="text-muted-foreground">管理训练、推理和验证任务</p>
        </div>
        <Button onClick={() => setShowTaskWizard(true)}>
          <Plus className="mr-2 h-4 w-4" />
          新建任务
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">筛选</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="搜索任务 ID 或算法名称..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setPage(1);
                }}
                className="pl-9"
              />
            </div>
          </div>
          <Select
            value={statusFilter}
            onValueChange={(value) => {
              setStatusFilter(value === 'all' ? '' : value);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="任务状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="pending">待处理</SelectItem>
              <SelectItem value="running">运行中</SelectItem>
              <SelectItem value="completed">已完成</SelectItem>
              <SelectItem value="failed">失败</SelectItem>
              <SelectItem value="cancelled">已取消</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="icon"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>任务ID</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>算法</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>进度</TableHead>
                <TableHead>节点</TableHead>
                <TableHead>创建时间</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8">
                    加载中...
                  </TableCell>
                </TableRow>
              ) : paginatedTasks.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8">
                    暂无任务记录
                  </TableCell>
                </TableRow>
              ) : (
                paginatedTasks.map((task) => {
                  const status = statusConfig[task.status] || statusConfig.pending;
                  return (
                    <TableRow key={task.task_id} className="cursor-pointer hover:bg-muted/50">
                      <TableCell>
                        <Link
                          href={`/tasks/${task.task_id}`}
                          className="font-medium hover:underline"
                        >
                          {task.task_id}
                        </Link>
                      </TableCell>
                      <TableCell>{taskTypeLabels[task.task_type] || task.task_type}</TableCell>
                      <TableCell>
                        <div>
                          <div>{task.algorithm_name}</div>
                          <div className="text-xs text-muted-foreground">{task.algorithm_version}</div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={status.variant}>{status.label}</Badge>
                      </TableCell>
                      <TableCell>
                        {task.progress !== null ? `${task.progress}%` : '-'}
                      </TableCell>
                      <TableCell>{task.assigned_node || '-'}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(task.created_at).toLocaleString('zh-CN')}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground">
            第 {page} / {totalPages} 页
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}

      <TaskWizard
        open={showTaskWizard}
        onOpenChange={setShowTaskWizard}
        onSuccess={() => refetch()}
      />
    </div>
  );
}
