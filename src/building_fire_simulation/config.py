"""Repository-relative paths used by optional persistence helpers."""
import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent


def _resolve_project_root() -> Path:
    override = os.environ.get("BUILDING_FIRE_SIMULATION_ROOT")
    if override:
        return Path(override).expanduser().resolve()

    for candidate in PACKAGE_DIR.parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate

    # A normal wheel has no repository parent. Optional command-line consumers
    # are expected to run from the checkout (or set the explicit override).
    return Path.cwd().resolve()


PROJECT_ROOT = _resolve_project_root()
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
