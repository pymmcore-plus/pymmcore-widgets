from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pyconify import svg_path
from pymmcore_plus import CMMCorePlus, DeviceType, Keyword
from qtpy.QtCore import QEvent, QObject, QSize, Qt, QTimerEvent, Signal
from qtpy.QtGui import QContextMenuEvent
from qtpy.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt.iconify import QIconifyIcon
from superqt.utils import signals_blocked

from ._q_stage_controller import QStageMoveAccumulator

if TYPE_CHECKING:
    from typing import Any

CORE = Keyword.CoreDevice
XY_STAGE = Keyword.CoreXYStage
FOCUS = Keyword.CoreFocus

MOVE_BUTTONS: dict[str, tuple[int, int, int, int]] = {
    # btn glyph                (r, c, xmag, ymag)
    "mdi:chevron-triple-up": (0, 3, 0, 3),
    "mdi:chevron-double-up": (1, 3, 0, 2),
    "mdi:chevron-up": (2, 3, 0, 1),
    "mdi:chevron-down": (4, 3, 0, -1),
    "mdi:chevron-double-down": (5, 3, 0, -2),
    "mdi:chevron-triple-down": (6, 3, 0, -3),
    "mdi:chevron-triple-left": (3, 0, -3, 0),
    "mdi:chevron-double-left": (3, 1, -2, 0),
    "mdi:chevron-left": (3, 2, -1, 0),
    "mdi:chevron-right": (3, 4, 1, 0),
    "mdi:chevron-double-right": (3, 5, 2, 0),
    "mdi:chevron-triple-right": (3, 6, 3, 0),
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
        self.setStyleSheet(
            f"""
            MoveStageButton {{
                border: none;
                width: 38px;
                image: url({svg_path(glyph, color="rgb(0, 180, 0)")});
                font-size: 38px;
            }}
            MoveStageButton:hover:!pressed {{
                image: url({svg_path(glyph, color="lime")});
            }}
            MoveStageButton:pressed {{
                image: url({svg_path(glyph, color="green")});
            }}
            """
        )


class MoveStageSpinBox(QDoubleSpinBox):
    """Common behavior for SpinBoxes that move stages."""

    def __init__(
        self,
        label: str,
        minimum: float = -10000000,
        maximum: float = 10000000,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.setToolTip(f"Set {label} in µm")
        self.setSuffix(" µm")
        self.setMinimum(minimum)
        self.setMaximum(maximum)
        self.setDecimals(1)
        self.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, 0)
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # enable custom context menu handling for right-click events
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)


class HaltButton(QPushButton):
    def __init__(self, device: str, core: CMMCorePlus, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self._device = device
        self._core = core
        self.setIcon(QIconifyIcon("bi:sign-stop-fill", color="red"))
        self.setIconSize(QSize(24, 24))
        self.setToolTip("Halt stage movement")
        self.setText("STOP!")
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        self._core.stop(self._device)


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
        if not (1 <= levels <= 3):
            raise ValueError("levels must be between 1-3")

        self._levels = levels
        self._x_visible = show_x

        btn_grid = QGridLayout(self)
        btn_grid.setContentsMargins(0, 0, 0, 0)
        btn_grid.setSpacing(0)

        # Create buttons based on levels and show_x settings
        self._create_buttons_for_levels(btn_grid)

        # step size spinbox in the middle of the move buttons
        self.step_size = MoveStageSpinBox(label="step size", minimum=0)
        self.step_size.setValue(10)
        self.step_size.valueChanged.connect(self._update_tooltips)

        btn_grid.addWidget(self.step_size, 3, 3, Qt.AlignmentFlag.AlignCenter)
        self._update_tooltips()

    def _create_buttons_for_levels(self, btn_grid: QGridLayout) -> None:
        """Create only the buttons needed based on levels and x visibility."""
        for glyph, (row, col, xmag, ymag) in MOVE_BUTTONS.items():
            # Determine if this button should be created based on levels

            # Level 1: only center arrows (magnitude 1)
            # Level 2: center + double arrows (magnitude 1, 2)
            # Level 3: all arrows (magnitude 1, 2, 3)
            if xmag != 0 or ymag != 0:
                max_magnitude = abs(max(xmag, ymag, key=abs))
            else:
                max_magnitude = 0

            if max_magnitude > self._levels or (xmag != 0 and not self._x_visible):
                continue

            btn = MoveStageButton(glyph, xmag, ymag)
            btn.clicked.connect(self._on_move_btn_clicked)
            btn_grid.addWidget(btn, row, col)

    def _on_move_btn_clicked(self) -> None:
        btn = cast("MoveStageButton", self.sender())
        self.moveRequested.emit(self._scale(btn.xmag), self._scale(btn.ymag))

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
    absolute_positioning: bool | None
        If True, the position displays can be edited to set absolute positions.
        If False, the position displays cannot be edited.
    position_label_below: bool | None
        If True, the position displays will appear below the move buttons.
        If False, the position displays will appear to the right of the move buttons.
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
        absolute_positioning: bool = False,
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

        # Initialize stage controller
        self._stage_controller = QStageMoveAccumulator.for_device(
            self._device, self._mmc
        )

        # WIDGETS ------------------------------------------------

        self._move_btns = StageMovementButtons(self._levels, self._is_2axis)
        self._step = self._move_btns.step_size

        self._pos = QHBoxLayout()
        self._pos_boxes: list[MoveStageSpinBox] = []
        self._pos_menu = QMenu(self)
        self._pos_toggle_action = self._pos_menu.addAction("Enable Editing")
        self._pos_toggle_action.setCheckable(True)
        self._pos_toggle_action.setChecked(absolute_positioning)
        self._pos_toggle_action.triggered.connect(self.enable_absolute_positioning)

        if self._is_2axis:
            self._pos.addWidget(QLabel("X: "))
            self._x_pos = MoveStageSpinBox(label="X")
            self._pos_boxes.append(self._x_pos)
            self._pos.addWidget(self._x_pos)
            self._x_pos.editingFinished.connect(self._move_absolute)

        self._pos.addWidget(QLabel(f"{self._Ylabel}: "))
        self._y_pos = MoveStageSpinBox(label="Y")
        self._pos_boxes.append(self._y_pos)
        self._y_pos.editingFinished.connect(self._move_absolute)
        self._pos.addWidget(self._y_pos)

        for box in self._pos_boxes:
            box.installEventFilter(self)
        self._pos.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._halt = HaltButton(device, self._mmc, self)
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
        main_layout.addWidget(self._halt)
        main_layout.addLayout(chxbox_grid)

        # pos label can appear either below or to the right of the move buttons
        if position_label_below:
            main_layout.insertLayout(2, self._pos)
        else:
            move_btns_layout = cast("QGridLayout", self._move_btns.layout())
            move_btns_layout.addLayout(
                self._pos, 4, 4, 2, 2, Qt.AlignmentFlag.AlignBottom
            )

        if not self._is_2axis:
            self._invert_x.hide()

        # SIGNALS -----------------------------------------------

        self._set_as_default_btn.toggled.connect(self._on_radiobutton_toggled)
        self._move_btns.moveRequested.connect(self._on_move_requested)
        self._poll_cb.toggled.connect(self._toggle_poll_timer)
        self._mmc.events.propertyChanged.connect(self._on_prop_changed)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_system_cfg)
        self._stage_controller.moveFinished.connect(self._update_position_from_core)

        # INITIALIZATION ----------------------------------------

        self._update_position_from_core()
        self.enable_absolute_positioning(absolute_positioning)
        self._set_as_default()

    def step(self) -> float:
        """Return the current step size."""
        return self._step.value()  # type: ignore

    def setStep(self, step: float) -> None:
        """Set the step size."""
        self._step.setValue(step)

    def enable_absolute_positioning(self, enabled: bool) -> None:
        """Toggles whether the position spinboxes can be edited by the user.

        Parameters
        ----------
        enabled: bool:
            If True, the position spinboxes will be enabled for user editing.
            If False, the position spinboxes will be disabled for user editing.
        """
        self._pos_toggle_action.setChecked(enabled)
        for box in self._pos_boxes:
            box.setEnabled(enabled)

    def _enable_wdg(self, enabled: bool) -> None:
        self._step.setEnabled(enabled)
        self._move_btns.setEnabled(enabled)
        for box in self._pos_boxes:
            box.setEnabled(enabled and self._pos_toggle_action.isChecked())
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

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
        # NB QAbstractSpinBox has its own Context Menu handler, which conflicts
        # with the one we want to generate. So we intercept the event here >:)
        # See https://stackoverflow.com/a/71126504
        if obj in self._pos_boxes and isinstance(event, QContextMenuEvent):
            self._pos_menu.exec_(event.globalPos())
            return True
        return super().eventFilter(obj, event)  # type: ignore [no-any-return]

    def _update_position_from_core(self) -> None:
        if self._device not in self._mmc.getLoadedDevicesOfType(self._dtype):
            return
        if self._is_2axis:
            x, y = self._mmc.getXYPosition(self._device)
            self._x_pos.setValue(x)
            self._y_pos.setValue(y)
        else:
            y = self._mmc.getPosition(self._device)
            self._y_pos.setValue(y)

    def _on_move_requested(self, xmag: float, ymag: float) -> None:
        if self._invert_x.isChecked():
            xmag *= -1
        if self._invert_y.isChecked():
            ymag *= -1

        val = (xmag, ymag) if self._is_2axis else ymag
        self._do_move(val, relative=True)

    def _move_absolute(self) -> None:
        y = self._y_pos.value()
        val = (self._x_pos.value(), y) if self._is_2axis else y
        self._do_move(val, relative=False)

    def _do_move(self, val: Any, relative: bool) -> None:
        if relative:
            self._stage_controller.move_relative(val)
        else:
            self._stage_controller.move_absolute(val)
        self._stage_controller.snap_on_finish = self.snap_checkbox.isChecked()

    def _disconnect(self) -> None:
        self._mmc.events.propertyChanged.disconnect(self._on_prop_changed)
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_system_cfg)
        if self._is_2axis:
            event = self._mmc.events.XYStagePositionChanged
        else:
            event = self._mmc.events.stagePositionChanged
        event.disconnect(self._update_position_from_core)
