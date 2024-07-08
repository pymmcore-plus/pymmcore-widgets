from __future__ import annotations

from typing import Iterable

import useq
from qtpy.QtCore import QRectF, QSize, Qt
from qtpy.QtGui import QColor, QPainter, QPen
from qtpy.QtWidgets import QGraphicsItem, QGraphicsScene, QWidget
from useq import Shape

from pymmcore_widgets.hcs._util import ResizingGraphicsView


class WellView(ResizingGraphicsView):
    """Graphics view to draw a well and the FOVs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self._scene = QGraphicsScene()

        super().__init__(self._scene, parent)
        self.setStyleSheet("background:grey; border-radius: 5px;")
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )

        # the scene coordinates are all real-world coordinates, in µm
        # with the origin at the center of the view (0, 0)
        self._well_width_um: float = 6000
        self._well_height_um: float = 6000
        self._fov_width_um: float = 400
        self._fov_height_um: float = 340
        self._is_circular: bool = False

        # the item that draws the outline of the entire well area
        self._outline_item: QGraphicsItem | None = None
        # all of the rectangles representing the FOVs
        self._fov_items: list[QGraphicsItem] = []

        self.setMinimumSize(250, 250)

    def sizeHint(self) -> QSize:
        return QSize(500, 500)

    def setPointsPlan(self, plan: useq.RelativeMultiPointPlan) -> None:
        """Set the plan to use to draw the FOVs."""
        plandict = plan.model_dump(exclude_none=True)
        # use our fov values if the plan doesn't have them
        plandict.setdefault("fov_width", self._fov_width_um)
        plandict.setdefault("fov_height", self._fov_height_um)
        plan = plan.model_construct(**plandict)

        self._fov_width_um = plan.fov_width
        self._fov_height_um = plan.fov_height
        if isinstance(plan, useq.RandomPoints):
            self._is_circular = plan.shape == Shape.ELLIPSE

        # WELL OUTLINE
        self._draw_outline()

        # DRAW FOVS
        self._draw_fovs(plan)

    def setWellSize(self, size: tuple[float | None, float | None]) -> None:
        """Set the well size width and height in mm."""
        if width := size[0] is not None:
            self._well_width_um = width * 1000
        if height := size[1] is not None:
            self._well_height_um = height * 1000

    def _well_rect(self) -> QRectF:
        """Return the QRectF of the well area."""
        return QRectF(
            -self._well_width_um / 2,
            -self._well_height_um / 2,
            self._well_width_um,
            self._well_height_um,
        )

    def _draw_outline(self) -> None:
        """Draw the outline of the well area."""
        if self._outline_item:
            self._scene.removeItem(self._outline_item)

        pen = QPen(QColor(Qt.GlobalColor.green))
        pen.setWidth(self._scaled_pen_size())
        if self._is_circular:
            self._outline_item = self._scene.addEllipse(self._well_rect(), pen=pen)
        else:
            self._outline_item = self._scene.addRect(self._well_rect(), pen=pen)

    def _draw_fovs(self, points: Iterable[useq.RelativePosition]) -> None:
        """Draw the fovs in the scene as rectangles."""
        # delete existing FOVs
        while self._fov_items:
            self._scene.removeItem(self._fov_items.pop())

        half_fov_width = self._fov_width_um / 2
        half_fov_height = self._fov_height_um / 2

        # constrain random points to our own well size, regardless of the plan settings
        # TODO: emit a warning here?
        if isinstance(points, useq.RandomPoints):
            points = points.replace(
                max_width=self._well_width_um - half_fov_width * 1.4,
                max_height=self._well_height_um - half_fov_height * 1.4,
            )

        pen = QPen(Qt.GlobalColor.white)
        pen.setWidth(self._scaled_pen_size())

        for pos in points:
            item = self._scene.addRect(
                pos.x - half_fov_width,
                pos.y - half_fov_height,
                self._fov_width_um,
                self._fov_height_um,
                pen,
            )
            if item:
                self._fov_items.append(item)

    def _scaled_pen_size(self) -> int:
        # pick a pen size appropriate for the scene scale
        # we might also want to scale this based on the sceneRect...
        # and it's possible this needs to be rescaled on resize
        return int(self._well_width_um / 150)
