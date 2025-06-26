from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, ClassVar, cast

from pymmcore_plus import CMMCorePlus, DeviceProperty, DeviceType, Keyword
from pymmcore_plus.model import Setting
from qtpy.QtCore import QEvent, Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpacerItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets.device_properties import DevicePropertyTable

if TYPE_CHECKING:
    from qtpy.QtGui import QMouseEvent


class GroupedDevicePropertyTable(QWidget):
    """More opinionated arrangement of device properties.

    This widget contains multiple `DevicePropertyTable` widgets, each filtered
    to highlight different aspects of the device properties.

    It's API mimics that of `DevicePropertyTable`, allowing you to get and set
    the union of checked settings across all sub-tables... it should be a drop-in
    replacement for `DevicePropertyTable` in most cases. (assuming you limit your API
    to value(), setValue(), and valueChanged()).
    """

    valueChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Groups -----------------------------------------------------
        self.light_path_props = _LightPathGroupBox(self)
        self.camera_props = _CameraGroupBox(self)

        # layout ------------------------------------------------------------

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.setContentsMargins(0, 0, 0, 0)
        splitter.addWidget(self.light_path_props)
        splitter.addWidget(self.camera_props)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(splitter)

        # init ------------------------------------------------------------

        self.light_path_props.valueChanged.connect(self.valueChanged)
        self.camera_props.valueChanged.connect(self.valueChanged)

    # --------------------------------------------------------------------- API

    def value(self) -> list[Setting]:
        """Return the union of checked settings from both panels."""
        # remove duplicates by converting to a dict keyed on (device, prop_name)
        settings = {
            (setting[0], setting[1]): setting
            for group in (self.light_path_props, self.camera_props)
            for setting in group.value()
        }
        return list(settings.values())

    def setValue(self, value: Iterable[Setting]) -> None:
        self.light_path_props.setValue(value)
        self.camera_props.setValue(value)

    def update_options_from_core(self, core: CMMCorePlus) -> None:
        """Populate the comboboxes with the available devices from the core."""
        self.light_path_props.active_shutter.update_from_core(core)
        self.camera_props.active_camera.update_from_core(core)


def _is_not_objective(prop: DeviceProperty) -> bool:
    return not any(x in prop.device for x in prop.core.guessObjectiveDevices())


def _light_path_predicate(prop: DeviceProperty) -> bool | None:
    devtype = prop.deviceType()
    if devtype in (
        DeviceType.Camera,
        DeviceType.Core,
        DeviceType.AutoFocus,
        DeviceType.Stage,
        DeviceType.XYStage,
    ):
        return False
    if devtype == DeviceType.State:
        if "State" in prop.name or "ClosedPosition" in prop.name:
            return False
    if devtype == DeviceType.Shutter and prop.name == Keyword.State.value:
        return False
    if not _is_not_objective(prop):
        return False
    return None


class _LightPathGroupBox(QGroupBox):
    valueChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Light Path", parent)
        # self.setCheckable(True)
        self.toggled.connect(self.valueChanged)

        self.active_shutter = CoreRoleSelector(DeviceType.ShutterDevice, self)
        self.active_shutter.valueChanged.connect(self.valueChanged)

        self.show_all = QCheckBox("Show All Properties", self)
        self.show_all.toggled.connect(self._show_all_toggled)

        self.props = DevicePropertyTable(self, connect_core=False)
        self.props.valueChanged.connect(self.valueChanged)
        self.props.setRowsCheckable(True)
        self.props.filterDevices(
            include_read_only=False,
            include_pre_init=False,
            predicate=_light_path_predicate,
        )

        shutter_layout = QHBoxLayout()
        shutter_layout.setContentsMargins(2, 0, 0, 0)
        shutter_layout.addWidget(self.active_shutter, 1)
        shutter_layout.addSpacerItem(QSpacerItem(40, 0))
        shutter_layout.addWidget(self.show_all, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        layout.addLayout(shutter_layout)
        layout.addWidget(self.props)

    def _show_all_toggled(self, show_all: bool) -> None:
        self.props.filterDevices(
            exclude_devices=(DeviceType.Camera, DeviceType.Core),
            include_read_only=False,
            include_pre_init=False,
            always_show_checked=True,
            predicate=_light_path_predicate if not show_all else _is_not_objective,
        )

    def value(self) -> Iterable[Setting]:
        yield from self.props.getCheckedProperties(visible_only=True)
        if self.active_shutter.isChecked():
            yield Setting(
                Keyword.CoreDevice.value,
                Keyword.CoreShutter.value,
                self.active_shutter.currentText(),
            )

    def setValue(self, value: Iterable[tuple[str, str, str]]) -> None:
        """Set the value of the properties in this group."""
        self.props.setValue(value)
        self.active_shutter.setChecked(False)
        for device, prop, val in value:
            if device == Keyword.CoreDevice.value and prop == Keyword.CoreShutter.value:
                self.active_shutter.setCurrentText(val)
                self.active_shutter.setChecked(True)
                break


class _CameraGroupBox(QGroupBox):
    valueChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Camera", parent)
        self.setCheckable(True)
        self.setChecked(True)
        self.toggled.connect(self.valueChanged)

        self.props = DevicePropertyTable(self, connect_core=False)
        self.props.valueChanged.connect(self.valueChanged)
        self.props.setRowsCheckable(True)
        self.props.filterDevices(
            include_devices=[DeviceType.Camera],
            include_read_only=False,
        )

        self.active_camera = CoreRoleSelector(DeviceType.CameraDevice, self)
        self.active_camera.valueChanged.connect(self.valueChanged)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        layout.addWidget(self.active_camera)
        layout.addWidget(self.props)

    def value(self) -> Iterable[Setting]:
        if not self.isChecked():
            return
        yield from self.props.getCheckedProperties(visible_only=True)
        if self.active_camera.isChecked():
            yield Setting(
                Keyword.CoreDevice.value,
                Keyword.CoreCamera.value,
                self.active_camera.currentText(),
            )

    def setValue(self, value: Iterable[tuple[str, str, str]]) -> None:
        """Set the value of the properties in this group."""
        self.props.setValue(value)

        self.active_camera.setChecked(False)
        for device, prop, val in value:
            if device == Keyword.CoreDevice.value and prop == Keyword.CoreCamera.value:
                self.active_camera.setCurrentText(val)
                self.active_camera.setChecked(True)
                break

        if (
            self.props.getCheckedProperties(visible_only=True)
            or self.active_camera.isChecked()
        ):
            self.setChecked(True)


class _ClickableLabel(QLabel):
    """A QLabel that emits a signal when clicked (even when disabled)."""

    clicked = Signal()

    def event(self, event: QEvent | None) -> bool:
        """Override event to handle mouse press even when disabled."""
        if event and event.type() == (QEvent.Type.MouseButtonRelease):
            if cast("QMouseEvent", event).button() == Qt.MouseButton.LeftButton:
                self.clicked.emit()
                return True
        return super().event(event)  # type: ignore[no-any-return]


class CheckableComboBox(QWidget):
    """Row containing checkbox, label, and combobox.

    Useful for settings that can be enabled/disabled with a checkbox.
    (Rather than adding a "null" option to the combobox.)
    """

    valueChanged = Signal()

    def __init__(
        self,
        label: str | None = None,
        parent: QWidget | None = None,
        *,
        checkable: bool = True,
    ) -> None:
        super().__init__(parent)

        self.checkbox = QCheckBox(self)  # not using label so we can independent enable
        self.label = _ClickableLabel(label or "", self)
        self.combobox = QComboBox(self)

        self.combobox.currentTextChanged.connect(self.valueChanged)
        self.checkbox.toggled.connect(self.valueChanged)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.checkbox)
        layout.addWidget(self.label)
        layout.addWidget(self.combobox, 1)

        if checkable:
            self.label.clicked.connect(self.checkbox.toggle)
            self.label.setEnabled(False)
            self.combobox.setEnabled(False)
        else:
            self.checkbox.setEnabled(False)
            self.checkbox.setVisible(False)

        self.checkbox.checkStateChanged.connect(self._on_checkbox_changed)

    def clear(self) -> None:
        """Clear the combobox."""
        self.combobox.clear()

    def addItem(self, item: str) -> None:
        """Add item to the combobox."""
        self.combobox.addItem(item)

    def addItems(self, items: Iterable[str]) -> None:
        """Add items to the combobox."""
        self.combobox.addItems(items)

    def isChecked(self) -> bool:
        """Return whether the checkbox is checked."""
        return self.checkbox.isChecked()  # type: ignore[no-any-return]

    def setChecked(self, checked: bool) -> None:
        """Set the checkbox state."""
        self.checkbox.setChecked(checked)

    def currentText(self) -> str:
        """Return the current text of the combobox."""
        return self.combobox.currentText()  # type: ignore[no-any-return]

    def setCurrentText(self, text: str) -> None:
        """Set the current text of the combobox."""
        self.combobox.setCurrentText(text)

    def _on_checkbox_changed(self, state: Qt.CheckState) -> None:
        """Handle checkbox state change."""
        checked = state == Qt.CheckState.Checked
        self.combobox.setEnabled(checked)
        self.label.setEnabled(checked)


class CoreRoleSelector(CheckableComboBox):
    """Widget for selecting a core role."""

    METHOD_MAP: ClassVar[Mapping[DeviceType, str]] = {
        DeviceType.Camera: "getCameraDevice",
        DeviceType.Shutter: "getShutterDevice",
        DeviceType.Stage: "getFocusDevice",
        DeviceType.XYStage: "getXYStageDevice",
        DeviceType.AutoFocus: "getAutoFocusDevice",
        DeviceType.ImageProcessor: "getImageProcessorDevice",
        DeviceType.SLM: "getSLMDevice",
        DeviceType.Galvo: "getGalvoDevice",
    }

    def __init__(
        self,
        device_type: DeviceType,
        parent: QWidget | None = None,
        *,
        label: str | None = None,
    ) -> None:
        if device_type not in CoreRoleSelector.METHOD_MAP:
            raise ValueError(f"MMCore has no 'current' {device_type.name} ")

        self.device_type = device_type
        if label is None:
            label = f"Active {device_type.name.replace('Device', '')}:"
        super().__init__(label, parent, checkable=True)

    def update_from_core(
        self,
        core: CMMCorePlus | None = None,
        *,
        update_options: bool = True,
        update_current: bool = True,
    ) -> None:
        """Update the combobox with the current core settings.

        If `update_options` is True, it will refresh the list of devices.
        If `update_current` is True, it will set the current text to the active device.
        """
        core = core or CMMCorePlus.instance()

        if update_options:
            self.clear()
            devices = core.getLoadedDevicesOfType(self.device_type)
            self.addItems(["", *devices])

        if update_current:
            method_name = self.METHOD_MAP[self.device_type]
            method = getattr(core, method_name)
            try:
                self.setCurrentText(method())
            except Exception:
                self.setCurrentText("")
