from __future__ import annotations

from enum import Enum
from typing import Any

from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from superqt.utils import signals_blocked


class AutofocusMode(str, Enum):
    NONE = "none"
    HARDWARE = "hardware"
    SOFTWARE = "software"


PYMMCW_AUTOFOCUS_KEY = "autofocus"
SOFTWARE_AF_DISABLED_TOOLTIP = (
    "Software autofocus cannot be used with absolute Z positions "
    "(TOP_BOTTOM mode)."
)
SOFTWARE_AF_OPTIONS_TOOLTIP = (
    "Open the software autofocus configuration widget."
)
SOFTWARE_AF_PENDING_TOOLTIP = (
    "Software autofocus configuration widget is not implemented yet."
)


class AutofocusControls(QWidget):
    valueChanged = Signal()
    configureRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._mode_label = QLabel("Autofocus:")
        self._mode = QComboBox()
        self._mode.addItem("None", AutofocusMode.NONE.value)
        self._mode.addItem("Hardware", AutofocusMode.HARDWARE.value)
        self._mode.addItem("Software", AutofocusMode.SOFTWARE.value)

        self.use_af_p = QCheckBox("p")
        self.use_af_t = QCheckBox("t")
        self.use_af_g = QCheckBox("g")
        self._configure = QPushButton("Configure...")
        self._configure.setEnabled(False)
        self._configure.setToolTip(SOFTWARE_AF_OPTIONS_TOOLTIP)

        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._mode_label)
        layout.addWidget(self._mode)
        layout.addWidget(QLabel("Axis:"))
        layout.addWidget(self.use_af_p)
        layout.addWidget(self.use_af_t)
        layout.addWidget(self.use_af_g)
        layout.addWidget(self._configure)
        layout.addStretch()

        self._mode.currentIndexChanged.connect(self._on_mode_changed)
        self.use_af_p.toggled.connect(self.valueChanged)
        self.use_af_t.toggled.connect(self.valueChanged)
        self.use_af_g.toggled.connect(self.valueChanged)
        self._configure.clicked.connect(self.configureRequested)

        self._axes_allowed = True
        self._axes_disabled_tooltip = ""
        self._hardware_available = True
        self._hardware_unavailable_tooltip = ""
        self._on_mode_changed()

    def mode(self) -> AutofocusMode:
        value = self._mode.currentData()
        return AutofocusMode(str(value))

    def setMode(self, mode: AutofocusMode | str) -> None:
        mode_value = mode.value if isinstance(mode, AutofocusMode) else str(mode)
        idx = self._mode.findData(mode_value)
        if idx >= 0:
            self._mode.setCurrentIndex(idx)

    def axes(self) -> tuple[str, ...]:
        if not self._axes_enabled():
            return ()
        axes: tuple[str, ...] = ()
        if self.use_af_p.isChecked():
            axes += ("p",)
        if self.use_af_t.isChecked():
            axes += ("t",)
        if self.use_af_g.isChecked():
            axes += ("g",)
        return axes

    def setAxes(self, value: tuple[str, ...]) -> None:
        self.use_af_p.setChecked("p" in value)
        self.use_af_t.setChecked("t" in value)
        self.use_af_g.setChecked("g" in value)

    def value(self) -> dict[str, Any]:
        return {"mode": self.mode().value, "axes": self.axes()}

    def setValue(self, value: dict[str, Any]) -> None:
        if not value:
            self.setMode(AutofocusMode.NONE)
            self.setAxes(())
            return
        mode = value.get("mode", AutofocusMode.NONE.value)
        axes = tuple(value.get("axes", ()))
        with signals_blocked(self._mode):
            self.setMode(mode)
        self.setAxes(axes)
        self._on_mode_changed()

    def setAxesAllowed(self, allowed: bool, tooltip: str = "") -> None:
        self._axes_allowed = allowed
        self._axes_disabled_tooltip = tooltip
        self._update_enabled_state()

    def setHardwareAvailable(self, available: bool, tooltip: str = "") -> None:
        self._hardware_available = available
        self._hardware_unavailable_tooltip = tooltip
        if not available and self.mode() == AutofocusMode.HARDWARE:
            self.setMode(AutofocusMode.NONE)
        self._update_enabled_state()

    def _axes_enabled(self) -> bool:
        return self._axes_allowed and self.mode() is not AutofocusMode.NONE

    def _current_tooltip(self) -> str:
        if not self._axes_allowed:
            return self._axes_disabled_tooltip
        if self.mode() is AutofocusMode.HARDWARE and not self._hardware_available:
            return self._hardware_unavailable_tooltip
        return ""

    def _on_mode_changed(self) -> None:
        self._update_enabled_state()
        self.valueChanged.emit()

    def _update_enabled_state(self) -> None:
        mode = self.mode()
        axes_enabled = self._axes_enabled()
        tooltip = self._current_tooltip()
        for widget in (self.use_af_p, self.use_af_t, self.use_af_g):
            widget.setEnabled(axes_enabled)
            widget.setToolTip(tooltip)
        self._configure.setEnabled(mode is AutofocusMode.SOFTWARE and self._axes_allowed)
        if mode is AutofocusMode.SOFTWARE:
            self._configure.setToolTip(SOFTWARE_AF_OPTIONS_TOOLTIP)
        elif mode is AutofocusMode.HARDWARE and not self._hardware_available:
            self._configure.setToolTip(self._hardware_unavailable_tooltip)
        else:
            self._configure.setToolTip(SOFTWARE_AF_PENDING_TOOLTIP)
