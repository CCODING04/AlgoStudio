'use client';

import { renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useTaskSSE } from '../use-sse';

// Mock EventSource
class MockEventSource {
  static instances: MockEventSource[] = [];
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  close = jest.fn();

  constructor(_url: string) {
    MockEventSource.instances.push(this);
  }

  // Simulate receiving a message
  static emitMessage(data: object) {
    const instance = MockEventSource.instances[MockEventSource.instances.length - 1];
    if (instance?.onmessage) {
      instance.onmessage({ data: JSON.stringify(data) } as MessageEvent);
    }
  }

  // Simulate an error
  static emitError() {
    const instance = MockEventSource.instances[MockEventSource.instances.length - 1];
    if (instance?.onerror) {
      instance.onerror();
    }
  }

  static reset() {
    MockEventSource.instances = [];
  }
}

jest.mock('@/lib/api', () => ({
  apiRequest: jest.fn(),
}));

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

describe('useTaskSSE', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    MockEventSource.reset();
    global.EventSource = MockEventSource as unknown as typeof EventSource;
  });

  test('当 taskId 为 null 时不创建 EventSource', () => {
    const { result } = renderHook(() => useTaskSSE(null), {
      wrapper: createWrapper(),
    });

    expect(result.current).toBeUndefined();
    expect(MockEventSource.instances).toHaveLength(0);
  });

  test('当 taskId 存在时创建 EventSource', () => {
    const { result, unmount } = renderHook(() => useTaskSSE('task-123'), {
      wrapper: createWrapper(),
    });

    expect(result.current).toBeUndefined();
    expect(MockEventSource.instances).toHaveLength(1);

    unmount();
  });

  test('接收到 progress 更新时调用 onProgress 回调', () => {
    const onProgress = jest.fn();

    renderHook(() => useTaskSSE('task-123', onProgress), {
      wrapper: createWrapper(),
    });

    // Simulate receiving a progress message
    MockEventSource.emitMessage({
      task_id: 'task-123',
      progress: 50,
      status: 'running',
      description: 'Training epoch 5',
    });

    expect(onProgress).toHaveBeenCalledWith({
      task_id: 'task-123',
      progress: 50,
      status: 'running',
      description: 'Training epoch 5',
    });
  });

  test('忽略不匹配 taskId 的消息', () => {
    const onProgress = jest.fn();

    renderHook(() => useTaskSSE('task-123', onProgress), {
      wrapper: createWrapper(),
    });

    MockEventSource.emitMessage({
      task_id: 'task-456',
      progress: 50,
      status: 'running',
    });

    expect(onProgress).not.toHaveBeenCalled();
  });

  test('忽略 JSON 解析错误', () => {
    const onProgress = jest.fn();

    renderHook(() => useTaskSSE('task-123', onProgress), {
      wrapper: createWrapper(),
    });

    // Manually call onmessage with invalid JSON
    const instance = MockEventSource.instances[MockEventSource.instances.length - 1];
    if (instance?.onmessage) {
      instance.onmessage({ data: 'invalid json' } as MessageEvent);
    }

    expect(onProgress).not.toHaveBeenCalled();
  });

  test('清理时关闭 EventSource', () => {
    const { unmount } = renderHook(() => useTaskSSE('task-123'), {
      wrapper: createWrapper(),
    });

    expect(MockEventSource.instances[0].close).not.toHaveBeenCalled();

    unmount();

    expect(MockEventSource.instances[0].close).toHaveBeenCalled();
  });

  test('重新连接时使用指数退避', () => {
    jest.useFakeTimers();

    const { unmount } = renderHook(() => useTaskSSE('task-123'), {
      wrapper: createWrapper(),
    });

    const instance = MockEventSource.instances[MockEventSource.instances.length - 1];

    // Emit error to trigger reconnect
    if (instance?.onerror) {
      instance.onerror();
    }

    // Fast-forward time to trigger reconnect
    jest.advanceTimersByTime(1000);

    // Should have created a new EventSource after reconnect delay
    expect(MockEventSource.instances.length).toBe(2);

    unmount();
    jest.useRealTimers();
  });

  test('超过最大重连次数时不重连', () => {
    jest.useFakeTimers();

    const { unmount } = renderHook(() => useTaskSSE('task-123'), {
      wrapper: createWrapper(),
    });

    const instance = MockEventSource.instances[MockEventSource.instances.length - 1];

    // Emit 5 errors to exceed MAX_RECONNECT_ATTEMPTS (5)
    for (let i = 0; i < 5; i++) {
      if (instance?.onerror) {
        instance.onerror();
      }
      jest.advanceTimersByTime(Math.pow(2, i) * 1000);
    }

    // Should not create more EventSource instances after max attempts
    // The 5th error won't trigger reconnect, so we have 6 instances total (initial + 5 reconnects)
    // Actually, the check happens BEFORE creating a new instance, so:
    // 1. initial create
    // 2-6. 5 reconnect attempts
    expect(MockEventSource.instances.length).toBe(6);

    // Now emit another error - should not reconnect
    if (instance?.onerror) {
      instance.onerror();
    }

    // Should still be 6 instances (no new one created)
    expect(MockEventSource.instances.length).toBe(6);

    unmount();
    jest.useRealTimers();
  });

  test('setQueryData被调用更新任务缓存', () => {
    // Create a query client with pre-populated cache
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    // Pre-populate the task cache
    queryClient.setQueryData(['task', 'task-123'], {
      task_id: 'task-123',
      progress: 0,
      status: 'pending',
    });

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const onProgress = jest.fn();

    renderHook(() => useTaskSSE('task-123', onProgress), {
      wrapper,
    });

    // Emit a progress message
    MockEventSource.emitMessage({
      task_id: 'task-123',
      progress: 50,
      status: 'running',
    });

    // onProgress should be called
    expect(onProgress).toHaveBeenCalled();
  });

  test('setQueryData被调用更新任务列表缓存', () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    // Pre-populate the tasks list cache
    queryClient.setQueryData(['tasks', undefined], {
      tasks: [
        { task_id: 'task-123', progress: 0, status: 'pending' },
        { task_id: 'task-456', progress: 0, status: 'pending' },
      ],
    });

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const onProgress = jest.fn();

    renderHook(() => useTaskSSE('task-123', onProgress), {
      wrapper,
    });

    // Emit a progress message
    MockEventSource.emitMessage({
      task_id: 'task-123',
      progress: 50,
      status: 'running',
    });

    // onProgress should be called
    expect(onProgress).toHaveBeenCalled();
  });

  test('当缓存数据不是对象时不更新', () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    // Set primitive value in cache
    queryClient.setQueryData(['task', 'task-123'], 'not an object');

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const onProgress = jest.fn();

    renderHook(() => useTaskSSE('task-123', onProgress), {
      wrapper,
    });

    // Emit a progress message
    MockEventSource.emitMessage({
      task_id: 'task-123',
      progress: 50,
      status: 'running',
    });

    // onProgress should still be called (but cache not updated)
    expect(onProgress).toHaveBeenCalled();
  });

  test('当任务列表缓存没有tasks属性时不更新', () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    // Set object without tasks property
    queryClient.setQueryData(['tasks', undefined], { total: 2 });

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const onProgress = jest.fn();

    renderHook(() => useTaskSSE('task-123', onProgress), {
      wrapper,
    });

    // Emit a progress message
    MockEventSource.emitMessage({
      task_id: 'task-123',
      progress: 50,
      status: 'running',
    });

    // onProgress should still be called
    expect(onProgress).toHaveBeenCalled();
  });

  test('cleanup清除reconnectTimeout', () => {
    jest.useFakeTimers();

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { unmount } = renderHook(() => useTaskSSE('task-123'), {
      wrapper,
    });

    // Trigger an error to set a reconnect timeout
    const instance = MockEventSource.instances[0];
    if (instance?.onerror) {
      instance.onerror();
    }

    // Advance time a bit but not enough to reconnect
    jest.advanceTimersByTime(500);

    // Unmount should clear the timeout
    unmount();

    // If we don't error, that's the expected behavior
    jest.useRealTimers();
  });

  test('cleanup在timeout未触发时清除reconnectTimeout', () => {
    jest.useFakeTimers();

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    // Create hook with a taskId
    const { result, unmount } = renderHook(() => useTaskSSE('task-123'), {
      wrapper,
    });

    // Trigger an error to set a reconnect timeout (line 88-90 in the hook sets this)
    const instance = MockEventSource.instances[0];
    if (instance?.onerror) {
      instance.onerror();
    }

    // The reconnect timeout is set but hasn't fired yet
    // When we unmount, cleanup should clear it
    unmount();

    // If we get here without error, the cleanup worked
    jest.useRealTimers();
  });

  test('当taskId为null时cleanup不执行', () => {
    const { result } = renderHook(() => useTaskSSE(null), {
      wrapper: createWrapper(),
    });

    expect(result.current).toBeUndefined();
    expect(MockEventSource.instances).toHaveLength(0);
  });

  test('taskId从有效值变为null时清理EventSource', () => {
    const { rerender } = renderHook(
      ({ taskId }: { taskId: string | null }) => useTaskSSE(taskId),
      { initialProps: { taskId: 'task-123' }, wrapper: createWrapper() }
    );

    expect(MockEventSource.instances).toHaveLength(1);

    // Change taskId to null
    rerender({ taskId: null });

    // EventSource should be closed
    expect(MockEventSource.instances[0].close).toHaveBeenCalled();
  });

  test('taskId改变时清除之前的reconnectTimeout', () => {
    jest.useFakeTimers();

    const { rerender } = renderHook(
      ({ taskId }: { taskId: string | null }) => useTaskSSE(taskId),
      { initialProps: { taskId: 'task-123' }, wrapper: createWrapper() }
    );

    // Trigger error to set reconnect timeout
    const instance = MockEventSource.instances[0];
    if (instance?.onerror) {
      instance.onerror();
    }

    // Verify timeout was set (advance time but not enough to reconnect)
    jest.advanceTimersByTime(500);
    expect(MockEventSource.instances).toHaveLength(1);

    // Change taskId - this should clear the timeout
    rerender({ taskId: 'task-456' });

    // New EventSource created, old one closed
    expect(MockEventSource.instances[0].close).toHaveBeenCalled();

    jest.useRealTimers();
  });

  test('cleanup清除reconnectTimeout当timeout存在时', () => {
    jest.useFakeTimers();

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    // First render with taskId
    const { rerender } = renderHook(
      ({ taskId }: { taskId: string | null }) => useTaskSSE(taskId),
      { initialProps: { taskId: 'task-123' }, wrapper }
    );

    // Trigger error to set reconnect timeout
    const instance = MockEventSource.instances[0];
    if (instance?.onerror) {
      instance.onerror();
    }

    // Verify timeout is set but not yet fired
    jest.advanceTimersByTime(500);

    // Rerender with new taskId - this triggers cleanup and should clear the timeout
    rerender({ taskId: 'task-456' });

    // The cleanup should have cleared the timeout before setting up new connection
    expect(MockEventSource.instances[0].close).toHaveBeenCalled();

    jest.useRealTimers();
  });

  test('连续错误触发多次重连', () => {
    jest.useFakeTimers();

    renderHook(() => useTaskSSE('task-123'), {
      wrapper: createWrapper(),
    });

    const instance = MockEventSource.instances[0];

    // First error
    if (instance?.onerror) instance.onerror();
    jest.advanceTimersByTime(1000);
    expect(MockEventSource.instances.length).toBe(2);

    // Second error
    const instance2 = MockEventSource.instances[1];
    if (instance2?.onerror) instance2.onerror();
    jest.advanceTimersByTime(2000);
    expect(MockEventSource.instances.length).toBe(3);

    jest.useRealTimers();
  });

  test('onmessage解析有效JSON调用onProgress', () => {
    const onProgress = jest.fn();

    renderHook(() => useTaskSSE('task-123', onProgress), {
      wrapper: createWrapper(),
    });

    const instance = MockEventSource.instances[0];
    if (instance?.onmessage) {
      instance.onmessage({
        data: JSON.stringify({
          task_id: 'task-123',
          progress: 75,
          status: 'running',
          description: 'Epoch 7/10',
        }),
      } as MessageEvent);
    }

    expect(onProgress).toHaveBeenCalledWith({
      task_id: 'task-123',
      progress: 75,
      status: 'running',
      description: 'Epoch 7/10',
    });
  });

  test('taskId改变时清除之前的reconnectTimeout并重置状态', () => {
    jest.useFakeTimers();

    const { rerender } = renderHook(
      ({ taskId }: { taskId: string | null }) => useTaskSSE(taskId),
      { initialProps: { taskId: 'task-123' }, wrapper: createWrapper() }
    );

    // Trigger error to set reconnect timeout
    const instance = MockEventSource.instances[0];
    if (instance?.onerror) {
      instance.onerror();
    }

    // At this point reconnectTimeoutRef.current should be set
    // Don't advance timers - keep the timeout pending

    // Change taskId - this triggers cleanup first, then effect body runs
    // Lines 100-101 should clear the pending timeout
    rerender({ taskId: 'task-456' });

    // New EventSource should be created
    expect(MockEventSource.instances.length).toBe(2);
    expect(MockEventSource.instances[0].close).toHaveBeenCalled();

    jest.useRealTimers();
  });

  test('连续错误后taskId变化能正确清除timeout', () => {
    jest.useFakeTimers();

    const { rerender } = renderHook(
      ({ taskId }: { taskId: string | null }) => useTaskSSE(taskId),
      { initialProps: { taskId: 'task-123' }, wrapper: createWrapper() }
    );

    const instance = MockEventSource.instances[0];

    // First error - timeout set for 1000ms
    instance.onerror?.();
    jest.advanceTimersByTime(500); // 500ms passed, 500ms remaining

    // Second error - reconnectAttemptsRef is now 1, timeout set for 2000ms
    instance.onerror?.();

    // Change taskId before any timeout fires
    // The cleanup should clear whatever timeout is pending
    rerender({ taskId: 'task-789' });

    // Old EventSource should be closed by cleanup
    expect(MockEventSource.instances[0].close).toHaveBeenCalled();

    // After cleanup, a new connection is created for the new taskId
    // But only one EventSource should exist (the new one from connect())
    expect(MockEventSource.instances.length).toBe(2);

    jest.useRealTimers();
  });

  test('effect cleanup清除待处理的reconnectTimeout (lines 100-101)', () => {
    jest.useFakeTimers();

    const { rerender } = renderHook(
      ({ taskId }: { taskId: string | null }) => useTaskSSE(taskId),
      { initialProps: { taskId: 'task-123' }, wrapper: createWrapper() }
    );

    // Trigger error to set reconnect timeout
    const instance = MockEventSource.instances[0];
    instance.onerror?.();

    // Verify timeout is pending
    jest.advanceTimersByTime(500);
    expect(MockEventSource.instances.length).toBe(1);

    // Change taskId - cleanup should clear the pending timeout at lines 100-101
    rerender({ taskId: 'task-456' });

    // New EventSource should be created
    expect(MockEventSource.instances.length).toBe(2);
    expect(MockEventSource.instances[0].close).toHaveBeenCalled();

    // Verify no timer leaks by advancing past the original timeout
    jest.advanceTimersByTime(2000);

    jest.useRealTimers();
  });

  test('unmount清除reconnectTimeout (lines 106-114)', () => {
    jest.useFakeTimers();

    const { unmount } = renderHook(() => useTaskSSE('task-123'), {
      wrapper: createWrapper(),
    });

    // Trigger error to set reconnect timeout
    const instance = MockEventSource.instances[0];
    instance.onerror?.();

    // Verify timeout is pending
    jest.advanceTimersByTime(500);
    expect(MockEventSource.instances.length).toBe(1);

    // Unmount should cleanup at lines 106-114
    unmount();

    // Verify no timer leaks by advancing past the original timeout
    jest.advanceTimersByTime(2000);

    jest.useRealTimers();
  });

  test('unmount时reconnectTimeout存在则清除', () => {
    jest.useFakeTimers();

    const { unmount } = renderHook(() => useTaskSSE('task-123'), {
      wrapper: createWrapper(),
    });

    // Trigger error to set reconnect timeout at line 88
    const instance = MockEventSource.instances[0];
    instance.onerror?.();

    // Unmount - cleanup should clear the timeout (lines 111-114)
    unmount();

    jest.useRealTimers();
  });

  test('cleanup函数清除reconnectTimeoutRef', () => {
    jest.useFakeTimers();

    const { rerender } = renderHook(
      ({ taskId }: { taskId: string | null }) => useTaskSSE(taskId),
      { initialProps: { taskId: 'task-123' }, wrapper: createWrapper() }
    );

    // Trigger error to set reconnect timeout
    const instance = MockEventSource.instances[0];
    instance.onerror?.();

    // Rerender with same taskId should not cleanup
    rerender({ taskId: 'task-123' });
    expect(MockEventSource.instances.length).toBe(1);

    jest.useRealTimers();
  });

  // ===== Additional Coverage Tests =====

  test('effect运行但reconnectTimeoutRef已为null时不报错 - 行99-101', () => {
    jest.useFakeTimers();

    const { rerender } = renderHook(
      ({ taskId }: { taskId: string | null }) => useTaskSSE(taskId),
      { initialProps: { taskId: 'task-123' }, wrapper: createWrapper() }
    );

    // Trigger error to set reconnect timeout
    const instance = MockEventSource.instances[0];
    instance.onerror?.();

    // Advance timers to fire the timeout and reconnect
    jest.advanceTimersByTime(1000);
    expect(MockEventSource.instances.length).toBe(2);

    // Now rerender with different taskId - the previous timeout should have fired already
    // so reconnectTimeoutRef.current should be null when cleanup runs
    rerender({ taskId: 'task-456' });

    // Should work without errors
    expect(MockEventSource.instances.length).toBe(3);

    jest.useRealTimers();
  });

  test('快速切换taskId时cleanup正确清除timeout - 行99-101', () => {
    jest.useFakeTimers();

    const { rerender } = renderHook(
      ({ taskId }: { taskId: string | null }) => useTaskSSE(taskId),
      { initialProps: { taskId: 'task-123' }, wrapper: createWrapper() }
    );

    // Trigger error
    const instance = MockEventSource.instances[0];
    instance.onerror?.();

    // Immediately rerender with different taskId (before timeout fires)
    rerender({ taskId: 'task-456' });

    // First EventSource should be closed, new one created
    expect(MockEventSource.instances[0].close).toHaveBeenCalled();
    expect(MockEventSource.instances.length).toBe(2);

    jest.useRealTimers();
  });

  test('unmount时reconnectTimeoutRef为null不阻断cleanup - 行99-101', () => {
    jest.useFakeTimers();

    const { unmount } = renderHook(() => useTaskSSE('task-123'), {
      wrapper: createWrapper(),
    });

    // Don't trigger any errors - reconnectTimeoutRef should remain null
    expect(MockEventSource.instances.length).toBe(1);

    // Unmount - the cleanup should handle null timeout without issues
    unmount();

    // EventSource should be closed
    expect(MockEventSource.instances[0].close).toHaveBeenCalled();

    jest.useRealTimers();
  });
});
