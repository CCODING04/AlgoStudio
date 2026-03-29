'use client';

import { useParams } from 'next/navigation';
import { useHosts } from '@/hooks/use-hosts';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function HostDetailPage() {
  const params = useParams();
  const nodeId = params.nodeId as string;
  const { data: hostsData, isLoading, error } = useHosts();

  const host = hostsData?.cluster_nodes?.find((n) => n.node_id === nodeId);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">加载中...</h1>
          <p className="text-muted-foreground">Node ID: {nodeId}</p>
        </div>
      </div>
    );
  }

  if (error || !host) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">节点详情</h1>
          <p className="text-muted-foreground">Node ID: {nodeId}</p>
        </div>
        <Card>
          <CardContent className="py-8">
            <p className="text-center text-muted-foreground">无法加载节点详情</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold">{host.hostname || '未知主机'}</h1>
          <Badge variant={host.status === 'online' ? 'success' : 'destructive'}>
            {host.status === 'online' ? '在线' : '离线'}
          </Badge>
          {host.is_local && <Badge variant="outline">Head 节点</Badge>}
        </div>
        <p className="text-muted-foreground">Node ID: {host.node_id}</p>
        <p className="text-muted-foreground">IP: {host.ip}</p>
      </div>

      {/* CPU Info */}
      <Card>
        <CardHeader>
          <CardTitle>CPU</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex justify-between">
            <span className="text-sm">型号:</span>
            <span className="text-sm font-medium">{host.resources?.cpu?.model || '未知'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sm">物理核心:</span>
            <span className="text-sm font-medium">{host.resources?.cpu?.physical_cores || '未知'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sm">使用率:</span>
            <span className="text-sm font-medium">{host.resources?.cpu?.used || 0}%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sm">频率:</span>
            <span className="text-sm font-medium">{host.resources?.cpu?.freq_mhz ? `${host.resources.cpu.freq_mhz} MHz` : '未知'}</span>
          </div>
        </CardContent>
      </Card>

      {/* GPU Info */}
      <Card>
        <CardHeader>
          <CardTitle>GPU</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex justify-between">
            <span className="text-sm">型号:</span>
            <span className="text-sm font-medium">{host.resources?.gpu?.name || '无 GPU'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sm">数量:</span>
            <span className="text-sm font-medium">{host.resources?.gpu?.total || 0}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sm">使用率:</span>
            <span className="text-sm font-medium">{host.resources?.gpu?.utilization || 0}%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sm">内存:</span>
            <span className="text-sm font-medium">
              {host.resources?.gpu?.memory_used || '0Gi'} / {host.resources?.gpu?.memory_total || '0Gi'}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Memory Info */}
      <Card>
        <CardHeader>
          <CardTitle>内存</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex justify-between">
            <span className="text-sm">已用:</span>
            <span className="text-sm font-medium">{host.resources?.memory?.used || '未知'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sm">总量:</span>
            <span className="text-sm font-medium">{host.resources?.memory?.total || '未知'}</span>
          </div>
        </CardContent>
      </Card>

      {/* Disk Info */}
      {host.resources?.disk && (
        <Card>
          <CardHeader>
            <CardTitle>磁盘</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm">已用:</span>
              <span className="text-sm font-medium">{host.resources.disk.used}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm">总量:</span>
              <span className="text-sm font-medium">{host.resources.disk.total}</span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
