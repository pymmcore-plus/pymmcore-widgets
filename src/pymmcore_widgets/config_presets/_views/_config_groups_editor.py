from __future__ import annotations

from typing import TYPE_CHECKING, cast

from qtpy.QtCore import (
    QItemSelection,
    QItemSelectionModel,
    QModelIndex,
    QSize,
    Qt,
    Signal,
)
from qtpy.QtGui import QKeySequence, QUndoStack
from qtpy.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSplitter,
    QToolBar,
    QUndoView,
    QVBoxLayout,
    QWidget,
)
from superqt import QIconifyIcon

from pymmcore_widgets._help._config_groups_help import ConfigGroupsHelpDialog
from pymmcore_widgets._icons import StandardIcon
from pymmcore_widgets._models import (
    ConfigGroup,
    ConfigPreset,
    DevicePropertySetting,
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
    _ModelCommand,
    undo_macro,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from pymmcore_plus import CMMCorePlus
    from PyQt6.QtGui import QAction, QActionGroup

else:
    from qtpy.QtGui import QAction, QActionGroup


# -----------------------------------------------------------------------------
# High-level editor widget
# -----------------------------------------------------------------------------


class ConfigGroupsEditor(QWidget):
    """Widget composed of two QListViews backed by a single tree model."""

    configChanged = Signal()
    applyRequested = Signal(
        list, list, object
    )  # list[ConfigGroup], list[str], str|None

    @classmethod
    def create_from_core(
        cls,
        core: CMMCorePlus,
        parent: QWidget | None = None,
        *,
        load_configs: bool = True,
    ) -> ConfigGroupsEditor:
        """Create a ConfigGroupsEditor from a CMMCorePlus instance.

        Available devices are loaded from the core, and if `load_configs` is True,
        config groups/presets are also loaded.
        """
        obj = cls(parent)
        obj.update_from_core(core, update_configs=load_configs)
        return obj

    def update_from_core(
        self,
        core: CMMCorePlus,
        *,
        update_devices: bool = True,
        update_configs: bool = False,
    ) -> None:
        """Refresh the editor from the current state of the core.

        Parameters
        ----------
        core : CMMCorePlus
            The core instance to pull data from.
        update_devices : bool
            If True, refresh the list of loaded devices and their properties.
            This determines which devices and properties appear in the "Edit Properties"
            and "Add Property" dialogs.
        update_configs : bool
            If True, replace the current editor contents with config groups, presets,
            and their settings from the core. If False, the current groups/presets will
            be left unchanged (meaning you will have an empty editor until you add
            groups/presets manually).
        """
        if update_devices:
            self._loaded_devices = tuple(get_loaded_devices(core))
            self._preset_table.setAvailableDevices(self._loaded_devices)
        if update_configs:
            self.setData(get_config_groups(core))

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("QToolBar { border: none; };")

        self._loaded_devices = ()
        self._model = QConfigGroupsModel()
        self._undo_stack = QUndoStack(self)
        self._clean_groups: dict[str, ConfigGroup] = {}
        self._syncing_selection = False
        self._prev_undo_index = 0
        self._dirty_icon = QIconifyIcon("mdi:alert-circle-outline", color="orange")
        self._clean_icon = QIconifyIcon("mdi:check-circle-outline", color="green")

        # widgets -------------------------------------------------------------

        # The GroupPresetSelector can switch between 2-list and tree views:
        # ┌───────────────┬───────────────┐
        # │     groups    │    presets    │
        # ├───────────────┴───────────────┤
        # │              ...              │
        # └───────────────────────────────┘
        # ┌───────────────────────────────┐
        # │              tree             │
        # ├───────────────────────────────┤
        # │              ...              │
        # └───────────────────────────────┘

        self._group_preset_sel = GroupsPresetFinder(self)
        self._group_preset_sel.setModel(self._model)

        self._preset_table = ConfigPresetsTable(self)
        self._preset_table.setModel(self._model)
        # Hide remove/duplicate in the table toolbar — the main toolbar has these
        self._preset_table.remove_action.setVisible(False)
        self._preset_table.duplicate_action.setVisible(False)

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

        # Bottom bar: status indicator (left) + Apply button (right)
        self._status_icon = QLabel(self)
        self._status_label = QLabel(self)
        self._apply_btn = QPushButton("Apply", self)
        self._apply_btn.setEnabled(False)

        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(5, 5, 5, 5)
        bottom_bar.setSpacing(5)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self._status_icon)
        bottom_bar.addWidget(self._status_label)
        bottom_bar.addWidget(self._apply_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        layout.addWidget(self._tb)
        layout.addWidget(main)
        layout.addLayout(bottom_bar)

        # signals ------------------------------------------------------------

        self._group_preset_sel.currentGroupChanged.connect(self._on_group_changed)
        self._group_preset_sel.presetSelectionChanged.connect(
            self._on_preset_selection_changed
        )
        if tree_sel := self._group_preset_sel.config_groups_tree.selectionModel():
            tree_sel.currentChanged.connect(self._on_tree_current_changed)

        self._model.dataChanged.connect(self._on_model_data_changed)
        self._model.rowsInserted.connect(self._on_model_structure_changed)
        self._model.rowsRemoved.connect(self._on_model_structure_changed)
        self._undo_stack.indexChanged.connect(self._on_undo_index_changed)

        # Sync table selection back to preset list
        self._connect_table_selection()
        # Transpose replaces the model (and selection model), so reconnect
        if act := self._preset_table.transpose_action:
            act.triggered.connect(self._connect_table_selection)

        self._undo_stack.cleanChanged.connect(self._update_status_indicator)
        self._apply_btn.clicked.connect(self._emit_apply_requested)
        self._update_status_indicator()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setCurrentGroup(self, group: str) -> QModelIndex:
        """Set the currently selected group in the editor.

        Returns the index of the group that was selected, or an invalid index if no such
        group exists.
        """
        return self._group_preset_sel.setCurrentGroup(group)

    def setCurrentPreset(self, group: str, preset: str) -> QModelIndex:
        """Set the currently selected preset in the editor.

        Returns the index of the preset that was selected, or an invalid index if no
        such preset exists.
        """
        return self._group_preset_sel.setCurrentPreset(group, preset)

    def setData(self, data: Iterable[ConfigGroup]) -> None:
        """Set the configuration data to be displayed in the editor."""
        data = list(data)  # ensure we can iterate multiple times
        self._model.set_groups(data)
        # Auto-select first group
        if self._model.rowCount():
            idx = self._model.index(0)
            if name := idx.data(Qt.ItemDataRole.DisplayRole):
                self._group_preset_sel.setCurrentGroup(name)
        else:
            self._group_preset_sel.clearSelection()
            # Ensure "add preset" action is disabled when no groups exist
            self._tb.add_preset_action.setEnabled(False)
        self._undo_stack.clear()  # marks stack as clean, clears history
        self._clean_groups = {g.name: g for g in self._model.get_groups()}
        self.configChanged.emit()

    def data(self) -> Sequence[ConfigGroup]:
        """Return the current configuration data as a list of ConfigGroup."""
        return self._model.get_groups()

    def isClean(self) -> bool:
        """Return True if the editor has no unapplied changes."""
        return self._undo_stack.isClean()  # type: ignore[no-any-return]

    def setClean(self) -> None:
        """Mark the current state as the clean (saved) baseline."""
        self._undo_stack.setClean()
        self._clean_groups = {g.name: g for g in self._model.get_groups()}

    def undoStack(self) -> QUndoStack:
        """Return the undo stack for this editor."""
        return self._undo_stack

    # ------------------------------------------------------------------
    # Private methods and slots
    # ------------------------------------------------------------------

    def _on_tree_current_changed(
        self, current: QModelIndex, previous: QModelIndex
    ) -> None:
        """Update toolbar actions based on what's selected in the tree view."""
        payload = current.data(Qt.ItemDataRole.UserRole) if current.isValid() else None
        is_group_or_preset = isinstance(payload, (ConfigGroup, ConfigPreset))
        self._tb.duplicate_action.setEnabled(is_group_or_preset)
        self._tb.remove_action.setEnabled(is_group_or_preset)

    def _on_group_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        """Called when the group selection in the GroupPresetSelector changes."""
        self._preset_table.setGroup(current)

        valid = current.isValid()
        self._tb.add_preset_action.setEnabled(valid)
        self._tb.duplicate_action.setEnabled(valid)
        self._tb.remove_action.setEnabled(valid)
        self._update_edit_properties_enabled(current)

        group = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(group, ConfigGroup):
            self._tb.set_channel_action.setEnabled(
                not group.is_channel_group and not group.is_system_group
            )

    def _on_preset_selection_changed(self, indices: list[QModelIndex]) -> None:
        """Sync the preset list selection to the table highlight."""
        if self._syncing_selection:
            return

        self._syncing_selection = True
        try:
            table = self._preset_table.view
            sm = table.selectionModel()
            model = table.model()
            if sm is None or model is None:
                return

            transposed = table.isTransposed()
            span = model.columnCount() if transposed else model.rowCount()
            selection = QItemSelection()
            if span > 0:
                for idx in indices:
                    r = idx.row()
                    if transposed:
                        selection.select(model.index(r, 0), model.index(r, span - 1))
                    else:
                        selection.select(model.index(0, r), model.index(span - 1, r))
            sm.select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        finally:
            self._syncing_selection = False

    def _connect_table_selection(self) -> None:
        """(Re)connect the table's selection model and re-apply preset selection."""
        if sm := self._preset_table.view.selectionModel():
            sm.selectionChanged.connect(self._on_table_selection_changed)
        # Re-apply the current preset list selection to the (possibly transposed) table
        self._on_preset_selection_changed(self._group_preset_sel.selectedPresets())

    def _on_table_selection_changed(self) -> None:
        """Sync the table's selected columns back to the preset list."""
        if self._syncing_selection:
            return

        view = self._preset_table.view
        sm = view.selectionModel()
        if sm is None:
            return

        indices = sm.selectedIndexes()
        if not indices:
            return

        # Collect unique columns (preset indices) from selection
        transposed = view.isTransposed()
        seen_cols = {idx.row() if transposed else idx.column() for idx in indices}

        try:
            pivot = view._get_pivot_model()
            src_indices = [
                pivot.get_source_index_for_column(c) for c in sorted(seen_cols)
            ]
        except (ValueError, IndexError):
            return

        valid = [i for i in src_indices if i.isValid()]
        if not valid:
            return

        self._syncing_selection = True
        try:
            preset_list = self._group_preset_sel.preset_list
            preset_sm = preset_list.selectionModel()
            if preset_sm is None:
                return

            selection = QItemSelection()
            for src_idx in valid:
                selection.select(src_idx, src_idx)
            preset_sm.select(
                selection, QItemSelectionModel.SelectionFlag.ClearAndSelect
            )
            # Set current to the last selected for keyboard navigation
            preset_sm.setCurrentIndex(
                valid[-1], QItemSelectionModel.SelectionFlag.NoUpdate
            )
        finally:
            self._syncing_selection = False

    def _add_preset_to_current_group(self) -> None:
        """Add a new preset to the currently selected group."""
        current_group = self._group_preset_sel.currentGroup()
        if current_group.isValid():
            self._undo_stack.push(AddPresetCommand(self._model, current_group))

    def _edit_group_properties(self) -> None:
        """Edit properties for the group or current preset."""
        current_group = self._group_preset_sel.currentGroup()
        if not current_group.isValid():
            return

        group = current_group.data(Qt.ItemDataRole.UserRole)
        if not isinstance(group, ConfigGroup):
            return

        current_preset = self._group_preset_sel.currentPreset()

        # Build dialog
        dialog = QDialog(
            self,
            Qt.WindowType.Sheet
            | Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.FramelessWindowHint,
        )
        dialog.setWindowTitle("Edit Properties")
        dialog.setModal(True)

        # Mode toggle
        group_radio = QRadioButton("All presets in group")
        preset_name = current_preset.data(Qt.ItemDataRole.DisplayRole) or ""
        preset_radio = QRadioButton(f"Preset {preset_name!r} only")
        preset_radio.setEnabled(current_preset.isValid())
        mode_group = QButtonGroup(dialog)
        mode_group.addButton(group_radio)
        mode_group.addButton(preset_radio)
        group_radio.setChecked(True)

        selector = DevicePropertySelector(dialog)
        selector.setAvailableDevices(self._loaded_devices)

        def _update_checked() -> None:
            if preset_radio.isChecked() and current_preset.isValid():
                preset_data = current_preset.data(Qt.ItemDataRole.UserRole)
                settings = preset_data.settings if preset_data else []
            else:
                settings = [s for p in group.presets.values() for s in p.settings]
            # Deduplicate by key, preserving first occurrence
            deduped: dict[tuple[str, str], DevicePropertySetting] = {}
            for s in settings:
                deduped.setdefault(s.key(), s)
            selector.setCheckedProperties(list(deduped.values()))

        mode_group.buttonToggled.connect(lambda *_: _update_checked())
        _update_checked()

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(group_radio)
        bottom_row.addWidget(preset_radio)
        bottom_row.addStretch()
        bottom_row.addWidget(btns)

        lay = QVBoxLayout(dialog)
        lay.addWidget(selector)
        lay.addLayout(bottom_row)
        dialog.resize(int(self.width() * 0.8), int(self.height() * 0.8))

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected = selector.checkedProperties()

        if preset_radio.isChecked() and current_preset.isValid():
            self._undo_stack.push(
                UpdatePresetPropertiesCommand(
                    self._model, current_preset, list(selected)
                )
            )
        else:
            # Update all presets in the group
            with undo_macro(self._undo_stack, "Update Group Properties"):
                for i in range(self._model.rowCount(current_group)):
                    preset_idx = self._model.index(i, 0, current_group)
                    self._undo_stack.push(
                        UpdatePresetPropertiesCommand(
                            self._model, preset_idx, list(selected)
                        )
                    )

    def _add_group(self) -> None:
        """Add a new group."""
        self._undo_stack.push(AddGroupCommand(self._model))

    def _remove_selected(self) -> None:
        """Remove the currently selected group or preset(s)."""
        # Check for multi-select presets first
        presets = self._group_preset_sel.selectedPresets()
        if len(presets) > 1:
            names = ", ".join(
                i.data(Qt.ItemDataRole.DisplayRole) or "?" for i in presets
            )
            msg = QMessageBox.question(
                self,
                "Confirm Deletion",
                f"Delete {len(presets)} presets ({names})?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if msg != QMessageBox.StandardButton.Yes:
                return
            with undo_macro(self._undo_stack, f"Remove {len(presets)} Presets"):
                for idx in sorted(presets, key=lambda i: i.row(), reverse=True):
                    self._undo_stack.push(RemovePresetCommand(self._model, idx))
            return

        idx = self._group_preset_sel._selected_index()
        if not idx.isValid():
            return

        payload = idx.data(Qt.ItemDataRole.UserRole)
        item_name = idx.data(Qt.ItemDataRole.DisplayRole)
        type_name = type(payload).__name__.replace("Config", "Config ")
        msg = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete {type_name} {item_name!r}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if msg != QMessageBox.StandardButton.Yes:
            return

        if isinstance(payload, ConfigGroup):
            self._undo_stack.push(RemoveGroupCommand(self._model, idx))
        elif isinstance(payload, ConfigPreset):
            self._undo_stack.push(RemovePresetCommand(self._model, idx))

    def _duplicate_selected(self) -> None:
        """Duplicate the currently selected group or preset(s)."""
        # Check for multi-select presets first
        presets = self._group_preset_sel.selectedPresets()
        if len(presets) > 1:
            with undo_macro(self._undo_stack, f"Duplicate {len(presets)} Presets"):
                for idx in presets:
                    self._undo_stack.push(DuplicatePresetCommand(self._model, idx))
            return

        idx = self._group_preset_sel._selected_index()
        if not idx.isValid():
            return
        payload = idx.data(Qt.ItemDataRole.UserRole)
        if isinstance(payload, ConfigGroup):
            self._undo_stack.push(DuplicateGroupCommand(self._model, idx))
        elif isinstance(payload, ConfigPreset):
            self._undo_stack.push(DuplicatePresetCommand(self._model, idx))

    def _update_edit_properties_enabled(
        self, group_idx: QModelIndex | None = None
    ) -> None:
        """Enable 'Edit Properties' only when the selected group has presets."""
        if group_idx is None:
            group_idx = self._group_preset_sel.currentGroup()
        has_presets = group_idx.isValid() and self._model.rowCount(group_idx) > 0
        self._tb.edit_properties_action.setEnabled(has_presets)

    def _on_model_structure_changed(self) -> None:
        """Handle rows inserted/removed in the model."""
        self._update_edit_properties_enabled()
        self.configChanged.emit()

    def _on_model_data_changed(self) -> None:
        """Handle model dataChanged (renames, value edits, etc.)."""
        self.configChanged.emit()

    def _on_undo_index_changed(self, idx: int) -> None:
        """Navigate to the item affected by the last undo/redo command."""
        self._prev_undo_index, prev = idx, self._prev_undo_index
        # Determine which command just ran
        if idx > prev:
            # Redo: the command at idx-1 just executed redo()
            cmd = self._undo_stack.command(idx - 1)
        elif idx < prev:
            # Undo: the command at idx just executed undo()
            cmd = self._undo_stack.command(idx)
        else:
            return

        # For macros, look at the first child command
        if cmd and not isinstance(cmd, _ModelCommand) and cmd.childCount() > 0:
            cmd = cmd.child(0)
        if not isinstance(cmd, _ModelCommand):
            return

        target = cmd.affected_index()
        if not target.isValid():
            return

        self._navigate_to_index(target)

    def _navigate_to_index(self, index: QModelIndex) -> None:
        """Select the given model index in the appropriate view."""
        parent = index.parent()
        tree = self._group_preset_sel.config_groups_tree
        if not parent.isValid():
            # It's a group — select it in the group list
            self._group_preset_sel.group_list.setCurrentIndex(index)
            tree.expand(index)
        else:
            # It's a preset — select its group first, then the preset
            self._group_preset_sel.group_list.setCurrentIndex(parent)
            self._group_preset_sel.preset_list.setCurrentIndex(index)
            tree.expand(parent)

    # ------------------------------------------------------------------
    # Dirty state indicator
    # ------------------------------------------------------------------

    def _update_status_indicator(self, clean: bool | None = None) -> None:
        """Update the status bar to reflect the undo stack's clean state."""
        if clean is None:
            clean = self._undo_stack.isClean()
        if clean:
            self._status_icon.setPixmap(self._clean_icon.pixmap(16, 16))
            self._status_label.setText("No changes")
            self._apply_btn.setEnabled(False)
        else:
            self._status_icon.setPixmap(self._dirty_icon.pixmap(16, 16))
            self._status_label.setText("Unsaved changes")
            self._apply_btn.setEnabled(True)

    def dirtyGroups(self) -> tuple[list[ConfigGroup], list[str], str | None]:
        """Return groups that changed, deleted names, and desired channel group.

        Compares only preset content (not the ``is_channel_group`` flag).
        The channel group designation is returned separately so the consumer
        can call ``setChannelGroup`` without needlessly recreating groups.

        Returns
        -------
        tuple[list[ConfigGroup], list[str], str | None]
            (changed_or_new_groups, deleted_group_names, channel_group_name).
            *channel_group_name* is the name of the group that should be the
            channel group, or None if the designation did not change.
        """
        current = {g.name: g for g in self.data()}
        deleted = [name for name in self._clean_groups if name not in current]
        changed = []
        for name, group in current.items():
            if name not in self._clean_groups:
                changed.append(group)
            else:
                clean = self._clean_groups[name]
                if group.presets != clean.presets:
                    changed.append(group)

        # Determine channel group change
        old_channel = next(
            (n for n, g in self._clean_groups.items() if g.is_channel_group), None
        )
        new_channel = next((n for n, g in current.items() if g.is_channel_group), None)
        channel_group = new_channel if new_channel != old_channel else None

        return changed, deleted, channel_group

    def _emit_apply_requested(self) -> None:
        changed, deleted, channel_group = self.dirtyGroups()
        self.applyRequested.emit(changed, deleted, channel_group)

    # ------------------------------------------------------------------
    # Layout management
    # ------------------------------------------------------------------

    def sizeHint(self) -> QSize:
        """Suggest a size for the widget."""
        return QSize(1200, 800)

    def _show_help(self) -> None:
        """Show help for this widget."""
        dialog = ConfigGroupsHelpDialog(self)
        size = (
            (self.size() * 0.8).expandedTo(QSize(600, 600)).boundedTo(QSize(800, 800))
        )
        dialog.resize(size)
        dialog.setWindowFlags(Qt.WindowType.Sheet | Qt.WindowType.WindowCloseButtonHint)
        dialog.exec()

    def _show_undo_view(self) -> None:
        """Show a dialog with the undo stack view."""
        dialog = QUndoView(self._undo_stack, self)
        dialog.setCleanIcon(StandardIcon.UNDO.icon())
        dialog.setEmptyLabel("<start of stack>")
        dialog.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
        )
        dialog.show()


class _ConfigEditorToolbar(QToolBar):
    """Toolbar for the ConfigGroupsEditor.

    Has actions for adding/removing/duplicating groups and presets.
    """

    def __init__(self, parent: ConfigGroupsEditor) -> None:
        super().__init__(parent)
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
        self.add_preset_action = cast(
            "QAction",
            self.addAction(
                StandardIcon.DOCUMENT_ADD.icon(),
                "Add Preset",
                parent._add_preset_to_current_group,
            ),
        )
        self.add_preset_action.setEnabled(False)
        self.edit_properties_action = cast(
            "QAction",
            self.addAction(
                StandardIcon.PROPERTY_ADD.icon(),
                "Edit Properties",
                parent._edit_group_properties,
            ),
        )
        self.edit_properties_action.setEnabled(False)
        self.duplicate_action = cast(
            "QAction",
            self.addAction(
                StandardIcon.COPY.icon(),
                "Duplicate",
                parent._duplicate_selected,
            ),
        )
        self.duplicate_action.setEnabled(False)
        self.remove_action = cast(
            "QAction",
            self.addAction(
                StandardIcon.DELETE.icon(),
                "Remove",
                parent._remove_selected,
            ),
        )
        self.remove_action.setEnabled(False)

        self.addSeparator()
        self.set_channel_action = cast(
            "QAction",
            self.addAction(
                StandardIcon.CHANNEL_GROUP.icon(),
                "Set Channel Group",
            ),
        )
        self.set_channel_action.triggered.connect(self._on_set_channel_group)

        self.addSeparator()
        # Undo/Redo actions — icon-only with descriptive tooltips
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

        # Override undo/redo buttons to icon-only (avoid layout thrash from
        # changing action text like "Undo Rename Group")
        for action in (self.undo_action, self.redo_action):
            if btn := self.widgetForAction(action):
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        if act := self.addAction(StandardIcon.HELP.icon(), "Help", parent._show_help):
            act.setToolTip("Show help")

    def _on_set_channel_group(self) -> None:
        parent = cast("ConfigGroupsEditor", self.parent())
        current_group = parent._group_preset_sel.currentGroup()
        if current_group.isValid():
            parent._undo_stack.push(
                SetChannelGroupCommand(parent._model, current_group)
            )
            self.set_channel_action.setEnabled(False)
