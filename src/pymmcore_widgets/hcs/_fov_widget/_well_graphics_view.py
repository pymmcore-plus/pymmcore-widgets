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


class WellView(ResizingGraphicsView):
    """Graphics view to draw a well and the FOVs."""

    maxPointsDetected = Signal(int)
    positionClicked = Signal(object)
    wellSizeSet = Signal(object, object)

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
        # the item that defines the bounding area to constrain the FOVs
        self._bounding_area: QGraphicsItem | None = None
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

            # WELL BOUNDING AREA
            boundig_area = self._get_bounding_area(plan)
            self._bounding_area = self._draw_outlines(boundig_area)

        elif self._bounding_area:
            self._scene.removeItem(self._bounding_area)

        # WELL OUTLINE
        self._outline_item = self._draw_outlines()

        # DRAW FOVS
        self._draw_fovs(plan)

    def _get_bounding_area(self, plan: useq.RelativeMultiPointPlan) -> QRectF:
        """Return the bounding area to constrain the FOVs."""
        if self._well_height_um is None or self._well_width_um is None:
            return QRectF()
        w, h = plan.max_width, plan.max_height
        # constrain the bounding area to the well size if max_width or max_height is
        # larger than the well size
        w = min(w, self._well_width_um)
        h = min(h, self._well_height_um)
        return (
            QRectF(-w / 2, -h / 2, w, h)
            if self._is_circular
            else QRectF(-(w - w / 2), -(h - h / 2), w, h)
        )

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        scene_pos = self.mapToScene(event.pos())
        items = self.scene().items(scene_pos)
        for item in items:
            if pos := item.data(DATA_POSITION):
                self.positionClicked.emit(pos)
                break

    def setWellSize(self, width_mm: float | None, height_mm: float | None) -> None:
        """Set the well size width and height in mm."""
        self._well_width_um = (width_mm * 1000) if width_mm else None
        self._well_height_um = (height_mm * 1000) if height_mm else None
        self.wellSizeSet.emit(width_mm, height_mm)

    def _well_rect(self) -> QRectF:
        """Return the QRectF of the well area."""
        if not (ww := self._well_width_um) or not (wh := self._well_height_um):
            return QRectF()
        return QRectF(-ww / 2, -wh / 2, ww, wh)

    def _bounding_rect(self) -> QRectF:
        """Return the QRectF of the bounding area."""
        return self._bounding_area.boundingRect() if self._bounding_area else QRectF()

    def _draw_outlines(
        self, bounding_rect: QRectF | None = None
    ) -> QGraphicsItem | None:
        """Draw the outline of the well or the bounding area to constrain the FOVs."""
        pen = QPen(QColor(Qt.GlobalColor.green))
        pen.setWidth(self._scaled_pen_size())

        # clear the scene from the correct item
        if bounding_rect is None:
            # remove the well outline if it exists
            if self._outline_item:
                self._scene.removeItem(self._outline_item)
        else:
            # set the pen style to dotted if we are drawing the bounding area
            pen.setStyle(Qt.PenStyle.DotLine)
            # remove the bounding area if it exists
            if self._bounding_area:
                self._scene.removeItem(self._bounding_area)

        # set the correct rect to draw
        rect = bounding_rect if bounding_rect is not None else self._well_rect()

        if rect.isNull():
            return None

        return (
            self._scene.addEllipse(rect, pen=pen)
            if self._is_circular
            else self._scene.addRect(rect, pen=pen)
        )

    def _resize_to_fit(self) -> None:
        self.setSceneRect(self._scene.itemsBoundingRect())
        self.resizeEvent(None)

    def _draw_fovs(self, plan: useq.RelativeMultiPointPlan) -> None:
        """Draw the fovs in the scene as rectangles."""
        # delete existing FOVs
        while self._fov_items:
            self._scene.removeItem(self._fov_items.pop())

        half_fov_width = self._fov_width_um / 2
        half_fov_height = self._fov_height_um / 2

        # constrain random points to our own well size.
        # if the well_width_um or well_height_um is not set, we use an arbitrary value.
        # if it is set and the plan's max_width or max_height is larger, we use the well
        # size instead.
        if isinstance(plan, useq.RandomPoints):
            # arbitrary default values if well size is not set
            default_max_width = (self._fov_width_um * 25) - half_fov_width * 1.4
            default_max_height = (self._fov_height_um * 25) - half_fov_height * 1.4
            kwargs = {
                "max_width": (
                    min(plan.max_width, self._well_width_um)
                    if self._well_width_um is not None
                    else default_max_width
                ),
                "max_height": (
                    min(plan.max_height, self._well_height_um)
                    if self._well_height_um is not None
                    else default_max_height
                ),
            }
            plan = plan.replace(**kwargs)

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

        # draw the FOVs, and a connecting line
        last_p: useq.RelativePosition | None = None
        for i, pos in enumerate(points):
            screen_x = pos.x
            screen_y = -pos.y  # invert y for screen coordinates
            if i == 0:
                pen.setColor(QColor(Qt.GlobalColor.black))
            else:
                pen.setColor(QColor(Qt.GlobalColor.white))
            if item := self._scene.addRect(
                screen_x - half_fov_width,
                screen_y - half_fov_height,
                self._fov_width_um,
                self._fov_height_um,
                pen,
            ):
                item.setData(DATA_POSITION, pos)
                item.setZValue(100 if i == 0 else 0)
                self._fov_items.append(item)

            # draw a line from the last point to this one
            if i > 0 and last_p:
                self._fov_items.append(
                    self._scene.addLine(
                        last_p.x, -last_p.y, screen_x, screen_y, line_pen
                    )
                )
            last_p = pos

        self._resize_to_fit()

    def _scaled_pen_size(self) -> int:
        # pick a pen size appropriate for the scene scale
        # we might also want to scale this based on the sceneRect...
        # and it's possible this needs to be rescaled on resize
        if self._well_width_um:
            return int(self._well_width_um / 150)
        return max(61, int(self.sceneRect().width() / 150))
