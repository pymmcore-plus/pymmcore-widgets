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
    QSpacerItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

from pymmcore_widgets.control import ObjectivesWidget
from pymmcore_widgets.device_properties import DevicePropertyTable

from ._unique_name_list import MapManager

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from pymmcore_plus import CMMCorePlus, DeviceProperty

    class NamedObject(Protocol):
        name: str

    T = TypeVar("T", bound=NamedObject)


def _copy_named_obj(obj: T, new_name: str) -> T:
    """Copy object `obj` and set its name to `new_name`."""
    obj = deepcopy(obj)
    obj.name = new_name
    return obj


class ConfigGroupsEditor(QWidget):
    """Widget for managing configuration groups and presets.

    This is a high level widget that allows the user to manage all of the configuration
    groups/presets. It is composed of a list of groups on the top left and a list of
    presets on the bottom left.  Once a preset is selected, the user can view and edit
    all of the settings associated with that preset.

    By design, the widget is not connected to a core instance, (changes to the settings
    do not affect the core instance).  They must be exported and applied to the core
    explicitly.
    """

    def __init__(
        self,
        data: Iterable[ConfigGroup] | None = None,
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

        # Track initialization state to prevent premature model updates
        self._initializing = True  # Flag to prevent premature model updates

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

        # basic_expert_tabs = QTabWidget(self)
        # basic_expert_tabs.addTab(right_splitter, "Basic")
        # basic_expert_tabs.addTab(self.expert_table, "Expert")

        layout = QHBoxLayout(self)
        layout.addLayout(left_layout)
        layout.addWidget(right_splitter, 1)

        self.groups.currentKeyChanged.connect(self._on_current_group_changed)
        if data is not None:
            self.setData(data)

        # after groups.setRoot to prevent a bunch of stuff when setting initial data
        self.presets.currentKeyChanged.connect(self._update_gui_from_model)

    # Public API -------------------------------------------------------

    def setData(self, data: Iterable[ConfigGroup]) -> None:
        """Replace all data with the given collection of ConfigGroup objects."""
        self.groups.setRoot({group.name: group for group in data})

    def data(self) -> Collection[ConfigGroup]:
        """Return the current data as a collection of ConfigGroup objects."""
        return deepcopy(list(self.groups.root().values()))

    def setCurrentGroup(self, group: str) -> None:
        """Set the current group by name.

        If the group does not exist, nothing happens (a warning is logged).
        """
        self.groups.setCurrentKey(group)

    def setCurrentPreset(self, preset: str) -> None:
        """Set the current preset by name.

        If the preset does not exist in the current group, nothing happens
        (a warning is logged).
        """
        self.presets.setCurrentKey(preset)

    def currentSettings(self) -> Collection[Setting]:
        """Return the current settings as a collection of Setting objects.

        This returns all of the currently **checked** property settings.
        """
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
        return [Setting(dev, prop, val) for (dev, prop), val in tmp.items()]

    def setCurrentSettings(self, settings: Iterable[Setting]) -> None:
        """Set the current settings to the given collection of Setting objects."""
        settings_list = list(settings)

        # Determine which groups should be enabled based on settings
        has_light_path_settings = False
        has_camera_settings = False
        has_core_shutter = False
        has_core_camera = False
        active_shutter = ""
        active_camera = ""

        for s in settings_list:
            if s.device_name == Keyword.CoreDevice:
                if s.property_name == Keyword.CoreShutter:
                    active_shutter = s.property_value
                    has_light_path_settings = True
                    has_core_shutter = True
                elif s.property_name == Keyword.CoreCamera:
                    active_camera = s.property_value
                    has_camera_settings = True
                    has_core_camera = True
            else:
                # Check if this setting belongs to light path or camera group
                if s.device_name == "Camera":
                    has_camera_settings = True
                elif s.device_name in [
                    "Dichroic",
                    "Emission",
                    "Excitation",
                    "Path",
                    "Shutter",
                ]:
                    has_light_path_settings = True

        # Enable/disable groups based on whether they have settings
        self._light_path_group.setChecked(has_light_path_settings)
        self._cam_group.setChecked(has_camera_settings)

        # Set flags for including active device settings
        self._light_path_group._include_active_shutter = has_core_shutter
        self._cam_group._include_active_camera = has_core_camera

        # Filter settings for each group to avoid conflicts
        light_path_settings = [
            s
            for s in settings_list
            if s.device_name != "Camera"
            and not (
                s.device_name == Keyword.CoreDevice
                and s.property_name == Keyword.CoreCamera
            )
        ]
        camera_settings = [
            s
            for s in settings_list
            if s.device_name == "Camera"
            or (
                s.device_name == Keyword.CoreDevice
                and s.property_name == Keyword.CoreCamera
            )
        ]

        # Update property tables with filtered settings
        self._light_path_group.props.setCheckedProperties(light_path_settings)
        self._cam_group.props.setCheckedProperties(camera_settings)

        # Set active devices only if they were explicitly specified
        self._light_path_group.active_shutter.setCurrentText(active_shutter)
        self._cam_group.active_camera.setCurrentText(active_camera)

    # Methods requiring a core instance ------------------------------

    @classmethod
    def create_from_core(
        cls, core: CMMCorePlus, parent: QWidget | None = None
    ) -> ConfigGroupsEditor:
        """Create a new instance and update it with the given core instance."""
        groups = ConfigGroup.all_config_groups(core)
        self = cls(data=groups.values(), parent=parent)
        self.update_options_from_core(core)
        self._initializing = False
        return self

    def update_options_from_core(self, core: CMMCorePlus) -> None:
        """Populate the comboboxes with the available devices from the core."""
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
        """Update GUI when preset selection changes."""
        if preset := self._selected_preset():
            self.setCurrentSettings(preset.settings)

    def _update_model_from_gui(self) -> None:
        if self._initializing:
            return
        if preset := self._selected_preset():
            current_settings = list(self.currentSettings())
            preset.settings = current_settings


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

        # Track whether to include active shutter in settings
        self._include_active_shutter = False

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

    def _show_all_toggled(self, show_all: bool) -> None:
        self.props.filterDevices(
            exclude_devices=(DeviceType.Camera, DeviceType.Core),
            include_read_only=False,
            include_pre_init=False,
            always_include_checked=True,
            predicate=_light_path_predicate if not show_all else _is_not_objective,
        )

    def settings(self) -> Iterable[tuple[str, str, str]]:
        yield from self.props.value()
        if self._include_active_shutter:
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

        # Track whether to include active camera in settings
        self._include_active_camera = False

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
        if self._include_active_camera:
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
