from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Literal, cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)
from superqt import fonticon

if TYPE_CHECKING:
    from typing_extensions import TypedDict

    class TimeDict(TypedDict, total=False):
        """Time plan dictionary."""

        phases: list
        interval: timedelta
        loops: int


class TimePlanWidget(QGroupBox):
    """Widget providing options for setting up a timelapse acquisition.

    The `value()` method returns a dictionary with the current state of the widget, in a
    format that matches one of the [useq-schema Time Plan
    specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#time-plans).
    """

    valueChanged = Signal()
    _warning_widget: QWidget

    def __init__(
        self,
        title: str = "Time",
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(title, parent=parent)
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self._mmc = mmcore or CMMCorePlus.instance()

        group_layout = QGridLayout()
        group_layout.setSpacing(15)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        # time table
        self._table = QTableWidget()
        self._table.setMinimumHeight(175)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(hdr.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setTabKeyNavigation(True)
        self._table.setColumnCount(3)
        self._table.setRowCount(0)
        self._table.setHorizontalHeaderLabels(["Timepoints", "Interval", "Units"])
        group_layout.addWidget(self._table, 0, 0)

        # buttons
        buttons_wdg = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        buttons_wdg.setLayout(layout)

        # ChannelGroup combobox
        self._add_button = QPushButton(text="Add")
        self._remove_button = QPushButton(text="Remove")
        self._clear_button = QPushButton(text="Clear")

        self._add_button.clicked.connect(self._create_new_row)
        self._remove_button.clicked.connect(self._remove_selected_rows)
        self._clear_button.clicked.connect(self._clear)

        spacer = QSpacerItem(
            10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        layout.addWidget(self._add_button)
        layout.addWidget(self._remove_button)
        layout.addWidget(self._clear_button)
        layout.addItem(spacer)

        group_layout.addWidget(buttons_wdg, 0, 1)

        # warning Icon (exclamation mark)
        self._warning_icon = QLabel()
        self.setWarningIcon(MDI6.exclamation_thick)
        self._warning_icon.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._warning_icon.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        # warning message
        self._warning_msg = QLabel()
        self.setWarningMessage("Interval shorter than acquisition time per timepoint.")
        # warning widget (icon + message)
        self._warning_widget = QWidget()
        _warning_layout = QHBoxLayout()
        _warning_layout.setSpacing(0)
        _warning_layout.setContentsMargins(0, 0, 0, 0)
        self._warning_widget.setLayout(_warning_layout)
        _warning_layout.addWidget(self._warning_icon)
        _warning_layout.addWidget(self._warning_msg)
        self._warning_widget.setStyleSheet("color:magenta")
        self._warning_widget.hide()

        group_layout.addWidget(self._warning_widget, 1, 0, 1, 2)

        self._mmc.events.systemConfigurationLoaded.connect(self._clear)

        self.destroyed.connect(self._disconnect)

    def _create_new_row(
        self,
        timepoint: int | None = None,
        interval: float | None = None,
        unit: Literal["ms", "sec", "min", "hours"] = "sec",
    ) -> None:
        _timepoints_spinbox = QSpinBox()
        _timepoints_spinbox.setRange(1, 1000000)
        _timepoints_spinbox.setValue(timepoint or 1)
        _timepoints_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        _timepoints_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _timepoints_spinbox.valueChanged.connect(self.valueChanged)

        _interval_spinbox = QDoubleSpinBox()
        _interval_spinbox.setRange(0, 100000)
        _interval_spinbox.setValue(interval or 1)
        _interval_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        _interval_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _interval_spinbox.valueChanged.connect(self.valueChanged)

        _units_combo = QComboBox()
        _units_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        _units_combo.addItems(["ms", "sec", "min", "hours"])
        _units_combo.setCurrentText(unit)
        _units_combo.currentIndexChanged.connect(self.valueChanged)

        idx = self._table.rowCount()
        self._table.insertRow(idx)
        self._table.setCellWidget(idx, 0, _timepoints_spinbox)
        self._table.setCellWidget(idx, 1, _interval_spinbox)
        self._table.setCellWidget(idx, 2, _units_combo)

        self.valueChanged.emit()

    def _remove_selected_rows(self) -> None:
        rows = {r.row() for r in self._table.selectedIndexes()}
        if not rows:
            return
        for idx in sorted(rows, reverse=True):
            self._table.removeRow(idx)
        self.valueChanged.emit()

    def _clear(self) -> None:
        """Clear the channel table."""
        if self._table.rowCount():
            self._table.clearContents()
            self._table.setRowCount(0)
        self.valueChanged.emit()

    def setWarningMessage(self, msg: str) -> None:
        """Set the text of the warning message."""
        self._warning_msg.setText(msg)

    def setWarningIcon(self, icon: str | QIcon) -> None:
        """Set the icon of the warning message."""
        if isinstance(icon, str):
            _icon: QIcon = fonticon.icon(MDI6.exclamation_thick, color="magenta")
        else:
            _icon = icon
        self._warning_icon.setPixmap(_icon.pixmap(QSize(30, 30)))

    def setWarningVisible(self, visible: bool = True) -> None:
        """Set the visibility of the warning message."""
        self._warning_widget.setVisible(visible)

    def value(self) -> TimeDict:
        # keys are from the combobox... values are kwargs for timedelta
        if not self._table.rowCount():
            return {}

        unit = {
            "ms": "milliseconds",
            "sec": "seconds",
            "min": "minutes",
            "hours": "hours",
        }

        if self._table.rowCount() == 1:
            _timepoints_spinbox = cast("QSpinBox", self._table.cellWidget(0, 0))
            _interval_spinbox = cast("QDoubleSpinBox", self._table.cellWidget(0, 1))
            _units_combo = cast("QComboBox", self._table.cellWidget(0, 2))

            _u = _units_combo.currentText()
            return {
                "interval": timedelta(**{unit[_u]: _interval_spinbox.value()}),
                "loops": _timepoints_spinbox.value(),
            }

        else:
            timeplan: TimeDict = {"phases": []}
            for row in range(self._table.rowCount()):
                _timepoints_spinbox = cast("QSpinBox", self._table.cellWidget(row, 0))
                _interval_spinbox = cast(
                    "QDoubleSpinBox", self._table.cellWidget(row, 1)
                )
                _units_combo = cast("QComboBox", self._table.cellWidget(row, 2))

                _u = _units_combo.currentText()
                timeplan["phases"].append(
                    {
                        "interval": timedelta(**{unit[_u]: _interval_spinbox.value()}),
                        "loops": _timepoints_spinbox.value(),
                    }
                )
            return timeplan

    # timeplan is a TimeDicts but it makes typing elsewhere harder
    def set_state(self, timeplan: dict) -> None:
        """Set the state of the widget from a useq time_plan dictionary."""
        self._clear()

        if "phases" in timeplan:
            for t in timeplan["phases"]:
                _tp, _int, _u = self._get_timepoints_interval_and_unit(t)
                self._create_new_row(timepoint=_tp, interval=_int, unit=_u)
        else:
            _tp, _int, _u = self._get_timepoints_interval_and_unit(timeplan)
            self._create_new_row(timepoint=_tp, interval=_int, unit=_u)

    def _get_timepoints_interval_and_unit(
        self, timeplan: dict
    ) -> tuple[int, int | float, Literal["ms", "sec", "min", "hours"]]:
        if "interval" not in timeplan or "loops" not in timeplan:
            raise ValueError("Only time_plans with 'interval' and 'loops' supported.")
        if not isinstance(timeplan["interval"], timedelta):
            raise ValueError(
                "Only time_plans with 'interval' as 'timedelta' supported."
            )
        _tp = int(timeplan["loops"])
        sec = timeplan["interval"].total_seconds()
        if sec >= 3600:
            _u = "hours"
            _int = sec // 3600
        elif sec >= 60:
            _u = "min"
            _int = sec // 60
        elif sec >= 1:
            _u = "sec"
            _int = int(sec)
        else:
            _u = "ms"
            _int = int(sec * 1000)

        return _tp, _int, cast(Literal["ms", "sec", "min", "hours"], _u)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._clear)
