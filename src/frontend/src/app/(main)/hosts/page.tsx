'use client';

import { useHosts } from '@/hooks/use-hosts';
import { HostCard } from '@/components/hosts/HostCard';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RefreshCw, Search } from 'lucide-react';
import { useState } from 'react';
import { Input } from '@/components/ui/input';

export default function HostsPage() {
  const { data: hostsData, isLoading, refetch, isFetching } = useHosts();
  const [searchQuery, setSearchQuery] = useState('');

  const hosts = hostsData?.cluster_nodes || [];
  const onlineCount = hosts.filter((h) => h.status === 'online').length;
  const offlineCount = hosts.filter((h) => h.status === 'offline').length;

  const filteredHosts = hosts.filter((host) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      host.ip.toLowerCase().includes(query) ||
      host.hostname.toLowerCase().includes(query)
    );
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold">主机监控</h1>
        <p className="text-muted-foreground">Ray 集群节点状态</p>
      </div>

      {/* Status Summary */}
      <div className="flex gap-4">
        <Badge variant="success" className="text-base px-4 py-2">
          {onlineCount} 在线
        </Badge>
        <Badge variant="secondary" className="text-base px-4 py-2">
          {offlineCount} 离线
        </Badge>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardContent className="flex items-center gap-4 p-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="搜索 IP 地址或主机名..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
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

      {/* Host Grid */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-6">
                <div className="h-32 bg-muted rounded" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : filteredHosts.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <p className="text-muted-foreground">
              {searchQuery ? '未找到匹配的主机' : '暂无节点连接'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredHosts.map((host) => (
            <HostCard key={host.node_id} host={host} />
          ))}
        </div>
      )}
    </div>
  );
}
