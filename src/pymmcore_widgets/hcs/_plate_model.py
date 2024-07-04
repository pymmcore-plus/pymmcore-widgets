from __future__ import annotations

import json
import warnings
from pathlib import Path

from useq import WellPlate

DEFAULT_PLATE_DB_PATH = Path(__file__).parent / "default_well_plate_database.json"


def load_database(path: str | Path = DEFAULT_PLATE_DB_PATH) -> dict[str, WellPlate]:
    """Load the database of well plates contained in database_path.

    If an error occurs, it will load the default database.

    Database must be a JSON file with this structure:

    "6-well": {
        "rows": 2,
        "columns": 3,
        "well_spacing": 39.12,
        "well_size": 34.8
        "circular_wells": true"  # optional, by default True
    },
    ...
    """
    if Path(path) == DEFAULT_PLATE_DB_PATH:
        with open(path) as f:
            return {k: WellPlate(**v, name=k) for k, v in json.load(f).items()}
    try:
        with open(path) as f:
            return {k: WellPlate(**v, name=k) for k, v in json.load(f).items()}
    except Exception as e:
        warnings.warn(
            f"Error loading well plate database: {e}."
            f"Loading default database from {DEFAULT_PLATE_DB_PATH}.",
            stacklevel=2,
        )
        with open(DEFAULT_PLATE_DB_PATH) as f:
            return {k: WellPlate(**v, name=k) for k, v in json.load(f).items()}


def save_database(database: dict[str, WellPlate], database_path: Path | str) -> None:
    """Save the database of well plates to database_path.

    The database will be saved as a JSON file.
    """
    with open(Path(database_path), "w") as f:
        json.dump({k: v.model_dump_json() for k, v in database.items()}, f, indent=4)
