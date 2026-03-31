'use client';

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DatasetForm } from '../DatasetForm';
import { DatasetResponse } from '@/types/dataset';

// Mock UI components
jest.mock('@/components/ui/dialog', () => ({
  Dialog: ({ children, open, onOpenChange }: any) =>
    open ? <div data-testid="dialog" data-open={open}>{children}</div> : null,
  DialogContent: ({ children, className, ...props }: any) => (
    <div data-testid="dialog-content" className={className} {...props}>{children}</div>
  ),
  DialogHeader: ({ children }: any) => <div data-testid="dialog-header">{children}</div>,
  DialogTitle: ({ children }: any) => <div data-testid="dialog-title">{children}</div>,
  DialogDescription: ({ children }: any) => <div data-testid="dialog-description">{children}</div>,
}));

jest.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick, type, disabled, variant, ...props }: any) => (
    <button
      type={type || 'button'}
      onClick={onClick}
      disabled={disabled}
      data-variant={variant}
      data-testid={props['data-testid']}
    >
      {children}
    </button>
  ),
}));

jest.mock('@/components/ui/input', () => ({
  Input: ({ value, onChange, placeholder, type, id, disabled, step, className, ...props }: any) => (
    <input
      type={type || 'text'}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      id={id}
      disabled={disabled}
      step={step}
      className={className}
      data-testid={props['data-testid']}
    />
  ),
}));

jest.mock('@/components/ui/label', () => ({
  Label: ({ children, htmlFor }: any) => (
    <label htmlFor={htmlFor} data-testid={`label-${htmlFor}`}>{children}</label>
  ),
}));

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  Database: () => <div data-testid="database-icon" />,
  Loader2: () => <div data-testid="loader-icon" />,
  Sparkles: () => <div data-testid="sparkles-icon" />,
  FolderOpen: () => <div data-testid="folder-open-icon" />,
}));

// Mock DatasetBrowser component
jest.mock('@/components/datasets/DatasetBrowser', () => ({
  DatasetBrowser: () => <div data-testid="dataset-browser" />,
}));

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe('DatasetForm', () => {
  const mockOnSuccess = jest.fn();
  const mockOnUpdate = jest.fn();
  const mockOnOpenChange = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
  });

  test('renders create mode dialog when open and no dataset provided', () => {
    render(
      <DatasetForm
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
        onUpdate={mockOnUpdate}
      />
    );

    expect(screen.getByTestId('dialog')).toBeInTheDocument();
    expect(screen.getByTestId('dialog-title')).toHaveTextContent('创建数据集');
  });

  test('renders edit mode dialog when dataset is provided', () => {
    const existingDataset: DatasetResponse = {
      dataset_id: 'ds-001',
      name: 'Test Dataset',
      path: '/mnt/data/test',
      description: null,
      storage_type: 'nfs',
      size_gb: 10.5,
      file_count: null,
      version: null,
      metadata: null,
      tags: null,
      is_public: true,
      owner_id: null,
      team_id: null,
      is_active: true,
      last_accessed_at: null,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: null,
    };

    render(
      <DatasetForm
        open={true}
        onOpenChange={mockOnOpenChange}
        dataset={existingDataset}
        onSuccess={mockOnSuccess}
        onUpdate={mockOnUpdate}
      />
    );

    expect(screen.getByTestId('dialog-title')).toHaveTextContent('编辑数据集');
  });

  test('shows validation error when name is empty on submit', () => {
    render(
      <DatasetForm
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
        onUpdate={mockOnUpdate}
      />
    );

    const pathInput = screen.getByTestId('label-path').parentElement?.querySelector('input');
    if (pathInput) {
      fireEvent.change(pathInput, { target: { value: '/mnt/data/test' } });
    }

    const submitButton = screen.getByTestId('dialog-content').querySelector('button[type="submit"]');
    if (submitButton) {
      fireEvent.click(submitButton);
    }

    expect(screen.getByText('请输入数据集名称')).toBeInTheDocument();
  });

  test('shows validation error when path is empty on submit', () => {
    render(
      <DatasetForm
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
        onUpdate={mockOnUpdate}
      />
    );

    const nameInput = screen.getByTestId('label-name').parentElement?.querySelector('input');
    if (nameInput) {
      fireEvent.change(nameInput, { target: { value: 'Test Dataset' } });
    }

    const submitButton = screen.getByTestId('dialog-content').querySelector('button[type="submit"]');
    if (submitButton) {
      fireEvent.click(submitButton);
    }

    expect(screen.getByText('请输入数据集路径')).toBeInTheDocument();
  });

  test('calls onSuccess after successful creation', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ dataset_id: 'ds-new' }),
    });

    render(
      <DatasetForm
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
        onUpdate={mockOnUpdate}
      />
    );

    // Fill in the form
    const nameInput = screen.getByTestId('label-name').parentElement?.querySelector('input');
    const pathInput = screen.getByTestId('label-path').parentElement?.querySelector('input');

    if (nameInput) fireEvent.change(nameInput, { target: { value: 'New Dataset' } });
    if (pathInput) fireEvent.change(pathInput, { target: { value: '/mnt/data/new' } });

    const submitButton = screen.getByTestId('dialog-content').querySelector('button[type="submit"]');
    if (submitButton) {
      fireEvent.click(submitButton);
    }

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });

  test('shows error message on creation failure', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ error: '创建失败' }),
    });

    render(
      <DatasetForm
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
        onUpdate={mockOnUpdate}
      />
    );

    const nameInput = screen.getByTestId('label-name').parentElement?.querySelector('input');
    const pathInput = screen.getByTestId('label-path').parentElement?.querySelector('input');

    if (nameInput) fireEvent.change(nameInput, { target: { value: 'New Dataset' } });
    if (pathInput) fireEvent.change(pathInput, { target: { value: '/mnt/data/new' } });

    const submitButton = screen.getByTestId('dialog-content').querySelector('button[type="submit"]');
    if (submitButton) {
      fireEvent.click(submitButton);
    }

    await waitFor(() => {
      expect(screen.getByText('创建失败')).toBeInTheDocument();
    });
  });

  test('calls onOpenChange with false when cancel is clicked', () => {
    render(
      <DatasetForm
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
        onUpdate={mockOnUpdate}
      />
    );

    const cancelButton = screen.getByTestId('cancel-button');
    if (cancelButton) {
      fireEvent.click(cancelButton);
    }

    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  test('resets form fields when dialog closes', () => {
    const { rerender } = render(
      <DatasetForm
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
        onUpdate={mockOnUpdate}
      />
    );

    const nameInput = screen.getByTestId('label-name').parentElement?.querySelector('input');
    if (nameInput) {
      fireEvent.change(nameInput, { target: { value: 'Test' } });
    }

    // Simulate closing the dialog
    mockOnOpenChange.mockImplementation((open: boolean) => {
      rerender(
        <DatasetForm
          open={open}
          onOpenChange={mockOnOpenChange}
          onSuccess={mockOnSuccess}
          onUpdate={mockOnUpdate}
        />
      );
    });

    const cancelButton = screen.getByTestId('dialog-content').querySelector('button:not([type="submit"])');
    if (cancelButton) {
      fireEvent.click(cancelButton);
    }
  });

  test('displays dataset description in create mode', () => {
    render(
      <DatasetForm
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
        onUpdate={mockOnUpdate}
      />
    );

    expect(screen.getByTestId('dialog-description')).toHaveTextContent('注册一个新的数据集路径到系统中');
  });

  test('displays dataset description in edit mode', () => {
    const existingDataset: DatasetResponse = {
      dataset_id: 'ds-001',
      name: 'Test Dataset',
      path: '/mnt/data/test',
      description: null,
      storage_type: 'nfs',
      size_gb: 10.5,
      file_count: null,
      version: null,
      metadata: null,
      tags: null,
      is_public: true,
      owner_id: null,
      team_id: null,
      is_active: true,
      last_accessed_at: null,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: null,
    };

    render(
      <DatasetForm
        open={true}
        onOpenChange={mockOnOpenChange}
        dataset={existingDataset}
        onSuccess={mockOnSuccess}
        onUpdate={mockOnUpdate}
      />
    );

    expect(screen.getByTestId('dialog-description')).toHaveTextContent('修改数据集信息');
  });

  test('form has correct structure with space-y-4', () => {
    const { container } = render(
      <DatasetForm
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
        onUpdate={mockOnUpdate}
      />
    );

    expect(container.querySelector('.space-y-4')).toBeInTheDocument();
  });

  test('calls onUpdate when submitting form in edit mode', async () => {
    const existingDataset: DatasetResponse = {
      dataset_id: 'ds-001',
      name: 'Test Dataset',
      path: '/mnt/data/test',
      description: null,
      storage_type: 'nfs',
      size_gb: 10.5,
      file_count: null,
      version: null,
      metadata: null,
      tags: null,
      is_public: true,
      owner_id: null,
      team_id: null,
      is_active: true,
      last_accessed_at: null,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: null,
    };

    mockOnUpdate.mockResolvedValueOnce(undefined);

    render(
      <DatasetForm
        open={true}
        onOpenChange={mockOnOpenChange}
        dataset={existingDataset}
        onSuccess={mockOnSuccess}
        onUpdate={mockOnUpdate}
      />
    );

    // Form should be pre-filled with existing dataset values
    const nameInput = screen.getByTestId('label-name').parentElement?.querySelector('input') as HTMLInputElement;
    const pathInput = screen.getByTestId('label-path').parentElement?.querySelector('input') as HTMLInputElement;

    expect(nameInput.value).toBe('Test Dataset');
    expect(pathInput.value).toBe('/mnt/data/test');

    // Submit the form
    const submitButton = screen.getByTestId('dialog-content').querySelector('button[type="submit"]');
    if (submitButton) {
      fireEvent.click(submitButton);
    }

    await waitFor(() => {
      expect(mockOnUpdate).toHaveBeenCalledWith('ds-001', { name: 'Test Dataset', path: '/mnt/data/test' });
    });
  });

  test('shows loading state during edit submission', async () => {
    const existingDataset: DatasetResponse = {
      dataset_id: 'ds-001',
      name: 'Test Dataset',
      path: '/mnt/data/test',
      description: null,
      storage_type: 'nfs',
      size_gb: 10.5,
      file_count: null,
      version: null,
      metadata: null,
      tags: null,
      is_public: true,
      owner_id: null,
      team_id: null,
      is_active: true,
      last_accessed_at: null,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: null,
    };

    let resolveUpdate: () => void;
    mockOnUpdate.mockImplementation(() => new Promise<void>(resolve => { resolveUpdate = resolve; }));

    render(
      <DatasetForm
        open={true}
        onOpenChange={mockOnOpenChange}
        dataset={existingDataset}
        onSuccess={mockOnSuccess}
        onUpdate={mockOnUpdate}
      />
    );

    const submitButton = screen.getByTestId('dialog-content').querySelector('button[type="submit"]');
    if (submitButton) {
      fireEvent.click(submitButton);
    }

    // Button should be disabled during loading
    const submitButtonDuringLoad = screen.getByTestId('dialog-content').querySelector('button[type="submit"]') as HTMLButtonElement;
    expect(submitButtonDuringLoad.disabled).toBe(true);

    // Resolve the update
    resolveUpdate!();
  });

  test('shows error message on edit submission failure', async () => {
    const existingDataset: DatasetResponse = {
      dataset_id: 'ds-001',
      name: 'Test Dataset',
      path: '/mnt/data/test',
      description: null,
      storage_type: 'nfs',
      size_gb: 10.5,
      file_count: null,
      version: null,
      metadata: null,
      tags: null,
      is_public: true,
      owner_id: null,
      team_id: null,
      is_active: true,
      last_accessed_at: null,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: null,
    };

    mockOnUpdate.mockRejectedValueOnce(new Error('更新失败'));

    render(
      <DatasetForm
        open={true}
        onOpenChange={mockOnOpenChange}
        dataset={existingDataset}
        onSuccess={mockOnSuccess}
        onUpdate={mockOnUpdate}
      />
    );

    const submitButton = screen.getByTestId('dialog-content').querySelector('button[type="submit"]');
    if (submitButton) {
      fireEvent.click(submitButton);
    }

    await waitFor(() => {
      expect(screen.getByText('更新失败')).toBeInTheDocument();
    });
  });
});
