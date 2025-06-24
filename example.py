from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Callable, cast

from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import ConfigGroup, ConfigPreset, Setting
from PyQt6.QtCore import QAbstractItemModel, QModelIndex, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QListView,
    QMessageBox,
    QSplitter,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets.device_properties import DevicePropertyTable

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


# -----------------------------------------------------------------------------
# Internal tree node helper
# -----------------------------------------------------------------------------


class _Node:
    """Generic tree node that wraps a ConfigGroup or ConfigPreset."""

    def __init__(
        self,
        name: str,
        payload: ConfigGroup | ConfigPreset | None = None,
        parent: _Node | None = None,
    ) -> None:
        self.name = name
        self.payload = payload
        self.parent = parent
        self.children: list[_Node] = []

    # convenience ------------------------------------------------------------

    def row_in_parent(self) -> int:
        return -1 if self.parent is None else self.parent.children.index(self)

    # type helpers -----------------------------------------------------------

    @property
    def is_group(self) -> bool:
        return isinstance(self.payload, ConfigGroup)

    @property
    def is_preset(self) -> bool:
        return isinstance(self.payload, ConfigPreset)


# -----------------------------------------------------------------------------
# ConfigTreeModel
# -----------------------------------------------------------------------------


class ConfigTreeModel(QAbstractItemModel):
    """Two-level model: root → groups → presets."""

    # emitted when underlying data change in any way
    dataChangedExternally = pyqtSignal()

    def __init__(self, groups: Iterable[ConfigGroup] | None = None) -> None:
        super().__init__()
        self._root = _Node("<root>")
        if groups:
            self._build_tree(groups)

    # ------------------------------------------------------------------
    # Public helpers used by the widget toolbar actions
    # ------------------------------------------------------------------

    # group-level -------------------------------------------------------------

    def add_group(self, base_name: str = "Group") -> QModelIndex:
        """Append a *new* empty group and return its QModelIndex."""
        name = self._unique_child_name(self._root, base_name)
        group = ConfigGroup(name)
        node = _Node(name, group, self._root)
        return self._insert_node(node, self._root, len(self._root.children))

    def duplicate_group(self, idx: QModelIndex) -> QModelIndex:
        if not self._is_group_index(idx):
            return QModelIndex()
        orig = cast("_Node", idx.internalPointer())
        new_grp = deepcopy(orig.payload)
        assert isinstance(new_grp, ConfigGroup)
        new_grp.name = self._unique_child_name(self._root, new_grp.name)
        node = _Node(new_grp.name, new_grp, self._root)
        # duplicate presets
        for p in new_grp.presets.values():
            child_node = _Node(p.name, p, node)
            node.children.append(child_node)
        return self._insert_node(node, self._root, idx.row() + 1)

    # preset-level ------------------------------------------------------------

    def add_preset(
        self, group_idx: QModelIndex, base_name: str = "Preset"
    ) -> QModelIndex:
        if not self._is_group_index(group_idx):
            return QModelIndex()
        parent_node = cast("_Node", group_idx.internalPointer())
        name = self._unique_child_name(parent_node, base_name)
        preset = ConfigPreset(name)
        node = _Node(name, preset, parent_node)
        return self._insert_node(node, parent_node, len(parent_node.children))

    def duplicate_preset(self, idx: QModelIndex) -> QModelIndex:
        if not self._is_preset_index(idx):
            return QModelIndex()
        parent_node = cast("_Node", idx.parent().internalPointer())
        orig = cast("_Node", idx.internalPointer())
        new_preset = deepcopy(orig.payload)
        assert isinstance(new_preset, ConfigPreset)
        new_preset.name = self._unique_child_name(parent_node, new_preset.name)
        node = _Node(new_preset.name, new_preset, parent_node)
        return self._insert_node(node, parent_node, idx.row() + 1)

    # generic remove ----------------------------------------------------------

    def remove(self, idx: QModelIndex) -> None:
        if not idx.isValid():
            return
        node = cast("_Node", idx.internalPointer())
        parent_node = node.parent
        if parent_node is None:
            return
        self.beginRemoveRows(idx.parent(), idx.row(), idx.row())
        parent_node.children.pop(idx.row())
        self.endRemoveRows()
        self.dataChangedExternally.emit()

    # ------------------------------------------------------------------
    # Required Qt model overrides
    # ------------------------------------------------------------------

    # structure helpers -------------------------------------------------------

    def _node(self, index: QModelIndex | None) -> _Node:
        return (
            cast("_Node", index.internalPointer())
            if index and index.isValid()
            else self._root
        )

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return len(self._node(parent).children)

    def columnCount(self, _parent: QModelIndex | None = None) -> int:
        return 1

    def index(
        self, row: int, column: int, parent: QModelIndex | None = None
    ) -> QModelIndex:
        if column != 0:
            return QModelIndex()
        parent_node = self._node(parent)
        if 0 <= row < len(parent_node.children):
            return self.createIndex(row, 0, parent_node.children[row])
        return QModelIndex()

    def parent(self, child: QModelIndex) -> QModelIndex:  # type: ignore[override]
        """Returns the parent of the model item with the given index.

        If the item has no parent, an invalid QModelIndex is returned.
        """
        if not child.isValid():
            return QModelIndex()
        parent_node = cast("_Node", child.internalPointer()).parent
        if parent_node is self._root or parent_node is None:
            return QModelIndex()
        return self.createIndex(parent_node.row_in_parent(), 0, parent_node)

    # data & editing ----------------------------------------------------------

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or role not in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.EditRole,
        ):
            return None
        return cast("_Node", index.internalPointer()).name

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        fl = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        # allow renaming
        fl |= Qt.ItemFlag.ItemIsEditable
        return fl

    def setData(
        self,
        index: QModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        node = cast("_Node", index.internalPointer())
        new_name = cast("str", value)
        if new_name == node.name:
            return True
        if self._name_exists(node.parent, new_name):
            self._show_dup_name_error(new_name)
            return False
        node.name = new_name
        if node.payload is not None:
            node.payload.name = new_name  # keep dataclass in sync
        self.dataChanged.emit(index, index, [role])
        self.dataChangedExternally.emit()
        return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_tree(self, groups: Iterable[ConfigGroup]) -> None:
        self._root.children.clear()
        for g in groups:
            gnode = _Node(g.name, g, self._root)
            self._root.children.append(gnode)
            for p in g.presets.values():
                pnode = _Node(p.name, p, gnode)
                gnode.children.append(pnode)

    # name uniqueness ---------------------------------------------------------

    @staticmethod
    def _unique_child_name(parent: _Node, base: str) -> str:
        names = {c.name for c in parent.children}
        if base not in names:
            return base
        i = 1
        while f"{base} {i}" in names:
            i += 1
        return f"{base} {i}"

    @staticmethod
    def _name_exists(parent: _Node | None, name: str) -> bool:
        return parent is not None and any(c.name == name for c in parent.children)

    @staticmethod
    def _show_dup_name_error(name: str) -> None:
        QMessageBox.warning(None, "Duplicate name", f"Name '{name}' already exists.")

    # convenience guards ------------------------------------------------------

    @staticmethod
    def _is_group_index(idx: QModelIndex) -> bool:
        return idx.isValid() and cast("_Node", idx.internalPointer()).is_group

    @staticmethod
    def _is_preset_index(idx: QModelIndex) -> bool:
        return idx.isValid() and cast("_Node", idx.internalPointer()).is_preset

    # insertion ---------------------------------------------------------------

    def _insert_node(self, node: _Node, parent_node: _Node, row: int) -> QModelIndex:
        self.beginInsertRows(self._index_from_node(parent_node), row, row)
        parent_node.children.insert(row, node)
        self.endInsertRows()
        self.dataChangedExternally.emit()
        return self.createIndex(row, 0, node)

    def _index_from_node(self, node: _Node) -> QModelIndex:
        if node is self._root:
            return QModelIndex()
        return self.createIndex(node.row_in_parent(), 0, node)

    # external data API -------------------------------------------------------

    def set_data(self, groups: Iterable[ConfigGroup]) -> None:
        self.beginResetModel()
        self._build_tree(groups)
        self.endResetModel()
        self.dataChangedExternally.emit()

    def data_as_groups(self) -> list[ConfigGroup]:
        """Return a *deep copy* of current configuration as dataclasses."""
        return deepcopy([cast("ConfigGroup", n.payload) for n in self._root.children])


# -----------------------------------------------------------------------------
# Property table placeholder (unchanged)
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# High-level editor widget
# -----------------------------------------------------------------------------


class ConfigEditor(QWidget):
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

        splitter.setStretchFactor(1, 1)  # property table expands
        splitter.setStretchFactor(2, 1)  # tree view expands

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(splitter)

        # signals ------------------------------------------------------------
        self._group_view.selectionModel().currentChanged.connect(self._on_group_sel)
        self._preset_view.selectionModel().currentChanged.connect(self._on_preset_sel)
        self._model.dataChangedExternally.connect(self.configChanged)

    # ------------------------------------------------------------------
    # Public API required by spec
    # ------------------------------------------------------------------

    def setData(self, data: Iterable[ConfigGroup]) -> None:
        self._model.set_data(data)
        self._group_view.setCurrentIndex(QModelIndex())
        self._preset_view.setRootIndex(QModelIndex())
        self._prop_table.setValue([])
        self.configChanged.emit()

    def data(self) -> Sequence[ConfigGroup]:
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
    # Property‑table sync
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
        preset = cast("ConfigPreset", node.payload)
        preset.settings = self._prop_table.value()
        # notify observers that model content changed
        self._model.dataChangedExternally.emit()
        self.configChanged.emit()


# -----------------------------------------------------------------------------
# Demo
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    core = CMMCorePlus()
    core.loadSystemConfiguration()

    # sample config ----------------------------------------------------------
    cam_grp = ConfigGroup(
        "Camera",
        presets={
            "Cy5": ConfigPreset(
                name="Cy5",
                settings=[
                    Setting("Dichroic", "Label", "400DCLP"),
                    Setting("Emission", "Label", "Chroma-HQ700"),
                    Setting("Excitation", "Label", "Chroma-HQ570"),
                    Setting("Core", "Shutter", "White Light Shutter"),
                ],
            ),
            "FITC": ConfigPreset(
                name="FITC",
                settings=[
                    Setting("Dichroic", "Label", "400DCLP"),
                    Setting("Emission", "Label", "Chroma-HQ620"),
                    Setting("Excitation", "Label", "Chroma-D360"),
                    Setting("Core", "Shutter", "White Light Shutter"),
                ],
            ),
        },
    )
    obj_grp = ConfigGroup("Objective")

    w = ConfigEditor()
    w.setData([cam_grp, obj_grp])
    w.resize(800, 600)
    w.show()
    sys.exit(app.exec())
