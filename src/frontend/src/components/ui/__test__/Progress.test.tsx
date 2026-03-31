'use client';

import { render, screen } from '@testing-library/react';
import { Progress } from '../progress';

describe('Progress', () => {
  test('渲染 Progress 组件', () => {
    render(<Progress />);
    const progressBar = document.querySelector('.relative.h-4.w-full.overflow-hidden.rounded-full.bg-secondary');
    expect(progressBar).toBeInTheDocument();
  });

  test('默认 value 为 0', () => {
    render(<Progress />);
    const innerBar = document.querySelector('.h-full.bg-primary');
    expect(innerBar).toBeInTheDocument();
    expect(innerBar).toHaveStyle({ width: '0%' });
  });

  test('应用 value prop', () => {
    render(<Progress value={50} />);
    const innerBar = document.querySelector('.h-full.bg-primary');
    expect(innerBar).toHaveStyle({ width: '50%' });
  });

  test('应用 max prop', () => {
    render(<Progress value={50} max={200} />);
    const innerBar = document.querySelector('.h-full.bg-primary');
    // 50/200 * 100 = 25%
    expect(innerBar).toHaveStyle({ width: '25%' });
  });

  test('value 超过 max 时限制为 100%', () => {
    render(<Progress value={150} max={100} />);
    const innerBar = document.querySelector('.h-full.bg-primary');
    expect(innerBar).toHaveStyle({ width: '100%' });
  });

  test('value 为负数时限制为 0%', () => {
    render(<Progress value={-10} />);
    const innerBar = document.querySelector('.h-full.bg-primary');
    expect(innerBar).toHaveStyle({ width: '0%' });
  });

  test('应用自定义 className', () => {
    const { container } = render(<Progress className="custom-progress" />);
    const progressWrapper = container.querySelector('.relative.h-4.w-full.overflow-hidden.rounded-full.bg-secondary');
    expect(progressWrapper).toHaveClass('custom-progress');
  });

  test('Progress 组件有正确的结构', () => {
    const { container } = render(<Progress />);
    // 外层容器
    const outer = container.querySelector('.relative.h-4.w-full.overflow-hidden.rounded-full.bg-secondary');
    expect(outer).toBeInTheDocument();
    // 内层进度条
    const inner = container.querySelector('.h-full.bg-primary');
    expect(inner).toBeInTheDocument();
  });

  test('进度条具有 transition 样式', () => {
    const { container } = render(<Progress />);
    const innerBar = container.querySelector('.h-full.bg-primary.transition-all.duration-300.ease-in-out');
    expect(innerBar).toBeInTheDocument();
  });

  test('value 为 100 时显示满进度', () => {
    render(<Progress value={100} />);
    const innerBar = document.querySelector('.h-full.bg-primary');
    expect(innerBar).toHaveStyle({ width: '100%' });
  });

  test('使用默认 max 值 100', () => {
    render(<Progress value={75} />);
    const innerBar = document.querySelector('.h-full.bg-primary');
    expect(innerBar).toHaveStyle({ width: '75%' });
  });

  test('传递额外 props', () => {
    const { container } = render(<Progress data-testid="progress-bar" aria-label="Test progress" />);
    const outer = container.querySelector('.relative.h-4.w-full.overflow-hidden.rounded-full.bg-secondary');
    expect(outer).toHaveAttribute('data-testid', 'progress-bar');
    expect(outer).toHaveAttribute('aria-label', 'Test progress');
  });
});
