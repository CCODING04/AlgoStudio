'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useHosts } from '@/hooks/use-hosts';
import { Cpu, HardDrive } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface NodeResource {
  name: string;
  gpu: number;
  memory: number;
}

export function ResourceChart() {
  const { data, isLoading } = useHosts();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cpu className="h-5 w-5" />
            资源使用
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">加载中...</p>
        </CardContent>
      </Card>
    );
  }

  if (!data?.cluster_nodes || data.cluster_nodes.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cpu className="h-5 w-5" />
            资源使用
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">暂无节点数据</p>
        </CardContent>
      </Card>
    );
  }

  // Treat 'online' and 'idle' as active states (Ray cluster states)
  const chartData: NodeResource[] = data.cluster_nodes
    .filter((node) => (node.status === 'online' || node.status === 'idle') && node.resources?.gpu?.utilization !== undefined)
    .map((node) => ({
      name: node.hostname || node.ip,
      gpu: node.resources?.gpu?.utilization || 0,
      memory: 0, // GPU memory calculation not straightforward with string format
    }));

  if (chartData.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cpu className="h-5 w-5" />
            资源使用
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">暂无GPU数据</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Cpu className="h-5 w-5" />
          GPU 使用率
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical">
              <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
              <YAxis type="category" dataKey="name" width={80} tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value) => [`${value}%`, 'GPU 使用率']}
                contentStyle={{ fontSize: 12 }}
              />
              <Bar dataKey="gpu" radius={[0, 4, 4, 0]}>
                {chartData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.gpu > 80 ? '#ef4444' : entry.gpu > 50 ? '#f59e0b' : '#22c55e'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 flex items-center justify-center gap-4 text-xs">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-green-500" />
            <span>低 (&lt;50%)</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-amber-500" />
            <span>中 (50-80%)</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-red-500" />
            <span>高 (&gt;80%)</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
