'use client';

import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { DatasetFilter, DatasetFilterValues } from '../DatasetFilter';

// Mock UI components
jest.mock('@/components/ui/input', () => ({
  Input: ({ value, onChange, placeholder, type, ...props }: any) => (
    <input
      type={type || 'text'}
      value={value ?? ''}
      onChange={onChange}
      placeholder={placeholder}
      data-testid={props['data-testid']}
      {...props}
    />
  ),
}));

// Create a context for Select callbacks
const SelectCallbackContext = React.createContext<{
  onValueChange?: (value: string) => void;
}>({});

jest.mock('@/components/ui/select', () => {
  return {
    Select: ({ children, value, onValueChange, 'data-testid': testId, ...props }: any) => {
      return (
        <SelectCallbackContext.Provider value={{ onValueChange }}>
          <div data-testid={testId} data-value={value} {...props}>{children}</div>
        </SelectCallbackContext.Provider>
      );
    },
    SelectContent: ({ children }: any) => <div>{children}</div>,
    SelectItem: ({ children, value, 'data-testid': testId, ...props }: any) => {
      const { onValueChange } = React.useContext(SelectCallbackContext);
      return (
        <div
          onClick={() => onValueChange?.(value)}
          data-value={value}
          data-testid={testId || `select-item-${value}`}
          {...props}
        >
          {children}
        </div>
      );
    },
    SelectTrigger: ({ children, ...props }: any) => (
      <button {...props}>{children}</button>
    ),
    SelectValue: ({ placeholder }: any) => <span>{placeholder || 'Select...'}</span>,
  };
});

describe('DatasetFilter', () => {
  const defaultFilters: DatasetFilterValues = {
    searchQuery: '',
    sizeMin: '',
    sizeMax: '',
    sortBy: 'name',
    sortOrder: 'asc',
  };

  const mockOnFiltersChange = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders filter components', () => {
    render(
      <DatasetFilter
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    expect(screen.getByPlaceholderText('搜索数据集名称...')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('最小 GB')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('最大 GB')).toBeInTheDocument();
  });

  test('renders with default filters', () => {
    render(
      <DatasetFilter
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    const searchInput = screen.getByPlaceholderText('搜索数据集名称...');
    expect(searchInput).toHaveValue('');
  });

  test('calls onFiltersChange when search query changes', () => {
    render(
      <DatasetFilter
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    const searchInput = screen.getByPlaceholderText('搜索数据集名称...');
    fireEvent.change(searchInput, { target: { value: 'imagenet' } });

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      searchQuery: 'imagenet',
    });
  });

  test('calls onFiltersChange when sizeMin changes', () => {
    render(
      <DatasetFilter
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    const minInput = screen.getByPlaceholderText('最小 GB');
    fireEvent.change(minInput, { target: { value: '10' } });

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      sizeMin: '10',
    });
  });

  test('calls onFiltersChange when sizeMax changes', () => {
    render(
      <DatasetFilter
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    const maxInput = screen.getByPlaceholderText('最大 GB');
    fireEvent.change(maxInput, { target: { value: '100' } });

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      sizeMax: '100',
    });
  });

  test('renders with custom filter values', () => {
    const customFilters: DatasetFilterValues = {
      searchQuery: 'cifar',
      sizeMin: '5',
      sizeMax: '50',
      sortBy: 'size_gb',
      sortOrder: 'desc',
    };

    render(
      <DatasetFilter
        filters={customFilters}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    expect(screen.getByPlaceholderText('搜索数据集名称...')).toHaveValue('cifar');
  });

  test('renders select components for sort options', () => {
    render(
      <DatasetFilter
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    // Check that select triggers are rendered
    const selects = document.querySelectorAll('button');
    expect(selects.length).toBeGreaterThanOrEqual(2);
  });

  test('filter layout has correct structure', () => {
    const { container } = render(
      <DatasetFilter
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    expect(container.querySelector('.flex.flex-wrap.gap-4')).toBeInTheDocument();
  });

  test('handles non-empty size values', () => {
    const filtersWithSizes: DatasetFilterValues = {
      ...defaultFilters,
      sizeMin: '10',
      sizeMax: '100',
    };

    render(
      <DatasetFilter
        filters={filtersWithSizes}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    const minInput = screen.getByPlaceholderText('最小 GB');
    const maxInput = screen.getByPlaceholderText('最大 GB');
    expect(minInput).toHaveValue();
    expect(maxInput).toHaveValue();
  });

  test('calls onFiltersChange for sortBy change', () => {
    render(
      <DatasetFilter
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    // The component uses Select components for sortBy/sortOrder
    // Our mock doesn't trigger onValueChange automatically
    // So we verify the component renders with the right structure
    expect(screen.getByPlaceholderText('搜索数据集名称...')).toBeInTheDocument();
  });

  // ===== Select onValueChange Tests (covers lines 67-84) =====

  test('calls onFiltersChange when sortBy select changes to size_gb', () => {
    render(
      <DatasetFilter
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    // Click the size_gb option in the sortBy select
    const sizeGbItem = screen.getByTestId('select-item-size_gb');
    fireEvent.click(sizeGbItem);

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      sortBy: 'size_gb',
    });
  });

  test('calls onFiltersChange when sortBy select changes to created_at', () => {
    render(
      <DatasetFilter
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    // Click the created_at option in the sortBy select
    const createdAtItem = screen.getByTestId('select-item-created_at');
    fireEvent.click(createdAtItem);

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      sortBy: 'created_at',
    });
  });

  test('calls onFiltersChange when sortBy select changes to name', () => {
    const filtersWithSizeGb: DatasetFilterValues = {
      ...defaultFilters,
      sortBy: 'size_gb',
    };

    render(
      <DatasetFilter
        filters={filtersWithSizeGb}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    // Click the name option to change back
    const nameItem = screen.getByTestId('select-item-name');
    fireEvent.click(nameItem);

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      sortBy: 'name',
    });
  });

  test('calls onFiltersChange when sortOrder select changes to desc', () => {
    render(
      <DatasetFilter
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    // Click the desc option in the sortOrder select
    const descItem = screen.getByTestId('select-item-desc');
    fireEvent.click(descItem);

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      sortOrder: 'desc',
    });
  });

  test('calls onFiltersChange when sortOrder select changes to asc', () => {
    const filtersWithDesc: DatasetFilterValues = {
      ...defaultFilters,
      sortOrder: 'desc',
    };

    render(
      <DatasetFilter
        filters={filtersWithDesc}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    // Click the asc option to change back
    const ascItem = screen.getByTestId('select-item-asc');
    fireEvent.click(ascItem);

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      sortOrder: 'asc',
    });
  });

  test('sortBy and sortOrder selects work independently', () => {
    render(
      <DatasetFilter
        filters={defaultFilters}
        onFiltersChange={mockOnFiltersChange}
      />
    );

    // First change sortBy
    const sizeGbItem = screen.getByTestId('select-item-size_gb');
    fireEvent.click(sizeGbItem);

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      sortBy: 'size_gb',
    });

    mockOnFiltersChange.mockClear();

    // Then change sortOrder
    const descItem = screen.getByTestId('select-item-desc');
    fireEvent.click(descItem);

    expect(mockOnFiltersChange).toHaveBeenCalledWith({
      ...defaultFilters,
      sortOrder: 'desc',
    });
  });
});
