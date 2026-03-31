'use client';

import { render } from '@testing-library/react';
import { Providers } from '../providers';

// Mock dependencies
jest.mock('@tanstack/react-query', () => ({
  QueryClient: jest.fn().mockImplementation(() => ({
    setDefaultOptions: jest.fn(),
  })),
  QueryClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));

jest.mock('@/components/ui/sonner', () => ({
  Toaster: () => <div data-testid="toaster">Toaster</div>,
}));

describe('Providers', () => {
  test('renders children within QueryClientProvider', () => {
    const { container } = render(
      <Providers>
        <div data-testid="child-content">Child Content</div>
      </Providers>
    );

    expect(container.querySelector('[data-testid="child-content"]')).toBeInTheDocument();
  });

  test('renders Toaster component', () => {
    const { container } = render(
      <Providers>
        <div>Content</div>
      </Providers>
    );

    expect(container.querySelector('[data-testid="toaster"]')).toBeInTheDocument();
  });

  test('renders multiple children', () => {
    const { container } = render(
      <Providers>
        <div>First Child</div>
        <div>Second Child</div>
        <span>Third Child</span>
      </Providers>
    );

    expect(container.textContent).toContain('First Child');
    expect(container.textContent).toContain('Second Child');
    expect(container.textContent).toContain('Third Child');
  });

  test('renders with nested structure', () => {
    const { container } = render(
      <Providers>
        <div>
          <span>Nested Content</span>
        </div>
      </Providers>
    );

    expect(container.querySelector('span')?.textContent).toBe('Nested Content');
  });
});
