from pymmcore_plus import CMMCorePlus, DeviceType
from pymmcore_plus.model import Microscope
from qtpy.QtWidgets import QCheckBox, QComboBox, QFormLayout

from ._base_page import _ConfigWizardPage


class DefaultsPage(_ConfigWizardPage):
    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__(model, core)
        self.setTitle("Select default devices and choose auto-shutter setting")

        self.camera_combo = QComboBox()
        self.shutter_combo = QComboBox()
        self.focus_combo = QComboBox()
        self.auto_shutter_checkbox = QCheckBox()

        # try/catch
        if cameras := core.getLoadedDevicesOfType(DeviceType.CameraDevice):
            self.camera_combo.addItems(("", *cameras))

        if shutters := core.getLoadedDevicesOfType(DeviceType.ShutterDevice):
            self.shutter_combo.addItems(("", *shutters))

        if stages := core.getLoadedDevicesOfType(DeviceType.StageDevice):
            self.focus_combo.addItems(("", *stages))

        layout = QFormLayout(self)
        layout.addRow("Default Camera", self.camera_combo)
        layout.addRow("Default Shutter", self.shutter_combo)
        layout.addRow("Default Focus Stage", self.focus_combo)
        layout.addRow("Use auto-shutter", self.auto_shutter_checkbox)
