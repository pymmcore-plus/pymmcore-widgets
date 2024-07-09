from __future__ import annotations

from itertools import product
from typing import TYPE_CHECKING

from qtpy.QtCore import QRectF, Qt
from qtpy.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)
from useq import WellPlate

from ._graphics_items import _WellGraphicsItem

if TYPE_CHECKING:
    from qtpy.QtGui import QBrush, QPen

    from ._graphics_items import Well


from typing import TYPE_CHECKING, NamedTuple

from qtpy.QtCore import Signal
from qtpy.QtGui import QBrush, QPen
from qtpy.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ._plate_graphics_scene import _PlateGraphicsScene
from ._util import PLATES, _ResizingGraphicsView

if TYPE_CHECKING:
    from useq import WellPlate

    from ._graphics_items import Well

PLATE_GRAPHICS_VIEW_HEIGHT = 440
BRUSH = QBrush(Qt.GlobalColor.lightGray)
PEN = QPen(Qt.GlobalColor.black)
PEN.setWidth(1)


class PlateInfo(NamedTuple):
    """Information about a well plate.

    Attributes
    ----------
    plate : WellPlate
        The well plate object.
    wells : list[WellInfo]
        The list of selected wells in the well plate.
    """

    plate: WellPlate
    wells: list[Well]


class _PlateSelectorWidget(QWidget):
    """Widget for selecting the well plate and its wells.

    Parameters
    ----------
    parent : QWidget, optional
        The parent widget, by default None
    """

    valueChanged = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # well plate combobox
        combo_label = QLabel("WellPlate:")
        self.plate_combo = QComboBox()
        self.plate_combo.addItems(list(PLATES))

        # clear selection button
        self._clear_button = QPushButton(text="Clear Selection")
        self._clear_button.setAutoDefault(False)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(5)
        top_layout.addWidget(combo_label, 0)
        top_layout.addWidget(self.plate_combo, 1)
        top_layout.addWidget(self._clear_button, 0)

        self.scene = _PlateGraphicsScene(parent=self)
        self.view = _ResizingGraphicsView(self.scene, self)
        self.view.setStyleSheet("background:grey; border-radius: 5px;")
        self.view.setMinimumHeight(PLATE_GRAPHICS_VIEW_HEIGHT)
        self.view.setMinimumWidth(int(PLATE_GRAPHICS_VIEW_HEIGHT * 1.5))

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.view)

        # connect
        self.scene.valueChanged.connect(self._on_value_changed)
        self._clear_button.clicked.connect(self.scene._clear_selection)
        self.plate_combo.currentTextChanged.connect(self._draw_plate)

        self._draw_plate(self.plate_combo.currentText())

    # _________________________PUBLIC METHODS_________________________ #

    def value(self) -> PlateInfo:
        """Return current plate and selected wells as a list of (name, row, column)."""
        curr_plate_name = self.plate_combo.currentText()
        curr_plate = PLATES[curr_plate_name]
        return PlateInfo(curr_plate, self.scene.value())

    def setValue(self, value: PlateInfo) -> None:
        """Set the current plate and the selected wells.

        Parameters
        ----------
        value : PlateInfo
            The plate information to set containing the plate and the selected wells
            as a list of (name, row, column).
        """
        if not value.plate:
            return

        if not value.plate.name:
            raise ValueError("Plate name is required.")

        if value.plate.name not in PLATES:
            raise ValueError(f"'{value.plate.name}' not in the database.")

        self.plate_combo.setCurrentText(value.plate.name)

        if not value.wells:
            return

        self.scene.setValue(value.wells)

    # _________________________PRIVATE METHODS________________________ #

    def _on_value_changed(self) -> None:
        """Emit the valueChanged signal when the value changes."""
        # not using lambda or tests will fail
        self.valueChanged.emit(self.value())

    def _draw_plate(self, plate_name: str) -> None:
        if not plate_name:
            return

        draw_plate(self.view, self.scene, PLATES[plate_name], brush=BRUSH, pen=PEN)
        self.valueChanged.emit(self.value())


# not making a _PlateSelectorWidget or _PlateGraphicsScene because I will use it for
# the database widget as well
def draw_plate(
    view: QGraphicsView,
    scene: QGraphicsScene,
    plate: WellPlate,
    brush: QBrush | None,
    pen: QPen | None,
    opacity: float = 1.0,
    text: bool = True,
) -> None:
    """Draw all wells of the plate in a QGraphicsScene."""
    # setting a custom well size in scene px. Using 10 times the well size in mm
    # gives a good resolution in the viewer.
    well_size_x, well_size_y = plate.well_size
    well_spacing_x, well_spacing_y = plate.well_spacing

    scene.clear()

    if not well_size_x or not well_size_y:
        return

    well_scene_size = well_size_x * 10

    # calculate the width and height of the well in scene px
    if well_size_x == well_size_y:
        well_width = well_height = well_scene_size
    elif well_size_x > well_size_y:
        well_width = well_scene_size
        # keep the ratio between well_size_x and well_size_y
        well_height = int(well_scene_size * well_size_y / well_size_x)
    else:
        # keep the ratio between well_size_x and well_size_y
        well_width = int(well_scene_size * well_size_x / well_size_y)
        well_height = well_scene_size

    # calculate the spacing between wells
    dx = well_spacing_x - well_size_x if well_spacing_x else 0
    dy = well_spacing_y - well_size_y if well_spacing_y else 0

    # convert the spacing between wells in pixels
    dx_px = dx * well_width / well_size_x if well_spacing_x else 0
    dy_px = dy * well_height / well_size_y if well_spacing_y else 0

    # the text size is the well_height of the well divided by 3
    text_size = well_height / 3 if text else None

    # draw the wells and place them in their correct row/column position
    for row, col in product(range(plate.rows), range(plate.columns)):
        _x = (well_width * col) + (dx_px * col)
        _y = (well_height * row) + (dy_px * row)
        rect = QRectF(_x, _y, well_width, well_height)
        w = _WellGraphicsItem(rect, row, col, plate.circular_wells, text_size)
        w.brush = brush
        w.pen = pen
        w.setOpacity(opacity)
        scene.addItem(w)

    # set the scene size
    plate_width = (well_width * plate.columns) + (dx_px * (plate.columns - 1))
    plate_height = (well_height * plate.rows) + (dy_px * (plate.rows - 1))

    # add some offset to the scene rect to leave some space around the plate
    offset = 20
    scene.setSceneRect(
        -offset, -offset, plate_width + (offset * 2), plate_height + (offset * 2)
    )

    # fit scene in view
    view.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
