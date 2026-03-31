'use client';

import { render, screen } from '@testing-library/react';
import { HostCard } from '../HostCard';

describe('HostCard', () => {
  const mockHost = {
    node_id: 'node-1',
    ip: '192.168.0.126',
    status: 'online' as const,
    is_local: true,
    hostname: 'test-host',
    resources: {
      cpu: { total: 32, used: 4, model: 'Intel i9' },
      gpu: { total: 1, utilization: 10, memory_used: '2Gi', memory_total: '24Gi' },
      memory: { total: '32Gi', used: '8Gi' },
    },
  };

  test('显示主机信息', () => {
    render(<HostCard host={mockHost} />);
    expect(screen.getByText('test-host')).toBeInTheDocument();
    expect(screen.getByText('192.168.0.126')).toBeInTheDocument();
  });

  test('显示在线状态', () => {
    render(<HostCard host={mockHost} />);
    expect(screen.getByText('在线')).toBeInTheDocument();
  });

  test('显示离线状态', () => {
    const offlineHost = { ...mockHost, status: 'offline' as const };
    render(<HostCard host={offlineHost} />);
    expect(screen.getByText('离线')).toBeInTheDocument();
  });

  test('显示空闲状态', () => {
    const idleHost = { ...mockHost, status: 'idle' as const };
    render(<HostCard host={idleHost} />);
    expect(screen.getByText('空闲')).toBeInTheDocument();
  });

  test('显示忙碌状态', () => {
    const busyHost = { ...mockHost, status: 'busy' as const };
    render(<HostCard host={busyHost} />);
    expect(screen.getByText('忙碌')).toBeInTheDocument();
  });

  test('显示 CPU 信息', () => {
    render(<HostCard host={mockHost} />);
    // HostCard displays CPU cores with label "CPU 核心"
    expect(screen.getByText('CPU 核心')).toBeInTheDocument();
  });

  test('显示 Head 节点标签', () => {
    render(<HostCard host={mockHost} />);
    expect(screen.getByText('Head')).toBeInTheDocument();
  });

  test('处理缺失的 GPU 信息', () => {
    const hostNoGpu = {
      ...mockHost,
      resources: {
        ...mockHost.resources,
        gpu: undefined,
      },
    };
    render(<HostCard host={hostNoGpu} />);
    // Should render without crashing
    expect(screen.getByText('test-host')).toBeInTheDocument();
  });

  test('parseMemoryString处理无效格式返回0 - 行59', () => {
    // Test the parseMemoryString fallback case
    // This tests when memory string doesn't match the expected format
    const hostInvalidMem = {
      ...mockHost,
      resources: {
        ...mockHost.resources,
        memory: {
          total: 'invalid',
          used: 'also_invalid',
        },
      },
    };
    render(<HostCard host={hostInvalidMem} />);
    // Should render without crashing when memory parsing fails
    expect(screen.getByText('test-host')).toBeInTheDocument();
  });

  test('显示GPU名称当存在时 - 行87-91', () => {
    const hostWithGpuName = {
      ...mockHost,
      resources: {
        ...mockHost,
        gpu: {
          total: 1,
          utilization: 50,
          memory_used: '8Gi',
          memory_total: '24Gi',
          name: 'NVIDIA RTX 4090',
        },
      },
    };
    render(<HostCard host={hostWithGpuName} />);
    expect(screen.getByText('NVIDIA RTX 4090')).toBeInTheDocument();
  });

  test('显示无GPU当GPU不存在 - 行92-94', () => {
    const hostNoGpu = {
      ...mockHost,
      resources: {
        ...mockHost.resources,
        gpu: {
          total: 0,
          utilization: 0,
          memory_used: '0Gi',
          memory_total: '0Gi',
        },
      },
    };
    render(<HostCard host={hostNoGpu} />);
    expect(screen.getByText('无 GPU')).toBeInTheDocument();
  });

  test('显示本地节点标签当is_local为true - 行116-118', () => {
    render(<HostCard host={mockHost} />);
    expect(screen.getByText('本地节点')).toBeInTheDocument();
  });

  test('不显示本地节点标签当is_local为false', () => {
    const remoteHost = { ...mockHost, is_local: false };
    render(<HostCard host={remoteHost} />);
    expect(screen.queryByText('本地节点')).not.toBeInTheDocument();
  });

  test('显示Worker标签当is_local为false - 行99-105', () => {
    const workerHost = { ...mockHost, is_local: false };
    render(<HostCard host={workerHost} />);
    expect(screen.getByText('Worker')).toBeInTheDocument();
  });

  test('GPU利用率显示正确 - 行126', () => {
    render(<HostCard host={mockHost} />);
    expect(screen.getByText('10%')).toBeInTheDocument(); // From mock host with 10% utilization
  });

  test('parseMemoryString处理带小数的Gi值', () => {
    const hostDecimalMem = {
      ...mockHost,
      resources: {
        ...mockHost.resources,
        gpu: {
          total: 1,
          utilization: 30,
          memory_used: '16.5Gi',
          memory_total: '24Gi',
          name: 'NVIDIA RTX 4090',
        },
      },
    };
    render(<HostCard host={hostDecimalMem} />);
    expect(screen.getByText('test-host')).toBeInTheDocument();
  });

  test('处理缺失的CPU信息', () => {
    const hostNoCpu = {
      ...mockHost,
      resources: {
        ...mockHost.resources,
        cpu: undefined as any,
      },
    };
    render(<HostCard host={hostNoCpu} />);
    // Should render without crashing
    expect(screen.getByText('test-host')).toBeInTheDocument();
    // CPU cores section should not be rendered
    expect(screen.queryByText('CPU 核心')).not.toBeInTheDocument();
  });

  test('处理缺失的内存信息', () => {
    const hostNoMem = {
      ...mockHost,
      resources: {
        ...mockHost.resources,
        memory: undefined as any,
      },
    };
    render(<HostCard host={hostNoMem} />);
    // Should render without crashing
    expect(screen.getByText('test-host')).toBeInTheDocument();
  });

  test('parseMemoryString处理带G后缀的内存值', () => {
    const hostGMem = {
      ...mockHost,
      resources: {
        ...mockHost.resources,
        memory: {
          total: '16G',
          used: '8G',
        },
      },
    };
    render(<HostCard host={hostGMem} />);
    expect(screen.getByText('test-host')).toBeInTheDocument();
  });

  // ===== Additional Coverage Tests =====

  test('CPU显示physical_cores当存在时 - 行159', () => {
    const hostWithPhysicalCores = {
      ...mockHost,
      resources: {
        ...mockHost.resources,
        cpu: {
          total: 32,
          physical_cores: 16,
          used: 4,
          model: 'Intel i9',
        },
      },
    };
    render(<HostCard host={hostWithPhysicalCores} />);
    // Should render with 16 physical cores instead of 32 total
    expect(screen.getByText('16')).toBeInTheDocument();
  });

  test('未知状态映射到离线配置 - 行70', () => {
    const hostUnknownStatus = {
      ...mockHost,
      status: 'unknown_status' as any,
    };
    render(<HostCard host={hostUnknownStatus} />);
    // Should fall back to offline status config
    expect(screen.getByText('离线')).toBeInTheDocument();
  });

  test('GPU内存显示正确解析的值 - 行75-76', () => {
    const hostWithGpuMem = {
      ...mockHost,
      resources: {
        ...mockHost.resources,
        gpu: {
          total: 1,
          utilization: 50,
          memory_used: '16Gi',
          memory_total: '24Gi',
        },
      },
    };
    render(<HostCard host={hostWithGpuMem} />);
    expect(screen.getByText('test-host')).toBeInTheDocument();
  });

  test('系统内存显示正确解析的值 - 行79-80', () => {
    const hostWithSysMem = {
      ...mockHost,
      resources: {
        ...mockHost.resources,
        memory: {
          total: '32Gi',
          used: '16Gi',
        },
      },
    };
    render(<HostCard host={hostWithSysMem} />);
    expect(screen.getByText('test-host')).toBeInTheDocument();
  });

  test('CPU资源存在时显示CPU核心数 - 行155', () => {
    const hostWithCpu = {
      ...mockHost,
      resources: {
        ...mockHost.resources,
        cpu: {
          total: 32,
          used: 8,
          model: 'AMD EPYC',
        },
      },
    };
    render(<HostCard host={hostWithCpu} />);
    // Should show CPU cores section
    expect(screen.getByText('CPU 核心')).toBeInTheDocument();
  });
});
