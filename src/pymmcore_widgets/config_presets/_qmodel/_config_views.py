from __future__ import annotations

from typing import TYPE_CHECKING, Callable, cast

from PyQt6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    Qt,
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QListView,
    QSplitter,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets.device_properties import DevicePropertyTable
from pymmcore_widgets.device_properties._property_widget import PropertyWidget

from ._config_model import ConfigTreeModel, _Node

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from pymmcore_plus.model import ConfigGroup, ConfigPreset


class SettingValueDelegate(QStyledItemDelegate):
    """Item delegate that uses a PropertyWidget for editing PropertySetting values."""

    def createEditor(
        self, parent: QWidget | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget | None:
        node = cast("_Node", index.internalPointer())
        if not (model := index.model()) or (index.column() != 2) or not node.is_setting:
            return super().createEditor(parent, option, index)

        row = index.row()
        device = model.data(index.sibling(row, 0))
        prop = model.data(index.sibling(row, 1))
        widget = PropertyWidget(device, prop, parent=parent, connect_core=False)
        widget.valueChanged.connect(lambda: self.commitData.emit(widget))
        widget.setAutoFillBackground(True)
        return widget

    def setEditorData(self, editor: QWidget | None, index: QModelIndex) -> None:
        if (model := index.model()) and isinstance(editor, PropertyWidget):
            data = model.data(index, Qt.ItemDataRole.EditRole)
            editor.setValue(data)
        else:
            super().setEditorData(editor, index)

    def setModelData(
        self,
        editor: QWidget | None,
        model: QAbstractItemModel | None,
        index: QModelIndex,
    ) -> None:
        if model and isinstance(editor, PropertyWidget):
            model.setData(index, editor.value(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)


# -----------------------------------------------------------------------------
# High-level editor widget
# -----------------------------------------------------------------------------


class ConfigGroupsEditor(QWidget):
    """Widget composed of two QListViews backed by a single tree model."""

    configChanged = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = ConfigTreeModel()

        # views --------------------------------------------------------------
        self._group_view = QListView()
        self._group_view.setModel(self._model)
        self._group_view.setSelectionMode(QListView.SelectionMode.SingleSelection)

        self._preset_view = QListView()
        self._preset_view.setModel(self._model)
        self._preset_view.setSelectionMode(QListView.SelectionMode.SingleSelection)

        # toolbars -----------------------------------------------------------
        self._group_tb = self._make_tb(self._new_group, self._remove, self._dup_group)
        self._preset_tb = self._make_tb(
            self._new_preset, self._remove, self._dup_preset
        )

        # layout -------------------------------------------------------------
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(self._group_tb)
        lv.addWidget(self._group_view)
        lv.addWidget(self._preset_tb)
        lv.addWidget(self._preset_view)

        splitter = QSplitter()
        # left-hand panel
        splitter.addWidget(left)

        # center placeholder property table
        self._prop_table = DevicePropertyTable()
        self._prop_table.setRowsCheckable(True)
        self._prop_table.filterDevices(include_pre_init=False, include_read_only=False)
        self._prop_table.valueChanged.connect(self._on_prop_table_changed)
        splitter.addWidget(self._prop_table)

        # right-hand tree view showing the *same* model
        self._tree_view = QTreeView()
        self._tree_view.setModel(self._model)
        self._tree_view.expandAll()  # helpful for the demo
        splitter.addWidget(self._tree_view)

        # column 2 (Value) uses a line-edit when editing a Setting
        self._tree_view.setItemDelegateForColumn(
            2, SettingValueDelegate(self._tree_view)
        )

        splitter.setStretchFactor(1, 1)  # property table expands
        splitter.setStretchFactor(2, 1)  # tree view expands

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(splitter)

        # signals ------------------------------------------------------------
        if sm := self._group_view.selectionModel():
            sm.currentChanged.connect(self._on_group_sel)
        if sm := self._preset_view.selectionModel():
            sm.currentChanged.connect(self._on_preset_sel)
        self._model.dataChanged.connect(self._on_model_data_changed)

    # ------------------------------------------------------------------
    # Public API required by spec
    # ------------------------------------------------------------------

    def setData(self, data: Iterable[ConfigGroup]) -> None:
        """Set the configuration data to be displayed in the editor."""
        self._model.set_groups(data)
        self._prop_table.setValue([])
        # Auto-select first group
        if self._model.rowCount():
            self._group_view.setCurrentIndex(self._model.index(0))
        else:
            self._preset_view.setRootIndex(QModelIndex())
            self._preset_view.clearSelection()
        self.configChanged.emit()

    def data(self) -> Sequence[ConfigGroup]:
        """Return the current configuration data as a list of ConfigGroup."""
        return self._model.data_as_groups()

    # ------------------------------------------------------------------
    # Toolbar action helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_tb(new_fn: Callable, rem_fn: Callable, dup_fn: Callable) -> QToolBar:
        tb = QToolBar()
        tb.addAction("New", new_fn)
        tb.addAction("Remove", rem_fn)
        tb.addAction("Duplicate", dup_fn)
        return tb

    def _current_group_index(self) -> QModelIndex:
        return self._group_view.currentIndex()

    def _current_preset_index(self) -> QModelIndex:
        return self._preset_view.currentIndex()

    # group actions ----------------------------------------------------------

    def _new_group(self) -> None:
        idx = self._model.add_group()
        self._group_view.setCurrentIndex(idx)

    def _dup_group(self) -> None:
        idx = self._current_group_index()
        if idx.isValid():
            self._group_view.setCurrentIndex(self._model.duplicate_group(idx))

    # preset actions ---------------------------------------------------------

    def _new_preset(self) -> None:
        gidx = self._current_group_index()
        if not gidx.isValid():
            return
        pidx = self._model.add_preset(gidx)
        self._preset_view.setCurrentIndex(pidx)

    def _dup_preset(self) -> None:
        pidx = self._current_preset_index()
        if pidx.isValid():
            self._preset_view.setCurrentIndex(self._model.duplicate_preset(pidx))

    # shared --------------------------------------------------------------

    def _remove(self) -> None:
        # Determine which view called us based on focus
        view = self._preset_view if self._preset_view.hasFocus() else self._group_view
        idx = view.currentIndex()
        self._model.remove(idx)

    # selection sync ---------------------------------------------------------

    def _on_group_sel(self, current: QModelIndex, _prev: QModelIndex) -> None:
        self._preset_view.setRootIndex(current)
        if current.isValid() and self._model.rowCount(current):
            self._preset_view.setCurrentIndex(self._model.index(0, 0, current))
        else:
            self._preset_view.clearSelection()

    # ------------------------------------------------------------------
    # Property-table sync
    # ------------------------------------------------------------------

    def _on_preset_sel(self, current: QModelIndex, _prev: QModelIndex) -> None:
        """Populate the DevicePropertyTable whenever the selected preset changes."""
        if not current.isValid():
            # clear table when nothing is selected
            self._prop_table.setValue([])
            return
        node = cast("_Node", current.internalPointer())
        if not node.is_preset:
            self._prop_table.setValue([])
            return
        preset = cast("ConfigPreset", node.payload)
        self._prop_table.setValue(preset.settings)

    def _on_prop_table_changed(self) -> None:
        """Write back edits from the table into the underlying ConfigPreset."""
        idx = self._current_preset_index()
        if not idx.isValid():
            return
        node = cast("_Node", idx.internalPointer())
        if not node.is_preset:
            return
        new_settings = self._prop_table.value()
        self._model.update_preset_settings(idx, new_settings)
        self.configChanged.emit()

    def _on_model_data_changed(
        self,
        topLeft: QModelIndex,
        bottomRight: QModelIndex,
        _roles: list[int] | None = None,
    ) -> None:
        """Refresh DevicePropertyTable if a setting in the current preset was edited."""
        cur_preset = self._current_preset_index()
        if not cur_preset.isValid():
            return

        # We only care about edits to rows that are direct children of the
        # currently-selected preset (i.e. Setting rows).
        if topLeft.parent() != cur_preset:
            return

        # pull updated settings from the model and push to the table
        node = cast("_Node", cur_preset.internalPointer())
        preset = cast("ConfigPreset", node.payload)
        self._prop_table.blockSignals(True)  # avoid feedback loop
        self._prop_table.setValue(preset.settings)
        self._prop_table.blockSignals(False)
