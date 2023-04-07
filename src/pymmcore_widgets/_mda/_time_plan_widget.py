from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, cast

from fonticon_mdi6 import MDI6
from pint import Quantity
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QAbstractSpinBox,
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
from superqt import QQuantity, fonticon

if TYPE_CHECKING:
    from typing_extensions import TypedDict

    class TimeDict(TypedDict, total=False):
        """Time plan dictionary."""

        phases: list
        interval: timedelta
        loops: int
        duration: timedelta


INTERVAL = 0
TIMEPOINTS = 1


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
        self._table.setColumnCount(2)
        self._table.setRowCount(0)
        self._table.setHorizontalHeaderLabels(["Interval", "Timepoints"])
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

        self._mmc.events.systemConfigurationLoaded.connect(self._clear)

        self.destroyed.connect(self._disconnect)

    def _create_new_row(
        self,
        interval: timedelta | None = None,
        loops: int | None = None,
    ) -> None:
        """Create a new row in the table."""
        val, u = (interval.total_seconds(), "s") if interval is not None else (1, "s")
        _interval = QQuantity(val, u)
        _interval._mag_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _interval._mag_spinbox.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        _interval.valueChanged.connect(self.valueChanged)

        _timepoints = QSpinBox()
        _timepoints.setRange(1, 1000000)
        _timepoints.setValue(loops or 1)
        _timepoints.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        _timepoints.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _timepoints.valueChanged.connect(self.valueChanged)

        idx = self._table.rowCount()
        self._table.insertRow(idx)
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
        """Clear the time table."""
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

    def _quantity_to_timedelta(self, value: Quantity) -> timedelta:
        if value.units == "day":
            return timedelta(days=value.magnitude)
        elif value.units == "hour":
            return timedelta(hours=value.magnitude)
        elif value.units == "minute":
            return timedelta(minutes=value.magnitude)
        elif value.units == "second":
            return timedelta(seconds=value.magnitude)
        elif value.units == "millisecond":
            return timedelta(milliseconds=value.magnitude)
        raise ValueError(f"Invalid units: {value.units}")

    def value(self) -> TimeDict:
        """Return the current time plan as a TimeDict.

        Note that the output TimeDict will match [TIntervalLoopsdictionary](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.TIntervalLoops
        ) or [MultiPhaseTimePlan](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.MultiPhaseTimePlan
        )[[TIntervalLoopsdictionary](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.TIntervalLoops
        )] from useq schema.
        """
        if not self._table.rowCount():
            return {}

        timeplan: TimeDict = {}
        phases: list = []
        for row in range(self._table.rowCount()):
            interval = cast("QQuantity", self._table.cellWidget(row, INTERVAL))
            timepoints = cast("QSpinBox", self._table.cellWidget(row, TIMEPOINTS))
            phases.append(
                {
                    "interval": self._quantity_to_timedelta(interval.value()),
                    "loops": timepoints.value(),
                }
            )
        if len(phases) == 1:
            timeplan = phases[0]
        else:
            timeplan["phases"] = phases

        return timeplan

    # t_plan is a TimeDicts but it makes typing elsewhere harder
    def set_state(self, t_plan: dict) -> None:
        """Set the state of the widget.

        Note that the output TimeDict will match [TIntervalLoopsdictionary](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.TIntervalLoops
        ) or [MultiPhaseTimePlan](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.MultiPhaseTimePlan
        )[[TIntervalLoopsdictionary](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.TIntervalLoops
        )] from useq schema.

        If the `interval` key is not a `timedelta` object, it will be converted to a
        timedelta object and will be considered as expressed in seconds.
        """
        self._clear()

        phases = t_plan.get("phases", [t_plan])
        for phase in phases:
            self._check_dict(phase)
            self._create_new_row(interval=phase["interval"], loops=phase["loops"])

    # t_plan is a TimeDicts but it makes typing elsewhere harder
    def _check_dict(self, t_plan: dict) -> None:
        """Check if the timeplan is valid."""
        if "interval" not in t_plan or "loops" not in t_plan:
            raise KeyError(
                "The time_plans dictionary must incluede 'interval' and 'loop' keys."
            )
        # if the interval is not a timedelta object, convert it to a minutes timedelta
        if not isinstance(t_plan["interval"], timedelta):
            t_plan["interval"] = timedelta(minutes=t_plan["interval"])

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._clear)
