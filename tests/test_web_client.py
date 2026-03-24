import pytest
import requests
from unittest.mock import patch, MagicMock
from algo_studio.web.client import get_tasks, get_hosts_status


class TestGetTasks:
    @patch("algo_studio.web.client.requests.get")
    def test_returns_list_of_tasks(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "tasks": [
                {"task_id": "train-001", "task_type": "train", "status": "pending"}
            ],
            "total": 1
        }
        mock_get.return_value = mock_resp

        result = get_tasks()

        assert result["total"] == 1
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["task_id"] == "train-001"
        mock_get.assert_called_once()


class TestGetHostsStatus:
    @patch("algo_studio.web.client.requests.get")
    def test_returns_cluster_and_local(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "cluster_nodes": [],
            "local_host": {"hostname": "test", "ip": "127.0.1.1", "status": "online"}
        }
        mock_get.return_value = mock_resp

        result = get_hosts_status()

        assert "cluster_nodes" in result
        assert "local_host" in result
        mock_get.assert_called_once()


class TestGetTasksError:
    @patch("algo_studio.web.client.requests.get")
    def test_raises_runtime_error_on_network_failure(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Network unreachable")
        with pytest.raises(RuntimeError) as exc_info:
            get_tasks()
        assert "Failed to fetch tasks" in str(exc_info.value)

    @patch("algo_studio.web.client.requests.get")
    def test_raises_runtime_error_on_http_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_resp
        with pytest.raises(RuntimeError) as exc_info:
            get_tasks()
        assert "Failed to fetch tasks" in str(exc_info.value)


class TestGetHostsStatusError:
    @patch("algo_studio.web.client.requests.get")
    def test_raises_runtime_error_on_network_failure(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Network unreachable")
        with pytest.raises(RuntimeError) as exc_info:
            get_hosts_status()
        assert "Failed to fetch hosts status" in str(exc_info.value)

    @patch("algo_studio.web.client.requests.get")
    def test_raises_runtime_error_on_http_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_resp
        with pytest.raises(RuntimeError) as exc_info:
            get_hosts_status()
        assert "Failed to fetch hosts status" in str(exc_info.value)
