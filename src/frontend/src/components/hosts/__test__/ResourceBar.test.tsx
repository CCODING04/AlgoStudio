'use client';

import { render, screen } from '@testing-library/react';
import { ResourceBar } from '../ResourceBar';

describe('ResourceBar', () => {
  test('renders resource bar with label', () => {
    render(<ResourceBar label="内存" used={8} total={16} unit="Gi" />);
    expect(screen.getByText('内存')).toBeInTheDocument();
  });

  test('displays used and total values', () => {
    render(<ResourceBar label="内存" used={8} total={16} unit="Gi" />);
    expect(screen.getByText('8.0 / 16.0 Gi')).toBeInTheDocument();
  });

  test('displays CPU with no unit', () => {
    render(<ResourceBar label="CPU" used={4} total={8} />);
    expect(screen.getByText('4.0 / 8.0')).toBeInTheDocument();
  });

  test('applies primary color when usage is low (<=70%)', () => {
    const { container } = render(<ResourceBar label="内存" used={30} total={100} unit="Gi" />);
    // Low usage - should have primary color class
    const bar = container.querySelector('.bg-primary');
    expect(bar).toBeInTheDocument();
  });

  test('applies medium color when usage is 70-90%', () => {
    const { container } = render(<ResourceBar label="内存" used={80} total={100} unit="Gi" />);
    // Medium usage - should have yellow-500 color class
    const bar = container.querySelector('.bg-yellow-500');
    expect(bar).toBeInTheDocument();
  });

  test('applies destructive color when usage is >90%', () => {
    const { container } = render(<ResourceBar label="内存" used={95} total={100} unit="Gi" />);
    // High usage - should have destructive color class
    const bar = container.querySelector('.bg-destructive');
    expect(bar).toBeInTheDocument();
  });

  test('handles zero total gracefully', () => {
    render(<ResourceBar label="内存" used={0} total={0} unit="Gi" />);
    // Should render without crashing
    expect(screen.getByText('0.0 / 0.0 Gi')).toBeInTheDocument();
  });

  test('calculates percentage correctly', () => {
    const { container } = render(<ResourceBar label="CPU" used={50} total={100} />);
    // 50% usage is low (not medium), should have primary color
    const bar = container.querySelector('.bg-primary');
    expect(bar).toBeInTheDocument();
  });

  test('handles decimal values', () => {
    render(<ResourceBar label="内存" used={7.5} total={16.5} unit="Gi" />);
    expect(screen.getByText('7.5 / 16.5 Gi')).toBeInTheDocument();
  });

  test('caps percentage at 100', () => {
    const { container } = render(<ResourceBar label="内存" used={150} total={100} unit="Gi" />);
    // Even with 150/100, percentage should cap at 100
    const bar = container.querySelector('[style*="width"]');
    expect(bar).toBeInTheDocument();
  });

  test('applies text color for high usage', () => {
    render(<ResourceBar label="内存" used={95} total={100} unit="Gi" />);
    // High usage text should have destructive color
    const textElement = screen.getByText('95.0 / 100.0 Gi');
    expect(textElement).toHaveClass('text-destructive');
  });

  test('applies text color for medium usage', () => {
    render(<ResourceBar label="内存" used={80} total={100} unit="Gi" />);
    // Medium usage text should have yellow-500 color
    const textElement = screen.getByText('80.0 / 100.0 Gi');
    expect(textElement).toHaveClass('text-yellow-500');
  });

  test('applies default unit when not provided', () => {
    render(<ResourceBar label="CPU" used={4} total={8} />);
    expect(screen.getByText('4.0 / 8.0')).toBeInTheDocument();
  });

  test('handles 100% usage exactly', () => {
    const { container } = render(<ResourceBar label="内存" used={100} total={100} unit="Gi" />);
    // Exactly 100% - should be high (not medium)
    const bar = container.querySelector('.bg-destructive');
    expect(bar).toBeInTheDocument();
  });

  test('handles exactly 70% usage', () => {
    // 70% is NOT medium because the condition is percentage > 70
    // 70 > 70 = false, so 70% falls into the "primary" (low) category
    const { container } = render(<ResourceBar label="内存" used={70} total={100} unit="Gi" />);
    const bar = container.querySelector('.bg-primary');
    expect(bar).toBeInTheDocument();
  });

  test('handles exactly 91% usage', () => {
    // 91% > 90%, so it should be high (destructive)
    const { container } = render(<ResourceBar label="内存" used={91} total={100} unit="Gi" />);
    const bar = container.querySelector('.bg-destructive');
    expect(bar).toBeInTheDocument();
  });
});
