# tests/unit/api/routes/test_algorithms.py
"""Unit tests for algorithms API endpoints."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

# Load algorithms module directly without going through package __init__
import importlib.util
algo_module_path = Path(__file__).parent.parent.parent.parent.parent / "src" / "algo_studio" / "api" / "routes" / "algorithms.py"
spec = importlib.util.spec_from_file_location("algorithms", algo_module_path)
algo_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(algo_module)

router = algo_module.router
scan_algorithms = algo_module.scan_algorithms
ALGORITHMS_DIR = algo_module.ALGORITHMS_DIR


class TestScanAlgorithms:
    """Unit tests for scan_algorithms function."""

    def test_scan_algorithms_returns_empty_when_dir_not_exists(self):
        """Test scan_algorithms returns empty list when algorithms dir does not exist."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False

        with patch.object(algo_module, "ALGORITHMS_DIR", mock_path):
            result = scan_algorithms()
            assert result == []

    def test_scan_algorithms_returns_empty_when_dir_is_empty(self):
        """Test scan_algorithms returns empty list when no algorithm dirs exist."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.iterdir.return_value = []

        with patch.object(algo_module, "ALGORITHMS_DIR", mock_path):
            result = scan_algorithms()
            assert result == []

    def test_scan_algorithms_skips_non_directory_items(self):
        """Test scan_algorithms skips files that are not directories."""
        mock_file = MagicMock()
        mock_file.is_dir.return_value = False

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.iterdir.return_value = [mock_file]

        with patch.object(algo_module, "ALGORITHMS_DIR", mock_path):
            result = scan_algorithms()
            assert result == []

    def test_scan_algorithms_skips_version_dirs_without_metadata(self):
        """Test scan_algorithms skips version directories without metadata.json."""
        mock_version_dir = MagicMock()
        mock_version_dir.is_dir.return_value = True
        mock_version_dir.__truediv__.return_value = MagicMock()
        mock_version_dir.__truediv__.return_value.exists.return_value = False

        mock_name_dir = MagicMock()
        mock_name_dir.is_dir.return_value = True
        mock_name_dir.iterdir.return_value = [mock_version_dir]

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.iterdir.return_value = [mock_name_dir]

        with patch.object(algo_module, "ALGORITHMS_DIR", mock_path):
            result = scan_algorithms()
            assert result == []

    def test_scan_algorithms_reads_valid_metadata(self):
        """Test scan_algorithms correctly reads valid metadata.json files."""
        metadata = {
            "name": "simple_classifier",
            "version": "v1",
            "description": "Test classifier",
            "task_type": "classification",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            algo_dir = Path(tmpdir) / "simple_classifier" / "v1"
            algo_dir.mkdir(parents=True)
            metadata_file = algo_dir / "metadata.json"
            metadata_file.write_text(json.dumps(metadata))

            with patch.object(algo_module, "ALGORITHMS_DIR", Path(tmpdir)):
                result = scan_algorithms()
                assert len(result) == 1
                assert result[0]["name"] == "simple_classifier"
                assert result[0]["version"] == "v1"

    def test_scan_algorithms_skips_invalid_json(self):
        """Test scan_algorithms skips metadata.json with invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            algo_dir = Path(tmpdir) / "simple_classifier" / "v1"
            algo_dir.mkdir(parents=True)
            metadata_file = algo_dir / "metadata.json"
            metadata_file.write_text("not valid json {")

            with patch.object(algo_module, "ALGORITHMS_DIR", Path(tmpdir)):
                result = scan_algorithms()
                assert result == []

    def test_scan_algorithms_reads_multiple_algorithms(self):
        """Test scan_algorithms reads multiple algorithm versions."""
        metadata1 = {"name": "algo1", "version": "v1"}
        metadata2 = {"name": "algo2", "version": "v1"}

        with tempfile.TemporaryDirectory() as tmpdir:
            algo1_dir = Path(tmpdir) / "algo1" / "v1"
            algo2_dir = Path(tmpdir) / "algo2" / "v1"
            algo1_dir.mkdir(parents=True)
            algo2_dir.mkdir(parents=True)
            (algo1_dir / "metadata.json").write_text(json.dumps(metadata1))
            (algo2_dir / "metadata.json").write_text(json.dumps(metadata2))

            with patch.object(algo_module, "ALGORITHMS_DIR", Path(tmpdir)):
                result = scan_algorithms()
                assert len(result) == 2

    def test_scan_algorithms_skips_version_dir_that_is_not_directory(self):
        """Test scan_algorithms skips version entries that are files, not directories (line 26)."""
        metadata = {"name": "algo1", "version": "v1"}

        with tempfile.TemporaryDirectory() as tmpdir:
            algo1_dir = Path(tmpdir) / "algo1" / "v1"
            algo1_dir.mkdir(parents=True)
            (algo1_dir / "metadata.json").write_text(json.dumps(metadata))

            # Create a file in place of a version directory
            fake_version_dir = Path(tmpdir) / "algo1" / "v2"
            fake_version_dir.write_text("I am not a directory")

            with patch.object(algo_module, "ALGORITHMS_DIR", Path(tmpdir)):
                result = scan_algorithms()
                # Should only find v1, not v2 (which is a file)
                assert len(result) == 1
                assert result[0]["version"] == "v1"


class TestAlgorithmsRouter:
    """Integration tests for algorithms router endpoints."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app with the algorithms router."""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, test_app):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")

    @pytest.mark.asyncio
    async def test_list_algorithms_returns_items_and_total(self, client):
        """Test GET /api/algorithms/ returns items list and total count."""
        mock_metadata = [{"name": "simple_classifier", "version": "v1"}]

        with patch.object(algo_module, "scan_algorithms", return_value=mock_metadata):
            response = await client.get("/api/algorithms/")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 1
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_list_algorithms_empty_when_no_algorithms(self, client):
        """Test GET /api/algorithms/ returns empty when no algorithms exist."""
        with patch.object(algo_module, "scan_algorithms", return_value=[]):
            response = await client.get("/api/algorithms/")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_algorithms_returns_error_on_exception(self, client):
        """Test GET /api/algorithms/ returns error structure on exception."""
        with patch.object(algo_module, "scan_algorithms", side_effect=Exception("Scan failed")):
            response = await client.get("/api/algorithms/")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert "error" in data

    @pytest.mark.asyncio
    async def test_list_algorithms_alias(self, client):
        """Test GET /api/algorithms/list alias returns same data."""
        mock_metadata = [{"name": "simple_classifier", "version": "v1"}]

        with patch.object(algo_module, "scan_algorithms", return_value=mock_metadata):
            response = await client.get("/api/algorithms/list")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1


class TestAlgorithmsIntegration:
    """Integration tests with real algorithms directory when available."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app with the algorithms router."""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, test_app):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")

    @pytest.mark.asyncio
    async def test_list_algorithms_with_real_algorithms_dir(self, client):
        """Test listing algorithms from real algorithms directory."""
        if not ALGORITHMS_DIR.exists():
            pytest.skip("Algorithms directory does not exist")

        response = await client.get("/api/algorithms/")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        # At least simple_classifier and simple_detector exist
        assert data["total"] >= 2

    @pytest.mark.asyncio
    async def test_list_algorithms_alias_with_real_dir(self, client):
        """Test the /list alias with real algorithms directory."""
        if not ALGORITHMS_DIR.exists():
            pytest.skip("Algorithms directory does not exist")

        response = await client.get("/api/algorithms/list")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
