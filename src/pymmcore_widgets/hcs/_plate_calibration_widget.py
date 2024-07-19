from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon
from superqt.utils import signals_blocked

COMBO_ROLE = Qt.ItemDataRole.UserRole + 1
ICON_PATH = Path(__file__).parent / "icons"
ONE_CIRCLE = QIcon(str(ICON_PATH / "circle-center.svg"))
ONE_SQUARE = QIcon(str(ICON_PATH / "square-center.svg"))
TWO = QIcon(str(ICON_PATH / "square-vertices.svg"))
THREE = QIcon(str(ICON_PATH / "circle-edges.svg"))
FOUR = QIcon(str(ICON_PATH / "square-edges.svg"))
NON_CALIBRATED_ICON = MDI6.close_octagon_outline
CALIBRATED_ICON = MDI6.check_bold
ICON_SIZE = QSize(30, 30)
RED = Qt.GlobalColor.red
GREEN = Qt.GlobalColor.green


class Mode(NamedTuple):
    """Calibration mode."""

    text: str
    points: int
    icon: QIcon | None = None


class _CalibrationModeWidget(QWidget):
    """Widget to select the calibration mode."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._mode_combo = QComboBox()
        self._mode_combo.currentIndexChanged.connect(self._on_value_changed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(QLabel("Calibration mode:"), 0)
        layout.addWidget(self._mode_combo, 1)

    def _on_value_changed(self) -> None:
        """Emit the selected mode with valueChanged signal."""
        mode = self._mode_combo.itemData(self._mode_combo.currentIndex(), COMBO_ROLE)
        self.valueChanged.emit(mode)

    def setValue(self, modes: list[Mode] | None) -> None:
        """Set the available modes."""
        self._mode_combo.clear()
        if modes is None:
            return
        for idx, mode in enumerate(modes):
            self._mode_combo.addItem(mode.icon, mode.text)
            self._mode_combo.setItemData(idx, mode, COMBO_ROLE)

    def value(self) -> Mode:
        """Return the selected calibration mode."""
        mode = self._mode_combo.itemData(self._mode_combo.currentIndex(), COMBO_ROLE)
        return cast(Mode, mode)


class _CalibrationTable(QTableWidget):
    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self = QTableWidget()
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hdr = self.horizontalHeader()
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignHCenter)
        hdr.setSectionResizeMode(hdr.ResizeMode.Stretch)
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["X", "Y"])

    def _add_position(self) -> None:
        """Add a new position to the table."""
        self.insertRow(self.rowCount())
        x_item = QTableWidgetItem(str(self._mmc.getXPosition()))
        y_item = QTableWidgetItem(str(self._mmc.getYPosition()))
        x_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        y_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(self.rowCount() - 1, 0, x_item)
        self.setItem(self.rowCount() - 1, 1, y_item)

    def _remove_selected(self) -> None:
        """Remove the selected position from the table."""
        for item in reversed(self.selectedItems()):
            self.removeRow(item.row())


class WellCalibrationWidget(QWidget):
    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)
        self._mmc = mmcore or CMMCorePlus.instance()

        self.MODES: dict[bool, list[Mode]] = {
            True: [
                Mode("1 points at the center", 1, ONE_CIRCLE),
                Mode("3 points on the edges", 3, THREE),
            ],
            False: [
                Mode("1 points at the center", 1, ONE_SQUARE),
                Mode("2 points on opposite vertices", 2, TWO),
                Mode("4 points on 4 opposite edges", 4, FOUR),
            ],
        }

        # WIDGETS -------------------------------------------------------------

        # Well label and calibration icon
        self._well_label = QLabel("Well A1")
        self._well_label.setStyleSheet("font: bold 20px;")
        self._calibration_icon = QLabel()
        self._calibration_icon.setPixmap(
            icon(NON_CALIBRATED_ICON, color=RED).pixmap(ICON_SIZE)
        )

        top_layout = QHBoxLayout()
        top_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(5)
        top_layout.addStretch()
        top_layout.addWidget(self._well_label)
        top_layout.addWidget(self._calibration_icon)
        top_layout.addStretch()

        # calibration mode
        self._calibration_mode_wdg = _CalibrationModeWidget(self)

        # calibration table and buttons
        self._table = _CalibrationTable(self, self._mmc)
        self._table.itemChanged.connect(self._validate_table)
        # add and remove buttons
        self._add_button = QPushButton("Add Position")
        self._add_button.setIcon(icon(MDI6.plus_thick, color=GREEN))
        self._remove_button = QPushButton("Remove Selected")
        self._remove_button.setIcon(icon(MDI6.close_box_outline, color=RED))
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)
        button_layout.addWidget(self._add_button)
        button_layout.addWidget(self._remove_button)
        # calibrate well button
        self._calibrate_well_button = QPushButton("Calibrate Well")
        self._calibrate_well_button.setIcon(icon(MDI6.target_variant))
        self._calibrate_well_button.setIconSize(ICON_SIZE)
        # layout
        table_layout = QVBoxLayout()
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(5)
        table_layout.addWidget(self._table)
        table_layout.addLayout(button_layout)
        table_layout.addWidget(self._calibrate_well_button)

        # LAYOUT --------------------------------------------------------------

        groupbox = QGroupBox()
        layout = QGridLayout(groupbox)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.addLayout(top_layout, 0, 0)
        layout.addWidget(self._calibration_mode_wdg, 1, 0)
        layout.addLayout(table_layout, 2, 0)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(groupbox)

        # CONNECTIONS ---------------------------------------------------------
        self._calibration_mode_wdg.valueChanged.connect(self._on_mode_changed)

        self.setCircularWell(True)  # TODO: remove when adding plate args

    def setCircularWell(self, circular: bool) -> None:
        """Update the calibration widget for circular or rectangular wells."""
        with signals_blocked(self._calibration_mode_wdg):
            self._calibration_mode_wdg.setValue(self.MODES[circular])
        self._calibration_mode_wdg.valueChanged.emit(self._calibration_mode_wdg.value())

    def _on_mode_changed(self, mode: Mode) -> None:
        """Update the rows in the calibration table."""
        self._clear_table()
        self._table.setRowCount(mode.points)
        for i in range(mode.points):
            x = QTableWidgetItem("-")
            y = QTableWidgetItem("-")
            x.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            y.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 0, x)
            self._table.setItem(i, 1, y)

    def _clear_table(self) -> None:
        self._table.setRowCount(0)
        self._table.clearContents()

    def _set_mode(self, mode: str) -> None:
        """Set the mode for the calibration table.

        - 1 center point (either)
        - 2 edge points (square)
        - 3 edge points (circle)
        - 4 edge points (square)
        """
        # self._table.setRowCount(...)
        # as as many row as required and populate with -

    def _validate_table(self, item: QTableWidgetItem) -> None:
        """Validate points.

        - if the new item is already in the list, show an error message and remove it.
        - if the number of points is not yet satisfied, just do nothing
        - if the number of points is correct, try to calculate the calibration,
          if it fails, show an error message. If it succeeds, emit
          calibrationChanged(True)
        - if we somehow went from a valid state to an invalid state, emit
          calibrationChanged(False)
        """


class WellCalibrationTable(QWidget):
    # emitted when the required number of points have been selected and validated
    calibrationChanged = Signal(bool)

    def __init__(self) -> None:
        ...
        self._combo = QComboBox()
        self._combo.currentTextChanged.connect(self._set_mode)

        self._table = QTableWidget()
        self._table.itemChanged.connect(self._validate_table)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

    def setCircularWell(self, circular: bool) -> None:
        """Populate the combobox with either circular or rectangular options."""

    def _set_mode(self, mode: str) -> None:
        """Set the mode for the calibration table.

        - 1 center point (either)
        - 2 edge points (square)
        - 3 edge points (circle)
        - 4 edge points (square)
        """
        self._table.setRowCount(...)

    def _validate_table(self, item: QTableWidgetItem) -> None:
        """Validate points.

        - if the new item is already in the list, show an error message and remove it.
        - if the number of points is not yet satisfied, just do nothing
        - if the number of points is correct, try to calculate the calibration,
          if it fails, show an error message. If it succeeds, emit
          calibrationChanged(True)
        - if we somehow went from a valid state to an invalid state, emit
          calibrationChanged(False)
        """

    def wellCenter(self) -> tuple[float, float] | None:
        """If calibrated, return the calculated center of the well."""


# from qtpy.QtWidgets import QApplication

# app = QApplication([])
# c = WellCalibrationWidget()
# c.show()
# # app.exec()
