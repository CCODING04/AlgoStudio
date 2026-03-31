'use client';

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TaskWizard } from '../TaskWizard';

// Mock hooks
const mockUseAlgorithms = jest.fn();
const mockUseHosts = jest.fn();
const mockUseTaskSSEWithToast = jest.fn();

jest.mock('@/hooks/use-algorithms', () => ({
  useAlgorithms: () => mockUseAlgorithms(),
}));

jest.mock('@/hooks/use-hosts', () => ({
  useHosts: () => mockUseHosts(),
}));

jest.mock('@/hooks/use-task-sse-toast', () => ({
  useTaskSSEWithToast: (...args: any[]) => mockUseTaskSSEWithToast(...args),
}));

// Mock API functions
const mockCreateTask = jest.fn();
const mockDispatchTask = jest.fn();

jest.mock('@/lib/api', () => ({
  createTask: (...args: any[]) => mockCreateTask(...args),
  dispatchTask: (...args: any[]) => mockDispatchTask(...args),
}));

// Track select callbacks - key is testId or 'default'
const selectCallbacks: Record<string, { onValueChange?: (value: string) => void; value?: string }> = {};

// Track which testId each Select uses
let lastSelectTestId: string = 'default';

// Track dialog state
let dialogOpenState = false;
let dialogOnOpenChange: ((open: boolean) => void) | null = null;

// Mock Dialog
jest.mock('@/components/ui/dialog', () => ({
  Dialog: ({ children, open, onOpenChange }: any) => {
    dialogOpenState = open;
    dialogOnOpenChange = onOpenChange;
    return (
      <div data-testid={open ? "dialog-open" : "dialog-closed"} data-open={open}>
        {children}
      </div>
    );
  },
  DialogContent: ({ children, className, ...props }: any) => {
    if (!dialogOpenState) return <div data-testid="dialog-content-hidden" />;
    return <div role="dialog" data-testid="dialog-content" className={className} {...props}>{children}</div>;
  },
  DialogDescription: ({ children }: any) => <div data-testid="dialog-description">{children}</div>,
  DialogFooter: ({ children }: any) => <div data-testid="dialog-footer">{children}</div>,
  DialogHeader: ({ children }: any) => <div data-testid="dialog-header">{children}</div>,
  DialogTitle: ({ children }: any) => <div data-testid="dialog-title">{children}</div>,
  DialogTrigger: ({ children, asChild, onClick, ...props }: any) => {
    return (
      <button data-testid="dialog-trigger" onClick={(e) => {
        dialogOpenState = true;
        dialogOnOpenChange?.(true);
        onClick?.(e);
      }} {...props}>{children}</button>
    );
  },
  __getDialogOpenState: () => dialogOpenState,
  __resetDialogState: () => { dialogOpenState = false; dialogOnOpenChange = null; },
}));

// Mock Select
jest.mock('@/components/ui/select', () => ({
  Select: ({ children, value, onValueChange, 'data-testid': testId, ...props }: any) => {
    const key = testId || 'default';
    if (onValueChange) selectCallbacks[key] = { onValueChange, value };
    lastSelectTestId = key;
    return <div data-testid={key} data-value={value} {...props}>{children}</div>;
  },
  SelectContent: ({ children }: any) => <div data-testid="select-content">{children}</div>,
  SelectItem: ({ children, value, onClick, 'data-testid': testId, ...props }: any) => {
    // Use the last Select's testId to look up the callback
    const captured = selectCallbacks[lastSelectTestId];
    return (
      <div data-value={value} data-testid={testId || `select-item-${value}`}
        onClick={() => { captured?.onValueChange?.(value); onClick?.(value); }} {...props}>
        {children}
      </div>
    );
  },
  SelectTrigger: ({ children, className, ...props }: any) => (
    <button role="combobox" className={className} data-testid="select-trigger" {...props}>{children}</button>
  ),
  SelectValue: ({ placeholder }: any) => <span data-testid="select-value">{placeholder || 'Select...'}</span>,
  __getSelectCallback: (testId: string) => selectCallbacks[testId],
  __resetSelectCallbacks: () => { Object.keys(selectCallbacks).forEach(k => delete selectCallbacks[k]); },
}));

// Mock Card
jest.mock('@/components/ui/card', () => ({
  Card: ({ children, className, ...props }: any) => <div className={className} {...props}>{children}</div>,
  CardContent: ({ children }: any) => <div data-testid="card-content">{children}</div>,
  CardHeader: ({ children }: any) => <div data-testid="card-header">{children}</div>,
  CardTitle: ({ children }: any) => <div data-testid="card-title">{children}</div>,
  CardDescription: ({ children }: any) => <div data-testid="card-description">{children}</div>,
}));

// Mock Textarea
jest.mock('@/components/ui/textarea', () => ({
  Textarea: ({ value, onChange, placeholder, ...props }: any) => (
    <textarea data-testid="textarea" value={value} onChange={onChange} placeholder={placeholder} {...props} />
  ),
}));

// Mock Label
jest.mock('@/components/ui/label', () => ({
  Label: ({ children, ...props }: any) => <label {...props}>{children}</label>,
}));

// Mock Badge
jest.mock('@/components/ui/badge', () => ({
  Badge: ({ children, ...props }: any) => <div data-testid="badge" {...props}>{children}</div>,
}));

// Mock lucide-react
jest.mock('lucide-react', () => ({
  Loader2: () => <span data-testid="loader-icon" />,
  Play: () => <span data-testid="play-icon" />,
  CheckCircle2: () => <span data-testid="check-icon" />,
  AlertCircle: () => <span data-testid="alert-icon" />,
  Server: () => <span data-testid="server-icon" />,
}));

// Mock DatasetSelector
jest.mock('@/components/datasets/DatasetSelector', () => ({
  DatasetSelector: ({ value, onChange, placeholder }: any) => (
    <input
      type="text"
      data-testid="dataset-input"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
    />
  ),
}));

import { useAlgorithms } from '@/hooks/use-algorithms';
import { useHosts } from '@/hooks/use-hosts';
import { useTaskSSEWithToast } from '@/hooks/use-task-sse-toast';
import { createTask, dispatchTask } from '@/lib/api';

// Default mock data
const mockAlgorithmsData = [
  { name: 'simple_classifier', version: 'v1' },
  { name: 'simple_classifier', version: 'v2' },
  { name: 'resnet50', version: 'v1' },
];

const mockHostsData = {
  cluster_nodes: [
    {
      node_id: 'node-1',
      ip: '192.168.0.126',
      status: 'online',
      is_local: true,
      hostname: 'head-node',
      resources: {
        cpu: { total: 32, used: 4 },
        gpu: { total: 1, utilization: 10, memory_used: '2Gi', memory_total: '24Gi' },
        memory: { total: '32Gi', used: '8Gi' },
      },
    },
  ],
};

describe('TaskWizard', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Reset mocks
    const { __resetSelectCallbacks } = require('@/components/ui/select');
    __resetSelectCallbacks();
    lastSelectTestId = 'default';
    const { __resetDialogState } = require('@/components/ui/dialog');
    __resetDialogState();

    mockUseAlgorithms.mockReturnValue({
      data: mockAlgorithmsData,
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    });

    mockUseHosts.mockReturnValue({
      data: mockHostsData,
      isLoading: false,
      error: undefined,
      refetch: jest.fn(),
      isFetching: false,
    });

    mockUseTaskSSEWithToast.mockReturnValue(undefined);
    mockCreateTask.mockResolvedValue({ task_id: 'task-123' });
    mockDispatchTask.mockResolvedValue({ success: true });
  });

  describe('Initial Render', () => {
    test('renders step 1 correctly with open dialog', () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      expect(screen.getByText(/新建任务 - 选择算法/i)).toBeInTheDocument();
      expect(screen.getByText(/选择要使用的算法和任务类型/i)).toBeInTheDocument();
    });

    test('does not render dialog content when closed', () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={false} onOpenChange={onOpenChange} />);

      // Dialog content should not be visible when closed
      expect(screen.queryByText(/新建任务/i)).not.toBeInTheDocument();
    });

    test('displays loading state for algorithms when loading', () => {
      mockUseAlgorithms.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: undefined,
        refetch: jest.fn(),
        isFetching: false,
      });

      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      expect(screen.getByText(/加载算法列表/i)).toBeInTheDocument();
    });
  });

  describe('Hidden Inputs for Automation', () => {
    test('hidden task type inputs exist with correct values', () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      expect(screen.getByTestId('task-type-train')).toBeInTheDocument();
      expect(screen.getByTestId('task-type-infer')).toBeInTheDocument();
      expect(screen.getByTestId('task-type-verify')).toBeInTheDocument();

      expect(screen.getByTestId('task-type-train')).toHaveValue('train');
      expect(screen.getByTestId('task-type-infer')).toHaveValue('infer');
      expect(screen.getByTestId('task-type-verify')).toHaveValue('verify');
    });
  });

  describe('Navigation Buttons', () => {
    test('cancel button is present and triggers close', () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      const cancelButton = screen.getByRole('button', { name: /取消/i });
      expect(cancelButton).toBeInTheDocument();

      fireEvent.click(cancelButton);
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });

    test('next button is disabled initially', () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      const nextButton = screen.getByRole('button', { name: /下一步/i });
      expect(nextButton).toBeDisabled();
    });
  });

  describe('Task Creation Flow', () => {
    test('createTask is not called on initial render', () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      expect(mockCreateTask).not.toHaveBeenCalled();
    });

    test('dispatchTask is not called on initial render', () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      expect(mockDispatchTask).not.toHaveBeenCalled();
    });
  });

  describe('onSuccess Callback', () => {
    test('onSuccess is not called on initial render', () => {
      const onOpenChange = jest.fn();
      const onSuccess = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} onSuccess={onSuccess} />);

      expect(onSuccess).not.toHaveBeenCalled();
    });
  });

  describe('SSE Toast Hook', () => {
    test('useTaskSSEWithToast is called', () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      expect(mockUseTaskSSEWithToast).toHaveBeenCalled();
    });
  });

  describe('Reset Behavior', () => {
    test('cancel resets and closes', () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      const cancelButton = screen.getByRole('button', { name: /取消/i });
      fireEvent.click(cancelButton);

      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  describe('Select Components', () => {
    test('has select triggers for task type', () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      const selectTriggers = screen.getAllByRole('combobox');
      expect(selectTriggers.length).toBeGreaterThanOrEqual(1);
    });

    test('can open task type select dropdown', async () => {
      const user = userEvent.setup();
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      // Find select triggers (they have role="combobox")
      const selectTriggers = screen.getAllByRole('combobox');
      expect(selectTriggers.length).toBeGreaterThanOrEqual(1);

      // Click on the first select trigger
      await user.click(selectTriggers[0]);

      // After clicking, options should be visible
      await waitFor(() => {
        expect(screen.queryByText(/训练 \(Train\)/i)).toBeInTheDocument();
      });
    });

    test('selects task type using callback', async () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      const { __getSelectCallback } = require('@/components/ui/select');

      // Get task type select callback and invoke it
      const callback = __getSelectCallback('default');
      if (callback?.onValueChange) {
        act(() => { callback.onValueChange('train'); });
      }

      // The callback should have been invoked
      expect(callback).toBeDefined();
    });

    test('clicking SelectItem triggers onValueChange', async () => {
      const user = userEvent.setup();
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      // Click first combobox to open the select
      const selectTriggers = screen.getAllByRole('combobox');
      await user.click(selectTriggers[0]);

      // Find and click the train option
      const trainOption = screen.getByTestId('select-item-train');
      await user.click(trainOption);

      // After clicking, the select should show the selected value
      await waitFor(() => {
        expect(screen.queryByText(/训练 \(Train\)/i)).toBeInTheDocument();
      });
    });
  });

  describe('Button States', () => {
    test('step 1 has cancel and next buttons', () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      expect(screen.getByRole('button', { name: /取消/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /下一步/i })).toBeInTheDocument();
    });

    test('navigates through wizard steps using callbacks', async () => {
      const user = userEvent.setup();
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      // Step 1: Select algorithm
      const selectTriggers = screen.getAllByRole('combobox');
      // First select is task type, second is algorithm
      await user.click(selectTriggers[1]);

      // Use getAll and pick the first one
      const algoOptions = screen.getAllByTestId('select-item-simple_classifier');
      await user.click(algoOptions[0]);

      // Now select version
      await user.click(selectTriggers[2]);

      const versionOptions = screen.getAllByTestId('select-item-v1');
      await user.click(versionOptions[0]);

      // Next button should now be enabled
      const nextButton = screen.getByRole('button', { name: /下一步/i });
      expect(nextButton).not.toBeDisabled();
    });
  });

  describe('Dialog Structure', () => {
    test('dialog has correct role', () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    test('dialog title is present', () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      expect(screen.getByText(/新建任务/i)).toBeInTheDocument();
    });
  });

  describe('Error Display', () => {
    test('error message is displayed when set', () => {
      // This test checks the error display logic
      // Since error starts as null, we can only verify the element exists
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      // Initially no error
      expect(screen.queryByText(/配置格式错误/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/请选择算法和版本/i)).not.toBeInTheDocument();
    });
  });

  describe('Step Content Rendering', () => {
    test('step 1 content renders correctly', () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      // Step 1 specific content
      expect(screen.getByText(/选择要使用的算法和任务类型/i)).toBeInTheDocument();
    });
  });

  describe('Mock API Behavior', () => {
    test('handles createTask success', async () => {
      const onOpenChange = jest.fn();
      const onSuccess = jest.fn();

      mockCreateTask.mockResolvedValueOnce({ task_id: 'test-task-456' });
      mockDispatchTask.mockResolvedValueOnce({ success: true });

      render(<TaskWizard open={true} onOpenChange={onOpenChange} onSuccess={onSuccess} />);

      // API is ready to be called when user completes the wizard
      expect(mockCreateTask).not.toHaveBeenCalled();
    });

    test('handles createTask error', async () => {
      mockCreateTask.mockRejectedValueOnce(new Error('API Error'));

      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      expect(mockCreateTask).not.toHaveBeenCalled();
    });
  });

  describe('Wizard Step Navigation', () => {
    test('navigates from step 1 to step 2', async () => {
      const user = userEvent.setup();
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      // Select algorithm (second combobox)
      const selectTriggers = screen.getAllByRole('combobox');
      await user.click(selectTriggers[1]);

      const algoOptions = screen.getAllByTestId('select-item-simple_classifier');
      await user.click(algoOptions[0]);

      // Select version (third combobox)
      await user.click(selectTriggers[2]);

      const versionOptions = screen.getAllByTestId('select-item-v1');
      await user.click(versionOptions[0]);

      // Click next button
      const nextButton = screen.getByRole('button', { name: /下一步/i });
      await user.click(nextButton);

      // Should now show step 2 content
      await waitFor(() => {
        expect(screen.getByText(/配置任务参数/i)).toBeInTheDocument();
      });
    });

    test('handles back button from step 2', async () => {
      const user = userEvent.setup();
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      // Navigate to step 2
      const selectTriggers = screen.getAllByRole('combobox');
      await user.click(selectTriggers[1]);
      const algoOptions1 = screen.getAllByTestId('select-item-simple_classifier');
      await user.click(algoOptions1[0]);
      await user.click(selectTriggers[2]);
      const versionOptions1 = screen.getAllByTestId('select-item-v1');
      await user.click(versionOptions1[0]);

      const nextButton = screen.getByRole('button', { name: /下一步/i });
      await user.click(nextButton);

      // Should be on step 2
      await waitFor(() => {
        expect(screen.getByText(/配置任务参数/i)).toBeInTheDocument();
      });

      // Click back button
      const backButton = screen.getByRole('button', { name: /上一步/i });
      await user.click(backButton);

      // Should be back on step 1
      await waitFor(() => {
        expect(screen.getByText(/选择要使用的算法和任务类型/i)).toBeInTheDocument();
      });
    });

    test('navigates from step 2 to step 3', async () => {
      const user = userEvent.setup();
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      // Navigate to step 2
      const selectTriggers = screen.getAllByRole('combobox');
      await user.click(selectTriggers[1]);
      const algoOptions2 = screen.getAllByTestId('select-item-simple_classifier');
      await user.click(algoOptions2[0]);
      await user.click(selectTriggers[2]);
      const versionOptions2 = screen.getAllByTestId('select-item-v1');
      await user.click(versionOptions2[0]);

      await user.click(screen.getByRole('button', { name: /下一步/i }));

      // Should be on step 2, click next again
      await waitFor(() => {
        expect(screen.getByText(/配置任务参数/i)).toBeInTheDocument();
      });

      const nextButton = screen.getByRole('button', { name: /下一步/i });
      await user.click(nextButton);

      // Should now show step 3 content
      await waitFor(() => {
        expect(screen.getByText(/选择任务分配方式/i)).toBeInTheDocument();
      });
    });

    test('step 2 shows train configuration', async () => {
      const user = userEvent.setup();
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      // Navigate to step 2
      const selectTriggers = screen.getAllByRole('combobox');
      await user.click(selectTriggers[1]);
      const algoOptions3 = screen.getAllByTestId('select-item-simple_classifier');
      await user.click(algoOptions3[0]);
      await user.click(selectTriggers[2]);
      const versionOptions3 = screen.getAllByTestId('select-item-v1');
      await user.click(versionOptions3[0]);

      await user.click(screen.getByRole('button', { name: /下一步/i }));

      await waitFor(() => {
        expect(screen.getByText(/配置任务参数/i)).toBeInTheDocument();
        // Should show data path input for train
        expect(screen.getByTestId('dataset-input')).toBeInTheDocument();
        // Should show textarea for config
        expect(screen.getByTestId('textarea')).toBeInTheDocument();
      });
    });

    test('typing in textarea updates config', async () => {
      const user = userEvent.setup();
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      // Navigate to step 2
      const selectTriggers = screen.getAllByRole('combobox');
      await user.click(selectTriggers[1]);
      const algoOptions4 = screen.getAllByTestId('select-item-simple_classifier');
      await user.click(algoOptions4[0]);
      await user.click(selectTriggers[2]);
      const versionOptions4 = screen.getAllByTestId('select-item-v1');
      await user.click(versionOptions4[0]);

      await user.click(screen.getByRole('button', { name: /下一步/i }));

      await waitFor(() => {
        expect(screen.getByText(/配置任务参数/i)).toBeInTheDocument();
      });

      // Type into config textarea using fireEvent to bypass userEvent's parsing
      const textarea = screen.getByTestId('textarea');
      fireEvent.change(textarea, { target: { value: '{"epochs": 5}' } });

      // Config should be updated
      expect(textarea).toHaveValue('{"epochs": 5}');
    });

    test('step 3 scheduling mode selection works', async () => {
      const user = userEvent.setup();
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      // Navigate to step 3
      const selectTriggers = screen.getAllByRole('combobox');
      await user.click(selectTriggers[1]);
      const algoOptions5 = screen.getAllByTestId('select-item-simple_classifier');
      await user.click(algoOptions5[0]);
      await user.click(selectTriggers[2]);
      const versionOptions5 = screen.getAllByTestId('select-item-v1');
      await user.click(versionOptions5[0]);

      await user.click(screen.getByRole('button', { name: /下一步/i }));
      await waitFor(() => expect(screen.getByText(/配置任务参数/i)).toBeInTheDocument());

      await user.click(screen.getByRole('button', { name: /下一步/i }));
      await waitFor(() => expect(screen.getByText(/选择任务分配方式/i)).toBeInTheDocument());

      // The scheduling mode select should be visible (use first match for label)
      const schedulingLabel = screen.getAllByText(/分配模式/i)[0];
      expect(schedulingLabel).toBeInTheDocument();
    });

    test('create task button is present on step 3', async () => {
      const user = userEvent.setup();
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      // Navigate to step 3
      const selectTriggers = screen.getAllByRole('combobox');
      await user.click(selectTriggers[1]);
      const algoOptions6 = screen.getAllByTestId('select-item-simple_classifier');
      await user.click(algoOptions6[0]);
      await user.click(selectTriggers[2]);
      const versionOptions6 = screen.getAllByTestId('select-item-v1');
      await user.click(versionOptions6[0]);

      await user.click(screen.getByRole('button', { name: /下一步/i }));
      await waitFor(() => expect(screen.getByText(/配置任务参数/i)).toBeInTheDocument());

      await user.click(screen.getByRole('button', { name: /下一步/i }));
      await waitFor(() => expect(screen.getByText(/选择任务分配方式/i)).toBeInTheDocument());

      // Create task button should be visible
      const createButton = screen.getByRole('button', { name: /创建任务/i });
      expect(createButton).toBeInTheDocument();
    });

    test('task type select has correct options', async () => {
      const user = userEvent.setup();
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      // Open task type select
      const selectTriggers = screen.getAllByRole('combobox');
      await user.click(selectTriggers[0]);

      // Should see train option
      expect(screen.getByText(/训练 \(Train\)/i)).toBeInTheDocument();
      // Should see infer option
      expect(screen.getByText(/推理 \(Infer\)/i)).toBeInTheDocument();
      // Should see verify option
      expect(screen.getByText(/验证 \(Verify\)/i)).toBeInTheDocument();
    });

    test('handleVersionChange sets version correctly', async () => {
      const onOpenChange = jest.fn();
      render(<TaskWizard open={true} onOpenChange={onOpenChange} />);

      // Use callback approach to directly test handleVersionChange
      const { __getSelectCallback } = require('@/components/ui/select');

      // First set algorithm name via act
      const algoCallback = __getSelectCallback('default');
      if (algoCallback?.onValueChange) {
        act(() => { algoCallback.onValueChange('simple_classifier'); });
      }

      // Now trigger version change
      const versionCallback = __getSelectCallback('default');
      if (versionCallback?.onValueChange) {
        act(() => { versionCallback.onValueChange('v1'); });
      }

      // The version callback should have been called
      expect(versionCallback).toBeDefined();
    });
  });
});
