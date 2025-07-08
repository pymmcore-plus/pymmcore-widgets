from __future__ import annotations

from typing import overload

from qtpy.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt
from typing_extensions import Self

from ._py_config_model import ConfigGroup, ConfigPreset, Device, DevicePropertySetting

NULL_INDEX = QModelIndex()


class _Node:
    """Generic tree node that wraps a ConfigGroup, ConfigPreset, or Setting."""

    __slots__ = (
        "check_state",
        "children",
        "name",
        "parent",
        "payload",
    )

    @classmethod
    def create(
        cls,
        payload: ConfigGroup | ConfigPreset | DevicePropertySetting | Device,
        parent: _Node | None = None,
        recursive: bool = True,
    ) -> Self:
        """Create a new _Node with the given name and payload."""
        if isinstance(payload, DevicePropertySetting):
            name = payload.property_name
        elif isinstance(payload, Device):
            name = payload.label
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
            elif isinstance(payload, Device):
                for prop in payload.properties:
                    node.children.append(_Node.create(prop, node))
        return node

    def __init__(
        self,
        name: str,
        payload: ConfigGroup
        | ConfigPreset
        | DevicePropertySetting
        | Device
        | None = None,
        parent: _Node | None = None,
    ) -> None:
        self.name = name
        self.payload = payload
        self.parent = parent
        self.check_state = Qt.CheckState.Unchecked
        self.children: list[_Node] = []

    # convenience ------------------------------------------------------------

    @property
    def siblings(self) -> list[_Node]:
        if self.parent is None:
            return []  # pragma: no cover
        return [x for x in self.parent.children if x is not self]

    def num_children(self) -> int:
        return len(self.children)

    def row_in_parent(self) -> int:
        if self.parent is None:
            return -1  # pragma: no cover
        try:
            return self.parent.children.index(self)
        except ValueError:  # pragma: no cover
            return -1

    # type helpers -----------------------------------------------------------

    @property
    def is_group(self) -> bool:
        return isinstance(self.payload, ConfigGroup)

    @property
    def is_preset(self) -> bool:
        return isinstance(self.payload, ConfigPreset)

    @property
    def is_setting(self) -> bool:
        return isinstance(self.payload, DevicePropertySetting)

    @property
    def is_device(self) -> bool:
        return isinstance(self.payload, Device)


class _BaseTreeModel(QAbstractItemModel):
    """Thin abstract tree model.

    Sub-classes should implement at least the following methods:

    * columnCount(self, parent: QModelIndex) -> int: ...
    * data(self, index: QModelIndex, role: int = ...) -> Any:
    * setData(self, index: QModelIndex, value: Any, role: int) -> bool:
    * flags(self, index: QModelIndex) -> Qt.ItemFlag:
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._root = _Node("<root>", None)

    def _node_from_index(self, index: QModelIndex | None) -> _Node:
        if (
            index
            and index.isValid()
            and isinstance((node := index.internalPointer()), _Node)
        ):
            # return the node if index is valid
            return node
        # otherwise return the root node
        return self._root

    # # ---------- Qt plumbing ----------------------------------------------

    def rowCount(self, parent: QModelIndex = NULL_INDEX) -> int:
        # Only column 0 should have children in tree models
        if parent is not None and parent.isValid() and parent.column() != 0:
            return 0
        return self._node_from_index(parent).num_children()

    def index(
        self, row: int, column: int = 0, parent: QModelIndex = NULL_INDEX
    ) -> QModelIndex:
        """Return the index of the item specified by row, column and parent index."""
        parent_node = self._node_from_index(parent)
        if 0 <= row < len(parent_node.children):
            return self.createIndex(row, column, parent_node.children[row])
        return QModelIndex()  # pragma: no cover

    @overload
    def parent(self, child: QModelIndex) -> QModelIndex: ...
    @overload
    def parent(self) -> QObject | None: ...
    def parent(self, child: QModelIndex | None = None) -> QModelIndex | QObject | None:
        """Return the parent of the model item with the given index.

        If the item has no parent, an invalid QModelIndex is returned.
        """
        if child is None:  # pragma: no cover
            return None
        node = self._node_from_index(child)
        if (
            node is self._root
            or not (parent_node := node.parent)
            or parent_node is self._root
        ):
            return QModelIndex()

        # A common convention used in models that expose tree data structures is that
        # only items in the first column have children.
        return self.createIndex(parent_node.row_in_parent(), 0, parent_node)
