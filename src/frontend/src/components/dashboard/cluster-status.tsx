'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useHosts } from '@/hooks/use-hosts';
import { Server, Cpu } from 'lucide-react';

export function ClusterStatus() {
  const { data, isLoading, error } = useHosts();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5" />
            集群状态
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">加载中...</p>
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5" />
            集群状态
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">暂无节点连接</p>
        </CardContent>
      </Card>
    );
  }

  const clusterNodes = data.cluster_nodes || [];
  const totalNodes = clusterNodes.length;
  // Treat 'online' and 'idle' as active states (Ray cluster states)
  const onlineNodes = clusterNodes.filter((n) => n.status === 'online' || n.status === 'idle').length;
  const offlineNodes = totalNodes - onlineNodes;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Server className="h-5 w-5" />
          集群状态
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">总节点数</span>
          <Badge variant="secondary">{totalNodes}</Badge>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">在线节点</span>
          <Badge variant="success">{onlineNodes}</Badge>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">离线节点</span>
          <Badge variant="destructive">{offlineNodes}</Badge>
        </div>

        {clusterNodes.length > 0 && (
          <div className="mt-4 pt-4 border-t">
            <p className="text-sm font-medium mb-2">节点列表</p>
            <div className="space-y-2">
              {clusterNodes.map((node) => (
                <div key={node.node_id} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${node.status === 'online' || node.status === 'idle' ? 'bg-green-500' : 'bg-red-500'}`} />
                    <span>{node.hostname || node.ip}</span>
                  </div>
                  {node.resources?.gpu?.utilization !== undefined && (
                    <div className="flex items-center gap-1 text-muted-foreground">
                      <Cpu className="h-3 w-3" />
                      <span>{node.resources.gpu.utilization}%</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
