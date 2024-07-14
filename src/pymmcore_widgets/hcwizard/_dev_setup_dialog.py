"""Device Setup Dialog.

This dialog lets you set up a device, managing its initialization properties and
com port devices in the process. It pops up when you click add or double-click an
available device in the devices page hardware config wizard.

Notes
-----
1. When the dialog is opened, it is assumed that the device name is already loaded
   in core... but not yet initialized (TODO: maybe have the dialog do this?)
2. It has a field to rename the device (so, if the user changes it, the device must
   be RE-loaded in core with the new name)
3. It has a table that shows all of the pre-initialization properties for the device.
   These are the properties that must be defined prior to initialization (i.e. where
   `core.isPropertyPreInit(...)` is True).
4. It has another table to setup the com port device (if any) for the device.
   The logic for setting up and associating com ports is a little implicit here:
    - if a device has a property named "Port" (`pymmcore.g_Keyword_Port`), then it is
      assumed that the value of the property points to the name of a loaded com port
    - a "loaded" com port is a SerialManager device with an adapter_name that matches
      the name of the desired com port (e.g. "COM4")
    - the value of the "Port" property must match the NAME of the loaded SerialManager
      device.
    - By convention, to avoid confusion, SerialManager devices should be loaded with
      the same name as their adapter_name (e.g. "COM4"):
      `core.loadDevice("COM4", "SerialManager", "COM4")`

Example
-------
This demonstrates how to setup a device with a com port device, and what this dialog
is trying to accomplish for the user:

```python
from pymmcore_plus import CMMCorePlus, Keyword

core = CMMCorePlus()

COM_DEVICE = "name of some loaded SerialManager"
COM_PORT = "COM4"  # the string name of the com port we want to use
PORT = "Port"  # A special property name (string)
assert PORT == Keyword.Port  # here's a constant for it

# a SerialManager device with adapter_name COM_PORT
# (conventionally, COM_DEVICE would equal COM_PORT, but this demonstrates that
# it's the 3rd argument to load device that really matters for com association)
core.loadDevice(COM_DEVICE, "SerialManager", COM_PORT)

# some other device that uses a com port:
core.loadDevice("MyDev", "ASIFW1000", "ASIFWController")

# a property named "Port" is defined for this device, that's "special"
# and it's what determines whether we show a COM table in the dialog
assert PORT in core.getDevicePropertyNames("MyDev")

# assign the "Port" property to the NAME of the loaded SerialManager device
# (again, convention would have COM_DEVICE == COM_PORT but it's arbitrary.)
core.setProperty("MyDev", PORT, COM_DEVICE)

# Note: it's critical that we initialize the com port device first
# or you might get hangs
core.initializeDevice(COM_DEVICE)

# NOW we can initialize the device using a com port properly
core.initializeDevice("MyDev")
```

here's how you might find available serial devices:

```python
from pymmcore_plus import CMMCorePlus, DeviceType

core = CMMCorePlus()
for adapter in core.getDeviceAdapterNames():
    try:
        devs = core.getAvailableDevices(adapter)
        types = core.getAvailableDeviceTypes(adapter)
    except RuntimeError:
        continue
    for dev, type in zip(devs, types):
        if type == DeviceType.Serial:
print(adapter, dev)
"""

from __future__ import annotations

import logging
from contextlib import suppress
from typing import TYPE_CHECKING, Sequence

from pymmcore_plus import CMMCorePlus, Keyword
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import exceptions_as_dialog

from ._simple_prop_table import PropTable

if TYPE_CHECKING:
    from qtpy.QtGui import QFocusEvent

logger = logging.getLogger(__name__)
PORT_SLEEP = 0.05  # revisit this  # TODO
DEFAULT_FLAGS = Qt.WindowType.Sheet | Qt.WindowType.MSWindowsFixedSizeDialogHint


class DeviceSetupDialog(QDialog):
    """Dialog to assist with setting up a device or editing an existing device."""

    @classmethod
    def for_loaded_device(
        cls,
        core: CMMCorePlus,
        device_label: str,
        parent: QWidget | None = None,
        available_com_ports: Sequence[tuple[str, str]] = (),
    ) -> DeviceSetupDialog:
        """Create a dialog to edit an existing device."""
        if device_label not in core.getLoadedDevices():  # pragma: no cover
            raise RuntimeError("No loaded device with label {device_label!r}")
        library_name = core.getDeviceLibrary(device_label)
        device_name = core.getDeviceName(device_label)
        return cls(
            core,
            device_label,
            library_name,
            device_name,
            existing_device=True,
            parent=parent,
            available_com_ports=available_com_ports,
        )

    @classmethod
    def for_new_device(
        cls,
        core: CMMCorePlus,
        library_name: str,
        device_name: str,
        device_label: str = "",
        available_com_ports: Sequence[tuple[str, str]] = (),
        parent: QWidget | None = None,
    ) -> DeviceSetupDialog:
        """Create a dialog to add a new device."""
        if not device_label:
            device_label = device_name
            count = 1
            # generate a unique name for the device
            while device_label in core.getLoadedDevices():
                device_label = f"{device_name}-{count}"

        elif device_label in core.getLoadedDevices():  # pragma: no cover
            raise RuntimeError(
                f"There is already a loaded device with label {device_label!r}"
            )

        core.loadDevice(device_label, library_name, device_name)
        return cls(
            core,
            device_label,
            library_name,
            device_name,
            existing_device=False,
            parent=parent,
            available_com_ports=available_com_ports,
        )

    def __init__(
        self,
        core: CMMCorePlus,
        device_label: str,
        library_name: str,
        device_name: str,
        parent: QWidget | None = None,
        existing_device: bool = False,
        available_com_ports: Sequence[tuple[str, str]] = (),  # (lib_name, device_name)
        flags: Qt.WindowType = DEFAULT_FLAGS,
    ) -> None:
        if device_label not in core.getLoadedDevices():  # pragma: no cover
            raise RuntimeError(
                "No loaded device with label {device_label!r}. Use `for_new_device` to "
                "create a dialog for a new device."
            )

        # get names of pre-init properties and any properties named "Port"
        # (this still needs to be used...)
        current_port = None
        pre_init_props: list[str] = []
        for prop_name in core.getDevicePropertyNames(device_label):
            if core.isPropertyPreInit(device_label, prop_name):
                pre_init_props.append(prop_name)
            if prop_name == Keyword.Port:  # type: ignore [comparison-overlap]
                current_port = core.getProperty(device_label, prop_name)

        self._library_name = library_name
        self._device_name = device_name
        self._existing_device = existing_device
        self._available_com_ports = available_com_ports
        self._core = core
        self._device_label = device_label

        super().__init__(parent, flags)
        self.setWindowTitle(f"Device: {device_name}; Library: {library_name}")

        # WIDGETS -------------

        self.name_edit = LastValueLineEdit(device_label)
        self.name_edit.editingFinished.connect(self._on_name_changed)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Help
        )
        btns.accepted.connect(self._on_ok_clicked)
        btns.rejected.connect(self.reject)
        btns.helpRequested.connect(self._show_help)

        self.prop_table = PropTable(core)
        if pre_init_props:
            dev_props = [(device_label, p) for p in pre_init_props]
            self.prop_table.rebuild(dev_props, available_com_ports)
        else:
            self.prop_table.hide()

        self.com_table = ComTable(core)
        self.prop_table.portChanged.connect(self.com_table.rebuild_port)
        if current_port is not None:
            self.com_table.rebuild_port(current_port)
        else:
            self.com_table.hide()

        # LAYOUT -------------

        top = QHBoxLayout()
        top.addWidget(QLabel("Device Name:"))
        top.addWidget(self.name_edit)

        layout = QVBoxLayout(self)
        lbl = QLabel(f"Setting up: {library_name}-{device_name}")
        # make bold
        font = lbl.font()
        font.setBold(True)
        lbl.setFont(font)
        layout.addWidget(lbl)
        layout.addLayout(top)
        if parent_label := core.getParentLabel(device_label):
            layout.addWidget(QLabel(f"Parent Device: {parent_label}"))
        if pre_init_props:
            layout.addWidget(QLabel("Initialization Properties:"))
        layout.addWidget(self.prop_table)
        layout.addWidget(self.com_table)
        layout.addWidget(btns)

        # DEVICE --------------

        # can not change pre-initialization properties on a device that was initialized
        # if device.initialized:
        #     with exceptions_as_dialog(use_error_message=True):
        #         device.load_in_core(reload=True)

    def _on_name_changed(self) -> None:
        new_name = self.name_edit.text()
        old_name = self.name_edit.lastValue()
        if new_name != old_name:
            if new_name in self._core.getLoadedDevices():
                self.name_edit.setText(old_name)
                QMessageBox.critical(
                    self,
                    "Name Taken",
                    f"Device name {new_name!r} already exists. Please rename.",
                )
                return
            with suppress(RuntimeError):
                self._core.unloadDevice(old_name)
            self._core.loadDevice(new_name, self._library_name, self._device_name)
            self._device_label = new_name

    def deviceLabel(self) -> str:
        """The device label, currently loaded in core."""
        return self._device_label

    def _on_ok_clicked(self) -> None:
        with exceptions_as_dialog(
            title="Failed to initialize device", parent=self
        ) as ctx:
            success = self._initialize_device()
        if ctx.exception or not success:  # pragma: no cover
            self._reload_device()
            return
        super().accept()

    def _reload_device(self) -> None:
        with suppress(RuntimeError):
            self._core.unloadDevice(self._device_label)
        self._core.loadDevice(self._device_label, self._library_name, self._device_name)

    def _initialize_device(self) -> bool:
        with exceptions_as_dialog(
            msg_template="Failed to initialize port device:<br>{exc_value}", parent=self
        ) as ctx:
            self._initialize_port()
        if ctx.exception:  # pragma: no cover
            logger.exception(ctx.exception)
            return False

        # NOTE: this only needs to be done if the device was already initialized...
        # but it's not always easy to know if it was or not
        if self._existing_device:
            self._reload_device()
        # get properties from table
        for prop_name, prop_value in self.prop_table.iterRows():
            self._core.setProperty(self._device_label, prop_name, prop_value)
        self._core.initializeDevice(self._device_label)
        return True

    def _initialize_port(self) -> None:
        port_dev_label = self.com_table._port_dev_name
        if port_dev_label not in self._core.getLoadedDevices():
            return

        for prop_name, prop_value in self.com_table.iterRows():
            self._core.setProperty(port_dev_label, prop_name, prop_value)

        self._core.initializeDevice(port_dev_label)

    def _show_help(self) -> None:  # pragma: no cover
        from webbrowser import open

        # TODO: some of these will be 404
        open(f"https://micro-manager.org/{self._library_name}")

    def reject(self) -> None:
        """Dialog has been rejected. Unload the device if it was new."""
        if not self._existing_device:
            with suppress(RuntimeError):
                self._core.unloadDevice(self._device_label)
        super().reject()


class ComTable(PropTable):
    """Variant of the property table, for com port devices."""

    _port_dev_name = ""

    def rebuild_port(self, port_dev_name: str, port_library_name: str = "") -> None:
        """Rebuild the table for the given port device.

        if port_dev_name is not currently loaded, and port_library_name is given,
        then it will be loaded, and the table will be rebuilt with the available
        property names.
        """
        self.setRowCount(0)
        self._port_dev_name = port_dev_name
        if port_dev_name not in self._core.getLoadedDevices():
            if not port_library_name:
                return
            self._core.loadDevice(port_dev_name, port_library_name, port_dev_name)
        prop_names = self._core.getDevicePropertyNames(port_dev_name)
        return super().rebuild([(port_dev_name, p) for p in prop_names])


class LastValueLineEdit(QLineEdit):
    """QLineEdit that stores the last value on focus in."""

    def focusInEvent(self, a0: QFocusEvent | None) -> None:
        """Store current value when editing starts."""
        self._last_value: str = self.text()
        super().focusInEvent(a0)

    def lastValue(self) -> str:
        """Return the last value stored when editing started."""
        return getattr(self, "_last_value", "")
