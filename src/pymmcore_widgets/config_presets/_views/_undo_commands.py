"""Undo/Redo command classes for ConfigGroupsEditor operations.

Every command exposes ``affected_index()`` — the model index the UI should
navigate to after the command runs (redo *or* undo).
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from qtpy.QtCore import QModelIndex, QPersistentModelIndex, Qt
from qtpy.QtGui import QUndoStack

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from PyQt6.QtGui import QUndoCommand

    from pymmcore_widgets._models import (
        ConfigGroup,
        ConfigPreset,
        DevicePropertySetting,
        QConfigGroupsModel,
    )
else:
    from qtpy.QtGui import QUndoCommand


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextmanager
def undo_macro(undo_stack: QUndoStack, text: str) -> Iterator[None]:
    """Context manager to group multiple commands into a single undo step."""
    undo_stack.beginMacro(text)
    try:
        yield
    finally:
        undo_stack.endMacro()


class _TrackedIndex:
    """A model index that survives remove / re-add cycles.

    Stores both a ``QPersistentModelIndex`` (fast when valid) and the original
    row-path from root (fallback when the persistent index goes stale because
    the row was removed then re-inserted by undo/redo).
    """

    def __init__(self, index: QModelIndex) -> None:
        self._persistent = QPersistentModelIndex(index)
        self._path = self._compute_path(index)

    def resolve(self, model: QConfigGroupsModel) -> QModelIndex:
        """Return a live QModelIndex, reconstructing from row-path if needed."""
        if self._persistent.isValid():
            return QModelIndex(self._persistent)
        idx = QModelIndex()
        for row in self._path:
            idx = model.index(row, 0, idx)
        if idx.isValid():
            self._persistent = QPersistentModelIndex(idx)
        return idx

    @staticmethod
    def _compute_path(index: QModelIndex) -> tuple[int, ...]:
        path: list[int] = []
        idx = index
        while idx.isValid():
            path.append(idx.row())
            idx = idx.parent()
        path.reverse()
        return tuple(path)


class _ModelCommand(QUndoCommand):
    """Base class for commands that operate on a QConfigGroupsModel."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        text: str,
        parent: QUndoCommand | None = None,
    ) -> None:
        # the \n separates ActionText from text used in QUndoStackView
        super().__init__(f"{text}\n", parent)
        self._model = model
        self._last_affected: QModelIndex = QModelIndex()

    def affected_index(self) -> QModelIndex:
        """Return the index the UI should navigate to after this command."""
        return self._last_affected

    @contextmanager
    def _undo_mode(self) -> Iterator[None]:
        """Suppress name-uniqueness validation during undo/redo."""
        self._model.set_undo_redo_mode(True)
        try:
            yield
        finally:
            self._model.set_undo_redo_mode(False)


# ---------------------------------------------------------------------------
# Group commands
# ---------------------------------------------------------------------------


class AddGroupCommand(_ModelCommand):
    """Add a new config group."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        name: str = "New Group",
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(model=model, text=f"Add Group '{name}'", parent=parent)
        self._name = name
        self._group_index: QPersistentModelIndex | None = None

    def redo(self) -> None:
        index = self._model.add_group(self._name)
        if index.isValid():
            self._group_index = QPersistentModelIndex(index)
        self._last_affected = index

    def undo(self) -> None:
        self._last_affected = QModelIndex()
        if self._group_index and self._group_index.isValid():
            self._model.removeRows(self._group_index.row(), 1, QModelIndex())


class RemoveGroupCommand(_ModelCommand):
    """Remove a config group."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        group_index: QModelIndex,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(
            model=model,
            text=f"Remove Group '{group_index.data() or 'Group'}'",
            parent=parent,
        )
        self._group_index = QPersistentModelIndex(group_index)
        self._row = group_index.row()
        self._group_data: ConfigGroup | None = None

    def redo(self) -> None:
        if self._group_index.isValid():
            self._group_data = deepcopy(
                self._group_index.data(Qt.ItemDataRole.UserRole)
            )
            self._model.removeRows(self._row, 1, QModelIndex())
        self._last_affected = QModelIndex()

    def undo(self) -> None:
        if self._group_data:
            with self._undo_mode():
                self._model.insertRows(
                    self._row, 1, QModelIndex(), _payloads=[self._group_data]
                )
        self._last_affected = self._model.index(self._row, 0)


class DuplicateGroupCommand(_ModelCommand):
    """Duplicate a config group."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        group_index: QModelIndex,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(
            model=model,
            text=f"Duplicate Group '{group_index.data() or 'Group'}'",
            parent=parent,
        )
        self._source = _TrackedIndex(group_index)
        self._new_group_index: QPersistentModelIndex | None = None

    def redo(self) -> None:
        idx = self._source.resolve(self._model)
        if idx.isValid():
            new_index = self._model.duplicate_group(idx)
            if new_index.isValid():
                self._new_group_index = QPersistentModelIndex(new_index)
            self._last_affected = new_index
        else:
            self._last_affected = QModelIndex()

    def undo(self) -> None:
        if self._new_group_index and self._new_group_index.isValid():
            self._model.removeRows(self._new_group_index.row(), 1, QModelIndex())
        self._last_affected = self._source.resolve(self._model)


# ---------------------------------------------------------------------------
# Preset commands
# ---------------------------------------------------------------------------


class AddPresetCommand(_ModelCommand):
    """Add a new preset to a group."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        group_index: QModelIndex,
        name: str = "New Preset",
        parent: QUndoCommand | None = None,
    ) -> None:
        group_name = group_index.data() or "Group"
        super().__init__(
            model=model,
            text=f"Add Preset '{name}' to '{group_name}'",
            parent=parent,
        )
        self._group = _TrackedIndex(group_index)
        self._name = name
        self._preset_index: QPersistentModelIndex | None = None

    def redo(self) -> None:
        group_idx = self._group.resolve(self._model)
        if group_idx.isValid():
            preset_index = self._model.add_preset(group_idx, self._name)
            if preset_index.isValid():
                self._preset_index = QPersistentModelIndex(preset_index)
            self._last_affected = preset_index
        else:
            self._last_affected = QModelIndex()

    def undo(self) -> None:
        group_idx = self._group.resolve(self._model)
        if self._preset_index and self._preset_index.isValid() and group_idx.isValid():
            self._model.removeRows(self._preset_index.row(), 1, group_idx)
        self._last_affected = group_idx


class RemovePresetCommand(_ModelCommand):
    """Remove a preset from a group."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        preset_index: QModelIndex,
        parent: QUndoCommand | None = None,
    ) -> None:
        preset_name = preset_index.data() or "Preset"
        group_name = preset_index.parent().data() or "Group"
        super().__init__(
            model=model,
            text=f"Remove Preset '{preset_name}' from '{group_name}'",
            parent=parent,
        )
        self._preset = _TrackedIndex(preset_index)
        self._group = _TrackedIndex(preset_index.parent())
        self._row = preset_index.row()
        self._preset_data: ConfigPreset | None = None

    def redo(self) -> None:
        preset_idx = self._preset.resolve(self._model)
        if preset_idx.isValid():
            self._preset_data = deepcopy(preset_idx.data(Qt.ItemDataRole.UserRole))
            group_idx = self._group.resolve(self._model)
            if group_idx.isValid():
                self._model.removeRows(self._row, 1, group_idx)
            self._last_affected = group_idx
        else:
            self._last_affected = QModelIndex()

    def undo(self) -> None:
        group_idx = self._group.resolve(self._model)
        if self._preset_data and group_idx.isValid():
            with self._undo_mode():
                self._model.insertRows(
                    self._row, 1, group_idx, _payloads=[self._preset_data]
                )
        self._last_affected = self._model.index(self._row, 0, group_idx)


class DuplicatePresetCommand(_ModelCommand):
    """Duplicate a preset."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        preset_index: QModelIndex,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(
            model=model,
            text=f"Duplicate Preset '{preset_index.data() or 'Preset'}'",
            parent=parent,
        )
        self._source = _TrackedIndex(preset_index)
        self._new_preset_index: QPersistentModelIndex | None = None

    def redo(self) -> None:
        idx = self._source.resolve(self._model)
        if idx.isValid():
            new_index = self._model.duplicate_preset(idx)
            if new_index.isValid():
                self._new_preset_index = QPersistentModelIndex(new_index)
            self._last_affected = new_index
        else:
            self._last_affected = QModelIndex()

    def undo(self) -> None:
        if self._new_preset_index and self._new_preset_index.isValid():
            group_index = self._new_preset_index.parent()
            self._model.removeRows(self._new_preset_index.row(), 1, group_index)
        self._last_affected = self._source.resolve(self._model)


# ---------------------------------------------------------------------------
# Rename (works for both groups and presets)
# ---------------------------------------------------------------------------


class _RenameCommand(_ModelCommand):
    """Base for rename commands (shared redo/undo logic)."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        index: QModelIndex,
        new_name: str,
        kind: str,
        parent: QUndoCommand | None = None,
    ) -> None:
        old_name = index.data() or kind
        super().__init__(
            model=model,
            text=f"Rename {kind} '{old_name}' to '{new_name}'",
            parent=parent,
        )
        self._target = _TrackedIndex(index)
        self._old_name = old_name
        self._new_name = new_name

    def redo(self) -> None:
        idx = self._target.resolve(self._model)
        if idx.isValid():
            with self._undo_mode():
                self._model.setData(idx, self._new_name)
        self._last_affected = idx

    def undo(self) -> None:
        idx = self._target.resolve(self._model)
        if idx.isValid():
            with self._undo_mode():
                self._model.setData(idx, self._old_name)
        self._last_affected = idx


class RenameGroupCommand(_RenameCommand):
    """Rename a config group."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        group_index: QModelIndex,
        new_name: str,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(
            model=model,
            index=group_index,
            new_name=new_name,
            kind="Group",
            parent=parent,
        )


class RenamePresetCommand(_RenameCommand):
    """Rename a preset."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        preset_index: QModelIndex,
        new_name: str,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(
            model=model,
            index=preset_index,
            new_name=new_name,
            kind="Preset",
            parent=parent,
        )


# ---------------------------------------------------------------------------
# Property / settings commands
# ---------------------------------------------------------------------------


class _UpdatePresetCommand(_ModelCommand):
    """Base for commands that swap a preset's settings, with undo support."""

    _redo_model_method: str  # model method name called in redo

    def __init__(
        self,
        model: QConfigGroupsModel,
        preset_index: QModelIndex,
        new_data: Sequence[DevicePropertySetting],
        text: str,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(model=model, text=text, parent=parent)
        self._target = _TrackedIndex(preset_index)
        self._new_data = deepcopy(list(new_data))
        self._old_settings: list[DevicePropertySetting] | None = None

    def redo(self) -> None:
        idx = self._target.resolve(self._model)
        if idx.isValid():
            preset_data = idx.data(Qt.ItemDataRole.UserRole)
            if preset_data:
                self._old_settings = deepcopy(preset_data.settings)
            with self._undo_mode():
                getattr(self._model, self._redo_model_method)(idx, self._new_data)
        self._last_affected = idx

    def undo(self) -> None:
        idx = self._target.resolve(self._model)
        if self._old_settings is not None and idx.isValid():
            with self._undo_mode():
                self._model.update_preset_settings(idx, self._old_settings)
        self._last_affected = idx


class UpdatePresetPropertiesCommand(_UpdatePresetCommand):
    """Update which properties a preset contains (merge with existing)."""

    _redo_model_method = "update_preset_properties"

    def __init__(
        self,
        model: QConfigGroupsModel,
        preset_index: QModelIndex,
        new_properties: Sequence[DevicePropertySetting],
        parent: QUndoCommand | None = None,
    ) -> None:
        name = preset_index.data() or "Preset"
        super().__init__(
            model,
            preset_index=preset_index,
            new_data=new_properties,
            text=f"Update Properties in '{name}'",
            parent=parent,
        )


class UpdatePresetSettingsCommand(_UpdatePresetCommand):
    """Replace all settings in a preset (wholesale)."""

    _redo_model_method = "update_preset_settings"

    def __init__(
        self,
        model: QConfigGroupsModel,
        preset_index: QModelIndex,
        new_settings: Sequence[DevicePropertySetting],
        parent: QUndoCommand | None = None,
    ) -> None:
        name = preset_index.data() or "Preset"
        super().__init__(
            model=model,
            preset_index=preset_index,
            new_data=new_settings,
            text=f"Update Settings in '{name}'",
            parent=parent,
        )


class ChangePropertyValueCommand(_ModelCommand):
    """Change a single property value in a preset."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        property_index: QModelIndex,
        new_value: Any,
        parent: QUndoCommand | None = None,
    ) -> None:
        preset_name = property_index.parent().data() or "Preset"
        super().__init__(
            model=model,
            text=f"Change Property Value in '{preset_name}'",
            parent=parent,
        )
        self._target = _TrackedIndex(property_index)
        self._new_value = new_value
        self._old_value: Any = None

    def redo(self) -> None:
        idx = self._target.resolve(self._model)
        if idx.isValid():
            self._old_value = idx.data()
            self._model.setData(idx, self._new_value)
        self._last_affected = idx.parent() if idx.isValid() else QModelIndex()

    def undo(self) -> None:
        idx = self._target.resolve(self._model)
        if self._old_value is not None and idx.isValid():
            self._model.setData(idx, self._old_value)
        self._last_affected = idx.parent() if idx.isValid() else QModelIndex()


# ---------------------------------------------------------------------------
# Channel group command
# ---------------------------------------------------------------------------


class SetChannelGroupCommand(_ModelCommand):
    """Set or unset the channel group."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        group_index: QModelIndex | None,
        parent: QUndoCommand | None = None,
    ) -> None:
        if group_index:
            text = f"Set '{group_index.data() or 'Group'}' as Channel Group"
        else:
            text = "Unset Channel Group"
        super().__init__(model=model, text=text, parent=parent)
        self._new_target = _TrackedIndex(group_index) if group_index else None
        self._old_target: _TrackedIndex | None = None

    def _apply(self, target: _TrackedIndex | None) -> None:
        idx = target.resolve(self._model) if target else None
        valid = idx if idx and idx.isValid() else None
        self._model.set_channel_group(valid)
        self._last_affected = QModelIndex(valid) if valid else QModelIndex()

    def redo(self) -> None:
        # Find and store the current channel group before overwriting
        self._old_target = None
        for i in range(self._model.rowCount()):
            idx = self._model.index(i, 0)
            data = idx.data(Qt.ItemDataRole.UserRole)
            if data and getattr(data, "is_channel_group", False):
                self._old_target = _TrackedIndex(idx)
                break
        self._apply(self._new_target)

    def undo(self) -> None:
        self._apply(self._old_target)
