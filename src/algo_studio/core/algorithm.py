from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union


@dataclass
class TrainResult:
    success: bool
    model_path: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class InferenceResult:
    success: bool
    outputs: Optional[List[Dict[str, Any]]] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class VerificationResult:
    success: bool
    passed: bool
    metrics: Optional[Dict[str, Any]] = None
    details: Optional[str] = None


@dataclass
class AlgorithmMetadata:
    name: str
    version: str
    task_type: str
    deployment: str  # "edge" | "cloud"
    expected_fps: Optional[int] = None


class AlgorithmInterface:
    """算法接口基类，所有算法必须实现此接口"""

    def train(self, data_path: str, config: dict) -> TrainResult:
        """训练接口"""
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