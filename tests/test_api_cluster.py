# tests/test_api_cluster.py
"""Tests for Cluster API Routes"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock
from algo_studio.api.main import app
from algo_studio.core.ray_dashboard_client import RayAPIClient, RayAPIResponse, CircuitState


@pytest.mark.asyncio
async def test_cluster_status_success():
    """Test successful cluster status retrieval"""
    mock_responses = [
        RayAPIResponse(success=True, data={"status": "ok"}),  # health_check
        RayAPIResponse(success=True, data={"cluster": "ready"}),  # get_cluster_status
        RayAPIResponse(success=True, data={"nodes": []}),  # list_nodes
        RayAPIResponse(success=True, data={"actors": []}),  # list_actors
        RayAPIResponse(success=True, data={"tasks": []}),  # list_tasks
    ]

    with patch('algo_studio.core.ray_dashboard_client.RayAPIClient') as MockClient:
        instance = MockClient.return_value
        instance.health_check.return_value = mock_responses[0]
        instance.get_cluster_status.return_value = mock_responses[1]
        instance.list_nodes.return_value = mock_responses[2]
        instance.list_actors.return_value = mock_responses[3]
        instance.list_tasks.return_value = mock_responses[4]

        # Patch get_ray_client to return our mock
        with patch('algo_studio.api.routes.cluster.get_ray_client', return_value=instance):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/cluster/status")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True


@pytest.mark.asyncio
async def test_cluster_status_health_check_failure():
    """Test cluster status when health check fails"""
    with patch('algo_studio.core.ray_dashboard_client.RayAPIClient') as MockClient:
        instance = MockClient.return_value
        instance.health_check.return_value = RayAPIResponse(
            success=False, data=None, error="Connection refused"
        )
        # Set up other responses that won't be used but need to exist
        instance.get_cluster_status.return_value = RayAPIResponse(success=True, data={})
        instance.list_nodes.return_value = RayAPIResponse(success=True, data={"nodes": []})
        instance.list_actors.return_value = RayAPIResponse(success=True, data={"actors": []})
        instance.list_tasks.return_value = RayAPIResponse(success=True, data={"tasks": []})

        with patch('algo_studio.api.routes.cluster.get_ray_client', return_value=instance):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/cluster/status")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False
    assert "Connection refused" in data["error"]


@pytest.mark.asyncio
async def test_list_nodes_success():
    """Test successful nodes listing"""
    mock_response = RayAPIResponse(
        success=True,
        data={
            "nodes": [
                {
                    "node_id": "node-1",
                    "ip": "192.168.0.101",
                    "hostname": "worker-1",
                    "status": "alive",
                    "resources": {"CPU": 24, "GPU": 1}
                }
            ]
        }
    )

    with patch('algo_studio.core.ray_dashboard_client.RayAPIClient') as MockClient:
        instance = MockClient.return_value
        instance.list_nodes.return_value = mock_response

        with patch('algo_studio.api.routes.cluster.get_ray_client', return_value=instance):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/cluster/nodes")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["node_id"] == "node-1"
    assert data[0]["gpu_count"] == 1


@pytest.mark.asyncio
async def test_list_nodes_api_failure():
    """Test nodes listing when API fails"""
    with patch('algo_studio.core.ray_dashboard_client.RayAPIClient') as MockClient:
        instance = MockClient.return_value
        instance.list_nodes.return_value = RayAPIResponse(
            success=False, data=None, error="API unavailable"
        )

        with patch('algo_studio.api.routes.cluster.get_ray_client', return_value=instance):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/cluster/nodes")

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_list_actors_success():
    """Test successful actors listing"""
    mock_response = RayAPIResponse(
        success=True,
        data={
            "actors": [
                {
                    "actor_id": "actor-1",
                    "class_name": "Worker",
                    "state": "ALIVE",
                }
            ]
        }
    )

    with patch('algo_studio.core.ray_dashboard_client.RayAPIClient') as MockClient:
        instance = MockClient.return_value
        instance.list_actors.return_value = mock_response

        with patch('algo_studio.api.routes.cluster.get_ray_client', return_value=instance):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/cluster/actors")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["actor_id"] == "actor-1"


@pytest.mark.asyncio
async def test_list_actors_with_limit():
    """Test actors listing with custom limit"""
    mock_response = RayAPIResponse(
        success=True,
        data={"actors": []}
    )

    with patch('algo_studio.core.ray_dashboard_client.RayAPIClient') as MockClient:
        instance = MockClient.return_value
        instance.list_actors.return_value = mock_response

        with patch('algo_studio.api.routes.cluster.get_ray_client', return_value=instance):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/cluster/actors?limit=50")

    assert response.status_code == 200
    instance.list_actors.assert_called_once_with(limit=50)


@pytest.mark.asyncio
async def test_health_check_healthy():
    """Test health check when system is healthy"""
    with patch('algo_studio.core.ray_dashboard_client.RayAPIClient') as MockClient:
        instance = MockClient.return_value
        instance.health_check.return_value = RayAPIResponse(
            success=True, data={"status": "ok"}
        )
        instance.get_cluster_status.return_value = RayAPIResponse(
            success=True, data={"cluster": "ready"}
        )
        instance.get_circuit_state.return_value = "closed"
        instance.get_cache_stats.return_value = {"size": 10, "max_size": 100}

        with patch('algo_studio.api.routes.cluster.get_ray_client', return_value=instance):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/cluster/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["ray_dashboard"] is True


@pytest.mark.asyncio
async def test_health_check_degraded():
    """Test health check when system is degraded"""
    with patch('algo_studio.core.ray_dashboard_client.RayAPIClient') as MockClient:
        instance = MockClient.return_value
        # health_check fails, but get_cluster_status succeeds
        # This results in "degraded" status per the API logic
        instance.health_check.return_value = RayAPIResponse(
            success=False, data=None, error="Connection refused"
        )
        instance.get_cluster_status.return_value = RayAPIResponse(success=True, data={})
        instance.get_circuit_state.return_value = "closed"
        instance.get_cache_stats.return_value = {"size": 0, "max_size": 100}

        with patch('algo_studio.api.routes.cluster.get_ray_client', return_value=instance):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/cluster/health")

    assert response.status_code == 200
    data = response.json()
    # Per API logic: health failed + cluster succeeded = degraded
    assert data["status"] == "degraded"


@pytest.mark.asyncio
async def test_get_circuit_breaker_status():
    """Test getting circuit breaker status"""
    with patch('algo_studio.core.ray_dashboard_client.RayAPIClient') as MockClient:
        instance = MockClient.return_value
        instance.get_circuit_state.return_value = "closed"
        instance.get_cache_stats.return_value = {"size": 5, "max_size": 100}

        with patch('algo_studio.api.routes.cluster.get_ray_client', return_value=instance):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/cluster/circuit-breaker")

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "closed"


@pytest.mark.asyncio
async def test_invalidate_all_cache():
    """Test invalidating all cache"""
    with patch('algo_studio.core.ray_dashboard_client.RayAPIClient') as MockClient:
        instance = MockClient.return_value
        instance.invalidate_cache.return_value = None

        with patch('algo_studio.api.routes.cluster.get_ray_client', return_value=instance):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/cluster/cache/invalidate")

    assert response.status_code == 200
    instance.invalidate_cache.assert_called_once_with(None)


@pytest.mark.asyncio
async def test_invalidate_endpoint_cache():
    """Test invalidating cache for specific endpoint"""
    with patch('algo_studio.core.ray_dashboard_client.RayAPIClient') as MockClient:
        instance = MockClient.return_value
        instance.invalidate_cache.return_value = None

        with patch('algo_studio.api.routes.cluster.get_ray_client', return_value=instance):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/cluster/cache/invalidate?endpoint=/api/nodes")

    assert response.status_code == 200
    instance.invalidate_cache.assert_called_once_with("/api/nodes")
