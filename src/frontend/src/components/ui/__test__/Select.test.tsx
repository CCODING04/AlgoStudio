'use client';

import React from 'react';
import { render, screen } from '@testing-library/react';

// Mock the Radix select primitive BEFORE importing the component
jest.mock('@radix-ui/react-select', () => {
  const { forwardRef } = React;
  return {
    __esModule: true,
    Root: ({ children }: { children?: React.ReactNode }) => <div data-testid="select-root">{children}</div>,
    Group: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
    Value: ({ children }: { children?: React.ReactNode }) => <span data-testid="select-value">{children}</span>,
    Trigger: forwardRef(({ children, className, ...props }: any, ref) => (
      <button ref={ref} className={className} data-testid="select-trigger" {...props}>{children}</button>
    )),
    Portal: ({ children }: { children?: React.ReactNode }) => <div data-testid="select-portal">{children}</div>,
    Content: forwardRef(({ children, className, position, ...props }: any, ref) => (
      <div ref={ref} className={className} data-position={position} data-testid="select-content" {...props}>{children}</div>
    )),
    Viewport: ({ children, className }: { children?: React.ReactNode; className?: string }) => (
      <div className={className} data-testid="select-viewport">{children}</div>
    ),
    Label: forwardRef(({ children, className }: { children?: React.ReactNode; className?: string }, ref) => (
      <div ref={ref} className={className} data-testid="select-label">{children}</div>
    )),
    Item: forwardRef(({ children, className, value, ...props }: any, ref) => (
      <div ref={ref} className={className} data-testid="select-item" data-value={value} {...props}>{children}</div>
    )),
    Separator: forwardRef(({ className }: { className?: string }, ref) => (
      <div ref={ref} className={className} data-testid="select-separator" />
    )),
    ItemText: ({ children }: { children?: React.ReactNode }) => <span>{children}</span>,
    ItemIndicator: ({ children }: { children?: React.ReactNode }) => <span data-testid="item-indicator">{children}</span>,
    ScrollUpButton: forwardRef(({ children, className, ...props }: any, ref) => (
      <div ref={ref} className={className} data-testid="scroll-up-button" {...props}>{children}</div>
    )),
    ScrollDownButton: forwardRef(({ children, className, ...props }: any, ref) => (
      <div ref={ref} className={className} data-testid="scroll-down-button" {...props}>{children}</div>
    )),
    Icon: ({ children }: { children?: React.ReactNode }) => <span data-testid="select-icon">{children}</span>,
  };
});

// Now import the components to test
import {
  Select,
  SelectGroup,
  SelectValue,
  SelectTrigger,
  SelectScrollUpButton,
  SelectScrollDownButton,
  SelectContent,
  SelectLabel,
  SelectItem,
  SelectSeparator,
} from '../select';

describe('Select Components', () => {
  describe('SelectLabel and SelectSeparator', () => {
    test('renders SelectLabel', () => {
      render(<SelectLabel>Test Label</SelectLabel>);
      expect(screen.getByText('Test Label')).toBeInTheDocument();
    });

    test('SelectLabel applies custom className', () => {
      const { container } = render(<SelectLabel className="custom-class">Test</SelectLabel>);
      expect(container.firstChild).toHaveClass('custom-class');
    });

    test('SelectLabel applies default styling classes', () => {
      const { container } = render(<SelectLabel>Test</SelectLabel>);
      expect(container.firstChild).toHaveClass('py-1.5');
      expect(container.firstChild).toHaveClass('pl-8');
      expect(container.firstChild).toHaveClass('pr-2');
      expect(container.firstChild).toHaveClass('text-sm');
      expect(container.firstChild).toHaveClass('font-semibold');
    });

    test('renders SelectSeparator', () => {
      const { container } = render(<SelectSeparator />);
      expect(container.firstChild).toBeInTheDocument();
    });

    test('SelectSeparator applies custom className', () => {
      const { container } = render(<SelectSeparator className="custom-class" />);
      expect(container.firstChild).toHaveClass('custom-class');
    });

    test('SelectSeparator applies default styling classes', () => {
      const { container } = render(<SelectSeparator />);
      expect(container.firstChild).toHaveClass('-mx-1');
      expect(container.firstChild).toHaveClass('my-1');
      expect(container.firstChild).toHaveClass('h-px');
      expect(container.firstChild).toHaveClass('bg-muted');
    });

    test('SelectLabel forwards ref correctly', () => {
      const ref = React.createRef<HTMLDivElement>();
      render(<SelectLabel ref={ref}>Test</SelectLabel>);
      expect(ref.current).toBeInstanceOf(HTMLDivElement);
    });

    test('SelectSeparator forwards ref correctly', () => {
      const ref = React.createRef<HTMLDivElement>();
      render(<SelectSeparator ref={ref} />);
      expect(ref.current).toBeInstanceOf(HTMLDivElement);
    });
  });

  describe('SelectTrigger', () => {
    test('renders SelectTrigger with children', () => {
      render(<SelectTrigger><SelectValue placeholder="Select..." /></SelectTrigger>);
      expect(screen.getByTestId('select-trigger')).toBeInTheDocument();
      expect(screen.getByTestId('select-value')).toBeInTheDocument();
    });

    test('SelectTrigger applies custom className', () => {
      render(
        <SelectTrigger className="custom-trigger-class">
          <SelectValue placeholder="Test" />
        </SelectTrigger>
      );
      expect(screen.getByTestId('select-trigger')).toHaveClass('custom-trigger-class');
    });

    test('SelectTrigger forwards ref correctly', () => {
      const ref = React.createRef<HTMLButtonElement>();
      render(
        <SelectTrigger ref={ref}>
          <SelectValue placeholder="Test" />
        </SelectTrigger>
      );
      expect(ref.current).toBeInstanceOf(HTMLButtonElement);
    });

    test('SelectTrigger has default styling classes', () => {
      render(
        <SelectTrigger>
          <SelectValue placeholder="Test" />
        </SelectTrigger>
      );
      const trigger = screen.getByTestId('select-trigger');
      expect(trigger).toHaveClass('flex');
      expect(trigger).toHaveClass('h-10');
      expect(trigger).toHaveClass('w-full');
      expect(trigger).toHaveClass('items-center');
    });
  });

  describe('SelectScrollUpButton', () => {
    test('renders SelectScrollUpButton', () => {
      render(<SelectScrollUpButton>Scroll Up Content</SelectScrollUpButton>);
      expect(screen.getByTestId('scroll-up-button')).toBeInTheDocument();
    });

    test('SelectScrollUpButton applies custom className', () => {
      render(
        <SelectScrollUpButton className="custom-scroll-class">Content</SelectScrollUpButton>
      );
      expect(screen.getByTestId('scroll-up-button')).toHaveClass('custom-scroll-class');
    });

    test('SelectScrollUpButton forwards ref correctly', () => {
      const ref = React.createRef<HTMLDivElement>();
      render(<SelectScrollUpButton ref={ref}>Content</SelectScrollUpButton>);
      expect(ref.current).toBeInstanceOf(HTMLDivElement);
    });
  });

  describe('SelectScrollDownButton', () => {
    test('renders SelectScrollDownButton', () => {
      render(<SelectScrollDownButton>Scroll Down Content</SelectScrollDownButton>);
      expect(screen.getByTestId('scroll-down-button')).toBeInTheDocument();
    });

    test('SelectScrollDownButton applies custom className', () => {
      render(
        <SelectScrollDownButton className="custom-scroll-class">Content</SelectScrollDownButton>
      );
      expect(screen.getByTestId('scroll-down-button')).toHaveClass('custom-scroll-class');
    });

    test('SelectScrollDownButton forwards ref correctly', () => {
      const ref = React.createRef<HTMLDivElement>();
      render(<SelectScrollDownButton ref={ref}>Content</SelectScrollDownButton>);
      expect(ref.current).toBeInstanceOf(HTMLDivElement);
    });
  });

  describe('SelectContent', () => {
    test('renders SelectContent with children', () => {
      render(
        <SelectContent>
          <SelectScrollUpButton />
          <SelectItem value="option1">Option 1</SelectItem>
          <SelectScrollDownButton />
        </SelectContent>
      );
      expect(screen.getByTestId('select-content')).toBeInTheDocument();
    });

    test('SelectContent applies default position className', () => {
      render(<SelectContent>Content</SelectContent>);
      expect(screen.getByTestId('select-content')).toHaveClass('relative');
      expect(screen.getByTestId('select-content')).toHaveClass('z-50');
    });

    test('SelectContent applies custom className', () => {
      render(
        <SelectContent className="custom-content-class">Content</SelectContent>
      );
      expect(screen.getByTestId('select-content')).toHaveClass('custom-content-class');
    });

    test('SelectContent with position prop', () => {
      render(<SelectContent position="popper">Content</SelectContent>);
      expect(screen.getByTestId('select-content')).toHaveAttribute('data-position', 'popper');
    });

    test('SelectContent forwards ref correctly', () => {
      const ref = React.createRef<HTMLDivElement>();
      render(<SelectContent ref={ref}>Content</SelectContent>);
      expect(ref.current).toBeInstanceOf(HTMLDivElement);
    });
  });

  describe('SelectItem', () => {
    test('renders SelectItem with children', () => {
      render(<SelectItem value="test-value">Test Item</SelectItem>);
      expect(screen.getByTestId('select-item')).toBeInTheDocument();
      expect(screen.getByText('Test Item')).toBeInTheDocument();
    });

    test('SelectItem has correct data attributes', () => {
      render(<SelectItem value="my-value">Item</SelectItem>);
      expect(screen.getByTestId('select-item')).toHaveAttribute('data-value', 'my-value');
    });

    test('SelectItem applies custom className', () => {
      render(
        <SelectItem value="test" className="custom-item-class">Item</SelectItem>
      );
      expect(screen.getByTestId('select-item')).toHaveClass('custom-item-class');
    });

    test('SelectItem has default styling classes', () => {
      render(<SelectItem value="test">Item</SelectItem>);
      const item = screen.getByTestId('select-item');
      expect(item).toHaveClass('relative');
      expect(item).toHaveClass('flex');
      expect(item).toHaveClass('w-full');
      expect(item).toHaveClass('cursor-default');
    });

    test('SelectItem forwards ref correctly', () => {
      const ref = React.createRef<HTMLDivElement>();
      render(<SelectItem ref={ref} value="test">Item</SelectItem>);
      expect(ref.current).toBeInstanceOf(HTMLDivElement);
    });
  });

  describe('Select Value and Group', () => {
    test('SelectValue renders with placeholder', () => {
      render(<SelectValue placeholder="Choose an option" />);
      expect(screen.getByTestId('select-value')).toBeInTheDocument();
    });

    test('SelectGroup renders children', () => {
      render(
        <SelectGroup>
          <SelectLabel>Group Label</SelectLabel>
          <SelectItem value="item1">Item 1</SelectItem>
        </SelectGroup>
      );
      expect(screen.getByText('Group Label')).toBeInTheDocument();
      expect(screen.getByText('Item 1')).toBeInTheDocument();
    });
  });

  describe('Select integration', () => {
    test('Select with SelectTrigger and SelectContent', () => {
      render(
        <Select value="option1" onValueChange={() => {}}>
          <SelectTrigger>
            <SelectValue placeholder="Select..." />
          </SelectTrigger>
          <SelectContent>
            <SelectLabel>Options</SelectLabel>
            <SelectItem value="option1">Option 1</SelectItem>
            <SelectItem value="option2">Option 2</SelectItem>
            <SelectSeparator />
            <SelectItem value="option3">Option 3</SelectItem>
          </SelectContent>
        </Select>
      );
      expect(screen.getByTestId('select-trigger')).toBeInTheDocument();
    });
  });
});
