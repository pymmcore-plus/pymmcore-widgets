from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, cast

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
        duration: timedelta


DURATION = 0
INTERVAL = 1
TIMEPOINTS = 2


class _DoubleSpinAndCombo(QWidget):
    """A widget with a double spinbox and a combo box."""

    valueChanged = Signal()

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)

        self._spin = QDoubleSpinBox()
        self._spin.setMinimum(0)
        self._spin.setMaximum(100000)
        self._spin.wheelEvent = lambda event: None  # block mouse scroll
        self._spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spin.valueChanged.connect(self.valueChanged)
        self._combo = QComboBox()
        self._combo.addItems(["ms", "sec", "min", "hours"])
        self._combo.currentTextChanged.connect(self.valueChanged)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self._spin)
        layout.addWidget(self._combo)
        self.setLayout(layout)

    def value(self) -> timedelta:
        """Return the value of the widget as a timedelta."""
        unit = {
            "ms": "milliseconds",
            "sec": "seconds",
            "min": "minutes",
            "hours": "hours",
        }
        _u = self._combo.currentText()
        return timedelta(**{unit[_u]: self._spin.value()})

    def setValue(self, value: timedelta) -> None:
        sec = value.total_seconds()
        if sec >= 3600:
            u = "hours"
            val = sec // 3600
        elif sec >= 60:
            u = "min"
            val = sec // 60
        elif sec >= 1:
            u = "sec"
            val = int(sec)
        else:
            u = "ms"
            val = int(sec * 1000)

        self._spin.setValue(val)
        self._combo.setCurrentText(u)


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
        self._table.setHorizontalHeaderLabels(["Durations", "Interval", "Timepoints"])
        group_layout.addWidget(self._table, 0, 0)

        # buttons
        buttons_wdg = QWidget()
        layout_buttons = QVBoxLayout()
        layout_buttons.setSpacing(10)
        layout_buttons.setContentsMargins(0, 0, 0, 0)
        buttons_wdg.setLayout(layout_buttons)

        min_size = 100
        self._add_button = QPushButton(text="Add")
        self._add_button.setMinimumWidth(min_size)
        self._remove_button = QPushButton(text="Remove")
        self._remove_button.setMinimumWidth(min_size)
        self._clear_button = QPushButton(text="Clear")
        self._clear_button.setMinimumWidth(min_size)

        self._add_button.clicked.connect(self._create_new_row)
        self._remove_button.clicked.connect(self._remove_selected_rows)
        self._clear_button.clicked.connect(self._clear)

        spacer = QSpacerItem(
            10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        layout_buttons.addWidget(self._add_button)
        layout_buttons.addWidget(self._remove_button)
        layout_buttons.addWidget(self._clear_button)
        layout_buttons.addItem(spacer)

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

        self._table.cellClicked.connect(self._enable_cell)

        self._mmc.events.systemConfigurationLoaded.connect(self._clear)

        self.destroyed.connect(self._disconnect)

    def _enable_cell(self, row: int, col: int) -> None:
        """Enable editing of duration or timepoints cell."""
        if col == 0:
            self._table.cellWidget(row, col).setEnabled(True)
            self._table.cellWidget(row, TIMEPOINTS).setEnabled(False)
        elif col == 2:
            self._table.cellWidget(row, col).setEnabled(True)
            self._table.cellWidget(row, DURATION).setEnabled(False)

    def _create_new_row(
        self,
        interval: timedelta | None = None,
        loops: int | None = None,
        duration: timedelta | None = None,
    ) -> None:
        """Create a new row in the table."""
        _interval = _DoubleSpinAndCombo()
        _interval.setValue(interval or timedelta(seconds=1))
        _interval.valueChanged.connect(self.valueChanged)

        _timepoints = QSpinBox()
        _timepoints.setRange(1, 1000000)
        _timepoints.setValue(loops or 1)
        _timepoints.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        _timepoints.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _timepoints.valueChanged.connect(self.valueChanged)
        if duration:
            _timepoints.setEnabled(False)

        _duration = _DoubleSpinAndCombo()
        if duration:
            _duration.setValue(duration)
        else:
            _duration.setEnabled(False)

        idx = self._table.rowCount()
        self._table.insertRow(idx)
        self._table.setCellWidget(idx, DURATION, _duration)
        self._table.setCellWidget(idx, INTERVAL, _interval)
        self._table.setCellWidget(idx, TIMEPOINTS, _timepoints)

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
        """Return the current time plan as a TimeDict.

        Note that the output TimeDict will match [TIntervalLoopsdictionary](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.TIntervalLoops
        ) or [TIntervalDuration](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.TIntervalDuration
        ) or [MultiPhaseTimePlan](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.MultiPhaseTimePlan
        )[[TIntervalLoopsdictionary](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.TIntervalLoops
        ) | [TIntervalDuration](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.TIntervalDuration
        )] from useq schema.
        """
        if not self._table.rowCount():
            return {}

        timeplan: TimeDict = {}

        if self._table.rowCount() == 1:
            duration = cast("_DoubleSpinAndCombo", self._table.cellWidget(0, DURATION))
            interval = cast("_DoubleSpinAndCombo", self._table.cellWidget(0, INTERVAL))
            timepoints = cast("QSpinBox", self._table.cellWidget(0, TIMEPOINTS))

            if duration.isEnabled():
                timeplan = {"interval": interval.value(), "duration": duration.value()}
            else:
                timeplan = {"interval": interval.value(), "loops": timepoints.value()}

        else:
            timeplan = {"phases": []}
            for row in range(self._table.rowCount()):
                duration = cast(
                    "_DoubleSpinAndCombo", self._table.cellWidget(row, DURATION)
                )
                interval = cast(
                    "_DoubleSpinAndCombo", self._table.cellWidget(row, INTERVAL)
                )
                timepoints = cast("QSpinBox", self._table.cellWidget(row, TIMEPOINTS))

                if duration.isEnabled():
                    timeplan["phases"].append(
                        {"interval": interval.value(), "duration": duration.value()}
                    )
                else:
                    timeplan["phases"].append(
                        {"interval": interval.value(), "loops": timepoints.value()}
                    )
        return timeplan

    # t_plan is a TimeDicts but it makes typing elsewhere harder
    def set_state(self, t_plan: dict) -> None:
        """Set the state of the widget.

        Note that the output TimeDict will match [TIntervalLoopsdictionary](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.TIntervalLoops
        ) or [TIntervalDuration](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.TIntervalDuration
        ) or [MultiPhaseTimePlan](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.MultiPhaseTimePlan
        )[[TIntervalLoopsdictionary](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.TIntervalLoops
        ) | [TIntervalDuration](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.TIntervalDuration
        )] from useq schema.
        """
        self._clear()

        if "phases" in t_plan:
            for t in t_plan["phases"]:
                self._check_dict(t)
                self._create_new_row(
                    interval=t["interval"],
                    loops=t.get("loops"),
                    duration=t.get("duration"),
                )
        else:
            self._check_dict(t_plan)
            self._create_new_row(
                interval=t_plan["interval"],
                loops=t_plan.get("loops"),
                duration=t_plan.get("duration"),
            )

    # t_plan is a TimeDicts but it makes typing elsewhere harder
    def _check_dict(self, t_plan: dict) -> None:
        """Check if the timeplan is valid."""
        if "interval" not in t_plan:
            raise NotImplementedError(
                "time_plans dictionary must incluede 'interval' key."
            )

        if not isinstance(t_plan["interval"], timedelta):
            raise ValueError(
                "Only time_plans with 'interval' as 'timedelta' supported."
            )

        if "loops" not in t_plan and "duration" not in t_plan:
            raise NotImplementedError(
                "time_plans dictionary must incluede 'loops' or 'duration' keys."
            )

        if t_plan.get("duration") and not isinstance(t_plan["duration"], timedelta):
            raise ValueError(
                "Only time_plans with 'duration' as 'timedelta' supported."
            )

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._clear)
