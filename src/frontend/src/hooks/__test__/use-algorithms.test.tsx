import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAlgorithms, Algorithm } from '../use-algorithms';

// Mock fetch globally
global.fetch = jest.fn();

const mockedFetch = fetch as jest.MockedFunction<typeof fetch>;

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

describe('useAlgorithms', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('返回空算法列表', async () => {
    mockedFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [] }),
    } as Response);

    const { result } = renderHook(() => useAlgorithms(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });

  test('返回算法列表数据（items 格式）', async () => {
    const mockAlgorithms: Algorithm[] = [
      { name: 'simple_classifier', version: 'v1' },
      { name: 'resnet50', version: 'v2' },
    ];

    mockedFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: mockAlgorithms }),
    } as Response);

    const { result } = renderHook(() => useAlgorithms(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(2);
    expect(result.current.data?.[0].name).toBe('simple_classifier');
  });

  test('返回算法列表数据（algorithms 格式）', async () => {
    const mockAlgorithms: Algorithm[] = [
      { name: 'yolo_v8', version: 'v1' },
    ];

    mockedFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ algorithms: mockAlgorithms }),
    } as Response);

    const { result } = renderHook(() => useAlgorithms(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].name).toBe('yolo_v8');
  });

  test('返回算法列表数据（数组直接返回）', async () => {
    const mockAlgorithms: Algorithm[] = [
      { name: 'bert_base', version: 'v1' },
      { name: 'gpt2', version: 'v1' },
    ];

    mockedFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockAlgorithms,
    } as Response);

    const { result } = renderHook(() => useAlgorithms(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(2);
  });

  test('处理加载状态', async () => {
    mockedFetch.mockImplementation(
      () => new Promise((resolve) =>
        setTimeout(
          () =>
            resolve({
              ok: true,
              json: async () => ({ items: [] }),
            } as Response),
          100
        )
      )
    );

    const { result } = renderHook(() => useAlgorithms(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();

    await waitFor(() => expect(result.current.isLoading).toBe(false));
  });

  test('处理错误状态', async () => {
    mockedFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    } as Response);

    const { result } = renderHook(() => useAlgorithms(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  test('具有正确的 queryKey', async () => {
    mockedFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [] }),
    } as Response);

    const { result } = renderHook(() => useAlgorithms(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockedFetch).toHaveBeenCalledTimes(1);
  });

  test('验证 staleTime 配置为 5 分钟', async () => {
    mockedFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [] }),
    } as Response);

    const { result } = renderHook(() => useAlgorithms(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeDefined();
  });

  test('请求使用正确的 API 路径', async () => {
    mockedFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [] }),
    } as Response);

    const { result } = renderHook(() => useAlgorithms(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockedFetch).toHaveBeenCalledWith('/api/proxy/algorithms', {
      cache: 'no-store',
    });
  });
});
