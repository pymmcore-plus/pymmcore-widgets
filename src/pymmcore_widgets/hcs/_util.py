from __future__ import annotations

import json
import math
import warnings
from itertools import product
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from qtpy.QtCore import QRectF, Qt
from qtpy.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)
from useq import WellPlate

from ._graphics_items import _WellGraphicsItem

if TYPE_CHECKING:
    from qtpy.QtGui import QBrush, QPen, QResizeEvent
    from useq._grid import GridPosition

    from ._graphics_items import Well

DEFAULT_PLATE_DB_PATH = Path(__file__).parent / "default_well_plate_database.json"


class _ResizingGraphicsView(QGraphicsView):
    """A QGraphicsView that resizes the scene to fit the view."""

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


def draw_plate(
    view: QGraphicsView,
    scene: QGraphicsScene,
    plate: WellPlate,
    brush: QBrush | None,
    pen: QPen | None,
    opacity: float = 1.0,
    text: bool = True,
) -> None:
    """Draw all wells of the plate."""
    # setting a custom well size in scene px. Using 10 times the well size in mm
    # gives a good resolution in the viewer.
    well_size_x, well_size_y = plate.well_size
    well_spacing_x, well_spacing_y = plate.well_spacing

    scene.clear()

    if not well_size_x or not well_size_y:
        return

    well_scene_size = well_size_x * 10

    # calculate the width and height of the well in scene px
    if well_size_x == well_size_y:
        well_width = well_height = well_scene_size
    elif well_size_x > well_size_y:
        well_width = well_scene_size
        # keep the ratio between well_size_x and well_size_y
        well_height = int(well_scene_size * well_size_y / well_size_x)
    else:
        # keep the ratio between well_size_x and well_size_y
        well_width = int(well_scene_size * well_size_x / well_size_y)
        well_height = well_scene_size

    # calculate the spacing between wells
    dx = well_spacing_x - well_size_x if well_spacing_x else 0
    dy = well_spacing_y - well_size_y if well_spacing_y else 0

    # convert the spacing between wells in pixels
    dx_px = dx * well_width / well_size_x if well_spacing_x else 0
    dy_px = dy * well_height / well_size_y if well_spacing_y else 0

    # the text size is the well_height of the well divided by 3
    text_size = well_height / 3 if text else None

    # draw the wells and place them in their correct row/column position
    for row, col in product(range(plate.rows), range(plate.columns)):
        _x = (well_width * col) + (dx_px * col)
        _y = (well_height * row) + (dy_px * row)
        rect = QRectF(_x, _y, well_width, well_height)
        w = _WellGraphicsItem(rect, row, col, plate.circular_wells, text_size)
        w.brush = brush
        w.pen = pen
        w.setOpacity(opacity)
        scene.addItem(w)

    # # set the scene size
    plate_width = (well_width * plate.columns) + (dx_px * (plate.columns - 1))
    plate_height = (well_height * plate.rows) + (dy_px * (plate.rows - 1))

    # add some offset to the scene rect to leave some space around the plate
    offset = 20
    scene.setSceneRect(
        -offset, -offset, plate_width + (offset * 2), plate_height + (offset * 2)
    )

    # fit scene in view
    view.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


def get_well_center(
    plate: WellPlate, well: Well, a1_center_x: float, a1_center_y: float
) -> tuple[float, float]:
    """Calculate the x, y stage coordinates of a well."""
    a1_x, a1_y = (a1_center_x, a1_center_y)
    well_spacing_x, well_spacing_y = plate.well_spacing
    spacing_x = well_spacing_x * 1000  # µm
    spacing_y = well_spacing_y * 1000  # µm

    if well.name == "A1":
        x, y = (a1_x, a1_y)
    else:
        x = a1_x + (spacing_x * well.column)
        y = a1_y - (spacing_y * well.row)
    return x, y


def apply_rotation_matrix(
    rotation_matrix: np.ndarray,
    a1_center_x: float,
    a1_center_y: float,
    new_x: float,
    new_y: float,
) -> tuple[float, float]:
    """Apply rotation matrix to x, y coordinates."""
    center = np.array([[a1_center_x], [a1_center_y]])
    coords = [[new_x], [new_y]]
    transformed = np.linalg.inv(rotation_matrix).dot(coords - center) + center
    x_rotated, y_rotated = transformed
    return x_rotated[0], y_rotated[0]


def nearest_neighbor(
    points: list[GridPosition], top_x: float, top_y: float
) -> list[GridPosition]:
    """Find the nearest neighbor path for a list of points.

    The starting point is the closest to (top_x, top_y).
    """
    first_point: GridPosition | None = _top_left(points, top_x, top_y)

    if first_point is None:
        return []

    n = len(points)
    visited: dict[int, bool] = {i: False for i in range(n)}
    path_indices: list[int] = [points.index(first_point)]
    visited[path_indices[0]] = True

    for _ in range(n - 1):
        current_point = path_indices[-1]
        nearest_point = None
        min_distance = float("inf")

        for i in range(n):
            if not visited[i]:
                distance = _calculate_distance(points[current_point], points[i])
                if distance < min_distance:
                    min_distance = distance
                    nearest_point = i

        if nearest_point is not None:
            path_indices.append(nearest_point)
            visited[nearest_point] = True

    return [points[i] for i in path_indices]


def _calculate_distance(point1: GridPosition, point2: GridPosition) -> float:
    """Calculate the Euclidean distance between two points."""
    return math.sqrt((point1.x - point2.x) ** 2 + (point1.y - point2.y) ** 2)


def _top_left(points: list[GridPosition], top_x: float, top_y: float) -> GridPosition:
    """Find the top left point in respect to (top_x, top_y)."""
    return sorted(
        points,
        key=lambda coord: math.sqrt(
            ((coord.x - top_x) ** 2) + ((coord.y - top_y) ** 2)
        ),
    )[0]


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