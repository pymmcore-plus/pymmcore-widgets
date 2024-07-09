from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

import useq
from qtpy.QtCore import QRectF, QSize, Qt, Signal
from qtpy.QtGui import QFont, QMouseEvent, QPainter, QPen
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

        well_width = plan.plate.well_size[0] * 1000
        well_height = plan.plate.well_size[1] * 1000
        well_rect = QRectF(0, 0, well_width, well_height)

        # Since most plates have the same extent, a constant pen width seems to work
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(200)

        self.clearWells()
        for pos in plan.all_well_positions:
            # XXX: why -y? i thought that was handled in useq?
            center = well_rect.translated(pos.x, -pos.y)
            top_left = center.translated(-well_width / 2, -well_height / 2)
            if plan.plate.circular_wells:
                item = self._scene.addEllipse(top_left, pen)
            else:
                item = self._scene.addRect(top_left, pen)
            self._well_items.append(item)

            # add text
            if text_item := self._scene.addText(pos.name):
                font = text_item.font() or QFont()
                font.setPixelSize(int(min(6000, well_rect.width() / 2.5)))
                text_item.setFont(font)
                br = text_item.boundingRect()
                text_item.setPos(
                    center.x() - br.width() // 2, center.y() - br.height() // 2
                )
                self._well_items.append(text_item)

        # fit scene in view
        self._scene.setSceneRect(self._scene.itemsBoundingRect())

    def clearWells(self) -> None:
        while self._well_items:
            self._scene.removeItem(self._well_items.pop())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # origin point of the SCREEN
        self.origin_point = event.screenPos()
        # rubber band to show the selection
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle)
        # origin point of the SCENE
        self.scene_origin_point = event.scenePos()

        # get the selected items
        self._selected_wells = [item for item in self.items() if item.isSelected()]

        # set the color of the selected wells to SELECTED_COLOR if they are within the
        # selection
        for item in self._selected_wells:
            item.brush = SELECTED_COLOR

        # if there is an item where the mouse is pressed and it is selected, deselect,
        # otherwise select it.
        if well := self.itemAt(self.scene_origin_point, QTransform()):
            if well.isSelected():
                well.brush = UNSELECTED_COLOR
                well.setSelected(False)
            else:
                well.brush = SELECTED_COLOR
                well.setSelected(True)
        self.valueChanged.emit()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        # update the rubber band geometry using the SCREEN origin point and the current
        self.rubber_band.setGeometry(QRect(self.origin_point, event.screenPos()))
        self.rubber_band.show()
        # get the items within the selection (within the rubber band)
        selection = self.items(QRectF(self.scene_origin_point, event.scenePos()))
        # loop through all the items in the scene and select them if they are within
        # the selection or deselect them if they are not (or if the shift key is pressed
        # while moving the movuse).
        for item in self.items():
            if item in selection:
                # if pressing shift, remove from selection
                if event.modifiers() and Qt.KeyboardModifier.ShiftModifier:
                    self._set_selected(item, False)
                else:
                    self._set_selected(item, True)
            elif item not in self._selected_wells:
                self._set_selected(item, False)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.rubber_band.hide()
        self.valueChanged.emit()


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
