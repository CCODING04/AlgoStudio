'use client';

import { render, screen, waitFor } from '@testing-library/react';
import { RecentTasks } from '../recent-tasks';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock the useTasks hook
jest.mock('@/hooks/use-tasks', () => ({
  useTasks: jest.fn(),
}));

// Mock next/link
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

import { useTasks } from '@/hooks/use-tasks';

const mockUseTasks = useTasks as jest.MockedFunction<typeof useTasks>;

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
    algorithm_name: 'resnet50',
    algorithm_version: 'v1',
    status: 'running' as const,
    created_at: '2026-03-30T11:00:00Z',
    started_at: '2026-03-30T11:00:01Z',
    completed_at: null,
    assigned_node: '192.168.0.115',
    error: null,
    progress: 45,
  },
  {
    task_id: 'infer-001',
    task_type: 'infer' as const,
    algorithm_name: 'simple_classifier',
    algorithm_version: 'v2',
    status: 'pending' as const,
    created_at: '2026-03-30T12:00:00Z',
    started_at: null,
    completed_at: null,
    assigned_node: null,
    error: null,
    progress: 0,
  },
  {
    task_id: 'verify-001',
    task_type: 'verify' as const,
    algorithm_name: 'simple_classifier',
    algorithm_version: 'v1',
    status: 'failed' as const,
    created_at: '2026-03-30T13:00:00Z',
    started_at: '2026-03-30T13:00:01Z',
    completed_at: '2026-03-30T13:05:00Z',
    assigned_node: '192.168.0.126',
    error: 'Verification failed',
    progress: 0,
  },
  {
    task_id: 'train-003',
    task_type: 'train' as const,
    algorithm_name: 'yolo_v3',
    algorithm_version: 'v1',
    status: 'cancelled' as const,
    created_at: '2026-03-30T14:00:00Z',
    started_at: '2026-03-30T14:00:01Z',
    completed_at: '2026-03-30T14:10:00Z',
    assigned_node: '192.168.0.115',
    error: 'Cancelled by user',
    progress: 20,
  },
];

describe('RecentTasks', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('显示加载状态', () => {
    mockUseTasks.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    expect(screen.getByText('加载中...')).toBeInTheDocument();
  });

  test('显示暂无任务记录', () => {
    mockUseTasks.mockReturnValue({
      data: [],
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    expect(screen.getByText('暂无任务记录')).toBeInTheDocument();
  });

  test('显示最近 5 个任务', () => {
    mockUseTasks.mockReturnValue({
      data: mockTasks,
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    // Should show 5 tasks + 1 "View All" link = 6 total links
    const links = screen.getAllByRole('link');
    expect(links.length).toBe(6);
  });

  test('显示正确的任务类型标签', () => {
    mockUseTasks.mockReturnValue({
      data: [mockTasks[0]], // train task
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    expect(screen.getByText('训练')).toBeInTheDocument();
  });

  test('显示推理任务类型', () => {
    mockUseTasks.mockReturnValue({
      data: [mockTasks[2]], // infer task
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    expect(screen.getByText('推理')).toBeInTheDocument();
  });

  test('显示验证任务类型', () => {
    mockUseTasks.mockReturnValue({
      data: [mockTasks[3]], // verify task
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    expect(screen.getByText('验证')).toBeInTheDocument();
  });

  test('显示已完成状态的任务', () => {
    mockUseTasks.mockReturnValue({
      data: [mockTasks[0]],
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    expect(screen.getByText('已完成')).toBeInTheDocument();
  });

  test('显示运行中状态的任务', () => {
    mockUseTasks.mockReturnValue({
      data: [mockTasks[1]],
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    expect(screen.getByText('运行中')).toBeInTheDocument();
  });

  test('显示失败状态的任务', () => {
    mockUseTasks.mockReturnValue({
      data: [mockTasks[3]],
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    expect(screen.getByText('失败')).toBeInTheDocument();
  });

  test('显示已取消状态的任务', () => {
    mockUseTasks.mockReturnValue({
      data: [mockTasks[4]],
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    expect(screen.getByText('已取消')).toBeInTheDocument();
  });

  test('显示待处理状态的任务', () => {
    mockUseTasks.mockReturnValue({
      data: [mockTasks[2]],
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    expect(screen.getByText('待处理')).toBeInTheDocument();
  });

  test('显示算法名称和版本', () => {
    mockUseTasks.mockReturnValue({
      data: [mockTasks[0]],
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    expect(screen.getByText('simple_classifier v1')).toBeInTheDocument();
  });

  test('显示进度百分比', () => {
    mockUseTasks.mockReturnValue({
      data: [mockTasks[1]],
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    expect(screen.getByText('45%')).toBeInTheDocument();
  });

  test('链接指向正确的任务详情页', () => {
    mockUseTasks.mockReturnValue({
      data: [mockTasks[0]],
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    // Get the link that points to task detail (not the "View All" link)
    const taskLinks = screen.getAllByRole('link').filter(link =>
      link.getAttribute('href') === '/tasks/train-001'
    );
    expect(taskLinks.length).toBe(1);
    expect(taskLinks[0]).toHaveAttribute('href', '/tasks/train-001');
  });

  test('显示查看全部链接', () => {
    mockUseTasks.mockReturnValue({
      data: mockTasks,
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    expect(screen.getByText(/查看全部/i)).toBeInTheDocument();
  });

  test('处理未知的任务状态使用pending作为默认值', () => {
    mockUseTasks.mockReturnValue({
      data: [{
        task_id: 'task-unknown',
        task_type: 'train',
        algorithm_name: 'test',
        algorithm_version: 'v1',
        status: 'unknown_status' as any,
        created_at: '2026-03-30T10:00:00Z',
        started_at: null,
        completed_at: null,
        assigned_node: null,
        error: null,
        progress: null,
      }],
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    // Should use pending as default status
    expect(screen.getByText('待处理')).toBeInTheDocument();
  });

  test('处理未知的任务类型使用原始值', () => {
    mockUseTasks.mockReturnValue({
      data: [{
        task_id: 'task-unknown-type',
        task_type: 'custom_type' as any,
        algorithm_name: 'test',
        algorithm_version: 'v1',
        status: 'pending',
        created_at: '2026-03-30T10:00:00Z',
        started_at: null,
        completed_at: null,
        assigned_node: null,
        error: null,
        progress: null,
      }],
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    // Should display the raw task_type value
    expect(screen.getByText('custom_type')).toBeInTheDocument();
  });

  test('处理progress为null时不显示进度', () => {
    mockUseTasks.mockReturnValue({
      data: [{
        task_id: 'task-no-progress',
        task_type: 'train',
        algorithm_name: 'test',
        algorithm_version: 'v1',
        status: 'pending',
        created_at: '2026-03-30T10:00:00Z',
        started_at: null,
        completed_at: null,
        assigned_node: null,
        error: null,
        progress: null,
      }],
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    // Should not display any progress percentage
    expect(screen.queryByText('%')).not.toBeInTheDocument();
  });

  test('处理tasks为undefined', () => {
    mockUseTasks.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<RecentTasks />, { wrapper: createWrapper() });

    // Should show empty state when tasks is undefined
    expect(screen.getByText('暂无任务记录')).toBeInTheDocument();
  });
});
