from __future__ import annotations

import warnings
from datetime import timedelta
from typing import TYPE_CHECKING, cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QGridLayout,
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
from superqt.utils import signals_blocked
from useq import MDASequence, MultiPhaseTimePlan, TIntervalLoops

if TYPE_CHECKING:
    from typing_extensions import TypedDict

    class TimeDict(TypedDict, total=False):
        """Time plan dictionary."""

        phases: list
        interval: timedelta
        loops: int

    class MultiPhaseTimeDict:
        """MultiPhase time plan dictionary."""

        phases: list[TimeDict]


INTERVAL = 0
TIMEPOINTS = 1


class TimePlanWidget(QWidget):
    """Widget providing options for setting up a timelapse acquisition.

    The `value()` method returns a dictionary with the current state of the widget, in a
    format that matches one of the [useq-schema MultiPhaseTimePlan
    specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.MultiPhaseTimePlan).

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget, by default None.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    valueChanged = Signal()
    _warning_widget: QWidget

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

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
        val, u = (
            (interval.total_seconds(), "s")
            if isinstance(interval, timedelta)
            else (1, "s")
        )
        quant_wdg = QQuantity(val, u)
        mag_spin = cast("QDoubleSpinBox", getattr(quant_wdg, "_mag_spinbox", None))
        if mag_spin is None:
            warnings.warn(
                "QQuantity._mag_spinbox not found, check superqt version.", stacklevel=1
            )

        mag_spin.setMinimum(0.0)
        mag_spin.wheelEvent = lambda event: None
        mag_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mag_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        mag_spin.setKeyboardTracking(False)
        quant_wdg.valueChanged.connect(self.valueChanged)

        time_spin = QSpinBox()
        time_spin.wheelEvent = lambda event: None
        time_spin.setRange(1, 1000000)
        time_spin.setValue(loops or 1)
        time_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        time_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_spin.setKeyboardTracking(False)
        time_spin.valueChanged.connect(self.valueChanged)

        idx = self._table.rowCount()
        self._table.insertRow(idx)
        self._table.setCellWidget(idx, INTERVAL, quant_wdg)
        self._table.setCellWidget(idx, TIMEPOINTS, time_spin)

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

    def value(self) -> MultiPhaseTimeDict:
        """Return the current time plan as a dictionary.

        Note that the output will match the [useq-schema
        MultiPhaseTimePlan specifications](
        https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.MultiPhaseTimePlan
        ).
        """
        timeplan: MultiPhaseTimeDict = {"phases": []}  # type: ignore
        if not self._table.rowCount():
            return timeplan

        for row in range(self._table.rowCount()):
            interval = cast("QQuantity", self._table.cellWidget(row, INTERVAL))
            timepoints = cast("QSpinBox", self._table.cellWidget(row, TIMEPOINTS))
            timeplan["phases"].append(  # type: ignore
                {
                    "interval": interval.value().to_timedelta(),
                    "loops": timepoints.value(),
                }
            )
        return timeplan

    # t_plan is a TimeDicts/MultiPhaseTimeDict but it makes typing elsewhere harder
    def set_state(self, t_plan: dict) -> None:
        """Set the state of the widget.

        Parameters
        ----------
        t_plan : dict
            A dictionary following the [useq-schema TIntervalLoopsdictionary
            specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.TIntervalLoops)
            or the
            [useq-schema MultiPhaseTimePlan TIntervalLoopsdictionary specifications](
            https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.MultiPhaseTimePlan).

            If the [TIntervalLoopsdictionary](
            https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.TIntervalLoops
            ) `interval` key is not a `timedelta` object, it will be converted to a
            timedelta object and will be considered as expressed in seconds.
        """
        tp = MDASequence(time_plan=t_plan).time_plan
        if tp is None:
            # should we raise/warn here?
            return
        with signals_blocked(self):
            self._clear()
            phases = tp.phases if isinstance(tp, MultiPhaseTimePlan) else [tp]
            for phase in phases:
                if not isinstance(phase, TIntervalLoops):
                    raise ValueError(
                        "Time dicts must have both 'interval' and 'loops'."
                    )
                self._create_new_row(interval=phase.interval, loops=phase.loops)
        self.valueChanged.emit()

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._clear)
