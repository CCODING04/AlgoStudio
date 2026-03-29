'use client';

import { useState } from 'react';
import { useAlgorithms } from '@/hooks/use-algorithms';
import { useHosts } from '@/hooks/use-hosts';
import { useTaskSSEWithToast } from '@/hooks/use-task-sse-toast';
import { createTask, dispatchTask } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Loader2, Play, CheckCircle2, AlertCircle, Server } from 'lucide-react';
import { DatasetSelector } from '@/components/datasets/DatasetSelector';

interface TaskWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (taskId: string) => void;
}

type TaskType = 'train' | 'infer' | 'verify';
type SchedulingMode = 'auto' | 'manual';

export function TaskWizard({ open, onOpenChange, onSuccess }: TaskWizardProps) {
  const { data: algorithms, isLoading: algorithmsLoading } = useAlgorithms();
  const { data: hostsData, isLoading: hostsLoading } = useHosts();

  const [step, setStep] = useState(1);
  const [taskType, setTaskType] = useState<TaskType>('train');
  const [algorithmName, setAlgorithmName] = useState('');
  const [algorithmVersion, setAlgorithmVersion] = useState('');
  const [dataPath, setDataPath] = useState('');
  const [inputs, setInputs] = useState('');
  const [config, setConfig] = useState('{"epochs": 2, "batch_size": 32}');

  // Node selection state
  const [schedulingMode, setSchedulingMode] = useState<SchedulingMode>('auto');
  const [selectedNodeId, setSelectedNodeId] = useState<string>('');

  const [isCreating, setIsCreating] = useState(false);
  const [isDispatching, setIsDispatching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdTaskId, setCreatedTaskId] = useState<string | null>(null);
  const [dispatchStatus, setDispatchStatus] = useState<'pending' | 'dispatching' | 'running' | 'failed'>('pending');

  // Listen for SSE allocated events when task is created
  useTaskSSEWithToast(createdTaskId, step === 4);

  const selectedAlgorithm = algorithms?.find(
    (a) => a.name === algorithmName && a.version === algorithmVersion
  );

  const handleAlgorithmChange = (name: string) => {
    setAlgorithmName(name);
    setAlgorithmVersion('');
    setError(null);
  };

  const handleVersionChange = (version: string) => {
    setAlgorithmVersion(version);
    setError(null);
  };

  const canProceedToStep2 = taskType && algorithmName && algorithmVersion;

  const handleProceedToStep2 = () => {
    if (!algorithmName || !algorithmVersion) {
      setError('请选择算法和版本');
      return;
    }
    setStep(2);
    setError(null);
  };

  const handleBack = () => {
    setStep(step - 1);
    setError(null);
  };

  const handleProceedToStep3 = () => {
    setStep(3);
    setError(null);
  };

  const handleReset = () => {
    setStep(1);
    setTaskType('train');
    setAlgorithmName('');
    setAlgorithmVersion('');
    setDataPath('');
    setInputs('');
    setConfig('{"epochs": 2, "batch_size": 32}');
    setSchedulingMode('auto');
    setSelectedNodeId('');
    setError(null);
    setCreatedTaskId(null);
    setIsCreating(false);
    setIsDispatching(false);
    setDispatchStatus('pending');
  };

  const handleClose = (isOpen: boolean) => {
    if (!isOpen) {
      handleReset();
      onOpenChange(false);
    }
  };

  const handleSubmit = async () => {
    if (!algorithmName || !algorithmVersion) {
      setError('请选择算法和版本');
      return;
    }

    setIsCreating(true);
    setIsDispatching(false);
    setError(null);

    try {
      const request: Parameters<typeof createTask>[0] = {
        task_type: taskType,
        algorithm_name: algorithmName,
        algorithm_version: algorithmVersion,
      };

      if (taskType === 'train') {
        request.data_path = dataPath || '/mnt/VtrixDataset/data/train';
        try {
          request.config = JSON.parse(config);
        } catch {
          setError('配置格式错误，请输入有效的 JSON');
          setIsCreating(false);
          return;
        }
      } else if (taskType === 'infer') {
        request.inputs = inputs.split('\n').filter((s) => s.trim());
      }

      const result = await createTask(request);
      setCreatedTaskId(result.task_id);
      setStep(4);

      // Auto-dispatch the task with selected node (if manual mode)
      setIsDispatching(true);
      setDispatchStatus('dispatching');

      try {
        const nodeId = schedulingMode === 'manual' ? selectedNodeId : undefined;
        await dispatchTask(result.task_id, nodeId);
        setDispatchStatus('running');
      } catch (dispatchErr) {
        console.error('Failed to dispatch task:', dispatchErr);
        setDispatchStatus('failed');
        // Still allow user to see the task, they can dispatch manually later
      }

      if (onSuccess) {
        onSuccess(result.task_id);
      }
    } catch (err) {
      console.error('Failed to create task:', err);
      setError(err instanceof Error ? err.message : '创建任务失败');
    } finally {
      setIsCreating(false);
      setIsDispatching(false);
    }
  };

  const algorithmVersions = algorithms?.filter((a) => a.name === algorithmName) || [];
  const clusterNodes = hostsData?.cluster_nodes || [];
  const onlineNodes = clusterNodes.filter((node) => node.status === 'online');

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>
            {step === 1 && '新建任务 - 选择算法'}
            {step === 2 && '新建任务 - 配置参数'}
            {step === 3 && '新建任务 - 选择节点'}
            {step === 4 && '任务创建成功'}
          </DialogTitle>
          <DialogDescription>
            {step === 1 && '选择要使用的算法和任务类型'}
            {step === 2 && '配置任务参数'}
            {step === 3 && '选择任务分配方式'}
            {step === 4 && '任务已提交，请等待调度执行'}
          </DialogDescription>
        </DialogHeader>

        {step === 1 && (
          <div className="space-y-6 py-4">
            {/* Task Type */}
            <div className="space-y-2">
              {/* Hidden inputs for test automation - always exist in DOM */}
              <input type="hidden" data-testid="task-type-train" value="train" />
              <input type="hidden" data-testid="task-type-infer" value="infer" />
              <input type="hidden" data-testid="task-type-verify" value="verify" />
              <Label>任务类型</Label>
              <Select
                value={taskType}
                onValueChange={(value) => setTaskType(value as TaskType)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择任务类型" />
                </SelectTrigger>
                <SelectContent className="z-[60]">
                  <SelectItem value="train">训练 (Train)</SelectItem>
                  <SelectItem value="infer">推理 (Infer)</SelectItem>
                  <SelectItem value="verify">验证 (Verify)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Algorithm */}
            <div className="space-y-2">
              <Label>算法</Label>
              {algorithmsLoading ? (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  加载算法列表...
                </div>
              ) : (
                <Select value={algorithmName} onValueChange={handleAlgorithmChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择算法" />
                  </SelectTrigger>
                  <SelectContent>
                    {algorithms?.map((algo) => (
                      <SelectItem key={`${algo.name}-${algo.version}`} value={algo.name}>
                        {algo.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            {/* Version */}
            {algorithmName && (
              <div className="space-y-2">
                <Label>版本</Label>
                <Select value={algorithmVersion} onValueChange={handleVersionChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择版本" />
                  </SelectTrigger>
                  <SelectContent>
                    {algorithmVersions.map((algo) => (
                      <SelectItem key={algo.version} value={algo.version}>
                        {algo.version}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
        )}

        {step === 2 && (
          <div className="space-y-6 py-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">已选算法</CardTitle>
                <CardDescription>
                  {algorithmName} {algorithmVersion}
                </CardDescription>
              </CardHeader>
            </Card>

            {taskType === 'train' && (
              <>
                <div className="space-y-2">
                  <Label>数据路径</Label>
                  <DatasetSelector
                    value={dataPath}
                    onChange={setDataPath}
                    placeholder="/mnt/VtrixDataset/data/train"
                  />
                  <p className="text-xs text-muted-foreground">
                    选择数据集或手动输入训练数据所在目录路径
                  </p>
                </div>

                <div className="space-y-2">
                  <Label>配置参数 (JSON)</Label>
                  <Textarea
                    value={config}
                    onChange={(e) => setConfig(e.target.value)}
                    placeholder='{"epochs": 10, "batch_size": 32}'
                    rows={4}
                  />
                  <p className="text-xs text-muted-foreground">
                    训练配置参数，需为有效的 JSON 格式
                  </p>
                </div>
              </>
            )}

            {taskType === 'infer' && (
              <div className="space-y-2">
                <Label>输入数据 (每行一个)</Label>
                <Textarea
                  value={inputs}
                  onChange={(e) => setInputs(e.target.value)}
                  placeholder="image1.jpg&#10;image2.jpg&#10;image3.jpg"
                  rows={6}
                />
                <p className="text-xs text-muted-foreground">
                  每行输入一个数据，支持图片路径或其他数据标识
                </p>
              </div>
            )}

            {taskType === 'verify' && (
              <div className="space-y-2">
                <Label>测试数据路径</Label>
                <DatasetSelector
                  value={dataPath}
                  onChange={setDataPath}
                  placeholder="/mnt/VtrixDataset/data/verify"
                />
                <p className="text-xs text-muted-foreground">
                  选择数据集或手动输入验证数据集所在目录路径
                </p>
              </div>
            )}

            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
        )}

        {step === 3 && (
          <div className="space-y-6 py-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">已选算法</CardTitle>
                <CardDescription>
                  {algorithmName} {algorithmVersion}
                </CardDescription>
              </CardHeader>
            </Card>

            {/* Scheduling Mode Selection */}
            <div className="space-y-2">
              <Label>分配模式</Label>
              <Select
                value={schedulingMode}
                onValueChange={(value) => {
                  setSchedulingMode(value as SchedulingMode);
                  if (value === 'auto') {
                    setSelectedNodeId('');
                  }
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择分配模式" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">自动分配 (推荐)</SelectItem>
                  <SelectItem value="manual">手动选择节点</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {schedulingMode === 'auto'
                  ? '调度器将自动选择最合适的节点'
                  : '手动选择要执行任务的节点'}
              </p>
            </div>

            {/* Node Selection (only in manual mode) */}
            {schedulingMode === 'manual' && (
              <div className="space-y-2">
                <Label>选择节点</Label>
                {hostsLoading ? (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    加载节点列表...
                  </div>
                ) : onlineNodes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">暂无可用节点</p>
                ) : (
                  <div className="grid gap-2">
                    {onlineNodes.map((node) => (
                      <Card
                        key={node.node_id}
                        className={`cursor-pointer transition-colors ${
                          selectedNodeId === node.node_id
                            ? 'border-primary bg-primary/5'
                            : 'hover:border-primary/50'
                        }`}
                        onClick={() => setSelectedNodeId(node.node_id)}
                      >
                        <CardContent className="p-3 flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <Server className="h-4 w-4 text-muted-foreground" />
                            <div>
                              <p className="text-sm font-medium">{node.hostname}</p>
                              <p className="text-xs text-muted-foreground">{node.ip}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {node.role && (
                              <Badge
                                variant={node.role === 'head' ? 'default' : 'secondary'}
                                className="text-xs"
                              >
                                {node.role === 'head' ? 'Head' : 'Worker'}
                              </Badge>
                            )}
                            {selectedNodeId === node.node_id && (
                              <CheckCircle2 className="h-4 w-4 text-primary" />
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            )}

            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
        )}

        {step === 4 && createdTaskId && (
          <div className="py-8">
            <div className="flex flex-col items-center gap-4">
              {dispatchStatus === 'running' ? (
                <CheckCircle2 className="h-16 w-16 text-green-500" />
              ) : dispatchStatus === 'dispatching' ? (
                <Loader2 className="h-16 w-16 text-blue-500 animate-spin" />
              ) : dispatchStatus === 'failed' ? (
                <AlertCircle className="h-16 w-16 text-yellow-500" />
              ) : (
                <CheckCircle2 className="h-16 w-16 text-green-500" />
              )}
              <div className="text-center">
                <p className="text-lg font-medium">
                  {dispatchStatus === 'running'
                    ? '任务已启动'
                    : dispatchStatus === 'dispatching'
                    ? '正在启动任务...'
                    : dispatchStatus === 'failed'
                    ? '任务创建成功但启动失败'
                    : '任务创建成功'}
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  任务 ID: {createdTaskId}
                </p>
              </div>
              <p className="text-sm text-muted-foreground text-center">
                {dispatchStatus === 'running'
                  ? '任务已开始执行，请查看任务列表监控进度'
                  : dispatchStatus === 'dispatching'
                  ? '正在将任务分发到集群，请稍候...'
                  : dispatchStatus === 'failed'
                  ? '任务已创建但启动失败，可能需要手动分发'
                  : '任务已提交到调度队列，请稍后刷新查看任务状态'}
              </p>
            </div>
          </div>
        )}

        <DialogFooter>
          {step === 1 && (
            <>
              <Button variant="outline" onClick={handleClose}>
                取消
              </Button>
              <Button onClick={handleProceedToStep2} disabled={!canProceedToStep2}>
                下一步
              </Button>
            </>
          )}

          {step === 2 && (
            <>
              <Button variant="outline" onClick={handleBack}>
                上一步
              </Button>
              <Button onClick={handleProceedToStep3}>
                下一步
              </Button>
            </>
          )}

          {step === 3 && (
            <>
              <Button variant="outline" onClick={handleBack}>
                上一步
              </Button>
              <Button
                onClick={handleSubmit}
                disabled={isCreating || (schedulingMode === 'manual' && !selectedNodeId)}
              >
                {isCreating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    创建中...
                  </>
                ) : (
                  <>
                    <Play className="mr-2 h-4 w-4" />
                    创建任务
                  </>
                )}
              </Button>
            </>
          )}

          {step === 4 && (
            <Button onClick={handleClose}>完成</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
