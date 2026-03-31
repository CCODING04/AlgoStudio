'use client';

import { render, screen, waitFor } from '@testing-library/react';
import { ClusterStatus } from '../cluster-status';

// Mock the useHosts hook
jest.mock('@/hooks/use-hosts', () => ({
  useHosts: jest.fn(),
}));

import { useHosts } from '@/hooks/use-hosts';

const mockUseHosts = useHosts as jest.MockedFunction<typeof useHosts>;

describe('ClusterStatus', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('显示加载状态', () => {
    mockUseHosts.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ClusterStatus />);
    expect(screen.getByText('加载中...')).toBeInTheDocument();
  });

  test('显示暂无节点连接', () => {
    mockUseHosts.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Failed'),
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ClusterStatus />);
    expect(screen.getByText('暂无节点连接')).toBeInTheDocument();
  });

  test('显示集群状态信息', () => {
    mockUseHosts.mockReturnValue({
      data: {
        cluster_nodes: [
          {
            node_id: 'node-1',
            ip: '192.168.0.126',
            status: 'online',
            is_local: true,
            hostname: 'head-node',
            resources: {
              cpu: { total: 32, used: 4, model: 'Intel i9' },
              gpu: { total: 1, utilization: 10, memory_used: '2Gi', memory_total: '24Gi' },
              memory: { total: '32Gi', used: '8Gi' },
            },
          },
          {
            node_id: 'node-2',
            ip: '192.168.0.115',
            status: 'idle',
            is_local: false,
            hostname: 'worker-node',
            resources: {
              cpu: { total: 32, used: 0, model: 'Intel i9' },
              gpu: { total: 1, utilization: 0, memory_used: '2Gi', memory_total: '24Gi' },
              memory: { total: '32Gi', used: '4Gi' },
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ClusterStatus />);

    expect(screen.getByText('总节点数')).toBeInTheDocument();
    expect(screen.getByText('在线节点')).toBeInTheDocument();
    expect(screen.getByText('离线节点')).toBeInTheDocument();
  });

  test('计算离线节点数', () => {
    mockUseHosts.mockReturnValue({
      data: {
        cluster_nodes: [
          {
            node_id: 'node-1',
            ip: '192.168.0.126',
            status: 'online',
            is_local: true,
            hostname: 'head-node',
            resources: {
              cpu: { total: 32, used: 4 },
              gpu: { total: 1, utilization: 10, memory_used: '2Gi', memory_total: '24Gi' },
              memory: { total: '32Gi', used: '8Gi' },
            },
          },
          {
            node_id: 'node-2',
            ip: '192.168.0.115',
            status: 'offline',
            is_local: false,
            hostname: 'worker-node',
            resources: {
              cpu: { total: 32, used: 0 },
              gpu: { total: 1, utilization: 0, memory_used: '2Gi', memory_total: '24Gi' },
              memory: { total: '32Gi', used: '0Gi' },
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ClusterStatus />);

    // Should show 2 total, 1 online, 1 offline
    // Use getAllByText since multiple badges show numbers
    const totalBadges = screen.getAllByText('2');
    expect(totalBadges.length).toBeGreaterThan(0);
    // Online and offline badges both show 1, so we check there are multiple "1" badges
    const oneBadges = screen.getAllByText('1');
    expect(oneBadges.length).toBeGreaterThanOrEqual(2);
  });

  test('处理cluster_nodes为undefined的情况', () => {
    mockUseHosts.mockReturnValue({
      data: {
        cluster_nodes: undefined,
      } as any,
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    });

    render(<ClusterStatus />);

    // Should show 0 nodes when cluster_nodes is undefined
    expect(screen.getByText('总节点数')).toBeInTheDocument();
    expect(screen.getByText('在线节点')).toBeInTheDocument();
    expect(screen.getByText('离线节点')).toBeInTheDocument();
  });

  test('处理gpu utilization为undefined的节点', () => {
    mockUseHosts.mockReturnValue({
      data: {
        cluster_nodes: [
          {
            node_id: 'node-1',
            ip: '192.168.0.126',
            status: 'online',
            is_local: true,
            hostname: 'head-node',
            resources: {
              cpu: { total: 32, used: 4 },
              // gpu is missing
              memory: { total: '32Gi', used: '8Gi' },
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ClusterStatus />);

    // Should render without crashing and show the node
    expect(screen.getByText('head-node')).toBeInTheDocument();
    // Should not show GPU utilization since it's undefined
    expect(screen.queryByText('%')).not.toBeInTheDocument();
  });

  test('处理空的cluster_nodes数组', () => {
    mockUseHosts.mockReturnValue({
      data: {
        cluster_nodes: [],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ClusterStatus />);

    // Should show 0 total, 0 online, 0 offline
    expect(screen.getByText('总节点数')).toBeInTheDocument();
    expect(screen.getByText('在线节点')).toBeInTheDocument();
    expect(screen.getByText('离线节点')).toBeInTheDocument();
  });
});
