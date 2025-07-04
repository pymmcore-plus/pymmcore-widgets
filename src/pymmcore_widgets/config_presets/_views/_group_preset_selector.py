from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

from qtpy.QtCore import QItemSelectionModel, QModelIndex, QSignalBlocker, Qt, Signal
from qtpy.QtWidgets import QListView, QSplitter, QStackedWidget, QWidget

from pymmcore_widgets._models import QConfigGroupsModel

from ._config_groups_tree import ConfigGroupsTree

if TYPE_CHECKING:
    from qtpy.QtCore import QAbstractItemModel


class GroupPresetSelector(QStackedWidget):
    """Widget that switches between list views and tree view for config groups.

    This widget contains:
    - A splitter with separate list views for groups and presets (index 0)
    - A tree view showing the hierarchical structure (index 1)

    The preset list and tree view share a selection model for consistency,
    while the group list uses its own selection model to show visual feedback
    when presets are selected (grayed out parent group selection).

    Signals
    -------
    groupSelectionChanged : Signal[QModelIndex, QModelIndex]
        Emitted when the group selection changes (current, previous)
    presetSelectionChanged : Signal[QModelIndex, QModelIndex]
        Emitted when the preset selection changes (current, previous)
    """

    groupSelectionChanged = Signal(QModelIndex, QModelIndex)
    presetSelectionChanged = Signal(QModelIndex, QModelIndex)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._model: QConfigGroupsModel | None = None
        self._selection_model = QItemSelectionModel()

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

        # MAIN STACK  ------------------------------------------------------

        self.addWidget(lists_splitter)  # index 0
        self.addWidget(self.config_groups_tree)  # index 1

        self._selection_model.currentChanged.connect(self._on_current_changed)

    def _on_current_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        if not current.isValid():
            return

        is_preset = current.parent().isValid()

        # Emit the same high-level signals your old slots produced.
        if is_preset:
            self.presetSelectionChanged.emit(current, previous)
        else:
            self.groupSelectionChanged.emit(current, previous)

        # Keep the three views visually in sync.
        self._sync_to_lists(current)
        self._sync_to_tree(current)

    def _on_group_selection_changed(
        self, current: QModelIndex, previous: QModelIndex
    ) -> None:
        """Handle group selection changes and emit signal."""
        # Update preset list root to show presets for the selected group
        self.preset_list.setRootIndex(current)
        self.preset_list.clearSelection()
        self.groupSelectionChanged.emit(current, previous)
        self._sync_to_tree(current)

    def _on_group_current_changed(
        self, current: QModelIndex, previous: QModelIndex
    ) -> None:
        """Handle group selection changes from the group list."""
        if not current.isValid():
            return

        # When group is selected directly, clear preset selection and update views
        self._selection_model.clearCurrentIndex()
        self.preset_list.setRootIndex(current)
        self.preset_list.clearSelection()
        self.groupSelectionChanged.emit(current, previous)
        self._sync_to_tree(current)

    # ---------------------------------------------------------------------
    # Synchronisation helpers
    # ---------------------------------------------------------------------
    def _sync_to_tree(self, idx: QModelIndex) -> None:
        """Select *idx* in the tree view while blocking feedback loops."""
        if not idx.isValid():
            return
        with QSignalBlocker(self.config_groups_tree.selectionModel()):
            self.config_groups_tree.setCurrentIndex(idx)
            self.config_groups_tree.scrollTo(idx)

    def _sync_to_lists(self, idx: QModelIndex) -> None:
        """Reflect *idx* in the list views while blocking feedback loops."""
        if not idx.isValid():
            return

        # A group lives at depth-0, a preset at depth-1.
        is_preset = idx.parent().isValid()
        group_idx = idx.parent() if is_preset else idx

        # Always set the preset list root to show presets for the current group
        self.preset_list.setRootIndex(group_idx)

        # Update group list selection (this will show grayed out when not focused)
        group_sel_model = self.group_list.selectionModel()
        if group_sel_model is not None:
            with QSignalBlocker(group_sel_model):
                group_sel_model.setCurrentIndex(
                    group_idx, QItemSelectionModel.SelectionFlag.ClearAndSelect
                )
        self.group_list.scrollTo(group_idx)

        if is_preset:
            # Preset is already current in main selection model
            self.preset_list.scrollTo(idx)
        else:
            # For group selection: clear preset selection
            self.preset_list.clearSelection()

    def selectionModel(self) -> QItemSelectionModel:
        """Return the shared selection model for this widget."""
        return self._selection_model

    def model(self) -> QConfigGroupsModel | None:
        """Return the currently attached model."""
        return self._model

    def setModel(self, model: QAbstractItemModel | None) -> None:
        """Attach *model* to all views and give them one shared selection model."""
        if not isinstance(model, QConfigGroupsModel):
            raise TypeError("Model must be an instance of QConfigGroupsModel")

        self._model = model
        self._selection_model.setModel(model)

        # Set models for all views
        self.group_list.setModel(model)
        self.preset_list.setModel(model)
        self.config_groups_tree.setModel(model)

        # Use shared selection model for preset list and tree
        self.preset_list.setSelectionModel(self._selection_model)
        self.config_groups_tree.setSelectionModel(self._selection_model)

        # Connect to group list's built-in selection model
        group_sel_model = self.group_list.selectionModel()
        if group_sel_model is not None:
            group_sel_model.currentChanged.connect(self._on_group_current_changed)

    def showListViews(self) -> None:
        """Switch to list view mode (groups and presets side by side)."""
        self.setCurrentIndex(0)

    def showTreeView(self) -> None:
        """Switch to tree view mode (hierarchical view)."""
        self.setCurrentIndex(1)

    def toggleView(self) -> None:
        """Toggle between list view and tree view modes."""
        if self.currentIndex() == 0:
            self.showTreeView()
        else:
            self.showListViews()

    def isTreeViewActive(self) -> bool:
        """Return True if tree view is currently active."""
        return bool(self.currentIndex() == 1)

    def setCurrentGroup(self, group: str) -> QModelIndex:
        """Set the currently selected group by name."""
        if not (model := self._model):
            warnings.warn(
                "Model is not set. Cannot set current group.",
                UserWarning,
                stacklevel=2,
            )
            return QModelIndex()

        idx = model.index_for_group(group)
        if idx.isValid():
            group_sel_model = self.group_list.selectionModel()
            if group_sel_model is not None:
                group_sel_model.setCurrentIndex(
                    idx, QItemSelectionModel.SelectionFlag.ClearAndSelect
                )
        else:
            group_sel_model = self.group_list.selectionModel()
            if group_sel_model is not None:
                group_sel_model.clearCurrentIndex()
        return idx

    def setCurrentPreset(self, group: str, preset: str) -> QModelIndex:
        """Set the currently selected preset by group and preset name."""
        if not (model := self._model):
            warnings.warn(
                "Model is not set. Cannot set current preset.",
                UserWarning,
                stacklevel=2,
            )
            return QModelIndex()

        group_index = self.setCurrentGroup(group)
        idx = model.index_for_preset(group_index, preset)
        if idx.isValid():
            self._selection_model.setCurrentIndex(
                idx, QItemSelectionModel.SelectionFlag.ClearAndSelect
            )
            self.preset_list.setFocus()
        else:
            self._selection_model.clearCurrentIndex()
        return idx

    def currentGroupIndex(self) -> QModelIndex:
        """Return the currently selected group index."""
        group_sel_model = self.group_list.selectionModel()
        if group_sel_model is not None:
            return group_sel_model.currentIndex()
        return QModelIndex()

    def currentPresetIndex(self) -> QModelIndex:
        """Return the currently selected preset index."""
        return self._selection_model.currentIndex()

    def clearSelection(self) -> None:
        """Clear selection in all views."""
        group_sel_model = self.group_list.selectionModel()
        if group_sel_model is not None:
            group_sel_model.clearCurrentIndex()
        self._selection_model.clearCurrentIndex()
        self.config_groups_tree.clearSelection()
        # Reset preset list root
        self.preset_list.setRootIndex(QModelIndex())
