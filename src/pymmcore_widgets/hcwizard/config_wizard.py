import logging
from pathlib import Path

from pymmcore_plus import CMMCorePlus, Device, DeviceType
from qtpy.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLineEdit,
    QTableWidget,
    QRadioButton,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QWizard,
    QWizardPage,
    QPushButton,
)

logger = logging.getLogger(__name__)


class MicroscopeModel:
    def __init__(self, core: CMMCorePlus, _filename: Path = Path()) -> None:
        self.core = core
        self.filename: Path = _filename
        self._available_devices: list[Device] = []
        self._available_com_ports: list[Device] = []
        self._available_hubs: list[Device] = []
        self._bad_libraries: set[str] = set()
        self._used_com_ports: dict[str, Device] = {}
        self.loadAvailableDeviceList()

    def loadAvailableDeviceList(self, core: CMMCorePlus | None = None) -> None:
        """Gather information about all available devices."""
        if core is not None:
            self.core = core

        self._available_devices.clear()
        self._available_hubs.clear()
        self._available_com_ports.clear()
        self._used_com_ports.clear()

        for lib in self.core.iterDeviceAdapters():
            good = False
            try:
                for dev in lib.available_devices:
                    if dev.type() == DeviceType.SerialDevice:  # com port
                        dev.label = dev.name()
                        if dev not in self._available_com_ports:
                            self._available_com_ports.append(dev)
                    else:
                        self._available_devices.append(dev)
                        if dev.type() == DeviceType.Hub:
                            self._available_hubs.append(dev)
                    good = True
            except Exception as e:
                logger.error("Unable to load library %s: %s", lib.name, e)
            if not good:
                self._bad_libraries.add(lib.name)


class _ConfigWizardPage(QWizardPage):
    def __init__(self, model: MicroscopeModel):
        super().__init__()
        self.model = model


class _IntroPage(_ConfigWizardPage):
    def __init__(self, model: MicroscopeModel):
        super().__init__(model)
        self.setTitle("Select Configuration File")
        self.setSubTitle(
            "This wizard will walk you through setting up the hardware in your system."
        )

        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        self.file_edit.setPlaceholderText("Select a configuration file...")
        self.select_file_btn = QPushButton("Browse...")
        self.select_file_btn.clicked.connect(self.select_file)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.addWidget(self.file_edit)
        row_layout.addWidget(self.select_file_btn)

        self.new_btn = QRadioButton("Create new configuration")
        self.new_btn.clicked.connect(row.setDisabled)
        self.modify_btn = QRadioButton("Modify or explore existing configuration")
        self.modify_btn.clicked.connect(row.setEnabled)
        self.new_btn.click()

        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.new_btn)
        self.btn_group.addButton(self.modify_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.new_btn)
        layout.addWidget(self.modify_btn)
        layout.addWidget(row)

    def select_file(self) -> None:
        (fname, _) = QFileDialog.getOpenFileName(
            self, "Select Configuration File", "", "Config Files (*.cfg)"
        )
        if fname:
            self.file_edit.setText(fname)


class DeviceTable(QTableWidget):
    def __init__(self, model: MicroscopeModel):
        super().__init__()
        self.model = model
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        h = self.horizontalHeader()
        h.stretchLastSection = True

        headers = ["Name", "Adapter/Module", "Description", "Status"]
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)


class _DevicesPage(_ConfigWizardPage):
    def __init__(self, model: MicroscopeModel):
        super().__init__(model)
        self.setTitle("Add or remove devices")

        self.table = DeviceTable(model)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)


class _RolesPage(_ConfigWizardPage):
    def __init__(self, model: MicroscopeModel):
        super().__init__(model)
        self.setTitle("Select default devices and choose auto-shutter setting")


class _DelayPage(_ConfigWizardPage):
    def __init__(self, model: MicroscopeModel):
        super().__init__(model)
        self.setTitle("Set delays for devices without synchronization capabilities")


class _LabelsPage(_ConfigWizardPage):
    def __init__(self, model: MicroscopeModel):
        super().__init__(model)
        self.setTitle("Define position labels for state devices")


class _FinishPage(_ConfigWizardPage):
    def __init__(self, model: MicroscopeModel):
        super().__init__(model)
        self.setTitle("Save configuration and exit")


class ConfigWizard(QWizard):
    def __init__(self, core: CMMCorePlus | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._core = core or CMMCorePlus.instance()
        self._model = MicroscopeModel(self._core)

        self.setWindowTitle("Hardware Configuration Wizard")
        self.addPage(_IntroPage(self._model))
        self.addPage(_DevicesPage(self._model))
        self.addPage(_RolesPage(self._model))
        self.addPage(_DelayPage(self._model))
        self.addPage(_LabelsPage(self._model))
        self.addPage(_FinishPage(self._model))


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    wiz = ConfigWizard()
    wiz.show()
    app.exec_()
