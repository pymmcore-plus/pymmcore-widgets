from __future__ import annotations

from typing import TYPE_CHECKING, Callable, cast

from pymmcore_plus import DeviceProperty, DeviceType, Keyword
from qtpy.QtCore import QAbstractItemModel, QModelIndex, QSize, Qt, Signal
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QListView,
    QSplitter,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from superqt import QIconifyIcon

from pymmcore_widgets.device_properties import DevicePropertyTable, PropertyWidget

from ._config_model import QConfigTreeModel, _Node

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from pymmcore_plus.model import ConfigGroup, ConfigPreset, Setting


def _is_not_objective(prop: DeviceProperty) -> bool:
    return not any(x in prop.device for x in prop.core.guessObjectiveDevices())


def _light_path_predicate(prop: DeviceProperty) -> bool | None:
    devtype = prop.deviceType()
    if devtype in (
        DeviceType.Camera,
        DeviceType.Core,
        DeviceType.AutoFocus,
        DeviceType.Stage,
        DeviceType.XYStage,
    ):
        return False
    if devtype == DeviceType.State:
        if "State" in prop.name or "ClosedPosition" in prop.name:
            return False
    if devtype == DeviceType.Shutter and prop.name == Keyword.State.value:
        return False
    if not _is_not_objective(prop):
        return False
    return None


class DualDevicePropertyTable(QWidget):
    valueChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # widgets --------------------------------------------------------------

        self._light_path_table = DevicePropertyTable()
        self._light_path_table.setRowsCheckable(True)
        self._light_path_table.valueChanged.connect(self.valueChanged)

        self._camera_table = DevicePropertyTable()
        self._camera_table.setRowsCheckable(True)
        self._camera_table.valueChanged.connect(self.valueChanged)

        # layout ------------------------------------------------------------

        light_path_group = QGroupBox("Light Path", self)
        layout = QVBoxLayout(light_path_group)
        layout.addWidget(self._light_path_table)

        camera_group = QGroupBox("Camera", self)
        layout = QVBoxLayout(camera_group)
        layout.addWidget(self._camera_table)

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.addWidget(light_path_group)
        splitter.addWidget(camera_group)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(splitter)

        # init ------------------------------------------------------------

        self.filterDevices()

    # --------------------------------------------------------------------- API
    def value(self) -> list[Setting]:
        """Return the union of checked settings from both panels."""
        # remove duplicates by converting to a dict keyed on (device, prop_name)
        settings = {
            (setting[0], setting[1]): setting
            for table in (self._light_path_table, self._camera_table)
            for setting in table.getCheckedProperties(visible_only=True)
        }
        return list(settings.values())

    def setValue(self, value: Iterable[Setting]) -> None:
        self._light_path_table.setValue(value)
        self._camera_table.setValue(value)

    def filterDevices(self) -> None:
        """Call ``filterDevices`` on *both* tables with the same arguments."""
        self._light_path_table.filterDevices(
            include_pre_init=False,
            include_read_only=False,
            predicate=_light_path_predicate,
        )
        self._camera_table.filterDevices(
            include_devices=[DeviceType.Camera],
            include_pre_init=False,
            include_read_only=False,
        )


class SettingValueDelegate(QStyledItemDelegate):
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


class _NameList(QGroupBox):
    """A group box that contains a toolbar and a QListView for cfg groups or presets."""

    def __init__(
        self, title: str, parent: QWidget | None, new_fn: Callable, list_view: QListView
    ) -> None:
        super().__init__(title, parent)

        # toolbar
        self._toolbar = QToolBar()
        self._toolbar.setIconSize(QSize(18, 18))
        self._toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

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
        self._model = cast("QConfigTreeModel", list_view.model())
        layout = QVBoxLayout(self)
        layout.addWidget(self._toolbar)
        layout.addWidget(list_view)

    def _is_groups(self) -> bool:
        """Check if this box is for groups."""
        return bool(self.title() == "Groups")

    def _remove(self) -> None:
        self._model.remove(self._view.currentIndex())

    def _dupe(self) -> None:
        idx = self._view.currentIndex()
        if idx.isValid():
            if self._is_groups():
                self._view.setCurrentIndex(self._model.duplicate_group(idx))
            else:
                self._view.setCurrentIndex(self._model.duplicate_preset(idx))


class ConfigGroupsEditor(QWidget):
    """Widget composed of two QListViews backed by a single tree model."""

    configChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = QConfigTreeModel()

        # widgets --------------------------------------------------------------

        self._group_view = QListView()
        self._group_view.setModel(self._model)
        group_box = _NameList("Groups", self, self._new_group, self._group_view)

        self._preset_view = QListView()
        self._preset_view.setModel(self._model)
        preset_box = _NameList("Presets", self, self._new_preset, self._preset_view)

        self._prop_table = DualDevicePropertyTable()

        # layout ------------------------------------------------------------

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(group_box)
        lv.addWidget(preset_box)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(left)
        lay.addWidget(self._prop_table)

        # signals ------------------------------------------------------------

        if sm := self._group_view.selectionModel():
            sm.currentChanged.connect(self._on_group_sel)
        if sm := self._preset_view.selectionModel():
            sm.currentChanged.connect(self._on_preset_sel)
        self._model.dataChanged.connect(self._on_model_data_changed)
        self._prop_table.valueChanged.connect(self._on_prop_table_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setData(self, data: Iterable[ConfigGroup]) -> None:
        """Set the configuration data to be displayed in the editor."""
        self._model.set_groups(data)
        self._prop_table.setValue([])
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
            self._prop_table.setValue([])
            return
        node = cast("_Node", current.internalPointer())
        if not node.is_preset:
            self._prop_table.setValue([])
            return
        preset = cast("ConfigPreset", node.payload)
        self._prop_table.setValue(preset.settings)

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
        new_settings = self._prop_table.value()
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
        self._prop_table.blockSignals(True)  # avoid feedback loop
        self._prop_table.setValue(preset.settings)
        self._prop_table.blockSignals(False)
