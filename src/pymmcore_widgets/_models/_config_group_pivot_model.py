from __future__ import annotations

from typing import TYPE_CHECKING, Any

from qtpy.QtCore import QAbstractTableModel, QModelIndex, QSize, Qt

from pymmcore_widgets._icons import StandardIcon

from ._py_config_model import ConfigPreset, DevicePropertySetting
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
            if not group_name_or_index.isValid():  # pragma: no cover
                raise ValueError("Invalid QModelIndex provided for group selection.")
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

        # Get the preset and device/property for this cell
        preset = self._presets[col]
        dev_prop = self._rows[row]
        # Create or update the setting
        # Update our local data
        self._data[(row, col)] = setting = DevicePropertySetting(
            device=dev_prop[0], property_name=dev_prop[1], value=str(value)
        )

        # Update the preset's settings list
        preset_settings = list(preset.settings)

        # Find existing setting or add new one
        for i, existing_setting in enumerate(preset_settings):
            existing_key = (
                existing_setting.device_label,
                existing_setting.property_name,
            )
            if existing_key == dev_prop:
                preset_settings[i] = setting
                break
        else:
            preset_settings.append(setting)

        # Find the preset index in the source model and update it
        preset_idx = self._src.index_for_preset(self._gidx, preset.name)
        if preset_idx.isValid():
            self._src.update_preset_settings(preset_idx, preset_settings)

        # Emit dataChanged signal for the specific cell
        self._src.dataChanged.emit(preset_idx, preset_idx, [role])
        return True

    # ---------------------------------------------------------------- build --

    def _rebuild(self) -> None:  # slot signature is flexible
        if self._gidx is None:  # nothing selected yet
            return  # pragma: no cover
        self.beginResetModel()

        self._presets = []
        self._rows = []
        self._data.clear()
        try:
            node = self._gidx.internalPointer()
            if not node:
                return  # pragma: no cover
            self._presets = [child.payload for child in node.children]
            keys = (setting.key() for p in self._presets for setting in p.settings)
            self._rows = list(dict.fromkeys(keys, None))  # unique (device, prop) pairs

            self._data.clear()
            for col, preset in enumerate(self._presets):
                for row, (device, prop) in enumerate(self._rows):
                    for s in preset.settings:
                        if s.key() == (device, prop):
                            self._data[(row, col)] = s
                            break
        finally:
            self.endResetModel()

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
        if role == Qt.ItemDataRole.DisplayRole and section < len(self._presets):
            if orient == Qt.Orientation.Horizontal:
                return self._presets[section].name
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

    # make editable
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():  # pragma: no cover
            return Qt.ItemFlag.NoItemFlags
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
        )

    def get_source_index_for_column(self, column: int) -> QModelIndex:
        """Get the source index for a given column in the pivot model."""
        if self._src is None or self._gidx is None:  # pragma: no cover
            raise ValueError("Source model or group index is not set.")
        if column < 0 or column >= len(self._presets):  # pragma: no cover
            raise IndexError("Column index out of range.")

        preset = self._presets[column]
        preset_idx = self._src.index_for_preset(self._gidx, preset.name)
        return preset_idx

    def _on_source_data_changed(
        self,
        top_left: QModelIndex,
        bottom_right: QModelIndex,
        roles: list[int] | None = None,
    ) -> None:
        """Handle dataChanged signals from the source model."""
        if self._should_rebuild_for_changes(top_left, bottom_right):
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
