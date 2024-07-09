from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import useq
from qtpy.QtCore import QRectF, QSize, Qt, Signal
from qtpy.QtGui import QColor, QPainter, QPen
from qtpy.QtWidgets import QGraphicsItem, QGraphicsScene, QWidget
from useq import Shape

from pymmcore_widgets.hcs._util import ResizingGraphicsView

if TYPE_CHECKING:
    from PyQt6.QtGui import QMouseEvent

DATA_POSITION = 1
DATA_POSITION_INDEX = 2


class WellView(ResizingGraphicsView):
    """Graphics view to draw a well and the FOVs."""

    maxPointsDetected = Signal(int)
    positionClicked = Signal(int, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        self._scene = QGraphicsScene()

        super().__init__(self._scene, parent)
        self.setStyleSheet("background:grey; border-radius: 5px;")
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )

        # the scene coordinates are all real-world coordinates, in µm
        # with the origin at the center of the view (0, 0)
        self._well_width_um: float | None = 6000
        self._well_height_um: float | None = 6000
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

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        scene_pos = self.mapToScene(event.pos())
        items = self.scene().items(scene_pos)
        for item in items:
            if idx := item.data(DATA_POSITION_INDEX):
                self.positionClicked.emit(idx, item.data(DATA_POSITION))
                break

    def setWellSize(self, width_mm: float | None, height_mm: float | None) -> None:
        """Set the well size width and height in mm."""
        self._well_width_um = (width_mm * 1000) if width_mm else None
        self._well_height_um = (height_mm * 1000) if height_mm else None

    def _well_rect(self) -> QRectF:
        """Return the QRectF of the well area."""
        if not self._well_width_um or not self._well_height_um:
            return QRectF()
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

    def _draw_fovs(self, plan: useq.RelativeMultiPointPlan) -> None:
        """Draw the fovs in the scene as rectangles."""
        # delete existing FOVs
        while self._fov_items:
            self._scene.removeItem(self._fov_items.pop())

        half_fov_width = self._fov_width_um / 2
        half_fov_height = self._fov_height_um / 2

        # constrain random points to our own well size, regardless of the plan settings
        # TODO: emit a warning here?
        if isinstance(plan, useq.RandomPoints):
            kwargs = {}
            if self._well_width_um:
                kwargs["max_width"] = self._well_width_um - half_fov_width * 1.4
            if self._well_height_um:
                kwargs["max_height"] = self._well_height_um - half_fov_height * 1.4
            plan = plan.replace(**kwargs)

        pen = QPen(Qt.GlobalColor.white)
        pen.setWidth(self._scaled_pen_size())
        line_pen = QPen(QColor(0, 0, 0, 100))
        line_pen.setWidth(int(self._scaled_pen_size() // 1.5))

        # iterate over the plan greedily, catching any warnings
        # and then alert the model if we didn't get all the points
        # XXX: I'm not sure about this pattern... feels like the model should be
        # able to handle this itself, but this is perhaps the only place we actually
        # iterate over the plan
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            points = list(plan)
        if len(points) < getattr(plan, "num_points", 0):
            self.maxPointsDetected.emit(len(points))

        # draw the FOVs, and a connecting line
        last_p: useq.RelativePosition | None = None
        for i, pos in enumerate(points):
            if i == 0:
                pen.setColor(QColor(Qt.GlobalColor.black))
            else:
                pen.setColor(QColor(Qt.GlobalColor.white))
            item = self._scene.addRect(
                pos.x - half_fov_width,
                pos.y - half_fov_height,
                self._fov_width_um,
                self._fov_height_um,
                pen,
            )
            item.setData(DATA_POSITION, pos)
            item.setData(DATA_POSITION_INDEX, i)
            if item:
                item.setZValue(100 if i == 0 else 0)
                self._fov_items.append(item)
            # draw a line from the last point to this one
            if i > 0 and last_p:
                self._fov_items.append(
                    self._scene.addLine(last_p.x, last_p.y, pos.x, pos.y, line_pen)
                )
            last_p = pos

    def _scaled_pen_size(self) -> int:
        # pick a pen size appropriate for the scene scale
        # we might also want to scale this based on the sceneRect...
        # and it's possible this needs to be rescaled on resize
        if self._well_width_um:
            return int(self._well_width_um / 150)
        return int(self.sceneRect().width() / 150)
