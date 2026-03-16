"""Custom delegates that handle undo/redo for config group editing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import (
    QAbstractItemModel,
    QEvent,
    QModelIndex,
    QObject,
    Qt,
    QTransposeProxyModel,
)
from qtpy.QtWidgets import QMessageBox, QStyledItemDelegate, QWidget

from pymmcore_widgets._models import (
    ConfigGroupPivotModel,
    DevicePropertySetting,
    QConfigGroupsModel,
)

from ._property_setting_delegate import (
    ControlType,
    PropertySettingDelegate,
    _control_type,
)
from ._undo_commands import (
    ChangePropertyValueCommand,
    RenameGroupCommand,
    RenamePresetCommand,
)

if TYPE_CHECKING:
    from qtpy.QtGui import QUndoStack
    from qtpy.QtWidgets import QStyleOptionViewItem


def _resolve_source(
    model: QAbstractItemModel | None, index: QModelIndex
) -> tuple[QConfigGroupsModel | None, QModelIndex]:
    """Resolve a (model, index) pair to the underlying QConfigGroupsModel.

    Walks through QTransposeProxyModel and ConfigGroupPivotModel layers
    to find the source QConfigGroupsModel and the corresponding setting index.
    """
    if isinstance(model, QConfigGroupsModel):
        return model, index

    if isinstance(model, QTransposeProxyModel):
        index = model.mapToSource(index)
        model = model.sourceModel()

    if isinstance(model, ConfigGroupPivotModel):
        return model.mapToSourceSettingIndex(index)

    return None, QModelIndex()


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
        new_value: str | None = None
        if hasattr(editor, "text"):
            new_value = editor.text()
        elif hasattr(editor, "currentText"):
            new_value = editor.currentText()
        elif hasattr(editor, "value"):
            new_value = editor.value()

        if new_value is None:
            return

        # Get the current value before changing it
        old_value = index.data(Qt.ItemDataRole.EditRole)
        if old_value == new_value:
            return  # No change

        # Validate the name change before creating commands
        error_msg = model.is_name_change_valid(index, str(new_value))
        if error_msg:
            # Show validation error to user
            QMessageBox.warning(None, "Cannot Rename.", error_msg)
            return

        # Create rename commands for groups/presets if validation passes
        node = model._node_from_index(index)
        if node.is_group:
            self._undo_stack.push(RenameGroupCommand(model, index, str(new_value)))
        elif node.is_preset:
            self._undo_stack.push(RenamePresetCommand(model, index, str(new_value)))


class PropertyValueDelegate(PropertySettingDelegate):
    """Delegate that creates editors from setting metadata with undo/redo."""

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
        if not index.isValid() or editor is None or not hasattr(editor, "value"):
            return super().setModelData(editor, model, index)

        src_model, src_index = _resolve_source(model, index)
        if src_model is None or not src_index.isValid():
            return super().setModelData(editor, model, index)

        new_value = editor.value()
        old_value = src_index.data(Qt.ItemDataRole.EditRole)
        if old_value == new_value:
            return

        node = src_model._node_from_index(src_index)
        if node.is_setting:
            self._undo_stack.push(
                ChangePropertyValueCommand(src_model, src_index, new_value)
            )

    def editorEvent(
        self,
        event: QEvent,
        model: QAbstractItemModel,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        """Toggle checkboxes via undo stack on single click."""
        setting = index.data(Qt.ItemDataRole.UserRole)
        if (
            isinstance(setting, DevicePropertySetting)
            and _control_type(setting) is ControlType.CHECKBOX
            and event.type() == QEvent.Type.MouseButtonRelease
        ):
            src_model, src_index = _resolve_source(model, index)
            if src_model is not None and src_index.isValid():
                new_val = "0" if setting.value == "1" else "1"
                self._undo_stack.push(
                    ChangePropertyValueCommand(src_model, src_index, new_val)
                )
                return True
            # Fallback: toggle directly without undo
            if model is not None:
                new_val = "0" if setting.value == "1" else "1"
                model.setData(index, new_val, Qt.ItemDataRole.EditRole)
            return True
        return super().editorEvent(event, model, option, index)
