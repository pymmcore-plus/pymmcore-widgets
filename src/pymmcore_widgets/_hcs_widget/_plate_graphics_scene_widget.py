from __future__ import annotations

from typing import TYPE_CHECKING, cast

from qtpy.QtCore import QRect, QRectF, Qt
from qtpy.QtGui import QBrush, QTransform
from qtpy.QtWidgets import (
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QRubberBand,
    QWidget,
)

if TYPE_CHECKING:
    from ._graphics_items import _Well


class _HCSGraphicsScene(QGraphicsScene):
    """Custom QGraphicsScene to control the plate/well selection."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.unselected = QBrush(Qt.green)
        self.selected = QBrush(Qt.magenta)

        self.well_pos = 0
        self.new_well_pos = 0

        self._selected_wells: list[QGraphicsItem] = []

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self.originQPoint = event.screenPos()
        self.currentQRubberBand = QRubberBand(QRubberBand.Rectangle)
        self.originCropPoint = event.scenePos()

        self._selected_wells = [item for item in self.items() if item.isSelected()]

        for item in self._selected_wells:
            item = cast("_Well", item)
            item._setBrush(self.selected)

        if well := self.itemAt(self.originCropPoint, QTransform()):
            well = cast("_Well", well)
            if well.isSelected():
                well._setBrush(self.unselected)
                well.setSelected(False)
            else:
                well._setBrush(self.selected)
                well.setSelected(True)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self.currentQRubberBand.setGeometry(QRect(self.originQPoint, event.screenPos()))
        self.currentQRubberBand.show()
        selection = self.items(QRectF(self.originCropPoint, event.scenePos()))
        for item in self.items():
            item = cast("_Well", item)
            if item in selection:
                item._setBrush(self.selected)
                item.setSelected(True)
            elif item not in self._selected_wells:
                item._setBrush(self.unselected)
                item.setSelected(False)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self.currentQRubberBand.hide()

    def _clear_selection(self) -> None:
        for item in self.items():
            item = cast("_Well", item)
            if item.isSelected():
                item.setSelected(False)
                item._setBrush(self.unselected)

    def _get_plate_positions(self) -> list[tuple[str, int, int]] | None:
        """Return a list of (well, row, column) for each well selected."""
        if not self.items():
            return None

        well_list_to_order = [
            item._getPos() for item in reversed(self.items()) if item.isSelected()
        ]

        # for 'snake' acquisition
        correct_order = []
        to_add = []
        try:
            previous_row = well_list_to_order[0][1]
        except IndexError:
            return None
        current_row = 0
        for idx, wrc in enumerate(well_list_to_order):
            _, row, _ = wrc

            if idx == 0:
                correct_order.append(wrc)
            elif row == previous_row:
                to_add.append(wrc)
                if idx == len(well_list_to_order) - 1:
                    if current_row % 2:
                        correct_order.extend(iter(reversed(to_add)))
                    else:
                        correct_order.extend(iter(to_add))
            else:
                if current_row % 2:
                    correct_order.extend(iter(reversed(to_add)))
                else:
                    correct_order.extend(iter(to_add))
                to_add.clear()
                to_add.append(wrc)
                if idx == len(well_list_to_order) - 1:
                    if current_row % 2:
                        correct_order.extend(iter(reversed(to_add)))
                    else:
                        correct_order.extend(iter(to_add))

                previous_row = row
                current_row += 1

        return correct_order
