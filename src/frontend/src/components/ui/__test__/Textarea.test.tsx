'use client';

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Textarea } from '../textarea';

describe('Textarea', () => {
  test('renders textarea element', () => {
    render(<Textarea />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  test('renders with placeholder', () => {
    render(<Textarea placeholder="Enter text here" />);
    expect(screen.getByPlaceholderText('Enter text here')).toBeInTheDocument();
  });

  test('renders with default value', () => {
    render(<Textarea defaultValue="Initial text" />);
    expect(screen.getByDisplayValue('Initial text')).toBeInTheDocument();
  });

  test('applies custom className', () => {
    const { container } = render(<Textarea className="custom-class" />);
    const textarea = container.querySelector('textarea');
    expect(textarea?.className).toContain('custom-class');
  });

  test('forwards ref correctly', () => {
    const ref = React.createRef<HTMLTextAreaElement>();
    render(<Textarea ref={ref} />);
    expect(ref.current).toBeInstanceOf(HTMLTextAreaElement);
  });

  test('accepts disabled prop', () => {
    render(<Textarea disabled />);
    const textarea = screen.getByRole('textbox');
    expect(textarea).toBeDisabled();
  });

  test('has correct base styling classes', () => {
    const { container } = render(<Textarea />);
    const textarea = container.querySelector('textarea');
    expect(textarea?.className).toContain('min-h-[80px]');
    expect(textarea?.className).toContain('w-full');
    expect(textarea?.className).toContain('rounded-md');
    expect(textarea?.className).toContain('border');
  });

  test('passes through additional props', () => {
    const { container } = render(
      <Textarea
        id="test-textarea"
        name="test"
        rows={5}
        data-testid="test-textarea"
      />
    );
    const textarea = container.querySelector('textarea');
    expect(textarea).toHaveAttribute('id', 'test-textarea');
    expect(textarea).toHaveAttribute('name', 'test');
    expect(textarea).toHaveAttribute('rows', '5');
  });

  test('handles onChange event', () => {
    const handleChange = jest.fn();
    render(<Textarea onChange={handleChange} />);
    const textarea = screen.getByRole('textbox');

    fireEvent.change(textarea, { target: { value: 'Hello' } });

    expect(handleChange).toHaveBeenCalled();
  });
});
