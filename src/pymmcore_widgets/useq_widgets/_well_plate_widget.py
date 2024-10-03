from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Mapping

import numpy as np
import useq
from qtpy.QtCore import QRect, QRectF, QSize, Qt, Signal
from qtpy.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen
from qtpy.QtWidgets import (
    QAbstractGraphicsShapeItem,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsSceneHoverEvent,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

from pymmcore_widgets._util import ResizingGraphicsView

if TYPE_CHECKING:
    from qtpy.QtGui import QMouseEvent

    Index = int | list[int] | tuple[int] | slice
    IndexExpression = tuple[Index, ...] | Index


def _sort_plate(item: str) -> tuple[int, int | str]:
    """Sort well plate keys by number first, then by string."""
    parts = item.split("-")
    if parts[0].isdigit():
        return (0, int(parts[0]))
    return (1, item)


DATA_POSITION = 1
DATA_INDEX = 2
DATA_SELECTED = 3
DATA_COLOR = 4


class WellPlateWidget(QWidget):
    """Widget for selecting a well plate and a subset of wells.

    The value returned/received by this widget is a [useq.WellPlatePlan][] (or simply
    a [useq.WellPlate][] if no selection is made).  This widget draws the well plate
    and allows the user to select wells by clicking/dragging on them.

    Parameters
    ----------
    plan: useq.WellPlatePlan | useq.WellPlate | None, optional
        The initial well plate plan. Accepts both a useq.WellPlate (which lacks a
        selection definition), or a full WellPlatePlan. By default None.
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

        self._plate: useq.WellPlate | None = None
        self._a1_center_xy: tuple[float, float] = (0.0, 0.0)
        self._rotation: float | None = None

        # WIDGETS ---------------------------------------

        # well plate combobox
        self.plate_name = QComboBox()
        plate_names = sorted(useq.registered_well_plate_keys(), key=_sort_plate)
        self.plate_name.addItems(plate_names)

        # clear selection button
        self._clear_button = QPushButton(text="Clear Selection")
        self._clear_button.setAutoDefault(False)

        # plate view
        self._view = WellPlateView(self)

        self._show_rotation_cb = QCheckBox("Show Rotation", self._view)
        self._show_rotation_cb.setStyleSheet("background: transparent;")
        self._show_rotation_cb.move(6, 6)
        self._show_rotation_cb.hide()
        self._show_rotation = True

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
        main_layout.addWidget(self._view)

        # connect
        self._view.selectionChanged.connect(self._on_value_changed)
        self._clear_button.clicked.connect(self._view.clearSelection)
        self.plate_name.currentTextChanged.connect(self._on_plate_name_changed)
        self._show_rotation_cb.toggled.connect(self._update_view)

        if plan:
            self.setValue(plan)
        else:
            self.setValue(self.value())

    # _________________________PUBLIC METHODS_________________________ #

    def setShowRotation(self, allow: bool) -> None:
        """Set whether to allow visible rotation of the well plate.

        If `allow` is False, the rotation checkbox is hidden and the rotation is
        never shown.  If True, the checkbox is shown and the user can toggle the
        rotation on/off.
        """
        self._show_rotation = allow
        if not allow:
            self._show_rotation_cb.hide()
            self._show_rotation_cb.setChecked(False)
        elif self._rotation:
            self._show_rotation_cb.show()
            self._show_rotation_cb.setChecked(True)

    def value(self) -> useq.WellPlatePlan:
        """Return the current plate and the selected wells as a `useq.WellPlatePlan`."""
        return useq.WellPlatePlan(
            plate=self._plate or useq.WellPlate.from_str(self.plate_name.currentText()),
            a1_center_xy=self._a1_center_xy,
            rotation=self._rotation,
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
            plan = useq.WellPlatePlan(plate=value, a1_center_xy=(0, 0))
        else:
            plan = useq.WellPlatePlan.model_validate(value)

        self._plate = plan.plate
        self._rotation = plan.rotation
        self._a1_center_xy = plan.a1_center_xy
        with signals_blocked(self):
            self.plate_name.setCurrentText(plan.plate.name)
        self._update_view(plan)

        if self._show_rotation and plan.rotation:
            self._show_rotation_cb.show()
        else:
            self._show_rotation_cb.hide()

    def _update_view(self, value: bool | useq.WellPlatePlan | None = None) -> None:
        rot = self._rotation if self._show_rotation_cb.isChecked() else None
        plan = value if isinstance(value, useq.WellPlatePlan) else self.value()
        val = plan.model_copy(update={"rotation": rot})
        self._view.drawPlate(val)

    def currentSelection(self) -> tuple[tuple[int, int], ...]:
        """Return the indices of the selected wells as `((row, col), ...)`."""
        return self._view.selectedIndices()

    def setCurrentSelection(self, selection: IndexExpression) -> None:
        """Select the wells with the given indices.

        `selection` can be any 2-d numpy indexing expression, e.g.:
        - (0, 0)
        - [(0, 0), (1, 1), (2, 2)]
        - slice(0, 2)
        - (0, slice(0, 2))
        """
        self.setValue(
            useq.WellPlatePlan(
                plate=self.plate_name.currentText(),
                a1_center_xy=(0, 0),
                selected_wells=selection,
            )
        )

    # _________________________PRIVATE METHODS________________________ #

    def _on_value_changed(self) -> None:
        """Emit the valueChanged signal when the value changes."""
        self.valueChanged.emit(self.value())

    def _on_plate_name_changed(self, plate_name: str) -> None:
        self._view.clearSelection()
        plate = useq.WellPlate.from_str(plate_name)
        val = self.value().model_copy(update={"plate": plate, "selected_wells": None})
        self.setValue(val)
        self.valueChanged.emit(self.value())


class HoverEllipse(QGraphicsEllipseItem):
    def __init__(self, rect: QRectF, parent: QGraphicsItem | None = None):
        super().__init__(rect, parent)
        self.setAcceptHoverEvents(True)
        self._selected_color = Qt.GlobalColor.green
        self._unselected_color = Qt.GlobalColor.black
        self.setBrush(self._unselected_color)

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        """Update color and position when hovering over the well."""
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setBrush(self._selected_color)
        # update tooltip font color
        tooltip = self.toolTip()
        self.setToolTip(f"<font color='#CCC'>{tooltip}</font>")
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        """Reset color and position when leaving the well."""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setBrush(self._unselected_color)
        super().hoverLeaveEvent(event)


class WellPlateView(ResizingGraphicsView):
    """QGraphicsView for displaying a well plate."""

    selectionChanged = Signal()
    positionDoubleClicked = Signal(useq.Position)
    SelectionMode = QAbstractItemView.SelectionMode

    def __init__(self, parent: QWidget | None = None) -> None:
        self._scene = QGraphicsScene()
        super().__init__(self._scene, parent)
        self._selection_mode = QAbstractItemView.SelectionMode.MultiSelection
        self._selected_color = Qt.GlobalColor.green
        self._unselected_color = Qt.GlobalColor.transparent
        self._draw_labels: bool = True
        self._draw_well_edge_spots: bool = False

        self.setStyleSheet("background:grey; border-radius: 5px;")
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        # RubberBandDrag enables rubber band selection with mouse
        self.setDragMode(self.DragMode.RubberBandDrag)
        self.rubberBandChanged.connect(self._on_rubber_band_changed)

        # all the graphics items that outline wells
        self._well_items: dict[tuple[int, int], QAbstractGraphicsShapeItem] = {}
        # all the graphics items that label wells
        self._well_labels: list[QGraphicsItem] = []
        self._well_edge_spots: list[QGraphicsItem] = []

        # we manually manage the selection state of items
        self._selected_items: set[QAbstractGraphicsShapeItem] = set()
        # the set of selected items at the time of the mouse press
        self._selection_on_press: set[QAbstractGraphicsShapeItem] = set()

        # item at the point where the mouse was pressed
        self._pressed_item: QAbstractGraphicsShapeItem | None = None
        # whether option/alt is pressed at the time of the mouse press
        self._is_removing = False

    def setSelectedColor(self, color: Qt.GlobalColor) -> None:
        """Set the color of the selected wells."""
        self._selected_color = color

    def selectedColor(self) -> Qt.GlobalColor:
        """Return the color of the selected wells."""
        return self._selected_color

    def setSelectionMode(self, mode: QAbstractItemView.SelectionMode) -> None:
        self._selection_mode = mode

    def selectionMode(self) -> QAbstractItemView.SelectionMode:
        return self._selection_mode

    def setDrawLabels(self, draw: bool) -> None:
        """Set whether to draw the well labels."""
        self._draw_labels = draw

    def setDrawWellEdgeSpots(self, draw: bool) -> None:
        """Set whether to draw the well edge spots."""
        self._draw_well_edge_spots = draw

    def _on_rubber_band_changed(self, rect: QRect) -> None:
        """When the rubber band changes, select the items within the rectangle."""
        if rect.isNull():  # pragma: no cover
            # this is the last signal emitted when releasing the mouse
            return

        # all scene items within the rubber band
        bounded_items = set(self._scene.items(self.mapToScene(rect).boundingRect()))

        # loop through all wells and recolor them based on their selection state
        select = set()
        deselect = set()
        for item in self._well_items.values():
            if item in bounded_items:
                if self._is_removing:
                    deselect.add(item)
                else:
                    select.add(item)
            # if the item is not in the rubber band, keep its previous state
            elif item in self._selection_on_press:
                select.add(item)
            else:
                deselect.add(item)
        self._change_selection(select, deselect)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton:
            # store the state of selected items at the time of the mouse press
            self._selection_on_press = self._selected_items.copy()

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
                    if self._pressed_item.data(DATA_SELECTED) is True:
                        self._change_selection((), (self._pressed_item,))
                    else:
                        if self._selection_mode == self.SelectionMode.SingleSelection:
                            # deselect all other items
                            self._change_selection((), self._selected_items)
                        if self._selection_mode != self.SelectionMode.NoSelection:
                            self._change_selection((self._pressed_item,), ())
                    break

        self._pressed_item = None
        self._is_removing = False
        self._selection_on_press.clear()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:
        """Emit stage position when a position-storing item is double-clicked."""
        if event is not None:
            if pos := next(
                (item.data(DATA_POSITION) for item in self.items(event.pos())), None
            ):
                self.positionDoubleClicked.emit(pos)
        super().mouseDoubleClickEvent(event)

    def selectedIndices(self) -> tuple[tuple[int, int], ...]:
        """Return the indices of the selected wells."""
        return tuple(sorted(item.data(DATA_INDEX) for item in self._selected_items))

    def setSelectedIndices(self, indices: Iterable[tuple[int, int]]) -> None:
        """Select the wells with the given indices.

        Parameters
        ----------
        indices : Iterable[tuple[int, int]]
            The indices of the wells to select. Each index is a tuple of row and column.
            e.g. [(0, 0), (1, 1), (2, 2)]
        """
        _indices = {tuple(idx) for idx in indices}
        select = set()
        deselect = set()
        for item in self._well_items.values():
            if item.data(DATA_INDEX) in _indices:
                select.add(item)
            else:
                deselect.add(item)
        self._change_selection(select, deselect)

    def clearSelection(self) -> None:
        """Clear the current selection."""
        self._change_selection((), self._selected_items)

    def clear(self) -> None:
        """Clear all the wells from the view."""
        while self._well_items:
            self._scene.removeItem(self._well_items.popitem()[1])
        while self._well_labels:
            self._scene.removeItem(self._well_labels.pop())
        while self._well_edge_spots:
            self._scene.removeItem(self._well_edge_spots.pop())
        self.clearSelection()

    def drawPlate(self, plan: useq.WellPlate | useq.WellPlatePlan) -> None:
        """Draw the well plate on the view.

        Parameters
        ----------
        plan : useq.WellPlate | useq.WellPlatePlan
            The WellPlatePlan to draw. If a WellPlate is provided, the plate is drawn
            with no selected wells.
        """
        if isinstance(plan, useq.WellPlate):  # pragma: no cover
            plan = useq.WellPlatePlan(a1_center_xy=(0, 0), plate=plan)

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

        self.clear()
        indices = plan.all_well_indices.reshape(-1, 2)
        for idx, pos in zip(indices, plan.all_well_positions):
            # invert y-axis for screen coordinates
            screen_x, screen_y = pos.x, -pos.y
            rect = well_rect.translated(screen_x, screen_y)
            if item := add_item(rect, pen):
                item.setData(DATA_POSITION, pos)
                index = tuple(idx.tolist())
                item.setData(DATA_INDEX, index)
                if plan.rotation:
                    item.setTransformOriginPoint(rect.center())
                    item.setRotation(-plan.rotation)
                self._well_items[index] = item

            # NOTE, we are *not* using the Qt selection model here due to
            # customizations that we want to make.  So we don't use...
            # item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

            # add text
            if self._draw_labels:
                if text_item := self._scene.addText(pos.name):
                    text_item.setFont(font)
                    br = text_item.boundingRect()
                    text_item.setPos(
                        screen_x - br.width() // 2, screen_y - br.height() // 2
                    )
                    self._well_labels.append(text_item)

            if self._draw_well_edge_spots:
                self._add_preset_positions_items(rect, pos, plan)

        if plan.selected_wells:
            self.setSelectedIndices(plan.selected_well_indices)

        self._resize_to_fit()

    def _add_preset_positions_items(
        self,
        rect: QRectF,
        pos: useq.Position,
        plan: useq.WellPlatePlan,
    ) -> None:
        plate = plan.plate
        well_width = plate.well_size[0] * 1000
        well_height = plate.well_size[1] * 1000

        # calculate radius for the _PresetPositionItem based on well spacing and size
        half_sx = plate.well_spacing[0] * 1000 / 2
        half_sy = plate.well_spacing[1] * 1000 / 2
        width, height = half_sx - well_width / 2, half_sy - well_height / 2
        width = min(width, height)

        # central point
        cx, cy = rect.center().x(), rect.center().y()
        positions = [
            [cx, cy],
            [cx - well_width / 2, cy],  # center  # left
            [cx + well_width / 2, cy],  # right
            [cx, cy - well_height / 2],  # top
            [cx, cy + well_height / 2],  # bottom
        ]

        if plan.rotation:
            rad = -np.deg2rad(plan.rotation)
            cos_rad = np.cos(rad)
            sin_rad = np.sin(rad)
            for p in positions:
                dx, dy = p[0] - cx, p[1] - cy
                rotated_x = cx + dx * cos_rad - dy * sin_rad
                rotated_y = cy + dx * sin_rad + dy * cos_rad
                p[0], p[1] = rotated_x, rotated_y

        for x, y in positions:
            edge_rect = QRectF(x - width / 2, y - width / 2, width, width)
            new_pos = useq.Position(x=x, y=y, name=pos.name)
            item = HoverEllipse(edge_rect)
            item.setData(DATA_POSITION, new_pos)
            if new_pos.x is not None and new_pos.y is not None:
                item.setToolTip(f"{new_pos.name} ({new_pos.x:.0f}, {new_pos.y:.0f})")
            item.setZValue(1)  # make sure it's on top
            self._scene.addItem(item)
            self._well_edge_spots.append(item)

    def _resize_to_fit(self) -> None:
        self.setSceneRect(self._scene.itemsBoundingRect())
        self.resizeEvent(None)

    def _change_selection(
        self,
        select: Iterable[QAbstractGraphicsShapeItem],
        deselect: Iterable[QAbstractGraphicsShapeItem],
    ) -> None:
        before = self._selected_items.copy()

        for item in select:
            color = item.data(DATA_COLOR) or self._selected_color
            item.setBrush(color)
            item.setData(DATA_SELECTED, True)
        self._selected_items.update(select)

        for item in deselect:
            if item.data(DATA_SELECTED):
                color = item.data(DATA_COLOR) or self._unselected_color
                item.setBrush(color)
                item.setData(DATA_SELECTED, False)
        self._selected_items.difference_update(deselect)

        if before != self._selected_items:
            self.selectionChanged.emit()

    def sizeHint(self) -> QSize:
        """Provide a reasonable size hint with aspect ratio of a well plate."""
        aspect = 1.5
        width = 600
        height = int(width // aspect)
        return QSize(width, height)

    def setWellColor(self, row: int, col: int, color: Qt.GlobalColor | None) -> None:
        """Set the color of the well at the given row and column.

        This overrides any selection color.  If `color` is None, the well color is
        determined by the selection state.
        """
        if item := self._well_items.get((row, col)):
            if color is not None:
                color = QColor(color)
            item.setData(DATA_COLOR, color)
            if color is None:
                color = (
                    self._selected_color
                    if item.data(DATA_SELECTED)
                    else self._unselected_color
                )
            item.setBrush(color)
