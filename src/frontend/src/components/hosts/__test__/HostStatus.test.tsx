'use client';

import { render, screen } from '@testing-library/react';
import { HostStatus } from '../HostStatus';

describe('HostStatus', () => {
  test('显示在线状态', () => {
    render(<HostStatus status="online" />);
    expect(screen.getByText('在线')).toBeInTheDocument();
  });

  test('显示离线状态', () => {
    render(<HostStatus status="offline" />);
    expect(screen.getByText('离线')).toBeInTheDocument();
  });

  test('显示空闲状态', () => {
    render(<HostStatus status="idle" />);
    expect(screen.getByText('空闲')).toBeInTheDocument();
  });

  test('显示忙碌状态', () => {
    render(<HostStatus status="busy" />);
    expect(screen.getByText('忙碌')).toBeInTheDocument();
  });

  test('显示错误状态', () => {
    render(<HostStatus status="error" />);
    expect(screen.getByText('错误')).toBeInTheDocument();
  });

  test('离线状态作为默认值', () => {
    render(<HostStatus status="unknown" as any />);
    expect(screen.getByText('离线')).toBeInTheDocument();
  });

  test('显示最后在线时间当offline有lastSeen', () => {
    render(<HostStatus status="offline" lastSeen="2026-03-30T10:00:00Z" />);
    expect(screen.getByText('离线')).toBeInTheDocument();
    expect(screen.getByText(/最后在线:/)).toBeInTheDocument();
  });

  test('不显示最后在线时间当status不是offline', () => {
    render(<HostStatus status="online" lastSeen="2026-03-30T10:00:00Z" />);
    expect(screen.getByText('在线')).toBeInTheDocument();
    expect(screen.queryByText(/最后在线:/)).not.toBeInTheDocument();
  });

  test('不显示最后在线时间当没有lastSeen', () => {
    render(<HostStatus status="offline" />);
    expect(screen.getByText('离线')).toBeInTheDocument();
    expect(screen.queryByText(/最后在线:/)).not.toBeInTheDocument();
  });
});
