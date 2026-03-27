# src/algo_studio/api/routes/algorithms.py
import json
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(prefix="/api/algorithms", tags=["algorithms"])

# Algorithm directory path (relative to project root)
ALGORITHMS_DIR = Path(__file__).parent.parent.parent.parent.parent / "algorithms"


def scan_algorithms():
    """Scan the algorithms directory and return list of algorithm metadata."""
    algorithms = []

    if not ALGORITHMS_DIR.exists():
        return algorithms

    # Iterate through algorithm directories: algorithms/<name>/<version>/
    for name_dir in ALGORITHMS_DIR.iterdir():
        if not name_dir.is_dir():
            continue

        for version_dir in name_dir.iterdir():
            if not version_dir.is_dir():
                continue

            metadata_file = version_dir / "metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, "r") as f:
                        metadata = json.load(f)
                    algorithms.append(metadata)
                except (json.JSONDecodeError, IOError):
                    # Skip algorithms with invalid metadata
                    continue

    return algorithms


@router.get("/")
async def list_algorithms():
    """List all algorithms with their metadata."""
    try:
        algorithms = scan_algorithms()
        return {
            "items": algorithms,
            "total": len(algorithms)
        }
    except Exception as e:
        return {
            "items": [],
            "total": 0,
            "error": str(e)
        }


@router.get("/list")
async def list_algorithms_alias():
    """Alias for listing algorithms."""
    return await list_algorithms()