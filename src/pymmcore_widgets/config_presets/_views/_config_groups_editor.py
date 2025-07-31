from __future__ import annotations

from contextlib import contextmanager
from enum import Enum, auto
from typing import TYPE_CHECKING, cast

from qtpy.QtCore import QModelIndex, QSize, Qt, Signal
from qtpy.QtGui import QKeySequence, QUndoStack
from qtpy.QtWidgets import (
    QGroupBox,
    QMessageBox,
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
from ._group_preset_selector import GroupsPresetFinder
from ._undo_commands import (
    AddGroupCommand,
    AddPresetCommand,
    DuplicateGroupCommand,
    DuplicatePresetCommand,
    RemoveGroupCommand,
    RemovePresetCommand,
    SetChannelGroupCommand,
    UpdatePresetPropertiesCommand,
)

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
        self._loaded_devices = tuple(get_loaded_devices(core))
        if update_configs:
            self.setData(get_config_groups(core))

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("QToolBar { border: none; };")

        self._loaded_devices = ()
        self._model = QConfigGroupsModel()
        self._undo_stack = QUndoStack(self)

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

        self._group_preset_sel = GroupsPresetFinder(self)
        self._group_preset_sel.setModel(self._model)

        self._preset_table = ConfigPresetsTable(self)
        self._preset_table.setModel(self._model)

        # Set up undo/redo integration
        self._group_preset_sel.setUndoStack(self._undo_stack)
        self._preset_table.setUndoStack(self._undo_stack)
        self._preset_table.view.setUndoStack(self._undo_stack)

        # define this after the other widgets so that it can connect to their slots
        self._tb = _ConfigEditorToolbar(self)

        # layout ------------------------------------------------------------

        margin = 2
        groups_presets = QGroupBox("Navigate Groups && Presets", self)
        lay = QVBoxLayout(groups_presets)
        lay.setContentsMargins(margin, margin, margin, margin)
        lay.addWidget(self._group_preset_sel)

        table_group = QGroupBox("Presets Table", self)
        lay = QVBoxLayout(table_group)
        lay.setContentsMargins(margin, margin, margin, margin)
        lay.addWidget(self._preset_table)

        main = QSplitter(Qt.Orientation.Vertical)
        main.addWidget(groups_presets)
        main.addWidget(table_group)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        layout.addWidget(self._tb)
        layout.addWidget(main)

        # signals ------------------------------------------------------------

        self._group_preset_sel.currentGroupChanged.connect(self._on_group_changed)
        self._group_preset_sel.currentPresetChanged.connect(self._on_preset_changed)

        self._model.dataChanged.connect(self._on_model_data_changed)
        # self._group_preset_stack.presetSelectionChanged.connect(self._on_preset_sel)
        # self._model.dataChanged.connect(self._on_model_data_changed)
        # self._props.valueChanged.connect(self._on_prop_table_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _on_group_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        """Called when the group selection in the GroupPresetSelector changes."""
        # Show this group in the preset table
        self._preset_table.setGroup(current)
        self._preset_table.view.stretchHeaders()
        self._tb.add_preset_action.setEnabled(current.isValid())
        self._tb.duplicate_action.setEnabled(current.isValid())
        self._tb.remove_action.setEnabled(current.isValid())

        # Enable/disable actions based on the selected group
        group = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(group, ConfigGroup):
            # Enable/disable "set channel group" action depending on whether
            # the selected group is already a channel group
            self._tb.set_channel_action.setEnabled(
                not group.is_channel_group and not group.is_system_group
            )

    def _on_preset_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        """Called when the preset selection in the GroupPresetSelector changes."""
        print("CHANGED PRESET", current, previous)
        self._tb.add_properties_action.setEnabled(current.isValid())
        if not current.isValid():
            return

        # highlight the selected preset in the table
        table = self._preset_table.view
        row = current.row()
        table.selectRow(row) if table.isTransposed() else table.selectColumn(row)

    def _on_prop_selection_changed(self, props: Sequence[tuple[str, str]]) -> None:
        """Called when the selection in the DevicePropertySelector changes.

        value is a tuple of (device_label, property_name) pairs.
        We need to update the device properties in the currently selected preset.
        to match
        """
        idx = self._group_preset_sel.currentPreset()
        if idx.isValid():
            command = UpdatePresetPropertiesCommand(self._model, idx, props)
            self._undo_stack.push(command)

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
        # Auto-select first group
        if self._model.rowCount():
            idx = self._model.index(0)
            if hasattr(idx, "internalPointer"):
                node = idx.internalPointer()
                if hasattr(node, "name"):
                    self._group_preset_sel.setCurrentGroup(node.name)
        else:
            self._group_preset_sel.clearSelection()
            # Ensure "add preset" action is disabled when no groups exist
            self._tb.add_preset_action.setEnabled(False)
        self.configChanged.emit()

    def data(self) -> Sequence[ConfigGroup]:
        """Return the current configuration data as a list of ConfigGroup."""
        return self._model.get_groups()

    def undoStack(self) -> QUndoStack:
        """Return the undo stack for this editor."""
        return self._undo_stack

    def _add_preset_to_current_group(self) -> None:
        """Add a new preset to the currently selected group."""
        current_group = self._group_preset_sel.currentGroup()
        if current_group.isValid():
            command = AddPresetCommand(self._model, current_group)
            self._undo_stack.push(command)

    def _add_properties_to_current_preset(self) -> None:
        """Add properties to the currently selected preset."""
        current_preset = self._group_preset_sel.currentPreset()
        if current_preset.isValid():
            if properties := DevicePropertySelector.promptForProperties(
                self, self._loaded_devices
            ):
                command = UpdatePresetPropertiesCommand(
                    self._model, current_preset, properties
                )
                self._undo_stack.push(command)

    def _add_group(self) -> None:
        """Add a new group."""
        command = AddGroupCommand(self._model)
        self._undo_stack.push(command)

    def _remove_selected(self) -> None:
        """Remove the currently selected group or preset."""
        idx = self._group_preset_sel._selected_index()
        if idx.isValid():
            # Show confirmation dialog
            item_name = idx.data(Qt.ItemDataRole.DisplayRole)
            item_type = type(idx.data(Qt.ItemDataRole.UserRole))
            type_name = item_type.__name__.replace("Config", "Config ")
            msg = QMessageBox.question(
                self,
                "Confirm Deletion",
                f"Are you sure you want to delete {type_name} {item_name!r}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if msg != QMessageBox.StandardButton.Yes:
                return

            # Determine if it's a group or preset and create appropriate command
            node = idx.internalPointer()
            if hasattr(node, "is_group") and node.is_group:
                command = RemoveGroupCommand(self._model, idx)
            elif hasattr(node, "is_preset") and node.is_preset:
                command = RemovePresetCommand(self._model, idx)
            else:
                return  # Unknown item type

            self._undo_stack.push(command)

    def _duplicate_selected(self) -> None:
        """Duplicate the currently selected group or preset."""
        idx = self._group_preset_sel._selected_index()
        if idx.isValid():
            # Determine if it's a group or preset and create appropriate command
            node = idx.internalPointer()
            if hasattr(node, "is_group") and node.is_group:
                command = DuplicateGroupCommand(self._model, idx)
                self._undo_stack.push(command)
            elif hasattr(node, "is_preset") and node.is_preset:
                command = DuplicatePresetCommand(self._model, idx)
                self._undo_stack.push(command)

    def _on_model_data_changed(
        self,
        topLeft: QModelIndex,
        bottomRight: QModelIndex,
        roles: list[int] | None = None,
    ) -> None:
        """Handle model data changes to potentially create undo commands."""
        # For now, we'll just emit the configChanged signal
        # In the future, we might want to create undo commands for direct model edits
        self.configChanged.emit()

    # ------------------------------------------------------------------
    # Layout management
    # ------------------------------------------------------------------

    def sizeHint(self) -> QSize:
        """Suggest a size for the widget."""
        return QSize(1200, 800)

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

    def _show_undo_view(self) -> None:
        """Show a dialog with the undo stack view."""
        from qtpy.QtWidgets import QUndoView

        # TODO
        if self._undo_stack is not None:
            dialog = QUndoView(self._undo_stack, self)
            dialog.setCleanIcon(StandardIcon.UNDO.icon())
            dialog.setEmptyLabel("<start of stack>")
            dialog.setWindowFlags(
                Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
            )
            dialog.show()


class _ConfigEditorToolbar(QToolBar):
    def __init__(self, parent: ConfigGroupsEditor) -> None:
        super().__init__(parent)
        # tool bar --------------------------------------------------------------

        self.setIconSize(QSize(20, 20))
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
            parent._add_group,
        )
        self.add_preset_action = self.addAction(
            StandardIcon.DOCUMENT_ADD.icon(),
            "Add Preset",
            parent._add_preset_to_current_group,
        )
        self.add_preset_action.setEnabled(False)
        self.add_properties_action = self.addAction(
            StandardIcon.PROPERTY_ADD.icon(),
            "Add Properties",
            parent._add_properties_to_current_preset,
        )
        self.add_properties_action.setEnabled(False)
        self.duplicate_action = self.addAction(
            StandardIcon.COPY.icon(),
            "Duplicate",
            parent._duplicate_selected,
        )
        self.duplicate_action.setEnabled(False)
        self.remove_action = self.addAction(
            StandardIcon.DELETE.icon(),
            "Remove",
            parent._remove_selected,
        )
        self.remove_action.setEnabled(False)
        self.addSeparator()

        # Undo/Redo actions
        self.undo_action = parent._undo_stack.createUndoAction(self, "Undo")
        if self.undo_action:
            self.undo_action.setIcon(StandardIcon.UNDO.icon())
            self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
            self.addAction(self.undo_action)

        self.redo_action = parent._undo_stack.createRedoAction(self, "Redo")
        if self.redo_action:
            self.redo_action.setIcon(StandardIcon.REDO.icon())
            self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
            self.addAction(self.redo_action)

        self.addAction("Show Undo/Redo History...", parent._show_undo_view)
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
            current_group = parent._group_preset_sel.currentGroup()
            if current_group.isValid():
                command = SetChannelGroupCommand(parent._model, current_group)
                parent._undo_stack.push(command)
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


@contextmanager
def _updates_disabled(widget: QWidget) -> Iterator[None]:
    """Context manager to temporarily disable updates for a widget."""
    was_enabled = widget.updatesEnabled()
    widget.setUpdatesEnabled(False)
    try:
        yield
    finally:
        widget.setUpdatesEnabled(was_enabled)
