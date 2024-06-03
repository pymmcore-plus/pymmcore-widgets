from __future__ import annotations

import string
from typing import TYPE_CHECKING, NamedTuple

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QBrush, QPen
from qtpy.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

from ._plate_database_widget import PlateDatabaseWidget
from ._plate_graphics_scene import _HCSGraphicsScene
from ._plate_model import DEFAULT_PLATE_DB_PATH, load_database, save_database
from ._util import _ResizingGraphicsView, draw_plate

if TYPE_CHECKING:
    from pathlib import Path

    from ._graphics_items import Well
    from ._plate_model import Plate

AlignCenter = Qt.AlignmentFlag.AlignCenter

ALPHABET = string.ascii_uppercase
PLATE_GRAPHICS_VIEW_HEIGHT = 440
BRUSH = QBrush(Qt.GlobalColor.lightGray)
PEN = QPen(Qt.GlobalColor.black)
PEN.setWidth(1)


class PlateInfo(NamedTuple):
    """Information about a well plate.

    Attributes
    ----------
    plate : Plate
        The well plate object.
    wells : list[WellInfo] | None
        The list of selected wells in the well plate.
    """

    plate: Plate | None
    wells: list[Well] | None


class PlateSelectorWidget(QWidget):
    """Widget for selecting the well plate and its wells."""

    valueChanged = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        plate_database_path: Path | str = DEFAULT_PLATE_DB_PATH,
    ) -> None:
        super().__init__(parent)

        self._plate_db_path = plate_database_path
        self._plate_db = load_database(self._plate_db_path)

        # well plate combobox
        combo_label = QLabel()
        combo_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        combo_label.setText("Plate:")
        self.plate_combo = QComboBox()
        self.plate_combo.addItems(list(self._plate_db))
        wp_combo_wdg = QWidget()
        wp_combo_wdg.setLayout(QHBoxLayout())
        wp_combo_wdg.layout().setContentsMargins(0, 0, 0, 0)
        wp_combo_wdg.layout().setSpacing(5)
        wp_combo_wdg.layout().addWidget(combo_label)
        wp_combo_wdg.layout().addWidget(self.plate_combo)

        # clear and custom plate buttons
        self._custom_plate_button = QPushButton(text="Custom Plate")
        self._custom_plate_button.setAutoDefault(False)
        self._clear_button = QPushButton(text="Clear Selection")
        self._clear_button.setAutoDefault(False)
        self._load_plate_db_button = QPushButton(text="Load Plate Database")
        self._load_plate_db_button.setAutoDefault(False)
        btns_wdg = QWidget()
        btns_wdg.setLayout(QHBoxLayout())
        btns_wdg.layout().setContentsMargins(0, 0, 0, 0)
        btns_wdg.layout().setSpacing(5)
        btns_wdg.layout().addWidget(self._clear_button)
        btns_wdg.layout().addWidget(self._custom_plate_button)
        btns_wdg.layout().addWidget(self._load_plate_db_button)

        top_wdg = QWidget()
        top_wdg.setLayout(QHBoxLayout())
        top_wdg.layout().setContentsMargins(0, 0, 0, 0)
        top_wdg.layout().setSpacing(5)
        top_wdg.layout().addWidget(wp_combo_wdg)
        top_wdg.layout().addWidget(btns_wdg)

        self.scene = _HCSGraphicsScene(parent=self)
        self.view = _ResizingGraphicsView(self.scene, self)
        self.view.setStyleSheet("background:grey; border-radius: 5px;")
        self.view.setMinimumHeight(PLATE_GRAPHICS_VIEW_HEIGHT)
        self.view.setMinimumWidth(int(PLATE_GRAPHICS_VIEW_HEIGHT * 1.5))

        self.setLayout(QVBoxLayout())
        self.layout().setSpacing(15)
        self.layout().setContentsMargins(10, 10, 10, 10)
        self.layout().addWidget(top_wdg)
        self.layout().addWidget(self.view)

        self._plate_db_wdg = PlateDatabaseWidget(
            parent=self,
            plate_database_path=self._plate_db_path,
        )

        # connect
        self.scene.valueChanged.connect(self.valueChanged)
        self._clear_button.clicked.connect(self.scene._clear_selection)
        self.plate_combo.currentTextChanged.connect(self._draw_plate)
        self._custom_plate_button.clicked.connect(self._show_database_wdg)
        self._plate_db_wdg.valueChanged.connect(self._update_wdg)
        self._load_plate_db_button.clicked.connect(self._load_plate_database)

        self._draw_plate(self.plate_combo.currentText())

    # _________________________PUBLIC METHODS_________________________ #

    def value(self) -> PlateInfo:
        """Return current plate and selected wells as a list of (name, row, column)."""
        curr_plate_name = self.plate_combo.currentText()
        curr_plate = self._plate_db[curr_plate_name] if curr_plate_name else None
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

        if value.plate.id not in self._plate_db:
            raise ValueError(f"'{value.plate.id}' not in the database.")

        self.plate_combo.setCurrentText(value.plate.id)

        if not value.wells:
            return

        self.scene.setValue(value.wells)

    def save_database(self, plate_database_path: Path | str) -> None:
        """Save the current plate database to a json file.

        Parameters
        ----------
        plate_database_path : Path | str
            The path to save the plate database.
        """
        save_database(self._plate_db, plate_database_path)

    def load_database(self, plate_database_path: Path | str | None = None) -> None:
        """Load a plate database.

        Parameters
        ----------
        plate_database_path : Path | str | None
            The path to the plate database. If None, a dialog will open to select a
            plate database. By default, None.
        """
        if not plate_database_path:
            (plate_database_path, _) = QFileDialog.getOpenFileName(
                self, "Select a Plate Database", "", "json(*.json)"
            )

        if not plate_database_path:
            return

        # update the plate database
        self._plate_db_path = plate_database_path
        self._plate_db = load_database(self._plate_db_path)

        # update the well plate combobox
        self.plate_combo.clear()
        if plates := list(self._plate_db):
            self.plate_combo.addItems(plates)
        else:
            self.scene.clear()

        # update the custom plate widget
        self._plate_db_wdg.load_database(self._plate_db_path)

    def database_path(self) -> str:
        """Return the path to the current plate database."""
        return str(self._plate_db_path)

    def database(self) -> dict[str, Plate]:
        """Return the current plate database."""
        return self._plate_db

    # _________________________PRIVATE METHODS________________________ #

    def _draw_plate(self, plate_name: str) -> None:
        if not plate_name:
            return

        draw_plate(
            self.view, self.scene, self._plate_db[plate_name], brush=BRUSH, pen=PEN
        )
        self.valueChanged.emit()

    def _show_database_wdg(self) -> None:
        """Show the database plate widget widget."""
        if self._plate_db_wdg.isVisible():
            self._plate_db_wdg.raise_()
        else:
            self._plate_db_wdg.show()
            self._plate_db_wdg.plate_table.clearSelection()
            self._plate_db_wdg.reset()

    def _update_wdg(
        self,
        new_plate: Plate | None,
        plate_db: dict[str, Plate],
        plate_db_path: Path | str,
    ) -> None:
        """Update the widget with the updated plate database."""
        # if a new plate database is loaded in the custom plate widget, update this
        # widget as well with the new plate database
        if plate_db != self._plate_db:
            self.load_database(plate_db_path)
            return

        # if a new plate is created in the custom plate widget, add it to the
        # plate_combo and set it as the current plate
        with signals_blocked(self.plate_combo):
            self.plate_combo.clear()
        self.plate_combo.addItems(list(self._plate_db))
        if new_plate:
            self.plate_combo.setCurrentText(new_plate.id)  # trigger _draw_plate

    def _load_plate_database(self) -> None:
        """Load a new plate database."""
        (plate_database_path, _) = QFileDialog.getOpenFileName(
            self, "Select a Plate Database", "", "json(*.json)"
        )

        if not plate_database_path:
            return

        self.load_database(plate_database_path)
