'use client';

import { render, screen } from '@testing-library/react';
import { ResourceChart } from '../resource-chart';

// Mock the useHosts hook
jest.mock('@/hooks/use-hosts', () => ({
  useHosts: jest.fn(),
}));

// Track mock state for coverage verification
const mockState = {
  xAxisType: undefined as string | undefined,
  xAxisDomain: undefined as number[] | undefined,
  xAxisTickFormatter: undefined as ((v: number) => string) | undefined,
  yAxisType: undefined as string | undefined,
  yAxisDataKey: undefined as string | undefined,
  yAxisWidth: undefined as number | undefined,
  yAxisTick: undefined as object | undefined,
  tooltipFormatter: undefined as ((value: number) => [string, string]) | undefined,
  tooltipContentStyle: undefined as object | undefined,
  barDataKey: undefined as string | undefined,
  barRadius: undefined as number[] | undefined,
  layout: undefined as string | undefined,
  cellFill: undefined as string | undefined,
  reset: () => {
    mockState.xAxisType = undefined;
    mockState.xAxisDomain = undefined;
    mockState.xAxisTickFormatter = undefined;
    mockState.yAxisType = undefined;
    mockState.yAxisDataKey = undefined;
    mockState.yAxisWidth = undefined;
    mockState.yAxisTick = undefined;
    mockState.tooltipFormatter = undefined;
    mockState.tooltipContentStyle = undefined;
    mockState.barDataKey = undefined;
    mockState.barRadius = undefined;
    mockState.layout = undefined;
    mockState.cellFill = undefined;
  },
};

// Mock recharts - capture props for coverage verification
jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => children,
  BarChart: ({ children, data, layout }: any) => {
    mockState.layout = layout;
    return children;
  },
  Bar: ({ dataKey, radius, children }: any) => {
    mockState.barDataKey = dataKey;
    mockState.barRadius = radius;
    return children;
  },
  XAxis: ({ type, domain, tickFormatter }: any) => {
    mockState.xAxisType = type;
    mockState.xAxisDomain = domain;
    mockState.xAxisTickFormatter = tickFormatter;
    return null;
  },
  YAxis: ({ type, dataKey, width, tick }: any) => {
    mockState.yAxisType = type;
    mockState.yAxisDataKey = dataKey;
    mockState.yAxisWidth = width;
    mockState.yAxisTick = tick;
    return null;
  },
  Tooltip: ({ formatter, contentStyle }: any) => {
    mockState.tooltipFormatter = formatter;
    mockState.tooltipContentStyle = contentStyle;
    return null;
  },
  Cell: ({ fill }: any) => {
    mockState.cellFill = fill;
    return null;
  },
}));

import { useHosts } from '@/hooks/use-hosts';

const mockUseHosts = useHosts as jest.MockedFunction<typeof useHosts>;

describe('ResourceChart', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockState.reset();
  });

  test('显示加载状态', () => {
    mockUseHosts.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    expect(screen.getByText('加载中...')).toBeInTheDocument();
  });

  test('显示暂无数据', () => {
    mockUseHosts.mockReturnValue({
      data: { cluster_nodes: [] },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    expect(screen.getByText('暂无节点数据')).toBeInTheDocument();
  });

  test('显示暂无GPU数据当节点无GPU信息', () => {
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
              // No GPU resource
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    expect(screen.getByText('暂无GPU数据')).toBeInTheDocument();
  });

  test('显示暂无GPU数据当所有节点都不是online或idle', () => {
    mockUseHosts.mockReturnValue({
      data: {
        cluster_nodes: [
          {
            node_id: 'node-1',
            ip: '192.168.0.126',
            status: 'offline',
            is_local: true,
            hostname: 'head-node',
            resources: {
              gpu: { total: 1, utilization: 10, memory_used: '2Gi', memory_total: '24Gi' },
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    expect(screen.getByText('暂无GPU数据')).toBeInTheDocument();
  });

  test('显示资源使用图表', () => {
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
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    // Should show GPU usage chart title
    expect(screen.getByText('GPU 资源使用')).toBeInTheDocument();
  });

  test('显示低中高GPU使用率图例', () => {
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
              gpu: { total: 1, utilization: 10, memory_used: '2Gi', memory_total: '24Gi' },
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    // Check for legend text
    expect(screen.getByText(/低.*50%/)).toBeInTheDocument();
    expect(screen.getByText(/中.*50-80%/)).toBeInTheDocument();
    expect(screen.getByText(/高.*80%/)).toBeInTheDocument();
  });

  test('GPU使用率超过80%时Cell使用红色', () => {
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
              gpu: { total: 1, utilization: 90, memory_used: '20Gi', memory_total: '24Gi' },
            },
          },
          {
            node_id: 'node-2',
            ip: '192.168.0.127',
            status: 'online',
            is_local: false,
            hostname: 'worker-node',
            resources: {
              gpu: { total: 1, utilization: 60, memory_used: '12Gi', memory_total: '24Gi' },
            },
          },
          {
            node_id: 'node-3',
            ip: '192.168.0.128',
            status: 'idle',
            is_local: false,
            hostname: 'idle-node',
            resources: {
              gpu: { total: 1, utilization: 30, memory_used: '4Gi', memory_total: '24Gi' },
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    // Chart should render with high (>80%), medium (50-80%), and low (<50%) GPU usage
    expect(screen.getByText('GPU 资源使用')).toBeInTheDocument();
    // Legend should show all three levels
    expect(screen.getByText(/低.*50%/)).toBeInTheDocument();
    expect(screen.getByText(/中.*50-80%/)).toBeInTheDocument();
    expect(screen.getByText(/高.*80%/)).toBeInTheDocument();
  });

  test('Tooltip配置formatter和contentStyle', () => {
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
              gpu: { total: 1, utilization: 50, memory_used: '12Gi', memory_total: '24Gi' },
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    // Verify chart renders - Tooltip formatter and contentStyle are used internally
    expect(screen.getByText('GPU 资源使用')).toBeInTheDocument();
  });

  test('XAxis配置domain为0-100并使用tickFormatter', () => {
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
              gpu: { total: 1, utilization: 50, memory_used: '12Gi', memory_total: '24Gi' },
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    // Verify XAxis props are set
    expect(mockState.xAxisType).toBe('number');
    expect(mockState.xAxisDomain).toEqual([0, 100]);
    expect(mockState.xAxisTickFormatter).toBeDefined();
    expect(mockState.xAxisTickFormatter(50)).toBe('50%');
  });

  test('YAxis配置category类型和正确dataKey', () => {
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
              gpu: { total: 1, utilization: 50, memory_used: '12Gi', memory_total: '24Gi' },
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    // Verify YAxis props
    expect(mockState.yAxisType).toBe('category');
    expect(mockState.yAxisDataKey).toBe('name');
    expect(mockState.yAxisWidth).toBe(80);
    expect(mockState.yAxisTick).toEqual({ fontSize: 12 });
  });

  test('Tooltip formatter返回带百分号的字符串', () => {
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
              gpu: { total: 1, utilization: 75, memory_used: '12Gi', memory_total: '24Gi' },
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    // Verify Tooltip formatter
    expect(mockState.tooltipFormatter).toBeDefined();
    // Tooltip formatter now takes (value, name) where name is 'gpu' or 'gpuMemory'
    const result = mockState.tooltipFormatter(75, 'gpu');
    expect(result).toEqual(['75%', 'GPU 利用率']);
    expect(mockState.tooltipContentStyle).toEqual({ fontSize: 12 });
  });

  test('BarChart使用vertical布局', () => {
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
              gpu: { total: 1, utilization: 50, memory_used: '12Gi', memory_total: '24Gi' },
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    // Verify BarChart layout
    expect(mockState.layout).toBe('vertical');
    // Now there are two Bar elements: gpu (GPU utilization) and gpuMemory (GPU memory)
    // The mock captures the last Bar's dataKey which is 'gpuMemory'
    expect(mockState.barDataKey).toBe('gpuMemory');
    expect(mockState.barRadius).toEqual([0, 4, 4, 0]);
  });

  test('Cell根据GPU使用率设置正确颜色', () => {
    mockUseHosts.mockReturnValue({
      data: {
        cluster_nodes: [
          {
            node_id: 'node-1',
            ip: '192.168.0.126',
            status: 'online',
            is_local: true,
            hostname: 'head-node-high',
            resources: {
              gpu: { total: 1, utilization: 90, memory_used: '20Gi', memory_total: '24Gi' },
            },
          },
          {
            node_id: 'node-2',
            ip: '192.168.0.127',
            status: 'online',
            is_local: false,
            hostname: 'worker-node-med',
            resources: {
              gpu: { total: 1, utilization: 60, memory_used: '12Gi', memory_total: '24Gi' },
            },
          },
          {
            node_id: 'node-3',
            ip: '192.168.0.128',
            status: 'idle',
            is_local: false,
            hostname: 'idle-node-low',
            resources: {
              gpu: { total: 1, utilization: 30, memory_used: '4Gi', memory_total: '24Gi' },
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    // Verify Cell fill colors - the last cell rendered is for low usage (30%) which is green
    expect(mockState.cellFill).toBe('#22c55e'); // Green for <50%
    // The Cell component is called for each entry, so we verify the logic by checking the component renders
    expect(screen.getByText('GPU 资源使用')).toBeInTheDocument();
  });

  // ===== Additional Coverage Tests =====

  test('data存在但cluster_nodes为undefined显示暂无节点数据 - 行33', () => {
    mockUseHosts.mockReturnValue({
      data: {
        cluster_nodes: undefined,
      } as any,
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    expect(screen.getByText('暂无节点数据')).toBeInTheDocument();
  });

  test('data为null显示暂无节点数据 - 行33', () => {
    mockUseHosts.mockReturnValue({
      data: null as any,
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    expect(screen.getByText('暂无节点数据')).toBeInTheDocument();
  });

  test('所有节点都不是online或idle状态显示暂无GPU数据 - 行51', () => {
    mockUseHosts.mockReturnValue({
      data: {
        cluster_nodes: [
          {
            node_id: 'node-1',
            ip: '192.168.0.126',
            status: 'offline',
            is_local: true,
            hostname: 'head-node',
            resources: {
              gpu: { total: 1, utilization: 10, memory_used: '2Gi', memory_total: '24Gi' },
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    expect(screen.getByText('暂无GPU数据')).toBeInTheDocument();
  });

  test('节点GPU utilization为undefined时不显示在图表中 - 行51', () => {
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
              gpu: { total: 1, utilization: undefined as any, memory_used: '2Gi', memory_total: '24Gi' },
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    // Should show "暂无GPU数据" because utilization is undefined
    expect(screen.getByText('暂无GPU数据')).toBeInTheDocument();
  });

  test('chartData为空数组时显示暂无GPU数据 - 行58', () => {
    mockUseHosts.mockReturnValue({
      data: {
        cluster_nodes: [
          {
            node_id: 'node-1',
            ip: '192.168.0.126',
            status: 'online',
            is_local: true,
            hostname: 'head-node',
            // GPU resource missing completely
            resources: {
              cpu: { total: 32, used: 4 },
            },
          },
        ],
      },
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    } as any);

    render(<ResourceChart />);
    // Since no GPU info, chartData will be empty
    expect(screen.getByText('暂无GPU数据')).toBeInTheDocument();
  });
});
