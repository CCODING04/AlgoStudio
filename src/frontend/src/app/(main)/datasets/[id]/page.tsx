'use client';

import { useDataset, useRestoreDataset } from '@/hooks/use-datasets';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Loader2, ArrowLeft, RotateCcw, Database, FolderOpen, Clock, Hash, HardDrive } from 'lucide-react';
import Link from 'next/link';

export default function DatasetDetailPage() {
  const params = useParams();
  const router = useRouter();
  const datasetId = params.id as string;

  const { data: dataset, isLoading, error, refetch } = useDataset(datasetId);
  const restoreDataset = useRestoreDataset();

  const handleRestore = async () => {
    if (!dataset?.dataset_id) return;
    if (!window.confirm('确定要恢复此数据集吗？')) return;

    try {
      await restoreDataset.mutateAsync(dataset.dataset_id);
      refetch();
    } catch (err) {
      alert(err instanceof Error ? err.message : '恢复失败');
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !dataset) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">数据集详情</h1>
          <p className="text-muted-foreground">数据集不存在或加载失败</p>
        </div>
        <Card>
          <CardContent className="p-12 text-center">
            <p className="text-destructive">{error?.message || '数据集不存在'}</p>
            <Button variant="outline" className="mt-4" onClick={() => router.push('/datasets')}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              返回列表
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/datasets">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Database className="h-8 w-8" />
            {dataset.name}
          </h1>
          <p className="text-muted-foreground">{dataset.description || '无描述'}</p>
        </div>
        <div className="flex gap-2">
          {dataset.is_active ? (
            <Badge variant="success">活跃</Badge>
          ) : (
            <Badge variant="secondary">已删除</Badge>
          )}
        </div>
      </div>

      {/* Restore Button for soft-deleted datasets */}
      {!dataset.is_active && (
        <Card className="border-yellow-500/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-yellow-600">
                <RotateCcw className="h-4 w-4" />
                <span>此数据集已被删除，可以恢复</span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRestore}
                disabled={restoreDataset.isPending}
              >
                {restoreDataset.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RotateCcw className="mr-2 h-4 w-4" />
                )}
                恢复数据集
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Basic Info */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <FolderOpen className="h-4 w-4" />
              路径信息
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <p className="text-sm text-muted-foreground">数据集路径</p>
              <p className="font-mono text-sm">{dataset.path}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">存储类型</p>
              <Badge variant="outline">{dataset.storage_type}</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <HardDrive className="h-4 w-4" />
              统计信息
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">大小</span>
              <span className="font-medium">
                {dataset.size_gb !== null ? `${dataset.size_gb.toFixed(2)} GB` : '-'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">文件数量</span>
              <span className="font-medium">
                {dataset.file_count !== null ? dataset.file_count.toLocaleString() : '-'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">版本</span>
              <Badge variant="secondary">
                {dataset.version || '无版本'}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Clock className="h-4 w-4" />
              时间信息
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">创建时间</span>
              <span className="font-medium">
                {dataset.created_at
                  ? new Date(dataset.created_at).toLocaleString('zh-CN')
                  : '-'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">更新时间</span>
              <span className="font-medium">
                {dataset.updated_at
                  ? new Date(dataset.updated_at).toLocaleString('zh-CN')
                  : '-'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">最后访问</span>
              <span className="font-medium">
                {dataset.last_accessed_at
                  ? new Date(dataset.last_accessed_at).toLocaleString('zh-CN')
                  : '-'}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Hash className="h-4 w-4" />
              标识信息
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <p className="text-sm text-muted-foreground">数据集 ID</p>
              <p className="font-mono text-sm">{dataset.dataset_id}</p>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">公开访问</span>
              <Badge variant={dataset.is_public ? 'success' : 'secondary'}>
                {dataset.is_public ? '是' : '否'}
              </Badge>
            </div>
            {dataset.owner_id && (
              <div>
                <p className="text-sm text-muted-foreground">所有者</p>
                <p className="font-mono text-sm">{dataset.owner_id}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Tags */}
      {dataset.tags && dataset.tags.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">标签</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {dataset.tags.map((tag) => (
                <Badge key={tag} variant="outline">
                  {tag}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}