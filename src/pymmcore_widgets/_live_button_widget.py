from __future__ import annotations

from typing import Union

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QPushButton, QWidget
from superqt.fonticon import icon

COLOR_TYPE = Union[
    QColor,
    int,
    str,
    Qt.GlobalColor,
    "tuple[int, int, int, int]",
    "tuple[int, int, int]",
]


class LiveButton(QPushButton):
    """A Widget to create a two-state (on-off) live mode QPushButton.

    When pressed, a 'ContinuousSequenceAcquisition' is started or stopped
    and a pymmcore-plus signal
    [`continuousSequenceAcquisitionStarted`][pymmcore_plus.core.events._protocol.PCoreSignaler.continuousSequenceAcquisitionStarted]
    or
    [`sequenceAcquisitionStopped`][pymmcore_plus.core.events._protocol.PCoreSignaler.sequenceAcquisitionStopped]
    is emitted.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].

    Examples
    --------
    !!! example "Combining `LiveButton` with other widgets"

        see [ImagePreview](../ImagePreview#example)
    """

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._button_text_on: str = "Live"
        self._button_text_off: str = "Stop"
        self._icon_color_on: COLOR_TYPE = (0, 255, 0)
        self._icon_color_off: COLOR_TYPE = "magenta"

        self.streaming_timer = None

        self._mmc.events.systemConfigurationLoaded.connect(self._on_system_cfg_loaded)
        self._on_system_cfg_loaded()
        self._mmc.events.continuousSequenceAcquisitionStarted.connect(
            self._on_sequence_started
        )
        self._mmc.events.sequenceAcquisitionStopped.connect(self._on_sequence_stopped)
        self.destroyed.connect(self._disconnect)

        self._create_button()

        self.setEnabled(False)
        if len(self._mmc.getLoadedDevices()) > 1:
            self.setEnabled(True)

    @property
    def button_text_on(self) -> str:
        """
        Set the live button text for when live mode is on.

        Default = "Live."
        """
        return self._button_text_on

    @button_text_on.setter
    def button_text_on(self, text: str) -> None:
        if not self._mmc.isSequenceRunning():
            self.setText(text)
        self._button_text_on = text

    @property
    def button_text_off(self) -> str:
        """
        Set the live button text for when live mode is off.

        Default = "Stop."
        """
        return self._button_text_off

    @button_text_off.setter
    def button_text_off(self, text: str) -> None:
        if self._mmc.isSequenceRunning():
            self.setText(text)
        self._button_text_off = text

    @property
    def icon_color_on(self) -> COLOR_TYPE:
        """
        Set the live button color for when live mode is on.

        Default = (0. 255, 0).
        """
        return self._icon_color_on

    @icon_color_on.setter
    def icon_color_on(self, color: COLOR_TYPE) -> None:
        if not self._mmc.isSequenceRunning():
            self.setIcon(icon(MDI6.video_outline, color=color))
        self._icon_color_on = color

    @property
    def icon_color_off(self) -> COLOR_TYPE:
        """
        Set the live button color for when live mode is off.

        Default = "magenta".
        """
        return self._icon_color_off

    @icon_color_off.setter
    def icon_color_off(self, color: COLOR_TYPE) -> None:
        if self._mmc.isSequenceRunning():
            self.setIcon(icon(MDI6.video_off_outline, color=color))
        self._icon_color_off = color

    def _create_button(self) -> None:
        if self._button_text_on:
            self.setText(self._button_text_on)
        self._set_icon_state(False)
        self.setIconSize(QSize(30, 30))
        self.clicked.connect(self._toggle_live_mode)

    def _on_system_cfg_loaded(self) -> None:
        self.setEnabled(bool(self._mmc.getCameraDevice()))

    def _toggle_live_mode(self) -> None:
        """Start/stop SequenceAcquisition."""
        if self._mmc.isSequenceRunning():
            self._mmc.stopSequenceAcquisition()
            self._set_icon_state(False)
        else:
            self._mmc.startContinuousSequenceAcquisition()  # pymmcore-plus method
            self._set_icon_state(True)

    def _set_icon_state(self, state: bool) -> None:
        """Set the icon in the on or off state."""
        if state:  # set in the off mode
            self.setIcon(icon(MDI6.video_off_outline, color=self._icon_color_off))
            self.setText(self._button_text_off)
        else:  # set in the on mode
            self.setIcon(icon(MDI6.video_outline, color=self._icon_color_on))
            self.setText(self._button_text_on)

    def _on_sequence_started(self) -> None:
        self._set_icon_state(True)

    def _on_sequence_stopped(self, camera: str) -> None:
        self._set_icon_state(False)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(
            self._on_system_cfg_loaded
        )
        self._mmc.events.continuousSequenceAcquisitionStarted.disconnect(
            self._on_sequence_started
        )
        self._mmc.events.sequenceAcquisitionStopped.disconnect(
            self._on_sequence_stopped
        )
