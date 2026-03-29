# Algorithm Deployment Guide

This guide covers how to deploy, register, and use algorithms in AlgoStudio.

## Table of Contents

- [Algorithm Interface Specification](#algorithm-interface-specification)
- [Algorithm Directory Structure](#algorithm-directory-structure)
- [Creating a New Algorithm](#creating-a-new-algorithm)
- [Result Classes](#result-classes)
- [Progress Callback Interface](#progress-callback-interface)
- [Deployment](#deployment)
- [Task Examples](#task-examples)
- [Troubleshooting](#troubleshooting)

---

## Algorithm Interface Specification

All algorithms must implement four core methods using duck typing:

### Required Methods

| Method | Description |
|--------|-------------|
| `train(data_path, config, progress_callback)` | Train the model on provided data |
| `infer(inputs)` | Run inference on input data |
| `verify(test_data)` | Verify model performance |
| `get_metadata()` | Return algorithm metadata (static method) |

### Example Implementation Pattern

```python
class MyAlgorithm:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None

    @staticmethod
    def get_metadata() -> AlgorithmMetadata:
        return AlgorithmMetadata(
            name="my_algorithm",
            version="v1",
            task_type="classification",
            deployment="cloud",
            expected_fps=100
        )

    def train(self, data_path: str, config: dict, progress_callback=None) -> TrainResult:
        # Implementation
        return TrainResult(success=True, model_path="path/to/model.pth", metrics={})

    def infer(self, inputs: list) -> InferenceResult:
        # Implementation
        return InferenceResult(success=True, outputs=[], latency_ms=0.0)

    def verify(self, test_data: str) -> VerificationResult:
        # Implementation
        return VerificationResult(success=True, passed=True, metrics={})
```

---

## Algorithm Directory Structure

```
algorithms/
└── {algorithm_name}/
    └── {version}/
        ├── __init__.py          # Main algorithm implementation
        ├── metadata.json         # Algorithm metadata
        ├── requirements.txt     # Python dependencies
        ├── model.pth            # Trained model (generated)
        └── tests/               # Unit tests (optional)
```

### metadata.json Schema

```json
{
    "name": "algorithm_name",
    "version": "v1",
    "description": "Algorithm description",
    "task_type": "classification|detection|segmentation|...",
    "deployment": "cloud|edge",
    "framework": "pytorch|tensorflow|...",
    "expected_fps": 100,
    "input_types": ["image", "video"],
    "output_types": ["classification", "bbox"],
    "config_schema": {
        "param_name": {
            "type": "int|string|float",
            "default": 10,
            "description": "Parameter description"
        }
    },
    "data_requirements": {
        "train": "Path to training dataset",
        "verify": "Path to test dataset"
    }
}
```

---

## Creating a New Algorithm

### Step 1: Create Directory Structure

```bash
mkdir -p algorithms/my_algorithm/v1
cd algorithms/my_algorithm/v1
```

### Step 2: Create metadata.json

```json
{
    "name": "my_algorithm",
    "version": "v1",
    "description": "My custom algorithm",
    "task_type": "classification",
    "deployment": "cloud",
    "framework": "pytorch",
    "expected_fps": 50
}
```

### Step 3: Create requirements.txt

```
torch>=2.0.0
torchvision>=0.15.0
pillow>=9.0.0
numpy>=1.24.0
```

### Step 4: Implement __init__.py

See [Example: simple_classifier](#example-simple_classifier) below.

---

## Result Classes

### TrainResult

```python
class TrainResult:
    def __init__(
        self,
        success: bool,
        model_path: str = None,
        metrics: Dict = None,
        error: str = None
    ):
        self.success = success
        self.model_path = model_path
        self.metrics = metrics or {}
        self.error = error
```

**Fields:**
- `success: bool` - Whether training completed successfully
- `model_path: Optional[str]` - Path where model was saved
- `metrics: Optional[Dict]` - Training metrics (accuracy, loss, etc.)
- `error: Optional[str]` - Error message if failed

### InferenceResult

```python
class InferenceResult:
    def __init__(
        self,
        success: bool,
        outputs: List = None,
        latency_ms: float = None,
        error: str = None
    ):
        self.success = success
        self.outputs = outputs or []
        self.latency_ms = latency_ms
        self.error = error
```

**Fields:**
- `success: bool` - Whether inference completed successfully
- `outputs: Optional[List]` - List of inference results
- `latency_ms: Optional[float]` - Average inference latency in milliseconds
- `error: Optional[str]` - Error message if failed

### VerificationResult

```python
class VerificationResult:
    def __init__(
        self,
        success: bool,
        passed: bool,
        metrics: Dict = None,
        details: str = None
    ):
        self.success = success
        self.passed = passed
        self.metrics = metrics or {}
        self.details = details
```

**Fields:**
- `success: bool` - Whether verification ran to completion
- `passed: bool` - Whether model passed verification threshold
- `metrics: Optional[Dict]` - Verification metrics (accuracy, F1, etc.)
- `details: Optional[str]` - Human-readable verification details

### AlgorithmMetadata

```python
class AlgorithmMetadata:
    def __init__(
        self,
        name: str,
        version: str,
        task_type: str,
        deployment: str,
        expected_fps: int = None
    ):
        self.name = name
        self.version = version
        self.task_type = task_type
        self.deployment = deployment
        self.expected_fps = expected_fps
```

**Fields:**
- `name: str` - Algorithm name (must match directory name)
- `version: str` - Semantic version (e.g., "v1", "v2.1")
- `task_type: str` - Type of task (classification, detection, etc.)
- `deployment: str` - "cloud" or "edge"
- `expected_fps: Optional[int]` - Expected inference FPS

---

## Progress Callback Interface

The progress callback allows algorithms to report training progress to the Web Console in real-time.

### Interface

```python
class ProgressCallback:
    def update(self, current: int, total: int, description: str = ""):
        """Update progress

        Args:
            current: Current progress value
            total: Total progress value (e.g., total batches)
            description: Human-readable status (e.g., "Epoch 3/10 - acc: 85%")
        """
        raise NotImplementedError

    def set_description(self, description: str):
        """Set progress bar description"""
        raise NotImplementedError
```

### Usage Example

```python
def train(self, data_path: str, config: dict, progress_callback=None) -> TrainResult:
    # Use NullProgressCallback if no callback provided
    progress = progress_callback or NullProgressCallback()

    total_batches = len(dataloader) * epochs
    current_batch = 0

    for epoch in range(epochs):
        for i, (inputs, labels) in enumerate(dataloader):
            # Training steps...
            current_batch += 1

            # Report progress every 100 batches
            if i % 100 == 0:
                progress.update(
                    current_batch,
                    total_batches,
                    f"Epoch {epoch + 1}/{epochs} - batch {i}/{len(dataloader)}"
                )

    progress.update(total_batches, total_batches, "Training completed")
    return TrainResult(success=True, model_path=model_path, metrics={})
```

### Default Implementation

```python
class NullProgressCallback:
    """No-op progress callback for when progress reporting is not needed"""

    def update(self, current: int, total: int, description: str = ""):
        pass

    def set_description(self, description: str):
        pass
```

---

## Deployment

### Local Testing

Test your algorithm locally before deploying to the cluster:

```python
from my_algorithm.v1 import MyAlgorithm

algo = MyAlgorithm()

# Train
train_result = algo.train(
    data_path="/path/to/data",
    config={"epochs": 10, "batch_size": 32},
    progress_callback=NullProgressCallback()
)
print(f"Training: {train_result.success}, model saved to {train_result.model_path}")

# Infer
infer_result = algo.infer(["/path/to/image1.jpg", "/path/to/image2.jpg"])
print(f"Inference: {infer_result.outputs}, latency: {infer_result.latency_ms}ms")

# Verify
verify_result = algo.verify("/path/to/test_data")
print(f"Verification: passed={verify_result.passed}, accuracy={verify_result.metrics}")
```

### Ray Cluster Deployment

Algorithms are automatically deployed to the Ray cluster when:

1. The algorithm directory exists under `algorithms/{name}/{version}/`
2. The `requirements.txt` dependencies are installed on all worker nodes
3. The algorithm is registered via the API:

```bash
# Register algorithm
curl -X POST http://localhost:8000/api/algorithms/register \
  -H "Content-Type: application/json" \
  -d '{"name": "my_algorithm", "version": "v1"}'

# List available algorithms
curl http://localhost:8000/api/algorithms
```

### Installing Dependencies on Workers

For Ray cluster deployment, ensure dependencies are installed on all workers:

```bash
# SSH to each worker and install
ssh worker@192.168.0.115
cd ~/Code/AlgoStudio
source .venv-ray/bin/activate
pip install -r algorithms/my_algorithm/v1/requirements.txt

# Restart Ray on worker
ray stop
ray start --address='192.168.0.126:6379' --node-ip-address=192.168.0.115
```

---

## Task Examples

### Creating a Training Task

```python
import requests

response = requests.post("http://localhost:8000/api/tasks", json={
    "task_type": "train",
    "algorithm_name": "simple_classifier",
    "algorithm_version": "v1",
    "config": {
        "data_path": "/path/to/training/data",
        "epochs": 10,
        "batch_size": 64,
        "learning_rate": 0.001
    }
})
print(response.json())
```

### Creating an Inference Task

```python
response = requests.post("http://localhost:8000/api/tasks", json={
    "task_type": "infer",
    "algorithm_name": "simple_classifier",
    "algorithm_version": "v1",
    "config": {
        "inputs": [
            "/path/to/image1.jpg",
            "/path/to/image2.jpg",
            "/path/to/image3.jpg"
        ]
    }
})
```

### Creating a Verification Task

```python
response = requests.post("http://localhost:8000/api/tasks", json={
    "task_type": "verify",
    "algorithm_name": "simple_classifier",
    "algorithm_version": "v1",
    "config": {
        "test_data": "/path/to/test/data"
    }
})
```

### Monitoring Task Progress (SSE)

```python
import sseclient
import requests

def progress_stream(task_id):
    response = requests.get(
        f"http://localhost:8000/api/tasks/{task_id}/stream",
        stream=True
    )
    client = sseclient.SSEClient(response)
    for event in client.events():
        print(f"Progress: {event.data}")
        if event.data == "completed" or event.data == "failed":
            break

# Subscribe to progress updates
progress_stream("train-abc12345")
```

### Querying Task Status

```python
response = requests.get("http://localhost:8000/api/tasks/train-abc12345")
task = response.json()
print(f"Status: {task['status']}, Progress: {task['progress']}%")
```

---

## Troubleshooting

### Algorithm Not Found

**Error:** `FileNotFoundError: Algorithm implementation not found`

**Solution:** Ensure your algorithm directory structure is correct:
```
algorithms/{algorithm_name}/{version}/__init__.py
```

The loader looks for `classifier.py`, `detector.py`, `model.py`, or `algorithm.py` as fallback.

### Progress Not Updating

**Symptom:** Web Console shows 0% progress during training

**Solutions:**
1. Ensure `progress_callback.update()` is called during training
2. Check that `NullProgressCallback` is not being used when RayProgressCallback is expected
3. Verify the ProgressReporter Actor is running:
   ```bash
   ray list actors --namespace algo_studio
   ```

### CUDA Out of Memory

**Error:** `RuntimeError: CUDA out of memory`

**Solutions:**
1. Reduce `batch_size` in training config
2. Use gradient accumulation
3. Enable mixed precision training (FP16)

### Model Not Found During Inference

**Error:** "Model not found. Please train first."

**Solution:** Run training before inference:
```python
# First train
train_result = algo.train(data_path, config)
# Then infer
infer_result = algo.infer(inputs)
```

### Ray Worker Import Error

**Error:** `ModuleNotFoundError: No module named 'my_algorithm'`

**Cause:** Algorithm not installed on Ray worker nodes

**Solution:** Install the algorithm package on all workers:
```bash
# On each worker
pip install -e /path/to/algorithms/my_algorithm
```

Or ensure the algorithm directory is on the PYTHONPATH:
```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/algorithms"
ray stop && ray start --address='192.168.0.126:6379'
```

### Slow Inference Performance

**Symptom:** Inference latency higher than expected_fps

**Solutions:**
1. Enable GPU acceleration (`torch.cuda.is_available()`)
2. Use model optimization (quantization, pruning)
3. Enable batch inference for multiple inputs
4. Use ONNX Runtime for deployment

### DataLoader Worker Error

**Error:** `RuntimeError: DataLoader worker (pid xxx) is killed`

**Solution:** Reduce `num_workers` in DataLoader or set to 0 for debugging:
```python
torch.utils.data.DataLoader(dataset, num_workers=0)
```

---

## Example: simple_classifier

See `examples/algorithms/simple_classifier/v1/__init__.py` for a complete reference implementation of an image classifier using ResNet18 on CIFAR-10.

### Quick Reference

| Method | Description |
|--------|-------------|
| `train(data_path, config, progress_callback)` | Train ResNet18 on CIFAR-10 |
| `infer(inputs)` | Classify images, return top-5 predictions |
| `verify(test_data)` | Evaluate model, return per-class accuracy |
| `get_metadata()` | Returns AlgorithmMetadata |

### Running the Example

```python
from examples.algorithms.simple_classifier.v1 import SimpleClassifier

algo = SimpleClassifier()

# Train (will download CIFAR-10 if data_path is empty)
result = algo.train(
    data_path="./data",
    config={"epochs": 2, "batch_size": 64},
    progress_callback=NullProgressCallback()
)

# Infer
result = algo.infer(["/path/to/image.jpg"])

# Verify
result = algo.verify("./data")
```
