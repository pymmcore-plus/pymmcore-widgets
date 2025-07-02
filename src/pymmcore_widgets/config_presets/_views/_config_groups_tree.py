from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import QTreeView, QWidget

from pymmcore_widgets._models import QConfigGroupsModel
from pymmcore_widgets.config_presets._views._property_setting_delegate import (
    PropertySettingDelegate,
)

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtCore import QAbstractItemModel


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
        self.setItemDelegateForColumn(2, PropertySettingDelegate(self))

    def setModel(self, model: QAbstractItemModel | None) -> None:
        """Set the model for the tree view."""
        super().setModel(model)
        if hh := self.header():
            for col in range(hh.count()):
                hh.setSectionResizeMode(col, hh.ResizeMode.Stretch)
