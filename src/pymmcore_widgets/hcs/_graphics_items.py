from __future__ import annotations

from typing import Any, NamedTuple

from qtpy.QtCore import QRectF, Qt
from qtpy.QtGui import QBrush, QColor, QFont, QPainter, QPen, QTextOption
from qtpy.QtWidgets import QGraphicsItem
from useq._base_model import FrozenModel

GREEN = "#00FF00"  # "#00C600"
RED = "#C33"  # "#FF00FF"

POINT_SIZE = 3
DEFAULT_PEN = QPen(Qt.GlobalColor.white)
DEFAULT_PEN.setWidth(3)
DEFAULT_BRUSH = QBrush(Qt.GlobalColor.white)


class Well(FrozenModel):
    """Store well name, row and column.

    Attributes
    ----------
    name : str
        Well name.
    row : int
        Well row.
    column : int
        Well column.
    """

    name: str
    row: int
    column: int


class FOV(NamedTuple):
    """FOV x and y coordinates.

    Attributes
    ----------
    x : float
        FOV x coordinate.
    y : float
        FOV y coordinate.
    bounding_rect : QRectF
        Bounding rectangle delimiting the well area.
    """

    x: float
    y: float
    bounding_rect: QRectF


class _WellGraphicsItem(QGraphicsItem):
    """QGraphicsItem to draw a well of a plate."""

    def __init__(
        self,
        rect: QRectF,
        row: int,
        col: int,
        circular: bool,
        text_size: float | None,
        brush: QBrush | None = None,
        pen: QPen | None = None,
    ) -> None:
        super().__init__()

        self._row = row
        self._col = col
        self._text_size = text_size
        self._circular = circular

        self._brush = brush or QBrush(QColor(GREEN))

        default_pen = QPen(Qt.GlobalColor.black)
        default_pen.setWidth(1)
        self._pen = pen or default_pen

        self._well_shape = rect

        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable, True)

    @property
    def brush(self) -> QBrush:
        return self._brush

    @brush.setter
    def brush(self, brush: QBrush | None) -> None:
        if brush is None:
            return
        self._brush = brush
        self.update()

    @property
    def pen(self) -> QPen:
        return self._pen

    @pen.setter
    def pen(self, pen: QPen | None) -> None:
        if pen is None:
            return
        self._pen = pen
        self.update()

    def boundingRect(self) -> QRectF:
        return self._well_shape

    def paint(self, painter: QPainter, *args: Any) -> None:
        painter.setBrush(self._brush)
        painter.setPen(self._pen)
        # draw a circular or rectangular well
        if self._circular:
            painter.drawEllipse(self._well_shape)
        else:
            painter.drawRect(self._well_shape)

        # write the well name
        if self._text_size is None:
            return
        painter.setPen(Qt.GlobalColor.black)
        painter.pen().setWidth(1)
        font = QFont("Helvetica", int(self._text_size))
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        well_name = f"{self._index_to_row_name(self._row)}{self._col + 1}"
        painter.drawText(
            self._well_shape, well_name, QTextOption(Qt.AlignmentFlag.AlignCenter)
        )

    def value(self) -> Well:
        """Return the well name, row and column in a tuple."""
        row = self._row
        col = self._col
        well = f"{self._index_to_row_name(self._row)}{self._col + 1}"
        return Well(name=well, row=row, column=col)

    def _index_to_row_name(self, index: int) -> str:
        """Convert a zero-based column index to row name (A, B, ..., Z, AA, AB, ...)."""
        name = ""
        while index >= 0:
            name = chr(index % 26 + 65) + name
            index = index // 26 - 1
        return name


class _WellAreaGraphicsItem(QGraphicsItem):
    """QGraphicsItem to draw the single well area for the _SelectFOV widget."""

    def __init__(self, rect: QRectF, circular: bool, pen_width: int) -> None:
        super().__init__()

        self._circular = circular
        self._pen_width = pen_width
        self._rect = rect

    def boundingRect(self) -> QRectF:
        return self._rect

    def paint(self, painter: QPainter, *args: Any) -> None:
        pen = QPen(QColor(GREEN))
        pen.setStyle(Qt.PenStyle.DotLine)
        pen.setWidth(self._pen_width)
        painter.setPen(pen)
        if self._circular:
            painter.drawEllipse(self._rect)
        else:
            painter.drawRect(self._rect)


class _FOVGraphicsItem(QGraphicsItem):
    """QGraphicsItem to draw the the positions of each FOV in the _SelectFOV widget.

    The FOV is drawn as a rectangle which represents the camera FOV.
    """

    def __init__(
        self,
        center_x: float,
        center_y: float,
        fov_width: float,
        fov_height: float,
        bounding_rect: QRectF,
        pen: QPen = DEFAULT_PEN,
    ) -> None:
        super().__init__()

        self._rect = bounding_rect

        # center of the FOV in scene px
        self._center_x = center_x
        self._center_y = center_y

        self.fov_width = fov_width or POINT_SIZE
        self.fov_height = fov_height or POINT_SIZE

        self._pen = pen

    def boundingRect(self) -> QRectF:
        return self._rect

    def paint(self, painter: QPainter, *args) -> None:  # type: ignore
        painter.setPen(self._pen)

        start_x = self._center_x - (self.fov_width / 2)
        start_y = self._center_y - (self.fov_height / 2)
        painter.drawRect(QRectF(start_x, start_y, self.fov_width, self.fov_height))

    def value(self) -> FOV:
        """Return the center of the FOV."""
        return FOV(self._center_x, self._center_y, self._rect)
