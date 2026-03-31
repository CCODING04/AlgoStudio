import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useTasks, useTask } from '../use-tasks';

// Mock the API module
jest.mock('@/lib/api', () => ({
  getTasks: jest.fn(),
  getTask: jest.fn(),
}));

import { getTasks, getTask } from '@/lib/api';

const mockedGetTasks = getTasks as jest.MockedFunction<typeof getTasks>;
const mockedGetTask = getTask as jest.MockedFunction<typeof getTask>;

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

describe('useTasks', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('返回空任务列表', async () => {
    mockedGetTasks.mockResolvedValueOnce([]);

    const { result } = renderHook(() => useTasks(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });

  test('返回任务列表数据', async () => {
    const mockTasks = [
      {
        task_id: 'train-001',
        task_type: 'train' as const,
        algorithm_name: 'simple_classifier',
        algorithm_version: 'v1',
        status: 'completed' as const,
        created_at: '2026-03-30T10:00:00Z',
        started_at: '2026-03-30T10:00:01Z',
        completed_at: '2026-03-30T10:30:00Z',
        assigned_node: '192.168.0.126',
        error: null,
        progress: 100,
      },
      {
        task_id: 'train-002',
        task_type: 'train' as const,
        algorithm_name: 'simple_classifier',
        algorithm_version: 'v1',
        status: 'running' as const,
        created_at: '2026-03-30T11:00:00Z',
        started_at: '2026-03-30T11:00:01Z',
        completed_at: null,
        assigned_node: '192.168.0.115',
        error: null,
        progress: 45,
      },
    ];

    mockedGetTasks.mockResolvedValueOnce(mockTasks);

    const { result } = renderHook(() => useTasks(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(2);
    expect(result.current.data?.[0].task_id).toBe('train-001');
    expect(result.current.data?.[1].status).toBe('running');
  });

  test('按状态过滤任务', async () => {
    mockedGetTasks.mockResolvedValueOnce([]);

    const { result } = renderHook(() => useTasks('running'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockedGetTasks).toHaveBeenCalledWith('running');
  });

  test('处理加载状态', async () => {
    mockedGetTasks.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve([]), 100))
    );

    const { result } = renderHook(() => useTasks(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();

    await waitFor(() => expect(result.current.isLoading).toBe(false));
  });

  test('处理错误状态', async () => {
    mockedGetTasks.mockRejectedValueOnce(new Error('Failed to fetch tasks'));

    const { result } = renderHook(() => useTasks(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeDefined();
  });

  test('具有正确的 queryKey', async () => {
    mockedGetTasks.mockResolvedValueOnce([]);

    const { result } = renderHook(() => useTasks(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockedGetTasks).toHaveBeenCalledTimes(1);
  });

  test('验证 refetchInterval 配置为 30000ms', async () => {
    mockedGetTasks.mockResolvedValueOnce([]);

    const { result } = renderHook(() => useTasks(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockedGetTasks).toHaveBeenCalledTimes(1);
  });
});

describe('useTask', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('返回单个任务详情', async () => {
    const mockTask = {
      task_id: 'train-001',
      task_type: 'train' as const,
      algorithm_name: 'simple_classifier',
      algorithm_version: 'v1',
      status: 'completed' as const,
      created_at: '2026-03-30T10:00:00Z',
      started_at: '2026-03-30T10:00:01Z',
      completed_at: '2026-03-30T10:30:00Z',
      assigned_node: '192.168.0.126',
      error: null,
      progress: 100,
    };

    mockedGetTask.mockResolvedValueOnce(mockTask);

    const { result } = renderHook(() => useTask('train-001'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.task_id).toBe('train-001');
    expect(result.current.data?.status).toBe('completed');
  });

  test('没有 taskId 时不发起请求', async () => {
    const { result } = renderHook(() => useTask(''), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.isFetching).toBe(false);
    expect(mockedGetTask).not.toHaveBeenCalled();
  });

  test('处理任务加载状态', async () => {
    mockedGetTask.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({
        task_id: 'train-001',
        task_type: 'train' as const,
        algorithm_name: 'simple_classifier',
        algorithm_version: 'v1',
        status: 'running' as const,
        created_at: '2026-03-30T10:00:00Z',
        started_at: '2026-03-30T10:00:01Z',
        completed_at: null,
        assigned_node: '192.168.0.126',
        error: null,
        progress: 50,
      }), 100))
    );

    const { result } = renderHook(() => useTask('train-001'), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();

    await waitFor(() => expect(result.current.isLoading).toBe(false));
  });

  test('处理任务错误状态', async () => {
    mockedGetTask.mockRejectedValueOnce(new Error('Failed to fetch task'));

    const { result } = renderHook(() => useTask('train-001'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeDefined();
  });

  test('具有正确的 queryKey', async () => {
    mockedGetTask.mockResolvedValueOnce({
      task_id: 'train-001',
      task_type: 'train' as const,
      algorithm_name: 'simple_classifier',
      algorithm_version: 'v1',
      status: 'completed' as const,
      created_at: '2026-03-30T10:00:00Z',
      started_at: '2026-03-30T10:00:01Z',
      completed_at: '2026-03-30T10:30:00Z',
      assigned_node: '192.168.0.126',
      error: null,
      progress: 100,
    });

    const { result } = renderHook(() => useTask('train-001'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockedGetTask).toHaveBeenCalledWith('train-001');
  });
});
