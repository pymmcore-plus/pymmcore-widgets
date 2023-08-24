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
assert PORT in core.getDevicePropertyNames('MyDev')

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
import logging
from typing import Sequence

from pymmcore_plus import CMMCorePlus, DeviceDetectionStatus, Keyword
from pymmcore_plus.model import Device, Microscope
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import exceptions_as_dialog

from pymmcore_widgets._device_property_table import DevicePropertyTable

logger = logging.getLogger(__name__)
PORT_SLEEP = 0.05  # revisit this  # TODO


class _DeviceSetupDialog(QDialog):
    """Dialog that pops up when you click add or double-click an available device."""

    def __init__(
        self,
        device: Device,
        model: Microscope,
        core: CMMCorePlus,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Sheet)
        self._device = device
        self._model = model
        self._core = core

        self._port_device: Device | None = None

        # NOTE:
        # it's still not clear to me why MMStudio doesn't restrict this to
        # JUST the device we're setting up at the moment...
        # core.supportsDeviceDetection(device.name)
        # even in the scan ports thread, we're only detecting `device`.
        should_detect = False
        for dev in self._model.devices:
            for prop in dev.properties:
                if prop.name == Keyword.Port and core.supportsDeviceDetection(dev.name):
                    should_detect = True
                    break

        # get names of pre-init properties and any properties named "Port"
        # (this still needs to be used...)
        pre_init_props: list[str] = []
        port_props: list[str] = []
        for p in device.properties:
            if p.is_pre_init:
                pre_init_props.append(p.value)
            if p.name == Keyword.Port:
                port_props.append(p.value)

        if not model.available_com_ports:
            # needs to be done before the dialog # FIXME
            raise RuntimeError("No available COM ports")
        else:
            pass
            # if not port_props... hide the COMS table

        self.setWindowTitle(f"Device: {device.adapter_name}; Library: {device.library}")

        # WIDGETS -------------

        self.name_edit = QLineEdit(device.name)
        self.scan_ports_btn = QPushButton("Scan Ports")
        self.scan_ports_btn.clicked.connect(self._scan_ports)
        if not should_detect:
            self.scan_ports_btn.setEnabled(False)
            self.scan_ports_btn.setVisible(False)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Help
        )
        btns.accepted.connect(self._on_ok_clicked)
        btns.rejected.connect(self.reject)
        btns.helpRequested.connect(self._show_help)

        self.prop_table = DevicePropertyTable(connect_core=False)
        # The "-" suffix *should* be enough to select only this device...
        # but it's a bit hacky
        self.prop_table.filterDevices(
            f"{device.name}-", include_read_only=False, init_props_only=True
        )
        # FIXME: HACK
        for row in range(self.prop_table.rowCount()):
            if self.prop_table.isRowHidden(row):
                continue
            item = self.prop_table.item(row, 0)
            prop = item.data(self.prop_table.PROP_ROLE)
            if prop.name == Keyword.Port:
                tmp = QWidget()
                self.prop_table.cellWidget(row, 1).setParent(tmp)
                wdg = QComboBox()
                wdg.currentIndexChanged.connect(
                    lambda: setattr(self, "_port_device", wdg.currentData())
                )
                wdg.value = lambda _w=wdg: _w.currentText()
                for avail_port in model.available_com_ports:
                    wdg.addItem(avail_port.name, avail_port)
                self.prop_table.setCellWidget(row, 1, wdg)

        # self.com_table = QTableWidget()

        # LAYOUT -------------

        top = QHBoxLayout()
        top.addWidget(QLabel("Device Name:"))
        top.addWidget(self.name_edit)
        if device.parent_name:
            top.addWidget(QLabel(f"Parent Device: {device.parent_name}"))

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(QLabel("Initialization Properties:"))
        layout.addWidget(self.prop_table)
        layout.addWidget(self.scan_ports_btn)
        layout.addWidget(btns)

        # DEVICE --------------

        # can not change pre-initialization properties on a device that was initialized
        if device.initialized:
            with exceptions_as_dialog(use_error_message=True):
                device.load_in_core(reload=True)

    def _show_help(self) -> None:
        from webbrowser import open

        # TODO: some of these will be 404
        open(f"https://micro-manager.org/{self._device.library}")

    def _on_ok_clicked(self) -> None:
        old_name, new_name = self._device.name, self.name_edit.text()
        if old_name != new_name:
            if self._model.has_device_name(new_name):
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Device name {new_name!r} already exists. Please rename.",
                )
                return

            with exceptions_as_dialog(
                msg_template="Failed to re-load device with new name: {exc_value}",
                parent=self,
            ) as ctx:
                self._device.rename_in_core(new_name)
            if ctx.exception:
                logger.exception(ctx.exception)
                return

        if not self._model.has_device_name(new_name):
            QMessageBox.critical(
                self,
                "Error",
                f"Device {new_name!r} is not loaded properly.\nPlease try again.",
            )
            return

        if self._device.initialized:
            try:
                self._device.load_in_core(self._core, reload=True)
            except Exception as e:
                logger.exception(e)

        with exceptions_as_dialog(
            title="Failed to initialize device", parent=self
        ) as ctx:
            success = self._initialize_device()
        if ctx.exception:
            import traceback

            e = ctx.exception
            traceback.print_exception(type(e), e, e.__traceback__)
            return

        if ctx.exception or not success:
            self._device.initialized = False
            return

        if self._port_device:
            self._model.assigned_com_ports[self._port_device.name] = self._port_device
        # model.setModified

        # make sure parent refs are up to date
        if old_name != new_name:
            for dev in self._model.devices:
                if dev.parent_name == old_name:
                    dev.parent_name = new_name

        return super().accept()

    def _initialize_device(self) -> bool:
        print("-------------------")
        # if self._device.initialized:
        print("reloading")
        self._device.load_in_core(reload=True)

        # get properties from table
        for r in range(self.prop_table.rowCount()):
            if not self.prop_table.isRowHidden(r):
                _, prop, val = self.prop_table.getRowData(r)
                print("setprop", self._device.name, prop, val)
                self._core.setProperty(self._device.name, prop, val)

        with exceptions_as_dialog(
            msg_template="Failed to initialize port device:<br>{exc_value}", parent=self
        ) as ctx:
            self._initialize_port()
        if ctx.exception:
            logger.exception(ctx.exception)
            return False

        # FIXME: move this ... or remove?
        # if self._port_device:
        #     print("setting port prop", self._device.name, Keyword.Port, self._port_device.name)
        #     self._core.setProperty(
        #         self._device.name, Keyword.Port, self._port_device.name
        #     )

        print("init in core")
        self._device.initialize_in_core()
        return True

    def _initialize_port(self) -> None:
        if (port_dev := self._port_device) is None:
            return
        print("init port dev", port_dev)
        port_dev.initialize_in_core(self._core, reload=True)
        # TODO: ...
        # for prop in port_dev.properties:
        #     if port_dev.find_property(prop.name)...
        self._model.assigned_com_ports[port_dev.name] = port_dev

    def _scan_ports(self):
        if _PortWarning(self).exec() == QMessageBox.StandardButton.Cancel:
            return


def detect_ports(
    core: CMMCorePlus, device_name: str, available: Sequence[Device]
) -> list[str]:
    """Detect available devices.  Should be done in Thread."""
    # in try/except block ?

    ports_found_communcating: list[str] = []
    for port_dev in available:
        try:
            core.setProperty(device_name, Keyword.Port, port_dev.name)
        except Exception as e:
            logger.exception(e)

        # XXX: couldn't we do this before starting the thread?
        # core.supportsDeviceDetection(device_name) ??
        status = core.detectDevice(device_name)
        if status == DeviceDetectionStatus.Unimplemented:
            print(f"{device_name} does not support auto-detection")  # TODO
            return

        if status == DeviceDetectionStatus.CanCommunicate:
            ports_found_communcating.append(port_dev.name)

    if ports_found_communcating:
        print(f"Found ports: {ports_found_communcating}")  # TODO
    return ports_found_communcating


class _PortWarning(QMessageBox):
    def __init__(self, parent: QWidget):
        btns = QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        super().__init__(
            QMessageBox.Icon.Critical,
            "Scan Serial Ports?",
            "WARNING<br><br>This will send messages through all "
            "connected serial ports, potentially interfering with other "
            "serial devices connected to this computer.",
            btns,
            parent,
        )
        self.setDetailedText(
            "We strongly recommend turning off all other serial devices prior to "
            "starting this scan."
        )
