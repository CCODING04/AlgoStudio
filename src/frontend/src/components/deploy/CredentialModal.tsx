'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Loader2, KeyRound } from 'lucide-react';

interface CredentialModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (credentialId: string, username: string, password: string) => void;
}

export function CredentialModal({ open, onClose, onSave }: CredentialModalProps) {
  const [username, setUsername] = useState('admin02');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!password.trim()) {
      setError('请输入 SSH 密码');
      return;
    }

    setLoading(true);

    try {
      const res = await fetch('/api/proxy/deploy/credential', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || '存储凭据失败');
      }

      const data = await res.json();

      // Store password in sessionStorage for later use
      sessionStorage.setItem('deploy_credential_id', data.credential_id);
      sessionStorage.setItem('deploy_password', password);
      sessionStorage.setItem('deploy_username', username);

      onSave(data.credential_id, username, password);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : '存储凭据失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <KeyRound className="h-5 w-5" />
            SSH 凭据配置
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username">用户名</Label>
            <Input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin02"
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">SSH 密码</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="输入 SSH 密码"
              disabled={loading}
            />
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
              取消
            </Button>
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              保存凭据
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// Helper function to get stored credentials
export function getStoredCredentials(): { username: string; password: string; credentialId: string } | null {
  const username = sessionStorage.getItem('deploy_username');
  const password = sessionStorage.getItem('deploy_password');
  const credentialId = sessionStorage.getItem('deploy_credential_id');

  if (username && password && credentialId) {
    return { username, password, credentialId };
  }
  return null;
}

// Helper function to clear stored credentials
export function clearStoredCredentials(): void {
  sessionStorage.removeItem('deploy_username');
  sessionStorage.removeItem('deploy_password');
  sessionStorage.removeItem('deploy_credential_id');
}
