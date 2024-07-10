from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

import useq
from PyQt6.QtGui import QMouseEvent
from qtpy.QtCore import QRect, QRectF, QSize, Qt, Signal
from qtpy.QtGui import QFont, QPainter, QPen
from qtpy.QtWidgets import (
    QAbstractGraphicsShapeItem,
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
    from PyQt6.QtGui import QMouseEvent

    Index = int | list[int] | slice
    IndexExpression = tuple[Index, ...] | Index


DATA_POSITION = 1
SELECTED_COLOR = Qt.GlobalColor.green
UNSELECTED_COLOR = Qt.GlobalColor.transparent


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
        # RubberBandDrag enables rubber band selection with mouse
        self.setDragMode(self.DragMode.RubberBandDrag)
        self.rubberBandChanged.connect(self._on_rubber_band_changed)

        self._well_items: list[QAbstractGraphicsShapeItem] = []
        self._well_labels: list[QGraphicsItem] = []
        # item at the point where the mouse was pressed
        self._pressed_item: QAbstractGraphicsShapeItem | None = None
        # whether option/alt or cmd/control key is pressed (respectively)
        # at the time of the mouse press
        self._is_removing = False
        self._is_adding = False

    def _on_rubber_band_changed(self, rect: QRect) -> None:
        """When the rubber band changes, select the items within the rectangle."""
        if rect.isNull():
            # this is the last signal emitted when releasing the mouse
            return

        # all scene items within the rubber band
        bounded_items = self._scene.items(
            self.mapToScene(rect).boundingRect(),
            # this mode means that circular wells will be selected even if the rubber
            # band is only on the "corners" of the well (not sure if this is the best)
            Qt.ItemSelectionMode.IntersectsItemBoundingRect,
        )

        for item in self._scene.items():
            if isinstance(item, QAbstractGraphicsShapeItem):
                if item in bounded_items:
                    item.setBrush(
                        UNSELECTED_COLOR if self._is_removing else SELECTED_COLOR
                    )
                # elif not (self._is_adding or self._is_removing):
                #     item.setBrush(UNSELECTED_COLOR)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton:
            # when the cmd/control key is pressed, add to the selection
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._is_adding = True
            elif event.modifiers() & Qt.KeyboardModifier.AltModifier:
                self._is_removing = True

            for item in self.items(event.pos()):
                if isinstance(item, QAbstractGraphicsShapeItem):
                    self._pressed_item = item
                    break
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton:
            for item in self.items(event.pos()):
                if item == self._pressed_item:
                    was_selected = self._pressed_item.brush().color() == SELECTED_COLOR
                    color = UNSELECTED_COLOR if was_selected else SELECTED_COLOR
                    self._pressed_item.setBrush(color)
                    break
            # clear selection if no item was clicked
            # FIXME: this is good, but needs to play better with the mouse release
            # event of the rubber band selection
            # else:
            #     for item in self._selected_items():
            #         item.setBrush(UNSELECTED_COLOR)
        self._is_adding = False
        self._is_removing = False
        return super().mouseReleaseEvent(event)

    def _selected_items(self) -> list[QAbstractGraphicsShapeItem]:
        return [
            item for item in self._well_items if item.brush().color() == SELECTED_COLOR
        ]

    def clearSelection(self) -> None:
        for item in self._selected_items():
            item.setBrush(UNSELECTED_COLOR)

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
        well_rect = QRectF(-well_width / 2, -well_height / 2, well_width, well_height)
        add_item = (
            self._scene.addEllipse if plan.plate.circular_wells else self._scene.addRect
        )

        # font for well labels
        font = QFont()
        font.setPixelSize(int(min(6000, well_rect.width() / 2.5)))

        # Since most plates have the same extent, a constant pen width seems to work
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(200)

        self.clearWells()
        for pos in plan.all_well_positions:
            # invert y-axis for screen coordinates
            screen_x, screen_y = pos.x, -pos.y
            if item := add_item(well_rect.translated(screen_x, screen_y), pen):
                item.setData(DATA_POSITION, pos)
                self._well_items.append(item)

            # NOTE, we are *not* using the Qt selection model here due to
            # customizations that we want to make.  So we don't use...
            # item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

            # add text
            if text_item := self._scene.addText(pos.name):
                text_item.setFont(font)
                br = text_item.boundingRect()
                text_item.setPos(
                    screen_x - br.width() // 2,
                    screen_y - br.height() // 2,
                )
                self._well_labels.append(text_item)

        # fit scene in view
        self._scene.setSceneRect(self._scene.itemsBoundingRect())

    def clearWells(self) -> None:
        while self._well_items:
            self._scene.removeItem(self._well_items.pop())
        while self._well_labels:
            self._scene.removeItem(self._well_labels.pop())


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
