"""
Simple Image Classifier using PyTorch torchvision models
"""
import os
import time
import torch
import torchvision
import torchvision.transforms as transforms
from torch import nn
from typing import Any

from algo_studio.core.algorithm import (
    AlgorithmInterface,
    TrainResult,
    InferenceResult,
    VerificationResult,
    AlgorithmMetadata
)


class SimpleClassifier(AlgorithmInterface):
    """Simple image classifier using ResNet18 on CIFAR-10"""

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.classes = ('plane', 'car', 'bird', 'cat', 'deer',
                        'dog', 'frog', 'horse', 'ship', 'truck')

    @staticmethod
    def get_metadata() -> AlgorithmMetadata:
        return AlgorithmMetadata(
            name="simple_classifier",
            version="v1",
            task_type="classification",
            deployment="cloud",
            expected_fps=100
        )

    def _build_model(self):
        """Build or load model"""
        if self.model is None:
            # Use ResNet18 pretrained on ImageNet, modify final layer for 10 classes
            self.model = torchvision.models.resnet18(weights='IMAGENET1K_V1')
            num_ftrs = self.model.fc.in_features
            self.model.fc = nn.Linear(num_ftrs, 10)
            self.model = self.model.to(self.device)

    def train(self, data_path: str, config: dict) -> TrainResult:
        """Train the classifier on CIFAR-10"""
        try:
            epochs = config.get("epochs", 2)
            batch_size = config.get("batch_size", 64)
            lr = config.get("learning_rate", 0.001)

            # If data_path is a dataset path, use it; otherwise download CIFAR10
            if data_path and os.path.exists(data_path):
                data_root = data_path
            else:
                data_root = './data'

            os.makedirs(data_root, exist_ok=True)

            # Data transforms
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
                root=data_root, train=True, download=True, transform=transform_train
            )
            trainloader = torch.utils.data.DataLoader(
                trainset, batch_size=batch_size, shuffle=True, num_workers=2
            )

            testset = torchvision.datasets.CIFAR10(
                root=data_root, train=False, download=True, transform=transform_test
            )
            testloader = torch.utils.data.DataLoader(
                testset, batch_size=batch_size, shuffle=False, num_workers=2
            )

            self._build_model()
            criterion = nn.CrossEntropyLoss()
            optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)

            # Training loop
            self.model.train()
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

                    if i % 100 == 99:
                        print(f'[{epoch + 1}, {i + 1}] loss: {running_loss / 100:.3f} '
                              f'acc: {100. * correct / total:.3f}%')
                        running_loss = 0.0

            # Evaluate
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
                'classes': self.classes,
                'accuracy': accuracy
            }, model_path)

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

    def infer(self, inputs: list) -> InferenceResult:
        """Run inference on input images"""
        try:
            if self.model is None:
                model_path = os.path.join(os.path.dirname(__file__), 'model.pth')
                if os.path.exists(model_path):
                    self._build_model()
                    checkpoint = torch.load(model_path, map_location=self.device)
                    self.model.load_state_dict(checkpoint['model_state_dict'])
                    self.classes = checkpoint.get('classes', self.classes)
                else:
                    return InferenceResult(
                        success=False,
                        error="Model not found. Please train first."
                    )

            self.model.eval()
            results = []
            total_time = 0

            for img_path in inputs:
                if os.path.exists(img_path):
                    from PIL import Image
                    img = Image.open(img_path).convert('RGB')

                    transform = transforms.Compose([
                        transforms.Resize(256),
                        transforms.CenterCrop(224),
                        transforms.ToTensor(),
                        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
                    ])

                    img_tensor = transform(img).unsqueeze(0).to(self.device)

                    start_time = time.time()
                    with torch.no_grad():
                        output = self.model(img_tensor)
                        probabilities = torch.nn.functional.softmax(output[0], dim=0)
                        top5_prob, top5_idx = torch.topk(probabilities, 5)
                    latency = (time.time() - start_time) * 1000

                    predictions = [
                        {"class": self.classes[idx], "probability": prob.item()}
                        for idx, prob in zip(top5_idx, top5_prob)
                    ]

                    results.append({
                        "image": img_path,
                        "predictions": predictions,
                        "latency_ms": latency
                    })
                    total_time += latency
                else:
                    results.append({
                        "image": img_path,
                        "error": "File not found"
                    })

            avg_latency = total_time / len(inputs) if inputs else 0

            return InferenceResult(
                success=True,
                outputs=results,
                latency_ms=avg_latency
            )

        except Exception as e:
            return InferenceResult(success=False, error=str(e))

    def verify(self, test_data: str) -> VerificationResult:
        """Verify model on test dataset"""
        try:
            if self.model is None:
                model_path = os.path.join(os.path.dirname(__file__), 'model.pth')
                if os.path.exists(model_path):
                    self._build_model()
                    checkpoint = torch.load(model_path, map_location=self.device)
                    self.model.load_state_dict(checkpoint['model_state_dict'])
                    self.classes = checkpoint.get('classes', self.classes)
                else:
                    return VerificationResult(
                        success=False,
                        passed=False,
                        details="Model not found. Please train first."
                    )

            # Use CIFAR-10 test set if no test_data path
            if test_data and os.path.exists(test_data):
                data_root = test_data
            else:
                data_root = './data'

            transform = transforms.Compose([
                transforms.ToTensor(),
                transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
            ])

            testset = torchvision.datasets.CIFAR10(
                root=data_root, train=False, download=True, transform=transform
            )
            testloader = torch.utils.data.DataLoader(
                testset, batch_size=64, shuffle=False, num_workers=2
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
                self.classes[i]: 100. * class_correct[i] / class_total[i]
                if class_total[i] > 0 else 0
                for i in range(10)
            }

            passed = accuracy >= 70.0  # Threshold

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
            return VerificationResult(success=False, passed=False, details=str(e))
