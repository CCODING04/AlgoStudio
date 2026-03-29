'use client';

import { useState } from 'react';
import { useDatasets } from '@/hooks/use-datasets';
import { DatasetResponse } from '@/types/dataset';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent } from '@/components/ui/card';
import { Loader2, Database, Search, ChevronRight, FolderOpen } from 'lucide-react';

interface DatasetSelectorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  filterStorageType?: string;
}

export function DatasetSelector({
  value,
  onChange,
  placeholder = '选择数据集或手动输入路径',
  filterStorageType,
}: DatasetSelectorProps) {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [manualInput, setManualInput] = useState(false);
  const [manualPath, setManualPath] = useState('');

  const { data: datasets, isLoading } = useDatasets();

  // Filter datasets by storage type if specified
  const filteredDatasets = (datasets || []).filter((dataset) => {
    if (filterStorageType && dataset.storage_type !== filterStorageType) {
      return false;
    }
    if (searchQuery) {
      return dataset.name.toLowerCase().includes(searchQuery.toLowerCase());
    }
    return true;
  });

  const selectedDataset = (datasets || []).find((d) => d.path === value);

  const handleSelectDataset = (dataset: DatasetResponse) => {
    onChange(dataset.path);
    setOpen(false);
    setSearchQuery('');
  };

  const handleManualPathConfirm = () => {
    if (manualPath.trim()) {
      onChange(manualPath.trim());
    }
    setManualInput(false);
    setOpen(false);
    setSearchQuery('');
  };

  const handleOpenChange = (newOpen: boolean) => {
    setOpen(newOpen);
    if (!newOpen) {
      setSearchQuery('');
      setManualInput(false);
      setManualPath('');
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Select value={selectedDataset ? 'dataset' : 'manual'} onValueChange={(v) => {
          if (v === 'manual') {
            setManualInput(true);
          } else {
            setManualInput(false);
          }
        }}>
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="选择类型" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="dataset">选择数据集</SelectItem>
            <SelectItem value="manual">手动输入</SelectItem>
          </SelectContent>
        </Select>

        {manualInput ? (
          <Input
            value={manualPath}
            onChange={(e) => setManualPath(e.target.value)}
            placeholder={placeholder}
            className="flex-1"
          />
        ) : (
          <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogTrigger asChild>
              <Button
                variant="outline"
                className="flex-1 justify-between text-left font-normal"
                onClick={() => setManualInput(false)}
              >
                {selectedDataset ? (
                  <span className="flex items-center gap-2">
                    <Database className="h-4 w-4 text-muted-foreground" />
                    {selectedDataset.name}
                  </span>
                ) : value ? (
                  <span className="flex items-center gap-2 truncate">
                    <FolderOpen className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    <span className="truncate">{value}</span>
                  </span>
                ) : (
                  <span className="text-muted-foreground flex items-center gap-2">
                    <Database className="h-4 w-4" />
                    {placeholder}
                  </span>
                )}
                <ChevronRight className="h-4 w-4 text-muted-foreground ml-2 flex-shrink-0" />
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
              <DialogHeader>
                <DialogTitle>选择数据集</DialogTitle>
              </DialogHeader>

              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="搜索数据集..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                  autoFocus
                />
              </div>

              {/* Dataset List */}
              <div className="max-h-[300px] overflow-y-auto space-y-2">
                {isLoading ? (
                  <div className="flex items-center justify-center h-32">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                ) : filteredDatasets.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    {searchQuery ? '未找到匹配的数据集' : '暂无数据集'}
                  </div>
                ) : (
                  filteredDatasets.map((dataset) => (
                    <Card
                      key={dataset.dataset_id}
                      className={`cursor-pointer transition-colors hover:bg-accent ${
                        dataset.path === value ? 'border-primary' : ''
                      }`}
                    >
                      <CardContent className="p-3">
                        <button
                          type="button"
                          className="w-full text-left"
                          onClick={() => handleSelectDataset(dataset)}
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1 min-w-0">
                              <p className="font-medium truncate">{dataset.name}</p>
                              <p className="text-sm text-muted-foreground font-mono truncate">
                                {dataset.path}
                              </p>
                              <div className="flex gap-2 mt-1">
                                {dataset.size_gb !== null && (
                                  <span className="text-xs text-muted-foreground">
                                    {dataset.size_gb.toFixed(2)} GB
                                  </span>
                                )}
                                {dataset.version && (
                                  <span className="text-xs text-muted-foreground">
                                    v{dataset.version}
                                  </span>
                                )}
                              </div>
                            </div>
                            <Database className="h-4 w-4 text-muted-foreground flex-shrink-0 ml-2" />
                          </div>
                        </button>
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>

              {/* Manual Input Toggle */}
              <div className="border-t pt-4">
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full"
                  onClick={() => setManualInput(true)}
                >
                  手动输入路径
                </Button>
              </div>

              {/* Manual Input Section */}
              {manualInput && (
                <div className="space-y-2">
                  <Label htmlFor="manual-path">手动输入路径</Label>
                  <div className="flex gap-2">
                    <Input
                      id="manual-path"
                      value={manualPath}
                      onChange={(e) => setManualPath(e.target.value)}
                      placeholder="/mnt/VtrixDataset/data/train"
                    />
                    <Button onClick={handleManualPathConfirm} disabled={!manualPath.trim()}>
                      确认
                    </Button>
                  </div>
                </div>
              )}
            </DialogContent>
          </Dialog>
        )}
      </div>

      {manualInput && manualPath && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            onChange(manualPath);
            setManualInput(false);
          }}
        >
          确认路径
        </Button>
      )}
    </div>
  );
}