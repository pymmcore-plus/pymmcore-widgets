from __future__ import annotations

from typing import Iterable

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
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

from pymmcore_widgets._device_property_table import DevicePropertyTable
from pymmcore_widgets._objective_widget import ObjectivesWidget


class OpticalConfigDialog(QWidget):
    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)
        self._core = mmcore or CMMCorePlus.instance()
        self._model = ConfigGroup("")

        self.groups = QComboBox(self)
        self.groups.addItems(self._core.getAvailableConfigGroups())
        self.groups.currentTextChanged.connect(self.load_group)

        self._name_list = QListWidget(self)
        self._name_list.setEditTriggers(
            QListWidget.EditTrigger.DoubleClicked
            | QListWidget.EditTrigger.SelectedClicked
        )
        self._name_list.itemSelectionChanged.connect(self._on_selection_changed)
        self._name_list.currentTextChanged.connect(self._on_current_name_changed)
        self._name_list.itemChanged.connect(self._on_item_changed)
        self._active_item_name = ""

        # Second column: buttons ------------------------------------
        new = QPushButton("New...")
        new.clicked.connect(self._add_oc)
        remove = QPushButton("Remove...")
        remove.clicked.connect(self._remove_oc_dialog)
        dupe = QPushButton("Duplicate...")
        dupe.clicked.connect(self._dupe_oc)
        activate = QPushButton("Set Active")
        activate.clicked.connect(self._activate_oc)
        export = QPushButton("Export...")
        # export.clicked.connect(self._export)
        import_ = QPushButton("Import...")
        # import_.clicked.connect(self._import)

        # Groups -----------------------------------------------------

        self._scope_group = _LightPathGroupBox(self, mmcore=self._core)
        self._cam_group = _CameraGroupBox(self, mmcore=self._core)
        self._obj_group = _ObjectiveGroupBox(self, mmcore=self._core)
        self._scope_group.valueChanged.connect(self._on_value_changed)
        self._cam_group.valueChanged.connect(self._on_value_changed)
        self._obj_group.valueChanged.connect(self._on_value_changed)

        group_splitter = QSplitter(Qt.Orientation.Vertical, self)
        group_splitter.setContentsMargins(0, 0, 0, 0)
        group_splitter.addWidget(self._scope_group)
        group_splitter.addWidget(self._cam_group)
        group_splitter.addWidget(self._obj_group)
        group_splitter.setStretchFactor(0, 3)
        group_splitter.setStretchFactor(1, 1)
        group_splitter.setStretchFactor(2, 0)

        left_top = QWidget()
        # left_top.hide()
        left_top_layout = QHBoxLayout(left_top)
        left_top_layout.setContentsMargins(0, 0, 0, 0)
        left_top_layout.addWidget(QLabel("Group:"), 0)
        left_top_layout.addWidget(self.groups, 1)

        button_column = QVBoxLayout()
        button_column.addWidget(new)
        button_column.addWidget(remove)
        button_column.addWidget(dupe)
        button_column.addWidget(activate)
        button_column.addWidget(export)
        button_column.addWidget(import_)
        button_column.addStretch()

        left_bot = QHBoxLayout()
        left_bot.addWidget(self._name_list)
        left_bot.addLayout(button_column)

        left_layout = QVBoxLayout()
        left_layout.addWidget(left_top)
        left_layout.addLayout(left_bot)

        layout = QHBoxLayout(self)
        layout.addLayout(left_layout)
        layout.addWidget(group_splitter, 1)

        self.resize(1080, 920)

    def _add_oc(self) -> None:
        i = 1
        new_name = "Config"
        while new_name in self._model.presets:
            new_name = f"Config {i}"
            i += 1
        self._model.presets[new_name] = ConfigPreset(name=new_name)
        self._add_editable_item(new_name)

    def _remove_oc_dialog(self) -> None:
        if (current := self._name_list.currentItem()) is None:
            return
        if (
            QMessageBox.question(
                self,
                "Remove Preset",
                f"Are you sure you want to remove {current.text()!r}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            self._model.presets.pop(current.text())
            self._name_list.takeItem(self._name_list.currentRow())

    def _dupe_oc(self) -> None:
        if (current := self._name_list.currentItem()) is None:
            return
        selected = current.text()
        new_name = f"{selected} (Copy)"
        i = 1
        while new_name in self._model.presets:
            new_name = f"{selected} (Copy {i})"
            i += 1
        settings = self._model.presets[selected].settings
        self._model.presets[new_name] = ConfigPreset(name=new_name, settings=settings)
        self._add_editable_item(new_name)

    def _activate_oc(self) -> None:
        if (current := self._name_list.currentItem()) is None:
            return
        for dev, prop, value in self._model.presets[current.text()].settings:
            self._core.setProperty(dev, prop, value)

    def load_group(self, group: str) -> None:
        self.groups.setCurrentText(group)

        with signals_blocked(self._name_list):
            self._name_list.clear()
            for n in self._core.getAvailableConfigs(group):
                self._add_editable_item(n)

        self._model = ConfigGroup.create_from_core(self._core, group)
        self._name_list.setCurrentRow(0)

    def _add_editable_item(self, name: str) -> None:
        item = QListWidgetItem(name)
        item.setFlags(
            Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
        )
        self._name_list.addItem(item)
        # select it
        self._name_list.setCurrentItem(item)

    def load_preset(self, name: str) -> None:
        settings = self._model.presets[name].settings
        self._scope_group.props.setValue(settings)
        self._cam_group.props.setValue(settings)
        for s in settings:
            if s.device_name == Keyword.CoreDevice:
                if s.property_name == Keyword.CoreShutter:
                    self._scope_group.active_shutter.setCurrentText(s.property_value)
                elif s.property_name == Keyword.CoreCamera:
                    self._cam_group.active_camera.setCurrentText(s.property_value)

    def _on_selection_changed(self) -> None:
        if item := self._name_list.currentItem():
            self.load_preset(item.text())

    def _on_current_name_changed(self, text: str) -> None:
        self._active_item_name = text

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        new_text = item.text()
        previous_text = self._active_item_name
        if new_text in self._model.presets and new_text != previous_text:
            QMessageBox.warning(self, "Duplicate Item", f"{new_text!r} already exists.")
            item.setText(previous_text)
        else:
            self._model.presets[new_text] = self._model.presets.pop(previous_text)
            self._active_item_name = new_text

    def _on_value_changed(self) -> None:
        if (current := self._name_list.currentItem()) is None:
            return
        current_name = current.text()
        self._model.presets[current_name].settings = self._current_settings()

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
    if any(x in prop.device for x in prop.core.guessObjectiveDevices()):
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
            predicate=light_path_predicate if not checked else None,
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
