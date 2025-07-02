from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pymmcore_plus import DeviceProperty, DeviceType, Keyword
from qtpy.QtCore import QModelIndex, Qt, Signal
from qtpy.QtWidgets import (
    QHBoxLayout,
    QListView,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets.config_presets._model._py_config_model import (
    ConfigGroup,
    ConfigPreset,
    get_config_groups,
)
from pymmcore_widgets.config_presets._model._q_config_model import (
    QConfigGroupsModel,
)
from pymmcore_widgets.device_properties import DevicePropertyTable

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from pymmcore_plus import CMMCorePlus

    from pymmcore_widgets.config_presets._model._base_tree_model import _Node
else:
    pass


# -----------------------------------------------------------------------------
# High-level editor widget
# -----------------------------------------------------------------------------


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
            self.setData(get_config_groups(core))
        # if update_available:
        # self._props._update_device_buttons(core)
        # self._prop_tables.update_options_from_core(core)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = QConfigGroupsModel()

        # widgets --------------------------------------------------------------
        self._tb = QToolBar(self)

        self.group_list = QListView(self)
        self.group_list.setModel(self._model)
        self.group_list.setSelectionMode(QListView.SelectionMode.SingleSelection)

        self.preset_list = QListView(self)
        self.preset_list.setModel(self._model)
        self.preset_list.setSelectionMode(QListView.SelectionMode.SingleSelection)

        self._prop_selector = DevicePropertySelector()

        # layout ------------------------------------------------------------

        top = QWidget(self)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)
        top_layout.addWidget(self.group_list)
        top_layout.addWidget(self.preset_list)
        top_layout.addWidget(self._prop_selector)

        main_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        main_splitter.setHandleWidth(1)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.addWidget(top)
        # main_splitter.addWidget(preset_box)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._tb)
        layout.addWidget(main_splitter)

        # signals ------------------------------------------------------------

        if sm := self.group_list.selectionModel():
            sm.currentChanged.connect(self._on_group_sel)
        if sm := self.preset_list.selectionModel():
            sm.currentChanged.connect(self._on_preset_sel)
        self._model.dataChanged.connect(self._on_model_data_changed)
        # self._props.valueChanged.connect(self._on_prop_table_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setCurrentGroup(self, group: str) -> None:
        """Set the currently selected group in the editor."""
        idx = self._model.index_for_group(group)
        if idx.isValid():
            self.group_list.setCurrentIndex(idx)
        else:
            self.group_list.clearSelection()

    def setCurrentPreset(self, group: str, preset: str) -> None:
        """Set the currently selected preset in the editor."""
        self.setCurrentGroup(group)
        group_index = self._model.index_for_group(group)
        idx = self._model.index_for_preset(group_index, preset)
        if idx.isValid():
            self.preset_list.setCurrentIndex(idx)
            self.preset_list.setFocus()
        else:
            self.preset_list.clearSelection()

    def setData(self, data: Iterable[ConfigGroup]) -> None:
        """Set the configuration data to be displayed in the editor."""
        data = list(data)  # ensure we can iterate multiple times
        self._model.set_groups(data)
        # self._props.setValue([])
        # Auto-select first group
        if self._model.rowCount():
            self.group_list.setCurrentIndex(self._model.index(0))
        else:
            self.preset_list.setRootIndex(QModelIndex())
            self.preset_list.clearSelection()
        self.configChanged.emit()

    def data(self) -> Sequence[ConfigGroup]:
        """Return the current configuration data as a list of ConfigGroup."""
        return self._model.get_groups()

    # selection sync ---------------------------------------------------------

    def _on_group_sel(self, current: QModelIndex, _prev: QModelIndex) -> None:
        self.preset_list.setRootIndex(current)
        # self._props._presets_table.setGroup(current)
        self.preset_list.clearSelection()
        self._prop_selector.clear()

    def _on_preset_sel(self, current: QModelIndex, _prev: QModelIndex) -> None:
        """Populate the DevicePropertyTable whenever the selected preset changes."""
        if not current.isValid():
            # clear table when nothing is selected
            # self._props.setValue([])
            return
        node = cast("_Node", current.internalPointer())
        if not node.is_preset:
            # self._props.setValue([])
            return
        cast("ConfigPreset", node.payload)
        # self._prop_selector.setChecked(preset.settings)

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


# class _PropSettings(QSplitter):
#     """A wrapper for DevicePropertyTable for use in ConfigGroupsEditor."""

#     valueChanged = Signal()

#     def __init__(self, parent: QWidget | None = None) -> None:
#         super().__init__(Qt.Orientation.Vertical, parent)
#         # 2D table with presets as columns and device properties as rows
#         self._presets_table = ConfigPresetsTable(self)

#         # regular property table for editing all device properties
#         self._prop_tables = DevicePropertyTable()
#         self._prop_tables.valueChanged.connect(self.valueChanged)
#         self._prop_tables.setRowsCheckable(True)

#         # toolbar with device type buttons
#         self._action_group = QActionGroup(self)
#         self._action_group.setExclusive(False)
#         tb, self._action_group = self._create_device_buttons()

#         bot = QWidget()
#         bl = QVBoxLayout(bot)
#         bl.setContentsMargins(0, 0, 0, 0)
#         bl.addWidget(tb)
#         bl.addWidget(self._prop_tables)

#         self.addWidget(self._presets_table)
#         self.addWidget(bot)

#         self._filter_properties()

#     def value(self) -> list[Setting]:
#         """Return the current value of the property table."""
#         return self._prop_tables.value()

#     def setValue(self, value: list[Setting]) -> None:
#         """Set the value of the property table."""
#         self._prop_tables.setValue(value)

#     def _create_device_buttons(self) -> tuple[QToolBar, QActionGroup]:
#         tb = QToolBar()
#         tb.setMovable(False)
#         tb.setFloatable(False)
#         tb.setIconSize(QSize(18, 18))
#         tb.setStyleSheet("QToolBar {background: none; border: none;}")
#         tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
#         tb.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

#         # clear action group
#         action_group = QActionGroup(self)
#         action_group.setExclusive(False)

#         for dev_type, checked in {
#             DeviceType.CameraDevice: False,
#             DeviceType.ShutterDevice: True,
#             DeviceType.StateDevice: True,
#             DeviceType.StageDevice: False,
#             DeviceType.XYStageDevice: False,
#             DeviceType.SerialDevice: False,
#             DeviceType.GenericDevice: False,
#             DeviceType.AutoFocusDevice: False,
#             DeviceType.ImageProcessorDevice: False,
#             DeviceType.SignalIODevice: False,
#             DeviceType.MagnifierDevice: False,
#             DeviceType.SLMDevice: False,
#             DeviceType.HubDevice: False,
#             DeviceType.GalvoDevice: False,
#             DeviceType.CoreDevice: False,
#         }.items():
#             icon = QIconifyIcon(ICONS[dev_type], color="gray")
#             if act := tb.addAction(
#                 icon,
#                 dev_type.name.replace("Device", ""),
#                 self._filter_properties,
#             ):
#                 act.setCheckable(True)
#                 act.setChecked(checked)
#                 act.setData(dev_type)
#                 action_group.addAction(act)

#         return tb, action_group

#     def _filter_properties(self) -> None:
#         include_devices = {
#             action.data()
#             for action in self._action_group.actions()
#             if action.isChecked()
#         }
#         if not include_devices:
#             # If no devices are selected, show all properties
#             for row in range(self._prop_tables.rowCount()):
#                 self._prop_tables.hideRow(row)

#         else:
#             self._prop_tables.filterDevices(
#                 include_pre_init=False,
#                 include_read_only=False,
#                 always_show_checked=True,
#                 include_devices=include_devices,
#                 predicate=_hide_state_state,
#             )

#     def _update_device_buttons(self, core: CMMCorePlus) -> None:
#         for action in self._action_group.actions():
#             dev_type = cast("DeviceType", action.data())
#             for dev in core.getLoadedDevicesOfType(dev_type):
#                 writeable_props = (
#                     (
#                         not core.isPropertyPreInit(dev, prop)
#                         and not core.isPropertyReadOnly(dev, prop)
#                     )
#                     for prop in core.getDevicePropertyNames(dev)
#                 )
#                 if any(writeable_props):
#                     action.setVisible(True)
#                     break
#             else:
#                 action.setVisible(False)


def _hide_state_state(prop: DeviceProperty) -> bool | None:
    """Hide the State property for StateDevice (it duplicates state label)."""
    if prop.deviceType() == DeviceType.StateDevice and prop.name == Keyword.State:
        return False
    return None


class DevicePropertySelector(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.table = DevicePropertyTable(self, connect_core=False)
        self.table.filterDevices(
            include_pre_init=False,
            include_read_only=False,
            always_show_checked=True,
            # predicate=_hide_state_state,
        )
        self.table.setRowsCheckable(True)
        # hide the 2nd column (prop value)
        self.table.setColumnHidden(1, True)
        # hide header
        if hh := self.table.horizontalHeader():
            hh.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)

    def clear(self) -> None:
        """Clear the current selection."""
        self.table.setValue([])

    def setChecked(self, settings: Iterable[tuple[str, str, str]]) -> None:
        """Set the checked state of the properties based on the given settings."""
        self.table.setValue(settings)
