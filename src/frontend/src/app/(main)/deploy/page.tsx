'use client';

import { useState, useEffect } from 'react';
import { useHosts } from '@/hooks/use-hosts';
import { useAlgorithms } from '@/hooks/use-algorithms';
import { createDeployWorker } from '@/lib/api';
import { DeployWizard } from '@/components/deploy/DeployWizard';
import { DeployProgress } from '@/components/deploy/DeployProgress';
import { CredentialModal, getStoredCredentials } from '@/components/deploy/CredentialModal';
import { Card, CardContent } from '@/components/ui/card';

export default function DeployPage() {
  const { data: hostsData } = useHosts();
  const { data: algorithms } = useAlgorithms();
  const [deployTaskId, setDeployTaskId] = useState<string | null>(null);
  const [deployingHost, setDeployingHost] = useState<string | null>(null);
  const [deployingAlgorithm, setDeployingAlgorithm] = useState<string | null>(null);
  const [deployError, setDeployError] = useState<string | null>(null);
  const [showCredentialModal, setShowCredentialModal] = useState(false);
  const [credentials, setCredentials] = useState<{ username: string; password: string; credentialId: string } | null>(null);

  // Check for stored credentials on mount
  useEffect(() => {
    const stored = getStoredCredentials();
    if (stored) {
      setCredentials(stored);
    } else {
      // No credentials stored, show modal
      setShowCredentialModal(true);
    }
  }, []);

  const hosts = hostsData?.cluster_nodes || [];

  // Find head node IP from hosts list
  const headNode = hosts.find((h) => h.is_local);
  const HEAD_IP = headNode?.ip || '192.168.0.126'; // Fallback to known head IP

  const handleCredentialSave = (credentialId: string, username: string, password: string) => {
    setCredentials({ credentialId, username, password });
    setShowCredentialModal(false);
  };

  const handleDeploy = async (hostId: string, algorithmName: string, algorithmVersion: string) => {
    setDeployError(null);

    // Check if credentials are available
    const storedCreds = getStoredCredentials();
    if (!storedCreds) {
      setShowCredentialModal(true);
      return;
    }

    // Find the target host in the list to get its IP
    const targetHost = hosts.find((h) => h.node_id === hostId);
    if (!targetHost) {
      setDeployError('无法找到目标主机信息');
      return;
    }

    try {
      const result = await createDeployWorker({
        node_ip: targetHost.ip,
        username: storedCreds.username,
        password: storedCreds.password,
        head_ip: HEAD_IP,
        ray_port: 6379,
      });

      setDeployingHost(targetHost.ip);
      setDeployingAlgorithm(`${algorithmName} ${algorithmVersion}`);
      setDeployTaskId(result.task_id);
    } catch (error) {
      console.error('Deployment failed:', error);
      setDeployError(error instanceof Error ? error.message : '部署失败');
    }
  };

  const handleCloseProgress = () => {
    setDeployTaskId(null);
    setDeployingHost(null);
    setDeployingAlgorithm(null);
    setDeployError(null);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold">部署算法</h1>
        <p className="text-muted-foreground">将算法部署到 Ray 集群节点</p>
      </div>

      {/* Deploy Wizard */}
      <DeployWizard
        hosts={hosts}
        algorithms={algorithms || []}
        onDeploy={handleDeploy}
      />

      {/* Deployment Progress Modal */}
      {deployTaskId && deployingHost && deployingAlgorithm && (
        <DeployProgress
          taskId={deployTaskId}
          hostId={deployingHost}
          algorithmName={deployingAlgorithm}
          onClose={handleCloseProgress}
        />
      )}

      {/* Error Alert */}
      {deployError && (
        <Card className="border-destructive">
          <CardContent className="py-4">
            <p className="text-sm text-destructive">{deployError}</p>
          </CardContent>
        </Card>
      )}

      {/* Credential Modal */}
      <CredentialModal
        open={showCredentialModal}
        onClose={() => setShowCredentialModal(false)}
        onSave={handleCredentialSave}
      />
    </div>
  );
}
