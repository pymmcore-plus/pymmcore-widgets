from __future__ import annotations

from copy import deepcopy
from enum import IntEnum
from typing import TYPE_CHECKING, Any, cast, overload

from qtpy.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt
from qtpy.QtGui import QFont, QIcon
from qtpy.QtWidgets import QMessageBox

from pymmcore_widgets._icons import get_device_icon

from ._py_config_model import (
    ConfigGroup,
    ConfigPreset,
    DeviceProperty,
    get_config_groups,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pymmcore_plus import CMMCorePlus
    from typing_extensions import Self

NULL_INDEX = QModelIndex()


class Col(IntEnum):
    """Column indices for the ConfigTreeModel."""

    Item = 0
    Property = 1
    Value = 2


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
            name = f"{payload.device_label}-{payload.property_name}"
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


class QConfigGroupsModel(QAbstractItemModel):
    """Three-level model: root → groups → presets → settings."""

    @classmethod
    def create_from_core(cls, core: CMMCorePlus) -> Self:
        return cls(get_config_groups(core))

    def __init__(self, groups: Iterable[ConfigGroup] | None = None) -> None:
        super().__init__()
        self._root = _Node("<root>", None)
        if groups:
            self.set_groups(groups)

    # ------------------------------------------------------------------
    # Required Qt model overrides
    # ------------------------------------------------------------------

    # structure helpers -------------------------------------------------------

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        # Only column 0 should have children in tree models
        if parent is not None and parent.isValid() and parent.column() != 0:
            return 0
        return len(self._node_from_index(parent).children)

    def columnCount(self, _parent: QModelIndex | None = None) -> int:
        # In most subclasses, the number of columns is independent of the parent.
        return len(Col)

    def index(
        self, row: int, column: int = 0, parent: QModelIndex | None = None
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

    # data & editing ----------------------------------------------------------

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return the data stored for `role` for the item at `index`."""
        node = self._node_from_index(index)
        if node is self._root:
            return None

        # Qt.ItemDataRole.UserRole => return the original python object
        if role == Qt.ItemDataRole.UserRole:
            return node.payload

        if role == Qt.ItemDataRole.FontRole and index.column() == Col.Item:
            f = QFont()
            if node.is_group:
                f.setBold(True)
            return f

        if role == Qt.ItemDataRole.DecorationRole and index.column() == Col.Item:
            if node.is_group:
                return QIcon.fromTheme("folder")
            if node.is_preset:
                return QIcon.fromTheme("document")
            if node.is_setting:
                setting = cast("DeviceProperty", node.payload)
                if icon := get_device_icon(setting.device_label, color="gray"):
                    return icon.pixmap(16, 16)
                return QIcon.fromTheme("emblem-system")  # pragma: no cover

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            # settings: show Device, Property, Value
            if node.is_setting:
                setting = cast("DeviceProperty", node.payload)
                if index.column() == Col.Item:
                    return setting.device_label
                if index.column() == Col.Property:
                    return setting.property_name
                if index.column() == Col.Value:
                    return setting.value
            # groups / presets: only show name
            elif index.column() == Col.Item:
                return node.name

        return None

    def setData(
        self,
        index: QModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        node = self._node_from_index(index)
        if node is self._root or role != Qt.ItemDataRole.EditRole:
            return False  # pragma: no cover
        if node.is_setting:
            if 0 > index.column() > 3:
                return False  # pragma: no cover
            dev, prop, val = cast("DeviceProperty", node.payload).as_tuple()

            # update node in place  # FIXME ... this is hacky
            args = [dev, prop, val]
            args[index.column()] = str(value)
            node.name = f"{args[0]}-{args[1]}"
            node.payload = new_setting = DeviceProperty(
                device_label=args[0], property_name=args[1], value=args[2]
            )

            # also update the parent preset.settings list reference
            parent_preset = cast("ConfigPreset", node.parent.payload)  # type: ignore
            for i, s in enumerate(parent_preset.settings):
                if (s.device_label, s.property_name) == (dev, prop):
                    parent_preset.settings[i] = new_setting
                    break
        else:
            new_name = str(value).strip()
            if new_name == node.name or not new_name:
                return False

            if self._name_exists(node.parent, new_name):
                QMessageBox.warning(
                    None, "Duplicate name", f"Name '{new_name}' already exists."
                )
                return False

            node.name = new_name
            if isinstance(node.payload, (ConfigGroup, ConfigPreset)):
                node.payload.name = new_name  # keep dataclass in sync

        self.dataChanged.emit(index, index, [role])
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        node = self._node_from_index(index)
        if node is self._root:
            return Qt.ItemFlag.NoItemFlags

        fl = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        if node.is_setting and index.column() == Col.Value:
            fl |= Qt.ItemFlag.ItemIsEditable
        elif not node.is_setting and index.column() == Col.Item:
            fl |= Qt.ItemFlag.ItemIsEditable
        return fl

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return Col(section).name if section < len(Col) else None
        return super().headerData(section, orientation, role)  # pragma: no cover

    # ##################################################################
    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def index_for_group(self, group_name: str) -> QModelIndex:
        """Return the QModelIndex for the group with the given name."""
        for i, node in enumerate(self._root.children):
            if node.is_group and node.name == group_name:
                return self.createIndex(i, 0, node)
        return QModelIndex()

    def index_for_preset(
        self, group: QModelIndex | str, preset_name: str
    ) -> QModelIndex:
        """Return the QModelIndex for the preset with the given name in the group."""
        if isinstance(group, QModelIndex):
            group_index = group
        else:
            group_index = self.index_for_group(group)

        group_node = self._node_from_index(group_index)
        if not isinstance(group_node.payload, ConfigGroup):
            return QModelIndex()

        for i, node in enumerate(group_node.children):
            if node.is_preset and node.name == preset_name:
                return self.createIndex(i, 0, node)
        return QModelIndex()

    # group-level -------------------------------------------------------------

    def add_group(self, base_name: str = "Group") -> QModelIndex:
        """Append a *new* empty group and return its QModelIndex."""
        name = self._unique_child_name(self._root, base_name)
        group = ConfigGroup(name=name)
        row = self.rowCount()
        if self.insertRows(row, 1, NULL_INDEX, _payloads=[group]):
            return self.index(row, 0)
        return QModelIndex()  # pragma: no cover

    def duplicate_group(
        self, idx: QModelIndex, new_name: str | None = None
    ) -> QModelIndex:
        node = self._node_from_index(idx)
        if not isinstance((grp := node.payload), ConfigGroup):
            raise ValueError("Reference index is not a ConfigGroup.")

        new_grp = deepcopy(grp)
        new_grp.name = new_name or self._unique_child_name(self._root, new_grp.name)
        row = idx.row() + 1
        if self.insertRows(row, 1, NULL_INDEX, _payloads=[new_grp]):
            return self.index(row, 0)
        return QModelIndex()  # pragma: no cover

    # preset-level ------------------------------------------------------------

    def add_preset(
        self, group_idx: QModelIndex, base_name: str = "Preset"
    ) -> QModelIndex:
        group_node = self._node_from_index(group_idx)
        if not isinstance(group_node.payload, ConfigGroup):
            raise ValueError("Reference index is not a ConfigGroup.")

        name = self._unique_child_name(group_node, base_name)
        preset = ConfigPreset(name=name)
        row = len(group_node.children)
        if self.insertRows(row, 1, group_idx, _payloads=[preset]):
            return self.index(row, 0, group_idx)
        return QModelIndex()  # pragma: no cover

    def duplicate_preset(
        self, preset_index: QModelIndex, new_name: str | None = None
    ) -> QModelIndex:
        pre_node = self._node_from_index(preset_index)
        if not isinstance((pre := pre_node.payload), ConfigPreset):
            raise ValueError("Reference index is not a ConfigPreset.")

        pre_copy = deepcopy(pre)
        group_idx = preset_index.parent()
        group_node = self._node_from_index(group_idx)
        pre_copy.name = new_name or self._unique_child_name(group_node, pre_copy.name)
        row = preset_index.row() + 1
        if self.insertRows(row, 1, group_idx, _payloads=[pre_copy]):
            return self.index(row, 0, group_idx)
        return QModelIndex()  # pragma: no cover

    # generic remove ----------------------------------------------------------

    def removeRows(
        self,
        row: int,
        count: int,
        parent: QModelIndex = NULL_INDEX,
    ) -> bool:
        """Remove `count` rows starting at `row` from the parent index."""
        parent_node = self._node_from_index(parent)

        # sanity-check the request
        if count <= 0 or row < 0 or row + count > len(parent_node.children):
            return False  # pragma: no cover

        self.beginRemoveRows(parent, row, row + count - 1)

        # drop the slice from the tree
        del parent_node.children[row : row + count]

        # keep the owning dataclass in sync with the new order
        if isinstance((group := parent_node.payload), ConfigGroup):
            group.presets = {
                p.name: p
                for n in parent_node.children
                if isinstance((p := n.payload), ConfigPreset)
            }
        elif isinstance((preset := parent_node.payload), ConfigPreset):
            preset.settings = [
                cast("DeviceProperty", n.payload) for n in parent_node.children
            ]

        self.endRemoveRows()
        return True

    def remove(self, idx: QModelIndex) -> None:
        if idx.isValid():
            self.removeRows(idx.row(), 1, idx.parent())

    # ------------------------------------------------------------------
    # Public mutator helpers
    # ------------------------------------------------------------------

    # TODO: feels like this should be replaced with a more canonical method...
    def update_preset_settings(
        self, preset_idx: QModelIndex, settings: list[DeviceProperty]
    ) -> None:
        """Replace settings for `preset_idx` and update the tree safely."""
        preset_node = self._node_from_index(preset_idx)
        if not isinstance((preset := preset_node.payload), ConfigPreset):
            raise ValueError("Reference index is not a ConfigPreset.")

        # --- remove existing Setting rows ---------------------------------
        old_row_count = len(preset_node.children)
        if old_row_count:
            self.removeRows(0, old_row_count, preset_idx)

        # --- mutate underlying dataclass ----------------------------------
        preset.settings = list(settings)
        if n_rows := len(preset.settings):
            self.beginInsertRows(preset_idx, 0, n_rows - 1)
            for s in preset.settings:
                preset_node.children.append(_Node.create(s, preset_node))
            self.endInsertRows()

    # name uniqueness ---------------------------------------------------------

    @staticmethod
    def _unique_child_name(parent: _Node, base: str, suffix: str = " copy") -> str:
        names = {c.name for c in parent.children}
        if base not in names:
            return base
        # try 'base copy' ... but then resort to 'base copy(n)' if needed
        if (name := f"{base}{suffix}") not in names:
            return name
        n = 1
        while name in names:
            name = f"{base}{suffix} ({n})"
            n += 1
        return name

    @staticmethod
    def _name_exists(parent: _Node | None, name: str) -> bool:
        return parent is not None and any(c.name == name for c in parent.children)

    # external data API -------------------------------------------------------
    #
    # These methods deal with our internal python objects, rather than QModelIndex

    def set_groups(self, groups: Iterable[ConfigGroup]) -> None:
        """Clear model and set new groups."""
        self.beginResetModel()
        self._root.children.clear()
        for g in groups:
            self._root.children.append(_Node.create(g, self._root))
        self.endResetModel()

    def get_groups(self) -> list[ConfigGroup]:
        """Return All ConfigGroups in the model."""
        return deepcopy([cast("ConfigGroup", n.payload) for n in self._root.children])

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

    # insertion ---------------------------------------------------------------

    # TODO: use this instead of _insert_node
    # def insertRows(
    #     self, row: int, count: int, parent: QModelIndex = NULL_INDEX
    # ) -> bool: ...

    def insertRows(
        self,
        row: int,
        count: int,
        parent: QModelIndex = NULL_INDEX,
        *,
        _payloads: list[ConfigGroup | ConfigPreset | DeviceProperty] | None = None,
    ) -> bool:
        """Insert *count* rows at *row* under *parent*.

        *_payloads* is for internal use, and must be a list of exactly *count* data
        objects (ConfigGroup, ConfigPreset, or Setting) that will become the new rows.
        """
        parent_node = self._node_from_index(parent)

        # ---------- basic validation ----------
        if count <= 0 or not (0 <= row <= len(parent_node.children)):
            return False  # bad range  # pragma: no cover
        if _payloads is not None and len(_payloads) != count:
            return False  # mismatch  # pragma: no cover

        # ---------- build default payloads for external callers ----------
        if _payloads is None:
            _payloads = []
            for _ in range(count):
                if isinstance(parent_node.payload, ConfigGroup):
                    # inserting a new ConfigPreset
                    name = self._unique_child_name(parent_node, "Preset")
                    _payloads.append(ConfigPreset(name=name))
                elif isinstance(parent_node.payload, ConfigPreset):
                    raise NotImplementedError(
                        "Inserting a Setting is not supported in this context."
                    )
                    # # inserting a placeholder Setting
                    # idx_placeholder = len(parent_node.children) + len(_payloads)
                    # _payloads.append(
                    #     Setting(
                    #         device_name=f"Device {idx_placeholder}",
                    #         property_name=f"Property {idx_placeholder}",
                    #         property_value="",
                    #     )
                    # )
                else:  # root level → ConfigGroup
                    name = self._unique_child_name(parent_node, "Group")
                    _payloads.append(ConfigGroup(name=name))

        self.beginInsertRows(parent, row, row + count - 1)

        # ---------- modify the tree ----------
        for i, payload in enumerate(_payloads):
            parent_node.children.insert(row + i, _Node.create(payload, parent_node))

        # ---------- keep dataclasses in sync ----------
        if isinstance((grp := parent_node.payload), ConfigGroup):
            presets = list(grp.presets.values())
            for i, payload in enumerate(_payloads):
                presets.insert(row + i, cast("ConfigPreset", payload))
            grp.presets = {p.name: p for p in presets}

        elif isinstance((pre := parent_node.payload), ConfigPreset):
            settings = list(pre.settings)
            for i, payload in enumerate(_payloads):
                settings.insert(row + i, cast("DeviceProperty", payload))
            pre.settings = settings

        self.endInsertRows()
        return True
