import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useDatasets, useDataset, useCreateDataset, useUpdateDataset, useDeleteDataset, useRestoreDataset } from '../use-datasets';

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('useDatasets', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('返回空数据集列表', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });

    const { result } = renderHook(() => useDatasets(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });

  test('返回数据集列表', async () => {
    const mockData = [
      { id: 'ds-001', name: 'ImageNet', size: '100GB', status: 'available' },
      { id: 'ds-002', name: 'CIFAR-10', size: '2GB', status: 'available' },
    ];
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    });

    const { result } = renderHook(() => useDatasets(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(2);
    expect(result.current.data?.[0].name).toBe('ImageNet');
  });

  test('处理 { items: [] } 响应格式', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [{ id: 'ds-001', name: 'Test', size: '1GB', status: 'available' }] }),
    });

    const { result } = renderHook(() => useDatasets(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].name).toBe('Test');
  });

  test('处理加载状态', async () => {
    mockFetch.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({
        ok: true,
        json: async () => [],
      }), 100))
    );

    const { result } = renderHook(() => useDatasets(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => expect(result.current.isLoading).toBe(false));
  });

  test('处理错误状态', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    const { result } = renderHook(() => useDatasets(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe('useDataset', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('返回单个数据集详情', async () => {
    const mockData = { id: 'ds-001', name: 'ImageNet', size: '100GB', status: 'available' };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    });

    const { result } = renderHook(() => useDataset('ds-001'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.name).toBe('ImageNet');
  });

  test('没有 id 时不发起请求', () => {
    const { result } = renderHook(() => useDataset(''), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.isFetching).toBe(false);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  test('处理错误状态', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    const { result } = renderHook(() => useDataset('ds-999'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe('useCreateDataset', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('创建数据集成功', async () => {
    const newDataset = { name: 'NewDataset', path: '/data/new', size: '10GB' };
    const createdDataset = { id: 'ds-new', ...newDataset, status: 'available' };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => createdDataset,
    });

    const { result } = renderHook(() => useCreateDataset(), {
      wrapper: createWrapper(),
    });

    let response;
    await waitFor(async () => {
      response = await result.current.mutateAsync(newDataset);
    });

    expect(response).toEqual(createdDataset);
    expect(mockFetch).toHaveBeenCalledWith('/api/proxy/datasets', expect.objectContaining({
      method: 'POST',
    }));
  });

  test('创建数据集失败时抛出错误', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ error: 'Invalid dataset name' }),
    });

    const { result } = renderHook(() => useCreateDataset(), {
      wrapper: createWrapper(),
    });

    let error: Error | undefined;
    try {
      await result.current.mutateAsync({ name: '', path: '/data', size: '1GB' });
    } catch (e) {
      error = e as Error;
    }

    expect(error).toBeDefined();
  });
});

describe('useUpdateDataset', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('更新数据集成功', async () => {
    const updatedDataset = { id: 'ds-001', name: 'UpdatedName', size: '100GB', status: 'available' };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => updatedDataset,
    });

    const { result } = renderHook(() => useUpdateDataset(), {
      wrapper: createWrapper(),
    });

    let response;
    await waitFor(async () => {
      response = await result.current.mutateAsync({ id: 'ds-001', name: 'UpdatedName' });
    });

    expect(response).toEqual(updatedDataset);
    expect(mockFetch).toHaveBeenCalledWith('/api/proxy/datasets/ds-001', expect.objectContaining({
      method: 'PUT',
    }));
  });

  test('更新数据集失败时抛出错误', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ error: 'Dataset not found' }),
    });

    const { result } = renderHook(() => useUpdateDataset(), {
      wrapper: createWrapper(),
    });

    let error: Error | undefined;
    try {
      await result.current.mutateAsync({ id: 'ds-001', name: 'UpdatedName' });
    } catch (e) {
      error = e as Error;
    }

    expect(error).toBeDefined();
    expect(error?.message).toBe('Dataset not found');
  });
});

describe('useDeleteDataset', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('删除数据集成功', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    });

    const { result } = renderHook(() => useDeleteDataset(), {
      wrapper: createWrapper(),
    });

    let response;
    await waitFor(async () => {
      response = await result.current.mutateAsync('ds-001');
    });

    expect(response).toEqual({ success: true });
    expect(mockFetch).toHaveBeenCalledWith('/api/proxy/datasets/ds-001', expect.objectContaining({
      method: 'DELETE',
    }));
  });

  test('删除数据集失败时抛出错误', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ error: 'Dataset not found' }),
    });

    const { result } = renderHook(() => useDeleteDataset(), {
      wrapper: createWrapper(),
    });

    let error: Error | undefined;
    try {
      await result.current.mutateAsync('ds-999');
    } catch (e) {
      error = e as Error;
    }

    expect(error).toBeDefined();
    expect(error?.message).toBe('Dataset not found');
  });
});

describe('useRestoreDataset', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('恢复数据集成功', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'ds-001', status: 'available' }),
    });

    const { result } = renderHook(() => useRestoreDataset(), {
      wrapper: createWrapper(),
    });

    let response;
    await waitFor(async () => {
      response = await result.current.mutateAsync('ds-001');
    });

    expect(response).toEqual({ id: 'ds-001', status: 'available' });
    expect(mockFetch).toHaveBeenCalledWith('/api/proxy/datasets/ds-001/restore', expect.objectContaining({
      method: 'POST',
    }));
  });

  test('恢复数据集失败时抛出错误', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ error: 'Restore failed' }),
    });

    const { result } = renderHook(() => useRestoreDataset(), {
      wrapper: createWrapper(),
    });

    let error: Error | undefined;
    try {
      await result.current.mutateAsync('ds-001');
    } catch (e) {
      error = e as Error;
    }

    expect(error).toBeDefined();
    expect(error?.message).toBe('Restore failed');
  });

  test('恢复数据集失败时使用默认错误消息', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({}), // No error field
    });

    const { result } = renderHook(() => useRestoreDataset(), {
      wrapper: createWrapper(),
    });

    let error: Error | undefined;
    try {
      await result.current.mutateAsync('ds-001');
    } catch (e) {
      error = e as Error;
    }

    expect(error).toBeDefined();
    expect(error?.message).toBe('Failed to restore dataset');
  });
});

describe('useDatasets fallback branches', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('处理 items 为 undefined 的响应', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: undefined }),
    });

    const { result } = renderHook(() => useDatasets(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });
});

describe('useCreateDataset fallback branches', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('创建数据集失败时使用默认错误消息', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({}), // No error field
    });

    const { result } = renderHook(() => useCreateDataset(), {
      wrapper: createWrapper(),
    });

    let error: Error | undefined;
    try {
      await result.current.mutateAsync({ name: '', path: '/data', size: '1GB' });
    } catch (e) {
      error = e as Error;
    }

    expect(error).toBeDefined();
    expect(error?.message).toBe('Failed to create dataset');
  });
});

describe('useUpdateDataset fallback branches', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('更新数据集失败时使用默认错误消息', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ message: 'Some error' }), // error field is undefined
    });

    const { result } = renderHook(() => useUpdateDataset(), {
      wrapper: createWrapper(),
    });

    let error: Error | undefined;
    try {
      await result.current.mutateAsync({ id: 'ds-001', name: 'UpdatedName' });
    } catch (e) {
      error = e as Error;
    }

    expect(error).toBeDefined();
    expect(error?.message).toBe('Failed to update dataset');
  });
});

describe('useDeleteDataset fallback branches', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('删除数据集失败时使用默认错误消息', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({}), // No error field
    });

    const { result } = renderHook(() => useDeleteDataset(), {
      wrapper: createWrapper(),
    });

    let error: Error | undefined;
    try {
      await result.current.mutateAsync('ds-999');
    } catch (e) {
      error = e as Error;
    }

    expect(error).toBeDefined();
    expect(error?.message).toBe('Failed to delete dataset');
  });
});
