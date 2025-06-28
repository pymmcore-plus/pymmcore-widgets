from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pymmcore_plus.model import ConfigPreset, Setting
from qtpy.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSize,
    Qt,
    QTransposeProxyModel,
)
from qtpy.QtWidgets import QTableView, QToolBar, QVBoxLayout, QWidget
from superqt import QIconifyIcon

from ._config_model import QConfigGroupsModel, _Node
from ._property_setting_delegate import PropertySettingDelegate

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pymmcore_plus.model import ConfigPreset


# -----------------------------------------------------------------------------
class _ConfigGroupPivotModel(QAbstractTableModel):
    """Pivot a single ConfigGroup into rows=Device/Property, cols=Presets."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._src: QConfigGroupsModel | None = None
        self._gidx: QModelIndex | None = None
        self._presets: list[ConfigPreset] = []
        self._rows: list[tuple[str, str]] = []  # (device_name, property_name)
        self._data: dict[tuple[int, int], Setting] = {}
        self._root = _Node("<root>", None)

    def sourceModel(self) -> QConfigGroupsModel | None:
        """Return the source model."""
        return self._src

    def setSourceModel(self, src_model: QConfigGroupsModel) -> None:
        """Set the source model and rebuild the matrix."""
        if not isinstance(src_model, QConfigGroupsModel):
            raise TypeError("Source model must be an instance of QConfigGroupsModel.")
        self._src = src_model

        # -> keep the pivot up-to-date whenever the tree model changes
        src_model.modelReset.connect(self._rebuild)
        src_model.rowsInserted.connect(self._rebuild)
        src_model.rowsRemoved.connect(self._rebuild)
        src_model.dataChanged.connect(self._rebuild)

    def setGroup(self, group_name_or_index: str | QModelIndex) -> None:
        """Set the group index to pivot and rebuild the matrix."""
        if self._src is None:
            raise ValueError("Source model is not set. Call setSourceModel first.")
        if not isinstance(group_name_or_index, QModelIndex):
            self._gidx = self._src.index_for_group(group_name_or_index)
        else:
            if not group_name_or_index.isValid():
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
            return False

        # Get the preset and device/property for this cell
        preset = self._presets[col]
        dev_prop = self._rows[row]

        # Create or update the setting
        # Update our local data
        self._data[(row, col)] = setting = Setting(dev_prop[0], dev_prop[1], str(value))

        # Update the preset's settings list
        preset_settings = list(preset.settings)

        # Find existing setting or add new one
        for i, (dev, prop, *_) in enumerate(preset_settings):
            if (dev, prop) == dev_prop:
                preset_settings[i] = setting
                break
        else:
            preset_settings.append(setting)

        # Find the preset index in the source model and update it
        preset_idx = self._src.index_for_preset(self._gidx, preset.name)
        if preset_idx.isValid():
            self._src.update_preset_settings(preset_idx, preset_settings)

        # Emit dataChanged for this cell
        self.dataChanged.emit(index, index, [role])
        return True

    # ---------------------------------------------------------------- build --

    def _rebuild(self) -> None:  # slot signature is flexible
        if self._gidx is None:  # nothing selected yet
            return
        self.beginResetModel()

        node = self._gidx.internalPointer()
        self._presets = [child.payload for child in node.children]
        keys = ((dev, prop) for p in self._presets for (dev, prop, *_) in p.settings)
        self._rows = list(dict.fromkeys(keys, None))  # unique (device, prop) pairs

        self._data.clear()
        for col, preset in enumerate(self._presets):
            for row, (device, prop) in enumerate(self._rows):
                for s in preset.settings:
                    if (s.device_name, s.property_name) == (device, prop):
                        self._data[(row, col)] = s
                        break

        self.endResetModel()

    # --------------------------------------------------------- Qt overrides --

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        return len(self._presets)

    def headerData(
        self,
        section: int,
        orient: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orient == Qt.Orientation.Horizontal:
            return self._presets[section].name
        return "-".join(self._rows[section])

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
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
            return setting.property_value if setting else None
        return None

    # make editable
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
        )


class PresetsTable(QWidget):
    """A simple table widget to display presets."""

    @classmethod
    def create_from_core(
        cls, core: CMMCorePlus, parent: QWidget | None = None
    ) -> PresetsTable:
        """Create a PresetsTable from a CMMCorePlus instance."""
        obj = cls(parent)
        model = QConfigGroupsModel.create_from_core(core)
        obj.setModel(model)
        return obj

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.table_view = QTableView(self)
        self.table_view.setItemDelegate(PropertySettingDelegate(self.table_view))

        self._toolbar = tb = QToolBar(self)
        tb.setIconSize(QSize(16, 16))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        if act := tb.addAction(
            QIconifyIcon("carbon:transpose"), "Transpose", self._transpose
        ):
            act.setCheckable(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self.table_view)

    def _update_view(self) -> None:
        matrix = self.table_view.model()
        if not isinstance(matrix, _ConfigGroupPivotModel):
            return

        if hh := self.table_view.horizontalHeader():
            hh.setSectionResizeMode(hh.ResizeMode.Stretch)

    def _transpose(self) -> None:
        """Transpose the table view."""
        pivot = self.table_view.model()
        if isinstance(pivot, _ConfigGroupPivotModel):
            proxy = QTransposeProxyModel(self)
            proxy.setSourceModel(pivot)
            self.table_view.setModel(proxy)
        elif isinstance(pivot, QTransposeProxyModel):
            # Already transposed, revert to original model
            source_model = pivot.sourceModel()
            if isinstance(source_model, _ConfigGroupPivotModel):
                self.table_view.setModel(source_model)

    def sourceModel(self) -> QConfigGroupsModel | None:
        """Return the source model of the table view."""
        model = self.table_view.model()
        if isinstance(model, QTransposeProxyModel):
            model = cast("_ConfigGroupPivotModel", model.sourceModel())
        if isinstance(model, _ConfigGroupPivotModel):
            return model.sourceModel()
        return None

    def setModel(self, model: QConfigGroupsModel | _ConfigGroupPivotModel) -> None:
        """Set the model for the table view."""
        if isinstance(model, QConfigGroupsModel):
            matrix = _ConfigGroupPivotModel()
            matrix.setSourceModel(model)
        elif isinstance(model, _ConfigGroupPivotModel):
            matrix = model
        else:
            raise TypeError(
                "Model must be an instance of QConfigGroupsModel "
                "or ConfigGroupPivotModel."
            )

        self.table_view.setModel(matrix)
        matrix.modelReset.connect(self._update_view)

    def setGroup(self, group_name_or_index: str | QModelIndex) -> None:
        """Set the group for the pivot model."""
        model = self.table_view.model()
        if isinstance(model, QTransposeProxyModel):
            model = cast("_ConfigGroupPivotModel", model.sourceModel())
        if not isinstance(model, _ConfigGroupPivotModel):
            raise ValueError("Source model is not set. Call setSourceModel first.")
        model.setGroup(group_name_or_index)
