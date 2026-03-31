'use client';

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Checkbox } from '../checkbox';

// Mock the Radix checkbox primitive
jest.mock('@radix-ui/react-checkbox', () => {
  const mockHandleClick = jest.fn();
  return {
    __esModule: true,
    Root: React.forwardRef<HTMLButtonElement, any>(
      ({ className, children, onClick, checked, disabled, ...props }, ref) => (
        <button
          ref={ref}
          type="button"
          role="checkbox"
          aria-checked={checked}
          disabled={disabled}
          className={className}
          onClick={onClick}
          {...props}
        >
          {children}
        </button>
      )
    ),
    Indicator: ({ children, className }: { children?: React.ReactNode; className?: string }) => (
      <div className={className}>{children}</div>
    ),
  };
});

describe('Checkbox', () => {
  test('renders checkbox', () => {
    render(<Checkbox />);
    expect(screen.getByRole('checkbox')).toBeInTheDocument();
  });

  test('renders checked state', () => {
    render(<Checkbox checked />);
    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toHaveAttribute('aria-checked', 'true');
  });

  test('renders unchecked state', () => {
    render(<Checkbox />);
    const checkbox = screen.getByRole('checkbox');
    // When unchecked, aria-checked is not present or is falsy
    expect(checkbox.getAttribute('aria-checked') ?? 'false').toBe('false');
  });

  test('applies custom className', () => {
    const { container } = render(<Checkbox className="custom-class" />);
    const checkbox = container.querySelector('button');
    expect(checkbox?.className).toContain('custom-class');
  });

  test('forwards ref correctly', () => {
    const ref = React.createRef<HTMLButtonElement>();
    render(<Checkbox ref={ref} />);
    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
  });

  test('is disabled when disabled prop is set', () => {
    render(<Checkbox disabled />);
    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeDisabled();
  });

  test('displays check icon when checked', () => {
    render(<Checkbox checked />);
    // The Check icon should be present when checked
    const icon = document.querySelector('svg');
    expect(icon).toBeInTheDocument();
  });
});
