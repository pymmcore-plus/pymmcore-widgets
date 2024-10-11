from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Sequence

from pymmcore_plus import CMMCorePlus, DeviceProperty, DeviceType, Keyword
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets.device_properties._device_property_table import (
    DevicePropertyTable,
)

if TYPE_CHECKING:
    from pymmcore_plus.model import Setting


class _PropertiesGroupBox(QGroupBox):
    """Base class for all property group boxes."""

    valueChanged = Signal()

    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(False)
        self.toggled.connect(self.valueChanged)
        self._mmc = mmcore or CMMCorePlus.instance()

        self.props = DevicePropertyTable(self, mmcore=self._mmc, connect_core=False)
        self.props.valueChanged.connect(self.valueChanged)
        self.props.setRowsCheckable(True)

    def value(self) -> Iterable[tuple[str, str, str]]:
        """Yield all the properties that are checked."""
        yield from self.props.value()

    def setValue(self, values: Sequence[tuple[str, str, str] | Setting]) -> None:
        """Set the properties and check the group box if any property is set."""
        self.props.setValue(values)

        # Check if the group box should be checked or not depending on the values.
        # the properties are set only if at least one row is visible.
        for d, p, _ in values:
            item = self.props.findItems(f"{d}-{p}", Qt.MatchFlag.MatchExactly)[0]
            row = item.row()
            if not self.props.isRowHidden(row):
                self.setChecked(True)
                return

        self.setChecked(False)

    def update_filter(self, query: str = "", checked: bool = False) -> None:
        """Show only the selected properties."""
        self.props.filterDevices(query=query, selected_only=checked)


def light_path_predicate(prop: DeviceProperty) -> bool | None:
    """Predicate to filter the light path properties."""
    devtype = prop.deviceType()
    # exclude all shutter devices but the Multi Shutter Utility  since we need to be
    # able to set which shutter to use withuin the Multi Shutter.
    if devtype == DeviceType.Shutter and "Physical Shutter" not in prop.name:
        return False
    if any(x in prop.device for x in prop.core.guessObjectiveDevices()):
        return False
    return None


class _LightPathGroupBox(_PropertiesGroupBox):
    """GroupBox to select the properties related to the light path."""

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__("Light Path", parent, mmcore)

        # add active shutter combobox
        self.active_shutter = QComboBox(self)
        shutters = self._mmc.getLoadedDevicesOfType(DeviceType.Shutter)
        self.active_shutter.addItems(("", *shutters))
        self.active_shutter.currentIndexChanged.connect(self.valueChanged)

        self.update_filter()

        shutter_layout = QHBoxLayout()
        shutter_layout.setContentsMargins(2, 0, 0, 0)
        shutter_layout.addWidget(QLabel("Active Shutter:"), 0)
        shutter_layout.addWidget(self.active_shutter, 1)
        shutter_layout.addSpacerItem(QSpacerItem(40, 0))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        layout.addLayout(shutter_layout)
        layout.addWidget(self.props)

    def value(self) -> Iterable[tuple[str, str, str]]:
        """Yield all the properties that are checked."""
        yield from super().value()
        yield (
            Keyword.CoreDevice.value,
            Keyword.CoreShutter.value,
            self.active_shutter.currentText(),
        )

    def setValue(self, values: Sequence[tuple[str, str, str] | Setting]) -> None:
        """Set the properties and check the group box if any property is set."""
        super().setValue(values)
        for d, p, v in values:
            if d == Keyword.CoreDevice.value and p == Keyword.CoreShutter.value:
                self.active_shutter.setCurrentText(v)
                self.setChecked(True)
                break

    def update_filter(self, query: str = "", checked: bool = False) -> None:
        """Show only the selected properties."""
        self.props.filterDevices(
            query=query,
            exclude_devices=[
                DeviceType.Camera,
                DeviceType.Core,
                DeviceType.AutoFocus,
                DeviceType.Stage,
                DeviceType.XYStage,
            ],
            include_read_only=False,
            include_pre_init=False,
            predicate=light_path_predicate,
            selected_only=checked,
        )


class _CameraGroupBox(_PropertiesGroupBox):
    """GroupBox to select the properties related to the cameras."""

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__("Camera", parent, mmcore)

        # add active camera combobox
        self.active_camera = QComboBox(self)
        cameras = self._mmc.getLoadedDevicesOfType(DeviceType.Camera)
        self.active_camera.addItems(("", *cameras))
        self.active_camera.currentIndexChanged.connect(self.valueChanged)

        self.update_filter()

        camera_layout = QHBoxLayout()
        camera_layout.setContentsMargins(2, 0, 0, 0)
        camera_layout.addWidget(QLabel("Active Camera:"), 0)
        camera_layout.addWidget(self.active_camera, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        layout.addLayout(camera_layout)
        layout.addWidget(self.props)

    def value(self) -> Iterable[tuple[str, str, str]]:
        """Yield all the properties that are checked."""
        yield from super().value()
        yield (
            Keyword.CoreDevice.value,
            Keyword.CoreCamera.value,
            self.active_camera.currentText(),
        )

    def setValue(self, values: Sequence[tuple[str, str, str] | Setting]) -> None:
        """Set the properties and check the group box if any property is set."""
        super().setValue(values)
        for d, p, v in values:
            if d == Keyword.CoreDevice.value and p == Keyword.CoreCamera.value:
                self.active_camera.setCurrentText(v)
                self.setChecked(True)
                break

    def update_filter(self, query: str = "", checked: bool = False) -> None:
        """Show only the selected properties."""
        self.props.filterDevices(
            query=query,
            include_devices=[DeviceType.Camera],
            include_read_only=False,
            include_pre_init=False,
            selected_only=checked,
        )


class _StageGroupBox(_PropertiesGroupBox):
    """GroupBox to select the properties related to the stages."""

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__("Stage", parent, mmcore)

        # add active xy stage combobox
        self.active_xy_stage = QComboBox(self)
        xy_stages = self._mmc.getLoadedDevicesOfType(DeviceType.XYStage)
        self.active_xy_stage.addItems(("", *xy_stages))
        self.active_xy_stage.currentIndexChanged.connect(self.valueChanged)

        # add active x stage combobox
        self.active_z_stage = QComboBox(self)
        stages = self._mmc.getLoadedDevicesOfType(DeviceType.Stage)
        self.active_z_stage.addItems(("", *stages))
        self.active_z_stage.currentIndexChanged.connect(self.valueChanged)

        self.update_filter()

        stage_layout = QHBoxLayout()
        stage_layout.setContentsMargins(0, 0, 0, 0)
        stage_layout.addWidget(QLabel("Active XY Stage:"), 0)
        stage_layout.addWidget(self.active_xy_stage, 1)
        stage_layout.addWidget(QLabel("Active Z Stage:"), 0)
        stage_layout.addWidget(self.active_z_stage, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        layout.addLayout(stage_layout)
        layout.addWidget(self.props)

    def value(self) -> Iterable[tuple[str, str, str]]:
        """Yield all the properties that are checked."""
        yield from super().value()
        yield (
            Keyword.CoreDevice.value,
            Keyword.CoreXYStage.value,
            self.active_xy_stage.currentText(),
        )
        yield (
            Keyword.CoreDevice.value,
            Keyword.CoreFocus.value,
            self.active_z_stage.currentText(),
        )

    def setValue(self, values: Sequence[tuple[str, str, str] | Setting]) -> None:
        """Set the properties and check the group box if any property is set."""
        super().setValue(values)
        for d, p, v in values:
            if d == Keyword.CoreDevice.value:
                if p == Keyword.CoreXYStage.value:
                    self.active_xy_stage.setCurrentText(v)
                    self.setChecked(True)
                    continue
                if p == Keyword.CoreFocus.value:
                    self.active_z_stage.setCurrentText(v)
                    self.setChecked(True)
                    continue

    def update_filter(self, query: str = "", checked: bool = False) -> None:
        """Show only the selected properties."""
        self.props.filterDevices(
            query=query,
            include_devices=[DeviceType.Stage, DeviceType.XYStage],
            include_read_only=False,
            include_pre_init=False,
            selected_only=checked,
        )


class _ObjectiveGroupBox(_PropertiesGroupBox):
    """GroupBox to select the properties related to the objectives."""

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__("Objective", parent, mmcore)

        self.update_filter()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        layout.addWidget(self.props)

    def _objective_predicate(self, prop: DeviceProperty) -> bool | None:
        devtype = prop.deviceType()
        if devtype == DeviceType.StateDevice:
            obj_devices = self._mmc.guessObjectiveDevices()
            if prop.device not in obj_devices:
                return False
        return None

    def update_filter(self, query: str = "", checked: bool = False) -> None:
        """Show only the selected properties."""
        self.props.filterDevices(
            query=query,
            include_devices=[DeviceType.StateDevice],
            include_read_only=False,
            include_pre_init=False,
            predicate=self._objective_predicate,
            selected_only=checked,
        )


def other_predicate(prop: DeviceProperty) -> bool | None:
    devtype = prop.deviceType()
    if devtype == DeviceType.CoreDevice and prop.name in (
        Keyword.CoreShutter.value,
        Keyword.CoreCamera.value,
        Keyword.CoreXYStage.value,
        Keyword.CoreFocus.value,
    ):
        return False
    return None


class _OtherGroupBox(_PropertiesGroupBox):
    """GroupBox to select the properties related to the general devices."""

    def __init__(
        self, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__("Other", parent, mmcore)

        self.update_filter()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        layout.addWidget(self.props)

    def update_filter(self, query: str = "", checked: bool = False) -> None:
        """Show only the selected properties."""
        self.props.filterDevices(
            query=query,
            exclude_devices=[
                DeviceType.Camera,
                DeviceType.Stage,
                DeviceType.XYStage,
                DeviceType.StateDevice,
                DeviceType.Shutter,
            ],
            include_read_only=False,
            include_pre_init=False,
            predicate=other_predicate,
            selected_only=checked,
        )
