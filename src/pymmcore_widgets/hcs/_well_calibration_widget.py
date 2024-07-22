from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QModelIndex, QSize, Qt, Signal
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

from ._util import find_circle_center, find_rectangle_center, show_critical_message

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
EMPTY = "-"


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
        layout.addWidget(QLabel("Mode:"), 0)
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
    valueChanged = Signal(object)

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)

        hdr = self.horizontalHeader()
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignHCenter)
        hdr.setSectionResizeMode(hdr.ResizeMode.Stretch)
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["X", "Y"])

        self.doubleClicked.connect(self._on_double_clicked)

    def value(self) -> list[tuple[float, float]]:
        """Return the list of calibration points."""
        return [
            (float(self.item(row, 0).text()), float(self.item(row, 1).text()))
            for row in range(self.rowCount())
            if self.item(row, 0).text() != EMPTY and self.item(row, 1).text() != EMPTY
        ]

    def add(self) -> None:
        """Add a new x, y stage position to the table."""
        x, y = self._mmc.getXPosition(), self._mmc.getYPosition()

        # if there are empty rows, fill the first one
        for row in range(self.rowCount()):
            rx, ry = self.item(row, 0).text(), self.item(row, 1).text()
            if rx == EMPTY and ry == EMPTY:
                self._add_item(row, x, y)
                self.valueChanged.emit((row, x, y))
                return

        # otherwise, add a new row
        self.insertRow(self.rowCount())
        self._add_item(self.rowCount() - 1, x, y)
        self.valueChanged.emit((self.rowCount() - 1, x, y))

    def remove_selected(self) -> None:
        """Remove the selected position from the table."""
        if selected := list({i.row() for i in self.selectedIndexes()}):
            for row in reversed(selected):
                self.removeRow(row)
        self.valueChanged.emit(None)

    def clear(self) -> None:
        """Clear the table."""
        self.setRowCount(0)
        self.clearContents()
        self.valueChanged.emit(None)

    def _add_item(self, row: int, x: str | float, y: str | float) -> None:
        """Add x and y values to the table and emit valueChanged only once."""
        x_item, y_item = QTableWidgetItem(str(x)), QTableWidgetItem(str(y))
        x_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        y_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, 0, x_item)
        self.setItem(row, 1, y_item)

    def _on_double_clicked(self, index: QModelIndex) -> None:
        """Move the stage to the selected position."""
        row = index.row()
        x, y = self.item(row, 0).text(), self.item(row, 1).text()
        if x == EMPTY or y == EMPTY:
            return
        self._mmc.setXYPosition(float(x), float(y))


class WellCalibrationWidget(QWidget):
    calibrationChanged = Signal(bool)

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self.MODES: dict[bool, list[Mode]] = {
            True: [
                Mode("1 points in the center", 1, ONE_CIRCLE),
                Mode("3 points on the edges", 3, THREE),
            ],
            False: [
                Mode("1 points in the center", 1, ONE_SQUARE),
                Mode("2 points on opposite vertices", 2, TWO),
                Mode("4 points on 4 opposite edges", 4, FOUR),
            ],
        }

        self._well_center: tuple[float, float] | None = None

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
        # add and remove buttons
        self._add_button = QPushButton("Add Position")
        self._add_button.setIcon(icon(MDI6.plus_thick, color=GREEN))
        self._add_button.setIconSize(ICON_SIZE)
        self._remove_button = QPushButton("Remove Selected")
        self._remove_button.setIcon(icon(MDI6.close_box_outline, color=RED))
        self._remove_all_button = QPushButton("Remove All")
        self._remove_all_button.setIcon(
            icon(MDI6.close_box_multiple_outline, color=RED)
        )
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)
        button_layout.addWidget(self._remove_button)
        button_layout.addWidget(self._remove_all_button)
        # layout
        table_layout = QVBoxLayout()
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(5)
        table_layout.addWidget(self._table)
        table_layout.addWidget(self._add_button)
        table_layout.addLayout(button_layout)

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
        self._add_button.clicked.connect(self._table.add)
        self._remove_button.clicked.connect(self._table.remove_selected)
        self._remove_all_button.clicked.connect(self._table.clear)
        self._table.valueChanged.connect(self._validate_table)

    def setWellCenter(self, center: tuple[float, float]) -> None:
        """Set the center of the well."""
        self._well_center = center
        self._set_calibrated(center)

    def wellCenter(self) -> tuple[float, float] | None:
        """Return the center of the well."""
        return self._well_center

    def setCircularWell(self, circular: bool) -> None:
        """Update the calibration widget for circular or rectangular wells."""
        with signals_blocked(self._calibration_mode_wdg):
            self._calibration_mode_wdg.setValue(self.MODES[circular])
        self._calibration_mode_wdg.valueChanged.emit(self._calibration_mode_wdg.value())

    def circularWell(self) -> bool:
        """Return True if the well is circular."""
        return self._calibration_mode_wdg.value() in self.MODES[True]

    def _on_mode_changed(self, mode: Mode) -> None:
        """Update the rows in the calibration table."""
        with signals_blocked(self._table):
            self._table.clear()
        for _ in range(mode.points):
            self._add_empty_row()

    def _add_empty_row(self) -> None:
        """Add an empty row to the table with x and y set to EMPTY."""
        self._table.insertRow(self._table.rowCount())
        self._table._add_item(self._table.rowCount() - 1, EMPTY, EMPTY)

    def _set_calibrated(self, center: tuple[float, float]) -> None:
        """Set the calibration icon and emit the calibrationChanged signal."""
        self._calibration_icon.setPixmap(
            icon(CALIBRATED_ICON, color=GREEN).pixmap(ICON_SIZE)
        )
        self._well_center = center
        self.calibrationChanged.emit(True)

    def _set_uncalibrated(self) -> None:
        """Set the uncalibrated icon and emit the calibrationChanged signal."""
        self._calibration_icon.setPixmap(
            icon(NON_CALIBRATED_ICON, color=RED).pixmap(ICON_SIZE)
        )
        self._well_center = None
        self.calibrationChanged.emit(False)

    def _validate_table(self, value: tuple[int, float, float] | None) -> None:
        """Validate the calibration points added to the table."""
        # get the count of (x, y) in the table
        current_values = self._table.value()
        mode = self._calibration_mode_wdg.value()

        # add empty rows if the number of points is less than the required number
        # this is triggered when the user removes a row(s) and the table is empty
        if value is None and self._table.rowCount() < mode.points:
            for _ in range(mode.points - self._table.rowCount()):
                self._add_empty_row()
            self._set_uncalibrated()
            return

        # if the new item is already in the list, show an error message and remove it.
        if value is not None:
            row, x, y = value
            # if the number of points is greater than the required number of points,
            # remove the last row
            if len(current_values) > mode.points:
                self._table.removeRow(row)
                show_critical_message(
                    self,
                    "Invalid number of points",
                    f"Invalid number of points. Expected {mode.points}.",
                )
                return

            # check if the new value appears more than once
            count = sum(v == (x, y) for v in current_values)
            # if the count is greater than 1, remove the row
            if count > 1:
                self._table.removeRow(row)
                self._add_empty_row()
                self._set_uncalibrated()
                show_critical_message(
                    self,
                    "Duplicate position",
                    f"Position ({x}, {y}) is already in the list and will be removed.",
                )
                return

        # if the number of points is not yet satisfied, just do nothing
        if len(current_values) < mode.points:
            self._set_uncalibrated()
            return

        # if the number of points is 1, well is already calibrated
        if mode.points == 1:
            self._set_calibrated(current_values[0])
            return

        # if the number of points is correct, try to calculate the calibration
        try:
            x, y = (
                find_circle_center(*current_values)
                if self.circularWell()
                else find_rectangle_center(*current_values)
            )
            self._set_calibrated((x, y))
        except Exception as e:
            self._set_uncalibrated()
            show_critical_message(
                self,
                "Calibration error",
                f"Could not calculate the center of the well.\nError: {e}",
            )
            return
