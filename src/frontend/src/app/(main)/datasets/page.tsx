'use client';

import { useDatasets, useUpdateDataset, useDeleteDataset } from '@/hooks/use-datasets';
import { DatasetTable } from '@/components/datasets/DatasetTable';

export default function DatasetsPage() {
  const { data: datasets, isLoading, refetch, isFetching } = useDatasets();
  const updateDataset = useUpdateDataset();
  const deleteDataset = useDeleteDataset();

  const handleUpdate = async (id: string, data: { name?: string; path?: string }) => {
    await updateDataset.mutateAsync({ id, ...data });
  };

  const handleDelete = async (id: string) => {
    await deleteDataset.mutateAsync(id);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">数据集管理</h1>
        <p className="text-muted-foreground">
          管理训练和验证数据集路径，支持 DVC 版本追踪
        </p>
      </div>

      <DatasetTable
        datasets={datasets || []}
        isLoading={isLoading || isFetching}
        onRefetch={refetch}
        onUpdate={handleUpdate}
        onDelete={handleDelete}
      />
    </div>
  );
}
