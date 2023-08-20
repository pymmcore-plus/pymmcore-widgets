import logging
import time

from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import Device, Microscope
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QErrorMessage,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


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
        self._device = device
        self._model = model
        self._core = core

        self._port_device: Device | None = None

        self.setWindowTitle(f"Device: {device.adapter_name}; Library: {device.library}")

        # WIDGETS -------------

        self.name_edit = QLineEdit(device.name)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Help
        )
        btns.accepted.connect(self._pre_accept)
        btns.rejected.connect(self.reject)
        btns.helpRequested.connect(self._show_help)

        # self.prop_table = QTableWidget()

        # self.com_table = QTableWidget()

        # LAYOUT -------------

        top = QHBoxLayout()
        top.addWidget(QLabel("Device Name:"))
        top.addWidget(self.name_edit)
        if device.parent_name:
            top.addWidget(QLabel(f"Parent Device: {device.parent_name}"))

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(btns)

        # DEVICE --------------

        # can not change pre-initialization properties on a device that was initialized
        if device.initialized:
            try:
                device.load_in_core(core, reload=True)
            except Exception as e:
                err = QErrorMessage()
                err.showMessage(str(e))

    def _show_help(self) -> None:
        from webbrowser import open

        # TODO: some of these will be 404
        open(f"https://micro-manager.org/{self._device.library}")

    def _pre_accept(self) -> None:
        old_name, new_name = self._device.name, self.name_edit.text()
        if old_name != new_name:
            if self._model.has_device_name(new_name):
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Device name {new_name} already exists. Please rename.",
                )
                return

            try:
                self._core.unloadDevice(old_name)
                self._device.initialized = False
                self._device.load_in_core(self._core)
                self._core.setParentLabel(new_name, self._device.parent_name)
            except Exception as e:
                logger.exception(e)
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Device failed to re-load with changed name: {e}",
                )
                return

            self._device.name = new_name

        if not self._model.has_device_name(new_name):
            QMessageBox.critical(
                self,
                "Error",
                f"Device {new_name} is not loaded properly.\n" "Please try again.",
            )
            return

        if self._device.initialized:
            try:
                self._device.load_in_core(self._core, reload=True)
            except Exception as e:
                logger.exception(e)

        try:
            success = self._initialize_device()
        except Exception as e:
            self._device.load_in_core(self._core, reload=True)
            logger.exception(e)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to initialize device: {e}",
            )
            return
        if not success:
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
            self._device.load_in_core(self._core, reload=True)

        # TODO: transfer props from properties_table to the device
        # for row in prop_table.rows:
        #     core.setProperty(dev.name, row.prop_name, row.prop_value)

        self._device.load_data_from_hardware(self._core)

        try:
            self._initialize_port()
        except Exception as e:
            logger.exception(e)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to initialize port device: {e}",
            )
            return False

        self._core.initializeDevice(self._device.name)
        self._device.load_data_from_hardware(self._core)
        self._device.initialized = True
        return True

    def _initialize_port(self) -> None:
        if (port_dev := self._port_device) is None:
            return

        self._core.unloadDevice(port_dev.name)
        self._core.waitForSystem()
        time.sleep(1)  # MMStudio does this
        self._core.loadDevice(port_dev.name, port_dev.library, port_dev.adapter_name)
        for prop in port_dev.properties:
            if prop.pre_init:
                self._core.setProperty(port_dev.name, prop.name, prop.value)

                # TODO: ...
                # if port_dev.find_property(prop.name)...
        self._core.initializeDevice(port_dev.name)
        time.sleep(1)  # MMStudio does this
        port_dev.load_data_from_hardware(self._core)
        self._model.assigned_com_ports[port_dev.name] = port_dev
