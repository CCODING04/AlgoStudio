'use client';

import { Badge } from '@/components/ui/badge';

interface HostStatusProps {
  status: 'online' | 'offline' | 'idle' | 'busy' | 'error';
  lastSeen?: string;
}

export function HostStatus({ status, lastSeen }: HostStatusProps) {
  const statusConfig = {
    online: { label: '在线', variant: 'success' as const },
    offline: { label: '离线', variant: 'secondary' as const },
    idle: { label: '空闲', variant: 'success' as const },
    busy: { label: '忙碌', variant: 'warning' as const },
    error: { label: '错误', variant: 'destructive' as const },
  };

  const config = statusConfig[status] || statusConfig.offline;

  return (
    <div className="flex items-center gap-2">
      <Badge variant={config.variant}>{config.label}</Badge>
      {lastSeen && status === 'offline' && (
        <span className="text-xs text-muted-foreground">
          最后在线: {new Date(lastSeen).toLocaleString('zh-CN')}
        </span>
      )}
    </div>
  );
}
