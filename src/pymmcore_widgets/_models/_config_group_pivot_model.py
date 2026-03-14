from __future__ import annotations

from typing import TYPE_CHECKING, Any

from qtpy.QtCore import QAbstractTableModel, QModelIndex, QSize, Qt

from pymmcore_widgets._icons import StandardIcon

from ._py_config_model import ConfigGroup, ConfigPreset, DevicePropertySetting
from ._q_config_model import QConfigGroupsModel

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget


class ConfigGroupPivotModel(QAbstractTableModel):
    """Pivot a single ConfigGroup into rows=Device/Property, cols=Presets."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._src: QConfigGroupsModel | None = None
        self._gidx: QModelIndex | None = None
        self._presets: list[ConfigPreset] = []
        self._rows: list[tuple[str, str]] = []  # (device_name, property_name)
        self._data: dict[tuple[int, int], DevicePropertySetting] = {}
        self._in_set_data = False  # guard to prevent rebuild during setData

    def sourceModel(self) -> QConfigGroupsModel | None:
        """Return the source model."""
        return self._src

    def setSourceModel(self, src_model: QConfigGroupsModel) -> None:
        """Set the source model and rebuild the matrix."""
        if not isinstance(src_model, QConfigGroupsModel):  # pragma: no cover
            raise TypeError("Source model must be an instance of QConfigGroupsModel.")
        self._src = src_model

        # -> keep the pivot up-to-date whenever the tree model changes
        src_model.modelReset.connect(self._rebuild)
        src_model.rowsInserted.connect(self._rebuild)
        src_model.rowsRemoved.connect(self._rebuild)
        src_model.dataChanged.connect(self._on_source_data_changed)

    def setGroup(self, group_name_or_index: str | QModelIndex) -> None:
        """Set the group index to pivot and rebuild the matrix."""
        if self._src is None:  # pragma: no cover
            raise ValueError("Source model is not set. Call setSourceModel first.")
        if not isinstance(group_name_or_index, QModelIndex):
            self._gidx = self._src.index_for_group(group_name_or_index)
        else:
            if group_name_or_index.isValid():  # pragma: no cover
                self._gidx = group_name_or_index
        self._rebuild()

    def setData(
        self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        """Set data for a specific cell in the pivot table."""
        if (
            role != Qt.ItemDataRole.EditRole
            or not index.isValid()
            or self._src is None
            or self._gidx is None
            or (row := index.row()) >= len(self._rows)
            or (col := index.column()) >= len(self._presets)
        ):
            return False  # pragma: no cover

        # Reject writes to empty cells (no existing setting)
        if (row, col) not in self._data:
            return False  # pragma: no cover

        setting = self._data[(row, col)]
        new_value = str(value)
        if setting.value == new_value:
            return True  # no change

        # Mutate in-place (the setting object is shared with the source model)
        setting.value = new_value

        # Notify the source model so other views update, but guard against
        # the source's dataChanged triggering a full pivot rebuild.
        self._in_set_data = True
        try:
            preset = self._presets[col]
            preset_idx = self._src.index_for_preset(self._gidx, preset.name)
            if preset_idx.isValid():
                src = self._src
                for i in range(src.rowCount(preset_idx)):
                    src_idx = src.index(i, 2, preset_idx)
                    if src_idx.data(Qt.ItemDataRole.UserRole) is setting:
                        src.setData(src_idx, new_value)
                        break
        finally:
            self._in_set_data = False

        self.dataChanged.emit(index, index, [])
        return True

    # ---------------------------------------------------------------- build --

    def _rebuild(self) -> None:  # slot signature is flexible
        self.beginResetModel()
        self._presets.clear()
        self._rows.clear()
        self._data.clear()
        if self._gidx is None:  # nothing selected yet
            self.endResetModel()
            return  # pragma: no cover

        try:
            group = self._gidx.data(Qt.ItemDataRole.UserRole)
            if not isinstance(group, ConfigGroup):
                return  # pragma: no cover
            self._presets = list(group.presets.values())
            keys = (setting.key() for p in self._presets for setting in p.settings)
            self._rows = sorted(dict.fromkeys(keys, None))

            for col, preset in enumerate(self._presets):
                for row, (device, prop) in enumerate(self._rows):
                    for s in preset.settings:
                        if s.key() == (device, prop):
                            self._data[(row, col)] = s
                            break
        finally:
            self.endResetModel()

    def _empty_setting_for_row(self, row: int) -> DevicePropertySetting:
        """Create an empty setting for the given row, preserving metadata."""
        # Try to copy metadata from an existing setting in another column
        for col in range(len(self._presets)):
            if (row, col) in self._data:
                src = self._data[(row, col)]
                return src.model_copy(update={"value": src.default_value})
        dev, prop = self._rows[row]
        return DevicePropertySetting(device=dev, property_name=prop)

    # --------------------------------------------------------- Qt overrides --

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._presets)

    def headerData(
        self,
        section: int,
        orient: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            if orient == Qt.Orientation.Horizontal and section < len(self._presets):
                return self._presets[section].name
            if orient == Qt.Orientation.Vertical and section < len(self._rows):
                return "-".join(self._rows[section])
        elif role == Qt.ItemDataRole.DecorationRole and section < len(self._rows):
            if orient == Qt.Orientation.Vertical:
                try:
                    dev, _prop = self._rows[section]
                except IndexError:  # pragma: no cover
                    return None
                if icon := StandardIcon.for_device_type(dev):
                    return icon.icon().pixmap(QSize(16, 16))
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():  # pragma: no cover
            return None

        setting = self._data.get((index.row(), index.column()))
        if setting is None:
            return None

        if role == Qt.ItemDataRole.UserRole:
            return setting

        if role in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.EditRole,
        ):
            return setting.value if setting else None
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():  # pragma: no cover
            return Qt.ItemFlag.NoItemFlags
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self._data.get((index.row(), index.column())) is not None:
            base |= Qt.ItemFlag.ItemIsEditable
        return base

    def add_setting_at(self, row: int, col: int) -> bool:
        """Add a placeholder setting at (row, col) if the cell is empty."""
        if (
            self._src is None
            or self._gidx is None
            or row >= len(self._rows)
            or col >= len(self._presets)
            or (row, col) in self._data
        ):
            return False  # pragma: no cover

        preset = self._presets[col]
        new_setting = self._empty_setting_for_row(row)

        preset_settings = list(preset.settings)
        preset_settings.append(new_setting)

        preset_idx = self._src.index_for_preset(self._gidx, preset.name)
        if preset_idx.isValid():
            self._src.update_preset_settings(preset_idx, preset_settings)
            return True
        return False  # pragma: no cover

    def remove_setting_at(self, row: int, col: int) -> bool:
        """Remove the setting at (row, col) if it exists."""
        if (
            self._src is None
            or self._gidx is None
            or row >= len(self._rows)
            or col >= len(self._presets)
            or (row, col) not in self._data
        ):
            return False

        preset = self._presets[col]
        target_key = self._rows[row]
        filtered = [s for s in preset.settings if s.key() != target_key]

        preset_idx = self._src.index_for_preset(self._gidx, preset.name)
        if preset_idx.isValid():
            self._src.update_preset_settings(preset_idx, filtered)
            return True
        return False  # pragma: no cover

    def get_source_index_for_column(self, column: int) -> QModelIndex:
        """Get the source index for a given column in the pivot model."""
        if self._src is None or self._gidx is None:  # pragma: no cover
            raise ValueError("Source model or group index is not set.")
        if column < 0 or column >= len(self._presets):  # pragma: no cover
            raise IndexError("Column index out of range.")

        preset = self._presets[column]
        preset_idx = self._src.index_for_preset(self._gidx, preset.name)
        return preset_idx

    def mapToSourceSettingIndex(
        self, index: QModelIndex
    ) -> tuple[QConfigGroupsModel | None, QModelIndex]:
        """Map a pivot index to the corresponding (source_model, setting_index).

        Returns (None, invalid) if the mapping cannot be made.
        """
        if (
            self._src is None
            or self._gidx is None
            or not index.isValid()
            or (row := index.row()) >= len(self._rows)
            or (col := index.column()) >= len(self._presets)
        ):
            return None, QModelIndex()

        setting = self._data.get((row, col))
        if setting is None:
            return None, QModelIndex()

        preset = self._presets[col]
        preset_idx = self._src.index_for_preset(self._gidx, preset.name)
        if preset_idx.isValid():
            for i in range(self._src.rowCount(preset_idx)):
                src_idx = self._src.index(i, 2, preset_idx)
                if src_idx.data(Qt.ItemDataRole.UserRole) is setting:
                    return self._src, src_idx

        return None, QModelIndex()

    def _on_source_data_changed(
        self,
        top_left: QModelIndex,
        bottom_right: QModelIndex,
        roles: list[int] | None = None,
    ) -> None:
        """Handle dataChanged signals from the source model."""
        if not self._in_set_data and self._should_rebuild_for_changes(
            top_left, bottom_right
        ):
            self._rebuild()

    def _should_rebuild_for_changes(
        self, top_left: QModelIndex, bottom_right: QModelIndex
    ) -> bool:
        """Determine if model changes require rebuilding the pivot."""
        if self._gidx is None or self._src is None:
            return False  # pragma: no cover

        tl_col = top_left.column()
        tl_par = top_left.parent()
        gid_row = self._gidx.row()
        for row in range(top_left.row(), bottom_right.row() + 1):
            changed_index = self._src.index(row, tl_col, tl_par)
            # Skip group metadata changes (at root level with our group row)
            if tl_par.isValid() or row != gid_row:
                if self._is_within_current_group(changed_index):
                    # Preset or setting data changed, rebuild needed
                    return True
        return False

    def _is_within_current_group(self, index: QModelIndex) -> bool:
        """Check if the given index is within the currently displayed group."""
        current_group_row = self._gidx.row()  # type: ignore[union-attr]

        # Walk up the parent hierarchy
        check_index = index
        while check_index.isValid():
            parent = check_index.parent()

            # At root level: check if this is our group
            if not parent.isValid():
                return check_index.row() == current_group_row  # type: ignore[no-any-return]

            # Parent at root level: check if parent is our group
            if not parent.parent().isValid():
                return parent.row() == current_group_row  # type: ignore[no-any-return]

            # Move up one level
            check_index = parent

        return False
