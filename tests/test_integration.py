# tests/test_integration.py
import pytest
import subprocess
import time

def test_api_health():
    """测试 API 服务健康检查"""
    import requests
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    except requests.exceptions.ConnectionError:
        pytest.skip("API server not running")

def test_ray_initialization():
    """测试 Ray 是否可用"""
    import ray
    if not ray.is_initialized():
        ray.init()
    assert ray.is_initialized()
    ray.shutdown()