'use client';

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { CredentialModal, getStoredCredentials, clearStoredCredentials } from '../CredentialModal';

// Mock fetch globally
global.fetch = jest.fn();

const mockFetch = global.fetch as jest.MockedFunction<typeof global.fetch>;

describe('CredentialModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Clear sessionStorage mocks
    jest.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
    jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {});
    jest.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('渲染表单字段', () => {
    render(<CredentialModal open={true} onClose={jest.fn()} onSave={jest.fn()} />);

    expect(screen.getByText(/SSH 凭据配置/i)).toBeInTheDocument();
    expect(screen.getByTestId('credential-username')).toBeInTheDocument();
    expect(screen.getByTestId('credential-password')).toBeInTheDocument();
  });

  test('用户名默认值为 admin02', () => {
    render(<CredentialModal open={true} onClose={jest.fn()} onSave={jest.fn()} />);

    const usernameInput = screen.getByTestId('credential-username') as HTMLInputElement;
    expect(usernameInput.value).toBe('admin02');
  });

  test('输入用户名', () => {
    const onClose = jest.fn();
    render(<CredentialModal open={true} onClose={onClose} onSave={jest.fn()} />);

    const usernameInput = screen.getByTestId('credential-username');
    fireEvent.change(usernameInput, { target: { value: 'newuser' } });

    expect((usernameInput as HTMLInputElement).value).toBe('newuser');
  });

  test('输入密码', () => {
    const onClose = jest.fn();
    render(<CredentialModal open={true} onClose={onClose} onSave={jest.fn()} />);

    const passwordInput = screen.getByTestId('credential-password');
    fireEvent.change(passwordInput, { target: { value: 'mypassword' } });

    expect((passwordInput as HTMLInputElement).value).toBe('mypassword');
  });

  test('密码为空时显示错误', async () => {
    const onClose = jest.fn();
    const onSave = jest.fn();
    render(<CredentialModal open={true} onClose={onClose} onSave={onSave} />);

    const saveButton = screen.getByTestId('credential-save');
    await act(async () => {
      fireEvent.click(saveButton);
    });

    expect(screen.getByTestId('credential-error')).toHaveTextContent('请输入 SSH 密码');
    expect(onSave).not.toHaveBeenCalled();
  });

  test('成功提交后调用 onSave 和 onClose', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ credential_id: 'cred-123' }),
    } as Response);

    const onClose = jest.fn();
    const onSave = jest.fn();
    render(<CredentialModal open={true} onClose={onClose} onSave={onSave} />);

    const passwordInput = screen.getByTestId('credential-password');
    fireEvent.change(passwordInput, { target: { value: 'mypassword' } });

    const saveButton = screen.getByTestId('credential-save');
    await act(async () => {
      fireEvent.click(saveButton);
    });

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith('cred-123', 'admin02', 'mypassword');
    });
    expect(onClose).toHaveBeenCalled();
  });

  test('API 错误时显示错误信息', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ error: '认证失败' }),
    } as Response);

    const onClose = jest.fn();
    const onSave = jest.fn();
    render(<CredentialModal open={true} onClose={onClose} onSave={onSave} />);

    const passwordInput = screen.getByTestId('credential-password');
    fireEvent.change(passwordInput, { target: { value: 'wrongpassword' } });

    const saveButton = screen.getByTestId('credential-save');
    await act(async () => {
      fireEvent.click(saveButton);
    });

    await waitFor(() => {
      expect(screen.getByTestId('credential-error')).toHaveTextContent('认证失败');
    });
    expect(onSave).not.toHaveBeenCalled();
  });

  test('取消按钮调用 onClose', () => {
    const onClose = jest.fn();
    const onSave = jest.fn();
    render(<CredentialModal open={true} onClose={onClose} onSave={onSave} />);

    const cancelButton = screen.getByTestId('credential-cancel');
    fireEvent.click(cancelButton);

    expect(onClose).toHaveBeenCalled();
  });

  // Note: open变为false时调用onClose cannot be tested because
  // Dialog's onOpenChange is only called on user interaction (click outside, Escape key),
  // not when open prop changes programmatically. The Dialog mock doesn't simulate this behavior.

  test('成功响应后将凭据存储到 sessionStorage', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ credential_id: 'cred-123' }),
    } as Response);

    const onClose = jest.fn();
    const onSave = jest.fn();
    render(<CredentialModal open={true} onClose={onClose} onSave={onSave} />);

    const passwordInput = screen.getByTestId('credential-password');
    fireEvent.change(passwordInput, { target: { value: 'mypassword' } });

    const saveButton = screen.getByTestId('credential-save');
    await act(async () => {
      fireEvent.click(saveButton);
    });

    await waitFor(() => {
      expect(sessionStorage.setItem).toHaveBeenCalledWith('deploy_credential_id', 'cred-123');
      expect(sessionStorage.setItem).toHaveBeenCalledWith('deploy_password', 'mypassword');
      expect(sessionStorage.setItem).toHaveBeenCalledWith('deploy_username', 'admin02');
    });
  });
});

describe('getStoredCredentials', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Storage.prototype, 'getItem').mockImplementation((key) => {
      if (key === 'deploy_username') return 'testuser';
      if (key === 'deploy_password') return 'testpass';
      if (key === 'deploy_credential_id') return 'cred-123';
      return null;
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('返回存储的凭据', () => {
    const credentials = getStoredCredentials();
    expect(credentials).toEqual({
      username: 'testuser',
      password: 'testpass',
      credentialId: 'cred-123',
    });
  });

  test('缺少任一凭据时返回 null', () => {
    jest.spyOn(Storage.prototype, 'getItem').mockImplementation((key) => {
      if (key === 'deploy_username') return 'testuser';
      if (key === 'deploy_password') return null;
      if (key === 'deploy_credential_id') return 'cred-123';
      return null;
    });

    const credentials = getStoredCredentials();
    expect(credentials).toBeNull();
  });

  test('所有凭据都为 null 时返回 null', () => {
    jest.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);

    const credentials = getStoredCredentials();
    expect(credentials).toBeNull();
  });
});

describe('clearStoredCredentials', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('清除所有凭据', () => {
    clearStoredCredentials();

    expect(sessionStorage.removeItem).toHaveBeenCalledWith('deploy_username');
    expect(sessionStorage.removeItem).toHaveBeenCalledWith('deploy_password');
    expect(sessionStorage.removeItem).toHaveBeenCalledWith('deploy_credential_id');
  });
});
