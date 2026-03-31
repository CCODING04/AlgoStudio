'use client';

import { useState } from 'react';
import { useBrowseDatasets } from '@/hooks/use-datasets';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { Loader2, FolderOpen, RefreshCw } from 'lucide-react';

interface DatasetBrowserProps {
  onSelect: (path: string) => void;
  currentPath?: string;
}

const PRESET_PATHS = [
  '/mnt/VtrixDataset/data/',
  '/mnt/VtrixDataset/',
  '/data/',
  '/datasets/',
];

export function DatasetBrowser({ onSelect, currentPath = '/mnt/VtrixDataset/data/' }: DatasetBrowserProps) {
  const [path, setPath] = useState(currentPath);
  const [inputPath, setInputPath] = useState(currentPath);
  const { data, isLoading, error, refetch } = useBrowseDatasets(path);

  const handlePathChange = (newPath: string) => {
    setInputPath(newPath);
  };

  const handleBrowse = () => {
    setPath(inputPath);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleBrowse();
    }
  };

  const handleFolderClick = (folder: string) => {
    // If current path ends with /, append folder; otherwise append /folder
    const newPath = path.endsWith('/') ? `${path}${folder}/` : `${path}/${folder}/`;
    setPath(newPath);
    setInputPath(newPath);
  };

  const handleGoUp = () => {
    // Go up one directory
    const parts = path.split('/').filter(Boolean);
    if (parts.length > 1) {
      parts.pop();
      const newPath = '/' + parts.join('/') + '/';
      setPath(newPath);
      setInputPath(newPath);
    }
  };

  const handleSelect = () => {
    // Use the current path (without trailing /) for the dataset path
    const selectedPath = path.replace(/\/$/, '');
    onSelect(selectedPath);
  };

  return (
    <div className="space-y-4">
      {/* Path Input */}
      <div className="space-y-2">
        <Label htmlFor="browse-path">浏览路径</Label>
        <div className="flex gap-2">
          <Input
            id="browse-path"
            value={inputPath}
            onChange={(e) => handlePathChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="/mnt/VtrixDataset/data/"
          />
          <Button onClick={handleBrowse} disabled={isLoading}>
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : '浏览'}
          </Button>
          <Button variant="outline" onClick={handleGoUp} disabled={isLoading || path === '/'}>
            返回
          </Button>
        </div>
      </div>

      {/* Preset Paths */}
      <div className="space-y-2">
        <Label>快捷路径</Label>
        <div className="flex flex-wrap gap-2">
          {PRESET_PATHS.map((preset) => (
            <Button
              key={preset}
              variant="outline"
              size="sm"
              onClick={() => {
                setPath(preset);
                setInputPath(preset);
              }}
              disabled={isLoading}
            >
              {preset}
            </Button>
          ))}
        </div>
      </div>

      {/* Folder List */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>文件夹 {data?.exists && `(${data.folders.length})`}</Label>
          <Button variant="ghost" size="sm" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="text-sm text-destructive">{error.message}</div>
        ) : !data?.exists ? (
          <div className="text-sm text-muted-foreground">
            路径不存在或无法访问
          </div>
        ) : data.folders.length === 0 ? (
          <div className="text-sm text-muted-foreground">
            目录为空
          </div>
        ) : (
          <div className="max-h-[200px] overflow-y-auto border rounded-md">
            {data.folders.map((folder) => (
              <button
                key={folder}
                type="button"
                onClick={() => handleFolderClick(folder)}
                className="w-full text-left px-3 py-2 hover:bg-muted flex items-center gap-2 border-b last:border-b-0"
              >
                <FolderOpen className="h-4 w-4 text-muted-foreground" />
                <span>{folder}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Current Selection */}
      {data?.exists && (
        <div className="p-3 bg-muted rounded-md">
          <p className="text-sm">
            <span className="font-medium">当前路径:</span>{' '}
            <code className="text-xs">{path}</code>
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-end gap-2">
        <Button onClick={handleSelect} disabled={!data?.exists}>
          选择此目录
        </Button>
      </div>
    </div>
  );
}
