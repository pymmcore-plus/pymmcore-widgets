from __future__ import annotations

import warnings
from typing import Any, Union

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QCheckBox, QHBoxLayout, QPushButton, QSizePolicy, QWidget
from superqt.fonticon import icon
from superqt.utils import signals_blocked

COLOR_TYPE = Union[
    QColor,
    int,
    str,
    Qt.GlobalColor,
    "tuple[int, int, int, int]",
    "tuple[int, int, int]",
]


class ShuttersWidget(QWidget):
    """A Widget to control shutters and Micro-Manager autoshutter.

    Parameters
    ----------
    shutter_device: str:
        The shutter device Label.
    autoshutter: bool
        If True, a checkbox controlling the Micro-Manager autoshutter
        is added to the layout.
    parent : QWidget | None
        Optional parent widget. By default, None.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self,
        shutter_device: str,
        autoshutter: bool = True,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self.shutter_device = shutter_device

        self._is_multiShutter = False
        self.autoshutter = autoshutter

        self._icon_open: str = MDI6.hexagon_outline
        self._icon_closed: str = MDI6.hexagon_slice_6
        self._icon_color_open: COLOR_TYPE = (0, 255, 0)
        self._icon_color_closed: COLOR_TYPE = "magenta"
        self._icon_size: int = 25
        self._button_text_open: str = ""
        self._button_text_closed: str = ""

        self._create_wdg()

        self._refresh_shutter_widget()

        self._mmc.events.systemConfigurationLoaded.connect(self._refresh_shutter_widget)
        self._mmc.events.autoShutterSet.connect(self._on_autoshutter_changed)
        self._mmc.events.propertyChanged.connect(self._on_shutter_device_changed)
        self._mmc.events.propertyChanged.connect(self._on_shutter_state_changed)
        self._mmc.events.configSet.connect(self._on_channel_set)
        self._mmc.events.continuousSequenceAcquisitionStarted.connect(
            self._on_live_mode
        )
        self._mmc.events.sequenceAcquisitionStarted.connect(self._on_live_mode)
        self._mmc.events.sequenceAcquisitionStopped.connect(self._on_live_mode)

        self.destroyed.connect(self._disconnect)

    @property
    def icon_open(self) -> str:
        """
        Set the icon of the QPushButton when the shutter is open.

        The icon_open.setter icon string should be any key recognizable as
        a superqt fonticon (e.g. mdi6.abacus).
        Default = MDI6.hexagon_outline (https://github.com/templarian/MaterialDesign).
        Note that MDI6 is installed by default, you must install other fonts
        if you want to use them.
        """
        return self._icon_open

    @icon_open.setter
    def icon_open(self, icon_o: str) -> None:
        if self._mmc.getShutterOpen(self.shutter_device):
            self.shutter_button.setIcon(icon(icon_o, color=self._icon_color_open))
        self._icon_open = icon_o

    @property
    def icon_closed(self) -> str:
        """
        Set the icon of the QPushButton when the shutter is closed.

        The icon_closed.setter icon string should be any key recognizable as
        a superqt fonticon (e.g. mdi6.abacus).
        Default = MDI6.hexagon_slice_6 (https://github.com/templarian/MaterialDesign).
        Note that MDI6 is installed by default, you must install other fonts
        if you want to use them.
        """
        return self._icon_closed

    @icon_closed.setter
    def icon_closed(self, icon_c: str) -> None:
        if not self._mmc.getShutterOpen(self.shutter_device):
            self.shutter_button.setIcon(icon(icon_c, color=self._icon_color_closed))
        self._icon_closed = icon_c

    @property
    def icon_color_open(self) -> COLOR_TYPE:
        """
        Set the button icon color for when the shutter is open.

        Default = (0, 255, 0)

        COLOR_TYPE = Union[QColor, int, str, Qt.GlobalColor, tuple[int, int, int, int],
        tuple[int, int, int]]
        """
        return self._icon_color_open

    @icon_color_open.setter
    def icon_color_open(self, color: COLOR_TYPE) -> None:
        if self._mmc.getShutterOpen(self.shutter_device):
            self.shutter_button.setIcon(icon(self._icon_open, color=color))
        self._icon_color_open = color

    @property
    def icon_color_closed(self) -> COLOR_TYPE:
        """
        Set the button icon color for when the shutter is closed.

        Default = 'magenta'

        COLOR_TYPE = Union[QColor, int, str, Qt.GlobalColor, tuple[int, int, int, int],
        tuple[int, int, int]]
        """
        return self._icon_color_closed

    @icon_color_closed.setter
    def icon_color_closed(self, color: COLOR_TYPE) -> None:
        if not self._mmc.getShutterOpen(self.shutter_device):
            self.shutter_button.setIcon(icon(self._icon_closed, color=color))
        self._icon_color_closed = color

    @property
    def icon_size(self) -> int:
        """
        Set the button icon size.

        Default = 25
        """
        return self._icon_size

    @icon_size.setter
    def icon_size(self, size: int) -> None:
        self.shutter_button.setIconSize(QSize(size, size))
        self._icon_size = size

    @property
    def button_text_open(self) -> str:
        """
        Set the button text for when the shutter is open.

        Default = ''
        """
        return self._button_text_open

    @button_text_open.setter
    def button_text_open(self, text: str) -> None:
        if self._mmc.getShutterOpen(self.shutter_device):
            self.shutter_button.setText(text)
        self._button_text_open = text

    @property
    def button_text_closed(self) -> str:
        """
        Set the button text for when the shutter is closed.

        Default = ''
        """
        return self._button_text_closed

    @button_text_closed.setter
    def button_text_closed(self, text: str) -> None:
        if not self._mmc.getShutterOpen(self.shutter_device):
            self.shutter_button.setText(text)
        self._button_text_closed = text

    def _create_wdg(self) -> None:
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(3)

        self.shutter_button = QPushButton(text=self._button_text_closed)
        sizepolicy_btn = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.shutter_button.setSizePolicy(sizepolicy_btn)
        self.shutter_button.setIcon(
            icon(self._icon_closed, color=self._icon_color_closed)
        )
        self.shutter_button.setIconSize(QSize(self._icon_size, self._icon_size))
        self.shutter_button.clicked.connect(self._on_shutter_btn_clicked)
        main_layout.addWidget(self.shutter_button)

        self.autoshutter_checkbox = QCheckBox(text="Auto")
        sizepolicy_checkbox = QSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.autoshutter_checkbox.setSizePolicy(sizepolicy_checkbox)
        self.autoshutter_checkbox.setChecked(False)
        self.autoshutter_checkbox.toggled.connect(self._on_shutter_checkbox_toggled)
        main_layout.addWidget(self.autoshutter_checkbox)

        if not self.autoshutter:
            self.autoshutter_checkbox.hide()

        self.setLayout(main_layout)

    def _on_system_cfg_loaded(self) -> None:
        self._refresh_shutter_widget()

    def _refresh_shutter_widget(self) -> None:
        if self.shutter_device not in self._mmc.getLoadedDevicesOfType(
            DeviceType.ShutterDevice
        ):
            if self.shutter_device != "":
                warnings.warn(
                    f"No device with label {self.shutter_device}!", stacklevel=2
                )
            self.shutter_button.setText("None")
            self.shutter_button.setEnabled(False)
            if self.autoshutter:
                self.autoshutter_checkbox.setEnabled(False)
        else:
            if self.autoshutter:
                self.autoshutter_checkbox.setEnabled(True)
                self.autoshutter_checkbox.setChecked(self._mmc.getAutoShutter())
            else:
                self.autoshutter_checkbox.setChecked(False)
            if self._mmc.getShutterDevice() == self.shutter_device:
                self.shutter_button.setEnabled(not self._mmc.getAutoShutter())
            else:
                self.shutter_button.setEnabled(True)
            if self._mmc.getShutterOpen(self.shutter_device):
                self._set_shutter_wdg_to_opened()
            else:
                self._set_shutter_wdg_to_closed()

            # bool to define if the shutter_device is a Micro-Manager 'Multi Shutter'
            props = self._mmc.getDevicePropertyNames(self.shutter_device)
            self._is_multiShutter = bool([x for x in props if "Physical Shutter" in x])

    def _on_shutter_state_changed(
        self, dev_name: str, prop_name: str, value: Any
    ) -> None:
        if dev_name != self.shutter_device or prop_name != "State":
            return
        state = value in [True, "1"]
        (
            self._set_shutter_wdg_to_opened()
            if state
            else self._set_shutter_wdg_to_closed()
        )
        if self._is_multiShutter:
            for i in range(1, 6):
                value = self._mmc.getProperty(
                    self.shutter_device, f"Physical Shutter {i}"
                )
                if value != "Undefined":
                    self._mmc.events.propertyChanged.emit(value, "State", state)

    def _on_shutter_device_changed(
        self, dev_name: str, prop_name: str, value: Any
    ) -> None:
        if dev_name != "Core" and prop_name != "Shutter":
            return

        if value != self.shutter_device:
            self.shutter_button.setEnabled(True)
        else:
            self.shutter_button.setEnabled(not self._mmc.getAutoShutter())

    def _on_live_mode(self) -> None:
        if not self._mmc.getShutterOpen(self.shutter_device):
            self._set_shutter_wdg_to_closed()
        else:
            self._set_shutter_wdg_to_opened()

    def _on_channel_set(self, group: str, preset: str) -> None:
        if (
            self._mmc.getShutterDevice() == self.shutter_device
        ) and self._mmc.getAutoShutter():
            self.shutter_button.setEnabled(False)
        else:
            self.shutter_button.setEnabled(True)

    def _on_shutter_btn_clicked(self) -> None:
        if self._mmc.getShutterOpen(self.shutter_device):
            self._close_shutter(self.shutter_device)
        else:
            self._open_shutter(self.shutter_device)

        if self._is_multiShutter:
            for shutter in self._mmc.getLoadedDevicesOfType(DeviceType.Shutter):
                if shutter == self.shutter_device:
                    continue
                if self._mmc.getShutterOpen(shutter):
                    self._mmc.events.propertyChanged.emit(shutter, "State", True)
                else:
                    self._mmc.events.propertyChanged.emit(shutter, "State", False)

    def _on_autoshutter_changed(self, state: bool) -> None:
        if self.autoshutter:
            with signals_blocked(self.autoshutter_checkbox):
                self.autoshutter_checkbox.setChecked(state)
        if self._mmc.getShutterDevice() == self.shutter_device:
            self.shutter_button.setEnabled(not state)

    def _close_shutter(self, shutter: str) -> None:
        self._set_shutter_wdg_to_closed()
        self._mmc.setShutterOpen(shutter, False)

    def _open_shutter(self, shutter: str) -> None:
        self._set_shutter_wdg_to_opened()
        self._mmc.setShutterOpen(shutter, True)

    def _on_shutter_checkbox_toggled(self, state: bool) -> None:
        self._mmc.setAutoShutter(state)

    def _set_shutter_wdg_to_opened(self) -> None:
        self.shutter_button.setText(self._button_text_open)
        self.shutter_button.setIcon(icon(self._icon_open, color=self._icon_color_open))

    def _set_shutter_wdg_to_closed(self) -> None:
        self.shutter_button.setText(self._button_text_closed)
        self.shutter_button.setIcon(
            icon(self._icon_closed, color=self._icon_color_closed)
        )

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(
            self._refresh_shutter_widget
        )
        self._mmc.events.autoShutterSet.disconnect(self._on_autoshutter_changed)
        self._mmc.events.propertyChanged.disconnect(self._on_shutter_device_changed)
        self._mmc.events.propertyChanged.disconnect(self._on_shutter_state_changed)
        self._mmc.events.configSet.disconnect(self._on_channel_set)
