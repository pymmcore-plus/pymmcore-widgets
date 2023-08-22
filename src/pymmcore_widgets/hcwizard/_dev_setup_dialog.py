import logging
import time
from typing import Sequence
from contextlib import suppress

from pymmcore_plus import CMMCorePlus, DeviceDetectionStatus, Keyword
from pymmcore_plus.model import Device, Microscope
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
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
            if p.pre_init:
                pre_init_props.append(p.value)
            if p.name == Keyword.Port:
                port_props.append(p.value)

        print("pre-init props", pre_init_props)
        print("port props", port_props)
        if port_props:
            print(model.available_com_ports)
            self._port_device = next(
                d for d in model.available_com_ports if d.adapter_name == 'COM4' #TODO
            )
        elif not model.available_com_ports:
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
            msg_template="Failed to initialize device: {exc_value}", parent=self
        ) as ctx:
            success = self._initialize_device()

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
        if self._device.initialized:
            self._device.load_in_core(reload=True)

        # get properties from table
        for r in range(self.prop_table.rowCount()):
            if not self.prop_table.isRowHidden(r):
                _, prop, val = self.prop_table.getRowData(r)
                self._core.setProperty(self._device.name, prop, val)

        with exceptions_as_dialog(
            msg_template="Failed to initialize port device: {exc_value}", parent=self
        ) as ctx:
            self._initialize_port()
        if ctx.exception:
            logger.exception(ctx.exception)
            return False

        # FIXME: move this
        self._core.setProperty(self._device.name, Keyword.Port, self._port_device.name)
        print("init", self._device.name)
        self._device.initialize_in_core()
        print("update from core", self._device.name)
        self._device.update_from_core()
        return True

    def _initialize_port(self) -> None:
        if (port_dev := self._port_device) is None:
            return

        with suppress(RuntimeError):
            self._core.unloadDevice(port_dev.name)

        time.sleep(PORT_SLEEP)  # MMStudio does this
        self._core.loadDevice(port_dev.name, port_dev.library, port_dev.adapter_name)
        for prop in port_dev.properties:
            if prop.pre_init:
                print("set prop", prop)
                self._core.setProperty(port_dev.name, prop.name, prop.value)

                # TODO: ...
                # if port_dev.find_property(prop.name)...
        self._core.initializeDevice(port_dev.name)
        time.sleep(PORT_SLEEP)  # MMStudio does this
        port_dev.update_from_core()
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
