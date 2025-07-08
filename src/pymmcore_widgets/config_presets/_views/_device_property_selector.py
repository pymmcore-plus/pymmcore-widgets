from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar, cast

from pymmcore_plus import DeviceType
from qtpy.QtCore import QAbstractItemModel, QAbstractProxyModel, QModelIndex, QSize, Qt
from qtpy.QtWidgets import (
    QLineEdit,
    QSizePolicy,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets._icons import StandardIcon
from pymmcore_widgets._models import Device, QDevicePropertyModel
from pymmcore_widgets._models._py_config_model import DevicePropertySetting
from pymmcore_widgets._models._q_device_prop_model import DevicePropertyFlatProxy

from ._checked_properties_proxy import CheckedProxy
from ._device_type_filter_proxy import DeviceTypeFilter

if TYPE_CHECKING:
    from collections.abc import Iterable

    from PyQt6.QtCore import pyqtSignal as Signal
    from PyQt6.QtGui import QAction, QKeyEvent
else:
    from qtpy.QtCore import QModelIndex, Signal


class _DeviceButtonToolbar(QToolBar):
    checkedDevicesChanged = Signal(set)
    readOnlyToggled = Signal(bool)
    preInitToggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setIconSize(QSize(16, 16))
        for device_type in sorted(DeviceType, key=lambda x: x.name):
            if device_type in (DeviceType.Any, DeviceType.Unknown):
                continue

            tooltip = device_type.name.replace("Device", " Devices")
            icon = StandardIcon.for_device_type(device_type)
            action = cast(
                "QAction",
                self.addAction(icon.icon(), f"Show {tooltip}", self._emit_selection),
            )
            action.setCheckable(True)
            action.setChecked(True)
            action.setData(device_type)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        self.act_show_read_only = cast(
            "QAction",
            self.addAction(
                StandardIcon.READ_ONLY.icon(color="gray"),
                "Show Read-Only Properties",
                self.readOnlyToggled,
            ),
        )
        self.act_show_pre_init = cast(
            "QAction",
            self.addAction(
                StandardIcon.PRE_INIT.icon(color="gray"),
                "Show Pre-Init Properties",
                self.preInitToggled,
            ),
        )
        self.act_show_read_only.setCheckable(True)
        self.act_show_pre_init.setCheckable(True)
        self.act_show_read_only.setChecked(False)
        self.act_show_pre_init.setChecked(False)

    def _emit_selection(self) -> None:
        """Emit the checkedDevicesChanged signal."""
        self.checkedDevicesChanged.emit(self.checkedDeviceTypes())

    def setVisibleDeviceTypes(self, device_types: Iterable[DeviceType]) -> None:
        """Set the visibility of the device type buttons based on the given types."""
        for action in self.actions():
            if isinstance(data := action.data(), DeviceType):
                action.setVisible(data in device_types)

    def setCheckedDeviceTypes(self, device_types: Iterable[DeviceType]) -> None:
        """Set the checked state of the device type buttons based on the given types."""
        checked = self.checkedDeviceTypes()
        for action in self.actions():
            if isinstance(data := action.data(), DeviceType):
                action.setChecked(data in device_types)
        if checked != self.checkedDeviceTypes():
            self._emit_selection()

    def checkedDeviceTypes(self) -> set[DeviceType]:
        """Return the currently selected device types."""
        return {
            data
            for action in self.actions()
            if (action.isChecked() and action.isVisible())
            if isinstance(data := action.data(), DeviceType)
        }


class _PropertySearchToolbar(QToolBar):
    """A toolbar with expand/collapse all buttons and a search box."""

    expandAllToggled = Signal()
    collapseAllToggled = Signal()
    viewModeToggled = Signal(bool)  # True for TreeView, False for TableView

    filterStringChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setIconSize(QSize(16, 16))

        # Add toggle button for view mode
        self.act_toggle_view = cast(
            "QAction",
            self.addAction(
                StandardIcon.TABLE.icon(color="gray"),
                "Switch to Tree View",
                self._toggle_view_mode,
            ),
        )
        self.act_toggle_view.setCheckable(True)
        self.act_toggle_view.setChecked(False)  # Default to TableView

        self._le = QLineEdit(self)
        self._le.setMinimumWidth(160)
        self._le.setClearButtonEnabled(True)
        self._le.setPlaceholderText("Search properties...")
        self._le.textChanged.connect(self.filterStringChanged)
        self.addWidget(self._le)

        self.act_expand = cast(
            "QAction",
            self.addAction(
                StandardIcon.EXPAND.icon(),
                "Expand all",
                self.expandAllToggled,
            ),
        )
        self.act_collapse = cast(
            "QAction",
            self.addAction(
                StandardIcon.COLLAPSE.icon(),
                "Collapse all",
                self.collapseAllToggled,
            ),
        )
        # Initially hide expand/collapse actions (TableView is default)
        self.act_expand.setVisible(False)
        self.act_collapse.setVisible(False)

    def _toggle_view_mode(self) -> None:
        """Toggle between TreeView and TableView."""
        is_tree_view = self.act_toggle_view.isChecked()

        # Update button icon and tooltip
        if is_tree_view:
            self.act_toggle_view.setIcon(StandardIcon.TREE.icon())
            self.act_toggle_view.setText("Switch to Table View")
        else:
            self.act_toggle_view.setIcon(StandardIcon.TABLE.icon())
            self.act_toggle_view.setText("Switch to Tree View")

        # Show/hide expand/collapse actions
        self.act_expand.setVisible(is_tree_view)
        self.act_collapse.setVisible(is_tree_view)

        # Emit signal
        self.viewModeToggled.emit(is_tree_view)


class DevicePropertySelector(QWidget):
    checkedPropertiesChanged = Signal(tuple)  # tuple[DevicePropertySetting, ...]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # WIDGETS ------------------------

        self._dev_type_btns = dev_btns = _DeviceButtonToolbar(self)
        self._tb2 = _PropertySearchToolbar(self)

        self._model = QDevicePropertyModel()
        self._model.dataChanged.connect(self._on_model_data_changed)

        # Track currently-checked (device_label, property_name) pairs
        self._checked_props: set[tuple[str, str]] = set()

        self._filtered_model = DeviceTypeFilter(allowed={DeviceType.Any}, parent=self)
        self._filtered_model.setSourceModel(self._model)

        self._flat_filtered_model = DevicePropertyFlatProxy()
        self._flat_filtered_model.setSourceModel(self._filtered_model)

        _checked = CheckedProxy(check_column=1)
        _checked.setSourceModel(self._model)
        self._flat_checked_model = DevicePropertyFlatProxy()
        self._flat_checked_model.setSourceModel(_checked)

        # Selected properties tree (shows only checked items)
        self.selected_tree = _ShrinkingQTreeView(self)
        self.selected_tree.setModel(self._flat_checked_model)

        self.tree = _CheckableTreeView(self)
        self._toggle_view_mode(False)  # Start with TableView (flat proxy model)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(dev_btns)
        layout.addWidget(self._tb2)
        layout.addWidget(self.tree, 2)
        layout.addWidget(self.selected_tree)

        dev_btns.checkedDevicesChanged.connect(
            self._filtered_model.setAllowedDeviceTypes
        )
        dev_btns.readOnlyToggled.connect(self._filtered_model.setReadOnlyVisible)
        dev_btns.preInitToggled.connect(self._filtered_model.setPreInitVisible)
        self._tb2.expandAllToggled.connect(self._expand_all)
        self._tb2.collapseAllToggled.connect(self.tree.collapseAll)
        self._tb2.filterStringChanged.connect(self._filtered_model.setFilterFixedString)
        self._tb2.viewModeToggled.connect(self._toggle_view_mode)

    def _expand_all(self) -> None:
        """Expand all items in the tree view."""
        self.tree.expandRecursively(QModelIndex())

    def _on_model_data_changed(
        self, topLeft: QModelIndex, bottomRight: QModelIndex, roles: list[int]
    ) -> None:
        """Incrementally update the checke-property cache and emit when it changes."""
        if Qt.ItemDataRole.CheckStateRole not in roles:
            return

        changed = False

        # Helper to update the cache for a single index
        def _update(idx: QModelIndex) -> None:
            nonlocal changed
            prop = idx.data(Qt.ItemDataRole.UserRole)
            if not isinstance(prop, DevicePropertySetting):
                return
            is_checked = (
                self._model.data(idx, Qt.ItemDataRole.CheckStateRole)
                == Qt.CheckState.Checked
            )
            key = prop.key()
            if is_checked and key not in self._checked_props:
                self._checked_props.add(key)
                changed = True
            elif not is_checked and key in self._checked_props:
                self._checked_props.remove(key)
                changed = True

        # Iterate through all rows in the changed range
        parent = topLeft.parent()
        for row in range(topLeft.row(), bottomRight.row() + 1):
            idx = self._model.index(row, 0, parent)
            if not idx.isValid():
                continue
            _update(idx)
            # If idx is a device row, also inspect its children
            if not isinstance(
                idx.data(Qt.ItemDataRole.UserRole), DevicePropertySetting
            ):
                for child_row in range(self._model.rowCount(idx)):
                    _update(self._model.index(child_row, 0, idx))

        if changed:
            self.checkedPropertiesChanged.emit(tuple(self._checked_props))

    def _toggle_view_mode(self, is_tree_view: bool) -> None:
        """Toggle between TreeView and TableView modes."""
        if is_tree_view:
            # Switch to TreeView: use filter proxy directly
            self.tree.setModel(self._filtered_model)
            self.tree.setColumnHidden(1, True)  # Hide the second column (device type)
            self.tree.expandAll()
            self.tree.setRootIsDecorated(True)
            self.tree.setSortingEnabled(False)
        else:
            # Switch to TableView: use flat proxy
            self.tree.setModel(self._flat_filtered_model)
            self.tree.setColumnHidden(1, False)  # Show the second column (property)
            self.tree.setRootIsDecorated(False)
            self.tree.setSortingEnabled(True)

    def clear(self) -> None:
        """Clear the current selection."""
        # self.table.setValue([])

    def clearCheckedProperties(self) -> None:
        """Clear all checked properties."""
        # clear all checks
        for row in range(self._model.rowCount()):
            dev_idx = self._model.index(row, 0)
            for prop_row in range(self._model.rowCount(dev_idx)):
                prop_idx = self._model.index(prop_row, 0, dev_idx)
                self._model.setData(
                    prop_idx,
                    Qt.CheckState.Unchecked,
                    Qt.ItemDataRole.CheckStateRole,
                )
        self._checked_props.clear()
        self.checkedPropertiesChanged.emit(())
        return

    def setCheckedProperties(self, props: Iterable[DevicePropertySetting]) -> None:
        """Set the checked state of the properties based on the given settings."""
        self.clearCheckedProperties()
        props = list(props)

        to_check = defaultdict(set)
        for prop in props:
            to_check[prop.device_label].add(prop.property_name)

        for row in range(self._model.rowCount()):
            dev_idx = self._model.index(row, 0)
            dev = dev_idx.data(Qt.ItemDataRole.UserRole)
            if isinstance(dev, Device) and dev.label in to_check:
                for prop_row in range(self._model.rowCount(dev_idx)):
                    prop_idx = self._model.index(prop_row, 0, dev_idx)
                    prop = prop_idx.data(Qt.ItemDataRole.UserRole)
                    if (
                        isinstance(prop, DevicePropertySetting)
                        and prop.property_name in to_check[dev.label]
                    ):
                        self._model.setData(
                            prop_idx,
                            Qt.CheckState.Checked,
                            Qt.ItemDataRole.CheckStateRole,
                        )
        self._checked_props = {p.key() for p in props}
        self.checkedPropertiesChanged.emit(tuple(self._checked_props))

    def setAvailableDevices(self, devices: Iterable[Device]) -> None:
        devices = list(devices)
        self._model.set_devices(devices)

        # Configure main tree view header
        if hh := self.tree.header():
            hh.setSectionResizeMode(hh.ResizeMode.ResizeToContents)
            self.selected_tree.setColumnWidth(0, self.tree.columnWidth(0))

        dev_types = {d.type for d in devices}
        self._dev_type_btns.setVisibleDeviceTypes(dev_types)

        # hide some types that are often not immediately useful in this context
        dev_types.difference_update(
            {DeviceType.AutoFocus, DeviceType.Core, DeviceType.Camera}
        )
        self._dev_type_btns.setCheckedDeviceTypes(dev_types)


class _CheckableTreeView(QTreeView):
    """A QTreeView that allows toggling check state with Return/Enter key."""

    ACTION_KEYS: ClassVar[set[int]] = {Qt.Key.Key_Return, Qt.Key.Key_Enter}

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events, specifically Return/Enter to toggle check state."""
        if event.key() in self.ACTION_KEYS:
            current_index = self.currentIndex()
            if current_index.isValid():
                self._toggle_check_state(current_index)
                return
        super().keyPressEvent(event)

    def _toggle_check_state(self, index: QModelIndex) -> None:
        """Toggle the check state of the given index if it's a checkable property."""
        if not index.isValid():
            return

        # Get the data to check if this is a property item (not a device header)
        user_data = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(user_data, DevicePropertySetting):
            return

        # Get current check state
        current_state = index.data(Qt.ItemDataRole.CheckStateRole)
        if current_state is None:
            return

        # Toggle the state
        new_state = (
            Qt.CheckState.Unchecked
            if current_state == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )

        # If we're working with a proxy model, we need to map to the source model
        model = index.model()
        if model is not None:
            # Try to get the source model if this is a proxy
            source_index = index
            if isinstance(model, QAbstractProxyModel):
                source_index = model.mapToSource(source_index)
                model = model.sourceModel()
                if model is None:
                    return

            # Set the new state on the source model
            model.setData(source_index, new_state, Qt.ItemDataRole.CheckStateRole)


class _ShrinkingQTreeView(_CheckableTreeView):
    """A QTreeView that shrinks to fit its contents."""

    ACTION_KEYS: ClassVar[set[int]] = {Qt.Key.Key_Backspace}

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.updateGeometry()
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)

    def sizeHint(self) -> QSize:
        """Return the size hint based on the contents."""
        size = super().sizeHint()
        size.setHeight(50)
        if (model := self.model()) and (nrows := model.rowCount()) > 0:
            size.setHeight(self.sizeHintForRow(0) * nrows + 2 * self.frameWidth() + 20)
        return size.boundedTo(QSize(10000, 220))

    def setModel(self, model: QAbstractItemModel | None) -> None:
        """Set the model and connect signals to update geometry."""
        super().setModel(model)
        if model is not None:
            model.modelReset.connect(self.updateGeometry)
            model.rowsInserted.connect(self.updateGeometry)
            model.rowsRemoved.connect(self.updateGeometry)
