# tests/factories/algorithm_factory.py
"""Algorithm data factory using factory-boy pattern."""

import factory
from faker import Faker
from typing import Any, Dict, List

fake = Faker()


class AlgorithmMetadataFactory(factory.DictFactory):
    """Factory for generating AlgorithmMetadata test data."""

    name = factory.Faker("random_element", elements=["simple_classifier", "simple_detector", "yolo"])
    version = factory.Faker("random_element", elements=["v1", "v2", "v1.0.0"])
    description = factory.Faker("sentence")
    supported_task_types = factory.LazyFunction(
        lambda: ["train", "infer", "verify"]
    )
    input_schema = factory.DictFactory
    output_schema = factory.DictFactory


class TrainResultFactory(factory.DictFactory):
    """Factory for generating TrainResult test data."""

    success = True
    model_path = factory.LazyFunction(lambda: f"/models/{fake.uuid4()}.pth")
    metrics = factory.LazyFunction(
        lambda: {
            "accuracy": fake.pyfloat(min_value=0.7, max_value=0.99),
            "loss": fake.pyfloat(min_value=0.01, max_value=0.3),
            "f1_score": fake.pyfloat(min_value=0.7, max_value=0.99),
        }
    )
    error = None


class InferenceResultFactory(factory.DictFactory):
    """Factory for generating InferenceResult test data."""

    success = True
    outputs = factory.LazyFunction(lambda: [[fake.random_int(0, 1) for _ in range(10)] for _ in range(5)])
    latency_ms = factory.LazyFunction(lambda: fake.pyfloat(min_value=1.0, max_value=100.0))
    error = None


class VerificationResultFactory(factory.DictFactory):
    """Factory for generating VerificationResult test data."""

    success = True
    passed = True
    metrics = factory.LazyFunction(
        lambda: {
            "precision": fake.pyfloat(min_value=0.7, max_value=1.0),
            "recall": fake.pyfloat(min_value=0.7, max_value=1.0),
        }
    )
    details = factory.LazyFunction(lambda: {"test_cases": fake.random_int(10, 100), "failures": 0})
    error = None


class FailedTrainResultFactory(TrainResultFactory):
    """Factory for failed training results."""
    success = False
    model_path = None
    error = factory.Faker("sentence")


class FailedInferenceResultFactory(InferenceResultFactory):
    """Factory for failed inference results."""
    success = False
    outputs = None
    error = factory.Faker("sentence")
