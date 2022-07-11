from __future__ import annotations

from typing import Any, Optional, Tuple, Union

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy import QtWidgets as QtW
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QColor, QIcon
from superqt.fonticon import icon
from superqt.utils import signals_blocked

from ._core import get_core_singleton

COLOR_TYPE = Union[
    QColor,
    int,
    str,
    Qt.GlobalColor,
    Tuple[int, int, int, int],
    Tuple[int, int, int],
]


class ShuttersWidget(QtW.QWidget):
    """A Widget for shutters and Micro-Manager autoshutter.

    Parameters
    ----------
    shutter_device: str:
        The shutter device Label.
    autoshutter: bool
        If True, a checkbox controlling the Micro-Manager autoshutter
        is added to the layout.
    button_text_open_closed: Optional[tuple[str, str]]
       Text of the QPushButton when the shutter is open or closed
    icon_size : Optional[str]
        Size of the QPushButton icon.
    icon_color_open_closed : Optional[tuple[COLOR_TYPE, COLOR_TYPE]]
        Color of the QPushButton icon when the shutter is open or closed.
    text_color_combo:
        Text color of the shutter QComboBox.
    parent : Optional[QWidget]
        Optional parent widget.

    COLOR_TYPE = Union[QColor, int, str, Qt.GlobalColor, Tuple[int, int, int, int],
    Tuple[int, int, int]]
    """

    def __init__(
        self,
        shutter_device: str,
        autoshutter: bool = True,
        button_text_open_closed: Tuple[str, str] = (None, None),  # type: ignore
        icon_open_closed: Tuple[QIcon, QIcon] = (
            MDI6.hexagon_outline,
            MDI6.hexagon_slice_6,
        ),
        icon_size: int = 25,
        icon_color_open_closed: tuple[COLOR_TYPE, COLOR_TYPE] = ("", ""),
        text_color_combo: COLOR_TYPE = "",
        parent: Optional[QtW.QWidget] = None,
        *,
        mmcore: Optional[CMMCorePlus] = None,
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or get_core_singleton()

        self.shutter_device = shutter_device
        self._is_multiShutter = False
        self.autoshutter = autoshutter
        self.icon_open = icon_open_closed[0]
        self.icon_closed = icon_open_closed[1]
        self.button_text_open = button_text_open_closed[0]
        self.button_text_closed = button_text_open_closed[1]
        self.icon_size = icon_size
        self.icon_color_open = icon_color_open_closed[0]
        self.icon_color_closed = icon_color_open_closed[1]
        self.text_color_combo = text_color_combo

        self._create_wdg()

        self._refresh_shutter_widget()

        self._mmc.events.systemConfigurationLoaded.connect(self._refresh_shutter_widget)
        self._mmc.events.autoShutterSet.connect(self._on_autoshutter_changed)
        self._mmc.events.propertyChanged.connect(self._on_prop_changed)
        self._mmc.events.startContinuousSequenceAcquisition.connect(
            self._on_seq_started
        )
        self._mmc.events.startSequenceAcquisition.connect(self._on_seq_started)
        self._mmc.events.stopSequenceAcquisition.connect(self._on_seq_stopped)
        self._mmc.events.imageSnapped.connect(self._on_seq_stopped)

        self.destroyed.connect(self._disconnect)

    def _create_wdg(self) -> None:

        main_layout = QtW.QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(3)

        self.shutter_button = QtW.QPushButton(text=self.button_text_closed)
        sizepolicy_btn = QtW.QSizePolicy(QtW.QSizePolicy.Fixed, QtW.QSizePolicy.Fixed)
        self.shutter_button.setSizePolicy(sizepolicy_btn)
        self.shutter_button.setIcon(
            icon(self.icon_closed, color=self.icon_color_closed)
        )
        self.shutter_button.setIconSize(QSize(self.icon_size, self.icon_size))
        self.shutter_button.clicked.connect(self._on_shutter_btn_clicked)
        main_layout.addWidget(self.shutter_button)

        if self.autoshutter:
            self.autoshutter_checkbox = QtW.QCheckBox(text="Auto")
            sizepolicy_checkbox = QtW.QSizePolicy(
                QtW.QSizePolicy.Fixed, QtW.QSizePolicy.Fixed
            )
            self.autoshutter_checkbox.setSizePolicy(sizepolicy_checkbox)
            self.autoshutter_checkbox.setChecked(False)
            self.autoshutter_checkbox.toggled.connect(self._on_shutter_checkbox_toggled)
            main_layout.addWidget(self.autoshutter_checkbox)

        self.setLayout(main_layout)

    def _on_system_cfg_loaded(self) -> None:
        self._refresh_shutter_widget()

    def _refresh_shutter_widget(self) -> None:
        if self.shutter_device not in self._mmc.getLoadedDevicesOfType(
            DeviceType.ShutterDevice
        ):
            self.shutter_button.setText("None")
            self.shutter_button.setEnabled(False)
            if self.autoshutter:
                self.autoshutter_checkbox.setEnabled(False)
        else:
            self._close_shutter(self.shutter_device)
            if self.autoshutter:
                self.autoshutter_checkbox.setEnabled(True)
                self.autoshutter_checkbox.setChecked(True)
                self.shutter_button.setEnabled(False)
            else:
                self.shutter_button.setEnabled(not self._mmc.getAutoShutter())

            # bool to define if the shutter_device is a Micro-Manager 'Multi Shutter'
            props = self._mmc.getDevicePropertyNames(self.shutter_device)
            self._is_multiShutter = bool([x for x in props if "Physical Shutter" in x])

    def _on_seq_started(self) -> None:
        if self._mmc.getShutterOpen(self.shutter_device):
            self._set_shutter_wdg_to_opened()

    def _on_seq_stopped(self) -> None:
        self._close_shutter(self.shutter_device)

    def _on_prop_changed(self, dev_name: str, prop_name: str, value: Any) -> None:
        if dev_name != self.shutter_device or prop_name != "State":
            return
        state = value in [True, "1"]
        (
            self._set_shutter_wdg_to_opened()
            if state
            else self._set_shutter_wdg_to_closed()
        )
        if self._is_multiShutter and state:
            for i in range(1, 6):
                value = self._mmc.getProperty(
                    self.shutter_device, f"Physical Shutter {i}"
                )
                if value != "Undefined":
                    self._mmc.events.propertyChanged.emit(value, "State", True)

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
        self.shutter_button.setEnabled(not state)

        if state and self._mmc.isSequenceRunning():
            self._mmc.stopSequenceAcquisition()

    def _close_shutter(self, shutter: str) -> None:
        self._set_shutter_wdg_to_closed()
        self._mmc.setProperty(shutter, "State", False)

    def _open_shutter(self, shutter: str) -> None:
        self._set_shutter_wdg_to_opened()
        self._mmc.setProperty(shutter, "State", True)

    def _on_shutter_checkbox_toggled(self, state: bool) -> None:
        self._mmc.setAutoShutter(state)

    def _set_shutter_wdg_to_opened(self) -> None:
        if self.button_text_open:
            self.shutter_button.setText(self.button_text_open)
        self.shutter_button.setIcon(icon(self.icon_open, color=self.icon_color_open))

    def _set_shutter_wdg_to_closed(self) -> None:
        if self.button_text_closed:
            self.shutter_button.setText(self.button_text_closed)
        self.shutter_button.setIcon(
            icon(self.icon_closed, color=self.icon_color_closed)
        )

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(
            self._refresh_shutter_widget
        )
        self._mmc.events.autoShutterSet.disconnect(self._on_autoshutter_changed)
        self._mmc.events.propertyChanged.disconnect(self._on_prop_changed)
        self._mmc.events.startContinuousSequenceAcquisition.disconnect(
            self._on_seq_started
        )
        self._mmc.events.startSequenceAcquisition.disconnect(self._on_seq_started)
        self._mmc.events.stopSequenceAcquisition.disconnect(self._on_seq_stopped)
        self._mmc.events.imageSnapped.disconnect(self._on_seq_stopped)
