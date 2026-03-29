'use client';

import { StatsCard } from '@/components/dashboard/stats-card';
import { ClusterStatus } from '@/components/dashboard/cluster-status';
import { ResourceChart } from '@/components/dashboard/resource-chart';
import { RecentTasks } from '@/components/dashboard/recent-tasks';
import { useTasks } from '@/hooks/use-tasks';
import { Activity, CheckCircle, Clock, XCircle } from 'lucide-react';

export default async function DashboardPage() {
  // Stats will be calculated client-side with useTasks
  return (
    <DashboardContent />
  );
}

function DashboardContent() {
  const { data: tasks } = useTasks();

  const stats = {
    total: tasks?.length || 0,
    running: tasks?.filter((t) => t.status === 'running').length || 0,
    pending: tasks?.filter((t) => t.status === 'pending').length || 0,
    failed: tasks?.filter((t) => t.status === 'failed').length || 0,
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">AI 算法平台概览</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <div data-testid="stat-card-total"><StatsCard title="任务总数" value={stats.total} icon={Activity} /></div>
        <div data-testid="stat-card-running"><StatsCard title="运行中" value={stats.running} variant="primary" icon={CheckCircle} /></div>
        <div data-testid="stat-card-pending"><StatsCard title="待处理" value={stats.pending} variant="secondary" icon={Clock} /></div>
        <div data-testid="stat-card-failed"><StatsCard title="失败" value={stats.failed} variant="destructive" icon={XCircle} /></div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ClusterStatus />
        <ResourceChart />
      </div>

      <RecentTasks />
    </div>
  );
}
