"""Custom delegates that handle undo/redo for config group editing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import QModelIndex, QObject, Qt
from qtpy.QtWidgets import QStyledItemDelegate, QWidget

from pymmcore_widgets._models import QConfigGroupsModel
from pymmcore_widgets.device_properties import PropertyWidget

from ._property_setting_delegate import PropertySettingDelegate
from ._undo_commands import (
    ChangePropertyValueCommand,
    RenameGroupCommand,
    RenamePresetCommand,
)

if TYPE_CHECKING:
    from qtpy.QtCore import QAbstractItemModel
    from qtpy.QtGui import QUndoStack


class GroupPresetRenameDelegate(QStyledItemDelegate):
    """Delegate for renaming groups and presets in list views with undo support."""

    def __init__(self, undo_stack: QUndoStack, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._undo_stack = undo_stack

    def setModelData(
        self,
        editor: QWidget | None,
        model: QAbstractItemModel | None,
        index: QModelIndex,
    ) -> None:
        """Override to create undo commands for group/preset renames."""
        if (
            not index.isValid()
            or editor is None
            or not isinstance(model, QConfigGroupsModel)
        ):
            return super().setModelData(editor, model, index)  # type: ignore [no-any-return]

        # Get the new value from the editor
        new_value = None
        try:
            if hasattr(editor, "text"):
                new_value = editor.text()
            elif hasattr(editor, "currentText"):
                new_value = editor.currentText()
            elif hasattr(editor, "value"):
                new_value = editor.value()
        except (AttributeError, TypeError):
            pass

        if new_value is None:
            return

        # Get the current value before changing it
        old_value = index.data(Qt.ItemDataRole.EditRole)
        if old_value == new_value:
            return  # No change

        # Create rename commands for groups/presets
        node = model._node_from_index(index)
        if node.is_group:
            self._undo_stack.push(RenameGroupCommand(model, index, str(new_value)))
        elif node.is_preset:
            self._undo_stack.push(RenamePresetCommand(model, index, str(new_value)))


class PropertyValueDelegate(PropertySettingDelegate):
    """Delegate that uses PropertyWidgets and handles undo/redo for property values."""

    def __init__(self, undo_stack: QUndoStack, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._undo_stack = undo_stack

    def setModelData(
        self,
        editor: QWidget | None,
        model: QAbstractItemModel | None,
        index: QModelIndex,
    ) -> None:
        """Override to create undo commands for property value changes."""
        if (
            not index.isValid()
            or editor is None
            or not isinstance(model, QConfigGroupsModel)
            or not isinstance(editor, PropertyWidget)
        ):
            # Fall back to parent implementation for non-property editors
            return super().setModelData(editor, model, index)

        # Get the new value from the PropertyWidget
        new_value = editor.value()

        # Get the current value before changing it
        old_value = index.data(Qt.ItemDataRole.EditRole)
        if old_value == new_value:
            return  # No change

        # Create and push the undo command for property value changes
        node = model._node_from_index(index)
        if node.is_setting:
            self._undo_stack.push(ChangePropertyValueCommand(model, index, new_value))
