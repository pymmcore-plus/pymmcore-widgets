from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QBrush, QPen
from qtpy.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ._plate_graphics_scene import _PlateGraphicsScene
from ._util import (
    PLATES,
    _ResizingGraphicsView,
    draw_plate,
)

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


class PlateSelectorWidget(QWidget):
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
        combo_label = QLabel()
        combo_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        combo_label.setText("WellPlate:")
        self.plate_combo = QComboBox()
        self.plate_combo.addItems(list(PLATES))
        self.plate_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        wp_combo_wdg = QWidget()
        wp_combo_wdg_layout = QHBoxLayout(wp_combo_wdg)
        wp_combo_wdg_layout.setContentsMargins(0, 0, 0, 0)
        wp_combo_wdg_layout.setSpacing(5)
        wp_combo_wdg_layout.addWidget(combo_label)
        wp_combo_wdg_layout.addWidget(self.plate_combo)

        # clear selection button
        self._clear_button = QPushButton(text="Clear Selection")
        self._clear_button.setAutoDefault(False)
        self._clear_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        btns_wdg = QWidget()
        btns_wdg_layout = QHBoxLayout(btns_wdg)
        btns_wdg_layout.setContentsMargins(0, 0, 0, 0)
        btns_wdg_layout.setSpacing(5)
        btns_wdg_layout.addWidget(self._clear_button)

        top_wdg = QWidget()
        top_wdg_layout = QHBoxLayout(top_wdg)
        top_wdg_layout.setContentsMargins(0, 0, 0, 0)
        top_wdg_layout.setSpacing(5)
        top_wdg_layout.addWidget(wp_combo_wdg)
        top_wdg_layout.addWidget(btns_wdg)

        self.scene = _PlateGraphicsScene(parent=self)
        self.view = _ResizingGraphicsView(self.scene, self)
        self.view.setStyleSheet("background:grey; border-radius: 5px;")
        self.view.setMinimumHeight(PLATE_GRAPHICS_VIEW_HEIGHT)
        self.view.setMinimumWidth(int(PLATE_GRAPHICS_VIEW_HEIGHT * 1.5))

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(top_wdg)
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
