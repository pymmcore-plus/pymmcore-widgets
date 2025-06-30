from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pymmcore_plus import DeviceProperty, DeviceType, Keyword
from pymmcore_plus.model import ConfigGroup
from qtpy.QtCore import QModelIndex, QSize, Qt, Signal
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from superqt import QIconifyIcon

from pymmcore_widgets._icons import ICONS
from pymmcore_widgets.config_presets._qmodel._presets_table import PresetsTable
from pymmcore_widgets.device_properties import DevicePropertyTable

from ._config_model import QConfigGroupsModel, _Node

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from pymmcore_plus import CMMCorePlus
    from pymmcore_plus.model import ConfigPreset, Setting
    from PyQt6.QtGui import QAction, QActionGroup
else:
    from qtpy.QtGui import QAction, QActionGroup


# -----------------------------------------------------------------------------
# High-level editor widget
# -----------------------------------------------------------------------------


class _NameList(QWidget):
    """A group box that contains a toolbar and a QListView for cfg groups or presets."""

    def __init__(self, title: str, parent: QWidget | None) -> None:
        super().__init__(parent)
        self._title = title

        # toolbar
        self.list_view = QListView(self)

        self._toolbar = tb = QToolBar()
        tb.setStyleSheet("QToolBar {background: none; border: none;}")
        tb.setIconSize(QSize(18, 18))
        self._toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

        self.add_action = QAction(
            QIconifyIcon("mdi:plus-thick", color="gray"),
            f"Add {title.rstrip('s')}",
            self,
        )
        tb.addAction(self.add_action)
        tb.addSeparator()
        tb.addAction(
            QIconifyIcon("mdi:remove-bold", color="gray"), "Remove", self._remove
        )
        tb.addAction(
            QIconifyIcon("mdi:content-duplicate", color="gray"), "Duplicate", self._dupe
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self.list_view)

        if isinstance(self, QGroupBox):
            self.setTitle(title)
        else:
            label = QLabel(self._title, self)
            font = label.font()
            font.setBold(True)
            label.setFont(font)
            layout.insertWidget(0, label)

    def _is_groups(self) -> bool:
        """Check if this box is for groups."""
        return bool(self._title == "Groups")

    def _remove(self) -> None:
        self._model.remove(self.list_view.currentIndex())

    @property
    def _model(self) -> QConfigGroupsModel:
        """Return the model used by this list view."""
        model = self.list_view.model()
        if not isinstance(model, QConfigGroupsModel):
            raise TypeError("Expected a QConfigGroupsModel instance.")
        return model

    def _dupe(self) -> None: ...


class GroupsList(_NameList):
    def __init__(self, parent: QWidget | None) -> None:
        super().__init__("Groups", parent)

    def _dupe(self) -> None:
        idx = self.list_view.currentIndex()
        if idx.isValid():
            self.list_view.setCurrentIndex(self._model.duplicate_group(idx))


class PresetsList(_NameList):
    def __init__(self, parent: QWidget | None) -> None:
        super().__init__("Presets", parent)

        # TODO: we need `_NameList.setCore()` in order to be able to "activate" a preset
        self._toolbar.addAction(
            QIconifyIcon("clarity:play-solid", color="gray"),
            "Activate",
        )

    def _dupe(self) -> None:
        idx = self.list_view.currentIndex()
        if idx.isValid():
            self.list_view.setCurrentIndex(self._model.duplicate_preset(idx))


class ConfigGroupsEditor(QWidget):
    """Widget composed of two QListViews backed by a single tree model."""

    configChanged = Signal()

    @classmethod
    def create_from_core(
        cls, core: CMMCorePlus, parent: QWidget | None = None
    ) -> ConfigGroupsEditor:
        """Create a ConfigGroupsEditor from a CMMCorePlus instance."""
        obj = cls(parent)
        obj.update_from_core(core)
        return obj

    def update_from_core(
        self,
        core: CMMCorePlus,
        *,
        update_configs: bool = True,
        update_available: bool = True,
    ) -> None:
        """Update the editor's data from the core.

        Parameters
        ----------
        core : CMMCorePlus
            The core instance to pull configuration data from.
        update_configs : bool
            If True, update the entire list and states of config groups (i.e. make the
            editor reflect the current state of config groups in the core).
        update_available : bool
            If True, update the available options in the property tables (for things
            like "current device" comboboxes and other things that select from
            available devices).
        """
        if update_configs:
            groups = ConfigGroup.all_config_groups(core)
            self.setData(groups.values())
        if update_available:
            self._props._update_device_buttons(core)
            # self._prop_tables.update_options_from_core(core)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = QConfigGroupsModel()

        # widgets --------------------------------------------------------------

        group_box = GroupsList(self)
        self._group_view = group_box.list_view
        self._group_view.setModel(self._model)
        group_box.add_action.triggered.connect(self._new_group)

        preset_box = PresetsList(self)
        self._preset_view = preset_box.list_view
        self._preset_view.setModel(self._model)
        preset_box.add_action.triggered.connect(self._new_preset)

        self._props = _PropSettings(self)
        self._props._presets_table.setModel(self._model)

        # layout ------------------------------------------------------------

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(12, 12, 4, 12)
        lv.addWidget(group_box)
        lv.addWidget(preset_box)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(left)
        lay.addWidget(self._props, 1)

        # signals ------------------------------------------------------------

        if sm := self._group_view.selectionModel():
            sm.currentChanged.connect(self._on_group_sel)
        if sm := self._preset_view.selectionModel():
            sm.currentChanged.connect(self._on_preset_sel)
        self._model.dataChanged.connect(self._on_model_data_changed)
        self._props.valueChanged.connect(self._on_prop_table_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setCurrentGroup(self, group: str) -> None:
        """Set the currently selected group in the editor."""
        idx = self._model.index_for_group(group)
        if idx.isValid():
            self._group_view.setCurrentIndex(idx)
        else:
            self._group_view.clearSelection()

    def setCurrentPreset(self, group: str, preset: str) -> None:
        """Set the currently selected preset in the editor."""
        self.setCurrentGroup(group)
        group_index = self._model.index_for_group(group)
        idx = self._model.index_for_preset(group_index, preset)
        if idx.isValid():
            self._preset_view.setCurrentIndex(idx)
        else:
            self._preset_view.clearSelection()

    def setData(self, data: Iterable[ConfigGroup]) -> None:
        """Set the configuration data to be displayed in the editor."""
        data = list(data)  # ensure we can iterate multiple times
        self._model.set_groups(data)
        self._props.setValue([])
        # Auto-select first group
        if self._model.rowCount():
            self._group_view.setCurrentIndex(self._model.index(0))
        else:
            self._preset_view.setRootIndex(QModelIndex())
            self._preset_view.clearSelection()
        self.configChanged.emit()

    def data(self) -> Sequence[ConfigGroup]:
        """Return the current configuration data as a list of ConfigGroup."""
        return self._model.data_as_groups()

    # TODO:
    # def selectionModel(self) -> QItemSelectionModel: ...

    # "new" actions ----------------------------------------------------------

    def _new_group(self) -> None:
        idx = self._model.add_group()
        self._group_view.setCurrentIndex(idx)

    def _new_preset(self) -> None:
        gidx = self._group_view.currentIndex()
        if not gidx.isValid():
            return
        pidx = self._model.add_preset(gidx)
        self._preset_view.setCurrentIndex(pidx)

    # selection sync ---------------------------------------------------------

    def _on_group_sel(self, current: QModelIndex, _prev: QModelIndex) -> None:
        self._preset_view.setRootIndex(current)
        self._props._presets_table.setGroup(current)
        if current.isValid() and self._model.rowCount(current):
            self._preset_view.setCurrentIndex(self._model.index(0, 0, current))
        else:
            self._preset_view.clearSelection()

    def _on_preset_sel(self, current: QModelIndex, _prev: QModelIndex) -> None:
        """Populate the DevicePropertyTable whenever the selected preset changes."""
        if not current.isValid():
            # clear table when nothing is selected
            self._props.setValue([])
            return
        node = cast("_Node", current.internalPointer())
        if not node.is_preset:
            self._props.setValue([])
            return
        preset = cast("ConfigPreset", node.payload)
        self._props.setValue(preset.settings)

    # ------------------------------------------------------------------
    # Property-table sync
    # ------------------------------------------------------------------

    def _on_prop_table_changed(self) -> None:
        """Write back edits from the table into the underlying ConfigPreset."""
        idx = self._preset_view.currentIndex()
        if not idx.isValid():
            return
        node = cast("_Node", idx.internalPointer())
        if not node.is_preset:
            return
        new_settings = self._props.value()
        self._model.update_preset_settings(idx, new_settings)
        self.configChanged.emit()

    def _on_model_data_changed(
        self,
        topLeft: QModelIndex,
        bottomRight: QModelIndex,
        _roles: list[int] | None = None,
    ) -> None:
        """Refresh DevicePropertyTable if a setting in the current preset was edited."""
        if not (preset := self._our_preset_changed_by_range(topLeft, bottomRight)):
            return

        self._props.blockSignals(True)  # avoid feedback loop
        self._props.setValue(preset.settings)
        self._props.blockSignals(False)

    def _our_preset_changed_by_range(
        self, topLeft: QModelIndex, bottomRight: QModelIndex
    ) -> ConfigPreset | None:
        """Return our current preset if it was changed in the given range."""
        cur_preset = self._preset_view.currentIndex()
        if (
            not cur_preset.isValid()
            or not topLeft.isValid()
            or topLeft.parent() != cur_preset.parent()
            or topLeft.internalPointer().payload.name
            != cur_preset.internalPointer().payload.name
        ):
            return None

        # pull updated settings from the model and push to the table
        node = cast("_Node", self._preset_view.currentIndex().internalPointer())
        preset = cast("ConfigPreset", node.payload)
        return preset


class _PropSettings(QSplitter):
    """A wrapper for DevicePropertyTable for use in ConfigGroupsEditor."""

    valueChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Vertical, parent)
        # 2D table with presets as columns and device properties as rows
        self._presets_table = PresetsTable(self)

        # regular property table for editing all device properties
        self._prop_tables = DevicePropertyTable()
        self._prop_tables.valueChanged.connect(self.valueChanged)
        self._prop_tables.setRowsCheckable(True)

        # toolbar with device type buttons
        self._action_group = QActionGroup(self)
        self._action_group.setExclusive(False)
        tb, self._action_group = self._create_device_buttons()

        bot = QWidget()
        bl = QVBoxLayout(bot)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(tb)
        bl.addWidget(self._prop_tables)

        self.addWidget(self._presets_table)
        self.addWidget(bot)

        self._filter_properties()

    def value(self) -> list[Setting]:
        """Return the current value of the property table."""
        return self._prop_tables.value()

    def setValue(self, value: list[Setting]) -> None:
        """Set the value of the property table."""
        self._prop_tables.setValue(value)

    def _create_device_buttons(self) -> tuple[QToolBar, QActionGroup]:
        tb = QToolBar()
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setStyleSheet("QToolBar {background: none; border: none;}")
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        tb.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # clear action group
        action_group = QActionGroup(self)
        action_group.setExclusive(False)

        for dev_type, checked in {
            DeviceType.CameraDevice: False,
            DeviceType.ShutterDevice: True,
            DeviceType.StateDevice: True,
            DeviceType.StageDevice: False,
            DeviceType.XYStageDevice: False,
            DeviceType.SerialDevice: False,
            DeviceType.GenericDevice: False,
            DeviceType.AutoFocusDevice: False,
            DeviceType.ImageProcessorDevice: False,
            DeviceType.SignalIODevice: False,
            DeviceType.MagnifierDevice: False,
            DeviceType.SLMDevice: False,
            DeviceType.HubDevice: False,
            DeviceType.GalvoDevice: False,
            DeviceType.CoreDevice: False,
        }.items():
            icon = QIconifyIcon(ICONS[dev_type], color="gray")
            if act := tb.addAction(
                icon,
                dev_type.name.replace("Device", ""),
                self._filter_properties,
            ):
                act.setCheckable(True)
                act.setChecked(checked)
                act.setData(dev_type)
                action_group.addAction(act)

        return tb, action_group

    def _filter_properties(self) -> None:
        include_devices = {
            action.data()
            for action in self._action_group.actions()
            if action.isChecked()
        }
        if not include_devices:
            # If no devices are selected, show all properties
            for row in range(self._prop_tables.rowCount()):
                self._prop_tables.hideRow(row)

        else:
            self._prop_tables.filterDevices(
                include_pre_init=False,
                include_read_only=False,
                always_show_checked=True,
                include_devices=include_devices,
                predicate=_hide_state_state,
            )

    def _update_device_buttons(self, core: CMMCorePlus) -> None:
        for action in self._action_group.actions():
            dev_type = cast("DeviceType", action.data())
            for dev in core.getLoadedDevicesOfType(dev_type):
                writeable_props = (
                    (
                        not core.isPropertyPreInit(dev, prop)
                        and not core.isPropertyReadOnly(dev, prop)
                    )
                    for prop in core.getDevicePropertyNames(dev)
                )
                if any(writeable_props):
                    action.setVisible(True)
                    break
            else:
                action.setVisible(False)


def _hide_state_state(prop: DeviceProperty) -> bool | None:
    """Hide the State property for StateDevice (it duplicates state label)."""
    if prop.deviceType() == DeviceType.StateDevice and prop.name == Keyword.State:
        return False
    return None
