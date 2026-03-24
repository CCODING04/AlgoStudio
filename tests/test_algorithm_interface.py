import pytest
from algo_studio.core.algorithm import AlgorithmInterface, TrainResult, InferenceResult, VerificationResult, AlgorithmMetadata

def test_train_result_dataclass():
    result = TrainResult(
        success=True,
        model_path="/path/to/model.pt",
        metrics={"mAP": 0.78, "FPS": 35}
    )
    assert result.success is True
    assert result.model_path == "/path/to/model.pt"
    assert result.metrics["mAP"] == 0.78

def test_inference_result_dataclass():
    result = InferenceResult(
        success=True,
        outputs=[{"class": "dog", "confidence": 0.95}],
        latency_ms=12.5
    )
    assert result.success is True
    assert len(result.outputs) == 1

def test_algorithm_metadata_dataclass():
    metadata = AlgorithmMetadata(
        name="yolo_family",
        version="v1.0.0",
        task_type="object_detection",
        deployment="edge",
        expected_fps=30
    )
    assert metadata.name == "yolo_family"
    assert metadata.task_type == "object_detection"