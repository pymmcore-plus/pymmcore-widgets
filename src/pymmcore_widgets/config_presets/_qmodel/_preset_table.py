from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from qtpy.QtCore import QAbstractItemModel, QAbstractTableModel, QModelIndex, Qt, Signal
from qtpy.QtWidgets import (
    QAbstractItemView,
    QPushButton,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from pymmcore_plus.model._config_group import ConfigGroup, ConfigPreset

    from ._config_model import QConfigGroupsModel


class PresetTableDelegate(QStyledItemDelegate):
    """Custom delegate for preset table that uses PropertyWidget for editing."""

    def createEditor(
        self,
        parent: QWidget | None,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> QWidget | None:
        if not index.isValid():
            return super().createEditor(parent, option, index)

        model = cast("PresetTableModel", index.model())
        if not model:
            return super().createEditor(parent, option, index)

        # Get device and property for this row
        row = index.row()
        if row >= len(model._device_prop_pairs):
            return super().createEditor(parent, option, index)

        device, prop = model._device_prop_pairs[row]

        # Import PropertyWidget here to avoid circular imports
        from pymmcore_widgets.device_properties import PropertyWidget

        widget = PropertyWidget(device, prop, parent=parent, connect_core=False)
        widget.valueChanged.connect(lambda: self.commitData.emit(widget))
        widget.setAutoFillBackground(True)
        return widget

    def setEditorData(self, editor: QWidget | None, index: QModelIndex) -> None:
        # Import here to avoid circular imports
        from pymmcore_widgets.device_properties import PropertyWidget

        if isinstance(editor, PropertyWidget) and index.model():
            model = index.model()
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
        # Import here to avoid circular imports
        from pymmcore_widgets.device_properties import PropertyWidget

        if model and isinstance(editor, PropertyWidget):
            model.setData(index, editor.value(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)


class PresetTableModel(QAbstractTableModel):
    """Table model that presents a single ConfigGroup as a table.

    Columns represent presets, rows represent device/property combinations.
    This model is designed to work with PropertyValueDelegate by providing
    the expected data structure when queried.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source_model: QConfigGroupsModel | None = None
        self._group_index = QModelIndex()
        self._config_group: ConfigGroup | None = None
        self._presets: list[ConfigPreset] = []
        self._device_prop_pairs: list[tuple[str, str]] = []

    def setSourceModel(self, model: QConfigGroupsModel) -> None:
        """Set the source QConfigGroupsModel."""
        if self._source_model is not None:
            self._source_model.dataChanged.disconnect()
            self._source_model.modelReset.disconnect()
            self._source_model.rowsInserted.disconnect()
            self._source_model.rowsRemoved.disconnect()

        self._source_model = model
        if model is not None:
            model.dataChanged.connect(self._on_source_data_changed)
            model.modelReset.connect(self._refresh_data)
            model.rowsInserted.connect(self._refresh_data)
            model.rowsRemoved.connect(self._refresh_data)

    def setGroupIndex(self, group_index: QModelIndex) -> None:
        """Set the current group to display."""
        if not group_index.isValid() or self._source_model is None:
            self._group_index = QModelIndex()
            self._config_group = None
            self._refresh_data()
            return

        # Verify this is a group index
        node = group_index.internalPointer()
        if not hasattr(node, "is_group") or not node.is_group:
            return

        self._group_index = group_index
        self._config_group = cast("ConfigGroup", node.payload)
        self._refresh_data()

    def _refresh_data(self) -> None:
        """Rebuild internal data structures from the current group."""
        self.beginResetModel()

        if self._config_group is None:
            self._presets = []
            self._device_prop_pairs = []
        else:
            # Get all presets
            self._presets = list(self._config_group.presets.values())

            # Collect all unique device/property combinations
            device_prop_set = set()
            for preset in self._presets:
                for setting in preset.settings:
                    device_prop_set.add((setting.device_name, setting.property_name))

            self._device_prop_pairs = sorted(device_prop_set)

        self.endResetModel()

    def _on_source_data_changed(
        self, top_left: QModelIndex, bottom_right: QModelIndex
    ) -> None:
        """Handle changes in the source model."""
        # If the change affects our group, refresh
        if self._group_index.isValid() and self._affects_our_group(
            top_left, bottom_right
        ):
            self._refresh_data()

    def _affects_our_group(
        self, top_left: QModelIndex, bottom_right: QModelIndex
    ) -> bool:
        """Check if the changed indices affect our current group."""
        # For simplicity, refresh on any change for now
        # Could be optimized to only refresh when our specific group is affected
        return True

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is None:
            parent = QModelIndex()
        return len(self._device_prop_pairs)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is None:
            parent = QModelIndex()
        return len(self._presets)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            # Column headers are preset names
            if 0 <= section < len(self._presets):
                return self._presets[section].name
        elif orientation == Qt.Orientation.Vertical:
            # Row headers are device/property combinations
            if 0 <= section < len(self._device_prop_pairs):
                device, prop = self._device_prop_pairs[section]
                return f"{device}.{prop}"

        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if not (
            0 <= row < len(self._device_prop_pairs) and 0 <= col < len(self._presets)
        ):
            return None

        device, prop = self._device_prop_pairs[row]
        preset = self._presets[col]

        # Find the setting for this device/property in this preset
        setting = None
        for s in preset.settings:
            if s.device_name == device and s.property_name == prop:
                setting = s
                break

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return setting.property_value if setting else ""

        return None

    def setData(
        self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False

        row = index.row()
        col = index.column()

        if not (
            0 <= row < len(self._device_prop_pairs) and 0 <= col < len(self._presets)
        ):
            return False

        device, prop = self._device_prop_pairs[row]
        preset = self._presets[col]

        # Find or create the setting
        setting_idx = None
        for i, s in enumerate(preset.settings):
            if s.device_name == device and s.property_name == prop:
                setting_idx = i
                break

        # Import Setting here to avoid circular imports
        from pymmcore_plus.model._config_group import Setting

        new_setting = Setting(device, prop, str(value))

        if setting_idx is not None:
            # Update existing setting
            preset.settings[setting_idx] = new_setting
        else:
            # Add new setting
            preset.settings.append(new_setting)

        # Also need to update the source model if we can find the corresponding index
        if self._source_model and self._group_index.isValid():
            # Find the preset index in the source model
            for i in range(self._source_model.rowCount(self._group_index)):
                preset_index = self._source_model.index(i, 0, self._group_index)
                if self._source_model.data(preset_index) == preset.name:
                    # Find or create the setting index in the source model
                    for j in range(self._source_model.rowCount(preset_index)):
                        setting_model_index = self._source_model.index(
                            j, 0, preset_index
                        )
                        if (
                            self._source_model.data(setting_model_index) == device
                            and self._source_model.data(
                                setting_model_index.sibling(j, 1)
                            )
                            == prop
                        ):
                            # Update the value in the source model
                            value_index = setting_model_index.sibling(j, 2)
                            self._source_model.setData(value_index, value)
                            break
                    break

        self.dataChanged.emit(index, index, [role])
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return (
            Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsEditable
        )


class ConfigPresetTableWidget(QWidget):
    """Widget for editing a single ConfigGroup as a table with presets as columns."""

    currentGroupChanged = Signal(str)  # group_name

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source_model: QConfigGroupsModel | None = None
        self._current_group_name = ""

        # Create toolbar

        # Preset operations
        self._add_preset_btn = QPushButton("Add Preset")
        self._duplicate_preset_btn = QPushButton("Duplicate Preset")
        self._remove_preset_btn = QPushButton("Remove Preset")

        # Row operations
        self._add_row_btn = QPushButton("Add Row")
        self._remove_row_btn = QPushButton("Remove Row")

        self._toolbar = QToolBar()
        self._toolbar.addWidget(self._add_preset_btn)
        self._toolbar.addWidget(self._duplicate_preset_btn)
        self._toolbar.addWidget(self._remove_preset_btn)
        self._toolbar.addSeparator()
        self._toolbar.addWidget(self._add_row_btn)
        self._toolbar.addWidget(self._remove_row_btn)

        # Create table
        self._table_model = PresetTableModel(self)
        self._table_view = QTableView()
        self._table_view.setModel(self._table_model)
        self._table_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        # Configure headers

        if h_header := self._table_view.horizontalHeader():
            h_header.setStretchLastSection(True)

        if v_header := self._table_view.verticalHeader():
            v_header.setDefaultSectionSize(25)

        # Set up PropertyValueDelegate for all columns since they all represent values
        self._delegate = PresetTableDelegate(self._table_view)
        self._table_view.setItemDelegate(self._delegate)

        # LAYOUT ---------------------------------------------------
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._table_view)

        # CONNECT SIGNALS ---------------------------------------------------

        self._add_preset_btn.clicked.connect(self._add_preset)
        self._duplicate_preset_btn.clicked.connect(self._duplicate_preset)
        self._remove_preset_btn.clicked.connect(self._remove_preset)
        self._add_row_btn.clicked.connect(self._add_row)
        self._remove_row_btn.clicked.connect(self._remove_row)

    def setModel(self, model: QConfigGroupsModel) -> None:
        """Set the source QConfigGroupsModel."""
        self._source_model = model
        self._table_model.setSourceModel(model)

    def setCurrentGroup(self, group_name: str) -> None:
        """Set the current group by name."""
        if not self._source_model:
            return

        # Find the group index
        group_index = self._source_model.index_for_group(group_name)
        if group_index.isValid():
            self.setCurrentGroupIndex(group_index)

    def setCurrentGroupIndex(self, group_index: QModelIndex) -> None:
        """Set the current group by QModelIndex."""
        if not self._source_model or not group_index.isValid():
            return

        self._table_model.setGroupIndex(group_index)

        # Update current group name
        new_group_name = self._source_model.data(group_index)
        if new_group_name != self._current_group_name:
            self._current_group_name = new_group_name
            self.currentGroupChanged.emit(new_group_name)

    def currentGroupName(self) -> str:
        """Get the current group name."""
        return self._current_group_name

    def _add_preset(self) -> None:
        """Add a new preset to the current group."""
        if not self._source_model:
            return
        group_index = self._source_model.index_for_group(self._current_group_name)
        if group_index.isValid():
            preset_index = self._source_model.add_preset(group_index)
            if preset_index.isValid():
                self._table_model._refresh_data()

    def _duplicate_preset(self) -> None:
        """Duplicate the selected preset."""
        if not self._source_model:
            return

        # Get selected column (preset)
        sel_model = self._table_view.selectionModel()
        if not sel_model:
            return

        selection = sel_model.selectedColumns()
        if not selection:
            return

        col = selection[0].column()
        if col < 0 or col >= len(self._table_model._presets):
            return

        group_index = self._source_model.index_for_group(self._current_group_name)
        if not group_index.isValid():
            return

        preset_name = self._table_model._presets[col].name
        preset_index = self._source_model.index_for_preset(preset_name, group_index)
        if preset_index.isValid():
            self._source_model.duplicate_preset(preset_index)
            self._table_model._refresh_data()

    def _remove_preset(self) -> None:
        """Remove the selected preset."""
        if not self._source_model:
            return

        # Get selected column (preset)
        sel_model = self._table_view.selectionModel()
        if not sel_model:
            return

        selection = sel_model.selectedColumns()
        if not selection:
            return

        col = selection[0].column()
        if col < 0 or col >= len(self._table_model._presets):
            return

        group_index = self._source_model.index_for_group(self._current_group_name)
        if not group_index.isValid():
            return

        preset_name = self._table_model._presets[col].name
        preset_index = self._source_model.index_for_preset(preset_name, group_index)
        if preset_index.isValid():
            self._source_model.remove(preset_index)
            self._table_model._refresh_data()

    def _add_row(self) -> None:
        """Add a new device/property row."""
        # This will need custom logic - placeholder for now
        pass

    def _remove_row(self) -> None:
        """Remove the selected device/property row from all presets."""
        sel_model = self._table_view.selectionModel()
        if not sel_model:
            return

        selection = sel_model.selectedRows()
        if not selection:
            return

        row = selection[0].row()
        if row < 0 or row >= len(self._table_model._device_prop_pairs):
            return

        device, prop = self._table_model._device_prop_pairs[row]

        # Remove this device/property from all presets in the group
        for preset in self._table_model._presets:
            preset.settings = [
                s
                for s in preset.settings
                if not (s.device_name == device and s.property_name == prop)
            ]

        # Refresh the model
        self._table_model._refresh_data()
