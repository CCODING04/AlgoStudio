'use client';

import { useState } from 'react';
import { DatasetResponse } from '@/types/dataset';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Loader2, Database } from 'lucide-react';

interface DatasetFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  dataset?: DatasetResponse | null;
  onSuccess: () => void;
  onUpdate: (id: string, data: { name?: string; path?: string }) => Promise<void>;
}

export function DatasetForm({
  open,
  onOpenChange,
  dataset,
  onSuccess,
  onUpdate,
}: DatasetFormProps) {
  const [name, setName] = useState(dataset?.name || '');
  const [path, setPath] = useState(dataset?.path || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEditing = !!dataset?.dataset_id;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError('请输入数据集名称');
      return;
    }

    if (!path.trim()) {
      setError('请输入数据集路径');
      return;
    }

    setLoading(true);

    try {
      if (isEditing && dataset?.dataset_id) {
        await onUpdate(dataset.dataset_id, { name, path });
      } else {
        const res = await fetch('/api/proxy/datasets', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, path }),
        });

        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.error || '创建数据集失败');
        }
      }

      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败');
    } finally {
      setLoading(false);
    }
  };

  // Reset form when dataset changes or dialog opens/closes
  const handleOpenChange = (open: boolean) => {
    if (!open) {
      setName('');
      setPath('');
      setError(null);
    }
    onOpenChange(open);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            {isEditing ? '编辑数据集' : '创建数据集'}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? '修改数据集信息'
              : '注册一个新的数据集路径到系统中'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">数据集名称</Label>
            <Input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如: CIFAR-10 Training Set"
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="path">数据集路径</Label>
            <Input
              id="path"
              type="text"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/mnt/VtrixDataset/data/train"
              disabled={loading}
            />
            <p className="text-xs text-muted-foreground">
              数据集应通过 NFS/RSYNC 等方式预先放置到此路径
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="size_gb">大小 (GB) - 可选</Label>
            <Input
              id="size_gb"
              type="number"
              step="0.01"
              placeholder="例如: 10.5"
              disabled={loading}
              className="opacity-50"
            />
            <p className="text-xs text-muted-foreground">
              后端会自动计算数据集大小
            </p>
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={loading}
            >
              取消
            </Button>
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {isEditing ? '保存' : '创建'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
