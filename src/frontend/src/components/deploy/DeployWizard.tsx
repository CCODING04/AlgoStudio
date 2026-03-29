'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { DeployWizardStep } from './DeployWizardStep';
import { Check, ChevronRight, Server, Settings, Package } from 'lucide-react';

interface Algorithm {
  name: string;
  version: string;
}

interface Host {
  node_id: string;
  ip: string;
  status: 'online' | 'offline';
  is_local: boolean;
  hostname: string;
  resources: {
    cpu: { total: number; used: number; physical_cores?: number; model?: string; freq_mhz?: number };
    gpu: { total: number; utilization: number; memory_used: string; memory_total: string; name?: string };
    memory: { total: string; used: string };
    disk?: { total: string; used: string };
    swap?: { total: string; used: string };
  };
}

interface DeployWizardProps {
  hosts: Host[];
  algorithms: Algorithm[];
  onDeploy: (hostId: string, algorithmName: string, algorithmVersion: string) => void;
}

export function DeployWizard({ hosts, algorithms, onDeploy }: DeployWizardProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedAlgorithm, setSelectedAlgorithm] = useState<string | null>(null);
  const [selectedAlgorithmVersion, setSelectedAlgorithmVersion] = useState<string | null>(null);
  const [selectedHost, setSelectedHost] = useState<string | null>(null);
  const [startRayWorker, setStartRayWorker] = useState(true);
  const [autoRestart, setAutoRestart] = useState(false);
  const [gpuMemoryLimit, setGpuMemoryLimit] = useState<number>(24);

  const steps = [
    { number: 1, title: '选择算法', icon: Package },
    { number: 2, title: '选择主机', icon: Server },
    { number: 3, title: '配置部署', icon: Settings },
  ];

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return !!selectedAlgorithm && !!selectedAlgorithmVersion;
      case 2:
        return !!selectedHost;
      case 3:
        return true;
      default:
        return false;
    }
  };

  const handleNext = () => {
    if (currentStep === 3) {
      if (selectedHost && selectedAlgorithm && selectedAlgorithmVersion) {
        onDeploy(selectedHost, selectedAlgorithm, selectedAlgorithmVersion);
      }
    } else {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const selectedHostData = hosts.find((h) => h.node_id === selectedHost);

  return (
    <div className="space-y-6" data-testid="deploy-form">
      {/* Step Indicator */}
      <div className="flex items-center justify-center">
        <div className="flex items-center gap-2">
          {steps.map((step, index) => (
            <div key={step.number} className="flex items-center">
              <div
                className={`flex items-center gap-2 px-4 py-2 rounded-full ${
                  currentStep >= step.number
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                {currentStep > step.number ? (
                  <Check className="h-4 w-4" />
                ) : (
                  <step.icon className="h-4 w-4" />
                )}
                <span className="text-sm font-medium">{step.title}</span>
              </div>
              {index < steps.length - 1 && (
                <ChevronRight className="h-4 w-4 mx-2 text-muted-foreground" />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Step Content */}
      <Card>
        <CardHeader>
          <CardTitle>
            {currentStep === 1 && '选择要部署的算法'}
            {currentStep === 2 && '选择目标主机'}
            {currentStep === 3 && '配置部署选项'}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Step 1: Algorithm Selection */}
          {currentStep === 1 && (
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">算法名称</label>
                <Select
                  value={selectedAlgorithm || ''}
                  onValueChange={(value) => {
                    setSelectedAlgorithm(value);
                    setSelectedAlgorithmVersion(null);
                  }}
                  data-testid="deploy-algorithm-select"
                >
                  <SelectTrigger>
                    <SelectValue placeholder="选择算法" />
                  </SelectTrigger>
                  <SelectContent>
                    {algorithms.map((algo) => (
                      <SelectItem key={algo.name} value={algo.name}>
                        {algo.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {selectedAlgorithm && (
                <div className="space-y-2">
                  <label className="text-sm font-medium">算法版本</label>
                  <Select
                    value={selectedAlgorithmVersion || ''}
                    onValueChange={setSelectedAlgorithmVersion}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="选择版本" />
                    </SelectTrigger>
                    <SelectContent>
                      {algorithms
                        .filter((algo) => algo.name === selectedAlgorithm)
                        .map((algo) => (
                          <SelectItem key={algo.version} value={algo.version}>
                            {algo.version}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {selectedAlgorithm && selectedAlgorithmVersion && (
                <div className="p-4 bg-muted rounded-lg">
                  <p className="text-sm">
                    <span className="font-medium">已选择:</span>{' '}
                    {selectedAlgorithm} {selectedAlgorithmVersion}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Step 2: Host Selection */}
          {currentStep === 2 && (
            <div className="space-y-4">
              {/* Existing Deployed Nodes */}
              <div className="space-y-2" data-testid="deployed-nodes">
                <label className="text-sm font-medium">已部署节点</label>
                <div className="space-y-2">
                  {hosts.filter((h) => h.status === 'online' && !h.is_local).length === 0 ? (
                    <p className="text-sm text-muted-foreground">暂无已部署的工作节点</p>
                  ) : (
                    hosts.filter((h) => h.status === 'online' && !h.is_local).map((host) => (
                      <div
                        key={host.node_id}
                        className="p-3 bg-muted rounded-lg flex items-center justify-between"
                        data-node-id={host.node_id}
                      >
                        <div>
                          <p className="text-sm font-medium">{host.ip} ({host.hostname})</p>
                          {host.resources?.gpu?.name && (
                            <p className="text-xs text-muted-foreground">{host.resources.gpu.name}</p>
                          )}
                        </div>
                        <Badge variant="success">在线</Badge>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Target Host Selection */}
              <div className="space-y-2">
                <label className="text-sm font-medium">目标主机</label>
                <Select
                  value={selectedHost || ''}
                  onValueChange={setSelectedHost}
                  data-testid="deploy-node-select"
                >
                  <SelectTrigger>
                    <SelectValue placeholder="选择主机" />
                  </SelectTrigger>
                  <SelectContent>
                    {hosts.filter((h) => h.status === 'online').map((host) => (
                      <SelectItem key={host.node_id} value={host.node_id}>
                        {host.ip} ({host.hostname})
                        {host.resources?.gpu?.name && ` - ${host.resources.gpu.name}`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {selectedHostData && (
                <div className="p-4 bg-muted rounded-lg space-y-2">
                  <p className="text-sm">
                    <span className="font-medium">已选择:</span> {selectedHostData.ip}
                  </p>
                  <p className="text-sm">
                    <span className="font-medium">主机名:</span> {selectedHostData.hostname}
                  </p>
                  {selectedHostData.resources?.gpu?.name && (
                    <p className="text-sm">
                      <span className="font-medium">GPU:</span> {selectedHostData.resources.gpu.name} (
                      {selectedHostData.resources.gpu.memory_total})
                    </p>
                  )}
                  <p className="text-sm">
                    <span className="font-medium">状态:</span>{' '}
                    <Badge variant="success">在线</Badge>
                  </p>
                </div>
              )}

              {hosts.filter((h) => h.status === 'online').length === 0 && (
                <p className="text-sm text-muted-foreground">
                  暂无可用的在线主机
                </p>
              )}
            </div>
          )}

          {/* Step 3: Configuration */}
          {currentStep === 3 && (
            <div className="space-y-6">
              <div className="space-y-4">
                <h3 className="text-sm font-medium">部署选项</h3>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="startRayWorker"
                    checked={startRayWorker}
                    onCheckedChange={(checked: boolean | 'indeterminate') => setStartRayWorker(checked === true)}
                  />
                  <label htmlFor="startRayWorker" className="text-sm">
                    启动 Ray Worker
                  </label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="autoRestart"
                    checked={autoRestart}
                    onCheckedChange={(checked: boolean | 'indeterminate') => setAutoRestart(checked === true)}
                  />
                  <label htmlFor="autoRestart" className="text-sm">
                    故障时自动重启
                  </label>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">GPU 内存限制 (GB)</label>
                <Input
                  type="number"
                  value={gpuMemoryLimit}
                  onChange={(e) => setGpuMemoryLimit(Number(e.target.value))}
                  min={1}
                  max={24}
                />
                <p className="text-xs text-muted-foreground">
                  最大可用: {selectedHostData?.resources?.gpu?.memory_total || '24Gi'}
                </p>
              </div>

              {/* Summary */}
              <div className="p-4 bg-muted rounded-lg space-y-2">
                <h3 className="text-sm font-medium">部署摘要</h3>
                <p className="text-sm">
                  <span className="font-medium">算法:</span> {selectedAlgorithm} {selectedAlgorithmVersion}
                </p>
                <p className="text-sm">
                  <span className="font-medium">目标主机:</span> {selectedHostData?.ip}
                </p>
                <p className="text-sm">
                  <span className="font-medium">选项:</span>{' '}
                  {startRayWorker && '启动 Ray Worker'}
                  {autoRestart && ', 故障自动重启'}
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Navigation Buttons */}
      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={handleBack}
          disabled={currentStep === 1}
        >
          上一步
        </Button>
        <Button
          onClick={handleNext}
          disabled={!canProceed()}
          data-testid="deploy-submit-button"
        >
          {currentStep === 3 ? '开始部署' : '下一步'}
        </Button>
      </div>
    </div>
  );
}
