from __future__ import annotations

from typing import Any

from qtpy.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt
from typing_extensions import Self

from pymmcore_widgets.config_presets._model._py_config_model import (
    ConfigGroup,
    ConfigPreset,
    DeviceProperty,
)
from pymmcore_widgets.config_presets._model._q_config_model import NULL_INDEX


class _Node:
    """Generic tree node that wraps a ConfigGroup, ConfigPreset, or Setting."""

    @classmethod
    def create(
        cls,
        payload: ConfigGroup | ConfigPreset | DeviceProperty,
        parent: _Node | None = None,
        recursive: bool = True,
    ) -> Self:
        """Create a new _Node with the given name and payload."""
        if isinstance(payload, DeviceProperty):
            name = payload.display_name()
        else:
            name = payload.name

        node = cls(name, payload, parent)
        if recursive:
            if isinstance(payload, ConfigGroup):
                for p in payload.presets.values():
                    node.children.append(_Node.create(p, node))
            elif isinstance(payload, ConfigPreset):
                for s in payload.settings:
                    node.children.append(_Node.create(s, node))
        return node

    def __init__(
        self,
        name: str,
        payload: ConfigGroup | ConfigPreset | DeviceProperty | None = None,
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

    @property
    def is_setting(self) -> bool:
        return isinstance(self.payload, DeviceProperty)


class _BaseTreeModel(QAbstractItemModel):
    """Thin abstract tree model.

    Sub-classes implement five hooks:

    * _build_tree(self) -> _Node
    * _column_count(self) -> int
    * _data_for(self, node: _Node, column: int, role: int) -> Any
    * _flags_for(self, node: _Node, column: int) -> Qt.ItemFlag
    * _set_data(self, node: _Node, column: int, value: Any, role: int) -> bool.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._root: _Node | None = None  # created lazily

    # ---------- helpers ---------------------------------------------------
    def _ensure_tree(self) -> None:
        if self._root is None:
            self._root = self._build_tree()

    # ---------- Qt plumbing ----------------------------------------------
    def index(
        self,
        row: int,
        column: int = 0,
        parent: QModelIndex = NULL_INDEX,
    ) -> QModelIndex:
        self._ensure_tree()
        pnode = parent.internalPointer() if parent.isValid() else self._root
        if 0 <= row < len(pnode.children):
            return self.createIndex(row, column, pnode.children[row])
        return QModelIndex()

    def parent(self, child: QModelIndex) -> QModelIndex:
        if not child.isValid():
            return QModelIndex()
        node: _Node = child.internalPointer()
        if node.parent is None or node.parent is self._root:
            return QModelIndex()
        return self.createIndex(node.parent.row_in_parent(), 0, node.parent)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        self._ensure_tree()
        if parent.column() > 0:
            return 0
        node = parent.internalPointer() if parent.isValid() else self._root
        return len(node.children)

    def columnCount(self, _parent: QModelIndex = QModelIndex()) -> int:
        return self._column_count()

    def data(self, idx: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not idx.isValid():
            return None
        return self._data_for(idx.internalPointer(), idx.column(), role)

    def flags(self, idx: QModelIndex) -> Qt.ItemFlag:
        if not idx.isValid():
            return Qt.ItemFlag.NoItemFlags
        return self._flags_for(idx.internalPointer(), idx.column())

    def setData(
        self,
        idx: QModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if not idx.isValid():
            return False
        changed = self._set_data(idx.internalPointer(), idx.column(), value, role)
        if changed:
            self.dataChanged.emit(idx, idx, [role])
        return changed

    # ---------- hooks for subclasses -------------------------------------
    def _build_tree(self) -> _Node:  # pragma: no cover
        raise NotImplementedError

    def _column_count(self) -> int:
        return 1

    def _data_for(self, _node: _Node, _col: int, _role: int) -> Any:  # pragma: no cover
        raise NotImplementedError

    def _flags_for(self, _node: _Node, _col: int) -> Qt.ItemFlag:  # pragma: no cover
        raise NotImplementedError

    def _set_data(
        self,
        _node: _Node,
        _col: int,
        _value: Any,
        _role: int,
    ) -> bool:  # pragma: no cover
        return False
