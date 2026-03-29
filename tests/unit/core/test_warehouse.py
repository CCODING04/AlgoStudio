# tests/unit/core/test_warehouse.py
"""Unit tests for AlgorithmWarehouse - algorithm registry and version management."""

import json
import os
import tempfile
import pytest
from algo_studio.core.warehouse import AlgorithmWarehouse, AlgorithmVersion


class TestAlgorithmVersion:
    """Tests for AlgorithmVersion dataclass."""

    def test_algorithm_version_creation(self):
        """Test creating an AlgorithmVersion instance."""
        version = AlgorithmVersion(
            name="simple_classifier",
            version="v1",
            path="/algorithms/simple_classifier/v1",
            metadata={"accuracy": 0.95, "framework": "pytorch"},
        )

        assert version.name == "simple_classifier"
        assert version.version == "v1"
        assert version.path == "/algorithms/simple_classifier/v1"
        assert version.metadata["accuracy"] == 0.95
        assert version.metadata["framework"] == "pytorch"


class TestAlgorithmWarehouse:
    """Tests for AlgorithmWarehouse class."""

    @pytest.fixture
    def warehouse(self):
        """Create a fresh AlgorithmWarehouse instance."""
        return AlgorithmWarehouse(base_path="/algorithms")

    @pytest.fixture
    def warehouse_with_temp_path(self, tmp_path):
        """Create an AlgorithmWarehouse with a temporary base path."""
        return AlgorithmWarehouse(base_path=str(tmp_path / "algorithms"))

    def test_warehouse_initialization(self, warehouse):
        """Test warehouse initializes with empty index."""
        assert warehouse.base_path == "/algorithms"
        assert warehouse._index == {}

    def test_register_algorithm_with_metadata(self, tmp_path):
        """Test registering an algorithm version with metadata.json."""
        algo_dir = tmp_path / "test_algo" / "v1"
        algo_dir.mkdir(parents=True)

        metadata = {"name": "test_algo", "version": "v1", "description": "Test algorithm"}
        with open(algo_dir / "metadata.json", "w") as f:
            json.dump(metadata, f)

        warehouse = AlgorithmWarehouse(base_path=str(tmp_path))
        warehouse.register("test_algo", "v1", str(algo_dir))

        result = warehouse.get_version("test_algo", "v1")
        assert result is not None
        assert result.name == "test_algo"
        assert result.version == "v1"
        assert result.metadata["description"] == "Test algorithm"

    def test_register_algorithm_without_metadata(self, tmp_path):
        """Test registering an algorithm version without metadata.json."""
        algo_dir = tmp_path / "test_algo" / "v1"
        algo_dir.mkdir(parents=True)

        warehouse = AlgorithmWarehouse(base_path=str(tmp_path))
        warehouse.register("test_algo", "v1", str(algo_dir))

        result = warehouse.get_version("test_algo", "v1")
        assert result is not None
        assert result.name == "test_algo"
        assert result.version == "v1"
        # Should have default metadata
        assert result.metadata["name"] == "test_algo"
        assert result.metadata["version"] == "v1"

    def test_register_multiple_versions(self, tmp_path):
        """Test registering multiple versions of the same algorithm."""
        v1_dir = tmp_path / "algo" / "v1"
        v2_dir = tmp_path / "algo" / "v2"
        v1_dir.mkdir(parents=True)
        v2_dir.mkdir(parents=True)

        warehouse = AlgorithmWarehouse(base_path=str(tmp_path))
        warehouse.register("algo", "v1", str(v1_dir))
        warehouse.register("algo", "v2", str(v2_dir))

        versions = warehouse.list_versions("algo")
        assert len(versions) == 2

        v1 = warehouse.get_version("algo", "v1")
        v2 = warehouse.get_version("algo", "v2")
        assert v1 is not None
        assert v2 is not None
        assert v1.version == "v1"
        assert v2.version == "v2"

    def test_register_multiple_algorithms(self, tmp_path):
        """Test registering multiple different algorithms."""
        algo1_dir = tmp_path / "algo1" / "v1"
        algo2_dir = tmp_path / "algo2" / "v1"
        algo1_dir.mkdir(parents=True)
        algo2_dir.mkdir(parents=True)

        warehouse = AlgorithmWarehouse(base_path=str(tmp_path))
        warehouse.register("algo1", "v1", str(algo1_dir))
        warehouse.register("algo2", "v1", str(algo2_dir))

        algorithms = warehouse.list_algorithms()
        assert len(algorithms) == 2
        assert "algo1" in algorithms
        assert "algo2" in algorithms

    def test_get_version_existing(self, warehouse_with_temp_path, tmp_path):
        """Test getting an existing version."""
        algo_dir = tmp_path / "test_algo" / "v1"
        algo_dir.mkdir(parents=True)

        warehouse_with_temp_path.register("test_algo", "v1", str(algo_dir))

        result = warehouse_with_temp_path.get_version("test_algo", "v1")
        assert result is not None
        assert isinstance(result, AlgorithmVersion)

    def test_get_version_non_existing(self, warehouse):
        """Test getting a non-existing version returns None."""
        result = warehouse.get_version("non_existent", "v1")
        assert result is None

    def test_get_version_non_existing_version(self, warehouse_with_temp_path, tmp_path):
        """Test getting a non-existing version of an existing algorithm."""
        algo_dir = tmp_path / "test_algo" / "v1"
        algo_dir.mkdir(parents=True)

        warehouse_with_temp_path.register("test_algo", "v1", str(algo_dir))

        result = warehouse_with_temp_path.get_version("test_algo", "v2")
        assert result is None

    def test_list_versions_existing(self, warehouse_with_temp_path, tmp_path):
        """Test listing versions of an existing algorithm."""
        v1_dir = tmp_path / "test_algo" / "v1"
        v2_dir = tmp_path / "test_algo" / "v2"
        v1_dir.mkdir(parents=True)
        v2_dir.mkdir(parents=True)

        warehouse_with_temp_path.register("test_algo", "v1", str(v1_dir))
        warehouse_with_temp_path.register("test_algo", "v2", str(v2_dir))

        versions = warehouse_with_temp_path.list_versions("test_algo")
        assert len(versions) == 2

    def test_list_versions_non_existing(self, warehouse):
        """Test listing versions of a non-existing algorithm."""
        versions = warehouse.list_versions("non_existent")
        assert versions == []

    def test_list_algorithms_empty(self, warehouse):
        """Test listing algorithms when none are registered."""
        algorithms = warehouse.list_algorithms()
        assert algorithms == []

    def test_list_algorithms_multiple(self, warehouse_with_temp_path, tmp_path):
        """Test listing multiple algorithms."""
        for name in ["algo_a", "algo_b", "algo_c"]:
            algo_dir = tmp_path / name / "v1"
            algo_dir.mkdir(parents=True)
            warehouse_with_temp_path.register(name, "v1", str(algo_dir))

        algorithms = warehouse_with_temp_path.list_algorithms()
        assert len(algorithms) == 3
        assert "algo_a" in algorithms
        assert "algo_b" in algorithms
        assert "algo_c" in algorithms

    def test_list_algorithms_no_duplicates(self, warehouse_with_temp_path, tmp_path):
        """Test that list_algorithms returns unique algorithm names."""
        # Register multiple versions of the same algorithm
        for version in ["v1", "v2", "v3"]:
            algo_dir = tmp_path / "same_algo" / version
            algo_dir.mkdir(parents=True)
            warehouse_with_temp_path.register("same_algo", version, str(algo_dir))

        algorithms = warehouse_with_temp_path.list_algorithms()
        assert len(algorithms) == 1
        assert algorithms == ["same_algo"]

    def test_rebuild_index_empty_directory(self, warehouse_with_temp_path, tmp_path):
        """Test rebuild_index with empty base directory."""
        # Create empty base path
        (tmp_path / "algorithms").mkdir()
        warehouse_with_temp_path.rebuild_index()

        assert warehouse_with_temp_path._index == {}

    def test_rebuild_index_with_no_base_path(self, warehouse_with_temp_path, tmp_path):
        """Test rebuild_index when base path doesn't exist."""
        # Point to non-existent path
        warehouse_with_temp_path.base_path = str(tmp_path / "non_existent")
        warehouse_with_temp_path.rebuild_index()

        assert warehouse_with_temp_path._index == {}

    def test_rebuild_index_with_algorithms(self, warehouse_with_temp_path, tmp_path):
        """Test rebuild_index discovers algorithms from filesystem."""
        # Create algorithm structure
        algo_dir = tmp_path / "algorithms" / "discovered_algo" / "v1"
        algo_dir.mkdir(parents=True)

        metadata = {"name": "discovered_algo", "version": "v1", "discovered": True}
        with open(algo_dir / "metadata.json", "w") as f:
            json.dump(metadata, f)

        warehouse_with_temp_path.rebuild_index()

        result = warehouse_with_temp_path.get_version("discovered_algo", "v1")
        assert result is not None
        assert result.name == "discovered_algo"
        assert result.metadata["discovered"] is True

    def test_rebuild_index_skips_files(self, warehouse_with_temp_path, tmp_path):
        """Test rebuild_index skips files in algorithm directories."""
        algo_dir = tmp_path / "algorithms" / "algo_with_file" / "v1"
        algo_dir.mkdir(parents=True)

        # Create a file (not a directory) at the version level
        # This should be skipped, not treated as a version
        with open(algo_dir / "some_file.txt", "w") as f:
            f.write("not a version")

        # The directory itself should still be valid
        metadata = {"name": "algo_with_file", "version": "v1"}
        with open(algo_dir / "metadata.json", "w") as f:
            json.dump(metadata, f)

        warehouse_with_temp_path.rebuild_index()

        result = warehouse_with_temp_path.get_version("algo_with_file", "v1")
        assert result is not None

    def test_rebuild_index_handles_missing_metadata(self, warehouse_with_temp_path, tmp_path):
        """Test rebuild_index handles versions without metadata.json."""
        algo_dir = tmp_path / "algorithms" / "no_metadata" / "v1"
        algo_dir.mkdir(parents=True)

        # No metadata.json file
        warehouse_with_temp_path.rebuild_index()

        result = warehouse_with_temp_path.get_version("no_metadata", "v1")
        assert result is not None
        # Should have empty/default metadata
        assert result.metadata == {}

    def test_rebuild_index_multiple_algorithms_versions(self, warehouse_with_temp_path, tmp_path):
        """Test rebuild_index discovers multiple algorithms with multiple versions."""
        algorithms = {
            "algo1": ["v1", "v2"],
            "algo2": ["v1"],
            "algo3": ["v1", "v2", "v3"],
        }

        for algo_name, versions in algorithms.items():
            for version in versions:
                algo_dir = tmp_path / "algorithms" / algo_name / version
                algo_dir.mkdir(parents=True)
                metadata = {"name": algo_name, "version": version}
                with open(algo_dir / "metadata.json", "w") as f:
                    json.dump(metadata, f)

        warehouse_with_temp_path.rebuild_index()

        for algo_name, versions in algorithms.items():
            listed_versions = warehouse_with_temp_path.list_versions(algo_name)
            assert len(listed_versions) == len(versions)

        assert len(warehouse_with_temp_path.list_algorithms()) == 3

    def test_register_overwrites_existing(self, warehouse_with_temp_path, tmp_path):
        """Test that registering the same algorithm version overwrites."""
        v1_dir = tmp_path / "test_algo" / "v1"
        v1_dir.mkdir(parents=True)

        warehouse_with_temp_path.register("test_algo", "v1", str(v1_dir))
        first_version = warehouse_with_temp_path.get_version("test_algo", "v1")
        assert first_version.path == str(v1_dir)

        # Register again with different path
        v1_dir_new = tmp_path / "test_algo" / "v1_new"
        v1_dir_new.mkdir(parents=True)

        metadata = {"name": "test_algo", "version": "v1", "updated": True}
        with open(v1_dir_new / "metadata.json", "w") as f:
            json.dump(metadata, f)

        warehouse_with_temp_path.register("test_algo", "v1", str(v1_dir_new))
        second_version = warehouse_with_temp_path.get_version("test_algo", "v1")

        # Should be updated
        assert second_version.path == str(v1_dir_new)
        assert second_version.metadata["updated"] is True
