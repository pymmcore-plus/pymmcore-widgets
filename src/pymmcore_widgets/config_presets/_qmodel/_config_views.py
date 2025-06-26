from __future__ import annotations

from typing import TYPE_CHECKING, Callable, cast

from pymmcore_plus.model import ConfigGroup
from qtpy.QtCore import QAbstractItemModel, QModelIndex, QSize, Qt, Signal
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from superqt import QIconifyIcon

from pymmcore_widgets.device_properties import PropertyWidget

from ._config_model import QConfigGroupsModel, _Node
from ._config_properties import GroupedDevicePropertyTable

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from pymmcore_plus import CMMCorePlus
    from pymmcore_plus.model import ConfigPreset


class PropertyValueDelegate(QStyledItemDelegate):
    """Item delegate that uses a PropertyWidget for editing PropertySetting values."""

    def createEditor(
        self, parent: QWidget | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget | None:
        node = cast("_Node", index.internalPointer())
        if not (model := index.model()) or (index.column() != 2) or not node.is_setting:
            return super().createEditor(parent, option, index)

        row = index.row()
        device = model.data(index.sibling(row, 0))
        prop = model.data(index.sibling(row, 1))
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


# -----------------------------------------------------------------------------
# High-level editor widget
# -----------------------------------------------------------------------------


class _NameList(QWidget):
    """A group box that contains a toolbar and a QListView for cfg groups or presets."""

    def __init__(
        self, title: str, parent: QWidget | None, new_fn: Callable, list_view: QListView
    ) -> None:
        super().__init__(parent)
        self._title = title

        # toolbar
        self._toolbar = QToolBar()
        self._toolbar.setIconSize(QSize(18, 18))
        # self._toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

        self._toolbar.addAction(
            QIconifyIcon("mdi:plus-thick", color="gray"),
            f"Add {title.rstrip('s')}",
            new_fn,
        )
        self._toolbar.addAction(
            QIconifyIcon("mdi:remove-bold", color="gray"),
            "Remove",
            self._remove,
        )
        self._toolbar.addAction(
            QIconifyIcon("mdi:content-duplicate", color="gray"),
            "Duplicate",
            self._dupe,
        )

        self._view = list_view
        self._model = cast("QConfigGroupsModel", list_view.model())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._toolbar)
        layout.addWidget(list_view)

        if isinstance(self, QGroupBox):
            self.setTitle(title)
        else:
            layout.insertWidget(0, QLabel(self._title, self))

    def _is_groups(self) -> bool:
        """Check if this box is for groups."""
        return bool(self._title == "Groups")

    def _remove(self) -> None:
        self._model.remove(self._view.currentIndex())

    def _dupe(self) -> None:
        idx = self._view.currentIndex()
        if idx.isValid():
            if self._is_groups():
                self._view.setCurrentIndex(self._model.duplicate_group(idx))
            else:
                self._view.setCurrentIndex(self._model.duplicate_preset(idx))


# This should perhaps be a QAbstractItemView
class ConfigGroupsEditor(QWidget):
    """Widget composed of two QListViews backed by a single tree model."""

    configChanged = Signal()

    @classmethod
    def create_from_core(
        cls, core: CMMCorePlus, parent: QWidget | None = None
    ) -> ConfigGroupsEditor:
        """Create a ConfigGroupsEditor from a CMMCorePlus instance."""
        obj = cls(parent)
        groups = ConfigGroup.all_config_groups(core)
        obj.setData(groups.values())
        obj.update_options_from_core(core)
        return obj

    def update_options_from_core(self, core: CMMCorePlus) -> None:
        """Populate the comboboxes with the available devices from the core."""
        self._prop_tables.update_options_from_core(core)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = QConfigGroupsModel()

        # widgets --------------------------------------------------------------

        self._group_view = QListView()
        self._group_view.setModel(self._model)
        group_box = _NameList("Groups", self, self._new_group, self._group_view)

        self._preset_view = QListView()
        self._preset_view.setModel(self._model)
        preset_box = _NameList("Presets", self, self._new_preset, self._preset_view)

        self._prop_tables = GroupedDevicePropertyTable()

        # layout ------------------------------------------------------------

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(group_box)
        lv.addWidget(preset_box)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(left)
        lay.addWidget(self._prop_tables)

        # signals ------------------------------------------------------------

        if sm := self._group_view.selectionModel():
            sm.currentChanged.connect(self._on_group_sel)
        if sm := self._preset_view.selectionModel():
            sm.currentChanged.connect(self._on_preset_sel)
        self._model.dataChanged.connect(self._on_model_data_changed)
        self._prop_tables.valueChanged.connect(self._on_prop_table_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setData(self, data: Iterable[ConfigGroup]) -> None:
        """Set the configuration data to be displayed in the editor."""
        data = list(data)  # ensure we can iterate multiple times
        self._model.set_groups(data)
        self._prop_tables.setValue([])
        # Auto-select first group
        if self._model.rowCount():
            self._group_view.setCurrentIndex(self._model.index(0))
        else:
            self._preset_view.setRootIndex(QModelIndex())
            self._preset_view.clearSelection()
        self.configChanged.emit()

    def data(self) -> Sequence[ConfigGroup]:
        """Return the current configuration data as a list of ConfigGroup."""
        return self._model.data_as_groups()

    # "new" actions ----------------------------------------------------------

    def _new_group(self) -> None:
        idx = self._model.add_group()
        self._group_view.setCurrentIndex(idx)

    def _new_preset(self) -> None:
        gidx = self._group_view.currentIndex()
        if not gidx.isValid():
            return
        pidx = self._model.add_preset(gidx)
        self._preset_view.setCurrentIndex(pidx)

    # selection sync ---------------------------------------------------------

    def _on_group_sel(self, current: QModelIndex, _prev: QModelIndex) -> None:
        self._preset_view.setRootIndex(current)
        if current.isValid() and self._model.rowCount(current):
            self._preset_view.setCurrentIndex(self._model.index(0, 0, current))
        else:
            self._preset_view.clearSelection()

    def _on_preset_sel(self, current: QModelIndex, _prev: QModelIndex) -> None:
        """Populate the DevicePropertyTable whenever the selected preset changes."""
        if not current.isValid():
            # clear table when nothing is selected
            self._prop_tables.setValue([])
            return
        node = cast("_Node", current.internalPointer())
        if not node.is_preset:
            self._prop_tables.setValue([])
            return
        preset = cast("ConfigPreset", node.payload)
        self._prop_tables.setValue(preset.settings)

    # ------------------------------------------------------------------
    # Property-table sync
    # ------------------------------------------------------------------

    def _on_prop_table_changed(self) -> None:
        """Write back edits from the table into the underlying ConfigPreset."""
        idx = self._preset_view.currentIndex()
        if not idx.isValid():
            return
        node = cast("_Node", idx.internalPointer())
        if not node.is_preset:
            return
        new_settings = self._prop_tables.value()
        self._model.update_preset_settings(idx, new_settings)
        self.configChanged.emit()

    def _on_model_data_changed(
        self,
        topLeft: QModelIndex,
        bottomRight: QModelIndex,
        _roles: list[int] | None = None,
    ) -> None:
        """Refresh DevicePropertyTable if a setting in the current preset was edited."""
        cur_preset = self._preset_view.currentIndex()
        if not cur_preset.isValid():
            return

        # We only care about edits to rows that are direct children of the
        # currently-selected preset (i.e. Setting rows).
        if topLeft.parent() != cur_preset:
            return

        # pull updated settings from the model and push to the table
        node = cast("_Node", cur_preset.internalPointer())
        preset = cast("ConfigPreset", node.payload)
        self._prop_tables.blockSignals(True)  # avoid feedback loop
        self._prop_tables.setValue(preset.settings)
        self._prop_tables.blockSignals(False)
