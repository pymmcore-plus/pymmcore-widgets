from __future__ import annotations

from contextlib import suppress
from copy import deepcopy
from typing import TYPE_CHECKING, Any, cast

from qtpy.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt
from qtpy.QtGui import QBrush, QFont, QIcon
from superqt import QIconifyIcon

from ._base_tree_model import _BaseTreeModel, _Node
from ._core_functions import get_loaded_devices
from ._py_config_model import Device, DevicePropertySetting

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pymmcore_plus import CMMCorePlus
    from typing_extensions import Self

NULL_INDEX = QModelIndex()


class QDevicePropertyModel(_BaseTreeModel):
    """2-level model: devices -> properties."""

    @classmethod
    def create_from_core(cls, core: CMMCorePlus) -> Self:
        return cls(get_loaded_devices(core))

    def __init__(self, devices: Iterable[Device] | None = None) -> None:
        super().__init__()
        if devices:
            self.set_devices(devices)

    # ------------------------------------------------------------------
    # Required Qt model overrides
    # ------------------------------------------------------------------

    def columnCount(self, _parent: QModelIndex | None = None) -> int:
        return 2

    # data & editing ----------------------------------------------------------

    def _get_device_data(self, device: Device, col: int, role: int) -> Any:
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if col == 1:
                return device.type.name
            else:
                return device.label or f"{device.library}::{device.name}"
        elif role == Qt.ItemDataRole.DecorationRole:
            if col == 0:
                if icon := device.iconify_key:
                    return QIconifyIcon(icon, color="gray").pixmap(16, 16)
                return QIcon.fromTheme("emblem-system")  # pragma: no cover

        return None

    def _get_prop_data(self, prop: DevicePropertySetting, col: int, role: int) -> Any:
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if col == 1:
                return prop.property_type.name
            else:
                return prop.property_name
        elif role == Qt.ItemDataRole.DecorationRole:
            if col == 0:
                if icon := prop.iconify_key:
                    return QIconifyIcon(icon, color="gray").pixmap(16, 16)

        elif role == Qt.ItemDataRole.FontRole:
            if prop.is_read_only:
                font = QFont()
                font.setItalic(True)
                return font
        elif role == Qt.ItemDataRole.ForegroundRole:
            if prop.is_read_only or prop.is_pre_init:
                return QBrush(Qt.GlobalColor.gray)

        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return the data stored for `role` for the item at `index`."""
        node = self._node_from_index(index)
        if node is self._root:
            return None

        col = index.column()
        # Qt.ItemDataRole.UserRole => return the original python object
        if role == Qt.ItemDataRole.UserRole:
            return node.payload

        elif role == Qt.ItemDataRole.CheckStateRole:
            if isinstance(setting := node.payload, DevicePropertySetting):
                return node.check_state

        if isinstance(device := node.payload, Device):
            return self._get_device_data(device, col, role)
        elif isinstance(setting := node.payload, DevicePropertySetting):
            return self._get_prop_data(setting, col, role)
        return None

    def setData(
        self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        """Set the data for the item at `index` to `value` for `role`."""
        if not index.isValid():
            return False

        node = self._node_from_index(index)
        if node is self._root:
            return False

        if role == Qt.ItemDataRole.CheckStateRole:
            if isinstance(setting := node.payload, DevicePropertySetting):
                if not (setting.is_read_only or setting.is_pre_init):
                    node.check_state = Qt.CheckState(value)
                    self.dataChanged.emit(index, index, [role])
                    return True

        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        node = self._node_from_index(index)
        if node is self._root:
            return Qt.ItemFlag.NoItemFlags

        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def set_devices(self, devices: Iterable[Device]) -> None:
        """Clear model and set new devices."""
        self.beginResetModel()
        self._root.children.clear()
        for d in devices:
            self._root.children.append(_Node.create(d, self._root))
        self.endResetModel()

    def get_devices(self) -> list[Device]:
        """Return All Devices in the model."""
        return deepcopy([cast("Device", n.payload) for n in self._root.children])

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return "Device/Property" if section == 0 else "Type"
            elif orientation == Qt.Orientation.Vertical:
                return str(section + 1)
        return None


class DevicePropertyFlatProxy(QAbstractItemModel):
    """Flatten `Device → Property` into rows:  Device | Property."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._source_model: QAbstractItemModel | None = None
        self._rows: list[tuple[int, int]] = []

    def setSourceModel(self, source_model: QAbstractItemModel | None) -> None:
        """Set the source model and connect to its signals."""
        # Disconnect from old model
        if self._source_model is not None:
            with suppress(RuntimeError):
                self._source_model.modelReset.disconnect(self._rebuild_rows)
                self._source_model.layoutChanged.disconnect(self._rebuild_rows)
                self._source_model.rowsInserted.disconnect(self._rebuild_rows)
                self._source_model.rowsRemoved.disconnect(self._rebuild_rows)
                self._source_model.dataChanged.disconnect(self._on_source_data_changed)

        self._source_model = source_model

        # Connect to new model
        if source_model is not None:
            source_model.modelReset.connect(self._rebuild_rows)
            source_model.layoutChanged.connect(self._rebuild_rows)
            source_model.rowsInserted.connect(self._rebuild_rows)
            source_model.rowsRemoved.connect(self._rebuild_rows)
            source_model.dataChanged.connect(self._on_source_data_changed)

        self._rebuild_rows()

    def sourceModel(self) -> QAbstractItemModel | None:
        """Return the source model."""
        return self._source_model

    def index(
        self, row: int, column: int, parent: QModelIndex | None = None
    ) -> QModelIndex:
        if parent and parent.isValid():
            return QModelIndex()
        if 0 <= row < len(self._rows) and 0 <= column < 2:
            return self.createIndex(row, column)
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        return QModelIndex()  # Flat model has no hierarchy

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        return 2

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        source_idx = self._mapped_index(index.row(), index.column())
        return source_idx.data(role) if source_idx.isValid() else None

    def setData(
        self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if not index.isValid() or not self._source_model:
            return False

        source_idx = self._mapped_index(index.row(), index.column())
        if source_idx.isValid():
            return bool(self._source_model.setData(source_idx, value, role))
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid() or not self._source_model:
            return Qt.ItemFlag.NoItemFlags

        source_idx = self._mapped_index(index.row(), index.column())
        if not source_idx.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = self._source_model.flags(source_idx)
        if index.column() == 1:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return "Device" if section == 0 else "Property"
            elif orientation == Qt.Orientation.Vertical:
                return str(section + 1)
        elif role == Qt.ItemDataRole.FontRole:
            if orientation == Qt.Orientation.Horizontal:
                font = QFont()
                font.setBold(True)
                return font
        return None

    def sort(
        self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder
    ) -> None:
        if column not in (0, 1) or not (sm := self._source_model):
            return

        def _key(x: tuple[int, int]) -> Any:
            par = sm.index(x[0], 0) if column == 1 else NULL_INDEX
            return sm.index(x[column], 0, par).data() or ""

        self.layoutAboutToBeChanged.emit()
        self._rows.sort(key=_key, reverse=order == Qt.SortOrder.DescendingOrder)
        self.layoutChanged.emit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mapped_index(self, flat_row: int, column: int) -> QModelIndex:
        """Return the corresponding source QModelIndex for a given flat row/column.

        Parameters
        ----------
        flat_row : int
            Row in the *flattened* proxy model.
        column : int
            Column in the *flattened* proxy model (0=device, 1=property).

        Returns
        -------
        QModelIndex
            The matching index in the source model, or an invalid index
            when the mapping is impossible.
        """
        if (
            self._source_model is None
            or column not in (0, 1)
            or flat_row < 0
            or flat_row >= len(self._rows)
        ):
            return QModelIndex()

        drow, prow = self._rows[flat_row]
        device_idx = self._source_model.index(drow, 0)
        if column == 0:
            return device_idx

        # column 1 - property
        if device_idx.isValid():
            return self._source_model.index(prow, 0, device_idx)
        return QModelIndex()

    def _rebuild_rows(self) -> None:
        """Rebuild the flattened row structure."""
        self.beginResetModel()
        self._rows.clear()

        if self._source_model is not None:
            for drow in range(self._source_model.rowCount()):
                device_idx = self._source_model.index(drow, 0)
                if device_idx.isValid():
                    for prow in range(self._source_model.rowCount(device_idx)):
                        prop_idx = self._source_model.index(prow, 0, device_idx)
                        if prop_idx.isValid():
                            self._rows.append((drow, prow))

        self.endResetModel()

    def _on_source_data_changed(
        self, top_left: QModelIndex, bottom_right: QModelIndex, roles: list[int]
    ) -> None:
        """Handle dataChanged signal from source model and emit signals."""
        if not self._source_model:
            return

        # Find which flat proxy rows correspond to changed indices in source model
        changed_rows: set[int] = set()

        # Check if any of our flattened rows correspond to the changed indices
        for flat_row, (drow, prow) in enumerate(self._rows):
            # Check if this flat row corresponds to a changed device or property
            device_idx = self._source_model.index(drow, 0)
            if device_idx.isValid():
                prop_idx = self._source_model.index(prow, 0, device_idx)

                # Check if the changed range includes our device or property
                if self._index_in_range(
                    device_idx, top_left, bottom_right
                ) or self._index_in_range(prop_idx, top_left, bottom_right):
                    changed_rows.add(flat_row)

        # Emit dataChanged for all affected flat proxy rows
        for flat_row in changed_rows:
            top_left_flat = self.index(flat_row, 0)
            bottom_right_flat = self.index(flat_row, 1)
            if top_left_flat.isValid() and bottom_right_flat.isValid():
                self.dataChanged.emit(top_left_flat, bottom_right_flat, roles)

    def _index_in_range(
        self, index: QModelIndex, top_left: QModelIndex, bottom_right: QModelIndex
    ) -> bool:
        """Check if an index falls within the given range."""
        if not index.isValid() or not top_left.isValid() or not bottom_right.isValid():
            return False

        # Check if parent matches
        if index.parent() != top_left.parent():
            return False

        # Check if row and column are in range
        return bool(
            top_left.row() <= index.row() <= bottom_right.row()
            and top_left.column() <= index.column() <= bottom_right.column()
        )
