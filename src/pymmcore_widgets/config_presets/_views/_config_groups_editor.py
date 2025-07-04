from __future__ import annotations

from contextlib import contextmanager
from enum import Enum, auto
from typing import TYPE_CHECKING, cast

from qtpy.QtCore import QModelIndex, Qt, Signal
from qtpy.QtWidgets import QSizePolicy, QSplitter, QToolBar, QVBoxLayout, QWidget
from superqt import QIconifyIcon

from pymmcore_widgets._models import (
    ConfigGroup,
    ConfigPreset,
    QConfigGroupsModel,
    get_config_groups,
    get_loaded_devices,
)

from ._config_presets_table import ConfigPresetsTable
from ._device_property_selector import DevicePropertySelector
from ._group_preset_selector import GroupPresetSelector

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from pymmcore_plus import CMMCorePlus
    from PyQt6.QtGui import QAction

    from pymmcore_widgets._models._base_tree_model import _Node
else:
    from qtpy.QtGui import QAction


class LayoutMode(Enum):
    FAVOR_PRESETS = auto()  # preset-table full width at bottom
    FAVOR_PROPERTIES = auto()  # prop-selector full height at right


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
        icon = QIconifyIcon("fluent:layout-column-two-16-regular")
        icon.addKey(
            "fluent:list-bar-tree-20-regular",
            state=QIconifyIcon.State.On,
            color="#666",
        )
        if act := self._tb.addAction(icon, "Toggle Tree View", self._toggle_tree_view):
            act.setCheckable(True)
            act.setChecked(False)

        self._tb.addAction("Add Group")
        self._tb.addAction("Add Preset")
        self._tb.addAction("Remove")
        self._tb.addAction("Duplicate")

        spacer = QWidget(self._tb)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._tb.addWidget(spacer)

        icon = QIconifyIcon(
            "fluent:layout-row-two-split-top-focus-bottom-16-filled", color="#666"
        )
        icon.addKey(
            "fluent:layout-column-two-split-left-focus-right-16-filled",
            state=QIconifyIcon.State.On,
            color="#666",
        )
        if act := self._tb.addAction(icon, "Wide Layout", self.setLayoutMode):
            act.setCheckable(True)

        # ------------------------------------------------------------------
        # The GroupPresetSelector can switch between 2-list and tree views:
        # ┌───────────────┬───────────────┬───────────────┐
        # │     groups    │    presets    │      ...      │
        # ├───────────────┴───────────────┴───────────────┤
        # │                     ...                       │
        # └───────────────────────────────────────────────┘
        # ┌───────────────────────────────┬───────────────┐
        # │              tree             │               │
        # ├───────────────────────────────┴───────────────┤
        # │                     ...                       │
        # └───────────────────────────────────────────────┘

        self._group_preset_stack = GroupPresetSelector(self)
        self._group_preset_stack.setModel(self._model)

        # ------------------------------------------------------------------

        self._prop_selector = DevicePropertySelector()

        self._preset_table = ConfigPresetsTable(self)
        self._preset_table.setModel(self._model)
        self._preset_table.setGroup("Channel")

        # layout ------------------------------------------------------------

        self._current_mode: LayoutMode = LayoutMode.FAVOR_PRESETS
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._tb)
        self.setLayoutMode(mode=LayoutMode.FAVOR_PRESETS)

        # signals ------------------------------------------------------------

        self._group_preset_stack.groupSelectionChanged.connect(self._on_group_sel)
        self._group_preset_stack.presetSelectionChanged.connect(self._on_preset_sel)
        self._model.dataChanged.connect(self._on_model_data_changed)
        # self._props.valueChanged.connect(self._on_prop_table_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def _toggle_tree_view(self) -> None:
        self._group_preset_stack.toggleView()

    def setCurrentGroup(self, group: str) -> None:
        """Set the currently selected group in the editor."""
        self._group_preset_stack.setCurrentGroup(group)

    def setCurrentPreset(self, group: str, preset: str) -> None:
        """Set the currently selected preset in the editor."""
        self._group_preset_stack.setCurrentPreset(group, preset)

    def setData(self, data: Iterable[ConfigGroup]) -> None:
        """Set the configuration data to be displayed in the editor."""
        data = list(data)  # ensure we can iterate multiple times
        self._model.set_groups(data)
        # self._props.setValue([])
        # Auto-select first group
        if self._model.rowCount():
            idx = self._model.index(0)
            if hasattr(idx, "internalPointer"):
                node = idx.internalPointer()
                if hasattr(node, "name"):
                    self._group_preset_stack.setCurrentGroup(node.name)
        else:
            self._group_preset_stack.clearSelection()
        self.configChanged.emit()

    def data(self) -> Sequence[ConfigGroup]:
        """Return the current configuration data as a list of ConfigGroup."""
        return self._model.get_groups()

    # selection sync ---------------------------------------------------------

    def _on_group_sel(self, current: QModelIndex, _prev: QModelIndex) -> None:
        # The GroupPresetSelector already handles updating the preset list root
        # self._props._presets_table.setGroup(current)
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
        idx = self._group_preset_stack.currentPresetIndex()
        if not idx.isValid():
            return
        node = cast("_Node", idx.internalPointer())
        if not node.is_preset:
            return
        # new_settings = self._props.value()
        # self._model.update_preset_settings(idx, new_settings)
        self.configChanged.emit()

    def _on_model_data_changed(
        self,
        topLeft: QModelIndex,
        bottomRight: QModelIndex,
        _roles: list[int] | None = None,
    ) -> None:
        """Refresh DevicePropertyTable if a setting in the current preset was edited."""
        if not self._our_preset_changed_by_range(topLeft, bottomRight):
            return

        # self._props.blockSignals(True)  # avoid feedback loop
        # self._props.setValue(preset.settings)
        # self._props.blockSignals(False)

    def _our_preset_changed_by_range(
        self, topLeft: QModelIndex, bottomRight: QModelIndex
    ) -> ConfigPreset | None:
        """Return our current preset if it was changed in the given range."""
        cur_preset = self._group_preset_stack.currentPresetIndex()
        if (
            not cur_preset.isValid()
            or not topLeft.isValid()
            or topLeft.parent() != cur_preset.parent()
            or topLeft.internalPointer().payload.name
            != cur_preset.internalPointer().payload.name
        ):
            return None

        # pull updated settings from the model and push to the table
        node = cast("_Node", cur_preset.internalPointer())
        preset = cast("ConfigPreset", node.payload)
        return preset

    def _build_layout(self, mode: LayoutMode) -> QSplitter:
        """Return a new top-level splitter for the requested layout."""
        if mode is LayoutMode.FAVOR_PRESETS:
            # ┌───────────────────────────────┬────────────────┐
            # │       _group_preset_stack     │ _prop_selector │ <- top_splitter
            # ├───────────────────────────────┴────────────────┤
            # │               _preset_table                    │
            # └────────────────────────────────────────────────┘
            top_splitter = QSplitter(Qt.Orientation.Horizontal)
            top_splitter.addWidget(self._group_preset_stack)
            top_splitter.addWidget(self._prop_selector)
            top_splitter.setStretchFactor(1, 1)

            main = QSplitter(Qt.Orientation.Vertical)
            main.addWidget(top_splitter)
            main.addWidget(self._preset_table)
            return main

        if mode is LayoutMode.FAVOR_PROPERTIES:
            # ┌───────────────────────────────┬────────────────┐
            # │       _group_preset_stack     │                │
            # ├───────────────────────────────┤ _prop_selector │
            # │         _preset_table         │                │
            # └───────────────────────────────┴────────────────┘

            left_splitter = QSplitter(Qt.Orientation.Vertical)
            left_splitter.addWidget(self._group_preset_stack)
            left_splitter.addWidget(self._preset_table)

            main = QSplitter(Qt.Orientation.Horizontal)
            main.addWidget(left_splitter)
            main.addWidget(self._prop_selector)
            main.setStretchFactor(1, 1)
            return main

        raise ValueError(f"Unknown layout mode: {mode}")

    def setLayoutMode(self, mode: LayoutMode | None = None) -> None:
        """Slot connected to the toolbar action."""
        if not (layout := self.layout()):
            return

        if mode is None:
            if not isinstance(sender := self.sender(), QAction):
                return
            checked = sender.isChecked()
            mode = LayoutMode.FAVOR_PROPERTIES if checked else LayoutMode.FAVOR_PRESETS
        else:
            mode = LayoutMode(mode)

        sizes = None
        with _updates_disabled(self):
            if isinstance(
                cur_splitter := getattr(self, "_main_splitter", None), QSplitter
            ):
                sizes = self._get_splitter_sizes(cur_splitter)
                layout.removeWidget(cur_splitter)
                cur_splitter.setParent(None)
                cur_splitter.deleteLater()

            # build and insert the replacement
            self._main_splitter = new_splitter = self._build_layout(mode)
            self._current_mode = mode
            layout.addWidget(new_splitter)

            if sizes is not None:
                self._set_splitter_sizes(*sizes, new_splitter)

    def _get_splitter_sizes(
        self, splitter: QSplitter
    ) -> tuple[list[int], list[int]] | None:
        if isinstance(inner_splitter := splitter.widget(0), QSplitter):
            # FAVOR_PRESETS
            if splitter.orientation() == Qt.Orientation.Vertical:
                return inner_splitter.sizes(), splitter.sizes()
            # FAVOR_PROPERTIES
            else:
                return splitter.sizes(), inner_splitter.sizes()
        return None

    def _set_splitter_sizes(
        self, top_splits: list[int], left_heights: list[int], main_splitter: QSplitter
    ) -> None:
        """Set the saved sizes of the splitters."""
        if isinstance(inner_splitter := main_splitter.widget(0), QSplitter):
            # FAVOR_PRESETS
            if main_splitter.orientation() == Qt.Orientation.Vertical:
                inner_splitter.setSizes(top_splits)
                main_splitter.setSizes(left_heights)
            # FAVOR_PROPERTIES
            else:
                main_splitter.setSizes(top_splits)
                inner_splitter.setSizes(left_heights)


@contextmanager
def _updates_disabled(widget: QWidget) -> Iterator[None]:
    """Context manager to temporarily disable updates for a widget."""
    was_enabled = widget.updatesEnabled()
    widget.setUpdatesEnabled(False)
    try:
        yield
    finally:
        widget.setUpdatesEnabled(was_enabled)
