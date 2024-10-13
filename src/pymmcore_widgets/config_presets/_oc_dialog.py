from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Callable, Generic, TypeVar

from pymmcore_plus import CMMCorePlus, DeviceProperty, DeviceType, Keyword
from pymmcore_plus.model import ConfigGroup, ConfigPreset, Setting
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpacerItem,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets.control._objective_widget import ObjectivesWidget
from pymmcore_widgets.device_properties import PropertyBrowser
from pymmcore_widgets.device_properties._device_property_table import (
    DevicePropertyTable,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


class UniqueNameList(QWidget):
    nameAdded = Signal(str)
    nameRemoved = Signal(str)
    nameDuplicated = Signal(str, str)  # old, new
    nameChanged = Signal(str, str)  # old, new
    currentNameChanged = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        base_name: str = "Item",
    ) -> None:
        super().__init__(parent)
        self._base_name = base_name
        self._confirm_removal = True
        self._name_list = QListWidget(self)
        self._name_list.setEditTriggers(
            QListWidget.EditTrigger.DoubleClicked
            | QListWidget.EditTrigger.SelectedClicked
        )
        self._name_list.itemSelectionChanged.connect(self.currentNameChanged)

        # Second column: buttons ------------------------------------
        self.btn_new = QPushButton("New")
        self.btn_new.clicked.connect(self._add_oc)
        self.btn_remove = QPushButton("Remove...")
        self.btn_remove.clicked.connect(self._remove_oc_dialog)
        self.btn_duplicate = QPushButton("Duplicate")
        self.btn_duplicate.clicked.connect(self._dupe_oc)

        self.btn_layout = QVBoxLayout()
        self.btn_layout.addWidget(self.btn_new)
        self.btn_layout.addWidget(self.btn_remove)
        self.btn_layout.addWidget(self.btn_duplicate)
        self.btn_layout.addStretch()

        layout = QHBoxLayout(self)
        layout.addWidget(self._name_list)
        layout.addLayout(self.btn_layout)

    def listWidget(self) -> QListWidget:
        return self._name_list

    def clear(self) -> None:
        self._name_list.clear()

    def _on_current_name_changed(self, text: str) -> None:
        self._active_item_name = text
        self._previous_names = self._current_names()

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        new_text = item.text()
        previous_text = self._active_item_name
        if new_text in self._previous_names and new_text != previous_text:
            QMessageBox.warning(self, "Duplicate Item", f"{new_text!r} already exists.")
            item.setText(previous_text)
            return

        self._active_item_name = new_text
        self.nameChanged(previous_text, new_text)

    def _current_names(self) -> set[str]:
        return {self._name_list.item(i).text() for i in range(self._name_list.count())}

    def _add_oc(self) -> None:
        existing = self._current_names()
        i = 1
        new_name = self._base_name
        while new_name in existing:
            new_name = f"{self._base_name} {i}"
            i += 1
        self.addName(new_name)
        self.nameAdded.emit(new_name)
        self._name_list.setCurrentRow(self._name_list.count() - 1)

    def _remove_oc_dialog(self) -> None:
        if (current := self._name_list.currentItem()) is None:
            return
        if self._confirm_removal:
            if (
                QMessageBox.question(
                    self,
                    "Remove Preset",
                    f"Are you sure you want to remove {current.text()!r}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.No
            ):
                return
        if item := self._name_list.takeItem(self._name_list.currentRow()):
            self.nameRemoved.emit(item.text())

    def _dupe_oc(self) -> None:
        if (current := self._name_list.currentItem()) is None:
            return
        existing = self._current_names()
        name = current.text()
        new_name = f"{name} (Copy)"
        i = 1
        while new_name in existing:
            new_name = f"{name} (Copy {i})"
            i += 1
        self.addName(new_name)
        self.nameDuplicated.emit(name, new_name)
        self._name_list.setCurrentRow(self._name_list.count() - 1)

    def addName(self, name: str) -> None:
        item = QListWidgetItem(name)
        item.setFlags(
            Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
        )
        self._name_list.addItem(item)

    def addNames(self, names: Iterable[str]) -> None:
        for name in names:
            self.addName(name)

    def currentName(self) -> str | None:
        if (current := self._name_list.currentItem()) is not None:
            return current.text()  # type: ignore [no-any-return]
        return None

    def setCurrentName(self, name: str) -> None:
        if name == self.currentName():
            return
        for i in range(self._name_list.count()):
            if item := self._name_list.item(i):
                if item.text() == name:
                    self._name_list.setCurrentItem(item)


T = TypeVar("T")


class _Thing(UniqueNameList, Generic[T]):
    def __init__(self, parent: QWidget | None = None, base_name: str = "Item") -> None:
        super().__init__(parent, base_name)
        self._root: dict[str, T] = {}
        self._key_factory: Callable[[], T] = ConfigPreset
        self.nameAdded.connect(self._on_key_added)
        self.nameRemoved.connect(self._on_key_removed)
        self.nameChanged.connect(self._on_key_renamed)
        self.nameDuplicated.connect(self._on_key_duplicated)

    def setRoot(self, root: dict[str, T]) -> None:
        self._root = root
        self.clear()
        self.addNames(root)

    def root(self) -> dict[str, T]:
        return self._root

    def currentKey(self) -> str | None:  # remove me
        return self.currentName()

    def currentValue(self) -> T | None:
        if key := self.currentKey():
            return self._root.get(key)
        return None

    def _on_key_added(self, key: str) -> None:
        self._root[key] = self._key_factory(name=key)

    def _on_key_removed(self, key: str) -> None:
        self._root.pop(key, None)

    def _on_key_renamed(self, old_key: str, new_key: str) -> None:
        self._root[new_key] = self._root.pop(old_key)

    def _on_key_duplicated(self, existing_key: str, new_key: str) -> None:
        clone = deepcopy(self._root[existing_key])
        clone.name = new_key  # this is too magic
        self._root[new_key] = clone


class PresetList(_Thing[ConfigPreset]):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, "Config")
        self._key_factory: Callable = ConfigPreset


class GroupList(_Thing[ConfigGroup]):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, "Group")
        self._key_factory: Callable = ConfigGroup


class OpticalConfigDialog(QWidget):
    def __init__(
        self,
        data: dict[str, ConfigGroup] | None = None,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent)
        self._core = mmcore or CMMCorePlus.instance()

        self.groups = GroupList(self)
        self.groups.setRoot(data or {})
        self.groups.currentNameChanged.connect(self._on_current_group_changed)

        self.presets = PresetList(self)
        self.presets.currentNameChanged.connect(self._on_current_preset_changed)

        self.btn_activate = QPushButton("Set Active")
        self.btn_activate.clicked.connect(self._activate_preset)
        self.presets.btn_layout.insertWidget(3, self.btn_activate)

        # Groups -----------------------------------------------------

        self._scope_group = _LightPathGroupBox(self, mmcore=self._core)
        self._cam_group = _CameraGroupBox(self, mmcore=self._core)
        self._obj_group = _ObjectiveGroupBox(self, mmcore=self._core)
        self._scope_group.valueChanged.connect(self._update_model_preset)
        self._cam_group.valueChanged.connect(self._update_model_preset)
        self._obj_group.valueChanged.connect(self._update_model_preset)

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.groups)
        left_layout.addWidget(self.presets)

        right_splitter = QSplitter(Qt.Orientation.Vertical, self)
        right_splitter.setContentsMargins(0, 0, 0, 0)
        right_splitter.addWidget(self._scope_group)
        right_splitter.addWidget(self._cam_group)
        right_splitter.addWidget(self._obj_group)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 1)
        right_splitter.setStretchFactor(2, 0)

        self.expert_table = PropertyBrowser(parent=self, mmcore=self._core)
        self.expert_table._prop_table.setRowsCheckable(True)
        self.expert_table._device_filters.setShowReadOnly(False)
        self.expert_table._device_filters._read_only_checkbox.hide()
        self.expert_table._device_filters.setShowPreInitProps(False)
        self.expert_table._device_filters._pre_init_checkbox.hide()

        basic_expert_tabs = QTabWidget(self)
        basic_expert_tabs.addTab(right_splitter, "Basic")
        basic_expert_tabs.addTab(self.expert_table, "Expert")

        layout = QHBoxLayout(self)
        layout.addLayout(left_layout)
        layout.addWidget(basic_expert_tabs, 1)

        self.resize(1080, 920)

    def _on_current_group_changed(self) -> None:
        if config_group := self.groups.currentValue():
            self.presets.setRoot(config_group.presets)
        self.presets.listWidget().setCurrentRow(0)

    def setCurrentGroup(self, group: str) -> None:
        self.groups.setCurrentName(group)

    def _on_current_preset_changed(self) -> None:
        if not (config_preset := self.presets.currentValue()):
            return
        settings = config_preset.settings

        # update all the property browser tables
        self._scope_group.props.setValue(settings)
        self._cam_group.props.setValue(settings)
        for s in settings:
            if s.device_name == Keyword.CoreDevice:
                if s.property_name == Keyword.CoreShutter:
                    self._scope_group.active_shutter.setCurrentText(s.property_value)
                elif s.property_name == Keyword.CoreCamera:
                    self._cam_group.active_camera.setCurrentText(s.property_value)

    def _activate_preset(self) -> None:
        if (current := self.presets.currentName()) is not None:
            for dev, prop, value in self._config_group.presets[current].settings:
                self._core.setProperty(dev, prop, value)

    def _update_model_preset(self) -> None:
        if preset := self.presets.currentValue():
            preset.settings = self._current_settings()

    def _current_settings(self) -> list[Setting]:
        tmp = {}
        if self._scope_group.isChecked():
            tmp.update(
                {(dev, prop): val for dev, prop, val in self._scope_group.settings()}
            )
        if self._cam_group.isChecked():
            tmp.update(
                {(dev, prop): val for dev, prop, val in self._cam_group.settings()}
            )
        return [Setting(*k, v) for k, v in tmp.items()]


def is_not_objective(prop: DeviceProperty) -> bool:
    return not any(x in prop.device for x in prop.core.guessObjectiveDevices())


def light_path_predicate(prop: DeviceProperty) -> bool | None:
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
    if not is_not_objective(prop):
        return False
    return None


class _LightPathGroupBox(QGroupBox):
    valueChanged = Signal()

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__("Light Path", parent)
        self.setCheckable(True)
        self.toggled.connect(self.valueChanged)
        self._core = mmcore or CMMCorePlus.instance()

        self.active_shutter = QComboBox(self)
        shutters = self._core.getLoadedDevicesOfType(DeviceType.Shutter)
        self.active_shutter.addItems(("", *shutters))
        self.active_shutter.currentIndexChanged.connect(self.valueChanged)

        self.show_all = QCheckBox("Show All Properties", self)
        self.show_all.toggled.connect(self._show_all_toggled)

        self.props = DevicePropertyTable(self, mmcore=mmcore, connect_core=False)
        self.props.valueChanged.connect(self.valueChanged)
        self.props.setRowsCheckable(True)
        self.props.filterDevices(
            include_read_only=False,
            include_pre_init=False,
            predicate=light_path_predicate,
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
            predicate=light_path_predicate if not checked else is_not_objective,
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

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__("Camera", parent)
        self.setCheckable(True)
        self.setChecked(False)
        self.toggled.connect(self.valueChanged)
        self._core = mmcore or CMMCorePlus.instance()

        self.active_camera = QComboBox(self)
        cameras = self._core.getLoadedDevicesOfType(DeviceType.Camera)
        self.active_camera.addItems(("", *cameras))
        self.active_camera.currentIndexChanged.connect(self.valueChanged)

        self.props = DevicePropertyTable(self, mmcore=mmcore, connect_core=False)
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

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__("Objective", parent)
        self.setCheckable(True)
        self.setChecked(False)
        self.toggled.connect(self.valueChanged)
        self._obj_wdg = ObjectivesWidget(mmcore=mmcore)

        layout = QVBoxLayout(self)
        layout.addWidget(self._obj_wdg)
        layout.setContentsMargins(12, 0, 12, 0)
