from __future__ import annotations

import string
from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    NamedTuple,
    cast,
)

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)
from superqt.fonticon import icon
from superqt.utils import signals_blocked
from useq import WellPlate  # noqa: TCH002

from pymmcore_widgets.hcs._graphics_items import RED, Well
from pymmcore_widgets.useq_widgets._column_info import FloatColumn
from pymmcore_widgets.useq_widgets._data_table import DataTableWidget

if TYPE_CHECKING:
    from qtpy.QtGui import QIcon, QPixmap

AlignCenter = Qt.AlignmentFlag.AlignCenter
FixedSizePolicy = (QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

ALPHABET = string.ascii_uppercase
ROLE = Qt.ItemDataRole.UserRole + 1

MAX = 9999999
ICON_SIZE = 22

LABEL_STYLE = """
    background: #00FF00;
    font-size: 16pt; font-weight:bold;
    color : black;
    border: 1px solid black;
    border-radius: 5px;
"""


class Mode(NamedTuple):
    """Calibration mode."""

    text: str
    points: int
    icon: QIcon | None = None


class _CalibrationModeWidget(QGroupBox):
    """Widget to select the calibration mode."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._mode_combo = QComboBox()
        self._mode_combo.setEditable(True)
        self._mode_combo.lineEdit().setReadOnly(True)
        self._mode_combo.lineEdit().setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._mode_combo.currentIndexChanged.connect(self._on_value_changed)

        lbl = QLabel(text="Calibration Mode:")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.addWidget(lbl, 0)
        layout.addWidget(self._mode_combo, 1)

    def _on_value_changed(self) -> None:
        """Emit the selected mode with valueChanged signal."""
        mode = self._mode_combo.itemData(self._mode_combo.currentIndex(), ROLE)
        self.valueChanged.emit(mode)

    def setValue(self, modes: list[Mode] | None) -> None:
        """Set the available modes."""
        self._mode_combo.clear()
        if modes is None:
            return
        for idx, mode in enumerate(modes):
            self._mode_combo.addItem(mode.icon, mode.text)
            self._mode_combo.setItemData(idx, mode, ROLE)

    def value(self) -> Mode:
        """Return the selected calibration mode."""
        mode = self._mode_combo.itemData(self._mode_combo.currentIndex(), ROLE)
        return cast(Mode, mode)


class _CalibrationTable(DataTableWidget):
    """Table to store the calibration positions."""

    X = FloatColumn(
        key="x", header="X [µm]", maximum=MAX, minimum=-MAX, is_row_selector=True
    )
    Y = FloatColumn(
        key="y", header="Y [µm]", maximum=MAX, minimum=-MAX, is_row_selector=True
    )

    def __init__(
        self,
        rows: int = 0,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(rows, parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        # QLabels to show the well name
        # fix policy of space already in the toolbar
        spacer = self.toolBar().layout().itemAt(0).widget()
        spacer.setFixedSize(5, ICON_SIZE)
        spacer.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # label
        self._well_label = QLabel(text=" Well ")
        self._well_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._well_label.setFixedHeight(ICON_SIZE)
        self._well_label.setStyleSheet(LABEL_STYLE)
        self._well_label.setAlignment(AlignCenter)
        # spacer to keep the label to the left and the buttons to the right
        spacer_2 = QWidget()
        spacer_2.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # add widgets to the toolbar
        self.toolBar().insertWidget(self.act_add_row, self._well_label)
        self.toolBar().insertWidget(self.act_add_row, spacer_2)

        # when a new row is inserted, call _on_rows_inserted
        # to update the new values from the core position
        self.table().model().rowsInserted.connect(self._on_rows_inserted)

    # _________________________PUBLIC METHODS_________________________ #

    def value(
        self, exclude_unchecked: bool = True, exclude_hidden_cols: bool = True
    ) -> list[tuple[float, float]]:
        """Get the calibration positions as a list of (x, y) tuples."""
        pos = [(r["x"], r["y"]) for r in self.table().iterRecords()]
        return pos or []

    def setValue(self, value: Iterable[tuple[float, float]]) -> None:
        """Set the calibration positions."""
        pos = [{self.X.key: x, self.Y.key: y} for x, y in value]
        super().setValue(pos)

    def setLabelText(self, text: str) -> None:
        """Set the well name."""
        self._well_label.setText(text)

    def getLabelText(self) -> str:
        """Return the well name."""
        return str(self._well_label.text())

    # _________________________PRIVATE METHODS________________________ #

    def _add_row(self) -> None:
        """Add a new to the end of the table and use the current core position."""
        # note: _add_row is only called when act_add_row is triggered
        # (e.g. when the + button is clicked). Not when a row is added programmatically

        # block the signal that's going to be emitted until _on_rows_inserted
        # has had a chance to update the values from the current stage position
        with signals_blocked(self):
            super()._add_row()
        self.valueChanged.emit()

    def _on_rows_inserted(self, parent: Any, start: int, end: int) -> None:
        with signals_blocked(self):
            for row_idx in range(start, end + 1):
                self._set_xy_from_core(row_idx)
        self.valueChanged.emit()

    def _set_xy_from_core(self, row: int, col: int = 0) -> None:
        if self._mmc.getXYStageDevice():
            data = {
                self.X.key: self._mmc.getXPosition(),
                self.Y.key: self._mmc.getYPosition(),
            }
            self.table().setRowData(row, data)


class _TestCalibrationWidget(QGroupBox):
    """Widget to test the calibration of a well.

    You can select a well and move the XY stage to a random edge point of the well.
    """

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)
        self.setTitle("Test Calibration")

        self._mmc = mmcore or CMMCorePlus.instance()

        self._plate: WellPlate | None = None

        # test calibration groupbox
        lbl = QLabel("Move to edge:")
        # combo to select well letter
        self._letter_combo = QComboBox()
        # combo to select well number
        self._number_combo = QComboBox()
        # test button
        self._test_button = QPushButton("Go")
        self._test_button.setEnabled(False)
        self._stop_button = QPushButton("Stop")
        self._stop_button.setToolTip("Stop XY stage movement.")
        # groupbox
        test_calibration_layout = QHBoxLayout()
        test_calibration_layout.setSpacing(10)
        test_calibration_layout.setContentsMargins(10, 10, 10, 10)
        test_calibration_layout.addWidget(lbl, 0)
        test_calibration_layout.addWidget(self._letter_combo, 1)
        test_calibration_layout.addWidget(self._number_combo, 1)
        test_calibration_layout.addWidget(self._test_button, 0)
        test_calibration_layout.addWidget(self._stop_button, 0)

        # main
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addLayout(test_calibration_layout)

        # connect
        self._stop_button.clicked.connect(self._stop_xy_stage)

    # _________________________PUBLIC METHODS_________________________ #

    def value(self) -> tuple[WellPlate | None, Well]:
        """Return the selected test well as `WellInfo` object."""
        return self._plate, Well(
            name=self._letter_combo.currentText() + self._number_combo.currentText(),
            row=self._letter_combo.currentIndex(),
            column=self._number_combo.currentIndex(),
        )

    def setValue(self, plate: WellPlate | None, well: Well | None) -> None:
        """Set the selected test well."""
        self._plate = plate
        self._update_combos()
        self._letter_combo.setCurrentIndex(0 if well is None else well.row)
        self._number_combo.setCurrentIndex(0 if well is None else well.column)

    # _________________________PRIVATE METHODS________________________ #

    def _stop_xy_stage(self) -> None:
        self._mmc.stop(self._mmc.getXYStageDevice())

    def _update_combos(self) -> None:
        if self._plate is None:
            return
        self._letter_combo.clear()
        letters = [f"{self._index_to_row_name(r)}" for r in range(self._plate.rows)]
        self._letter_combo.addItems(letters)
        self._letter_combo.adjustSize()

        self._number_combo.clear()
        numbers = [str(c) for c in range(1, self._plate.columns + 1)]
        self._number_combo.addItems(numbers)
        self._number_combo.adjustSize()

    def _index_to_row_name(self, index: int) -> str:
        """Convert a zero-based column index to row name (A, B, ..., Z, AA, AB, ...)."""
        name = ""
        while index >= 0:
            name = chr(index % 26 + 65) + name
            index = index // 26 - 1
        return name


class _CalibrationLabel(QGroupBox):
    """Label to show the calibration status."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle("Calibration Status")

        # icon
        self._icon_lbl = QLabel()
        self._icon_lbl.setSizePolicy(*FixedSizePolicy)
        self._icon_lbl.setPixmap(
            icon(MDI6.close_octagon_outline, color=RED).pixmap(QSize(30, 30))
        )
        # text
        self._text_lbl = QLabel(text="Plate Not Calibrated!")
        self._text_lbl.setStyleSheet("font-size: 14px; font-weight: bold;")

        # main
        layout = QHBoxLayout(self)
        layout.setAlignment(AlignCenter)
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._icon_lbl)
        layout.addWidget(self._text_lbl)

    # _________________________PUBLIC METHODS_________________________ #

    def value(self) -> str:
        return str(self._text_lbl.text())

    def setValue(self, pixmap: QPixmap, text: str) -> None:
        """Set the icon and text of the labels."""
        self._icon_lbl.setPixmap(pixmap)
        self._text_lbl.setText(text)
