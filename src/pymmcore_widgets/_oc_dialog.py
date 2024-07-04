from typing import Iterable

from pymmcore_plus import CMMCorePlus, DeviceType, Keyword
from pymmcore_plus.model import ConfigGroup, ConfigPreset, Setting
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets._device_property_table import DevicePropertyTable
from pymmcore_widgets._objective_widget import ObjectivesWidget


class OpticalConfigDialog(QWidget):
    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)
        self._core = mmcore or CMMCorePlus.instance()

        self._name_list = QListWidget(self)
        self._name_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._name_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._name_list.setEditTriggers(
            QListWidget.EditTrigger.DoubleClicked
            & QListWidget.EditTrigger.SelectedClicked
        )
        self._name_list.itemSelectionChanged.connect(self._on_selection_changed)

        # Second column: buttons ------------------------------------
        new = QPushButton("New...")
        new.clicked.connect(self._add_oc)
        remove = QPushButton("Remove...")
        # remove.clicked.connect(self._remove_oc_dialog)
        dupe = QPushButton("Duplicate...")
        dupe.clicked.connect(self._dupe_oc)
        activate = QPushButton("Set Active")
        # activate.clicked.connect(self._activate_oc)
        export = QPushButton("Export...")
        # export.clicked.connect(self._export)
        import_ = QPushButton("Import...")
        # import_.clicked.connect(self._import)

        button_column = QVBoxLayout()
        button_column.addWidget(new)
        button_column.addWidget(remove)
        button_column.addWidget(dupe)
        button_column.addWidget(activate)
        button_column.addWidget(export)
        button_column.addWidget(import_)
        button_column.addStretch()

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

        layout = QHBoxLayout(self)
        layout.addWidget(self._name_list)
        layout.addLayout(button_column)
        layout.addWidget(group_splitter, 1)

        self.resize(1280, 920)

    def _add_oc(self) -> None:
        new_name = "New Optical Configuration"
        self._model.presets[new_name] = ConfigPreset(name=new_name)
        self._name_list.addItem("New Optical Configuration")

    def _dupe_oc(self) -> None:
        if (current := self._name_list.currentItem()) is None:
            return
        selected = current.text()
        new_name = f"{selected} (Copy)"
        settings = self._model.presets[selected].settings
        self._model.presets[new_name] = ConfigPreset(name=new_name, settings=settings)
        self._name_list.addItem(new_name)

    def load_group_from_core(self, group: str) -> None:
        self._name_list.clear()
        self._name_list.addItems(self._core.getAvailableConfigs(group))
        self._model = ConfigGroup.create_from_core(self._core, group)
        self._name_list.setCurrentRow(0)

    def load_preset(self, name: str) -> None:
        settings = self._model.presets[name].settings
        from rich import print

        print(settings)

        self._scope_group.props.setValue(settings)
        self._cam_group.props.setValue(settings)
        for s in settings:
            if s.device_name == Keyword.CoreDevice:
                if s.property_name == Keyword.CoreShutter:
                    self._scope_group.active_shutter.setCurrentText(s.property_value)
                elif s.property_name == Keyword.CoreCamera:
                    self._cam_group.active_camera.setCurrentText(s.property_value)

    def _on_selection_changed(self) -> None:
        self.load_preset(self._name_list.currentItem().text())

    def _on_value_changed(self) -> None:
        if (current := self._name_list.currentItem()) is None:
            return
        current_name = current.text()
        self._model.presets[current_name].settings = self._current_settings()
        print(self._model.presets[current_name])

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

        self.props = DevicePropertyTable(self, mmcore=mmcore, connect_core=False)
        self.props.valueChanged.connect(self.valueChanged)
        self.props.setRowsCheckable(True)
        self.props.filterDevices(
            exclude_devices=[DeviceType.Camera, DeviceType.Core],
            include_read_only=False,
            include_pre_init=False,
            # query=re.compile(r"^(?!.*-State).*"),
        )

        shutter_layout = QHBoxLayout()
        shutter_layout.setContentsMargins(2, 0, 0, 0)
        shutter_layout.addWidget(QLabel("Active Shutter:"), 0)
        shutter_layout.addWidget(self.active_shutter, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        layout.addLayout(shutter_layout)
        layout.addWidget(self.props)

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
