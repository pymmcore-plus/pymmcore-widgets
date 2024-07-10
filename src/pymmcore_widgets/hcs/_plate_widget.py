from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Mapping

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
DATA_INDEX = 2

# in the WellPlateView, any item that merely posses a brush color of SELECTED_COLOR
# IS a selected object.
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

    selectionChanged = Signal()

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

        # all the graphics items that outline wells
        self._well_items: list[QAbstractGraphicsShapeItem] = []
        # all the graphics items that label wells
        self._well_labels: list[QGraphicsItem] = []

        # item at the point where the mouse was pressed
        self._pressed_item: QAbstractGraphicsShapeItem | None = None
        # the set of selected items at the time of the mouse press
        self._selection_on_press: set[QAbstractGraphicsShapeItem] = set()
        # whether option/alt is pressed at the time of the mouse press
        self._is_removing = False

    def _on_rubber_band_changed(self, rect: QRect) -> None:
        """When the rubber band changes, select the items within the rectangle."""
        if rect.isNull():
            # this is the last signal emitted when releasing the mouse
            return

        # all scene items within the rubber band
        bounded_items = self._scene.items(self.mapToScene(rect).boundingRect())

        for item in self._scene.items():
            if isinstance(item, QAbstractGraphicsShapeItem):
                if item in bounded_items:
                    item.setBrush(
                        UNSELECTED_COLOR if self._is_removing else SELECTED_COLOR
                    )
                else:
                    # if the item is not in the rubber band, keep its previous state
                    color = (
                        SELECTED_COLOR
                        if item in self._selection_on_press
                        else UNSELECTED_COLOR
                    )
                    item.setBrush(color)
        self.selectionChanged.emit()

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton:
            # store the state of selected items at the time of the mouse press
            self._selection_on_press = set(self._selected_items())

            # when the cmd/control key is pressed, add to the selection
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                self._is_removing = True

            # store the item at the point where the mouse was pressed
            for item in self.items(event.pos()):
                if isinstance(item, QAbstractGraphicsShapeItem):
                    self._pressed_item = item
                    break
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton:
            # if we are on the same item that we pressed,
            # toggle selection of that item
            for item in self.items(event.pos()):
                if item == self._pressed_item:
                    was_selected = self._pressed_item.brush().color() == SELECTED_COLOR
                    color = UNSELECTED_COLOR if was_selected else SELECTED_COLOR
                    self._pressed_item.setBrush(color)
                    self.selectionChanged.emit()
                    break

        self._pressed_item = None
        self._is_removing = False
        self._selection_on_press.clear()
        super().mouseReleaseEvent(event)

    def _selected_items(self) -> list[QAbstractGraphicsShapeItem]:
        # perhaps oddly (?) our selection model is based on brush color state.
        return [
            item for item in self._well_items if item.brush().color() == SELECTED_COLOR
        ]

    def selectedIndices(self) -> tuple[tuple[int, int], ...]:
        """Return the indices of the selected wells."""
        return tuple(item.data(DATA_INDEX) for item in self._selected_items())

    def setSelectedIndices(self, indices: Iterable[tuple[int, int]]) -> None:
        _indices = {tuple(idx) for idx in indices}
        for item in self._well_items:
            is_selected = item.data(DATA_INDEX) in _indices
            item.setBrush(SELECTED_COLOR if is_selected else UNSELECTED_COLOR)

    def clearSelection(self) -> None:
        """Clear the current selection."""
        for item in self._selected_items():
            item.setBrush(UNSELECTED_COLOR)
        self.selectionChanged.emit()

    def sizeHint(self) -> QSize:
        """Provide a reasonable size hint with aspect ratio of a well plate."""
        aspect = 1.5
        width = 600
        height = int(width // aspect)
        return QSize(width, height)

    def drawPlate(self, plate: useq.WellPlate | useq.WellPlatePlan) -> None:
        """Draw the well plate on the view."""
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

        indices = plan.all_well_indices.reshape(-1, 2)
        self.clearWells()
        for idx, pos in zip(indices, plan.all_well_positions):
            # invert y-axis for screen coordinates
            screen_x, screen_y = pos.x, -pos.y
            if item := add_item(well_rect.translated(screen_x, screen_y), pen):
                item.setData(DATA_POSITION, pos)
                item.setData(DATA_INDEX, tuple(idx))
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

    def __init__(
        self,
        plan: useq.WellPlatePlan | useq.WellPlate | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # well plate combobox
        self.plate_name = QComboBox()
        plate_names = sorted(useq.registered_well_plate_keys(), key=_sort_plate)
        self.plate_name.addItems(plate_names)

        # clear selection button
        self._clear_button = QPushButton(text="Clear Selection")
        self._clear_button.setAutoDefault(False)

        self.view = WellPlateView(self)
        self.view.selectionChanged.connect(self._on_value_changed)

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
        self._clear_button.clicked.connect(self.view.clearSelection)
        self.plate_name.currentTextChanged.connect(self._on_plate_name_changed)
        self.view.drawPlate(self.value())

        if plan:
            self.setValue(plan)

    # _________________________PUBLIC METHODS_________________________ #

    def value(self) -> useq.WellPlatePlan:
        """Return current plate and selected wells as a list of (name, row, column)."""
        return useq.WellPlatePlan(
            plate=self.plate_name.currentText(),
            a1_center_xy=(0, 0),
            selected_wells=tuple(zip(*self.currentSelection())),
        )

    def setValue(self, value: useq.WellPlatePlan | useq.WellPlate | Mapping) -> None:
        """Set the current plate and the selected wells.

        Parameters
        ----------
        value : PlateInfo
            The plate information to set containing the plate and the selected wells
            as a list of (name, row, column).
        """
        if isinstance(value, useq.WellPlate):
            value = useq.WellPlatePlan(plate=value, a1_center_xy=(0, 0))
        value = useq.WellPlatePlan.model_validate(value)

        if value.plate.name not in useq.registered_well_plate_keys():
            if not value.plate.name:
                raise ValueError("Plate name must be provided.")
            useq.register_well_plates({value.plate.name: value.plate})
            self.plate_name.addItem(value.plate.name)

        self.plate_name.setCurrentText(value.plate.name)

        if value.selected_wells:
            self.view.setSelectedIndices(value.selected_well_indices)

    def currentPlate(self) -> useq.WellPlate:
        return useq.WellPlate.from_str(self.plate_name.currentText())

    def setCurrentPlate(self, plate: useq.WellPlate | str) -> None:
        if isinstance(plate, useq.WellPlate):
            plate = plate.name or "Custom Plate"
        self.plate_name.setCurrentText(plate)

    def currentSelection(self) -> tuple[tuple[int, int], ...]:
        return self.view.selectedIndices()

    def setCurrentSelection(self, selection: IndexExpression) -> None: ...

    # _________________________PRIVATE METHODS________________________ #

    def _on_value_changed(self) -> None:
        """Emit the valueChanged signal when the value changes."""
        # not using lambda or tests will fail
        self.valueChanged.emit(self.value())

    def _on_plate_name_changed(self, plate_name: str) -> None:
        self.view.drawPlate(useq.WellPlate.from_str(plate_name))
        self.valueChanged.emit(self.value())
