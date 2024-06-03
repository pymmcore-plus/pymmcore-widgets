from dataclasses import dataclass
from pathlib import Path

from ._base_dataclass import BaseDataclass

DEFAULT_PLATE_DB_PATH = Path(__file__).parent / "default_well_plate_database.json"


@dataclass(frozen=True)
class Plate(BaseDataclass):
    """General class describing a plate.

    It can be used to define multi-well plates or different types of general areas with
    rectangular, square or circular shapes (e.g. glass coverslips).

    Attributes
    ----------
    id : str
        The id of the plate.
    circular : bool
        Whether the plate is circular or not. By Default, False.
    rows : int
        The number of rows of the plate.
    columns : int
        The number of columns of the plate.
    well_spacing_x : float
        The spacing between wells in the x direction in mm.
    well_spacing_y : float
        The spacing between wells in the y direction in mm.
    well_size_x : float
        The size of the wells in the x direction in mm.
    well_size_y : float
        The size of the wells in the y direction in mm.
    """

    id: str = ""
    circular: bool = False
    rows: int = 0
    columns: int = 0
    well_spacing_x: float = 0.0
    well_spacing_y: float = 0.0
    well_size_x: float = 0.0
    well_size_y: float = 0.0


def save_database(database: dict[str, Plate], database_path: Path | str) -> None:
    """Save the database of well plates to database_path.

    The database will be saved as a JSON file.
    """
    import json

    with open(Path(database_path), "w") as f:
        json.dump([k.to_dict() for k in database.values()], f, indent=4)


def load_database(database_path: Path | str) -> dict[str, Plate]:
    """Load the database of well plates contained in database_path.

    The database must be a JSON file.
    """
    import json

    with open(Path(database_path)) as f:
        return {k["id"]: Plate(**k) for k in json.load(f)}
