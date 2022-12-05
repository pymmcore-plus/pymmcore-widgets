from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt import fonticon

if TYPE_CHECKING:
    from typing_extensions import TypedDict

    class TimeDict(TypedDict):
        """Time plan dictionary."""

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
        # self.setChecked(False)

        self._mmc = mmcore or CMMCorePlus.instance()

        # timepoints spinbox
        tpoints_label = QLabel(text="Timepoints:")
        tpoints_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._timepoints_spinbox = QSpinBox()
        self._timepoints_spinbox.setRange(1, 1000000)
        self._timepoints_spinbox.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._timepoints_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timepoints_spinbox.valueChanged.connect(self.valueChanged)

        # interval
        interval_label = QLabel(text="Interval:  ")
        interval_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._interval_spinbox = QDoubleSpinBox()
        self._interval_spinbox.setValue(1.0)
        self._interval_spinbox.setRange(0, 100000)
        self._interval_spinbox.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._interval_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._interval_spinbox.valueChanged.connect(self.valueChanged)

        self._units_combo = QComboBox()
        self._units_combo.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._units_combo.addItems(["ms", "sec", "min", "hours"])
        self._units_combo.setCurrentText("sec")
        self._units_combo.currentIndexChanged.connect(self.valueChanged)

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
        self._warning_widget.setLayout(QHBoxLayout())
        self._warning_widget.layout().addWidget(self._warning_icon)
        self._warning_widget.layout().addWidget(self._warning_msg)
        self._warning_widget.setStyleSheet("color:magenta")
        self._warning_widget.hide()

        self.setLayout(QVBoxLayout())
        top_row = QWidget()
        top_row.setLayout(QHBoxLayout())
        top_row.layout().setSpacing(5)
        top_row.layout().addWidget(tpoints_label)
        top_row.layout().addWidget(self._timepoints_spinbox)
        top_row.layout().addWidget(interval_label)
        top_row.layout().addWidget(self._interval_spinbox)
        top_row.layout().addWidget(self._units_combo)

        self.layout().addWidget(top_row)
        self.layout().addWidget(self._warning_widget)

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
        unit = {
            "ms": "milliseconds",
            "sec": "seconds",
            "min": "minutes",
            "hours": "hours",
        }
        u = self._units_combo.currentText()
        return {
            "interval": timedelta(**{unit[u]: self._interval_spinbox.value()}),
            "loops": self._timepoints_spinbox.value(),
        }

    def set_state(self, z_plan: dict) -> None:
        """Set the state of the widget from a useq time_plan dictionary."""
        if "interval" not in z_plan or "loops" not in z_plan:
            raise ValueError("Only time_plans with 'interval' and 'loops' supported.")

        self._timepoints_spinbox.setValue(z_plan["loops"])
        sec = cast(timedelta, z_plan["interval"]).total_seconds()
        if sec >= 60:
            self._units_combo.setCurrentText("min")
            self._interval_spinbox.setValue(sec // 60)
        elif sec >= 1:
            self._units_combo.setCurrentText("sec")
            self._interval_spinbox.setValue(int(sec))
        else:
            self._units_combo.setCurrentText("ms")
            self._interval_spinbox.setValue(int(sec * 1000))
