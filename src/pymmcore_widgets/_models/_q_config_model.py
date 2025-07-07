from __future__ import annotations

import warnings
from copy import deepcopy
from enum import IntEnum
from typing import TYPE_CHECKING, Any, cast

from qtpy.QtCore import QModelIndex, Qt
from qtpy.QtGui import QFont, QIcon
from qtpy.QtWidgets import QMessageBox, QWidget
from superqt import QIconifyIcon

from pymmcore_widgets._icons import StandardIcon

from ._base_tree_model import _BaseTreeModel, _Node
from ._core_functions import get_config_groups
from ._py_config_model import ConfigGroup, ConfigPreset, DevicePropertySetting

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


class QConfigGroupsModel(_BaseTreeModel):
    """Three-level model: root → groups → presets → settings."""

    @classmethod
    def create_from_core(cls, core: CMMCorePlus) -> Self:
        return cls(get_config_groups(core))

    def __init__(self, groups: Iterable[ConfigGroup] | None = None) -> None:
        super().__init__()
        if groups:
            self.set_groups(groups)

    # ------------------------------------------------------------------
    # Required Qt model overrides
    # ------------------------------------------------------------------

    def columnCount(self, _parent: QModelIndex | None = None) -> int:
        # In most subclasses, the number of columns is independent of the parent.
        return len(Col)

    # data & editing ----------------------------------------------------------

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return the data stored for `role` for the item at `index`."""
        node = self._node_from_index(index)
        if node is self._root:
            return None

        # Qt.ItemDataRole.UserRole => return the original python object
        if role == Qt.ItemDataRole.UserRole:
            return node.payload

        col = index.column()
        if role == Qt.ItemDataRole.FontRole and col == Col.Item:
            f = QFont()
            if node.is_group:
                f.setBold(True)
            return f

        if role == Qt.ItemDataRole.DecorationRole and col == Col.Item:
            if node.is_group:
                grp = cast("ConfigGroup", node.payload)
                if grp.is_channel_group:
                    return StandardIcon.CHANNEL_GROUP.icon().pixmap(16, 16)
                if grp.is_system_group:
                    return StandardIcon.SYSTEM_GROUP.icon().pixmap(16, 16)
                return StandardIcon.CONFIG_GROUP.icon().pixmap(16, 16)
            if node.is_preset:
                preset = cast("ConfigPreset", node.payload)
                if preset.is_system_startup:
                    return StandardIcon.STARTUP.icon().pixmap(16, 16)
                if preset.is_system_shutdown:
                    return StandardIcon.SHUTDOWN.icon().pixmap(16, 16)
                return StandardIcon.CONFIG_PRESET.icon().pixmap(16, 16)
            if node.is_setting:
                setting = cast("DevicePropertySetting", node.payload)
                if icon_key := setting.iconify_key:
                    return QIconifyIcon(icon_key).pixmap(16, 16)
                return QIcon.fromTheme("emblem-system")  # pragma: no cover

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            # settings: show Device, Property, Value
            if node.is_setting:
                setting = cast("DevicePropertySetting", node.payload)
                if col == Col.Item:
                    return setting.device_label
                if col == Col.Property:
                    return setting.property_name
                if col == Col.Value:
                    return setting.value
            # groups / presets: only show name
            elif col == Col.Item:
                return node.name

        return None

    def setData(
        self,
        index: QModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        """Set data for the given index."""
        node = self._node_from_index(index)
        if node is self._root or role != Qt.ItemDataRole.EditRole:
            return False  # pragma: no cover
        if node.is_setting:
            if 0 > index.column() > 3:
                return False  # pragma: no cover
            dev, prop, val = cast("DevicePropertySetting", node.payload).as_tuple()

            # update node in place  # FIXME ... this is hacky
            args = [dev, prop, val]
            args[index.column()] = str(value)
            node.name = f"{args[0]}-{args[1]}"
            node.payload = new_setting = DevicePropertySetting(
                device=args[0], property_name=args[1], value=args[2]
            )

            # also update the parent preset.settings list reference
            parent_preset = cast("ConfigPreset", node.parent.payload)  # type: ignore
            for i, s in enumerate(parent_preset.settings):
                if s.as_tuple()[0:2] == (dev, prop):
                    parent_preset.settings[i] = new_setting
                    break
        else:
            new_name = str(value).strip()
            if new_name == node.name or not new_name:
                return False

            if self._name_exists(node.parent, new_name):
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
        if isinstance((grp := node.payload), ConfigGroup) and grp.is_system_group:
            # system group name cannot be changed
            return fl
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

    def add_group(self, base_name: str = "New Group") -> QModelIndex:
        """Append a *new* empty group and return its QModelIndex."""
        name = self._unique_child_name(self._root, base_name, suffix="")
        group = ConfigGroup(name=name)
        row = self.rowCount()
        if self.insertRows(row, 1, QModelIndex(), _payloads=[group]):
            return self.index(row, 0)
        return QModelIndex()  # pragma: no cover

    def duplicate_group(
        self, idx: QModelIndex, new_name: str | None = None
    ) -> QModelIndex:
        node = self._node_from_index(idx)
        if not isinstance((grp := node.payload), ConfigGroup):
            raise ValueError("Reference index is not a ConfigGroup.")

        new_grp = deepcopy(grp)
        new_grp.is_channel_group = False  # this never gets duplicated
        new_grp.name = new_name or self._unique_child_name(self._root, new_grp.name)
        row = idx.row() + 1
        if self.insertRows(row, 1, QModelIndex(), _payloads=[new_grp]):
            return self.index(row, 0)
        return QModelIndex()  # pragma: no cover

    # preset-level ------------------------------------------------------------

    def add_preset(
        self, group_idx: QModelIndex, base_name: str = "New Preset"
    ) -> QModelIndex:
        group_node = self._node_from_index(group_idx)
        if not isinstance(group_node.payload, ConfigGroup):
            raise ValueError("Reference index is not a ConfigGroup.")

        name = self._unique_child_name(group_node, base_name, suffix="")
        preset = ConfigPreset(name=name, parent=group_node.payload)
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

    def set_channel_group(self, group_idx: QModelIndex | None) -> None:
        """Set the given group as the channel group.

        If *group_idx* is None or invalid, unset the current channel group.
        """
        changed = False
        if group_idx is None or not group_idx.isValid():
            # unset existing channel group
            for group_node in self._root.children:
                if isinstance((grp := group_node.payload), ConfigGroup):
                    if grp.is_channel_group:
                        changed = True
                    grp.is_channel_group = False
        else:
            group_node = self._node_from_index(group_idx)
            if not isinstance(
                (grp := group_node.payload), ConfigGroup
            ):  # pragma: no cover
                warnings.warn("Reference index is not a ConfigGroup.", stacklevel=2)
                return
            if grp.is_channel_group:
                return  # no change

            grp.is_channel_group = True
            # unset all other groups
            for sibling in group_node.siblings:
                if isinstance((sibling_grp := sibling.payload), ConfigGroup):
                    if sibling_grp.is_channel_group:
                        changed = True
                    sibling_grp.is_channel_group = False

            changed = True

        if changed:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(self.rowCount() - 1, 0),
                [Qt.ItemDataRole.DecorationRole],
            )

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
                cast("DevicePropertySetting", n.payload) for n in parent_node.children
            ]

        self.endRemoveRows()
        return True

    # TODO: probably remove the QWidget logic from here
    def remove(
        self,
        idx: QModelIndex,
        *,
        ask_confirmation: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        if idx.isValid():
            if ask_confirmation:
                item_name = idx.data(Qt.ItemDataRole.DisplayRole)
                item_type = type(idx.data(Qt.ItemDataRole.UserRole))
                type_name = item_type.__name__.replace(("Config"), "Config ")
                msg = QMessageBox.question(
                    parent,
                    "Confirm Deletion",
                    f"Are you sure you want to delete {type_name} {item_name!r}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if msg != QMessageBox.StandardButton.Yes:
                    return
            self.removeRows(idx.row(), 1, idx.parent())

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def is_name_change_valid(self, index: QModelIndex, new_name: str) -> str | None:
        """Validate a name change.

        Returns
        -------
        str | None
            error_message: Error message if invalid, None if valid
        """
        node = self._node_from_index(index)
        if node is self._root:
            return "Cannot rename root node"

        new_name = new_name.strip()
        if not new_name:
            return "Name cannot be empty"

        if new_name == node.name:
            return None  # No change

        if self._name_exists(node.parent, new_name):
            return f"Name '{new_name}' already exists"

        return None

    # ------------------------------------------------------------------
    # Public mutator helpers
    # ------------------------------------------------------------------

    # TODO: feels like this should be replaced with a more canonical method...
    def update_preset_settings(
        self, preset_idx: QModelIndex, settings: list[DevicePropertySetting]
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

    def update_preset_properties(
        self, preset_idx: QModelIndex, settings: Iterable[tuple[str, str]]
    ) -> None:
        """Update the preset to only include properties that match the given keys.

        Missing properties will be added as placeholder settings with empty values.
        """
        preset_node = self._node_from_index(preset_idx)
        if not isinstance((preset := preset_node.payload), ConfigPreset):
            raise ValueError("Reference index is not a ConfigPreset.")

        setting_keys = set(settings)

        # Create a dict of existing settings keyed by (device, property_name)
        existing_settings = {s.key(): s for s in preset.settings}

        # Build the final list of settings
        final_settings = []

        for key in setting_keys:
            if key in existing_settings:
                final_settings.append(existing_settings[key])
            else:
                final_settings.append(
                    DevicePropertySetting(device=key[0], property_name=key[1])
                )

        # Use the existing method to update the preset with the final settings
        self.update_preset_settings(preset_idx, final_settings)

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
        _payloads: list[ConfigGroup | ConfigPreset | DevicePropertySetting]
        | None = None,
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
                if isinstance((grp := parent_node.payload), ConfigGroup):
                    # inserting a new ConfigPreset
                    name = self._unique_child_name(parent_node, "Preset")
                    _payloads.append(ConfigPreset(name=name, parent=grp))
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
                settings.insert(row + i, cast("DevicePropertySetting", payload))
            pre.settings = settings

        self.endInsertRows()
        return True
