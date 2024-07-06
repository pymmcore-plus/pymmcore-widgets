from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
from qtpy.QtCore import QRectF, Qt, Signal
from qtpy.QtGui import QColor, QPen
from qtpy.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGroupBox,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from useq import GridRowsColumns, Position, RandomPoints, RelativePosition
from useq._grid import OrderMode, Shape

from pymmcore_widgets.hcs._graphics_items import (
    FOV,
    GREEN,
    _FOVGraphicsItem,
    _WellAreaGraphicsItem,
)
from pymmcore_widgets.hcs._util import _ResizingGraphicsView, nearest_neighbor

from ._util import create_label, make_wdg_with_label

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


class _CenterFOVWidget(QWidget):
    """Widget to select the center of a specifiied area."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._x: float = 0.0
        self._y: float = 0.0

        self._fov_size: tuple[float | None, float | None] = (None, None)

        lbl = QLabel(text="Center of the Well.")
        lbl.setStyleSheet("font-weight: bold;")
        lbl.setAlignment(AlignCenter)

        # add widgets layout
        self.wdg = QGroupBox()
        layout = QVBoxLayout(self.wdg)
        layout.setSpacing(0)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(lbl)

        # main
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.wdg)

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


class _RandomFOVWidget(QWidget):
    """Widget to generate random points within a specified area."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # setting a random seed for point generation reproducibility
        self._random_seed: int | None = int(
            np.random.randint(0, 2**32 - 1, dtype=np.uint32)
        )
        self._is_circular: bool = False
        self._fov_size: tuple[float | None, float | None] = (None, None)

        # well area doublespinbox along x
        self._area_x = QDoubleSpinBox()
        self._area_x.setAlignment(AlignCenter)
        self._area_x.setMinimum(0.0)
        self._area_x.setMaximum(1000000)
        self._area_x.setSingleStep(100)
        area_label_x = create_label("Area x (µm):")
        area_x = make_wdg_with_label(area_label_x, self._area_x)

        # well area doublespinbox along y
        self._area_y = QDoubleSpinBox()
        self._area_y.setAlignment(AlignCenter)
        self._area_y.setMinimum(0.0)
        self._area_y.setMaximum(1000000)
        self._area_y.setSingleStep(100)
        area_label_y = create_label("Area y (µm):")
        area_y = make_wdg_with_label(area_label_y, self._area_y)

        # number of FOVs spinbox
        self._number_of_points = QSpinBox()
        self._number_of_points.setAlignment(AlignCenter)
        self._number_of_points.setMinimum(1)
        self._number_of_points.setMaximum(1000)
        number_of_points_label = create_label("Points:")
        n_of_points = make_wdg_with_label(
            number_of_points_label, self._number_of_points
        )

        self._random_button = QPushButton(text="Generate Random Points")

        # add widgets to wdg layout
        title = QLabel(text="Random Fields of Views.")
        title.setStyleSheet("font-weight: bold;")
        title.setAlignment(AlignCenter)

        self._wdg = QGroupBox()
        layout = QVBoxLayout(self._wdg)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(title)
        layout.addItem(QSpacerItem(0, 10, *FIXED_POLICY))
        layout.addWidget(area_x)
        layout.addWidget(area_y)
        layout.addWidget(n_of_points)
        layout.addWidget(self._random_button)

        # set labels sizes
        for lbl in (area_label_x, area_label_y, number_of_points_label):
            lbl.setMinimumWidth(area_label_x.sizeHint().width())

        # main
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._wdg)

        # connect
        self._area_x.valueChanged.connect(self._on_value_changed)
        self._area_y.valueChanged.connect(self._on_value_changed)
        self._number_of_points.valueChanged.connect(self._on_value_changed)
        self._random_button.clicked.connect(self._on_random_clicked)

    @property
    def is_circular(self) -> bool:
        """Return True if the well is circular."""
        return self._is_circular

    @is_circular.setter
    def is_circular(self, circular: bool) -> None:
        """Set True if the well is circular."""
        self._is_circular = circular

    @property
    def fov_size(self) -> tuple[float | None, float | None]:
        """Return the FOV size."""
        return self._fov_size

    @fov_size.setter
    def fov_size(self, size: tuple[float | None, float | None]) -> None:
        """Set the FOV size."""
        self._fov_size = size

    @property
    def random_seed(self) -> int | None:
        """Return the random seed."""
        return self._random_seed

    @random_seed.setter
    def random_seed(self, seed: int) -> None:
        """Set the random seed."""
        self._random_seed = seed

    def _on_value_changed(self) -> None:
        """Emit the valueChanged signal."""
        self.valueChanged.emit(self.value())

    def _on_random_clicked(self) -> None:
        """Emit the valueChanged signal."""
        # reset the random seed
        self.random_seed = int(np.random.randint(0, 2**32 - 1, dtype=np.uint32))
        self.valueChanged.emit(self.value())

    def value(self) -> RandomPoints:
        """Return the values of the widgets."""
        fov_x, fov_y = self._fov_size
        return RandomPoints(
            num_points=self._number_of_points.value(),
            shape=ELLIPSE if self._is_circular else RECT,
            random_seed=self.random_seed,
            max_width=self._area_x.value(),
            max_height=self._area_y.value(),
            allow_overlap=False,
            fov_width=fov_x,
            fov_height=fov_y,
        )

    def setValue(self, value: RandomPoints) -> None:
        """Set the values of the widgets."""
        self.is_circular = value.shape == ELLIPSE
        self.random_seed = (
            value.random_seed
            if value.random_seed is not None
            else int(np.random.randint(0, 2**32 - 1, dtype=np.uint32))
        )
        self._number_of_points.setValue(value.num_points)
        self._area_x.setMaximum(value.max_width)
        self._area_x.setValue(value.max_width)
        self._area_y.setMaximum(value.max_height)
        self._area_y.setValue(value.max_height)
        self._fov_size = (value.fov_width, value.fov_height)

    def reset(self) -> None:
        """Reset the values of the widgets."""
        self._number_of_points.setValue(1)
        self._area_x.setValue(0)
        self._area_y.setValue(0)
        self._fov_size = (None, None)
        self.is_circular = False


class _GridFovWidget(QWidget):
    """Widget to generate a grid of FOVs within a specified area."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._fov_size: tuple[float | None, float | None] = (None, None)

        self._rows = QSpinBox()
        self._rows.setAlignment(AlignCenter)
        self._rows.setMinimum(1)
        rows_lbl = create_label("Rows:")
        rows = make_wdg_with_label(rows_lbl, self._rows)
        self._rows.valueChanged.connect(self._on_value_changed)

        self._cols = QSpinBox()
        self._cols.setAlignment(AlignCenter)
        self._cols.setMinimum(1)
        cols_lbl = create_label("Columns:")
        cols = make_wdg_with_label(cols_lbl, self._cols)
        self._cols.valueChanged.connect(self._on_value_changed)

        self._overlap_x = QDoubleSpinBox()
        self._overlap_x.setAlignment(AlignCenter)
        self._overlap_x.setMinimum(-10000)
        self._overlap_x.setMaximum(100)
        self._overlap_x.setSingleStep(1.0)
        self._overlap_x.setValue(0)
        overlap_x_lbl = create_label("Overlap x (%):")
        overlap_x = make_wdg_with_label(overlap_x_lbl, self._overlap_x)
        self._overlap_x.valueChanged.connect(self._on_value_changed)

        self._overlap_y = QDoubleSpinBox()
        self._overlap_y.setAlignment(AlignCenter)
        self._overlap_y.setMinimum(-10000)
        self._overlap_y.setMaximum(100)
        self._overlap_y.setSingleStep(1.0)
        self._overlap_y.setValue(0)
        spacing_y_lbl = create_label("Overlap y (%):")
        overlap_y = make_wdg_with_label(spacing_y_lbl, self._overlap_y)
        self._overlap_y.valueChanged.connect(self._on_value_changed)

        self._order_combo = QComboBox()
        self._order_combo.addItems([mode.value for mode in OrderMode])
        self._order_combo.setCurrentText(OrderMode.row_wise_snake.value)
        order_combo_lbl = create_label("Grid Order:")
        order_combo = make_wdg_with_label(order_combo_lbl, self._order_combo)
        self._order_combo.currentTextChanged.connect(self._on_value_changed)

        # add widgets to wdg layout
        self._wdg = QGroupBox()
        layout = QVBoxLayout(self._wdg)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        title = QLabel(text="Fields of Views in a Grid.")
        title.setStyleSheet("font-weight: bold;")
        title.setAlignment(AlignCenter)
        layout.addWidget(title)
        layout.addItem(QSpacerItem(0, 10, *FIXED_POLICY))
        layout.addWidget(rows)
        layout.addWidget(cols)
        layout.addWidget(overlap_x)
        layout.addWidget(overlap_y)
        layout.addWidget(order_combo)

        # set labels sizes
        for lbl in (
            rows_lbl,
            cols_lbl,
            overlap_x_lbl,
            spacing_y_lbl,
            order_combo_lbl,
        ):
            lbl.setMinimumWidth(overlap_x_lbl.sizeHint().width())

        # main
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._wdg)

    @property
    def fov_size(self) -> tuple[float | None, float | None]:
        """Return the FOV size."""
        return self._fov_size

    @fov_size.setter
    def fov_size(self, size: tuple[float | None, float | None]) -> None:
        """Set the FOV size."""
        self._fov_size = size

    def _on_value_changed(self) -> None:
        """Emit the valueChanged signal."""
        self.valueChanged.emit(self.value())

    def value(self) -> GridRowsColumns:
        """Return the values of the widgets."""
        fov_x, fov_y = self._fov_size
        return GridRowsColumns(
            rows=self._rows.value(),
            columns=self._cols.value(),
            overlap=(self._overlap_x.value(), self._overlap_y.value()),
            mode=self._order_combo.currentText(),
            fov_width=fov_x,
            fov_height=fov_y,
        )

    def setValue(self, value: GridRowsColumns) -> None:
        """Set the values of the widgets."""
        self._rows.setValue(value.rows)
        self._cols.setValue(value.columns)
        self._overlap_x.setValue(value.overlap[0])
        self._overlap_y.setValue(value.overlap[1])
        self._order_combo.setCurrentText(value.mode.value)
        self.fov_size = (value.fov_width, value.fov_height)

    def reset(self) -> None:
        """Reset the values of the widgets."""
        self._rows.setValue(1)
        self._cols.setValue(1)
        self._overlap_x.setValue(0)
        self._overlap_y.setValue(0)
        self._fov_size = (None, None)


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
