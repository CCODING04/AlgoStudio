'use client';

import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export interface DatasetFilterValues {
  searchQuery: string;
  sizeMin: string;
  sizeMax: string;
  sortBy: 'name' | 'size_gb' | 'created_at';
  sortOrder: 'asc' | 'desc';
}

interface DatasetFilterProps {
  filters: DatasetFilterValues;
  onFiltersChange: (filters: DatasetFilterValues) => void;
}

export function DatasetFilter({ filters, onFiltersChange }: DatasetFilterProps) {
  return (
    <div className="flex flex-wrap gap-4">
      <div className="flex-1 min-w-[200px]">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="搜索数据集名称..."
            value={filters.searchQuery}
            onChange={(e) =>
              onFiltersChange({ ...filters, searchQuery: e.target.value })
            }
            className="pl-9"
          />
        </div>
      </div>

      <div className="w-[140px]">
        <Input
          type="number"
          placeholder="最小 GB"
          value={filters.sizeMin}
          onChange={(e) =>
            onFiltersChange({ ...filters, sizeMin: e.target.value })
          }
        />
      </div>

      <div className="w-[140px]">
        <Input
          type="number"
          placeholder="最大 GB"
          value={filters.sizeMax}
          onChange={(e) =>
            onFiltersChange({ ...filters, sizeMax: e.target.value })
          }
        />
      </div>

      <Select
        value={filters.sortBy}
        onValueChange={(value: 'name' | 'size_gb' | 'created_at') =>
          onFiltersChange({ ...filters, sortBy: value })
        }
      >
        <SelectTrigger className="w-[140px]">
          <SelectValue placeholder="排序字段" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="name">名称</SelectItem>
          <SelectItem value="size_gb">大小</SelectItem>
          <SelectItem value="created_at">创建时间</SelectItem>
        </SelectContent>
      </Select>

      <Select
        value={filters.sortOrder}
        onValueChange={(value: 'asc' | 'desc') =>
          onFiltersChange({ ...filters, sortOrder: value })
        }
      >
        <SelectTrigger className="w-[120px]">
          <SelectValue placeholder="排序方向" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="asc">升序</SelectItem>
          <SelectItem value="desc">降序</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
