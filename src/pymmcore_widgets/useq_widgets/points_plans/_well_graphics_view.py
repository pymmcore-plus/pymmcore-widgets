from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import useq
from qtpy.QtCore import QRectF, QSize, Qt, Signal
from qtpy.QtGui import QColor, QPainter, QPen
from qtpy.QtWidgets import QGraphicsItem, QGraphicsScene, QWidget
from useq import Shape

from pymmcore_widgets._util import ResizingGraphicsView

if TYPE_CHECKING:
    from qtpy.QtGui import QMouseEvent

DATA_POSITION = 1


class WellView(ResizingGraphicsView):
    """Graphics view to draw a well and the FOVs."""

    maxPointsDetected = Signal(int)
    positionClicked = Signal(object)

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
        self._fov_width_um: float | None = 400
        self._fov_height_um: float | None = 340
        self._is_circular: bool = False

        # the item that draws the outline of the entire well area
        self._outline_item: QGraphicsItem | None = None
        # all of the rectangles representing the FOVs
        self._fov_items: list[QGraphicsItem] = []

        self.setMinimumSize(250, 250)

    def sizeHint(self) -> QSize:
        return QSize(500, 500)

    def setWellSize(self, width_mm: float | None, height_mm: float | None) -> None:
        """Set the well size width and height in mm."""
        self._well_width_um = (width_mm * 1000) if width_mm else None
        self._well_height_um = (height_mm * 1000) if height_mm else None

    def setPointsPlan(self, plan: useq.RelativeMultiPointPlan) -> None:
        """Set the plan to use to draw the FOVs."""
        self._fov_width_um = plan.fov_width
        self._fov_height_um = plan.fov_height
        if hasattr(plan, "shape") and isinstance(plan.shape, Shape):
            self._is_circular = plan.shape == Shape.ELLIPSE

        # WELL OUTLINE
        self._draw_outline()

        # DRAW FOVS
        self._draw_fovs(plan)

    def _draw_outline(self) -> None:
        """Draw the outline of the well area."""
        if self._outline_item:
            self._scene.removeItem(self._outline_item)
        if (rect := self._well_rect()).isNull():
            return

        pen = QPen(QColor(Qt.GlobalColor.green))
        pen.setWidth(self._scaled_pen_size())
        if self._is_circular:
            self._outline_item = self._scene.addEllipse(rect, pen=pen)
        else:
            self._outline_item = self._scene.addRect(rect, pen=pen)
        self._resize_to_fit()

    def _draw_fovs(self, plan: useq.RelativeMultiPointPlan) -> None:
        """Draw the fovs in the scene as rectangles."""
        # delete existing FOVs
        while self._fov_items:
            self._scene.removeItem(self._fov_items.pop())

        # constrain random points to our own well size, regardless of the plan settings
        # XXX: this may not always be what we want...
        if isinstance(plan, useq.RandomPoints):
            updates = {}
            if fovw := self._fov_width_um:
                ww = self._well_width_um or (fovw * 25)
                updates["max_width"] = ww - fovw * 0.5 * 1.4
            if fovh := self._fov_height_um:
                wh = self._well_height_um or (fovh * 25)
                updates["max_height"] = wh - fovh * 0.5 * 1.4
            plan = plan.model_copy(update=updates)

        pen = QPen(Qt.GlobalColor.white)
        pen.setWidth(self._scaled_pen_size())
        line_pen = QPen(QColor(0, 0, 0, 100))
        line_pen.setWidth(int(self._scaled_pen_size() // 1.5))

        # iterate over the plan greedily, catching any warnings
        # and then alert the model if we didn't get all the points
        # TODO: I think this logic should somehow be on the RandomPointsWidget itself
        # however, because we add additional information above about max_width, etc
        # the RandomPointsWidget doesn't have all the information it needs ...
        # so we need to refactor this a bit
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            points = list(plan)
        if len(points) < getattr(plan, "num_points", 0):
            self.maxPointsDetected.emit(len(points))

        # decide what type of FOV to draw.
        # fov_rect will be null if no FOV is set, in which case just draw a point
        if (fov_rect := self._fov_rect()).isNull():
            w = pen.width()
            fov_rect = QRectF(-w / 2, -w / 2, w, w)
            add_item = self._scene.addEllipse
        else:
            # otherwise, draw a rectangle
            add_item = self._scene.addRect

        # draw the FOVs, and a connecting line
        last_p: useq.RelativePosition | None = None
        item: QGraphicsItem
        for i, pos in enumerate(points):
            # first point is black, the rest are white
            first_point = i == 0
            color = Qt.GlobalColor.black if first_point else Qt.GlobalColor.white
            pen.setColor(QColor(color))

            # invert y for screen coordinates
            px, py = pos.x, -pos.y
            # add the item to the scene

            # (not sure when addRect would return None, but it's possible...)
            if item := add_item(fov_rect.translated(px, py), pen):
                item.setData(DATA_POSITION, pos)
                item.setZValue(100 if first_point else 0)
                self._fov_items.append(item)

            # draw a line from the last point to this one
            if i > 0 and last_p:
                line = self._scene.addLine(last_p.x, -last_p.y, px, py, line_pen)
                line.setZValue(2)
                self._fov_items.append(line)
            last_p = pos

        self._resize_to_fit()

    def _well_rect(self) -> QRectF:
        """Return the QRectF of the well area."""
        if not (ww := self._well_width_um) or not (wh := self._well_height_um):
            return QRectF()
        return QRectF(-ww / 2, -wh / 2, ww, wh)

    def _fov_rect(self) -> QRectF:
        """Return the QRectF of the FOV area."""
        fov_w = self._fov_width_um or 0
        fov_h = self._fov_height_um or 0
        if not fov_w and not fov_h:
            return QRectF()
        return QRectF(-fov_w / 2, -fov_h / 2, fov_w, fov_h)

    def _scaled_pen_size(self) -> int:
        # pick a pen size appropriate for the scene scale
        # we might also want to scale this based on the sceneRect...
        # and it's possible this needs to be rescaled on resize
        if self._well_width_um:
            return int(self._well_width_um / 150)
        return max(61, int(self.sceneRect().width() / 150))

    def _resize_to_fit(self) -> None:
        self.setSceneRect(self._scene.itemsBoundingRect())
        self.resizeEvent(None)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None:
            scene_pos = self.mapToScene(event.pos())
            items = self.scene().items(scene_pos)
            for item in items:
                if pos := item.data(DATA_POSITION):
                    self.positionClicked.emit(pos)
                    break
