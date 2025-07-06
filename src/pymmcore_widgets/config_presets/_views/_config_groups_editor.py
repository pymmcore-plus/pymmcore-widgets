from __future__ import annotations

from contextlib import contextmanager
from enum import Enum, auto
from typing import TYPE_CHECKING, cast

from qtpy.QtCore import QModelIndex, QSize, Qt, Signal
from qtpy.QtWidgets import (
    QGroupBox,
    QSizePolicy,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from superqt import QIconifyIcon

from pymmcore_widgets._icons import StandardIcon
from pymmcore_widgets._models import (
    ConfigGroup,
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
    from PyQt6.QtGui import QAction, QActionGroup

else:
    from qtpy.QtGui import QAction, QActionGroup


class LayoutMode(Enum):
    FAVOR_PRESETS = auto()  # preset-table full width at bottom
    FAVOR_PROPERTIES = auto()  # prop-selector full height at right


# -----------------------------------------------------------------------------
# High-level editor widget
# -----------------------------------------------------------------------------


class _ConfigEditorToolbar(QToolBar):
    def __init__(self, parent: ConfigGroupsEditor) -> None:
        super().__init__(parent)
        # tool bar --------------------------------------------------------------

        self.setIconSize(QSize(22, 22))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

        # Create exclusive action group for view modes
        view_action_group = QActionGroup(self)

        # Column View action
        column_icon = QIconifyIcon("fluent:layout-column-two-24-regular")
        if column_act := self.addAction(
            column_icon, "Column View", parent._group_preset_sel.showColumnView
        ):
            column_act.setCheckable(True)
            column_act.setChecked(True)
            view_action_group.addAction(column_act)

        # Tree View action
        if tree_act := self.addAction(
            StandardIcon.TREE.icon(), "Tree View", parent._group_preset_sel.showTreeView
        ):
            tree_act.setCheckable(True)
            view_action_group.addAction(tree_act)

        self.addAction(
            StandardIcon.FOLDER_ADD.icon(),
            "Add Group",
            parent._model.add_group,
        )
        self.addAction(
            StandardIcon.DOCUMENT_ADD.icon(),
            "Add Preset",
            parent._add_preset_to_current_group,
        )
        self.addAction(
            StandardIcon.DELETE.icon(),
            "Remove",
            parent._group_preset_sel.removeSelected,
        )
        self.addAction(
            StandardIcon.COPY.icon(),
            "Duplicate",
            parent._group_preset_sel.duplicateSelected,
        )
        self.addSeparator()
        self.set_channel_action = cast(
            "QAction",
            self.addAction(
                StandardIcon.CHANNEL_GROUP.icon(),
                "Set Channel Group",
            ),
        )

        @self.set_channel_action.triggered.connect  # type: ignore[misc]
        def _on_set_channel_group() -> None:
            parent._group_preset_sel.setCurrentGroupAsChannelGroup()
            self.set_channel_action.setEnabled(False)

        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        if act := self.addAction(
            StandardIcon.HELP.icon(),
            "Help",
            parent._show_help,
        ):
            act.setToolTip("Show help")

        icon = QIconifyIcon(
            "fluent:layout-row-two-split-top-focus-bottom-16-filled", color="#666"
        )
        icon.addKey(
            "fluent:layout-column-two-split-left-focus-right-16-filled",
            state=QIconifyIcon.State.On,
            color="#666",
        )
        if act := self.addAction(icon, "Layout", parent.setLayoutMode):
            act.setToolTip("Toggle layout mode")
            act.setCheckable(True)


class ConfigGroupsEditor(QWidget):
    """Widget composed of two QListViews backed by a single tree model.

    ```
    ┌────────────┬────────────┬───────────────┐
    │      groups/presets     |   prop_sel    │
    ├────────────┴────────────+ - - - - - - - ┤ (layout toggleable)
    │     2D Presets Table    |               │
    └─────────────────────────┴───────────────┘
    ```

    """

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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = QConfigGroupsModel()

        # widgets -------------------------------------------------------------

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

        self._group_preset_sel = GroupPresetSelector(self)
        self._group_preset_sel.setModel(self._model)

        self._prop_selector = DevicePropertySelector()

        self._preset_table = ConfigPresetsTable(self)
        self._preset_table.setModel(self._model)
        self._preset_table.setGroup("Channel")

        # define this after the other widgets so that it can connect to their slots
        self._tb = _ConfigEditorToolbar(self)

        # layout ------------------------------------------------------------

        self._current_mode: LayoutMode = LayoutMode.FAVOR_PRESETS
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._tb)
        self.setLayoutMode(mode=LayoutMode.FAVOR_PRESETS)

        # signals ------------------------------------------------------------

        self._group_preset_sel.currentGroupChanged.connect(self._on_group_changed)
        self._group_preset_sel.currentPresetChanged.connect(self._on_preset_changed)
        # self._group_preset_stack.presetSelectionChanged.connect(self._on_preset_sel)
        # self._model.dataChanged.connect(self._on_model_data_changed)
        # self._props.valueChanged.connect(self._on_prop_table_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def _on_group_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        """Called when the group selection in the GroupPresetSelector changes."""
        self._preset_table.setGroup(current)
        self._preset_table.view.stretchHeaders()

        if current.isValid():
            group = current.data(Qt.ItemDataRole.UserRole)
            if isinstance(group, ConfigGroup) and group.is_channel_group:
                self._tb.set_channel_action.setEnabled(False)
            else:
                self._tb.set_channel_action.setEnabled(True)

    def _on_preset_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        """Called when the preset selection in the GroupPresetSelector changes."""
        if not current.isValid():
            return
        view = self._preset_table.view
        row = current.row()
        view.selectRow(row) if view.isTransposed() else view.selectColumn(row)

    def setCurrentGroup(self, group: str) -> None:
        """Set the currently selected group in the editor."""
        self._group_preset_sel.setCurrentGroup(group)

    def setCurrentPreset(self, group: str, preset: str) -> None:
        """Set the currently selected preset in the editor."""
        self._group_preset_sel.setCurrentPreset(group, preset)

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
                    self._group_preset_sel.setCurrentGroup(node.name)
        else:
            self._group_preset_sel.clearSelection()
        self.configChanged.emit()

    def data(self) -> Sequence[ConfigGroup]:
        """Return the current configuration data as a list of ConfigGroup."""
        return self._model.get_groups()

    def _add_preset_to_current_group(self) -> None:
        """Add a new preset to the currently selected group."""
        current_group = self._group_preset_sel.currentGroup()
        if current_group.isValid():
            self._model.add_preset(current_group)

    # ------------------------------------------------------------------
    # Layout management
    # ------------------------------------------------------------------

    def _build_layout(self, mode: LayoutMode) -> QSplitter:
        """Return a new top-level splitter for the requested layout."""
        margin = 2
        groups_presets = QGroupBox("Navigate Groups && Presets", self)
        lay = QVBoxLayout(groups_presets)
        lay.setContentsMargins(margin, margin, margin, margin)
        lay.addWidget(self._group_preset_sel)

        prop_sel = QGroupBox("Select Properties", self)
        lay = QVBoxLayout(prop_sel)
        lay.setContentsMargins(margin, margin, margin, margin)
        lay.addWidget(self._prop_selector)

        table_group = QGroupBox("Presets Table", self)
        lay = QVBoxLayout(table_group)
        lay.setContentsMargins(margin, margin, margin, margin)
        lay.addWidget(self._preset_table)

        if mode is LayoutMode.FAVOR_PRESETS:
            # ┌───────────────────────────────┬────────────────┐
            # │       _group_preset_stack     │ _prop_selector │ <- top_splitter
            # ├───────────────────────────────┴────────────────┤
            # │               _preset_table                    │
            # └────────────────────────────────────────────────┘
            top_splitter = QSplitter(Qt.Orientation.Horizontal)
            top_splitter.addWidget(groups_presets)
            top_splitter.addWidget(prop_sel)
            # top_splitter.setStretchFactor(1, 1)

            main = QSplitter(Qt.Orientation.Vertical)
            main.addWidget(top_splitter)
            main.addWidget(table_group)
            return main

        if mode is LayoutMode.FAVOR_PROPERTIES:
            # ┌───────────────────────────────┬────────────────┐
            # │       _group_preset_stack     │                │
            # ├───────────────────────────────┤ _prop_selector │
            # │         _preset_table         │                │
            # └───────────────────────────────┴────────────────┘

            left_splitter = QSplitter(Qt.Orientation.Vertical)
            left_splitter.addWidget(groups_presets)
            left_splitter.addWidget(table_group)

            main = QSplitter(Qt.Orientation.Horizontal)
            main.addWidget(left_splitter)
            main.addWidget(prop_sel)
            # main.setStretchFactor(1, 1)
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

    def _show_help(self) -> None:
        """Show help for this widget."""
        from pymmcore_widgets._help._config_groups_help import ConfigGroupsHelpDialog

        dialog = ConfigGroupsHelpDialog(self)
        size = (
            (self.size() * 0.8).expandedTo(QSize(600, 600)).boundedTo(QSize(800, 800))
        )
        dialog.resize(size)
        dialog.setWindowFlags(Qt.WindowType.Sheet | Qt.WindowType.WindowCloseButtonHint)
        dialog.exec()

    # ------------------------------------------------------------------
    # Property-table sync
    # ------------------------------------------------------------------

    # def _on_prop_table_changed(self) -> None:
    #     """Write back edits from the table into the underlying ConfigPreset."""
    #     idx = self._group_preset_sel.currentPresetIndex()
    #     if not idx.isValid():
    #         return
    #     node = cast("_Node", idx.internalPointer())
    #     if not node.is_preset:
    #         return
    #     # new_settings = self._props.value()
    #     # self._model.update_preset_settings(idx, new_settings)
    #     self.configChanged.emit()

    # def _on_model_data_changed(
    #     self,
    #     topLeft: QModelIndex,
    #     bottomRight: QModelIndex,
    #     _roles: list[int] | None = None,
    # ) -> None:
    #     """Refresh DevicePropertyTable if the current preset was edited."""
    #     if not self._our_preset_changed_by_range(topLeft, bottomRight):
    #         return

    #     # self._props.blockSignals(True)  # avoid feedback loop
    #     # self._props.setValue(preset.settings)
    #     # self._props.blockSignals(False)

    # def _our_preset_changed_by_range(
    #     self, topLeft: QModelIndex, bottomRight: QModelIndex
    # ) -> ConfigPreset | None:
    #     """Return our current preset if it was changed in the given range."""
    #     cur_preset = self._group_preset_sel.currentPresetIndex()
    #     if (
    #         not cur_preset.isValid()
    #         or not topLeft.isValid()
    #         or topLeft.parent() != cur_preset.parent()
    #         or topLeft.internalPointer().payload.name
    #         != cur_preset.internalPointer().payload.name
    #     ):
    #         return None

    #     # pull updated settings from the model and push to the table
    #     node = cast("_Node", cur_preset.internalPointer())
    #     preset = cast("ConfigPreset", node.payload)
    #     return preset


@contextmanager
def _updates_disabled(widget: QWidget) -> Iterator[None]:
    """Context manager to temporarily disable updates for a widget."""
    was_enabled = widget.updatesEnabled()
    widget.setUpdatesEnabled(False)
    try:
        yield
    finally:
        widget.setUpdatesEnabled(was_enabled)
