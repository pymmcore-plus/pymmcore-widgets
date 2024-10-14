from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Protocol, TypeVar

from pymmcore_plus import DeviceType, Keyword
from pymmcore_plus.model import ConfigGroup, ConfigPreset, Setting
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpacerItem,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

from pymmcore_widgets.control import ObjectivesWidget
from pymmcore_widgets.device_properties import DevicePropertyTable

from ._unique_name_list import MapManager

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from pymmcore_plus import CMMCorePlus, DeviceProperty

    class NamedObject(Protocol):
        name: str

    T = TypeVar("T", bound=NamedObject)


def _copy_named_obj(obj: T, new_name: str) -> T:
    """Copy object `obj` and set its name to `new_name`."""
    obj = deepcopy(obj)
    obj.name = new_name
    return obj


class ConfigGroupWidget(QWidget):
    def __init__(
        self,
        data: dict[str, ConfigGroup] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.groups = MapManager(
            ConfigGroup, clone_function=_copy_named_obj, parent=self, base_key="Group"
        )
        self.groups.listWidget().setMinimumWidth(120)
        self.presets = MapManager(
            ConfigPreset, clone_function=_copy_named_obj, parent=self, base_key="Config"
        )

        self.btn_activate = QPushButton("Set Active")
        self.presets.btn_layout.insertWidget(3, self.btn_activate)

        # Groups -----------------------------------------------------
        self._light_path_group = _LightPathGroupBox(self)
        self._cam_group = _CameraGroupBox(self)
        self._obj_group = _ObjectiveGroupBox(self)
        self._light_path_group.valueChanged.connect(self._update_model_from_gui)
        self._cam_group.valueChanged.connect(self._update_model_from_gui)
        self._obj_group.valueChanged.connect(self._update_model_from_gui)

        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("<b>Groups</b>"), 0, Qt.AlignmentFlag.AlignLeft)
        left_layout.addWidget(self.groups, 1)
        left_layout.addSpacing(6)
        left_layout.addWidget(QLabel("<b>Presets</b>"), 0, Qt.AlignmentFlag.AlignLeft)
        left_layout.addWidget(self.presets, 1)

        right_splitter = QSplitter(Qt.Orientation.Vertical, self)
        right_splitter.setContentsMargins(0, 0, 0, 0)
        right_splitter.addWidget(self._light_path_group)
        right_splitter.addWidget(self._cam_group)
        right_splitter.addWidget(self._obj_group)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 1)
        right_splitter.setStretchFactor(2, 0)

        # self.expert_table = PropertyBrowser(parent=self)
        # self.expert_table._prop_table.setRowsCheckable(True)
        # self.expert_table._device_filters.setShowReadOnly(False)
        # self.expert_table._device_filters._read_only_checkbox.hide()
        # self.expert_table._device_filters.setShowPreInitProps(False)
        # self.expert_table._device_filters._pre_init_checkbox.hide()

        basic_expert_tabs = QTabWidget(self)
        basic_expert_tabs.addTab(right_splitter, "Basic")
        # basic_expert_tabs.addTab(self.expert_table, "Expert")

        layout = QHBoxLayout(self)
        layout.addLayout(left_layout)
        layout.addWidget(basic_expert_tabs, 1)

        self.resize(1080, 920)

        self.groups.currentKeyChanged.connect(self._on_current_group_changed)
        self.groups.setRoot(data or {})

        # after groups.setRoot to prevent a bunch of stuff when setting initial data
        self.presets.currentKeyChanged.connect(self._update_gui_from_model)

    def setCurrentGroup(self, group: str) -> None:
        self.groups.setCurrentKey(group)

    def setCurrentPreset(self, preset: str) -> None:
        self.presets.setCurrentKey(preset)

    def currentSettings(self) -> list[Setting]:
        tmp = {}
        if self._light_path_group.isChecked():
            tmp.update(
                {
                    (dev, prop): val
                    for dev, prop, val in self._light_path_group.settings()
                }
            )
        if self._cam_group.isChecked():
            tmp.update(
                {(dev, prop): val for dev, prop, val in self._cam_group.settings()}
            )
        return [Setting(*k, v) for k, v in tmp.items()]

    def setCurrentSettings(self, settings: Sequence[Setting]) -> None:
        # update all the property browser tables
        self._light_path_group.props.setValue(settings)
        self._cam_group.props.setValue(settings)
        active_shutter = ""
        active_camera = ""
        for s in settings:
            if s.device_name == Keyword.CoreDevice:
                if s.property_name == Keyword.CoreShutter:
                    active_shutter = s.property_value
                elif s.property_name == Keyword.CoreCamera:
                    active_camera = s.property_value

        self._light_path_group.active_shutter.setCurrentText(active_shutter)
        self._cam_group.active_camera.setCurrentText(active_camera)

    def update_options_from_core(self, core: CMMCorePlus) -> None:
        """The only place that a core instance should have influence."""
        shutters = core.getLoadedDevicesOfType(DeviceType.Shutter)
        self._light_path_group.active_shutter.clear()
        self._light_path_group.active_shutter.addItems(("", *shutters))

        cameras = core.getLoadedDevicesOfType(DeviceType.Camera)
        self._cam_group.active_camera.clear()
        self._cam_group.active_camera.addItems(("", *cameras))

    # PRIVATE -----------------------------------------------------------

    def _on_current_group_changed(self) -> None:
        with signals_blocked(self.presets):
            if config_group := self.groups.currentValue():
                self.presets.setRoot(config_group.presets)
        self.presets.listWidget().setCurrentRow(0)

    def _selected_preset(self) -> ConfigPreset | None:
        """Returns the data object for the currently selected preset."""
        if grp := self.groups.currentValue():
            if current_preset := self.presets.currentKey():
                return grp.presets[current_preset]
        return None

    def _update_gui_from_model(self) -> None:
        if preset := self._selected_preset():
            self.setCurrentSettings(preset.settings)

    def _update_model_from_gui(self) -> None:
        if preset := self._selected_preset():
            preset.settings = self.currentSettings()


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
        self.setCheckable(True)
        self.toggled.connect(self.valueChanged)

        self.active_shutter = QComboBox(self)
        self.active_shutter.currentIndexChanged.connect(self.valueChanged)

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
        shutter_layout.addWidget(QLabel("Active Shutter:"), 0)
        shutter_layout.addWidget(self.active_shutter, 1)
        shutter_layout.addSpacerItem(QSpacerItem(40, 0))
        shutter_layout.addWidget(self.show_all, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        layout.addLayout(shutter_layout)
        layout.addWidget(self.props)

    def _show_all_toggled(self, checked: bool) -> None:
        self.props.filterDevices(
            exclude_devices=(DeviceType.Camera, DeviceType.Core),
            include_read_only=False,
            include_pre_init=False,
            predicate=_light_path_predicate if not checked else _is_not_objective,
        )

    def settings(self) -> Iterable[tuple[str, str, str]]:
        yield from self.props.value()
        yield (
            Keyword.CoreDevice.value,
            Keyword.CoreShutter.value,
            self.active_shutter.currentText(),
        )


class _CameraGroupBox(QGroupBox):
    valueChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Camera", parent)
        self.setCheckable(True)
        self.setChecked(False)
        self.toggled.connect(self.valueChanged)

        self.active_camera = QComboBox(self)
        self.active_camera.currentIndexChanged.connect(self.valueChanged)

        self.props = DevicePropertyTable(self, connect_core=False)
        self.props.valueChanged.connect(self.valueChanged)
        self.props.setRowsCheckable(True)
        self.props.filterDevices(
            include_devices=[DeviceType.Camera],
            include_read_only=False,
        )

        camera_layout = QHBoxLayout()
        camera_layout.setContentsMargins(2, 0, 0, 0)
        camera_layout.addWidget(QLabel("Active Camera:"), 0)
        camera_layout.addWidget(self.active_camera, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        layout.addLayout(camera_layout)
        layout.addWidget(self.props)

    def settings(self) -> Iterable[tuple[str, str, str]]:
        yield from self.props.value()
        yield (
            Keyword.CoreDevice.value,
            Keyword.CoreCamera.value,
            self.active_camera.currentText(),
        )


class _ObjectiveGroupBox(QGroupBox):
    valueChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Objective", parent)
        self.setCheckable(True)
        self.setChecked(False)
        self.toggled.connect(self.valueChanged)
        self._obj_wdg = ObjectivesWidget()

        layout = QVBoxLayout(self)
        layout.addWidget(self._obj_wdg)
        layout.setContentsMargins(12, 0, 12, 0)
