from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import QTreeView, QWidget

from pymmcore_widgets._models import QConfigGroupsModel

from ._property_setting_delegate import PropertySettingDelegate
from ._undo_delegates import GroupPresetRenameDelegate, PropertyValueDelegate

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtCore import QAbstractItemModel
    from qtpy.QtGui import QUndoStack


class ConfigGroupsTree(QTreeView):
    """A tree widget that displays configuration groups."""

    @classmethod
    def create_from_core(
        cls, core: CMMCorePlus, parent: QWidget | None = None
    ) -> ConfigGroupsTree:
        """Create a ConfigGroupsTree from a CMMCorePlus instance."""
        obj = cls(parent)
        model = QConfigGroupsModel.create_from_core(core)
        obj.setModel(model)
        return obj

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._undo_stack: QUndoStack | None = None
        # Set initial delegates (will be replaced if undo stack is set)
        self.setItemDelegateForColumn(2, PropertySettingDelegate(self))

    def setUndoStack(self, undo_stack: QUndoStack) -> None:
        """Set the undo stack and configure undo-aware delegates."""
        self._undo_stack = undo_stack

        if undo_stack is not None:
            # Set up undo-aware delegates for different columns
            # Column 0 (names): for renaming groups/presets
            self.setItemDelegateForColumn(
                0, GroupPresetRenameDelegate(undo_stack, self)
            )
            # Column 2 (values): for property value changes
            self.setItemDelegateForColumn(2, PropertyValueDelegate(undo_stack, self))

    def setModel(self, model: QAbstractItemModel | None) -> None:
        """Set the model for the tree view."""
        super().setModel(model)
        if hh := self.header():
            for col in range(hh.count()):
                hh.setSectionResizeMode(col, hh.ResizeMode.Stretch)
