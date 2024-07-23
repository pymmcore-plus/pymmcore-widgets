from __future__ import annotations

from typing import TYPE_CHECKING

import useq
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)
from useq import WellPlate

if TYPE_CHECKING:
    from qtpy.QtGui import QResizeEvent


# add few coverslips to the known well plates
useq.register_well_plates(
    {
        "coverslip-18mm": {
            "rows": 1,
            "columns": 1,
            "well_spacing": 0.0,
            "well_size": 18.0,
            "circular_wells": False,
            "name": "18mm coverslip",
        },
        "coverslip-22mm": {
            "rows": 1,
            "columns": 1,
            "well_spacing": 0.0,
            "well_size": 22.0,
            "circular_wells": False,
            "name": "22mm coverslip",
        },
    }
)


def custom_sort_key(item: str) -> tuple[int, int | str]:
    """Sort well plate keys by number first, then by string."""
    parts = item.split("-")
    return (0, int(parts[0])) if parts[0].isdigit() else (1, item)  # type: ignore


# sort the well plates by number first, then by string
sorted_wells = sorted(useq.registered_well_plate_keys(), key=custom_sort_key)

# create a plate database with all known well plates
PLATES: dict[str, WellPlate] = {}
for key in sorted_wells:
    plate = useq.WellPlate.from_str(key)
    if isinstance(plate, WellPlate):
        if not plate.name:
            plate = plate.replace(name=key)
        PLATES[key] = plate
    elif isinstance(plate, dict):
        PLATES[key] = WellPlate(**plate).replace(name=key)


class _ResizingGraphicsView(QGraphicsView):
    """A QGraphicsView that resizes the scene to fit the view."""

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
