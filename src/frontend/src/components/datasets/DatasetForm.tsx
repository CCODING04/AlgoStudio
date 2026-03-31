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
import { Loader2, Database, Sparkles, FolderOpen } from 'lucide-react';
import { DatasetBrowser } from './DatasetBrowser';

interface DatasetFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  dataset?: DatasetResponse | null;
  onSuccess: () => void;
  onUpdate: (id: string, data: { name?: string; path?: string }) => Promise<void>;
}

// Common dataset presets for quick selection
const DATASET_PRESETS = [
  { name: 'CIFAR-10', path: '/mnt/VtrixDataset/data/cifar10', description: 'CIFAR-10 图像分类数据集' },
  { name: 'COCO', path: '/mnt/VtrixDataset/data/coco', description: 'COCO 目标检测数据集' },
  { name: 'ImageNet', path: '/mnt/VtrixDataset/data/imagenet', description: 'ImageNet 分类数据集' },
  { name: 'MNIST', path: '/mnt/VtrixDataset/data/mnist', description: 'MNIST 手写数字数据集' },
];

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
  const [showBrowseDialog, setShowBrowseDialog] = useState(false);

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
            <div className="flex gap-2">
              <Input
                id="path"
                type="text"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                placeholder="/mnt/VtrixDataset/data/train"
                disabled={loading}
                className="flex-1"
              />
              {!isEditing && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowBrowseDialog(true)}
                  disabled={loading}
                  title="浏览服务器目录"
                >
                  <FolderOpen className="h-4 w-4" />
                </Button>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              数据集应通过 NFS/RSYNC 等方式预先放置到此路径
            </p>
          </div>

          {/* Quick Presets */}
          {!isEditing && (
            <div className="space-y-2">
              <Label className="flex items-center gap-1.5">
                <Sparkles className="h-3 w-3" />
                快速选择
              </Label>
              <div className="flex flex-wrap gap-2">
                {DATASET_PRESETS.map((preset) => (
                  <Button
                    key={preset.path}
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setName(preset.name);
                      setPath(preset.path);
                    }}
                    disabled={loading}
                    title={preset.description}
                  >
                    {preset.name}
                  </Button>
                ))}
              </div>
            </div>
          )}

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
              data-testid="cancel-button"
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

      {/* Browse Server Dialog */}
      <Dialog open={showBrowseDialog} onOpenChange={setShowBrowseDialog}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>浏览服务器目录</DialogTitle>
            <DialogDescription>
              选择服务器上的数据集目录
            </DialogDescription>
          </DialogHeader>
          <DatasetBrowser
            currentPath={path || '/mnt/VtrixDataset/data/'}
            onSelect={(selectedPath) => {
              setPath(selectedPath);
              setShowBrowseDialog(false);
            }}
          />
        </DialogContent>
      </Dialog>
    </Dialog>
  );
}
