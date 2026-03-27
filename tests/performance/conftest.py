# Performance Test Configuration
import pytest
import json
import os

# Base paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BENCHMARK_DIR = os.path.join(PROJECT_ROOT, "tests", "performance", "benchmarks")
MONITORING_DIR = os.path.join(PROJECT_ROOT, "monitoring")


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "performance: mark test as a performance benchmark"
    )
    config.addinivalue_line(
        "markers", "api: mark test as API performance test"
    )
    config.addinivalue_line(
        "markers", "gpu: mark test as GPU performance test"
    )
    config.addinivalue_line(
        "markers", "database: mark test as database performance test"
    )
    config.addinivalue_line(
        "markers", "throughput: mark test as throughput test"
    )


@pytest.fixture(scope="session")
def benchmark_dir():
    """Return the benchmark directory path."""
    return BENCHMARK_DIR


@pytest.fixture(scope="session")
def load_api_baseline(benchmark_dir):
    """Load API baseline benchmarks."""
    with open(os.path.join(benchmark_dir, "api_baseline.json")) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def load_gpu_baseline(benchmark_dir):
    """Load GPU baseline benchmarks."""
    with open(os.path.join(benchmark_dir, "gpu_baseline.json")) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def load_db_baseline(benchmark_dir):
    """Load database baseline benchmarks."""
    with open(os.path.join(benchmark_dir, "db_baseline.json")) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def load_throughput_baseline(benchmark_dir):
    """Load throughput baseline benchmarks."""
    with open(os.path.join(benchmark_dir, "throughput_baseline.json")) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def api_base_url():
    """Return the API base URL."""
    return "http://192.168.0.126:8000"


@pytest.fixture(scope="session")
def ray_address():
    """Return the Ray cluster address."""
    return "192.168.0.126:6379"
