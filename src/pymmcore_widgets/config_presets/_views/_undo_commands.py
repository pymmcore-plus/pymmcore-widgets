"""Undo/Redo command classes for ConfigGroupsEditor operations.

Uses QPersistentModelIndex with row-path fallback: persistent indices go stale
when the target row is removed and re-inserted (e.g. undo add → redo add).  We
store the original row path (tuple of row indices from root) at construction
time and reconstruct from it when the persistent index is no longer valid.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from qtpy.QtCore import QModelIndex, QPersistentModelIndex

if TYPE_CHECKING:
    from collections.abc import Sequence

    from PyQt6.QtGui import QUndoCommand

    from pymmcore_widgets._models import (
        ConfigGroup,
        ConfigPreset,
        DevicePropertySetting,
        QConfigGroupsModel,
    )
else:
    from qtpy.QtGui import QUndoCommand


def _row_path(index: QModelIndex) -> tuple[int, ...]:
    """Extract the row path from root to *index*."""
    path: list[int] = []
    idx = index
    while idx.isValid():
        path.append(idx.row())
        idx = idx.parent()
    path.reverse()
    return tuple(path)


def _resolve(
    model: QConfigGroupsModel,
    persistent: QPersistentModelIndex,
    path: tuple[int, ...],
) -> tuple[QModelIndex, QPersistentModelIndex]:
    """Return a live QModelIndex, refreshing *persistent* from *path* if stale."""
    if persistent.isValid():
        return QModelIndex(persistent), persistent
    idx = QModelIndex()
    for row in path:
        idx = model.index(row, 0, idx)
    new_persistent = QPersistentModelIndex(idx) if idx.isValid() else persistent
    return idx, new_persistent


class AddGroupCommand(QUndoCommand):
    """Command for adding a new config group."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        name: str = "New Group",
        parent: QUndoCommand | None = None,
    ) -> None:
        # the \n separates ActionText from text used in QUndoStackView
        super().__init__(f"Add Group '{name}'\n", parent)
        self._model = model
        self._name = name
        self._group_index: QPersistentModelIndex | None = None

    def redo(self) -> None:
        """Execute the add group operation."""
        index = self._model.add_group(self._name)
        if index.isValid():
            self._group_index = QPersistentModelIndex(index)

    def undo(self) -> None:
        """Undo the add group operation."""
        if self._group_index and self._group_index.isValid():
            self._model.removeRows(self._group_index.row(), 1, QModelIndex())


class RemoveGroupCommand(QUndoCommand):
    """Command for removing a config group."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        group_index: QModelIndex,
        parent: QUndoCommand | None = None,
    ) -> None:
        group_name = group_index.data() or "Group"
        # the \n separates ActionText from text used in QUndoStackView
        super().__init__(f"Remove Group '{group_name}'\n", parent)
        self._model = model
        self._group_index = QPersistentModelIndex(group_index)
        self._row = group_index.row()
        self._group_data: ConfigGroup | None = None

    def redo(self) -> None:
        """Execute the remove group operation."""
        # Store the group data before removing
        if self._group_index.isValid():
            from qtpy.QtCore import Qt

            self._group_data = deepcopy(
                self._group_index.data(Qt.ItemDataRole.UserRole)
            )
            self._model.removeRows(self._row, 1, QModelIndex())

    def undo(self) -> None:
        """Undo the remove group operation."""
        if self._group_data:
            self._model.set_undo_redo_mode(True)
            try:
                self._model.insertRows(
                    self._row, 1, QModelIndex(), _payloads=[self._group_data]
                )
            finally:
                self._model.set_undo_redo_mode(False)


class DuplicateGroupCommand(QUndoCommand):
    """Command for duplicating a config group."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        group_index: QModelIndex,
        parent: QUndoCommand | None = None,
    ) -> None:
        group_name = group_index.data() or "Group"
        # the \n separates ActionText from text used in QUndoStackView
        super().__init__(f"Duplicate Group '{group_name}'\n", parent)
        self._model = model
        self._group_index = QPersistentModelIndex(group_index)
        self._group_path = _row_path(group_index)
        self._new_group_index: QPersistentModelIndex | None = None

    def redo(self) -> None:
        """Execute the duplicate group operation."""
        idx, self._group_index = _resolve(
            self._model, self._group_index, self._group_path
        )
        if idx.isValid():
            new_index = self._model.duplicate_group(idx)
            if new_index.isValid():
                self._new_group_index = QPersistentModelIndex(new_index)

    def undo(self) -> None:
        """Undo the duplicate group operation."""
        if self._new_group_index and self._new_group_index.isValid():
            self._model.removeRows(self._new_group_index.row(), 1, QModelIndex())


class RenameGroupCommand(QUndoCommand):
    """Command for renaming a config group."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        group_index: QModelIndex,
        new_name: str,
        parent: QUndoCommand | None = None,
    ) -> None:
        old_name = group_index.data() or "Group"
        # the \n separates ActionText from text used in QUndoStackView
        super().__init__(f"Rename Group '{old_name}' to '{new_name}'\n", parent)
        self._model = model
        self._group_index = QPersistentModelIndex(group_index)
        self._group_path = _row_path(group_index)
        self._old_name = old_name
        self._new_name = new_name

    def redo(self) -> None:
        """Execute the rename group operation."""
        idx, self._group_index = _resolve(
            self._model, self._group_index, self._group_path
        )
        if idx.isValid():
            self._model.set_undo_redo_mode(True)
            try:
                self._model.setData(idx, self._new_name)
            finally:
                self._model.set_undo_redo_mode(False)

    def undo(self) -> None:
        """Undo the rename group operation."""
        idx, self._group_index = _resolve(
            self._model, self._group_index, self._group_path
        )
        if idx.isValid():
            self._model.set_undo_redo_mode(True)
            try:
                self._model.setData(idx, self._old_name)
            finally:
                self._model.set_undo_redo_mode(False)


class AddPresetCommand(QUndoCommand):
    """Command for adding a new preset to a group."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        group_index: QModelIndex,
        name: str = "New Preset",
        parent: QUndoCommand | None = None,
    ) -> None:
        group_name = group_index.data() or "Group"
        # the \n separates ActionText from text used in QUndoStackView
        super().__init__(f"Add Preset '{name}' to '{group_name}'\n", parent)
        self._model = model
        self._group_index = QPersistentModelIndex(group_index)
        self._group_path = _row_path(group_index)
        self._name = name
        self._preset_index: QPersistentModelIndex | None = None

    def redo(self) -> None:
        """Execute the add preset operation."""
        group_idx, self._group_index = _resolve(
            self._model, self._group_index, self._group_path
        )
        if group_idx.isValid():
            preset_index = self._model.add_preset(group_idx, self._name)
            if preset_index.isValid():
                self._preset_index = QPersistentModelIndex(preset_index)

    def undo(self) -> None:
        """Undo the add preset operation."""
        group_idx, self._group_index = _resolve(
            self._model, self._group_index, self._group_path
        )
        if self._preset_index and self._preset_index.isValid() and group_idx.isValid():
            self._model.removeRows(self._preset_index.row(), 1, group_idx)


class RemovePresetCommand(QUndoCommand):
    """Command for removing a preset from a group."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        preset_index: QModelIndex,
        parent: QUndoCommand | None = None,
    ) -> None:
        preset_name = preset_index.data() or "Preset"
        group_name = preset_index.parent().data() or "Group"
        # the \n separates ActionText from text used in QUndoStackView
        super().__init__(f"Remove Preset '{preset_name}' from '{group_name}'\n", parent)
        self._model = model
        self._preset_index = QPersistentModelIndex(preset_index)
        self._group_index = QPersistentModelIndex(preset_index.parent())
        self._group_path = _row_path(preset_index.parent())
        self._row = preset_index.row()
        self._preset_data: ConfigPreset | None = None

    def redo(self) -> None:
        """Execute the remove preset operation."""
        preset_idx, self._preset_index = _resolve(
            self._model, self._preset_index, (*self._group_path, self._row)
        )
        if preset_idx.isValid():
            from qtpy.QtCore import Qt

            self._preset_data = deepcopy(
                preset_idx.data(Qt.ItemDataRole.UserRole)
            )
            group_idx, self._group_index = _resolve(
                self._model, self._group_index, self._group_path
            )
            if group_idx.isValid():
                self._model.removeRows(self._row, 1, group_idx)

    def undo(self) -> None:
        """Undo the remove preset operation."""
        group_idx, self._group_index = _resolve(
            self._model, self._group_index, self._group_path
        )
        if self._preset_data and group_idx.isValid():
            self._model.set_undo_redo_mode(True)
            try:
                self._model.insertRows(
                    self._row, 1, group_idx, _payloads=[self._preset_data]
                )
            finally:
                self._model.set_undo_redo_mode(False)


class DuplicatePresetCommand(QUndoCommand):
    """Command for duplicating a preset."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        preset_index: QModelIndex,
        parent: QUndoCommand | None = None,
    ) -> None:
        preset_name = preset_index.data() or "Preset"
        # the \n separates ActionText from text used in QUndoStackView
        super().__init__(f"Duplicate Preset '{preset_name}'\n", parent)
        self._model = model
        self._preset_index = QPersistentModelIndex(preset_index)
        self._preset_path = _row_path(preset_index)
        self._new_preset_index: QPersistentModelIndex | None = None

    def redo(self) -> None:
        """Execute the duplicate preset operation."""
        idx, self._preset_index = _resolve(
            self._model, self._preset_index, self._preset_path
        )
        if idx.isValid():
            new_preset_index = self._model.duplicate_preset(idx)
            if new_preset_index.isValid():
                self._new_preset_index = QPersistentModelIndex(new_preset_index)

    def undo(self) -> None:
        """Undo the duplicate preset operation."""
        if self._new_preset_index and self._new_preset_index.isValid():
            group_index = self._new_preset_index.parent()
            self._model.removeRows(self._new_preset_index.row(), 1, group_index)


class RenamePresetCommand(QUndoCommand):
    """Command for renaming a preset."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        preset_index: QModelIndex,
        new_name: str,
        parent: QUndoCommand | None = None,
    ) -> None:
        old_name = preset_index.data() or "Preset"
        # the \n separates ActionText from text used in QUndoStackView
        super().__init__(f"Rename Preset '{old_name}' to '{new_name}'\n", parent)
        self._model = model
        self._preset_index = QPersistentModelIndex(preset_index)
        self._preset_path = _row_path(preset_index)
        self._old_name = old_name
        self._new_name = new_name

    def redo(self) -> None:
        """Execute the rename preset operation."""
        idx, self._preset_index = _resolve(
            self._model, self._preset_index, self._preset_path
        )
        if idx.isValid():
            self._model.set_undo_redo_mode(True)
            try:
                self._model.setData(idx, self._new_name)
            finally:
                self._model.set_undo_redo_mode(False)

    def undo(self) -> None:
        """Undo the rename preset operation."""
        idx, self._preset_index = _resolve(
            self._model, self._preset_index, self._preset_path
        )
        if idx.isValid():
            self._model.set_undo_redo_mode(True)
            try:
                self._model.setData(idx, self._old_name)
            finally:
                self._model.set_undo_redo_mode(False)


class UpdatePresetPropertiesCommand(QUndoCommand):
    """Command for updating the properties in a preset."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        preset_index: QModelIndex,
        new_properties: Sequence[DevicePropertySetting],
        parent: QUndoCommand | None = None,
    ) -> None:
        preset_name = preset_index.data() or "Preset"
        # the \n separates ActionText from text used in QUndoStackView
        super().__init__(f"Update Properties in '{preset_name}'\n", parent)
        self._model = model
        self._preset_index = QPersistentModelIndex(preset_index)
        self._preset_path = _row_path(preset_index)
        self._new_properties = deepcopy(list(new_properties))
        self._old_settings: list[DevicePropertySetting] | None = None

    def redo(self) -> None:
        """Execute the update preset properties operation."""
        idx, self._preset_index = _resolve(
            self._model, self._preset_index, self._preset_path
        )
        if idx.isValid():
            from qtpy.QtCore import Qt

            preset_data = idx.data(Qt.ItemDataRole.UserRole)
            if preset_data:
                self._old_settings = deepcopy(preset_data.settings)

            self._model.set_undo_redo_mode(True)
            try:
                self._model.update_preset_properties(idx, self._new_properties)
            finally:
                self._model.set_undo_redo_mode(False)

    def undo(self) -> None:
        """Undo the update preset properties operation."""
        idx, self._preset_index = _resolve(
            self._model, self._preset_index, self._preset_path
        )
        if self._old_settings is not None and idx.isValid():
            self._model.set_undo_redo_mode(True)
            try:
                self._model.update_preset_settings(idx, self._old_settings)
            finally:
                self._model.set_undo_redo_mode(False)


class UpdatePresetSettingsCommand(QUndoCommand):
    """Command for updating all settings in a preset."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        preset_index: QModelIndex,
        new_settings: list[DevicePropertySetting],
        parent: QUndoCommand | None = None,
    ) -> None:
        preset_name = preset_index.data() or "Preset"
        # the \n separates ActionText from text used in QUndoStackView
        super().__init__(f"Update Settings in '{preset_name}'\n", parent)
        self._model = model
        self._preset_index = QPersistentModelIndex(preset_index)
        self._preset_path = _row_path(preset_index)
        self._new_settings = deepcopy(new_settings)
        self._old_settings: list[DevicePropertySetting] | None = None

    def redo(self) -> None:
        """Execute the update preset settings operation."""
        idx, self._preset_index = _resolve(
            self._model, self._preset_index, self._preset_path
        )
        if idx.isValid():
            from qtpy.QtCore import Qt

            preset_data = idx.data(Qt.ItemDataRole.UserRole)
            if preset_data:
                self._old_settings = deepcopy(preset_data.settings)

            self._model.set_undo_redo_mode(True)
            try:
                self._model.update_preset_settings(idx, self._new_settings)
            finally:
                self._model.set_undo_redo_mode(False)

    def undo(self) -> None:
        """Undo the update preset settings operation."""
        idx, self._preset_index = _resolve(
            self._model, self._preset_index, self._preset_path
        )
        if self._old_settings is not None and idx.isValid():
            self._model.set_undo_redo_mode(True)
            try:
                self._model.update_preset_settings(idx, self._old_settings)
            finally:
                self._model.set_undo_redo_mode(False)


class ChangePropertyValueCommand(QUndoCommand):
    """Command for changing a single property value in a preset."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        property_index: QModelIndex,
        new_value: Any,
        parent: QUndoCommand | None = None,
    ) -> None:
        preset_index = property_index.parent()
        preset_name = preset_index.data() or "Preset"
        # the \n separates ActionText from text used in QUndoStackView
        super().__init__(f"Change Property Value in '{preset_name}'\n", parent)
        self._model = model
        self._property_index = QPersistentModelIndex(property_index)
        self._property_path = _row_path(property_index)
        self._new_value = new_value
        self._old_value: Any = None

    def redo(self) -> None:
        """Execute the change property value operation."""
        idx, self._property_index = _resolve(
            self._model, self._property_index, self._property_path
        )
        if idx.isValid():
            self._old_value = idx.data()
            self._model.setData(idx, self._new_value)

    def undo(self) -> None:
        """Undo the change property value operation."""
        idx, self._property_index = _resolve(
            self._model, self._property_index, self._property_path
        )
        if self._old_value is not None and idx.isValid():
            self._model.setData(idx, self._old_value)


class SetChannelGroupCommand(QUndoCommand):
    """Command for setting/unsetting a group as the channel group."""

    def __init__(
        self,
        model: QConfigGroupsModel,
        group_index: QModelIndex | None,
        parent: QUndoCommand | None = None,
    ) -> None:
        if group_index:
            group_name = group_index.data() or "Group"
            super().__init__(f"Set '{group_name}' as Channel Group\n", parent)
        else:
            super().__init__("Unset Channel Group\n", parent)

        self._model = model
        self._new_group_index = (
            QPersistentModelIndex(group_index) if group_index else None
        )
        self._new_group_path = _row_path(group_index) if group_index else ()
        self._old_channel_group_index: QPersistentModelIndex | None = None
        self._old_channel_group_path: tuple[int, ...] = ()

    def redo(self) -> None:
        """Execute the set channel group operation."""
        from qtpy.QtCore import Qt

        # Find and store the current channel group
        self._old_channel_group_index = None
        self._old_channel_group_path = ()
        for i in range(self._model.rowCount()):
            idx = self._model.index(i, 0)
            group_data = idx.data(Qt.ItemDataRole.UserRole)
            if (
                group_data
                and hasattr(group_data, "is_channel_group")
                and group_data.is_channel_group
            ):
                self._old_channel_group_index = QPersistentModelIndex(idx)
                self._old_channel_group_path = _row_path(idx)
                break

        if self._new_group_index is not None:
            new_idx, self._new_group_index = _resolve(
                self._model, self._new_group_index, self._new_group_path
            )
        else:
            new_idx = None
        self._model.set_channel_group(new_idx if new_idx and new_idx.isValid() else None)

    def undo(self) -> None:
        """Undo the set channel group operation."""
        if self._old_channel_group_index is not None:
            old_idx, self._old_channel_group_index = _resolve(
                self._model,
                self._old_channel_group_index,
                self._old_channel_group_path,
            )
        else:
            old_idx = None
        self._model.set_channel_group(
            old_idx if old_idx and old_idx.isValid() else None
        )
