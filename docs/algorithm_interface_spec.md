# 算法接口规范

## 数据类

### TrainResult
训练结果数据类，包含以下字段：
- `success: bool` - 训练是否成功
- `model_path: Optional[str]` - 模型保存路径
- `metrics: Optional[Dict[str, Any]]` - 训练指标（如 mAP、FPS 等）
- `error: Optional[str]` - 错误信息

### InferenceResult
推理结果数据类，包含以下字段：
- `success: bool` - 推理是否成功
- `outputs: Optional[List[Dict[str, Any]]]` - 推理输出结果
- `latency_ms: Optional[float]` - 推理延迟（毫秒）
- `error: Optional[str]` - 错误信息

### VerificationResult
验证结果数据类，包含以下字段：
- `success: bool` - 验证是否成功完成
- `passed: bool` - 验证是否通过
- `metrics: Optional[Dict[str, Any]]` - 验证指标
- `details: Optional[str]` - 详细说明

### AlgorithmMetadata
算法元信息数据类，包含以下字段：
- `name: str` - 算法名称
- `version: str` - 算法版本
- `task_type: str` - 任务类型（如 object_detection）
- `deployment: str` - 部署环境（"edge" 或 "cloud"）
- `expected_fps: Optional[int]` - 预期帧率

## 必须实现的方法

### train(data_path: str, config: dict, progress_callback=None) -> TrainResult
- `data_path`: 训练数据集路径
- `config`: 训练配置（epochs, batch_size 等）
- `progress_callback`: 进度回调对象（可选，用于报告训练进度）
- 返回训练结果和指标

### infer(inputs: list) -> InferenceResult
- `inputs`: 输入数据列表
- 返回推理结果和延迟

### verify(test_data: str) -> VerificationResult
- `test_data`: 测试数据集路径
- 返回验证是否通过

### get_metadata() -> AlgorithmMetadata
- 返回算法元信息

## 进度回调接口

进度回调用于在训练过程中向调度系统报告进度，使 Web Console 可以实时显示训练状态。

### ProgressCallback 接口
```python
class ProgressCallback:
    """进度回调基类"""

    def update(self, current: int, total: int, description: str = ""):
        """更新进度

        Args:
            current: 当前进度值
            total: 总进度值
            description: 进度描述（如 "Epoch 3/10"）
        """
        raise NotImplementedError

    def set_description(self, description: str):
        """设置进度条描述"""
        raise NotImplementedError
```

### NullProgressCallback（默认实现）
当 `progress_callback=None` 时使用，不执行任何操作。

### Ray 分布式进度回调
在 Ray 集群中运行时使用，通过 Ray Actor 异步更新任务状态。

## 算法接口基类

```python
class AlgorithmInterface:
    """算法接口基类，所有算法必须实现此接口"""

    def train(self, data_path: str, config: dict, progress_callback=None) -> TrainResult:
        """训练接口

        Args:
            data_path: 数据集路径
            config: 训练配置
            progress_callback: 进度回调，算法内部应在适当时机调用更新进度
        """
        raise NotImplementedError

    def infer(self, inputs: list) -> InferenceResult:
        """推理接口"""
        raise NotImplementedError

    def verify(self, test_data: str) -> VerificationResult:
        """验证接口"""
        raise NotImplementedError

    @staticmethod
    def get_metadata() -> AlgorithmMetadata:
        """返回算法元信息"""
        raise NotImplementedError
```

所有具体算法实现必须继承 `AlgorithmInterface` 并实现上述四个方法。