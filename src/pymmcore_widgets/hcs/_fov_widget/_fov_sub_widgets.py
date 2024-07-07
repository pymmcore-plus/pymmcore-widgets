from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, Optional

from qtpy.QtCore import QRectF, Qt, Signal
from qtpy.QtGui import QColor, QPen
from qtpy.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGroupBox,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from useq import GridRowsColumns, Position, RandomPoints, RelativePosition
from useq._grid import Shape

from pymmcore_widgets.hcs._graphics_items import (
    FOV,
    GREEN,
    _FOVGraphicsItem,
    _WellAreaGraphicsItem,
)
from pymmcore_widgets.hcs._util import _ResizingGraphicsView

from ._util import nearest_neighbor

AlignCenter = Qt.AlignmentFlag.AlignCenter
FIXED_POLICY = (QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
DEFAULT_VIEW_SIZE = (300, 300)  # px
DEFAULT_WELL_SIZE = (10, 10)  # mm
DEFAULT_FOV_SIZE = (DEFAULT_WELL_SIZE[0] / 10, DEFAULT_WELL_SIZE[1] / 10)  # mm
PEN_WIDTH = 4
RECT = Shape.RECTANGLE
ELLIPSE = Shape.ELLIPSE
PEN_AREA = QPen(QColor(GREEN))
PEN_AREA.setWidth(PEN_WIDTH)


class Center(Position):
    """A subclass of GridRowsColumns to store the center coordinates and FOV size.

    Attributes
    ----------
    fov_width : float | None
        The width of the FOV in µm.
    fov_height : float | None
        The height of the FOV in µm.
    """

    fov_width: Optional[float] = None  # noqa: UP007
    fov_height: Optional[float] = None  # noqa: UP007


class _CenterFOVWidget(QGroupBox):
    """Widget to select the center of a specifiied area."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._x: float = 0.0
        self._y: float = 0.0

        self._fov_size: tuple[float | None, float | None] = (None, None)

        lbl = QLabel(text="Center of the Well.")
        lbl.setStyleSheet("font-weight: bold;")
        lbl.setAlignment(AlignCenter)

        # main
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(lbl)

    @property
    def fov_size(self) -> tuple[float | None, float | None]:
        """Return the FOV size."""
        return self._fov_size

    @fov_size.setter
    def fov_size(self, size: tuple[float | None, float | None]) -> None:
        """Set the FOV size."""
        self._fov_size = size

    def value(self) -> Center:
        """Return the values of the widgets."""
        fov_x, fov_y = self._fov_size
        return Center(x=self._x, y=self._y, fov_width=fov_x, fov_height=fov_y)

    def setValue(self, value: Center) -> None:
        """Set the values of the widgets."""
        self._x = value.x or 0.0
        self._y = value.y or 0.0
        self.fov_size = (value.fov_width, value.fov_height)


@dataclass
class _WellViewData:
    """A NamedTuple to store the well view data.

    Attributes
    ----------
    well_size : tuple[float | None, float | None]
        The size of the well in µm. By default, (None, None).
    circular : bool
        True if the well is circular. By default, False.
    padding : int
        The padding in pixel between the well and the view. By default, 0.
    show_fovs_order : bool
        If True, the FOVs will be connected by black lines to represent the order of
        acquisition. In addition, the first FOV will be drawn with a black color, the
        others with a white color. By default, True.
    mode : Center | GridRowsColumns | RandomPoints | None
        The mode to use to draw the FOVs. By default, None.
    """

    well_size: tuple[float | None, float | None] = (None, None)
    circular: bool = False
    padding: int = 0
    show_fovs_order: bool = True
    mode: Center | GridRowsColumns | RandomPoints | None = None

    def replace(self, **kwargs: Any) -> _WellViewData:
        """Replace the attributes of the dataclass."""
        return _WellViewData(
            well_size=kwargs.get("well_size", self.well_size),
            circular=kwargs.get("circular", self.circular),
            padding=kwargs.get("padding", self.padding),
            show_fovs_order=kwargs.get("show_fovs_order", self.show_fovs_order),
            mode=kwargs.get("mode", self.mode),
        )


DEFAULT_WELL_DATA = _WellViewData()


class _WellView(_ResizingGraphicsView):
    """Graphics view to draw a well and the FOVs.

    Parameters
    ----------
    parent : QWidget | None
        The parent widget.
    view_size : tuple[int, int]
        The minimum size of the QGraphicsView in pixel. By default (300, 300).
    data : WellViewData
        The data to use to initialize the view. By default:
        WellViewData(
            well_size=(None, None),
            circular=False,
            padding=0,
            show_fovs_order=True,
            mode=None,
        )
    """

    pointsWarning: Signal = Signal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
        view_size: tuple[int, int] = DEFAULT_VIEW_SIZE,
        data: _WellViewData = DEFAULT_WELL_DATA,
    ) -> None:
        self._scene = QGraphicsScene()
        super().__init__(self._scene, parent)

        self.setStyleSheet("background:grey; border-radius: 5px;")

        self._size_x, self._size_y = view_size
        self.setMinimumSize(self._size_x, self._size_y)

        # set the scene rect so that the center is (0, 0)
        self.setSceneRect(
            -self._size_x / 2, -self._size_x / 2, self._size_x, self._size_y
        )

        self.setValue(data)

    # _________________________PUBLIC METHODS_________________________ #

    def setMode(self, mode: Center | GridRowsColumns | RandomPoints | None) -> None:
        """Set the mode to use to draw the FOVs."""
        self._mode = mode
        self._fov_width = mode.fov_width if mode else None
        self._fov_height = mode.fov_height if mode else None

        # convert size in scene pixel
        self._fov_width_px = (
            (self._size_x * self._fov_width) / self._well_width
            if self._fov_width and self._well_width
            else None
        )
        self._fov_height_px = (
            (self._size_y * self._fov_height) / self._well_height
            if self._fov_height and self._well_height
            else None
        )
        self._update_scene(self._mode)

    def mode(self) -> Center | GridRowsColumns | RandomPoints | None:
        """Return the mode to use to draw the FOVs."""
        return self._mode

    def setWellSize(self, size: tuple[float | None, float | None]) -> None:
        """Set the well size width and height in mm."""
        self._well_width, self._well_height = size

    def wellSize(self) -> tuple[float | None, float | None]:
        """Return the well size width and height in mm."""
        return self._well_width, self._well_height

    def setCircular(self, is_circular: bool) -> None:
        """Set True if the well is circular."""
        self._is_circular = is_circular
        # update the mode fov size if a mode is set
        if self._mode is not None and isinstance(self._mode, RandomPoints):
            self._mode = self._mode.replace(shape=ELLIPSE if is_circular else RECT)

    def isCircular(self) -> bool:
        """Return True if the well is circular."""
        return self._is_circular

    def setPadding(self, padding: int) -> None:
        """Set the padding in pixel between the well and the view."""
        self._padding = padding

    def padding(self) -> int:
        """Return the padding in pixel between the well and the view."""
        return self._padding

    def showFovOrder(self, show: bool) -> None:
        """Show the FOVs order in the scene by drawing lines connecting the FOVs."""
        self._show_fovs_order = show

    def fovsOrder(self) -> bool:
        """Return True if the FOVs order is shown."""
        return self._show_fovs_order

    def clear(self, *item_types: Any) -> None:
        """Remove all items of `item_types` from the scene."""
        if not item_types:
            self._scene.clear()
            self._mode = None
        for item in self._scene.items():
            if not item_types or isinstance(item, item_types):
                self._scene.removeItem(item)
        self._scene.update()

    def refresh(self) -> None:
        """Refresh the scene."""
        self._scene.clear()
        self._draw_well_area()
        if self._mode is not None:
            self._update_scene(self._mode)

    def value(self) -> _WellViewData:
        """Return the value of the scene."""
        return _WellViewData(
            well_size=(self._well_width, self._well_height),
            circular=self._is_circular,
            padding=self._padding,
            show_fovs_order=self._show_fovs_order,
            mode=self._mode,
        )

    def setValue(self, value: _WellViewData) -> None:
        """Set the value of the scene."""
        self.clear()

        self.setWellSize(value.well_size)
        self.setCircular(value.circular)
        self.setPadding(value.padding)
        self.showFovOrder(value.show_fovs_order)
        self.setMode(value.mode)

        if self._well_width is None or self._well_height is None:
            self.clear()
            return

        self._draw_well_area()
        self._update_scene(self._mode)

    # _________________________PRIVATE METHODS_________________________ #

    def _get_reference_well_area(self) -> QRectF | None:
        """Return the well area in scene pixel as QRectF."""
        if self._well_width is None or self._well_height is None:
            return None

        well_aspect = self._well_width / self._well_height
        well_size_px = self._size_x - self._padding
        size_x = size_y = well_size_px
        # keep the ratio between well_size_x and well_size_y
        if well_aspect > 1:
            size_y = int(well_size_px * 1 / well_aspect)
        elif well_aspect < 1:
            size_x = int(well_size_px * well_aspect)
        # set the position of the well plate in the scene using the center of the view
        # QRectF as reference
        x = self.sceneRect().center().x() - (size_x / 2)
        y = self.sceneRect().center().y() - (size_y / 2)
        w = size_x
        h = size_y

        return QRectF(x, y, w, h)

    def _draw_well_area(self) -> None:
        """Draw the well area in the scene."""
        if self._well_width is None or self._well_height is None:
            self.clear()
            return

        ref = self._get_reference_well_area()
        if ref is None:
            return

        if self._is_circular:
            self._scene.addEllipse(ref, pen=PEN_AREA)
        else:
            self._scene.addRect(ref, pen=PEN_AREA)

    def _update_scene(
        self, value: Center | GridRowsColumns | RandomPoints | None
    ) -> None:
        """Update the scene with the given mode."""
        if value is None:
            self.clear(_WellAreaGraphicsItem, _FOVGraphicsItem)
            return

        if isinstance(value, Center):
            self._update_center_fov(value)
        elif isinstance(value, RandomPoints):
            self._update_random_fovs(value)
        elif isinstance(value, (GridRowsColumns)):
            self._update_grid_fovs(value)
        else:
            raise ValueError(f"Invalid value: {value}")

    def _update_center_fov(self, value: Center) -> None:
        """Update the scene with the center point."""
        points = [FOV(value.x or 0.0, value.y or 0.0, self.sceneRect())]
        self._draw_fovs(points)

    def _update_random_fovs(self, value: RandomPoints) -> None:
        """Update the scene with the random points."""
        self.clear(_WellAreaGraphicsItem, QGraphicsEllipseItem, QGraphicsRectItem)

        if isinstance(value, RandomPoints):
            self._is_circular = value.shape == ELLIPSE

        # get the well area in scene pixel
        ref_area = self._get_reference_well_area()

        if ref_area is None or self._well_width is None or self._well_height is None:
            return

        well_area_x_px = ref_area.width() * value.max_width / self._well_width
        well_area_y_px = ref_area.height() * value.max_height / self._well_height

        # calculate the starting point of the well area
        x = ref_area.center().x() - (well_area_x_px / 2)
        y = ref_area.center().y() - (well_area_y_px / 2)

        rect = QRectF(x, y, well_area_x_px, well_area_y_px)
        area = _WellAreaGraphicsItem(rect, self._is_circular, PEN_WIDTH)

        # draw well and well area
        self._draw_well_area()
        self._scene.addItem(area)

        val = value.replace(
            max_width=area.boundingRect().width(),
            max_height=area.boundingRect().height(),
            fov_width=self._fov_width_px,
            fov_height=self._fov_height_px,
        )
        # get the random points list

        points = self._get_random_points(val, area.boundingRect())
        # draw the random points
        self._draw_fovs(points)

    def _get_random_points(self, points: RandomPoints, area: QRectF) -> list[FOV]:
        """Create the points for the random scene."""
        # catch the warning raised by the RandomPoints class if the max number of
        # iterations is reached.
        with warnings.catch_warnings(record=True) as w:
            # note: inverting the y axis because in scene, y up is negative and y down
            # is positive.
            pos = [
                RelativePosition(x=point.x, y=point.y * (-1), name=point.name)  # type: ignore
                for point in points
            ]
            if len(pos) != points.num_points:
                self.pointsWarning.emit(len(pos))

        if len(w):
            warnings.warn(w[0].message, w[0].category, stacklevel=2)

        top_x, top_y = area.topLeft().x(), area.topLeft().y()
        return [FOV(p.x, p.y, area) for p in nearest_neighbor(pos, top_x, top_y)]

    def _update_grid_fovs(self, value: GridRowsColumns) -> None:
        """Update the scene with the grid points."""
        val = value.replace(fov_width=self._fov_width_px, fov_height=self._fov_width_px)

        # x and y center coords of the scene in px
        x, y = (
            self._scene.sceneRect().center().x(),
            self._scene.sceneRect().center().y(),
        )
        rect = self._get_reference_well_area()

        if rect is None:
            return
        # create a list of FOV points by shifting the grid by the center coords.
        # note: inverting the y axis because in scene, y up is negative and y down is
        # positive.
        points = [FOV(g.x + x, (g.y - y) * (-1), rect) for g in val]
        self._draw_fovs(points)

    def _draw_fovs(self, points: list[FOV]) -> None:
        """Draw the fovs in the scene as `_FOVPoints.

        If 'showFOVsOrder' is True, the FOVs will be connected by black lines to
        represent the order of acquisition. In addition, the first FOV will be drawn
        with a black color, the others with a white color.
        """
        if not self._fov_width_px or not self._fov_height_px:
            return

        def _get_pen(index: int) -> QPen:
            """Return the pen to use for the fovs."""
            pen = (
                QPen(Qt.GlobalColor.black)
                if index == 0 and len(points) > 1
                else QPen(Qt.GlobalColor.white)
            )
            pen.setWidth(3)
            return pen

        self.clear(_FOVGraphicsItem, QGraphicsLineItem)

        line_pen = QPen(Qt.GlobalColor.black)
        line_pen.setWidth(2)

        x = y = None
        for index, fov in enumerate(points):
            fovs = _FOVGraphicsItem(
                fov.x,
                fov.y,
                self._fov_width_px,
                self._fov_height_px,
                fov.bounding_rect,
                (
                    _get_pen(index)
                    if self._show_fovs_order
                    else QPen(Qt.GlobalColor.white)
                ),
            )

            self._scene.addItem(fovs)
            # draw the lines connecting the fovs
            if x is not None and y is not None and self._show_fovs_order:
                self._scene.addLine(x, y, fov.x, fov.y, pen=line_pen)
            x, y = (fov.x, fov.y)
