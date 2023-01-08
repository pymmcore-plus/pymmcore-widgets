from __future__ import annotations

from abc import abstractmethod
from typing import Any

import pymmcore
from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtWidgets import QComboBox, QHBoxLayout, QWidget
from superqt.utils import signals_blocked

LABEL = pymmcore.g_Keyword_Label


class DeviceWidget(QWidget):
    """A general Device Widget.

    Use `DeviceWidget.for_device('device_label')` method to create a device-type
    appropriate subclass.

    !!! Note

        Currently, `DeviceWidget` only supports devices of type
        [`StateDevice`][pymmcore_plus.core._constants.DeviceType.StateDevice]. Calling
        `DeviceWidget.for_device("device_label")`, will create the `DeviceWidget`
        subclass [pymmcore_widgets.StateDeviceWidget][].

    Parameters
    ----------
    device_label : str
        A device label for which to create a widget.
    parent : QWidget | None
        Optional parent widget.
    mmcore: CMMCorePlus | None
        Optional [`CMMCorePlus`][pymmcore_plus.CMMCorePlus] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self,
        device_label: str,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)
        self._device_label = device_label
        self._mmc = mmcore or CMMCorePlus.instance()
        self.destroyed.connect(self._disconnect)

        # TODO:
        # currently, if the device is not Loaded, you'll likely get an error on init in
        # a subclass.  Similarly, if the config changes and the device becomes
        # unavailable, we need to handle it.
        # For now, we could handle that in subclasses but it would be good to raise
        # that to the base class and potentially have the concept of a "temporarily"
        # unavailable device.

    @abstractmethod
    def _disconnect(self) -> None:
        """Disconnect from core when the widget is destroyed.

        Must implement in subclass. (note we can't actually enforce this without
        subclassing from abc.ABC, but that has an incompatible metaclass with QWidget).

        The goal is that any connections made in init must have a corresponding
        disconnection that will be called when this widget is destroyed.

        # connect
        core.events.propertyChanged.connect(self._on_prop_change)
        # disconnect
        core.events.propertyChanged.disconnect(self._on_prop_change)
        """

    def deviceLabel(self) -> str:
        """Return device label."""
        return self._device_label

    def deviceName(self) -> str:
        """Return device name (this is *not* the device label)."""
        return self._mmc.getDeviceName(self._device_label)

    def deviceType(self) -> DeviceType:
        """Return type of Device (`pymmcore_plus.DeviceType`)."""
        return self._mmc.getDeviceType(self._device_label)

    @classmethod
    def for_device(cls, device_label: str) -> "DeviceWidget":
        """Create a type-appropriate subclass for device with label `device_label`.

        Parameters
        ----------
        device_label : str
            A deviceLabel for which to create a widget.

        Returns
        -------
        DeviceWidget
            Appropriate DeviceWidget subclass instance.
        """
        dev_type = CMMCorePlus.instance().getDeviceType(device_label)
        _map = {DeviceType.StateDevice: StateDeviceWidget}
        if dev_type not in _map:
            raise NotImplementedError(
                "No DeviceWidget subclass has been implemented for devices of "
                f"type {dev_type.name!r}"
            )
        return _map[dev_type](device_label)


class StateDeviceWidget(DeviceWidget):
    """A Widget with a QComboBox to control the states of a StateDevice.

    Parameters
    ----------
    device_label : str
        A device label for which to create a widget.
    parent : QWidget | None
        Optional parent widget.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self,
        device_label: str,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(device_label, parent=parent, mmcore=mmcore)
        assert self.deviceType() == DeviceType.StateDevice

        self._combo = QComboBox()
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        self._refresh_choices()
        self._combo.setCurrentText(self._mmc.getStateLabel(self._device_label))

        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self._combo)
        self._mmc.events.propertyChanged.connect(self._on_prop_change)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)

    def _pre_change_hook(self) -> None:
        pass  # for subclasses

    def _post_change_hook(self) -> None:
        pass  # for subclasses

    def _on_sys_cfg_loaded(self) -> None:
        with signals_blocked(self._combo):
            self._combo.clear()
            if self._device_label in self._mmc.getLoadedDevices():
                self.setEnabled(True)
                self._refresh_choices()
            else:
                self._combo.addItem(f"{self._device_label!r} not found")
                self.setEnabled(False)

    def _disconnect(self) -> None:
        """Disconnect from core when the widget is destroyed."""
        self._mmc.events.propertyChanged.disconnect(self._on_prop_change)
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)

    def _on_combo_changed(self, index: int) -> None:
        """Update core state when the combobox changes."""
        self._pre_change_hook()
        self._mmc.setState(self._device_label, index)
        self._post_change_hook()

    def _on_prop_change(self, dev_label: str, prop: str, value: Any) -> None:
        """Update the combobox when the state changes."""
        if dev_label == self._device_label and prop == LABEL:
            with signals_blocked(self._combo):
                self._combo.setCurrentText(value)

    def _refresh_choices(self) -> None:
        """Refresh the combobox choices from core."""
        with signals_blocked(self._combo):
            self._combo.clear()
            self._combo.addItems(self.stateLabels())

    def state(self) -> int:
        """Return current state (index) of the device."""
        return self._mmc.getState(self._device_label)

    def stateLabel(self) -> str:
        """Return current state (label) of the device."""
        return self._mmc.getStateLabel(self._device_label)

    def stateLabels(self) -> tuple[str]:
        """Return all state labels of the device."""
        return self._mmc.getStateLabels(self._device_label)

    def currentText(self) -> str:
        # pass through the QComboBox interface
        return self._combo.currentText()  # type: ignore [no-any-return]

    def setCurrentText(self, text: str) -> None:
        # pass through the QComboBox interface
        if text not in self.stateLabels():
            raise ValueError(f"State label must be one of: {self.stateLabels()}")
        self._combo.setCurrentText(text)

    def currentIndex(self) -> int:
        # pass through the QComboBox interface
        return self._combo.currentIndex()  # type: ignore [no-any-return]

    def setCurrentIndex(self, index: int) -> None:
        # pass through the QComboBox interface
        nstates = self._mmc.getNumberOfStates(self._device_label)
        if not (0 <= index < nstates):
            raise ValueError(f"Index must be between 0 and {nstates}")
        self._combo.setCurrentIndex(index)
