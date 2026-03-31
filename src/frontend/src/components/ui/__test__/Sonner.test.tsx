'use client';

import { render } from '@testing-library/react';
import { Toaster } from '../sonner';

// Mock sonner module
jest.mock('sonner', () => ({
  Toaster: ({ position, toastOptions }: { position?: string; toastOptions?: object }) => (
    <div data-testid="sonner-toaster" data-position={position}>
      Mocked Sonner Toaster
    </div>
  ),
}));

describe('Sonner Toaster', () => {
  test('渲染 Toaster 组件', () => {
    const { getByTestId } = render(<Toaster />);
    expect(getByTestId('sonner-toaster')).toBeInTheDocument();
  });

  test('Toaster 包含正确位置配置', () => {
    const { getByTestId } = render(<Toaster />);
    expect(getByTestId('sonner-toaster')).toHaveAttribute('data-position', 'bottom-right');
  });

  test('Toaster 渲染文本内容', () => {
    const { getByText } = render(<Toaster />);
    expect(getByText('Mocked Sonner Toaster')).toBeInTheDocument();
  });

  test('多次渲染 Toaster', () => {
    const { getAllByTestId } = render(<><Toaster /><Toaster /></>);
    expect(getAllByTestId('sonner-toaster')).toHaveLength(2);
  });

  test('Toaster 组件无子元素时正常渲染', () => {
    const { getByTestId } = render(<Toaster />);
    const toaster = getByTestId('sonner-toaster');
    expect(toaster.children).toHaveLength(0);
  });
});
