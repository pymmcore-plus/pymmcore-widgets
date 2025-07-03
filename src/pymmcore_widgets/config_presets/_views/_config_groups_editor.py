from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pymmcore_plus import DeviceType
from qtpy.QtCore import QModelIndex, QSortFilterProxyModel, Qt, Signal
from qtpy.QtWidgets import (
    QListView,
    QSplitter,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets._models import (
    ConfigGroup,
    ConfigPreset,
    Device,
    DevicePropertySetting,
    QConfigGroupsModel,
    QDevicePropertyModel,
    get_config_groups,
    get_loaded_devices,
)
from pymmcore_widgets.config_presets._views._config_presets_table import (
    ConfigPresetsTable,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from pymmcore_plus import CMMCorePlus

    from pymmcore_widgets._models._base_tree_model import _Node
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
        self._prop_selector.setAvailableDevices(get_loaded_devices(core))
        self._preset_table.setModel(self._model)
        self._preset_table.setGroup("Channel")

        # if update_available:
        # self._props._update_device_buttons(core)
        # self._prop_tables.update_options_from_core(core)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = QConfigGroupsModel()

        # widgets --------------------------------------------------------------
        self._tb = QToolBar(self)
        self._tb.addAction("Add Group")
        self._tb.addAction("Add Preset")
        self._tb.addAction("Remove")
        self._tb.addAction("Duplicate")

        self.group_list = QListView(self)
        self.group_list.setModel(self._model)
        self.group_list.setSelectionMode(QListView.SelectionMode.SingleSelection)

        self.preset_list = QListView(self)
        self.preset_list.setModel(self._model)
        self.preset_list.setSelectionMode(QListView.SelectionMode.SingleSelection)

        self._prop_selector = DevicePropertySelector()

        self._preset_table = ConfigPresetsTable(self)
        self._preset_table.setModel(self._model)
        self._preset_table.setGroup("Channel")
        # layout ------------------------------------------------------------

        top = QSplitter(Qt.Orientation.Horizontal, self)
        top.addWidget(self.group_list)
        top.addWidget(self.preset_list)
        top.addWidget(self._prop_selector)

        top_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        top_splitter.setHandleWidth(1)
        top_splitter.setChildrenCollapsible(False)
        top_splitter.addWidget(top)
        # top_splitter.addWidget(preset_box)

        main_splitter = QSplitter(Qt.Orientation.Vertical, self)
        main_splitter.setHandleWidth(1)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(self._preset_table)

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


# TODO: Allow GUI control of parameters
class DeviceTypeFilter(QSortFilterProxyModel):
    def __init__(self, allowed: set[DeviceType], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.allowed = allowed  # e.g. {"Camera", "Shutter"}

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if sm := self.sourceModel():
            idx = sm.index(source_row, 0, source_parent)
            if DeviceType.Any in self.allowed:
                return True
            data = idx.data(Qt.ItemDataRole.UserRole)
            if isinstance(obj := data, Device):
                return obj.type in self.allowed
            elif isinstance(obj, DevicePropertySetting):
                if obj.is_pre_init or obj.is_read_only:
                    return False
        return True


class DevicePropertySelector(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        tree = QTreeView(self)

        self._model = QDevicePropertyModel()
        # flat_proxy = FlatPropertyModel()
        # proxy = DeviceTypeFilter(allowed={DeviceType.Camera}, parent=self)
        # proxy.setSourceModel(self._model)
        # flat_proxy.setSourceModel(self._model)

        tree.setModel(self._model)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(tree)

    def clear(self) -> None:
        """Clear the current selection."""
        # self.table.setValue([])

    def setChecked(self, settings: Iterable[tuple[str, str, str]]) -> None:
        """Set the checked state of the properties based on the given settings."""
        # self.table.setValue(settings)

    def setAvailableDevices(self, devices: Iterable[Device]) -> None:
        self._model.set_devices(devices)
