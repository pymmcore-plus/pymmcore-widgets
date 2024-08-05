from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QRectF, Qt, Signal
from qtpy.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen
from qtpy.QtWidgets import (
    QCheckBox,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QHBoxLayout,
    QLabel,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets.useq_widgets._well_plate_widget import (
    DATA_POSITION,
    WellPlateView,
)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsSceneMouseEvent
    from qtpy.QtGui import QMouseEvent

UNSELECTED_COLOR = Qt.GlobalColor.transparent
SELECTED_COLOR = QColor(Qt.GlobalColor.green)
SELECTED_COLOR.setAlpha(127)  # Set opacity to 50%
UNSELECTED_MOVE_TO_COLOR = QColor(Qt.GlobalColor.black)
FREE_MOVEMENT = (
    "Double-Click anywhere inside a well to move the stage to that position."
)
PRESET_MOVEMENT = "Double-Click on any point to move the stage to that position."


class _HoverWellItem(QGraphicsItem):
    def __init__(
        self,
        mmcore: CMMCorePlus,
        rect: QRectF,
        circular_well: bool,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._mmc = mmcore

        self._current_position: tuple[float, float] | None = None

        if circular_well:
            self._item = QGraphicsEllipseItem(rect, self)
        else:
            self._item = QGraphicsRectItem(rect, self)

        self.setAcceptHoverEvents(True)
        self._item.setBrush(UNSELECTED_COLOR)
        self._item.setPen(QPen(Qt.GlobalColor.black, 200))

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Move the stage to the clicked position in the well."""
        print("mouseDoubleClickEvent")
        if event and event.button() == Qt.MouseButton.LeftButton:
            x, y = self._get_current_xy_coords(event)
            self._current_position = (x, y)
            self._mmc.waitForSystem()
            self._mmc.setXYPosition(x, y)

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        """Update color and position when hovering over the well."""
        self._item.setBrush(SELECTED_COLOR)
        if not event:
            return
        self._current_position = self._get_current_xy_coords(event)
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        """Update color and position when hovering over the well."""
        self._item.setBrush(SELECTED_COLOR)
        if not event:
            return
        self._current_position = self._get_current_xy_coords(event)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        """Reset color andwhen leaving the well."""
        self._current_position = None
        self._item.setBrush(UNSELECTED_COLOR)
        super().hoverLeaveEvent(event)

    def _get_current_xy_coords(
        self, event: QGraphicsSceneHoverEvent | QGraphicsSceneMouseEvent
    ) -> tuple[float, float]:
        scene_pos = self.mapToScene(event.pos())
        pos = self._item.mapFromScene(scene_pos)
        x, y = pos.x(), -pos.y()
        return x, y

    def boundingRect(self) -> QRectF:
        return self._item.boundingRect()

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget
    ) -> None:
        self._item.paint(painter, option, widget)


class _PresetPositionItem(QGraphicsItem):
    def __init__(
        self,
        rect: QRectF,
        mmcore: CMMCorePlus,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._mmc = mmcore

        self._item = QGraphicsEllipseItem(rect, self)

        self._current_position: tuple[float, float] | None = None

        self.setAcceptHoverEvents(True)
        self._item.setBrush(UNSELECTED_MOVE_TO_COLOR)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Move the stage to the clicked position in the well."""
        if event and event.button() == Qt.MouseButton.LeftButton:
            pos = self.data(DATA_POSITION)
            self._mmc.waitForSystem()
            self._mmc.setXYPosition(pos.x, pos.y)
            self._current_position = (pos.x, pos.y)

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        """Update color and position when hovering over the well."""
        self._item.setBrush(SELECTED_COLOR)
        self._update_current_position()
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        """Update color and position when hovering over the well."""
        self._item.setBrush(SELECTED_COLOR)
        self._update_current_position()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        """Reset color andwhen leaving the well."""
        self._item.setBrush(UNSELECTED_MOVE_TO_COLOR)
        self._current_position = None
        super().hoverLeaveEvent(event)

    def boundingRect(self) -> QRectF:
        return self._item.boundingRect()

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget
    ) -> None:
        self._item.paint(painter, option, widget)

    def _update_current_position(self) -> None:
        pos = self.data(DATA_POSITION)
        self._current_position = (pos.x, pos.y)


class _WellPlateView(WellPlateView):
    positionChanged = Signal(object)

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self.setDragMode(self.DragMode.NoDrag)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._plan: useq.WellPlatePlan | None = None

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if not event:
            return

        item = self.itemAt(event.pos())
        if not item:
            self.positionChanged.emit(None)
            return

        parent_item = item.parentItem()
        if isinstance(parent_item, (_HoverWellItem, _PresetPositionItem)):
            self.positionChanged.emit(parent_item._current_position)
        else:
            self.positionChanged.emit(None)
        super().mouseMoveEvent(event)

    # overriding the super method to not use the well selection logic
    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        return

    # overriding the super method to not use the well selection logic
    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        return

    def drawPlate(self, plan: useq.WellPlate | useq.WellPlatePlan) -> None:
        """Draw the well plate on the view.

        Parameters
        ----------
        plan : useq.WellPlate | useq.WellPlatePlan
            The WellPlatePlan to draw. If a WellPlate is provided, the plate is drawn
            with no selected wells.
        """
        # NOTE: rewriting the whole method to use the _HoverWellItem

        self._scene.clear()

        if isinstance(plan, useq.WellPlate):  # pragma: no cover
            plan = useq.WellPlatePlan(a1_center_xy=(0, 0), plate=plan)

        self._plan = plan

        well_width = plan.plate.well_size[0] * 1000
        well_height = plan.plate.well_size[1] * 1000
        well_rect = QRectF(-well_width / 2, -well_height / 2, well_width, well_height)

        # font for well labels
        font = QFont()
        font.setPixelSize(int(min(6000, well_rect.width() / 2.5)))

        for pos in plan.all_well_positions:
            # invert y-axis for screen coordinates
            screen_x, screen_y = pos.x, -pos.y
            rect = well_rect.translated(screen_x, screen_y)

            item = self._add_hover_well_item(rect, plan.plate.circular_wells, pos)

            if plan.rotation:
                item.setTransformOriginPoint(rect.center())
                item.setRotation(-plan.rotation)

            # add text
            if text_item := self._scene.addText(pos.name):
                text_item.setFont(font)
                br = text_item.boundingRect()
                text_item.setPos(
                    screen_x - br.width() // 2, screen_y - br.height() // 2
                )

        if plan.selected_wells:
            self.setSelectedIndices(plan.selected_well_indices)

        self._resize_to_fit()

    def _add_hover_well_item(
        self, rect: QRectF, circular_wells: bool, pos: useq.Position
    ) -> QGraphicsItem:
        item = _HoverWellItem(self._mmc, rect, circular_wells)
        item.setZValue(1)
        item.setData(DATA_POSITION, pos)
        self._scene.addItem(item)
        return item

    def drawPlatePresetPositions(
        self, plan: useq.WellPlate | useq.WellPlatePlan
    ) -> None:
        """Draw the well plate on the view with preset positions.

        Parameters
        ----------
        plan : useq.WellPlate | useq.WellPlatePlan
            The WellPlatePlan to draw. If a WellPlate is provided, the plate is drawn
            with no selected wells.
        """
        # NOTE: rewriting the whole method to use the _PresetPositionItem

        self._scene.clear()

        if isinstance(plan, useq.WellPlate):  # pragma: no cover
            plan = useq.WellPlatePlan(a1_center_xy=(0, 0), plate=plan)

        self._plan = plan

        well_width = plan.plate.well_size[0] * 1000
        well_height = plan.plate.well_size[1] * 1000
        well_rect = QRectF(-well_width / 2, -well_height / 2, well_width, well_height)

        for pos in plan.all_well_positions:
            # invert y-axis for screen coordinates
            screen_x, screen_y = pos.x, -pos.y
            rect = well_rect.translated(screen_x, screen_y)

            item = self._add_well_outline(rect, plan.plate.circular_wells)
            self._add_preset_positions_items(rect, pos, plan)

            if plan.rotation:
                item.setTransformOriginPoint(rect.center())
                item.setRotation(-plan.rotation)

        if plan.selected_wells:
            self.setSelectedIndices(plan.selected_well_indices)

        self._resize_to_fit()

    def _add_well_outline(self, rect: QRectF, circular_wells: bool) -> QGraphicsItem:
        item = QGraphicsEllipseItem(rect) if circular_wells else QGraphicsRectItem(rect)
        item.setPen(QPen(Qt.GlobalColor.black, 200))
        item.setZValue(0)
        self._scene.addItem(item)
        return item

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
        rect = QRectF(cx - width / 2, cy - width / 2, width, width)
        self._add_preset_position_item(rect, pos)

        # points on the edges
        positions = [
            (cx - well_width / 2, cy),  # left
            (cx + well_width / 2, cy),  # right
            (cx, cy - well_height / 2),  # top
            (cx, cy + well_height / 2),  # bottom
        ]

        for x, y in positions:
            edge_rect = QRectF(x - width / 2, y - width / 2, width, width)
            self._add_preset_position_item(
                edge_rect, useq.Position(x=x, y=y), plan.rotation
            )

    def _add_preset_position_item(
        self, rect: QRectF, pos: useq.Position, rotation: float | None = None
    ) -> None:
        item = _PresetPositionItem(rect, self._mmc)
        center_x, center_y = rect.center().x(), rect.center().y()

        # adjust position if rotation
        if rotation is not None:
            rad = np.deg2rad(rotation)
            cos_rad = np.cos(rad)
            sin_rad = np.sin(rad)
            rotated_x = (
                center_x + (pos.x - center_x) * cos_rad - (pos.y - center_y) * sin_rad
            )
            rotated_y = -(
                center_y + (pos.x - center_x) * sin_rad + (pos.y - center_y) * cos_rad
            )
            rotated_pos = useq.Position(x=rotated_x, y=rotated_y)
            item.setData(DATA_POSITION, rotated_pos)
        else:
            item.setData(DATA_POSITION, pos)

        self._scene.addItem(item)


class PlateNavigatorWidget(QWidget):
    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._info_label = QLabel(FREE_MOVEMENT)
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self._info_label.font()
        font.setBold(True)
        self._info_label.setFont(font)

        self._xy_label = QLabel()

        self._preset_movements = QCheckBox("Preset Movements")

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(10, 10, 10, 10)
        top_layout.addWidget(self._info_label)
        top_layout.addStretch(1)
        top_layout.addWidget(self._preset_movements)

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(10, 10, 10, 10)
        bottom_layout.addWidget(self._xy_label)
        bottom_layout.addStretch(1)

        self._plate_view = _WellPlateView(self)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self._plate_view)
        main_layout.addLayout(bottom_layout)

        # connections
        self._plate_view.positionChanged.connect(self._on_position_changed)
        self._preset_movements.toggled.connect(self._on_preset_movements_toggled)

    def set_plan(self, plan: useq.WellPlate | useq.WellPlatePlan) -> None:
        """Set the plate to be displayed."""
        self._plate_view.drawPlate(plan)

    def _on_position_changed(self, position: tuple[float, float] | None) -> None:
        if position is None:
            self._xy_label.setText("")
            return
        self._xy_label.setText(f"X: {position[0]:.2f}, Y: {position[1]:.2f}")

    def _on_preset_movements_toggled(self, checked: bool) -> None:
        self._plate_view._scene.clear()

        plan = self._plate_view._plan
        if plan is None:
            return

        if checked:
            self._plate_view.drawPlatePresetPositions(plan)
            self._info_label.setText(PRESET_MOVEMENT)
        else:
            self._plate_view.drawPlate(plan)
            self._info_label.setText(FREE_MOVEMENT)
