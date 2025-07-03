from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, cast

from pymmcore_plus import PropertyType
from qtpy.QtCore import (
    QAbstractItemModel,
    QAbstractProxyModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
)
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

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return the data stored for `role` for the item at `index`."""
        node = self._node_from_index(index)
        index.column()
        if node is self._root:
            return None

        if index.column() == 1:
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                if isinstance(device := node.payload, Device):
                    return device.type.name
                elif isinstance(setting := node.payload, DevicePropertySetting):
                    return setting.property_type.name
            elif role == Qt.ItemDataRole.DecorationRole:
                if isinstance(device := node.payload, Device):
                    if icon := device.iconify_key:
                        return QIconifyIcon(icon, color="gray").pixmap(16, 16)
                    return QIcon.fromTheme("emblem-system")  # pragma: no cover
                elif isinstance(setting := node.payload, DevicePropertySetting):
                    if setting.is_read_only:
                        return QIcon.fromTheme("lock")
                    elif setting.is_pre_init:
                        return QIconifyIcon(
                            "ph:letter-circle-p-duotone", color="gray"
                        ).pixmap(16, 16)
                    elif setting.property_type == PropertyType.String:
                        return QIconifyIcon("mdi:code-string", color="gray").pixmap(
                            16, 16
                        )
                    elif setting.property_type in (
                        PropertyType.Integer,
                        PropertyType.Float,
                    ):
                        return QIconifyIcon("mdi:numbers", color="gray").pixmap(16, 16)
            return

        # Qt.ItemDataRole.UserRole => return the original python object
        if role == Qt.ItemDataRole.UserRole:
            return node.payload

        if isinstance(device := node.payload, Device):
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                return device.name
        elif isinstance(setting := node.payload, DevicePropertySetting):
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                return setting.property_name
            elif role == Qt.ItemDataRole.FontRole:
                if setting.is_read_only:
                    font = QFont()
                    font.setItalic(True)
                    return font
            elif role == Qt.ItemDataRole.CheckStateRole:
                if not (setting.is_read_only or setting.is_pre_init):
                    return node.check_state
            elif role == Qt.ItemDataRole.ForegroundRole:
                if setting.is_read_only or setting.is_pre_init:
                    return QBrush(Qt.GlobalColor.gray)

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
                    node.check_state = value
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


class FlatPropertyModel(QAbstractProxyModel):
    """Presents every *leaf* of an arbitrary tree model as a top-level row."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._leaves: list[QPersistentModelIndex] = []

    def index(self, row: int, column: int, parent: QModelIndex = ...) -> QModelIndex:
        if not (sm := self.sourceModel()):
            return QModelIndex()
        return sm.index(row, column, parent)

    # --------------------------------------------------------------------------------
    # mandatory proxy plumbing
    # --------------------------------------------------------------------------------
    def setSourceModel(self, source_model: QAbstractItemModel | None) -> None:
        super().setSourceModel(source_model)
        self._rebuild()
        # keep list in sync with structural changes
        source_model.rowsInserted.connect(self._rebuild)
        source_model.rowsRemoved.connect(self._rebuild)
        source_model.modelReset.connect(self._rebuild)

    # map source ↔ proxy -----------------------------------------------------
    def mapToSource(self, proxy_index: QModelIndex) -> QModelIndex:
        return (
            QModelIndex(self._leaves[proxy_index.row()])
            if proxy_index.isValid()
            else QModelIndex()
        )

    def mapFromSource(self, source_index: QModelIndex) -> QModelIndex:
        try:
            row = self._leaves.index(QPersistentModelIndex(source_index))
            return self.createIndex(row, source_index.column())
        except ValueError:
            return QModelIndex()

    # shape ------------------------------------------------------------------
    def rowCount(self, _parent: QModelIndex = NULL_INDEX) -> int:
        return len(self._leaves)

    def columnCount(self, parent: QModelIndex = NULL_INDEX) -> int:
        if sm := self.sourceModel():
            return sm.columnCount(self.mapToSource(parent))
        return 0

    # data, flags, setData simply delegate to the source --------------------
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if sm := self.sourceModel():
            return sm.data(self.mapToSource(index), role)
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if sm := self.sourceModel():
            return sm.flags(self.mapToSource(index))
        return Qt.ItemFlag.NoItemFlags

    def setData(
        self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if sm := self.sourceModel():
            return sm.setData(self.mapToSource(index), value, role)
        return False

    # helpers ----------------------------------------------------------------
    def _rebuild(self) -> None:
        """Cache every leaf `QModelIndex` of the tree."""
        if not (sm := self.sourceModel()):
            return
        self.beginResetModel()
        self._leaves.clear()

        def walk(parent: QModelIndex) -> None:
            rows = sm.rowCount(parent)
            for r in range(rows):
                idx = sm.index(r, 0, parent)
                if sm.rowCount(idx):  # branch
                    walk(idx)
                else:  # leaf
                    self._leaves.append(QPersistentModelIndex(idx))

        walk(QModelIndex())
        self.endResetModel()
