# tests/test_api_tasks.py
import pytest
from httpx import AsyncClient, ASGITransport
from algo_studio.api.main import app

@pytest.mark.asyncio
async def test_create_task():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/tasks",
            json={
                "task_type": "train",
                "algorithm_name": "yolo",
                "algorithm_version": "v1.0.0",
                "config": {"epochs": 100}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] is not None
        assert data["status"] == "pending"

@pytest.mark.asyncio
async def test_list_tasks():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data