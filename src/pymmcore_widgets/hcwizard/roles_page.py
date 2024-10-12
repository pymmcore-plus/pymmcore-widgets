from pymmcore_plus import CMMCorePlus, DeviceType, Keyword
from pymmcore_plus.model import Microscope
from qtpy.QtWidgets import QCheckBox, QComboBox, QFormLayout
from superqt.utils import signals_blocked

from ._base_page import ConfigWizardPage


class RolesPage(ConfigWizardPage):
    """Page for selecting default devices and auto-shutter setting."""

    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__(model, core)
        self.setTitle("Select default devices and choose auto-shutter setting")
        self.setSubTitle(
            "Select the default device to use for certain important roles."
        )
        self.camera_combo = QComboBox()
        self.camera_combo.currentTextChanged.connect(self._on_camera_changed)
        self.shutter_combo = QComboBox()
        self.shutter_combo.currentTextChanged.connect(self._on_shutter_changed)
        self.focus_combo = QComboBox()
        self.focus_combo.currentTextChanged.connect(self._on_focus_changed)
        self.auto_shutter_checkbox = QCheckBox()
        self.auto_shutter_checkbox.stateChanged.connect(self._on_auto_shutter_changed)

        # TODO: focus directions
        layout = QFormLayout(self)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addRow("Default Camera", self.camera_combo)
        layout.addRow("Default Shutter", self.shutter_combo)
        layout.addRow("Default Focus Stage", self.focus_combo)
        layout.addRow("Use auto-shutter", self.auto_shutter_checkbox)

    def initializePage(self) -> None:
        """Called to prepare the page just before it is shown."""
        # try/catch

        # reset and populate the combo boxes with available devices
        with signals_blocked(self.camera_combo):
            self.camera_combo.clear()
            cameras = [
                x.name
                for x in self._model.filter_devices(device_type=DeviceType.Camera)
            ]
            if cameras:
                self.camera_combo.addItems(("", *cameras))

        with signals_blocked(self.shutter_combo):
            self.shutter_combo.clear()
            shutters = [
                x.name
                for x in self._model.filter_devices(device_type=DeviceType.Shutter)
            ]
            if shutters:
                self.shutter_combo.addItems(("", *shutters))

        with signals_blocked(self.focus_combo):
            self.focus_combo.clear()
            stages = [
                x.name for x in self._model.filter_devices(device_type=DeviceType.Stage)
            ]
            if stages:
                self.focus_combo.addItems(("", *stages))

        with signals_blocked(self.auto_shutter_checkbox):
            self.auto_shutter_checkbox.setChecked(True)

        # update values from the model
        for prop in self._model.core_device.properties:
            if prop.name == Keyword.CoreCamera and prop.value:
                self.camera_combo.setCurrentText(prop.value)
            elif prop.name == Keyword.CoreShutter and prop.value:
                self.shutter_combo.setCurrentText(prop.value)
            elif prop.name == Keyword.CoreFocus and prop.value:
                self.focus_combo.setCurrentText(prop.value)
            elif prop.name == Keyword.CoreAutoShutter:
                self.auto_shutter_checkbox.setChecked(prop.value == "1")

        if cameras and not self.camera_combo.currentText():
            self.camera_combo.setCurrentText(cameras[0])
        if shutters and not self.shutter_combo.currentText():
            self.shutter_combo.setCurrentText(shutters[0])
        if stages and not self.focus_combo.currentText():
            self.focus_combo.setCurrentText(stages[0])

        super().initializePage()

    def _on_camera_changed(self, text: str) -> None:
        self._model.core_device.set_property(Keyword.CoreCamera, text)

    def _on_shutter_changed(self, text: str) -> None:
        self._model.core_device.set_property(Keyword.CoreShutter, text)

    def _on_focus_changed(self, text: str) -> None:
        self._model.core_device.set_property(Keyword.CoreFocus, text)

    def _on_auto_shutter_changed(self, state: int) -> None:
        val = "1" if bool(state) else "0"
        self._model.core_device.set_property(Keyword.CoreAutoShutter, val)
