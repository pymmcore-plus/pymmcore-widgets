from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pymmcore_plus import DeviceType
from qtpy.QtCore import QModelIndex, QSize
from qtpy.QtWidgets import (
    QLineEdit,
    QSizePolicy,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from superqt import QIconifyIcon

from pymmcore_widgets._icons import DEVICE_TYPE_ICON, StandardIcon
from pymmcore_widgets._models import Device, QDevicePropertyModel
from pymmcore_widgets._models._q_device_prop_model import DevicePropertyFlatProxy

from ._checked_properties_proxy import CheckedProxy
from ._device_type_filter_proxy import DeviceTypeFilter

if TYPE_CHECKING:
    from collections.abc import Iterable

    from PyQt6.QtCore import pyqtSignal as Signal
    from PyQt6.QtGui import QAction
else:
    from qtpy.QtCore import QModelIndex, Signal


class _DeviceButtonToolbar(QToolBar):
    checkedDevicesChanged = Signal(set)
    readOnlyToggled = Signal(bool)
    preInitToggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        for device_type, icon_key in sorted(
            DEVICE_TYPE_ICON.items(), key=lambda x: x[0].name
        ):
            tooltip = device_type.name.replace("Device", " Devices")
            action = cast(
                "QAction",
                self.addAction(
                    QIconifyIcon(icon_key, color="gray"),
                    f"Show {tooltip}",
                    self._emit_selection,
                ),
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
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._dev_type_btns = _DeviceButtonToolbar(self)
        self._dev_type_btns.setIconSize(QSize(16, 16))
        self._tb2 = _PropertySearchToolbar(self)
        self._tb2.setIconSize(QSize(16, 16))
        self.setStyleSheet("QToolBar { border: none; };")

        self._model = QDevicePropertyModel()

        self._filtered_model = DeviceTypeFilter(allowed={DeviceType.Any}, parent=self)
        self._filtered_model.setSourceModel(self._model)

        self._flat_filtered_model = DevicePropertyFlatProxy()
        self._flat_filtered_model.setSourceModel(self._filtered_model)

        _checked = CheckedProxy(check_column=1)
        _checked.setSourceModel(self._model)
        self._flat_checked_model = DevicePropertyFlatProxy()
        self._flat_checked_model.setSourceModel(_checked)

        # Selected properties tree (shows only checked items)
        self.selected_tree = QTreeView(self)
        self.selected_tree.setModel(self._flat_checked_model)
        self.selected_tree.setSortingEnabled(True)
        self.selected_tree.setMaximumHeight(150)  # Limit height

        self.tree = QTreeView(self)
        # Start with TableView (flat proxy model)
        self.tree.setModel(self._flat_filtered_model)
        self.tree.setSortingEnabled(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.selected_tree)
        layout.addWidget(self._dev_type_btns)
        layout.addWidget(self._tb2)
        layout.addWidget(self.tree)

        self._dev_type_btns.checkedDevicesChanged.connect(
            self._filtered_model.setAllowedDeviceTypes
        )
        self._dev_type_btns.readOnlyToggled.connect(
            self._filtered_model.setReadOnlyVisible
        )
        self._dev_type_btns.preInitToggled.connect(
            self._filtered_model.setPreInitVisible
        )
        self._tb2.expandAllToggled.connect(self._expand_all)
        self._tb2.collapseAllToggled.connect(self.tree.collapseAll)
        self._tb2.filterStringChanged.connect(self._filtered_model.setFilterFixedString)
        self._tb2.viewModeToggled.connect(self._toggle_view_mode)

    def _expand_all(self) -> None:
        """Expand all items in the tree view."""
        self.tree.expandRecursively(QModelIndex())

    def _toggle_view_mode(self, is_tree_view: bool) -> None:
        """Toggle between TreeView and TableView modes."""
        if is_tree_view:
            # Switch to TreeView: use filter proxy directly
            self.tree.setModel(self._filtered_model)
            self.tree.setColumnHidden(1, True)  # Hide the second column (device type)
            self.tree.expandAll()
        else:
            # Switch to TableView: use flat proxy
            self.tree.setModel(self._flat_filtered_model)
            self.tree.setColumnHidden(1, False)  # Show the second column (property)

    def clear(self) -> None:
        """Clear the current selection."""
        # self.table.setValue([])

    def setChecked(self, settings: Iterable[tuple[str, str, str]]) -> None:
        """Set the checked state of the properties based on the given settings."""
        # self.table.setValue(settings)

    def setAvailableDevices(self, devices: Iterable[Device]) -> None:
        devices = list(devices)
        self._model.set_devices(devices)

        # Configure main tree view header
        if hh := self.tree.header():
            hh.setSectionResizeMode(hh.ResizeMode.ResizeToContents)

        # Configure selected properties tree view header
        if hh := self.selected_tree.header():
            hh.setSectionResizeMode(hh.ResizeMode.ResizeToContents)

        dev_types = {d.type for d in devices}
        self._dev_type_btns.setVisibleDeviceTypes(dev_types)

        # # hide some types that are often not immediately useful in this context
        # dev_types.difference_update(
        #     {DeviceType.AutoFocus, DeviceType.Core, DeviceType.Camera}
        # )
        # self._device_type_buttons.setCheckedDeviceTypes(dev_types)
