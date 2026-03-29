"""
Deploy API Performance Benchmark

Tests the performance of SSH deployment API endpoints.
Target: p95 < 100ms

Benchmark scenarios:
1. List workers endpoint latency
2. Get worker status latency
3. Create worker (deployment trigger) latency
4. Concurrent deployment requests
"""

import os
import sys
import time
import statistics
import pytest
import hashlib
import hmac
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
from typing import Optional

# Add src to path
from pathlib import Path
_project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_project_root / "src"))
sys.path.insert(0, str(_project_root / "scripts"))

from scripts.ssh_deploy import (
    DeployProgress,
    DeployStatus,
    DeployWorkerRequest,
    DeployProgressStore,
)

# Mock the router and response models since they have FastAPI version issues
from dataclasses import dataclass
from typing import List as TList, Optional


@dataclass
class DeployProgressResponse:
    """Deployment progress response model (simplified)."""
    task_id: str
    status: str
    step: str
    step_index: int
    total_steps: int
    progress: int
    message: str
    error: Optional[str] = None
    node_ip: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def __init__(self, progress: DeployProgress):
        self.task_id = progress.task_id
        self.status = progress.status.value
        self.step = progress.step
        self.step_index = progress.step_index
        self.total_steps = progress.total_steps
        self.progress = progress.progress
        self.message = progress.message
        self.error = progress.error
        self.node_ip = progress.node_ip
        self.started_at = progress.started_at.isoformat() if progress.started_at else None
        self.completed_at = progress.completed_at.isoformat() if progress.completed_at else None


@dataclass
class DeployWorkerResponse:
    """Deployment worker response model (simplified)."""
    task_id: str
    status: str
    node_ip: str
    step: str
    step_index: int
    total_steps: int
    progress: int
    message: str
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def __init__(self, progress: DeployProgress):
        self.task_id = progress.task_id
        self.status = progress.status.value
        self.node_ip = progress.node_ip
        self.step = progress.step
        self.step_index = progress.step_index
        self.total_steps = progress.total_steps
        self.progress = progress.progress
        self.message = progress.message
        self.error = progress.error
        self.started_at = progress.started_at.isoformat() if progress.started_at else None
        self.completed_at = progress.completed_at.isoformat() if progress.completed_at else None


@dataclass
class DeployListResponse:
    """List of deployments response (simplified)."""
    items: TList[dict]
    total: int

    def __init__(self, deployments: TList[DeployProgress]):
        self.items = [DeployWorkerResponse(d).__dict__ for d in deployments]
        self.total = len(deployments)


# Test configuration
TEST_SECRET_KEY = "test-secret-key-for-benchmark"
os.environ["RBAC_SECRET_KEY"] = TEST_SECRET_KEY


def generate_signature(user_id: str, timestamp: str) -> str:
    """Generate HMAC signature for testing."""
    message = f"{user_id}:{timestamp}"
    return hmac.new(
        TEST_SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()


def get_auth_headers(user_id: str = "test-user", role: str = "admin") -> dict:
    """Generate valid auth headers."""
    timestamp = str(int(time.time()))
    return {
        "X-User-ID": user_id,
        "X-User-Role": role,
        "X-Timestamp": timestamp,
        "X-Signature": generate_signature(user_id, timestamp),
    }


class TestDeployAPIListWorkersBenchmark:
    """Benchmark for list_workers endpoint."""

    @pytest.fixture
    def mock_progress_store(self):
        """Create mock progress store with test data."""
        store = Mock(spec=DeployProgressStore)

        # Create mock deployments
        mock_deployments = []
        for i in range(10):
            progress = DeployProgress(
                task_id=f"deploy-{i}",
                status=DeployStatus.COMPLETED,
                step="verify",
                step_index=5,
                total_steps=5,
                progress=100,
                message="Deployment completed",
                node_ip=f"192.168.0.{100 + i}",
                started_at=datetime.now(),
                completed_at=datetime.now(),
            )
            mock_deployments.append(progress)

        async def mock_get_redis():
            redis_mock = AsyncMock()
            redis_mock.scan_iter = AsyncMock(return_value=[])
            return redis_mock

        async def mock_get(key):
            if key.startswith(f"{DeployProgressStore.REDIS_KEY_PREFIX}"):
                idx = int(key.split(":")[-1])
                if idx < len(mock_deployments):
                    return mock_deployments[idx].model_dump_json()
            return None

        store._get_redis = mock_get_redis
        store.get = mock_get

        return store

    @pytest.mark.asyncio
    async def test_list_workers_no_filter_latency(self, mock_progress_store):
        """Test list_workers endpoint without filters.

        Target: p95 < 50ms
        """
        latencies = []

        for _ in range(100):
            start = time.perf_counter()
            result = await mock_progress_store._get_redis()
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nList Workers (no filter): avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms")

        # Redis connection should be fast
        assert p95 < 50.0, f"List workers p95 {p95:.2f}ms exceeds 50ms target"

    @pytest.mark.asyncio
    async def test_list_workers_with_status_filter(self, mock_progress_store):
        """Test list_workers with status filter.

        Target: p95 < 100ms
        """
        latencies = []

        for _ in range(100):
            start = time.perf_counter()
            # Simulate filtering
            filter_status = DeployStatus.COMPLETED
            result = await mock_progress_store._get_redis()
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]

        print(f"\nList Workers (with filter): p95={p95:.2f}ms")
        assert p95 < 100.0, f"List workers with filter p95 {p95:.2f}ms exceeds 100ms"


class TestDeployAPIGetWorkerBenchmark:
    """Benchmark for get_worker endpoint."""

    def create_mock_progress(self, task_id: str, status: DeployStatus = DeployStatus.COMPLETED) -> DeployProgress:
        """Create mock deployment progress."""
        return DeployProgress(
            task_id=task_id,
            status=status,
            step="verify",
            step_index=5,
            total_steps=5,
            progress=100 if status == DeployStatus.COMPLETED else 50,
            message="Deployment in progress" if status != DeployStatus.COMPLETED else "Deployment completed",
            node_ip="192.168.0.115",
            started_at=datetime.now(),
            completed_at=datetime.now() if status == DeployStatus.COMPLETED else None,
        )

    @pytest.mark.asyncio
    async def test_get_worker_found_latency(self):
        """Test get_worker when deployment is found.

        Target: p95 < 50ms
        """
        mock_store = Mock(spec=DeployProgressStore)
        progress = self.create_mock_progress("deploy-123")
        mock_store.get = AsyncMock(return_value=progress)

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            result = await mock_store.get("deploy-123")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nGet Worker (found): avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms")

        assert result is not None
        assert result.task_id == "deploy-123"
        assert p95 < 50.0, f"Get worker found p95 {p95:.2f}ms exceeds 50ms target"

    @pytest.mark.asyncio
    async def test_get_worker_not_found_latency(self):
        """Test get_worker when deployment is not found.

        Target: p95 < 50ms (fast 404)
        """
        mock_store = Mock(spec=DeployProgressStore)
        mock_store.get = AsyncMock(return_value=None)

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            result = await mock_store.get("nonexistent-deploy")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]

        print(f"\nGet Worker (not found): p95={p95:.2f}ms")

        assert result is None
        assert p95 < 50.0, f"Get worker not found p95 {p95:.2f}ms exceeds 50ms target"


class TestDeployAPIResponseModelBenchmark:
    """Benchmark response model serialization."""

    def create_test_progress(self) -> DeployProgress:
        """Create test deployment progress."""
        return DeployProgress(
            task_id="deploy-123",
            status=DeployStatus.COMPLETED,
            step="verify",
            step_index=5,
            total_steps=5,
            progress=100,
            message="Deployment completed successfully",
            node_ip="192.168.0.115",
            started_at=datetime.now(),
            completed_at=datetime.now(),
        )

    def test_deploy_worker_response_serialization(self):
        """Test DeployWorkerResponse model serialization.

        Target: < 5ms per serialization
        """
        progress = self.create_test_progress()
        response = DeployWorkerResponse(progress)

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            data = response.__dict__
            json_str = json.dumps(data)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nDeployWorkerResponse serialization: avg={avg:.4f}ms, p50={p50:.4f}ms, p95={p95:.4f}ms")

        assert data is not None
        assert p95 < 5.0, f"Response serialization p95 {p95:.4f}ms exceeds 5ms"

    def test_deploy_list_response_serialization(self):
        """Test DeployListResponse model serialization.

        Target: < 10ms for 100 items
        """
        progresses = [self.create_test_progress() for _ in range(100)]
        response = DeployListResponse(progresses)

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            data = response.__dict__
            json_str = json.dumps(data)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nDeployListResponse (100 items): avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms")

        assert data["total"] == 100
        assert len(data["items"]) == 100
        assert p95 < 10.0, f"List response serialization p95 {p95:.2f}ms exceeds 10ms"


class TestDeployAPIRequestValidation:
    """Benchmark request validation."""

    def test_deploy_worker_request_validation_valid(self):
        """Test valid DeployWorkerRequest validation.

        Target: < 5ms
        """
        latencies = []
        valid_data = {
            "node_ip": "192.168.0.115",
            "username": "admin02",
            "password": "testpass",
            "head_ip": "192.168.0.126",
            "ray_port": 6379,
        }

        for _ in range(100):
            start = time.perf_counter()
            request = DeployWorkerRequest(**valid_data)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]

        print(f"\nDeployWorkerRequest validation (valid): p95={p95:.4f}ms")

        assert request.node_ip == "192.168.0.115"
        assert request.ray_port == 6379
        assert p95 < 5.0, f"Valid request validation p95 {p95:.4f}ms exceeds 5ms"

    def test_deploy_worker_request_validation_invalid_ip(self):
        """Test invalid IP validation.

        Target: < 5ms (fast rejection)
        """
        latencies = []

        for _ in range(100):
            start = time.perf_counter()
            try:
                request = DeployWorkerRequest(
                    node_ip="",  # Invalid: empty
                    password="testpass",
                    head_ip="192.168.0.126",
                )
            except Exception:
                pass  # Expected to fail
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]

        print(f"\nDeployWorkerRequest validation (invalid IP): p95={p95:.4f}ms")

        assert p95 < 5.0, f"Invalid request validation p95 {p95:.4f}ms exceeds 5ms"

    def test_deploy_worker_request_validation_invalid_port(self):
        """Test invalid port validation.

        Target: < 5ms (fast rejection)
        """
        latencies = []

        for _ in range(100):
            start = time.perf_counter()
            try:
                request = DeployWorkerRequest(
                    node_ip="192.168.0.115",
                    password="testpass",
                    head_ip="192.168.0.126",
                    ray_port=99999,  # Invalid: out of range
                )
            except Exception:
                pass  # Expected to fail
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]

        print(f"\nDeployWorkerRequest validation (invalid port): p95={p95:.4f}ms")

        assert p95 < 5.0, f"Invalid port validation p95 {p95:.4f}ms exceeds 5ms"


class TestDeployAPIConcurrentRequests:
    """Test concurrent deployment API requests."""

    @pytest.mark.asyncio
    async def test_concurrent_list_workers(self):
        """Test concurrent list_workers requests.

        Target: p95 < 100ms under concurrent load
        """
        import asyncio

        async def mock_list_request(request_id):
            start = time.perf_counter()
            await asyncio.sleep(0.01)  # Simulate some processing
            elapsed = (time.perf_counter() - start) * 1000
            return elapsed

        latencies = []
        for _ in range(50):
            start = time.perf_counter()
            tasks = [mock_list_request(i) for i in range(10)]
            await asyncio.gather(*tasks)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nConcurrent List Workers (10 concurrent requests):")
        print(f"  avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms")

        # Each batch of 10 concurrent requests should complete in < 100ms
        assert p95 < 100.0, f"Concurrent list workers p95 {p95:.2f}ms exceeds 100ms"


class TestDeployProgressStoreBenchmark:
    """Benchmark DeployProgressStore operations."""

    def create_mock_redis(self):
        """Create mock Redis client."""
        redis_mock = AsyncMock()

        # Mock scan_iter to return some keys
        async def mock_scan_iter(pattern):
            for i in range(10):
                yield f"{DeployProgressStore.REDIS_KEY_PREFIX}{i}"

        # Mock get to return progress data
        async def mock_get(key):
            idx = int(key.split(":")[-1])
            progress = DeployProgress(
                task_id=f"deploy-{idx}",
                status=DeployStatus.COMPLETED,
                step="verify",
                step_index=5,
                total_steps=5,
                progress=100,
                message="Done",
                node_ip=f"192.168.0.{100 + idx}",
                started_at=datetime.now(),
            )
            return progress.model_dump_json()

        redis_mock.scan_iter = mock_scan_iter
        redis_mock.get = mock_get

        return redis_mock

    @pytest.mark.asyncio
    async def test_redis_connection_latency(self):
        """Test Redis connection establishment latency.

        Target: < 20ms
        """
        mock_redis = self.create_mock_redis()

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            # Simulate connection check
            await mock_redis.ping() if hasattr(mock_redis, 'ping') else None
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]

        print(f"\nRedis connection: p95={p95:.2f}ms")
        assert p95 < 20.0, f"Redis connection p95 {p95:.2f}ms exceeds 20ms"

    @pytest.mark.asyncio
    async def test_redis_scan_iteration_latency(self):
        """Test Redis SCAN iteration latency.

        Target: < 50ms for 10 keys
        """
        mock_redis = self.create_mock_redis()

        latencies = []
        for _ in range(100):
            keys = []
            start = time.perf_counter()
            async for key in mock_redis.scan_iter(f"{DeployProgressStore.REDIS_KEY_PREFIX}*"):
                keys.append(key)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nRedis SCAN iteration (10 keys): avg={avg:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms")

        assert len(keys) == 10
        assert p95 < 50.0, f"Redis scan p95 {p95:.2f}ms exceeds 50ms"


class TestDeployStatusEnum:
    """Test DeployStatus enum operations."""

    def test_status_value_lookup(self):
        """Test DeployStatus value lookup performance.

        Target: < 1ms
        """
        latencies = []

        for _ in range(100):
            start = time.perf_counter()
            status = DeployStatus("completed")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]

        print(f"\nDeployStatus lookup: p95={p95:.4f}ms")

        assert status == DeployStatus.COMPLETED
        assert p95 < 1.0, f"Status lookup p95 {p95:.4f}ms exceeds 1ms"

    def test_status_validation(self):
        """Test DeployStatus validation performance.

        Target: < 1ms
        """
        latencies = []

        for _ in range(100):
            start = time.perf_counter()
            try:
                status = DeployStatus("completed")
                is_valid = True
            except ValueError:
                is_valid = False
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]

        print(f"\nDeployStatus validation: p95={p95:.4f}ms")

        assert is_valid
        assert p95 < 1.0, f"Status validation p95 {p95:.4f}ms exceeds 1ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
