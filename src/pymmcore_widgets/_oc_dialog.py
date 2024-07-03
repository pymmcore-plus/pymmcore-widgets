import re

from pymmcore_plus import CMMCorePlus, DeviceType
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

        # Second column: buttons ------------------------------------
        new = QPushButton("New...")
        new.clicked.connect(self._add_oc)
        remove = QPushButton("Remove...")
        # remove.clicked.connect(self._remove_oc_dialog)
        dupe = QPushButton("Duplicate...")
        # dupe.clicked.connect(self._dupe_oc_dialog)
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

        self._cam_group = _CameraGroupBox(self, mmcore=self._core)
        self._scope_group = _ScopeGroupBox(self, mmcore=self._core)
        self._obj_group = _ObjectiveGroupBox(self, mmcore=self._core)

        group_splitter = QSplitter(Qt.Orientation.Vertical, self)
        group_splitter.addWidget(self._cam_group)
        group_splitter.addWidget(self._scope_group)
        group_splitter.addWidget(self._obj_group)
        group_splitter.setStretchFactor(0, 1)
        group_splitter.setStretchFactor(1, 4)
        group_splitter.setStretchFactor(2, 0)

        layout = QHBoxLayout(self)
        layout.addWidget(self._name_list)
        layout.addLayout(button_column)
        layout.addWidget(group_splitter, 1)

    def _add_oc(self) -> None:
        self._name_list.addItem("New Optical Configuration")


class _CameraGroupBox(QGroupBox):
    valueChanged = Signal()

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__("Camera", parent)
        self.setCheckable(True)
        self._core = mmcore or CMMCorePlus.instance()

        self.props = DevicePropertyTable(self, mmcore=mmcore, connect_core=False)
        self.props.valueChanged.connect(self.valueChanged)
        self.props.setRowsCheckable(True)
        self.props.filterDevices(
            include_devices=[DeviceType.Camera],
            include_read_only=False,
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self.props)


class _ScopeGroupBox(QGroupBox):
    valueChanged = Signal()

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__("Microscope", parent)
        self.setCheckable(True)
        self._core = mmcore or CMMCorePlus.instance()

        self.active_shutter = QComboBox(self)
        shutters = self._core.getLoadedDevicesOfType(DeviceType.Shutter)
        self.active_shutter.addItems(shutters)

        self.props = DevicePropertyTable(self, mmcore=mmcore, connect_core=False)
        self.props.valueChanged.connect(self.valueChanged)
        self.props.setRowsCheckable(True)
        self.props.filterDevices(
            include_devices=[
                DeviceType.State,
                DeviceType.MagnifierDevice,
                DeviceType.AutoFocus,
            ],
            include_read_only=False,
            include_pre_init=False,
            query=re.compile(r"^(?!.*-State).*"),
        )

        shutter_layout = QHBoxLayout()
        shutter_layout.addWidget(QLabel("Active Shutter:"), 0)
        shutter_layout.addWidget(self.active_shutter, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(shutter_layout)
        layout.addWidget(self.props)


class _ObjectiveGroupBox(QGroupBox):
    valueChanged = Signal()

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__("Objective", parent)
        self.setCheckable(True)
        self._obj_wdg = ObjectivesWidget(mmcore=mmcore)

        layout = QVBoxLayout(self)
        layout.addWidget(self._obj_wdg)
        layout.setContentsMargins(12, 0, 12, 0)
