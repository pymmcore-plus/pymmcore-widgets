from __future__ import annotations

from typing import TYPE_CHECKING

import useq
from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from PyQt6.QtGui import QMouseEvent
from qtpy.QtCore import QRectF, QSize, Qt, Signal
from qtpy.QtGui import QColor, QFont, QPainter, QPen
from qtpy.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsSceneHoverEvent,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon

from pymmcore_widgets.useq_widgets._well_plate_widget import (
    DATA_INDEX,
    DATA_POSITION,
    SELECTED_COLOR,
    UNSELECTED_COLOR,
    WellPlateView,
)

if TYPE_CHECKING:
    import numpy as np
    from PyQt6.QtWidgets import QGraphicsSceneMouseEvent
    from qtpy.QtGui import QMouseEvent

SELECTED_COLOR = QColor(SELECTED_COLOR)
SELECTED_COLOR.setAlpha(127)  # Set opacity to 50%


class _HoverableWellItem(QGraphicsItem):
    def __init__(
        self,
        mmcore: CMMCorePlus,
        rect: QRectF,
        circular_well: bool,
        parent: QGraphicsItem | None = None,
    ) -> None:
        QGraphicsItem.__init__(self, parent)
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


class _WellPlateView(WellPlateView):
    positionChanged = Signal(object)

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self.setDragMode(self.DragMode.NoDrag)

        self._mmc = mmcore or CMMCorePlus.instance()

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if not event:
            return

        item = self.itemAt(event.pos())
        if not item:
            self.positionChanged.emit(None)
            return

        parent_item = item.parentItem()
        if isinstance(parent_item, _HoverableWellItem):
            self.positionChanged.emit(parent_item._current_position)
        else:
            self.positionChanged.emit(None)
        super().mouseMoveEvent(event)

    # overwriting the super method to not use the well selection logic
    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        return

    # overwriting the super method to not use the well selection logic
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
        # NOTE: rewriting the whole method to use the _HoverableWellItem in _add_item

        if isinstance(plan, useq.WellPlate):  # pragma: no cover
            plan = useq.WellPlatePlan(a1_center_xy=(0, 0), plate=plan)

        well_width = plan.plate.well_size[0] * 1000
        well_height = plan.plate.well_size[1] * 1000
        well_rect = QRectF(-well_width / 2, -well_height / 2, well_width, well_height)

        # font for well labels
        font = QFont()
        font.setPixelSize(int(min(6000, well_rect.width() / 2.5)))

        self.clear()
        indices = plan.all_well_indices.reshape(-1, 2)
        for idx, pos in zip(indices, plan.all_well_positions):
            # invert y-axis for screen coordinates
            screen_x, screen_y = pos.x, -pos.y
            rect = well_rect.translated(screen_x, screen_y)
            item = self._add_item(rect, plan.plate.circular_wells, pos, idx)
            if plan.rotation:
                item.setTransformOriginPoint(rect.center())
                item.setRotation(-plan.rotation)
            self._well_items.append(item)

            # add text
            if text_item := self._scene.addText(pos.name):
                text_item.setFont(font)
                br = text_item.boundingRect()
                text_item.setPos(
                    screen_x - br.width() // 2, screen_y - br.height() // 2
                )
                self._well_labels.append(text_item)

        if plan.selected_wells:
            self.setSelectedIndices(plan.selected_well_indices)

        self._resize_to_fit()

    def _add_item(
        self, rect: QRectF, circular_wells: bool, pos: useq.Position, idx: np.ndarray
    ) -> QGraphicsItem:
        item = _HoverableWellItem(self._mmc, rect, circular_wells)
        item.setZValue(1)
        item.setData(DATA_POSITION, pos)
        item.setData(DATA_INDEX, tuple(idx.tolist()))
        self._scene.addItem(item)
        return item


class PlateNavigator(QWidget):
    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._info_label = QLabel(
            "Double-Click on any point inside a well to move the stage."
        )
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self._info_label.font()
        font.setBold(True)
        self._info_label.setFont(font)

        self._xy_label = QLabel()

        self._stop_button = QPushButton("Stop Stage")
        self._stop_button.setIcon(icon(MDI6.stop, color=Qt.GlobalColor.red))
        self._stop_button.setIconSize(QSize(30, 30))

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(10, 10, 10, 10)
        bottom_layout.addWidget(self._xy_label)
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(self._stop_button)

        self._plate_view = _WellPlateView(self)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)
        main_layout.addWidget(self._info_label)
        main_layout.addWidget(self._plate_view)
        main_layout.addLayout(bottom_layout)

        # connections
        self._stop_button.clicked.connect(self._stop_stage)
        self._plate_view.positionChanged.connect(self._on_position_changed)

    def set_plan(self, plan: useq.WellPlate | useq.WellPlatePlan) -> None:
        """Set the plate to be displayed."""
        self._plate_view.drawPlate(plan)

    def _stop_stage(self) -> None:
        self._mmc.stop(self._mmc.getXYStageDevice())

    def _on_position_changed(self, position: tuple[float, float] | None) -> None:
        if position is None:
            self._xy_label.setText("")
            return
        self._xy_label.setText(f"X: {position[0]:.2f}, Y: {position[1]:.2f}")
