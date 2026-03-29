'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ResourceBar } from './ResourceBar';
import { Play, Cpu } from 'lucide-react';
import Link from 'next/link';

// Host info structure matching FastAPI /api/hosts response
export interface HostResource {
  cpu: {
    total: number;
    used: number;
    physical_cores?: number;
    model?: string;
    freq_mhz?: number;
  };
  gpu: {
    total: number;
    utilization: number;
    memory_used: string;
    memory_total: string;
    name?: string;
  };
  memory: {
    total: string;
    used: string;
  };
  disk?: {
    total: string;
    used: string;
  };
  swap?: {
    total: string;
    used: string;
  };
}

export interface HostInfo {
  node_id: string;
  ip: string;
  status: 'online' | 'offline';
  is_local: boolean;
  hostname: string;
  resources: HostResource;
}

interface HostCardProps {
  host: HostInfo;
}

function parseMemoryString(memStr: string): { used: number; total: number } {
  // Parse strings like "16.5Gi" or "16Gi" to numbers
  const match = memStr.match(/^([\d.]+)(Gi|G)$/);
  if (match) {
    return { used: parseFloat(match[1]), total: parseFloat(match[1]) };
  }
  return { used: 0, total: 0 };
}

export function HostCard({ host }: HostCardProps) {
  const statusConfig = {
    online: { label: '在线', variant: 'success' as const },
    offline: { label: '离线', variant: 'secondary' as const },
  };

  const status = statusConfig[host.status] || statusConfig.offline;
  const gpuInfo = host.resources?.gpu;
  const memInfo = host.resources?.memory;

  // Parse GPU memory strings like "16.5Gi"
  const gpuMem = gpuInfo ? parseMemoryString(gpuInfo.memory_used) : { used: 0, total: 0 };
  const gpuMemTotal = gpuInfo ? parseMemoryString(gpuInfo.memory_total) : { used: 0, total: 0 };

  // Parse system memory strings
  const sysMem = memInfo ? parseMemoryString(memInfo.used) : { used: 0, total: 0 };
  const sysMemTotal = memInfo ? parseMemoryString(memInfo.total) : { used: 0, total: 0 };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-lg font-medium flex items-center gap-2">
          {gpuInfo?.name ? (
            <>
              <Cpu className="h-4 w-4" />
              {gpuInfo.name}
            </>
          ) : (
            '无 GPU'
          )}
        </CardTitle>
        <Badge variant={status.variant}>{status.label}</Badge>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Host Info */}
        <div className="text-sm text-muted-foreground space-y-1">
          <p className="font-mono">{host.ip}</p>
          <p>{host.hostname}</p>
          {host.is_local && (
            <Badge variant="outline" className="text-xs">本地节点</Badge>
          )}
        </div>

        {/* GPU Section */}
        {gpuInfo && gpuInfo.total > 0 && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>GPU 利用率</span>
              <span className="font-medium">{gpuInfo.utilization}%</span>
            </div>
            <div className="h-2 w-full rounded-full bg-secondary overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{ width: `${gpuInfo.utilization}%` }}
              />
            </div>

            <ResourceBar
              label="GPU 内存"
              used={gpuMem.used}
              total={gpuMemTotal.used}
              unit="Gi"
            />
          </div>
        )}

        {/* RAM Section */}
        {memInfo && (
          <ResourceBar
            label="内存"
            used={sysMem.used}
            total={sysMemTotal.used}
            unit="Gi"
          />
        )}

        {/* CPU Cores */}
        {host.resources?.cpu && (
          <div className="flex justify-between text-sm">
            <span>CPU 核心</span>
            <span className="font-medium">
              {host.resources.cpu.physical_cores || host.resources.cpu.total}
            </span>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2 pt-2">
          <Link href={`/deploy?host=${host.node_id}`} className="flex-1">
            <Button variant="outline" className="w-full">
              <Play className="mr-2 h-4 w-4" />
              部署
            </Button>
          </Link>
          <Link href={`/hosts/${host.node_id}`} className="flex-1">
            <Button variant="outline" className="w-full">
              详情
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
