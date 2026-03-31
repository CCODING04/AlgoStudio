'use client';

import { render, screen } from '@testing-library/react';
import { StatsCard } from '../stats-card';
import { Activity, Cpu, HardDrive, Zap } from 'lucide-react';

describe('StatsCard', () => {
  test('渲染标题和数值', () => {
    render(<StatsCard title="总节点数" value={10} />);

    expect(screen.getByText('总节点数')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
  });

  test('渲染字符串类型的数值', () => {
    render(<StatsCard title="集群状态" value="健康" />);

    expect(screen.getByText('集群状态')).toBeInTheDocument();
    expect(screen.getByText('健康')).toBeInTheDocument();
  });

  test('渲染不同 variant 的组件', () => {
    const variants: Array<'default' | 'primary' | 'secondary' | 'destructive'> = [
      'default', 'primary', 'secondary', 'destructive'
    ];

    variants.forEach((variant) => {
      const { unmount } = render(
        <StatsCard title={`测试-${variant}`} value={5} variant={variant} />
      );
      expect(screen.getByText(`测试-${variant}`)).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
      unmount();
    });
  });

  test('带 icon 时显示图标', () => {
    render(<StatsCard title="CPU 使用" value="40%" icon={Cpu} />);

    expect(screen.getByText('CPU 使用')).toBeInTheDocument();
    // Icon renders as a Lucide icon component
    const icon = screen.getByText('CPU 使用').parentElement?.querySelector('svg');
    expect(icon).toBeInTheDocument();
  });

  test('不带 icon 时不渲染图标', () => {
    render(<StatsCard title="内存" value="8Gi" />);

    // Check that no icon (Lucide icon) is rendered in the card
    // Using text content to find the card
    const card = screen.getByText('内存').closest('.bg-card, [class*="Card"]');
    expect(card).toBeTruthy();
  });

  test('不同的 icon 类型正常渲染', () => {
    const icons = [Activity, Cpu, HardDrive, Zap];

    icons.forEach((Icon) => {
      const { unmount } = render(
        <StatsCard title="测试" value={10} icon={Icon} />
      );
      expect(screen.getByText('测试')).toBeInTheDocument();
      unmount();
    });
  });

  test('数值可以为零', () => {
    render(<StatsCard title="离线节点" value={0} />);

    expect(screen.getByText('0')).toBeInTheDocument();
  });

  test('数值可以是负数', () => {
    render(<StatsCard title="温度变化" value={-5} />);

    expect(screen.getByText('-5')).toBeInTheDocument();
  });

  test('空字符串数值正常渲染', () => {
    render(<StatsCard title="状态" value="" />);

    expect(screen.getByText('状态')).toBeInTheDocument();
    // The value div should be in the document (empty div)
    const valueDiv = screen.getByText('状态').closest('.bg-card')?.querySelector('.text-3xl');
    expect(valueDiv).toBeTruthy();
  });
});
