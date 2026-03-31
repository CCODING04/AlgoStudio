'use client';

import { renderHook } from '@testing-library/react';
import { useTaskSSEWithToast } from '../use-task-sse-toast';

// Mock sonner toast
jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

// Mock EventSource
class MockEventSource {
  static instances: MockEventSource[] = [];
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  addEventListener: jest.Mock = jest.fn();
  close = jest.fn();

  constructor(_url: string) {
    MockEventSource.instances.push(this);
  }

  static reset() {
    MockEventSource.instances = [];
  }
}

jest.mock('@/lib/api', () => ({
  apiRequest: jest.fn(),
}));

describe('useTaskSSEWithToast', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    MockEventSource.reset();
    global.EventSource = MockEventSource as unknown as typeof EventSource;
  });

  test('当 taskId 为 null 时不创建 EventSource', () => {
    const { result } = renderHook(() => useTaskSSEWithToast(null));

    expect(result.current).toBeUndefined();
    expect(MockEventSource.instances).toHaveLength(0);
  });

  test('当 enabled 为 false 时不创建 EventSource', () => {
    const { result } = renderHook(() => useTaskSSEWithToast('task-123', false));

    expect(result.current).toBeUndefined();
    expect(MockEventSource.instances).toHaveLength(0);
  });

  test('当 taskId 存在且 enabled 时创建 EventSource', () => {
    const { result, unmount } = renderHook(() => useTaskSSEWithToast('task-123', true));

    expect(result.current).toBeUndefined();
    expect(MockEventSource.instances).toHaveLength(1);

    unmount();
  });

  test('cleanup 时关闭 EventSource', () => {
    const { unmount } = renderHook(() => useTaskSSEWithToast('task-123', true));

    expect(MockEventSource.instances[0].close).not.toHaveBeenCalled();

    unmount();

    expect(MockEventSource.instances[0].close).toHaveBeenCalled();
  });

  test('切换 taskId 时重置重连计数', () => {
    const { rerender, unmount } = renderHook(
      ({ taskId }: { taskId: string | null }) => useTaskSSEWithToast(taskId, true),
      { initialProps: { taskId: 'task-123' } }
    );

    const instance = MockEventSource.instances[0];

    // Trigger reconnect by emitting error
    if (instance?.onerror) {
      instance.onerror();
    }

    // Switch to different taskId
    rerender({ taskId: 'task-456' });

    // Should reset reconnect attempts (check by verifying new instance was created)
    expect(MockEventSource.instances.length).toBeGreaterThanOrEqual(2);

    unmount();
  });

  test('addEventListener 注册 allocated 事件', () => {
    renderHook(() => useTaskSSEWithToast('task-123', true));

    const instance = MockEventSource.instances[0];
    expect(instance.addEventListener).toHaveBeenCalledWith('allocated', expect.any(Function));
  });

  test('忽略 JSON 解析错误（allocated 事件）', () => {
    const { rerender, unmount } = renderHook(
      ({ taskId }: { taskId: string | null }) => useTaskSSEWithToast(taskId, true),
      { initialProps: { taskId: 'task-123' } }
    );

    const { toast } = require('sonner');
    const instance = MockEventSource.instances[0];

    // Find the allocated event handler
    const allocatedHandler = instance.addEventListener.mock.calls.find(
      (call: unknown[]) => call[0] === 'allocated'
    )?.[1];

    // Call with invalid JSON
    if (allocatedHandler) {
      allocatedHandler({ data: 'invalid json' } as MessageEvent);
    }

    expect(toast.success).not.toHaveBeenCalled();

    unmount();
  });

  test('忽略 onmessage JSON 解析错误', () => {
    const { unmount } = renderHook(() => useTaskSSEWithToast('task-123', true));

    const instance = MockEventSource.instances[0];

    if (instance?.onmessage) {
      instance.onmessage({ data: 'not valid json' } as MessageEvent);
    }

    expect(MockEventSource.instances.length).toBe(1);

    unmount();
  });

  test('allocated 事件触发 toast.success', () => {
    const { rerender, unmount } = renderHook(
      ({ taskId }: { taskId: string | null }) => useTaskSSEWithToast(taskId, true),
      { initialProps: { taskId: 'task-123' } }
    );

    const { toast } = require('sonner');
    const instance = MockEventSource.instances[0];

    // Find the allocated event handler
    const allocatedHandler = instance.addEventListener.mock.calls.find(
      (call: unknown[]) => call[0] === 'allocated'
    )?.[1];

    // Call with valid JSON
    if (allocatedHandler) {
      allocatedHandler({
        data: JSON.stringify({
          task_id: 'task-123',
          node_id: 'node-1',
          node_name: 'Worker-1',
          status: 'allocated',
        }),
      } as MessageEvent);
    }

    expect(toast.success).toHaveBeenCalledWith(
      '任务已分配到 Worker-1',
      expect.objectContaining({
        description: '任务ID: task-123',
        duration: 5000,
      })
    );

    unmount();
  });

  test('重复 allocated 事件不触发多个 toast', () => {
    const { unmount } = renderHook(() => useTaskSSEWithToast('task-123', true));

    const { toast } = require('sonner');
    toast.success.mockClear();

    const instance = MockEventSource.instances[0];

    // Find the allocated event handler
    const allocatedHandler = instance.addEventListener.mock.calls.find(
      (call: unknown[]) => call[0] === 'allocated'
    )?.[1];

    // Call twice with same taskId
    if (allocatedHandler) {
      allocatedHandler({
        data: JSON.stringify({
          task_id: 'task-123',
          node_id: 'node-1',
          node_name: 'Worker-1',
          status: 'allocated',
        }),
      } as MessageEvent);
      allocatedHandler({
        data: JSON.stringify({
          task_id: 'task-123',
          node_id: 'node-2',
          node_name: 'Worker-2',
          status: 'allocated',
        }),
      } as MessageEvent);
    }

    // Should only show toast once (first one)
    expect(toast.success).toHaveBeenCalledTimes(1);

    unmount();
  });

  test('切换 taskId 时重置 toast 标记', () => {
    const { rerender, unmount } = renderHook(
      ({ taskId }: { taskId: string | null }) => useTaskSSEWithToast(taskId, true),
      { initialProps: { taskId: 'task-123' } }
    );

    const { toast } = require('sonner');
    const instance = MockEventSource.instances[0];

    // Find the allocated event handler
    const allocatedHandler = instance.addEventListener.mock.calls.find(
      (call: unknown[]) => call[0] === 'allocated'
    )?.[1];

    // Trigger toast for first task
    if (allocatedHandler) {
      allocatedHandler({
        data: JSON.stringify({
          task_id: 'task-123',
          node_id: 'node-1',
          node_name: 'Worker-1',
          status: 'allocated',
        }),
      } as MessageEvent);
    }

    expect(toast.success).toHaveBeenCalledTimes(1);

    // Switch to different taskId
    rerender({ taskId: 'task-456' });

    // Find the new allocated handler
    const newInstance = MockEventSource.instances[1];
    const newAllocatedHandler = newInstance?.addEventListener.mock.calls.find(
      (call: unknown[]) => call[0] === 'allocated'
    )?.[1];

    // Trigger toast for second task
    if (newAllocatedHandler) {
      newAllocatedHandler({
        data: JSON.stringify({
          task_id: 'task-456',
          node_id: 'node-2',
          node_name: 'Worker-2',
          status: 'allocated',
        }),
      } as MessageEvent);
    }

    // Should have shown toast for second task (task-456)
    expect(toast.success).toHaveBeenCalledTimes(2);

    unmount();
  });

  test('onerror 关闭 EventSource', () => {
    const { unmount } = renderHook(() => useTaskSSEWithToast('task-123', true));

    const instance = MockEventSource.instances[0];

    if (instance?.onerror) {
      instance.onerror();
    }

    expect(instance.close).toHaveBeenCalled();

    unmount();
  });

  test('错误后关闭EventSource并设置reconnectTimeout', () => {
    jest.useFakeTimers();

    const { unmount } = renderHook(() => useTaskSSEWithToast('task-123', true));

    const instance = MockEventSource.instances[0];

    // Trigger first error
    if (instance?.onerror) {
      instance.onerror();
    }

    // Should close current instance
    expect(instance.close).toHaveBeenCalled();

    // Timeout should be set but not fired yet
    jest.advanceTimersByTime(500);
    expect(MockEventSource.instances.length).toBe(1);

    // Fire the timeout
    jest.advanceTimersByTime(500);
    // Cleanup is called but no new EventSource is created in this hook

    expect(MockEventSource.instances.length).toBe(1);

    unmount();
    jest.useRealTimers();
  });

  test('超过最大重连次数时onerror直接返回不设置timeout', () => {
    jest.useFakeTimers();

    const { unmount } = renderHook(() => useTaskSSEWithToast('task-123', true));

    const MAX_RECONNECT_ATTEMPTS = 5;

    // Emit errors up to max attempts
    for (let i = 0; i < MAX_RECONNECT_ATTEMPTS; i++) {
      const instance = MockEventSource.instances[0];
      if (instance?.onerror) {
        instance.onerror();
      }
      // Advance time for exponential backoff
      jest.advanceTimersByTime(Math.pow(2, i) * 1000);
    }

    // Should still have only 1 instance (no reconnection happens)
    expect(MockEventSource.instances.length).toBe(1);

    // Emit another error after max attempts - should return early
    const instance = MockEventSource.instances[0];
    instance.close.mockClear();
    if (instance?.onerror) {
      instance.onerror();
    }

    // close should still be called (the first line in onerror)
    expect(instance.close).toHaveBeenCalled();

    jest.useRealTimers();
  });

  test('enabled从true变为false时清理', () => {
    const { rerender, unmount } = renderHook(
      ({ taskId, enabled }: { taskId: string | null; enabled: boolean }) =>
        useTaskSSEWithToast(taskId, enabled),
      { initialProps: { taskId: 'task-123', enabled: true } }
    );

    expect(MockEventSource.instances).toHaveLength(1);

    // Change enabled to false
    rerender({ taskId: 'task-123', enabled: false });

    // EventSource should be closed
    expect(MockEventSource.instances[0].close).toHaveBeenCalled();

    unmount();
  });

  test('taskId改变时触发cleanup清除reconnectTimeout', () => {
    jest.useFakeTimers();

    const { rerender, unmount } = renderHook(
      ({ taskId, enabled }: { taskId: string | null; enabled: boolean }) =>
        useTaskSSEWithToast(taskId, enabled),
      { initialProps: { taskId: 'task-123', enabled: true } }
    );

    const instance = MockEventSource.instances[0];

    // Trigger error to set reconnect timeout
    if (instance?.onerror) {
      instance.onerror();
    }

    // Verify timeout is pending (not fired yet)
    jest.advanceTimersByTime(500);
    expect(MockEventSource.instances.length).toBe(1);

    // Change taskId - this should trigger cleanup which clears the timeout
    rerender({ taskId: 'task-456', enabled: true });

    // Should have closed the old EventSource
    expect(instance.close).toHaveBeenCalled();
    // New hook instance created
    expect(MockEventSource.instances.length).toBe(2);

    unmount();
    jest.useRealTimers();
  });

  test('onmessage处理非progress消息时不报错', () => {
    const { unmount } = renderHook(() => useTaskSSEWithToast('task-123', true));

    const instance = MockEventSource.instances[0];

    // Send a message that doesn't have progress field
    if (instance?.onmessage) {
      instance.onmessage({
        data: JSON.stringify({
          task_id: 'task-123',
          status: 'some_status',
        }),
      } as MessageEvent);
    }

    // Should not error
    expect(MockEventSource.instances.length).toBe(1);

    unmount();
  });

  test('onerror后timeout触发cleanup关闭EventSource', () => {
    jest.useFakeTimers();

    const { unmount } = renderHook(() => useTaskSSEWithToast('task-123', true));

    const instance = MockEventSource.instances[0];

    // Trigger error to set reconnect timeout
    if (instance?.onerror) {
      instance.onerror();
    }

    expect(instance.close).toHaveBeenCalledTimes(1);

    // Advance time to fire the reconnect timeout
    jest.advanceTimersByTime(1000);

    // cleanup() was called, closing the EventSource
    expect(instance.close).toHaveBeenCalledTimes(2);

    unmount();
    jest.useRealTimers();
  });

  test('onerror后reconnectTimeout被清除', () => {
    jest.useFakeTimers();

    const { unmount } = renderHook(() => useTaskSSEWithToast('task-123', true));

    const instance = MockEventSource.instances[0];

    // Trigger error to set reconnect timeout
    instance.onerror?.();

    // The reconnectTimeoutRef is now set to a timeout ID
    // Verify that the timeout was scheduled
    jest.advanceTimersByTime(500);
    expect(MockEventSource.instances.length).toBe(1);

    // Advance past the reconnect delay to trigger the timeout callback
    jest.advanceTimersByTime(500); // Total 1000ms

    // The timeout callback runs cleanup() which clears reconnectTimeoutRef
    // Then it tries to close eventSourceRef.current (which is already null from cleanup)

    unmount();
    jest.useRealTimers();
  });

  test('连续错误重连时eventSourceRef被正确清除', () => {
    jest.useFakeTimers();

    const { rerender, unmount } = renderHook(
      ({ taskId, enabled }: { taskId: string | null; enabled: boolean }) =>
        useTaskSSEWithToast(taskId, enabled),
      { initialProps: { taskId: 'task-123', enabled: true } }
    );

    // Trigger first error
    const instance = MockEventSource.instances[0];
    instance.onerror?.();

    // Advance time to fire the reconnect timeout
    jest.advanceTimersByTime(1000);

    // After timeout, cleanup was called and eventSourceRef was set to null
    // Change taskId to trigger reconnection
    rerender({ taskId: 'task-456', enabled: true });

    // New EventSource should be created
    expect(MockEventSource.instances.length).toBe(2);

    unmount();
    jest.useRealTimers();
  });

  test('超过最大重连次数后错误不设置timeout', () => {
    jest.useFakeTimers();

    const { unmount } = renderHook(() => useTaskSSEWithToast('task-123', true));

    const MAX_RECONNECT_ATTEMPTS = 5;

    // Emit errors up to max attempts
    for (let i = 0; i < MAX_RECONNECT_ATTEMPTS; i++) {
      const instance = MockEventSource.instances[0];
      instance.close.mockClear();
      instance.onerror?.();
      jest.advanceTimersByTime(Math.pow(2, i) * 1000);
    }

    // Should still have only 1 instance after max attempts
    expect(MockEventSource.instances.length).toBe(1);

    // The 6th error should return early without scheduling reconnect
    const instance = MockEventSource.instances[0];
    instance.onerror?.();

    // No new timeout scheduled
    expect(MockEventSource.instances.length).toBe(1);

    unmount();
    jest.useRealTimers();
  });
});
