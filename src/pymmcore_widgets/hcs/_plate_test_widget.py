from __future__ import annotations

import useq
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QRectF, Qt
from qtpy.QtGui import QFont, QMouseEvent, QPen
from qtpy.QtWidgets import QVBoxLayout, QWidget

from pymmcore_widgets.useq_widgets._well_plate_widget import (
    DATA_INDEX,
    DATA_POSITION,
    WellPlateView,
)


class _WellPlateView(WellPlateView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setDragMode(self.DragMode.NoDrag)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        return

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
                item.setData(DATA_INDEX, tuple(idx.tolist()))
                if plan.rotation:
                    item.setTransformOriginPoint(rect.center())
                    item.setRotation(-plan.rotation)
                self._well_items.append(item)

            # NOTE, we are *not* using the Qt selection model here due to
            # customizations that we want to make.  So we don't use...
            # item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

            # add text
            # if text_item := self._scene.addText(pos.name):
            #     text_item.setFont(font)
            #     br = text_item.boundingRect()
            #     text_item.setPos(
            #         screen_x - br.width() // 2,
            #         screen_y - br.height() // 2,
            #     )
            #     self._well_labels.append(text_item)

        if plan.selected_wells:
            self.setSelectedIndices(plan.selected_well_indices)

        self._resize_to_fit()


class PlateTestWidget(QWidget):
    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._plate_view = _WellPlateView(self)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._plate_view)

    def set_plate(self, plate: useq.WellPlate | useq.WellPlatePlan) -> None:
        """Set the plate to be displayed."""
        self._plate_view.drawPlate(plate)
