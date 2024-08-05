from __future__ import annotations

from pathlib import Path
from typing import Iterator, NamedTuple, cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QItemSelection, QSize, Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon
from superqt.utils import signals_blocked

from ._util import find_circle_center, find_rectangle_center

COMBO_ROLE = Qt.ItemDataRole.UserRole + 1
ICON_PATH = Path(__file__).parent / "icons"
ONE_CIRCLE = QIcon(str(ICON_PATH / "circle-center.svg"))
ONE_SQUARE = QIcon(str(ICON_PATH / "square-center.svg"))
TWO = QIcon(str(ICON_PATH / "square-vertices.svg"))
THREE = QIcon(str(ICON_PATH / "circle-edges.svg"))
FOUR = QIcon(str(ICON_PATH / "square-edges.svg"))
NON_CALIBRATED_ICON = MDI6.circle
CALIBRATED_ICON = MDI6.check_circle
ICON_SIZE = QSize(30, 30)
YELLOW = Qt.GlobalColor.yellow
GREEN = Qt.GlobalColor.green


class Mode(NamedTuple):
    """Calibration mode."""

    text: str
    points: int
    icon: QIcon | None = None


# mapping of Circular well -> [Modes]
MODES: dict[bool, list[Mode]] = {
    True: [
        Mode("1 Center point", 1, ONE_CIRCLE),
        Mode("3 Edge points", 3, THREE),
    ],
    False: [
        Mode("1 Center point", 1, ONE_SQUARE),
        Mode("2 Corners", 2, TWO),
        Mode("4 Edge points", 4, FOUR),
    ],
}


class _CalibrationModeWidget(QComboBox):
    """Widget to select the calibration mode."""

    modeChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._is_circular = False
        self.currentIndexChanged.connect(self._on_value_changed)

    def _on_value_changed(self, index: int) -> None:
        """Emit the selected mode with valueChanged signal."""
        self.modeChanged.emit(self.currentMode())

    def isCircularMode(self) -> bool:
        """Return True if the well is circular."""
        return self._is_circular

    def setCircularMode(self, circular: bool) -> None:
        self._is_circular = bool(circular)
        with signals_blocked(self):
            self.clear()
            for idx, mode in enumerate(MODES[self._is_circular]):
                self.addItem(mode.icon, mode.text)
                self.setItemData(idx, mode, COMBO_ROLE)
        self.modeChanged.emit(self.currentMode())

    def currentMode(self) -> Mode:
        """Return the selected calibration mode."""
        return cast(Mode, self.itemData(self.currentIndex(), COMBO_ROLE))


class _CalibrationTable(QTableWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 2, parent)

        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        hdr = self.horizontalHeader()
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr.setSectionResizeMode(hdr.ResizeMode.Stretch)

        self.setHorizontalHeaderLabels(["X [µm]", "Y [µm]"])
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(
        self, selected: QItemSelection, deselected: QItemSelection
    ) -> None:
        # ensure something is always selected
        if selected.count() == 0 and deselected.count() > 0:
            sel_model = self.selectionModel()
            for item in deselected.indexes():
                sel_model.select(item, sel_model.SelectionFlag.Select)

    def positions(self) -> Iterator[tuple[int, float, float]]:
        """Return the list of non-null (row, x, y) points."""
        for row in range(self.rowCount()):
            if (
                (x_item := self.item(row, 0))
                and (y_item := self.item(row, 1))
                and (x_text := x_item.text())
                and (y_text := y_item.text())
            ):
                yield (row, float(x_text), float(y_text))

    def set_selected(self, x: float, y: float) -> None:
        """Assign (x, y) to the currently selected row in the table."""
        if not (indices := self.selectedIndexes()):
            return  # pragma: no cover

        selected_row = indices[0].row()
        for row, *p in self.positions():
            if p == [x, y] and row != selected_row:
                QMessageBox.critical(
                    self,
                    "Duplicate position",
                    f"Position ({x}, {y}) is already in the list.",
                )
                return

        self._set_row(selected_row, x, y)
        if selected_row < self.rowCount() - 1:
            self.setCurrentCell(selected_row + 1, 0)

    def _set_row(self, row: int, x: str | float, y: str | float) -> None:
        """Emit only one itemChanged signal when setting the item."""
        itemx = QTableWidgetItem(f"{x:.2f}")
        itemx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        itemy = QTableWidgetItem(f"{y:.2f}")
        itemy.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        with signals_blocked(self):
            self.setItem(row, 0, itemx)
        self.setItem(row, 1, itemy)

    def clear_selected(self) -> None:
        """Remove the selected position from the table."""
        if items := self.selectedItems():
            with signals_blocked(self):
                for item in items:
                    item.setText("")
            self.itemChanged.emit(item)

    def clear_all(self) -> None:
        self.resetRowCount(self.rowCount())

    def resetRowCount(self, num: int) -> None:
        with signals_blocked(self):
            self.clearContents()
            self.setRowCount(num)
            # select the first row
            self.setCurrentCell(0, 0)
        self.itemChanged.emit(self.item(0, 0))


class WellCalibrationWidget(QWidget):
    calibrationChanged = Signal(bool)

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._well_center: tuple[float, float] | None = None

        # WIDGETS -------------------------------------------------------------

        # Well label
        self.well_label = QLabel("Well A1")
        font = self.well_label.font()
        font.setBold(True)
        font.setPixelSize(16)
        self.well_label.setFont(font)

        # Icon for calibration status
        self._calibration_icon = QLabel()
        icn = icon(NON_CALIBRATED_ICON, color=YELLOW)
        self._calibration_icon.setPixmap(icn.pixmap(ICON_SIZE))

        # calibration mode
        self._calibration_mode_wdg = _CalibrationModeWidget(self)

        # calibration table and buttons
        self._table = _CalibrationTable(self)

        # add and remove buttons
        self._set_button = QPushButton("Set")
        self._clear_button = QPushButton("Clear")
        self._clear_all_button = QPushButton("Clear All")

        # LAYOUT --------------------------------------------------------------

        labels = QHBoxLayout()
        labels.setContentsMargins(0, 0, 0, 0)
        labels.addWidget(self._calibration_icon)
        labels.addWidget(self.well_label, 1)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Method:"))
        mode_row.addWidget(self._calibration_mode_wdg, 1)

        remove_btns = QHBoxLayout()
        remove_btns.setContentsMargins(0, 0, 0, 0)
        remove_btns.addWidget(self._clear_button)
        remove_btns.addWidget(self._clear_all_button)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.addLayout(labels)
        main_layout.addLayout(mode_row)
        main_layout.addWidget(self._table)
        main_layout.addWidget(self._set_button)
        main_layout.addLayout(remove_btns)

        # CONNECTIONS ---------------------------------------------------------

        self._calibration_mode_wdg.modeChanged.connect(self._on_mode_changed)
        self._set_button.clicked.connect(self._on_set_clicked)
        self._clear_button.clicked.connect(self._table.clear_selected)
        self._clear_all_button.clicked.connect(self._table.clear_all)
        self._table.itemChanged.connect(self._validate_calibration)

    def wellCenter(self) -> tuple[float, float] | None:
        """Return the center of the well, or None if not calibrated."""
        return self._well_center

    def setWellCenter(self, center: tuple[float, float] | None) -> None:
        """Set the calibration icon and emit the calibrationChanged signal."""
        if self._well_center == center:
            return

        self._well_center = center
        if center is None:
            icn = icon(NON_CALIBRATED_ICON, color=YELLOW)
        else:
            icn = icon(CALIBRATED_ICON, color=GREEN)
        self._calibration_icon.setPixmap(icn.pixmap(ICON_SIZE))
        self.calibrationChanged.emit(center is not None)

    def setCircularWell(self, circular: bool) -> None:
        """Update the calibration widget for circular or rectangular wells."""
        self._calibration_mode_wdg.setCircularMode(circular)

    def circularWell(self) -> bool:
        """Return True if the well is circular."""
        return self._calibration_mode_wdg.isCircularMode()

    def _on_set_clicked(self) -> None:
        x, y = self._mmc.getXYPosition()
        self._table.set_selected(round(x, 2), round(y, 2))

    def _on_mode_changed(self, mode: Mode) -> None:
        """Update the rows in the calibration table."""
        self._table.resetRowCount(mode.points)
        self.setWellCenter(None)

    def _validate_calibration(self) -> None:
        """Validate the calibration points added to the table."""
        # get the current (x, y) positions in the table
        points = [p[1:] for p in self._table.positions()]
        needed_points = self._calibration_mode_wdg.currentMode().points

        # if the number of points is not yet satisfied, do nothing
        if len(points) < needed_points:
            self.setWellCenter(None)
            return

        # if the number of points is 1, well is already calibrated
        if needed_points == 1:
            self.setWellCenter(points[0])
            return

        # if the number of points is correct, try to calculate the calibration
        try:
            # TODO: allow additional sanity checks for min/max radius, width/height
            if self.circularWell():
                x, y, radius = find_circle_center(points)
            else:
                x, y, width, height = find_rectangle_center(points)
        except Exception as e:  # pragma: no cover
            self.setWellCenter(None)
            QMessageBox.critical(
                self,
                "Calibration error",
                f"Could not calculate the center of the well.\n\n{e}",
            )
        else:
            self.setWellCenter((x, y))
