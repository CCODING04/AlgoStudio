'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useHosts } from '@/hooks/use-hosts';
import { Cpu, HardDrive } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface NodeResource {
  name: string;
  displayName: string;
  gpu: number;
  gpuMemory: number;
}

/**
 * Parse memory string like "16.5Gi" or "8G" to a number in Gi.
 */
function parseMemoryToGi(memStr: string): number {
  if (!memStr) return 0;
  const match = memStr.match(/^([\d.]+)(Gi|G)$/i);
  if (match) {
    return parseFloat(match[1]);
  }
  return 0;
}

/**
 * Truncate long hostname for display.
 */
function truncateName(name: string, maxLen: number = 20): string {
  if (name.length <= maxLen) return name;
  return name.slice(0, maxLen - 2) + '...';
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
    .map((node) => {
      const gpuUsed = parseMemoryToGi(node.resources.gpu.memory_used);
      const gpuTotal = parseMemoryToGi(node.resources.gpu.memory_total);
      const gpuMemoryPct = gpuTotal > 0 ? Math.round((gpuUsed / gpuTotal) * 100) : 0;
      const rawName = node.hostname || node.ip;
      return {
        name: truncateName(rawName, 16),
        displayName: rawName,
        gpu: node.resources?.gpu?.utilization || 0,
        gpuMemory: gpuMemoryPct,
      };
    });

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
          GPU 资源使用
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" barCategoryGap="30%">
              <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
              <YAxis type="category" dataKey="name" width={80} tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value, name) => {
                  if (name === 'gpu') return [`${value}%`, 'GPU 使用率'];
                  if (name === 'gpuMemory') return [`${value}%`, 'GPU 内存占用率'];
                  return [`${value}%`, String(name)];
                }}
                labelFormatter={(label) => {
                  const entry = chartData.find((d) => d.name === label);
                  return entry?.displayName || label;
                }}
                contentStyle={{ fontSize: 12 }}
              />
              <Bar dataKey="gpu" name="gpu" radius={[0, 4, 4, 0]} maxBarSize={20}>
                {chartData.map((entry, index) => (
                  <Cell
                    key={`cell-gpu-${index}`}
                    fill={entry.gpu > 80 ? '#ef4444' : entry.gpu > 50 ? '#f59e0b' : '#22c55e'}
                  />
                ))}
              </Bar>
              <Bar dataKey="gpuMemory" name="gpuMemory" radius={[0, 4, 4, 0]} maxBarSize={20} fill="#6366f1" fillOpacity={0.6}>
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 flex items-center justify-center gap-6 text-xs">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-green-500" />
            <span>GPU 利用率低 (&lt;50%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-amber-500" />
            <span>GPU 利用率中 (50-80%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-red-500" />
            <span>GPU 利用率高 (&gt;80%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-indigo-500" />
            <span>GPU 内存</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
