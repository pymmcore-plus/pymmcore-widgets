from __future__ import annotations

from contextlib import suppress
from copy import deepcopy
from enum import IntEnum
from typing import TYPE_CHECKING, Any, cast

from pymmcore_plus import CMMCorePlus
from pymmcore_plus.model import ConfigGroup, ConfigPreset, Setting
from qtpy.QtCore import QAbstractItemModel, QModelIndex, Qt
from qtpy.QtGui import QFont, QIcon
from qtpy.QtWidgets import (
    QMessageBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)
from superqt import QIconifyIcon

from pymmcore_widgets._icons import ICONS
from pymmcore_widgets.device_properties._property_widget import PropertyWidget

if TYPE_CHECKING:
    from collections.abc import Iterable


class Col(IntEnum):
    """Column indices for the ConfigTreeModel."""

    Item = 0
    Property = 1
    Value = 2


class _Node:
    """Generic tree node that wraps a ConfigGroup or ConfigPreset."""

    def __init__(
        self,
        name: str,
        payload: ConfigGroup | ConfigPreset | Setting | None = None,
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
        return isinstance(self.payload, Setting)


class QConfigGroupsModel(QAbstractItemModel):
    """Three-level model: root → groups → presets → settings."""

    def __init__(self, groups: Iterable[ConfigGroup] | None = None) -> None:
        super().__init__()
        self._root = _Node("<root>", None)
        if groups:
            self._build_tree(groups)

    # ------------------------------------------------------------------
    # Public helpers used by the widget toolbar actions
    # ------------------------------------------------------------------

    # group-level -------------------------------------------------------------

    def add_group(self, base_name: str = "Group") -> QModelIndex:
        """Append a *new* empty group and return its QModelIndex."""
        name = self._unique_child_name(self._root, base_name)
        group = ConfigGroup(name=name)
        node = _Node(name, group, self._root)
        return self._insert_node(node, self._root, len(self._root.children))

    def duplicate_group(self, idx: QModelIndex) -> QModelIndex:
        if not self._is_group_index(idx):
            return QModelIndex()
        node = cast("_Node", idx.internalPointer())
        new_grp = deepcopy(node.payload)
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
        return len(Col)

    def index(
        self, row: int, column: int = 0, parent: QModelIndex | None = None
    ) -> QModelIndex:
        parent_node = self._node(parent)
        if 0 <= row < len(parent_node.children):
            return self.createIndex(row, column, parent_node.children[row])
        return QModelIndex()

    def parent(self, child: QModelIndex) -> QModelIndex:
        """Returns the parent of the model item with the given index.

        If the item has no parent, an invalid QModelIndex is returned.
        """
        if not child or not child.isValid():
            return QModelIndex()
        parent_node = cast("_Node", child.internalPointer()).parent
        if parent_node is self._root or parent_node is None:
            return QModelIndex()
        return self.createIndex(parent_node.row_in_parent(), 0, parent_node)

    # data & editing ----------------------------------------------------------

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        node = cast("_Node", index.internalPointer())
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
                setting = cast("Setting", node.payload)
                with suppress(Exception):
                    dtype = CMMCorePlus.instance().getDeviceType(setting.device_name)
                    if icon_string := ICONS.get(dtype):
                        return QIconifyIcon(icon_string, color="gray").pixmap(16, 16)

                return QIcon.fromTheme("emblem-system")

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            # settings: show Device, Property, Value
            if node.is_setting:
                setting = cast("Setting", node.payload)
                if index.column() == Col.Item:
                    return setting.device_name
                if index.column() == Col.Property:
                    return setting.property_name
                if index.column() == Col.Value:
                    return setting.property_value
                return None

            # groups / presets: only show name
            elif index.column() == Col.Item:
                return node.name
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        fl = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        node = cast("_Node", index.internalPointer())
        if node.is_setting and index.column() == Col.Value:
            fl |= Qt.ItemFlag.ItemIsEditable
        elif not node.is_setting and index.column() == Col.Item:
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
        if node.is_setting and index.column() == Col.Value:
            setting = cast("Setting", node.payload)
            setting = Setting(
                setting.device_name, setting.property_name, cast("str", value)
            )
            node.payload = setting
            # also update the preset.settings list reference
            # find node.parent.payload (ConfigPreset) and update list element
            parent_preset = cast("ConfigPreset", node.parent.payload)  # type: ignore
            for i, s in enumerate(parent_preset.settings):
                if (
                    s.device_name == setting.device_name
                    and s.property_name == setting.property_name
                ):
                    parent_preset.settings[i] = setting
                    break
            self.dataChanged.emit(index, index, [role])
            return True
        new_name = cast("str", value)
        if new_name == node.name:
            return True
        if not new_name:
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
                # add one child per Setting
                for s in p.settings:
                    snode = _Node(s.device_name, s, pnode)
                    pnode.children.append(snode)

    # ------------------------------------------------------------------
    # Public mutator helpers
    # ------------------------------------------------------------------

    def update_preset_settings(
        self, preset_idx: QModelIndex, settings: list[Setting]
    ) -> None:
        """Replace <preset> settings and update the tree safely.

        We remove old Setting rows with beginRemoveRows/endRemoveRows,
        then insert the new ones.  This guarantees attached views drop any
        QModelIndex that referenced the old child nodes (avoiding the crash
        seen when switching presets).
        """
        if not self._is_preset_index(preset_idx):
            return

        preset_node = cast("_Node", preset_idx.internalPointer())
        preset: ConfigPreset = cast("ConfigPreset", preset_node.payload)

        # --- mutate underlying dataclass ----------------------------------
        preset.settings = list(settings)

        # --- remove existing Setting rows ---------------------------------
        old_row_count = len(preset_node.children)
        if old_row_count:
            self.beginRemoveRows(preset_idx, 0, old_row_count - 1)
            preset_node.children.clear()
            self.endRemoveRows()

        # --- insert new Setting rows --------------------------------------
        new_row_count = len(settings)
        if new_row_count:
            self.beginInsertRows(preset_idx, 0, new_row_count - 1)
            for s in settings:
                preset_node.children.append(_Node(s.device_name, s, preset_node))
            self.endInsertRows()

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
        return super().headerData(section, orientation, role)

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
        return self.createIndex(row, 0, node)

    def _index_from_node(self, node: _Node) -> QModelIndex:
        if node is self._root:
            return QModelIndex()
        return self.createIndex(node.row_in_parent(), 0, node)

    # external data API -------------------------------------------------------

    def set_groups(self, groups: Iterable[ConfigGroup]) -> None:
        self.beginResetModel()
        self._build_tree(groups)
        self.endResetModel()

    def data_as_groups(self) -> list[ConfigGroup]:
        """Return a *deep copy* of current configuration as dataclasses."""
        return deepcopy([cast("ConfigGroup", n.payload) for n in self._root.children])


# -----------------------------------------------------------------------------
# Property table placeholder (unchanged)
# -----------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Delegate: always use QLineEdit for a Setting's value cell (column 2)
# ---------------------------------------------------------------------------
class SettingValueDelegate(QStyledItemDelegate):
    """Item delegate that uses a PropertyWidget for editing PropertySetting values."""

    def createEditor(
        self, parent: QWidget | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget | None:
        node = cast("_Node", index.internalPointer())
        if (
            not (model := index.model())
            or (index.column() != Col.Value)
            or not node.is_setting
        ):
            return super().createEditor(parent, option, index)

        row = index.row()
        device = model.data(index.sibling(row, Col.Item))
        prop = model.data(index.sibling(row, Col.Property))
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
