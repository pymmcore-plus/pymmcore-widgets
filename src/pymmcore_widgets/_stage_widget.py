from __future__ import annotations

from itertools import product
from typing import cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, DeviceType, Keyword
from qtpy.QtCore import Qt, QTimerEvent, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGridLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import setTextIcon
from superqt.utils import signals_blocked

CORE = Keyword.CoreDevice
XY_STAGE = Keyword.CoreXYStage
FOCUS = Keyword.CoreFocus

MOVE_BUTTONS: dict[str, tuple[int, int, int, int]] = {
    # btn glyph                (r, c, xmag, ymag)
    MDI6.chevron_triple_up: (0, 3, 0, 3),
    MDI6.chevron_double_up: (1, 3, 0, 2),
    MDI6.chevron_up: (2, 3, 0, 1),
    MDI6.chevron_down: (4, 3, 0, -1),
    MDI6.chevron_double_down: (5, 3, 0, -2),
    MDI6.chevron_triple_down: (6, 3, 0, -3),
    MDI6.chevron_triple_left: (3, 0, -3, 0),
    MDI6.chevron_double_left: (3, 1, -2, 0),
    MDI6.chevron_left: (3, 2, -1, 0),
    MDI6.chevron_right: (3, 4, 1, 0),
    MDI6.chevron_double_right: (3, 5, 2, 0),
    MDI6.chevron_triple_right: (3, 6, 3, 0),
}


class MoveStageButton(QPushButton):
    def __init__(self, glyph: str, xmag: int, ymag: int, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.xmag = xmag
        self.ymag = ymag
        self.setAutoRepeat(True)
        self.setFlat(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        setTextIcon(self, glyph)
        self.setStyleSheet(
            """
            MoveStageButton {
                border: none;
                background: transparent;
                color: rgb(0, 180, 0);
                font-size: 36px;
            }
            MoveStageButton:hover:!pressed {
                color: rgb(0, 255, 0);
            }
            MoveStageButton:pressed {
                color: rgb(0, 100, 0);
            }
            """
        )


class HaltButton(QPushButton):
    def __init__(self, core: CMMCorePlus, parent: QWidget | None = None):
        super().__init__("STOP!", parent=parent)
        self._core = core
        self.setStyleSheet("color: red; font-weight: bold;")
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        for stage in self._core.getLoadedDevicesOfType(DeviceType.Stage):
            self._core.stop(stage)
        for stage in self._core.getLoadedDevicesOfType(DeviceType.XYStage):
            self._core.stop(stage)


class StageMovementButtons(QWidget):
    """Grid of buttons to move a stage in 2D.

            ^
    << < [dstep] > >>
            v
    """

    moveRequested = Signal(float, float)

    def __init__(
        self, levels: int = 2, show_x: bool = True, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._levels = levels
        self._x_visible = show_x

        btn_grid = QGridLayout(self)
        btn_grid.setContentsMargins(0, 0, 0, 0)
        btn_grid.setSpacing(0)
        for glyph, (row, col, xmag, ymag) in MOVE_BUTTONS.items():
            btn = MoveStageButton(glyph, xmag, ymag)
            btn.clicked.connect(self._on_move_btn_clicked)
            btn_grid.addWidget(btn, row, col, Qt.AlignmentFlag.AlignCenter)

        # step size spinbox in the middle of the move buttons
        self.step_size = QDoubleSpinBox()
        self.step_size.setSuffix(" µm")
        self.step_size.setDecimals(1)
        self.step_size.setToolTip("Set step size in µm")
        self.step_size.setValue(10)
        self.step_size.setMaximum(99999)
        self.step_size.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, 0)
        self.step_size.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.step_size.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step_size.valueChanged.connect(self._update_tooltips)

        btn_grid.addWidget(self.step_size, 3, 3, Qt.AlignmentFlag.AlignCenter)

        self.set_visible_levels(self._levels)
        self.set_x_visible(self._x_visible)
        self._update_tooltips()

    def _on_move_btn_clicked(self) -> None:
        btn = cast("MoveStageButton", self.sender())
        self.moveRequested.emit(self._scale(btn.xmag), self._scale(btn.ymag))

    def set_visible_levels(self, levels: int) -> None:
        """Hide upper-level stage buttons as desired. Levels must be between 1-3."""
        if not (1 <= levels <= 3):
            raise ValueError("levels must be between 1-3")
        self._levels = levels

        btn_layout = cast("QGridLayout", self.layout())
        for btn in self.findChildren(MoveStageButton):
            btn.show()

        to_hide: set[tuple[int, int]] = set()
        if levels < 3:
            to_hide.update(product(range(7), (0, 6)))
        if levels < 2:
            to_hide.update(product(range(1, 6), (1, 5)))
        # add all the flipped indices as well
        to_hide.update((c, r) for r, c in list(to_hide))

        for r, c in to_hide:
            if (item := btn_layout.itemAtPosition(r, c)) and (wdg := item.widget()):
                wdg.hide()

    def set_x_visible(self, visible: bool) -> None:
        """Show or hide the horizontal buttons."""
        self._x_visible = visible
        btn_layout = cast("QGridLayout", self.layout())
        cols: list[int] = [2, 4]
        if self._levels > 1:
            cols += [1, 5]
            if self._levels > 2:
                cols += [0, 6]

        for c in cols:
            if (item := btn_layout.itemAtPosition(3, c)) and (wdg := item.widget()):
                wdg.setVisible(visible)

    def _update_tooltips(self) -> None:
        """Update tooltips for the move buttons."""
        for btn in self.findChildren(MoveStageButton):
            if xmag := btn.xmag:
                btn.setToolTip(f"move by {self._scale(xmag)} µm")
            elif ymag := btn.ymag:
                btn.setToolTip(f"move by {self._scale(ymag)} µm")

    def _scale(self, mag: int) -> float:
        """Convert step mag of (1, 2, 3) to absolute XY units.

        Can be used to step 1x field of view, etc...
        """
        return float(mag * self.step_size.value())


class StageWidget(QWidget):
    """A Widget to control a XY and/or a Z stage.

    Parameters
    ----------
    device: str:
        Stage device.
    levels: int | None:
        Number of "arrow" buttons per widget per direction, by default, 2.
    position_label_below: bool | None
        If True, the position labels will appear below the move buttons.
        If False, the position labels will appear to the right of the move buttons.
    parent : QWidget | None
        Optional parent widget.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    BTN_SIZE = 30

    def __init__(
        self,
        device: str,
        levels: int = 2,
        *,
        position_label_below: bool = True,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ):
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._levels = levels
        self._device = device
        self._poll_timer_id: int | None = None

        self._dtype = self._mmc.getDeviceType(self._device)
        if self._dtype not in {DeviceType.Stage, DeviceType.XYStage}:
            raise ValueError("This widget only supports Stage and XYStage devices.")

        self._is_2axis = self._dtype is DeviceType.XYStage
        self._Ylabel = "Y" if self._is_2axis else self._device

        # WIDGETS ------------------------------------------------

        self._move_btns = StageMovementButtons(self._levels, self._is_2axis)
        self._step = self._move_btns.step_size

        self._pos_label = QLabel()
        self._pos_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._poll_cb = QCheckBox("Poll")
        self.snap_checkbox = QCheckBox(text="Snap on Click")
        self._invert_x = QCheckBox(text="Invert X")
        self._invert_y = QCheckBox(text=f"Invert {self._Ylabel}")
        self._set_as_default_btn = QRadioButton(text="Set as Default")
        # no need to show the "set as default" button if there is only one device
        if len(self._mmc.getLoadedDevicesOfType(self._dtype)) < 2:
            self._set_as_default_btn.hide()

        # LAYOUT ------------------------------------------------

        # checkboxes below the move buttons
        chxbox_grid = QGridLayout()
        chxbox_grid.setSpacing(12)
        chxbox_grid.setContentsMargins(0, 0, 0, 0)
        chxbox_grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chxbox_grid.addWidget(self.snap_checkbox, 0, 0)
        chxbox_grid.addWidget(self._poll_cb, 0, 1)
        chxbox_grid.addWidget(self._invert_x, 1, 0)
        chxbox_grid.addWidget(self._invert_y, 1, 1)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.addWidget(self._set_as_default_btn, 0, Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self._move_btns, Qt.AlignmentFlag.AlignCenter)
        main_layout.addLayout(chxbox_grid)

        # pos label can appear either below or to the right of the move buttons
        if position_label_below:
            main_layout.insertWidget(2, self._pos_label)
        else:
            move_btns_layout = cast("QGridLayout", self._move_btns.layout())
            move_btns_layout.addLayout(
                self._pos_label, 4, 4, 2, 2, Qt.AlignmentFlag.AlignBottom
            )

        if not self._is_2axis:
            self._invert_x.hide()

        # SIGNALS -----------------------------------------------

        self._set_as_default_btn.toggled.connect(self._on_radiobutton_toggled)
        self._move_btns.moveRequested.connect(self._on_move_requested)
        self._poll_cb.toggled.connect(self._toggle_poll_timer)
        self._mmc.events.propertyChanged.connect(self._on_prop_changed)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_system_cfg)
        if self._is_2axis:
            pos_event = self._mmc.events.XYStagePositionChanged
        else:
            pos_event = self._mmc.events.stagePositionChanged
        pos_event.connect(self._update_position_from_core)
        self.destroyed.connect(self._disconnect)

        # INITIALIZATION ----------------------------------------

        self._update_position_from_core()
        self._set_as_default()

    def step(self) -> float:
        """Return the current step size."""
        return self._step.value()  # type: ignore

    def setStep(self, step: float) -> None:
        """Set the step size."""
        self._step.setValue(step)

    def _enable_wdg(self, enabled: bool) -> None:
        self._step.setEnabled(enabled)
        self._move_btns.setEnabled(enabled)
        self.snap_checkbox.setEnabled(enabled)
        self._set_as_default_btn.setEnabled(enabled)
        self._poll_cb.setEnabled(enabled)

    def _on_system_cfg(self) -> None:
        if self._device in self._mmc.getLoadedDevicesOfType(self._dtype):
            self._enable_wdg(True)
            self._update_position_from_core()
        else:
            self._enable_wdg(False)
        self._set_as_default()

    def _set_as_default(self) -> None:
        if self._dtype is DeviceType.XYStage:
            if self._mmc.getXYStageDevice() == self._device:
                self._set_as_default_btn.setChecked(True)
        elif self._dtype is DeviceType.Stage:
            if self._mmc.getFocusDevice() == self._device:
                self._set_as_default_btn.setChecked(True)

    def _on_radiobutton_toggled(self, state: bool) -> None:
        prop = XY_STAGE if self._is_2axis else FOCUS
        if state:
            self._mmc.setProperty(CORE, prop, self._device)
        elif len(self._mmc.getLoadedDevicesOfType(self._dtype)) == 1:
            with signals_blocked(self._set_as_default_btn):
                self._set_as_default_btn.setChecked(True)
        else:
            self._mmc.setProperty(CORE, prop, "")

    def _on_prop_changed(self, dev: str, prop: str, val: str) -> None:
        if (
            (dev != CORE)
            or (self._is_2axis and prop != XY_STAGE)
            or (not self._is_2axis and prop != FOCUS)
        ):
            return
        with signals_blocked(self._set_as_default_btn):
            self._set_as_default_btn.setChecked(val == self._device)

    def _toggle_poll_timer(self, on: bool) -> None:
        if on:
            if self._poll_timer_id is None:
                self._poll_timer_id = self.startTimer(500)
        else:
            if self._poll_timer_id is not None:
                self.killTimer(self._poll_timer_id)
                self._poll_timer_id = None

    def timerEvent(self, event: QTimerEvent | None) -> None:
        if event and event.timerId() == self._poll_timer_id:
            self._update_position_from_core()
        super().timerEvent(event)

    def _update_position_from_core(self) -> None:
        if self._device not in self._mmc.getLoadedDevicesOfType(self._dtype):
            return
        if self._is_2axis:
            x, y = self._mmc.getXYPosition(self._device)
            lbl = f"X: {x:.01f}  {self._Ylabel}: {y:.01f}"
        else:
            lbl = f"{self._Ylabel}: {self._mmc.getPosition(self._device):.01f}"
        self._pos_label.setText(lbl)

    def _on_move_requested(self, xmag: float, ymag: float) -> None:
        if self._invert_x.isChecked():
            xmag *= -1
        if self._invert_y.isChecked():
            ymag *= -1
        self._move_stage(xmag, ymag)

    def _move_stage(self, x: float, y: float) -> None:
        try:
            if self._is_2axis:
                self._mmc.setRelativeXYPosition(self._device, x, y)
            else:
                self._mmc.setRelativePosition(self._device, y)
        except Exception as e:
            self._mmc.logMessage(f"Error moving stage: {e}")
        else:
            if self.snap_checkbox.isChecked():
                self._mmc.snap()

    def _disconnect(self) -> None:
        self._mmc.events.propertyChanged.disconnect(self._on_prop_changed)
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_system_cfg)
        if self._is_2axis:
            event = self._mmc.events.XYStagePositionChanged
        else:
            event = self._mmc.events.stagePositionChanged
        event.disconnect(self._update_position_from_core)
