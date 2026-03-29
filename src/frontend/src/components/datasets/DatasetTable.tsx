'use client';

import { useState } from 'react';
import { DatasetResponse } from '@/types/dataset';
import { DatasetFilter, DatasetFilterValues } from './DatasetFilter';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { DatasetForm } from './DatasetForm';
import { Pencil, Trash2, Plus, RefreshCw } from 'lucide-react';
import Link from 'next/link';

const PAGE_SIZE = 10;

interface DatasetTableProps {
  datasets: DatasetResponse[];
  isLoading: boolean;
  onRefetch: () => void;
  onDelete: (id: string) => Promise<void>;
  onUpdate: (id: string, data: { name?: string; path?: string }) => Promise<void>;
}

export function DatasetTable({
  datasets,
  isLoading,
  onRefetch,
  onDelete,
  onUpdate,
}: DatasetTableProps) {
  const [filters, setFilters] = useState<DatasetFilterValues>({
    searchQuery: '',
    sizeMin: '',
    sizeMax: '',
    sortBy: 'created_at',
    sortOrder: 'desc',
  });
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [editingDataset, setEditingDataset] = useState<DatasetResponse | null>(null);

  // Filter and sort datasets
  const filteredDatasets = datasets.filter((dataset) => {
    // Search filter
    if (filters.searchQuery) {
      const query = filters.searchQuery.toLowerCase();
      if (!dataset.name.toLowerCase().includes(query)) {
        return false;
      }
    }

    // Size min filter
    if (filters.sizeMin && dataset.size_gb !== null) {
      if (dataset.size_gb < parseFloat(filters.sizeMin)) {
        return false;
      }
    }

    // Size max filter
    if (filters.sizeMax && dataset.size_gb !== null) {
      if (dataset.size_gb > parseFloat(filters.sizeMax)) {
        return false;
      }
    }

    return true;
  });

  // Sort datasets
  const sortedDatasets = [...filteredDatasets].sort((a, b) => {
    let comparison = 0;

    switch (filters.sortBy) {
      case 'name':
        comparison = a.name.localeCompare(b.name);
        break;
      case 'size_gb':
        comparison = (a.size_gb || 0) - (b.size_gb || 0);
        break;
      case 'created_at':
        comparison = new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime();
        break;
    }

    return filters.sortOrder === 'asc' ? comparison : -comparison;
  });

  const totalPages = Math.ceil(sortedDatasets.length / PAGE_SIZE);
  const paginatedDatasets = sortedDatasets.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const handleEdit = (dataset: DatasetResponse) => {
    setEditingDataset(dataset);
    setShowForm(true);
  };

  const handleDelete = async (dataset: DatasetResponse) => {
    if (!dataset.dataset_id) return;
    if (window.confirm(`确定要删除数据集 "${dataset.name}" 吗？`)) {
      await onDelete(dataset.dataset_id);
    }
  };

  const handleFormSuccess = () => {
    setShowForm(false);
    setEditingDataset(null);
    onRefetch();
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingDataset(null);
  };

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">筛选</CardTitle>
        </CardHeader>
        <CardContent>
          <DatasetFilter filters={filters} onFiltersChange={setFilters} />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="flex items-center justify-between p-4">
            <span className="text-sm text-muted-foreground">
              共 {sortedDatasets.length} 个数据集
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="icon" onClick={onRefetch} disabled={isLoading}>
                <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              </Button>
              <Button onClick={() => setShowForm(true)}>
                <Plus className="mr-2 h-4 w-4" />
                新建数据集
              </Button>
            </div>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>名称</TableHead>
                <TableHead>路径</TableHead>
                <TableHead>版本</TableHead>
                <TableHead>大小 (GB)</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8">
                    加载中...
                  </TableCell>
                </TableRow>
              ) : paginatedDatasets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8">
                    暂无数据集记录
                  </TableCell>
                </TableRow>
              ) : (
                paginatedDatasets.map((dataset) => (
                  <TableRow key={dataset.dataset_id}>
                    <TableCell className="font-medium">
                      <Link href={`/datasets/${dataset.dataset_id}`} className="hover:underline">
                        {dataset.name}
                      </Link>
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate text-muted-foreground">
                      {dataset.path}
                    </TableCell>
                    <TableCell>
                      {dataset.version ? (
                        <Badge variant="secondary">{dataset.version}</Badge>
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell>
                      {dataset.size_gb !== null ? dataset.size_gb.toFixed(2) : '-'}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {dataset.created_at
                        ? new Date(dataset.created_at).toLocaleString('zh-CN')
                        : '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleEdit(dataset)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(dataset)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            上一页
          </Button>
          <span className="text-sm text-muted-foreground">
            第 {page} / {totalPages} 页
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            下一页
          </Button>
        </div>
      )}

      <DatasetForm
        open={showForm}
        onOpenChange={(open) => {
          if (!open) handleFormClose();
          else setShowForm(true);
        }}
        dataset={editingDataset}
        onSuccess={handleFormSuccess}
        onUpdate={onUpdate}
      />
    </>
  );
}
