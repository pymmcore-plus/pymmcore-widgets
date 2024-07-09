from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

import useq
from qtpy.QtCore import QRectF, QSize, Qt, Signal
from qtpy.QtGui import QPainter, QPen
from qtpy.QtWidgets import (
    QComboBox,
    QGraphicsItem,
    QGraphicsScene,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ._util import ResizingGraphicsView

if TYPE_CHECKING:
    Index = int | list[int] | slice
    IndexExpression = tuple[Index, ...] | Index


def _sort_plate(item: str) -> tuple[int, int | str]:
    """Sort well plate keys by number first, then by string."""
    parts = item.split("-")
    if parts[0].isdigit():
        return (0, int(parts[0]))
    return (1, item)


class WellPlateView(ResizingGraphicsView):
    """QGraphicsView for displaying a well plate."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self._scene = QGraphicsScene()
        super().__init__(self._scene, parent)
        self.setStyleSheet("background:grey; border-radius: 5px;")
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )

        self._well_items: list[QGraphicsItem] = []

    def sizeHint(self) -> QSize:
        aspect = 1.5
        width = 600
        height = int(width // aspect)
        return QSize(width, height)

    def drawPlate(self, plate: useq.WellPlate | useq.WellPlatePlan) -> None:
        if isinstance(plate, useq.WellPlatePlan):
            plan = plate
        else:
            plan = useq.WellPlatePlan(a1_center_xy=(0, 0), plate=plate)

        width, height = plan.plate.well_size
        well_rect = QRectF(0, 0, width * 1000, height * 1000)

        # Since most plates have the same extent, a constant pen width seems to work
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(200)

        self.clearWells()
        for pos in plan.all_well_positions:
            rt = well_rect.translated(pos.x, pos.y)
            if plan.plate.circular_wells:
                item = self._scene.addEllipse(rt, pen)
            else:
                item = self._scene.addRect(rt, pen)
            self._well_items.append(item)

        # fit scene in view
        self._scene.setSceneRect(self._scene.itemsBoundingRect())

    def clearWells(self) -> None:
        while self._well_items:
            self._scene.removeItem(self._well_items.pop())


class PlateSelectorWidget(QWidget):
    """Widget for selecting the well plate and its wells.

    Parameters
    ----------
    parent : QWidget, optional
        The parent widget, by default None
    """

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # well plate combobox
        self.plate_name = QComboBox()
        plate_names = sorted(useq.registered_well_plate_keys(), key=_sort_plate)
        self.plate_name.addItems(plate_names)

        # clear selection button
        self._clear_button = QPushButton(text="Clear Selection")
        self._clear_button.setAutoDefault(False)

        self.view = WellPlateView(self)

        # LAYOUT ---------------------------------------

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(QLabel("WellPlate:"), 0)
        top_layout.addWidget(self.plate_name, 1)
        top_layout.addWidget(self._clear_button, 0)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.view)

        # connect
        # self.scene.valueChanged.connect(self._on_value_changed)
        # self._clear_button.clicked.connect(self.scene._clear_selection)
        self.plate_name.currentTextChanged.connect(self._on_plate_name_changed)
        self.view.drawPlate(self.value())

    # _________________________PUBLIC METHODS_________________________ #

    def value(self) -> useq.WellPlatePlan:
        """Return current plate and selected wells as a list of (name, row, column)."""
        return useq.WellPlatePlan(
            plate=self.plate_name.currentText(),
            a1_center_xy=(0, 0),
            selected_wells=self.currentSelection(),
        )

    def setValue(self, value: useq.WellPlatePlan | Mapping) -> None:
        """Set the current plate and the selected wells.

        Parameters
        ----------
        value : PlateInfo
            The plate information to set containing the plate and the selected wells
            as a list of (name, row, column).
        """
        value = useq.WellPlatePlan.model_validate(value)
        self.plate_name.setCurrentText(value.plate.name)

        if value.plate.name not in useq.registered_well_plate_keys():
            ...  # consider how to deal with this

    def currentPlate(self) -> useq.WellPlate:
        return useq.WellPlate.from_str(self.plate_name.currentText())

    def setCurrentPlate(self, plate: useq.WellPlate | str) -> None:
        if isinstance(plate, useq.WellPlate):
            plate = plate.name or "Custom Plate"
        self.plate_name.setCurrentText(plate)

    def currentSelection(self) -> IndexExpression:
        return slice(0, 0)

    def setCurrentSelection(self, selection: IndexExpression) -> None: ...

    # _________________________PRIVATE METHODS________________________ #

    def _on_value_changed(self) -> None:
        """Emit the valueChanged signal when the value changes."""
        # not using lambda or tests will fail
        self.valueChanged.emit(self.value())

    def _on_plate_name_changed(self, plate_name: str) -> None:
        self.view.drawPlate(useq.WellPlate.from_str(plate_name))
        self.valueChanged.emit(self.value())
