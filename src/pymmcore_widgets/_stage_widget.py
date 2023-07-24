from __future__ import annotations

from itertools import chain, product, repeat
from typing import ClassVar

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import setTextIcon
from superqt.utils import signals_blocked

AlignCenter = Qt.AlignmentFlag.AlignCenter
PREFIX = MDI6.__name__.lower()
STAGE_DEVICES = {DeviceType.Stage, DeviceType.XYStage}
STYLE = """
QPushButton {
    border: none;
    background: transparent;
    color: rgb(0, 180, 0);
    font-size: 40px;
}
QPushButton:hover:!pressed {
    color: rgb(0, 255, 0);
}
QPushButton:pressed {
    color: rgb(0, 100, 0);
}
QSpinBox {
    min-width: 35px;
    height: 22px;
}
QLabel {
    color: #999;
}
QCheckBox {
    color: #999;
}
QCheckBox::indicator {
    width: 11px;
    height: 11px;
}
"""


class StageWidget(QWidget):
    """A Widget to control a XY and/or a Z stage.

    Parameters
    ----------
    device: str:
        Stage device.
    levels: int | None:
        Number of "arrow" buttons per widget per direction, by default, 2.
    parent : QWidget | None
        Optional parent widget.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    # fmt: off
    BTNS: ClassVar[ dict]= {
        # btn glyph                (r, c, xmag, ymag)
        MDI6.chevron_triple_up:    (0, 3,  0,  3),
        MDI6.chevron_double_up:    (1, 3,  0,  2),
        MDI6.chevron_up:           (2, 3,  0,  1),
        MDI6.chevron_down:         (4, 3,  0, -1),
        MDI6.chevron_double_down:  (5, 3,  0, -2),
        MDI6.chevron_triple_down:  (6, 3,  0, -3),
        MDI6.chevron_triple_left:  (3, 0, -3,  0),
        MDI6.chevron_double_left:  (3, 1, -2,  0),
        MDI6.chevron_left:         (3, 2, -1,  0),
        MDI6.chevron_right:        (3, 4,  1,  0),
        MDI6.chevron_double_right: (3, 5,  2,  0),
        MDI6.chevron_triple_right: (3, 6,  3,  0),
    }
    BTN_SIZE = 30
    # fmt: on

    def __init__(
        self,
        device: str,
        levels: int | None = 2,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ):
        super().__init__(parent=parent)

        self.setStyleSheet(STYLE)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._levels = levels
        self._device = device
        self._dtype = self._mmc.getDeviceType(self._device)
        assert self._dtype in STAGE_DEVICES, f"{self._dtype} not in {STAGE_DEVICES}"

        self._create_widget()

        self._connect_events()

        self._set_as_default()

        self.destroyed.connect(self._disconnect)

    def _create_widget(self) -> None:
        self._step = QDoubleSpinBox()
        self._step.setValue(10)
        self._step.setMaximum(9999)
        self._step.valueChanged.connect(self._update_ttips)
        self._step.clearFocus()
        self._step.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, 0)
        self._step.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self._step.setAlignment(AlignCenter)

        self._btns = QWidget()
        self._btns.setLayout(QGridLayout())
        self._btns.layout().setContentsMargins(0, 0, 0, 0)
        self._btns.layout().setSpacing(0)
        for glpyh, (row, col, *_) in self.BTNS.items():
            btn = QPushButton()
            btn.setAutoRepeat(True)
            btn.setFlat(True)
            btn.setFixedSize(self.BTN_SIZE, self.BTN_SIZE)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            setTextIcon(btn, glpyh)
            btn.clicked.connect(self._on_click)
            self._btns.layout().addWidget(btn, row, col, AlignCenter)

        self._btns.layout().addWidget(self._step, 3, 3, AlignCenter)
        self._set_visible_levels(self._levels)  # type: ignore
        self._set_xy_visible()
        self._update_ttips()

        self._readout = QLabel()
        self._readout.setAlignment(AlignCenter)
        self._update_position_label()

        self._poll_cb = QCheckBox("poll")
        self._poll_cb.setMaximumWidth(50)
        self._poll_timer = QTimer()
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._update_position_label)
        self._poll_cb.toggled.connect(self._toggle_poll_timer)

        self.snap_checkbox = QCheckBox(text="Snap on Click")

        self.radiobutton = QRadioButton(text="Set as Default")
        self.radiobutton.toggled.connect(self._on_radiobutton_toggled)

        top_row = QWidget()
        top_row_layout = QHBoxLayout()
        top_row_layout.setAlignment(AlignCenter)
        top_row.setLayout(top_row_layout)
        top_row.layout().addWidget(self.radiobutton)

        bottom_row_1 = QWidget()
        bottom_row_1.setLayout(QHBoxLayout())
        bottom_row_1.layout().addWidget(self._readout)

        bottom_row_2 = QWidget()
        bottom_row_2_layout = QHBoxLayout()
        bottom_row_2_layout.setSpacing(10)
        bottom_row_2_layout.setContentsMargins(0, 0, 0, 0)
        bottom_row_2_layout.setAlignment(AlignCenter)
        bottom_row_2.setLayout(bottom_row_2_layout)
        bottom_row_2.layout().addWidget(self.snap_checkbox)
        bottom_row_2.layout().addWidget(self._poll_cb)

        self.setLayout(QVBoxLayout())
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(5, 5, 5, 5)
        self.layout().addWidget(top_row)
        self.layout().addWidget(self._btns, AlignCenter)
        self.layout().addWidget(bottom_row_1)
        self.layout().addWidget(bottom_row_2)

    def _connect_events(self) -> None:
        self._mmc.events.propertyChanged.connect(self._on_prop_changed)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_system_cfg)
        if self._dtype is DeviceType.XYStage:
            event = self._mmc.events.XYStagePositionChanged
        elif self._dtype is DeviceType.Stage:
            event = self._mmc.events.stagePositionChanged
        event.connect(self._update_position_label)

    def _enable_wdg(self, enabled: bool) -> None:
        self._step.setEnabled(enabled)
        self._btns.setEnabled(enabled)
        self.snap_checkbox.setEnabled(enabled)
        self.radiobutton.setEnabled(enabled)
        self._poll_cb.setEnabled(enabled)

    def _on_system_cfg(self) -> None:
        if self._dtype is DeviceType.XYStage:
            if self._device not in self._mmc.getLoadedDevicesOfType(DeviceType.XYStage):
                self._enable_and_update(False)
            else:
                self._enable_and_update(True)

        if self._dtype is DeviceType.Stage:
            if self._device not in self._mmc.getLoadedDevicesOfType(DeviceType.Stage):
                self._enable_and_update(False)
            else:
                self._enable_and_update(True)

        self._set_as_default()

    def _enable_and_update(self, enable: bool) -> None:
        if enable:
            self._enable_wdg(True)
            self._update_position_label()
        else:
            self._readout.setText(f"{self._device} not loaded.")
            self._enable_wdg(False)

    def _set_as_default(self) -> None:
        current_xy = self._mmc.getXYStageDevice()
        current_z = self._mmc.getFocusDevice()
        if self._dtype is DeviceType.XYStage and current_xy == self._device:
            self.radiobutton.setChecked(True)
        elif self._dtype is DeviceType.Stage and current_z == self._device:
            self.radiobutton.setChecked(True)

    def _on_radiobutton_toggled(self, state: bool) -> None:
        if self._dtype is DeviceType.XYStage:
            if state:
                self._mmc.setProperty("Core", "XYStage", self._device)
            elif (
                not state
                and len(self._mmc.getLoadedDevicesOfType(DeviceType.XYStage)) == 1
            ):
                with signals_blocked(self.radiobutton):
                    self.radiobutton.setChecked(True)
            else:
                self._mmc.setProperty("Core", "XYStage", "")

        elif self._dtype is DeviceType.Stage:
            if state:
                self._mmc.setProperty("Core", "Focus", self._device)
            elif (
                not state
                and len(self._mmc.getLoadedDevicesOfType(DeviceType.Stage)) == 1
            ):
                with signals_blocked(self.radiobutton):
                    self.radiobutton.setChecked(True)
            else:
                self._mmc.setProperty("Core", "Focus", "")

    def _on_prop_changed(self, dev: str, prop: str, val: str) -> None:
        if dev != "Core":
            return

        if self._dtype is DeviceType.XYStage and prop == "XYStage":
            with signals_blocked(self.radiobutton):
                self.radiobutton.setChecked(val == self._device)

        if self._dtype is DeviceType.Stage and prop == "Focus":
            with signals_blocked(self.radiobutton):
                self.radiobutton.setChecked(val == self._device)

    def _toggle_poll_timer(self, on: bool) -> None:
        self._poll_timer.start() if on else self._poll_timer.stop()

    def _update_position_label(self) -> None:
        if (
            self._dtype is DeviceType.XYStage
            and self._device in self._mmc.getLoadedDevicesOfType(DeviceType.XYStage)
        ):
            pos = self._mmc.getXYPosition(self._device)  # type: ignore # pymmcore wrong
            p = ", ".join(str(round(x, 2)) for x in pos)
            self._readout.setText(f"{self._device}:  {p}")
        elif (
            self._dtype is DeviceType.Stage
            and self._device in self._mmc.getLoadedDevicesOfType(DeviceType.Stage)
        ):
            p = str(round(self._mmc.getPosition(self._device), 2))
            self._readout.setText(f"{self._device}:  {p}")

    def _update_ttips(self) -> None:
        coords = chain(zip(repeat(3), range(7)), zip(range(7), repeat(3)))
        Y = {DeviceType.XYStage: "Y"}.get(self._dtype, "Z")

        btn_layout: QGridLayout = self._btns.layout()
        for r, c in coords:
            if item := btn_layout.itemAtPosition(r, c):
                if (r, c) == (3, 3):
                    continue
                if btn := item.widget():
                    xmag, ymag = self.BTNS[f"{PREFIX}.{btn.text()}"][-2:]
                    if xmag:
                        btn.setToolTip(f"move X by {self._scale(xmag)} µm")
                    elif ymag:
                        btn.setToolTip(f"move {Y} by {self._scale(ymag)} µm")

    def _set_xy_visible(self) -> None:
        if self._dtype is not DeviceType.XYStage:
            btn_layout: QGridLayout = self._btns.layout()
            for c in (0, 1, 2, 4, 5, 6):
                if item := btn_layout.itemAtPosition(3, c):
                    item.widget().hide()

    def _set_visible_levels(self, levels: int) -> None:
        """Hide upper-level stage buttons as desired. Levels must be between 1-3."""
        assert 1 <= levels <= 3, "levels must be between 1-3"
        btn_layout: QGridLayout = self._btns.layout()
        for btn in self._btns.findChildren(QPushButton):
            btn.show()
        if levels < 3:
            # hide row/col 0, 6
            for r, c in product(range(7), (0, 6)):
                if item := btn_layout.itemAtPosition(r, c):
                    item.widget().hide()
                if item := btn_layout.itemAtPosition(c, r):
                    item.widget().hide()
        if levels < 2:
            # hide row/col 1, 5
            for r, c in product(range(1, 6), (1, 5)):
                if item := btn_layout.itemAtPosition(r, c):
                    item.widget().hide()
                if item := btn_layout.itemAtPosition(c, r):
                    item.widget().hide()

    def _on_click(self) -> None:
        btn: QPushButton = self.sender()
        xmag, ymag = self.BTNS[f"{PREFIX}.{btn.text()}"][-2:]
        self._move_stage(self._scale(xmag), self._scale(ymag))

    def _move_stage(self, x: float, y: float) -> None:
        if self._dtype is DeviceType.XYStage:
            self._mmc.setRelativeXYPosition(self._device, x, y)
        else:
            self._mmc.setRelativePosition(self._device, y)
        if self.snap_checkbox.isChecked():
            self._mmc.snap()

    def _scale(self, mag: int) -> float:
        """Convert step mag of (1, 2, 3) to absolute XY units.

        Can be used to step 1x field of view, etc...
        """
        return float(mag * self._step.value())

    def _disconnect(self) -> None:
        self._mmc.events.propertyChanged.disconnect(self._on_prop_changed)
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_system_cfg)
        if self._dtype is DeviceType.XYStage:
            event = self._mmc.events.XYStagePositionChanged
        elif self._dtype is DeviceType.Stage:
            event = self._mmc.events.stagePositionChanged
        event.disconnect(self._update_position_label)
