from __future__ import annotations

import warnings
from typing import Any, Union

from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QColor, QIcon
from qtpy.QtWidgets import QCheckBox, QHBoxLayout, QPushButton, QSizePolicy, QWidget
from superqt.iconify import QIconifyIcon
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
    shutter_device : str
        The shutter device Label.
    autoshutter : bool
        If True, a checkbox controlling the Micro-Manager autoshutter
        is added to the layout.
    button_text_open : str
        Text shown on the button when the shutter is open.
    button_text_closed : str
        Text shown on the button when the shutter is closed.
    icon_open : str
        Iconify icon key for the open state.
    icon_closed : str
        Iconify icon key for the closed state.
    icon_color_open : COLOR_TYPE
        Icon color for the open state.
    icon_color_closed : COLOR_TYPE
        Icon color for the closed state.
    icon_size : int
        Icon size in pixels.
    parent : QWidget | None
        Optional parent widget.
    mmcore : CMMCorePlus | None
        Optional CMMCorePlus micromanager core.
    """

    def __init__(
        self,
        shutter_device: str,
        *,
        autoshutter: bool = True,
        button_text_open: str = "",
        button_text_closed: str = "",
        icon_open: str = "mdi:hexagon-outline",
        icon_closed: str = "mdi:hexagon-slice-6",
        icon_color_open: COLOR_TYPE = "green",
        icon_color_closed: COLOR_TYPE = "gray",
        icon_size: int = 25,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()
        self.shutter_device = shutter_device
        self._is_open = False
        self._show_autoshutter = autoshutter
        self._button_text_open = button_text_open
        self._button_text_closed = button_text_closed

        # Pre-cache icons
        self._icon_open: QIcon = QIconifyIcon(icon_open, color=icon_color_open)
        self._icon_closed: QIcon = QIconifyIcon(icon_closed, color=icon_color_closed)

        # Build UI
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        self.shutter_button = QPushButton(text=button_text_closed)
        self.shutter_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.shutter_button.setIcon(self._icon_closed)
        self.shutter_button.setIconSize(QSize(icon_size, icon_size))
        self.shutter_button.clicked.connect(self._on_shutter_btn_clicked)
        layout.addWidget(self.shutter_button)

        self.autoshutter_checkbox = QCheckBox(text="Auto")
        self.autoshutter_checkbox.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.autoshutter_checkbox.toggled.connect(self._on_shutter_checkbox_toggled)
        if not autoshutter:
            self.autoshutter_checkbox.hide()
        layout.addWidget(self.autoshutter_checkbox)

        self.setLayout(layout)

        # Read current state BEFORE connecting signals, so deferred C++
        # callbacks (from prior loadSystemConfiguration etc.) that fire during
        # GIL-releasing C++ calls inside _refresh() have no handler to call.
        self._initializing = True
        self._refresh()
        self._initializing = False

        self._mmc.events.systemConfigurationLoaded.connect(self._refresh)
        self._mmc.events.autoShutterSet.connect(self._on_autoshutter_changed)
        # shutterOpenChanged is relayed from the C++ OnShutterOpenChanged callback,
        # which fires for ALL shutter state changes: direct setShutterOpen calls,
        # Multi Shutter sub-shutter propagation, and autoShutter open/close during
        # sequence acquisition. propertyChanged only fires from the Python-level
        # setShutterOpen override, missing the latter two cases.
        self._mmc.events.shutterOpenChanged.connect(self._on_shutter_open_changed)
        # propertyChanged is still needed for Core/Shutter device reassignment.
        self._mmc.events.propertyChanged.connect(self._on_core_property_changed)
        self._mmc.events.configSet.connect(self._on_config_set)

        self.destroyed.connect(self._disconnect)

    def _refresh(self) -> None:
        """Full widget refresh from current core state."""
        loaded = self._mmc.getLoadedDevicesOfType(DeviceType.ShutterDevice)
        if self.shutter_device not in loaded:
            if self.shutter_device != "":
                warnings.warn(
                    f"No device with label {self.shutter_device}!", stacklevel=2
                )
            self.shutter_button.setText("None")
            self.shutter_button.setEnabled(False)
            if self._show_autoshutter:
                self.autoshutter_checkbox.setEnabled(False)
            return

        if self._show_autoshutter:
            self.autoshutter_checkbox.setEnabled(True)
            with signals_blocked(self.autoshutter_checkbox):
                self.autoshutter_checkbox.setChecked(self._mmc.getAutoShutter())
        else:
            with signals_blocked(self.autoshutter_checkbox):
                self.autoshutter_checkbox.setChecked(False)

        self._is_open = self._mmc.getShutterOpen(self.shutter_device)
        self._update_ui()
        self._update_button_enabled()

    def _update_ui(self) -> None:
        """Update button icon and text from local _is_open state only."""
        if self._is_open:
            self.shutter_button.setText(self._button_text_open)
            self.shutter_button.setIcon(self._icon_open)
        else:
            self.shutter_button.setText(self._button_text_closed)
            self.shutter_button.setIcon(self._icon_closed)

    def _update_button_enabled(self) -> None:
        """Update button enabled state based on autoshutter and core shutter."""
        if self._mmc.getShutterDevice() == self.shutter_device:
            self.shutter_button.setEnabled(not self._mmc.getAutoShutter())
        else:
            self.shutter_button.setEnabled(True)

    def _on_shutter_open_changed(self, dev: str, is_open: bool) -> None:
        if self._initializing or dev != self.shutter_device:
            return
        self._is_open = is_open
        self._update_ui()

    def _on_core_property_changed(self, dev: str, prop: str, value: Any) -> None:
        if self._initializing:
            return
        if dev == "Core" and prop == "Shutter":
            self._update_button_enabled()

    def _on_autoshutter_changed(self, state: bool) -> None:
        if self._initializing:
            return
        if self._show_autoshutter:
            with signals_blocked(self.autoshutter_checkbox):
                self.autoshutter_checkbox.setChecked(state)
        self._update_button_enabled()

    def _on_config_set(self, group: str, preset: str) -> None:
        if self._initializing:
            return
        self._update_button_enabled()

    def _on_shutter_btn_clicked(self) -> None:
        new_state = not self._is_open
        self._mmc.setShutterOpen(self.shutter_device, new_state)

    def _on_shutter_checkbox_toggled(self, state: bool) -> None:
        self._mmc.setAutoShutter(state)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._refresh)
        self._mmc.events.autoShutterSet.disconnect(self._on_autoshutter_changed)
        self._mmc.events.shutterOpenChanged.disconnect(self._on_shutter_open_changed)
        self._mmc.events.propertyChanged.disconnect(self._on_core_property_changed)
        self._mmc.events.configSet.disconnect(self._on_config_set)
