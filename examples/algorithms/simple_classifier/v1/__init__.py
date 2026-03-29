"""
Simple Image Classifier using PyTorch torchvision models

This is a reference implementation demonstrating the AlgoStudio algorithm interface.
It uses ResNet18 pretrained on ImageNet and fine-tunes on CIFAR-10.

Algorithm Interface:
- train(data_path, config, progress_callback) -> TrainResult
- infer(inputs) -> InferenceResult
- verify(test_data) -> VerificationResult
- get_metadata() -> AlgorithmMetadata

Usage:
    from examples.algorithms.simple_classifier.v1 import SimpleClassifier

    algo = SimpleClassifier()
    result = algo.train("/path/to/data", {"epochs": 10, "batch_size": 64})
    result = algo.infer(["image1.jpg", "image2.jpg"])
    result = algo.verify("/path/to/test_data")
"""

import os
import sys
import time
from typing import Any, Dict, List, Optional

import torch
import torchvision
import torchvision.transforms as transforms
from torch import nn

# Try to import PIL, handle case where it's not available
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# =============================================================================
# Result Classes
# =============================================================================

class TrainResult:
    """Training result containing model path and metrics."""

    def __init__(
        self,
        success: bool,
        model_path: str = None,
        metrics: Dict[str, Any] = None,
        error: str = None
    ):
        """
        Args:
            success: Whether training completed successfully
            model_path: Path where model was saved
            metrics: Training metrics (accuracy, loss, epochs, dataset)
            error: Error message if training failed
        """
        self.success = success
        self.model_path = model_path
        self.metrics = metrics or {}
        self.error = error


class InferenceResult:
    """Inference result containing predictions and latency."""

    def __init__(
        self,
        success: bool,
        outputs: List[Dict[str, Any]] = None,
        latency_ms: float = None,
        error: str = None
    ):
        """
        Args:
            success: Whether inference completed successfully
            outputs: List of prediction results, each containing:
                - image: input image path
                - predictions: list of {class, probability} dicts
                - latency_ms: inference time for this image
                - error: error message if failed
            latency_ms: Average latency across all inferences in milliseconds
            error: Error message if inference failed entirely
        """
        self.success = success
        self.outputs = outputs or []
        self.latency_ms = latency_ms
        self.error = error


class VerificationResult:
    """Verification result indicating whether model passes threshold."""

    def __init__(
        self,
        success: bool,
        passed: bool,
        metrics: Dict[str, Any] = None,
        details: str = None
    ):
        """
        Args:
            success: Whether verification ran to completion
            passed: Whether model passed verification threshold (>=70% accuracy)
            metrics: Verification metrics including overall_accuracy and per_class_accuracy
            details: Human-readable verification details
        """
        self.success = success
        self.passed = passed
        self.metrics = metrics or {}
        self.details = details


class AlgorithmMetadata:
    """Metadata describing the algorithm."""

    def __init__(
        self,
        name: str,
        version: str,
        task_type: str,
        deployment: str,
        expected_fps: int = None
    ):
        """
        Args:
            name: Algorithm name (simple_classifier)
            version: Semantic version (v1)
            task_type: Task type (classification)
            deployment: Deployment environment (cloud)
            expected_fps: Expected inference FPS (100)
        """
        self.name = name
        self.version = version
        self.task_type = task_type
        self.deployment = deployment
        self.expected_fps = expected_fps


# =============================================================================
# Progress Callback
# =============================================================================

class NullProgressCallback:
    """No-op progress callback for when progress reporting is not needed."""

    def update(self, current: int, total: int, description: str = ""):
        """Do nothing."""
        pass

    def set_description(self, description: str):
        """Do nothing."""
        pass


# =============================================================================
# Algorithm Implementation
# =============================================================================

class SimpleClassifier:
    """
    Simple image classifier using ResNet18 on CIFAR-10 dataset.

    This classifier fine-tunes a pretrained ResNet18 model on CIFAR-10,
    which contains 10 classes: plane, car, bird, cat, deer, dog, frog,
    horse, ship, truck.

    Example:
        >>> from examples.algorithms.simple_classifier.v1 import SimpleClassifier
        >>> algo = SimpleClassifier()
        >>> result = algo.train("/path/to/data", {"epochs": 2, "batch_size": 64})
        >>> print(result.success, result.model_path)
        >>> result = algo.infer(["/path/to/image.jpg"])
        >>> print(result.outputs)
    """

    # CIFAR-10 class labels
    CLASSES = ('plane', 'car', 'bird', 'cat', 'deer',
               'dog', 'frog', 'horse', 'ship', 'truck')

    def __init__(self):
        """Initialize the classifier with device detection."""
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None

    @staticmethod
    def get_metadata() -> AlgorithmMetadata:
        """
        Return algorithm metadata.

        Returns:
            AlgorithmMetadata with algorithm information
        """
        return AlgorithmMetadata(
            name="simple_classifier",
            version="v1",
            task_type="classification",
            deployment="cloud",
            expected_fps=100
        )

    def _build_model(self):
        """Build or load the model architecture."""
        if self.model is None:
            # Use ResNet18 pretrained on ImageNet, modify final layer for 10 classes
            self.model = torchvision.models.resnet18(weights='IMAGENET1K_V1')
            num_ftrs = self.model.fc.in_features
            self.model.fc = nn.Linear(num_ftrs, 10)
            self.model = self.model.to(self.device)

    def _load_model(self):
        """Load trained model weights from disk."""
        model_path = os.path.join(os.path.dirname(__file__), 'model.pth')
        if not os.path.exists(model_path):
            return False

        self._build_model()
        checkpoint = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.classes = checkpoint.get('classes', self.CLASSES)
        return True

    def train(
        self,
        data_path: str,
        config: dict,
        progress_callback: Optional[object] = None
    ) -> TrainResult:
        """
        Train the classifier on CIFAR-10.

        Args:
            data_path: Root directory for dataset. Uses CIFAR-10 download if empty
                       or if path does not exist.
            config: Training configuration with keys:
                - epochs (int): Number of training epochs (default: 2)
                - batch_size (int): Batch size (default: 64)
                - learning_rate (float): Learning rate (default: 0.001)
            progress_callback: Callback for progress updates. Should implement:
                - update(current, total, description)

        Returns:
            TrainResult with success status, model_path, and metrics
        """
        progress = progress_callback or NullProgressCallback()

        try:
            # Parse configuration
            epochs = config.get("epochs", 2)
            batch_size = config.get("batch_size", 64)
            lr = config.get("learning_rate", 0.001)

            # Determine data root
            if data_path and os.path.exists(data_path):
                data_root = data_path
            else:
                data_root = './data'

            os.makedirs(data_root, exist_ok=True)

            # Define data transforms
            transform_train = transforms.Compose([
                transforms.RandomCrop(32, padding=4),
                transforms.RandomHorizontalFlip(),
                transforms.ToTensor(),
                transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
            ])

            transform_test = transforms.Compose([
                transforms.ToTensor(),
                transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
            ])

            # Load CIFAR-10 dataset
            trainset = torchvision.datasets.CIFAR10(
                root=data_root,
                train=True,
                download=True,
                transform=transform_train
            )
            trainloader = torch.utils.data.DataLoader(
                trainset,
                batch_size=batch_size,
                shuffle=True,
                num_workers=2
            )

            testset = torchvision.datasets.CIFAR10(
                root=data_root,
                train=False,
                download=True,
                transform=transform_test
            )
            testloader = torch.utils.data.DataLoader(
                testset,
                batch_size=batch_size,
                shuffle=False,
                num_workers=2
            )

            # Calculate total batches for progress reporting
            total_batches = len(trainloader) * epochs

            # Build model and set up training
            self._build_model()
            criterion = nn.CrossEntropyLoss()
            optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)

            # Training loop
            self.model.train()
            current_batch = 0

            for epoch in range(epochs):
                running_loss = 0.0
                correct = 0
                total = 0

                for i, (inputs, labels) in enumerate(trainloader):
                    inputs, labels = inputs.to(self.device), labels.to(self.device)

                    optimizer.zero_grad()
                    outputs = self.model(inputs)
                    loss = criterion(outputs, labels)
                    loss.backward()
                    optimizer.step()

                    running_loss += loss.item()
                    _, predicted = outputs.max(1)
                    total += labels.size(0)
                    correct += predicted.eq(labels).sum().item()
                    current_batch += 1

                    # Report progress every 100 batches or on last batch
                    if i % 100 == 99 or i == len(trainloader) - 1:
                        progress.update(
                            current_batch,
                            total_batches,
                            f"Epoch {epoch + 1}/{epochs} - acc: {100. * correct / total:.1f}%"
                        )

            # Evaluate on test set
            self.model.eval()
            correct = 0
            total = 0
            with torch.no_grad():
                for inputs, labels in testloader:
                    inputs, labels = inputs.to(self.device), labels.to(self.device)
                    outputs = self.model(inputs)
                    _, predicted = outputs.max(1)
                    total += labels.size(0)
                    correct += predicted.eq(labels).sum().item()

            accuracy = 100. * correct / total

            # Save model
            model_path = os.path.join(os.path.dirname(__file__), 'model.pth')
            torch.save({
                'model_state_dict': self.model.state_dict(),
                'classes': self.CLASSES,
                'accuracy': accuracy
            }, model_path)

            progress.update(total_batches, total_batches, "Training completed")

            return TrainResult(
                success=True,
                model_path=model_path,
                metrics={
                    "accuracy": accuracy,
                    "epochs": epochs,
                    "dataset": "CIFAR-10"
                }
            )

        except Exception as e:
            return TrainResult(success=False, error=str(e))

    def infer(self, inputs: List[str]) -> InferenceResult:
        """
        Run inference on input images.

        Args:
            inputs: List of image file paths to classify

        Returns:
            InferenceResult with predictions and latency for each image
        """
        # Load model if not already loaded
        if self.model is None:
            if not self._load_model():
                return InferenceResult(
                    success=False,
                    error="Model not found. Please train first."
                )

        if not PIL_AVAILABLE:
            return InferenceResult(
                success=False,
                error="PIL not available. Please install pillow."
            )

        self.model.eval()
        results = []
        total_time = 0.0

        transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
        ])

        for img_path in inputs:
            if not os.path.exists(img_path):
                results.append({
                    "image": img_path,
                    "error": "File not found"
                })
                continue

            try:
                img = Image.open(img_path).convert('RGB')
                img_tensor = transform(img).unsqueeze(0).to(self.device)

                start_time = time.time()
                with torch.no_grad():
                    output = self.model(img_tensor)
                    probabilities = torch.nn.functional.softmax(output[0], dim=0)
                    top5_prob, top5_idx = torch.topk(probabilities, 5)
                latency = (time.time() - start_time) * 1000

                predictions = [
                    {"class": self.CLASSES[idx], "probability": prob.item()}
                    for idx, prob in zip(top5_idx, top5_prob)
                ]

                results.append({
                    "image": img_path,
                    "predictions": predictions,
                    "latency_ms": latency
                })
                total_time += latency

            except Exception as e:
                results.append({
                    "image": img_path,
                    "error": str(e)
                })

        avg_latency = total_time / len(inputs) if inputs else 0

        return InferenceResult(
            success=True,
            outputs=results,
            latency_ms=avg_latency
        )

    def verify(self, test_data: str) -> VerificationResult:
        """
        Verify model performance on test dataset.

        Uses CIFAR-10 test set if test_data path is not provided or doesn't exist.
        Model is considered passing if overall accuracy >= 70%.

        Args:
            test_data: Root directory containing test dataset. Uses CIFAR-10
                      test set if empty or not found.

        Returns:
            VerificationResult with passed status and per-class accuracy metrics
        """
        # Load model if not already loaded
        if self.model is None:
            if not self._load_model():
                return VerificationResult(
                    success=False,
                    passed=False,
                    details="Model not found. Please train first."
                )

        try:
            # Determine data root
            if test_data and os.path.exists(test_data):
                data_root = test_data
            else:
                data_root = './data'

            transform = transforms.Compose([
                transforms.ToTensor(),
                transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
            ])

            testset = torchvision.datasets.CIFAR10(
                root=data_root,
                train=False,
                download=True,
                transform=transform
            )
            testloader = torch.utils.data.DataLoader(
                testset,
                batch_size=64,
                shuffle=False,
                num_workers=2
            )

            self.model.eval()
            correct = 0
            total = 0
            class_correct = [0] * 10
            class_total = [0] * 10

            with torch.no_grad():
                for inputs, labels in testloader:
                    inputs, labels = inputs.to(self.device), labels.to(self.device)
                    outputs = self.model(inputs)
                    _, predicted = outputs.max(1)
                    total += labels.size(0)
                    correct += predicted.eq(labels).sum().item()

                    for i in range(len(labels)):
                        label = labels[i].item()
                        class_total[label] += 1
                        if predicted[i] == label:
                            class_correct[label] += 1

            accuracy = 100. * correct / total
            per_class_accuracy = {
                self.CLASSES[i]: 100. * class_correct[i] / class_total[i]
                if class_total[i] > 0 else 0
                for i in range(10)
            }

            passed = accuracy >= 70.0  # Threshold for passing verification

            return VerificationResult(
                success=True,
                passed=passed,
                metrics={
                    "overall_accuracy": accuracy,
                    "per_class_accuracy": per_class_accuracy
                },
                details=f"Overall accuracy: {accuracy:.2f}%"
            )

        except Exception as e:
            return VerificationResult(
                success=False,
                passed=False,
                details=str(e)
            )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "SimpleClassifier",
    "TrainResult",
    "InferenceResult",
    "VerificationResult",
    "AlgorithmMetadata",
    "NullProgressCallback",
]
