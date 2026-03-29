# Frontend Engineer Reply: 数据集管理界面详细规划

## Q1: 数据集管理范围

**推荐方案: 选项 A (仅管理路径) + 扩展预留**

理由:
1. **后端 DatasetManager 现状**: 当前 `DatasetManager` 仅支持路径管理和 DVC 版本追踪，无上传/导入功能
2. **数据安全**: 大文件上传不适合通过 Web Console 处理，应通过专业工具 (rsync/NFS) 放置
3. **职责分离**: Web Console 专注于管理和调度，不做数据传输

**具体范围:**
- 展示已存在的数据集列表 (路径、版本、大小)
- 支持数据集路径注册/编辑 (前端仅记录路径，不做传输)
- 与 TaskWizard 集成: 选择数据集而非手动输入路径
- 预留: 未来可扩展"导入外部 URL"功能 (需要后端支持)

**不建议:**
- 直接文件上传 (大文件、进度管理复杂)
- 实时数据传输 (NFS/SSH 预放置是标准做法)

---

## Q2: 页面功能

### 列表页 (`/datasets`)

**展示字段:**
| 字段 | 说明 |
|------|------|
| name | 数据集名称 |
| path | 完整路径 |
| version | DVC 版本 (git hash 短版) |
| size_gb | 大小 (GB) |
| created_at | 创建时间 |
| actions | 操作 (编辑/删除) |

**搜索/过滤/排序:**
- 搜索: 按名称模糊搜索
- 过滤: 按 size_gb 范围
- 排序: 按 name / size_gb / created_at

### 详情页 (`/datasets/[id]`)

**展示信息:**
- 数据集基本信息 (name, path, version, size_gb)
- 关联任务列表 (使用该数据集的训练/验证任务)
- 目录结构预览 (可选, 如果后端支持)

---

## Q3: TaskWizard 集成

**现状:**
```tsx
// TaskWizard.tsx line 43 - 当前是 free-text input
const [dataPath, setDataPath] = useState('');
```

**集成方案:**

替换数据路径输入为 DatasetSelector 组件:

```tsx
// Step 2 中的数据路径选择
<div className="space-y-2">
  <Label>选择数据集</Label>
  <DatasetSelector
    value={dataPath}
    onChange={setDataPath}
    filter={{ taskType }} // 根据任务类型过滤
  />
  <p className="text-xs text-muted-foreground">
    或手动输入路径: <Input value={dataPath} onChange={...} />
  </p>
</div>
```

**交互方式:**
1. **Select + Dialog**: 点击后弹出 DatasetSelector Dialog
2. Dialog 内显示数据集列表, 支持搜索
3. 选择后填充 dataPath
4. 提供"手动输入"切换, 兼容自定义路径

---

## Q4: UI 组件

### 新增组件清单

| 组件 | 类型 | 说明 |
|------|------|------|
| `DatasetTable` | component | 数据集列表 Table 组件 (参考 TaskTable) |
| `DatasetCard` | component | 数据集卡片 (用于 Dialog 选择器) |
| `DatasetSelector` | component | TaskWizard 内置选择器 (Select + Dialog) |
| `DatasetForm` | component | 创建/编辑表单 (Dialog) |
| `DatasetFilter` | component | 筛选栏组件 |
| `useDatasets` | hook | React Query hook (参考 use-tasks) |

### 组件结构

```
src/frontend/src/
├── app/(main)/datasets/
│   ├── page.tsx           # 列表页
│   └── [id]/page.tsx      # 详情页
├── components/
│   └── datasets/
│       ├── DatasetTable.tsx
│       ├── DatasetCard.tsx
│       ├── DatasetSelector.tsx
│       ├── DatasetForm.tsx
│       └── DatasetFilter.tsx
├── hooks/
│   └── use-datasets.ts
├── lib/
│   └── api.ts             # 新增 getDatasets, getDataset, createDataset, updateDataset, deleteDataset
└── types/
    └── dataset.ts         # DatasetResponse 类型
```

### API 代理路由

```
/api/proxy/datasets/route.ts    # GET (list), POST (create)
/api/proxy/datasets/[id]/route.ts  # GET, PUT, DELETE
```

---

## 工作量估算

| 任务 | 工作量 | 说明 |
|------|--------|------|
| 数据集列表页 (`/datasets`) | 4h (0.5d) | page.tsx + DatasetTable + DatasetFilter |
| 数据集详情页 (`/datasets/[id]`) | 3h (0.4d) | page.tsx + 基本信息展示 |
| 数据集创建/编辑表单 (DatasetForm) | 4h (0.5d) | Dialog + Form, 包含验证 |
| TaskWizard 数据集选择器 (DatasetSelector) | 6h (0.75d) | Select + Dialog + 搜索 + 集成 |
| API 集成 (use-datasets hook + proxy routes) | 4h (0.5d) | React Query hook + 4 个 proxy routes |
| 类型定义 (dataset.ts) | 1h | TypeScript interfaces |
| **总计** | **22h (2.75d)** | ~3 working days |

### 详细分解

```
Day 1:
  - 类型定义 + API routes (proxy)     [3h]
  - DatasetTable + DatasetFilter        [3h]
  - 数据集列表页 page.tsx               [2h]

Day 2:
  - DatasetForm (创建/编辑)             [3h]
  - 数据集详情页 page.tsx              [2h]
  - use-datasets hook                  [2h]

Day 3:
  - DatasetSelector 组件                [3h]
  - TaskWizard 集成                     [3h]
```

---

## 技术方案要点

### 1. 类型定义 (`types/dataset.ts`)

```typescript
export interface DatasetResponse {
  id?: string;              // 后端生成, 创建后返回
  name: string;
  path: string;
  version: string | null;
  size_gb: number | null;
  created_at?: string;
}

export interface CreateDatasetRequest {
  name: string;
  path: string;
}

export interface UpdateDatasetRequest {
  name?: string;
  path?: string;
}
```

### 2. Proxy Route 模式

参考现有 `/api/proxy/tasks/route.ts`:

```typescript
// /api/proxy/datasets/route.ts
export async function GET(request: Request) {
  const url = `${API_BASE}/api/datasets`;
  // ... 复用 getUserHeaders + fetch 模式
}

export async function POST(request: Request) {
  const body = await request.json();
  const url = `${API_BASE}/api/datasets`;
  // ... 复用模式
}
```

### 3. DatasetSelector 在 TaskWizard 中的位置

替换 Step 2 中 taskType === 'train' / 'verify' 的数据路径输入:

```tsx
{taskType === 'train' && (
  <>
    <DatasetSelector
      value={dataPath}
      onChange={setDataPath}
      placeholder="/mnt/VtrixDataset/data/train"
    />
    {/* 或手动输入的 Toggle */}
  </>
)}
```

### 4. 响应式考虑

- 移动端: DatasetTable 转为 Card 布局
- Dialog 在移动端全屏显示
- 搜索/筛选使用 collapsible sections

---

## 依赖与前提

**前端依赖 (已存在):**
- React Query (TanStack Query)
- shadcn/ui components
- Tailwind CSS

**需要后端支持:**
- `/api/datasets` GET - 列出数据集
- `/api/datasets` POST - 创建数据集
- `/api/datasets/[id]` GET/PUT/DELETE

**当前后端 DatasetManager (`src/algo_studio/core/dataset.py`):**
- `list_datasets()` - 已有
- `add_dataset()` - 已有 (DVC 初始化)
- 需要补充: CRUD API routes

---

## 结论

推荐按 **选项 A (仅管理路径)** 实现, 预留扩展能力。总工作量约 **3 person-days**, 主要工作量在 DatasetSelector 和 TaskWizard 集成。

如需加快进度, 可分两个 milestone:
1. **M1**: 列表页 + 详情页 + CRUD (1.5d)
2. **M2**: TaskWizard 集成 (1.5d)
