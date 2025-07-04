from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import QModelIndex, QSignalBlocker, Qt, Signal
from qtpy.QtWidgets import QListView, QSplitter, QStackedWidget, QWidget

from pymmcore_widgets._models import QConfigGroupsModel

from ._config_groups_tree import ConfigGroupsTree

if TYPE_CHECKING:
    from qtpy.QtCore import QAbstractItemModel


class GroupPresetSelector(QStackedWidget):
    """Widget that switches between column (2-list) and tree view for config groups.

    This widget contains:
    - A splitter with separate list views for groups and presets (index 0)
    - A tree view showing the hierarchical structure (index 1)
    """

    currentPresetChanged = Signal(QModelIndex, QModelIndex)
    currentGroupChanged = Signal(QModelIndex, QModelIndex)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._model: QConfigGroupsModel | None = None

        # STACK_0 : List views for groups and presets ----------------------

        self.group_list = QListView(self)
        self.group_list.setSelectionMode(QListView.SelectionMode.SingleSelection)

        self.preset_list = QListView(self)
        self.preset_list.setSelectionMode(QListView.SelectionMode.SingleSelection)

        # Create the splitter for the list views
        lists_splitter = QSplitter(Qt.Orientation.Horizontal)
        lists_splitter.addWidget(self.group_list)
        lists_splitter.addWidget(self.preset_list)

        # STACK_1 : Tree view for config groups ----------------------------

        self.config_groups_tree = ConfigGroupsTree(self)
        self.config_groups_tree.setSelectionMode(
            ConfigGroupsTree.SelectionMode.SingleSelection
        )
        self.config_groups_tree.setSelectionBehavior(
            ConfigGroupsTree.SelectionBehavior.SelectRows
        )

        # MAIN STACK  ------------------------------------------------------

        self.addWidget(lists_splitter)  # index 0
        self.addWidget(self.config_groups_tree)  # index 1

    def model(self) -> QConfigGroupsModel | None:
        """Return the currently attached model."""
        return self._model

    def setModel(self, model: QAbstractItemModel | None) -> None:
        """Attach *model* to all views and give them one shared selection model."""
        if not isinstance(model, QConfigGroupsModel):
            raise TypeError("Model must be an instance of QConfigGroupsModel")

        self._model = model

        # Set models for all views
        self.group_list.setModel(model)
        self.preset_list.setModel(model)
        self.config_groups_tree.setModel(model)

        self._connect_selection_models()

    def _connect_selection_models(self) -> None:
        """Connect all selection model signals to slots."""
        # TODO: Disconnect
        if group_sel := self.group_list.selectionModel():
            group_sel.currentChanged.connect(self._on_group_selection_changed)

        if preset_sel := self.preset_list.selectionModel():
            preset_sel.currentChanged.connect(self._on_preset_selection_changed)

        if tree_sel := self.config_groups_tree.selectionModel():
            tree_sel.currentChanged.connect(self._on_tree_selection_changed)

    def _on_group_selection_changed(
        self, current: QModelIndex, previous: QModelIndex
    ) -> None:
        """Handle change in the group_list selection."""
        prev_preset = self.preset_list.currentIndex()
        self.preset_list.setRootIndex(current)
        self.preset_list.setCurrentIndex(QModelIndex())
        with QSignalBlocker(self.config_groups_tree.selectionModel()):
            self.config_groups_tree.collapseAll()
            self.config_groups_tree.setCurrentIndex(current)
            self.config_groups_tree.expand(current)

        self.currentGroupChanged.emit(current, previous)
        if prev_preset.isValid():
            self.currentPresetChanged.emit(QModelIndex(), prev_preset)

    def _on_preset_selection_changed(
        self, current: QModelIndex, previous: QModelIndex
    ) -> None:
        """Handle change in the preset_list selection."""
        with QSignalBlocker(self.config_groups_tree.selectionModel()):
            self.config_groups_tree.setCurrentIndex(current)
        self.currentPresetChanged.emit(current, previous)

    def _group_preset_index(self, idx: QModelIndex) -> tuple[QModelIndex, QModelIndex]:
        """Extract group and preset indices from a given index."""
        parent = idx.parent()
        # idx is a SETTING
        if (group_idx := parent.parent()).isValid():
            return group_idx, parent
        # idx is a PRESET
        if parent.isValid():
            return parent, idx
        # idx is a GROUP
        return idx, QModelIndex()

    def _on_tree_selection_changed(
        self, current: QModelIndex, previous: QModelIndex
    ) -> None:
        """Handle change in the config_groups_tree selection."""
        group_idx, preset_idx = self._group_preset_index(current)
        prev_group, prev_preset = self._group_preset_index(previous)

        if group_idx.row() != prev_group.row():
            self.currentGroupChanged.emit(group_idx, prev_group)
            if prev_preset.isValid():
                self.currentPresetChanged.emit(preset_idx, prev_preset)
        elif preset_idx.row() != prev_preset.row():
            self.currentPresetChanged.emit(preset_idx, prev_preset)

        with (
            QSignalBlocker(self.group_list.selectionModel()),
            QSignalBlocker(self.preset_list.selectionModel()),
        ):
            self.group_list.setCurrentIndex(group_idx)
            self.preset_list.setRootIndex(group_idx)
            self.preset_list.setCurrentIndex(preset_idx)

    def _selected_index(self) -> QModelIndex:
        """Return the currently selected index from the group or preset list."""
        if self.group_list.hasFocus():
            return self.group_list.currentIndex()
        elif self.preset_list.hasFocus():
            return self.preset_list.currentIndex()
        return QModelIndex()

    def removeSelected(self) -> None:
        if self._model:
            self._model.remove(self._selected_index())

    def duplicateSelected(self) -> None:
        if self._model:
            if self.group_list.hasFocus():
                self._model.duplicate_group(self.group_list.currentIndex())
            elif self.preset_list.hasFocus():
                self._model.duplicate_preset(self.preset_list.currentIndex())

    def showColumnView(self) -> None:
        """Switch to column view mode (groups and presets side by side)."""
        self.setCurrentIndex(0)

    def showTreeView(self) -> None:
        """Switch to tree view mode (hierarchical view)."""
        self.setCurrentIndex(1)

    def toggleView(self) -> None:
        """Toggle between column view and tree view modes."""
        if self.currentIndex() == 0:
            self.showTreeView()
        else:
            self.showColumnView()

    def isTreeViewActive(self) -> bool:
        """Return True if tree view is currently active."""
        return bool(self.currentIndex() == 1)

    def setCurrentGroup(self, group: str) -> QModelIndex:
        """Set the currently selected group by name."""
        if not (model := self._model):
            return QModelIndex()

        idx = model.index_for_group(group)
        self.group_list.setCurrentIndex(idx)
        return idx

    def currentGroup(self) -> QModelIndex:
        """Return the currently selected group index."""
        return self.group_list.currentIndex()

    def currentPreset(self) -> QModelIndex:
        """Return the currently selected preset index."""
        return self.preset_list.currentIndex()

    def setCurrentPreset(self, group: str, preset: str) -> QModelIndex:
        """Set the currently selected preset by group and preset name."""
        if not (model := self._model):
            return QModelIndex()

        group_index = self.setCurrentGroup(group)
        idx = model.index_for_preset(group_index, preset)
        self.preset_list.setCurrentIndex(idx)
        return idx

    def clearSelection(self) -> None:
        """Clear selection in all views."""
        group_sel_model = self.group_list.selectionModel()
        if group_sel_model is not None:
            group_sel_model.clearCurrentIndex()
        self.config_groups_tree.clearSelection()
        # Reset preset list root
        self.preset_list.setRootIndex(QModelIndex())
