from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar, cast

from pymmcore_plus import DeviceType
from qtpy.QtCore import QAbstractProxyModel, QModelIndex, QSignalBlocker, QSize, Qt
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QSizePolicy,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from superqt.iconify import QIconifyIcon

from pymmcore_widgets._icons import StandardIcon
from pymmcore_widgets._models import Device, QDevicePropertyModel
from pymmcore_widgets._models._py_config_model import DevicePropertySetting
from pymmcore_widgets._models._q_device_prop_model import DevicePropertyFlatProxy
from pymmcore_widgets.device_properties._device_type_toolbar import DeviceButtonToolbar

from ._checked_properties_proxy import CheckedProxy
from ._device_type_filter_proxy import DeviceTypeFilter

if TYPE_CHECKING:
    from collections.abc import Iterable

    from PyQt6.QtCore import pyqtSignal as Signal
    from PyQt6.QtGui import QAction, QKeyEvent
else:
    from qtpy.QtCore import Signal


class _PropertySearchToolbar(QToolBar):
    """A toolbar with expand/collapse all buttons and a search box."""

    expandAllToggled = Signal()
    collapseAllToggled = Signal()
    viewModeToggled = Signal(bool)  # True for TreeView, False for TableView
    checkedOnlyToggled = Signal(bool)

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

        # Show checked only toggle
        self.act_checked_only = cast(
            "QAction",
            self.addAction(
                QIconifyIcon("mdi:filter-check-outline", color="gray"),
                "Show Checked Only",
                self._toggle_checked_only,
            ),
        )
        self.act_checked_only.setCheckable(True)
        self.act_checked_only.setChecked(False)

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
        is_tree = self.act_toggle_view.isChecked()
        if is_tree:
            self.act_toggle_view.setIcon(StandardIcon.TREE.icon())
            self.act_toggle_view.setText("Switch to Table View")
        else:
            self.act_toggle_view.setIcon(StandardIcon.TABLE.icon())
            self.act_toggle_view.setText("Switch to Tree View")
        self.act_expand.setVisible(is_tree)
        self.act_collapse.setVisible(is_tree)
        self.viewModeToggled.emit(is_tree)

    def _toggle_checked_only(self) -> None:
        """Toggle between showing all properties and checked-only."""
        self.checkedOnlyToggled.emit(self.act_checked_only.isChecked())


class DevicePropertySelector(QWidget):
    checkedPropertiesChanged = Signal(tuple)  # tuple[DevicePropertySetting, ...]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._dev_type_btns = dev_btns = DeviceButtonToolbar(self)
        self._tb2 = _PropertySearchToolbar(self)

        self._model = QDevicePropertyModel()
        self._model.dataChanged.connect(self._on_model_data_changed)

        # Track currently-checked (device_label, property_name) pairs
        self._checked_settings: list[DevicePropertySetting] = []

        self._filtered_model = DeviceTypeFilter(allowed={DeviceType.Any}, parent=self)
        self._filtered_model.setSourceModel(self._model)

        self._flat_filtered_model = DevicePropertyFlatProxy()
        self._flat_filtered_model.setSourceModel(self._filtered_model)

        self._checked_proxy = CheckedProxy(check_column=1, parent=self)
        self._checked_proxy.setSourceModel(self._model)
        self._flat_checked_model = DevicePropertyFlatProxy()
        self._flat_checked_model.setSourceModel(self._checked_proxy)

        self._showing_checked_only = False

        self.tree = _CheckableTreeView(self)
        self._toggle_view_mode(False)  # Start with TableView (flat proxy model)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(dev_btns)
        layout.addWidget(self._tb2)
        layout.addWidget(self.tree, 2)

        dev_btns.checkedDevicesChanged.connect(
            self._filtered_model.setAllowedDeviceTypes
        )
        dev_btns.readOnlyToggled.connect(self._filtered_model.setReadOnlyVisible)
        dev_btns.preInitToggled.connect(self._filtered_model.setPreInitVisible)
        self._tb2.expandAllToggled.connect(self._expand_all)
        self._tb2.collapseAllToggled.connect(self.tree.collapseAll)
        self._tb2.filterStringChanged.connect(self._filtered_model.setFilterFixedString)
        self._tb2.viewModeToggled.connect(self._toggle_view_mode)
        self._tb2.checkedOnlyToggled.connect(self._toggle_checked_only)

    def _expand_all(self) -> None:
        """Expand all items in the tree view."""
        self.tree.expandRecursively(QModelIndex())

    def _on_model_data_changed(
        self, topLeft: QModelIndex, bottomRight: QModelIndex, roles: list[int]
    ) -> None:
        """Incrementally update the check-property cache and emit when it changes."""
        if Qt.ItemDataRole.CheckStateRole not in roles:
            return

        checked_keys = {p.key() for p in self._checked_settings}
        changed = False

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
            if is_checked and key not in checked_keys:
                self._checked_settings.append(prop)
                checked_keys.add(key)
                changed = True
            elif not is_checked and key in checked_keys:
                self._checked_settings = [
                    p for p in self._checked_settings if p.key() != key
                ]
                checked_keys.discard(key)
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
            self.checkedPropertiesChanged.emit(tuple(self._checked_settings))

    def _toggle_view_mode(self, is_tree_view: bool) -> None:
        """Toggle between TreeView and TableView modes."""
        if self._showing_checked_only:
            return  # checked-only always uses flat checked model
        self._apply_view_mode(is_tree_view)

    def _apply_view_mode(self, is_tree_view: bool) -> None:
        """Apply the tree/table view mode to the tree widget."""
        if is_tree_view:
            self.tree.setModel(self._filtered_model)
            self.tree.setColumnHidden(1, True)
            self.tree.expandAll()
            self.tree.setRootIsDecorated(True)
            self.tree.setSortingEnabled(False)
        else:
            self.tree.setModel(self._flat_filtered_model)
            self.tree.setColumnHidden(1, False)
            self.tree.setRootIsDecorated(False)
            self.tree.setSortingEnabled(True)

    def _toggle_checked_only(self, checked_only: bool) -> None:
        """Toggle between showing all properties and checked-only."""
        self._showing_checked_only = checked_only
        if checked_only:
            self.tree.setModel(self._flat_checked_model)
            self.tree.setColumnHidden(1, False)
            self.tree.setRootIsDecorated(False)
            self.tree.setSortingEnabled(True)
        else:
            self._apply_view_mode(self._tb2.act_toggle_view.isChecked())
        enabled = not checked_only
        self._tb2.act_toggle_view.setEnabled(enabled)
        self._tb2.act_expand.setEnabled(enabled)
        self._tb2.act_collapse.setEnabled(enabled)
        self._dev_type_btns.setEnabled(enabled)

    def checkedProperties(self) -> tuple[DevicePropertySetting, ...]:
        return tuple(self._checked_settings)

    def clearCheckedProperties(self) -> None:
        """Clear all checked properties."""
        with QSignalBlocker(self._model):
            for row in range(self._model.rowCount()):
                dev_idx = self._model.index(row, 0)
                for prop_row in range(self._model.rowCount(dev_idx)):
                    prop_idx = self._model.index(prop_row, 0, dev_idx)
                    self._model.setData(
                        prop_idx,
                        Qt.CheckState.Unchecked,
                        Qt.ItemDataRole.CheckStateRole,
                    )
        self._checked_settings.clear()
        self._emit_model_data_changed()
        self.checkedPropertiesChanged.emit(())

    def setCheckedProperties(self, props: Iterable[DevicePropertySetting]) -> None:
        """Set the checked state of the properties based on the given settings."""
        props = list(props)
        to_check: dict[str, set[str]] = defaultdict(set)
        for prop in props:
            to_check[prop.device_label].add(prop.property_name)

        with QSignalBlocker(self._model):
            for row in range(self._model.rowCount()):
                dev_idx = self._model.index(row, 0)
                dev = dev_idx.data(Qt.ItemDataRole.UserRole)
                dev_props = (
                    to_check.get(dev.label, set()) if isinstance(dev, Device) else set()
                )
                for prop_row in range(self._model.rowCount(dev_idx)):
                    prop_idx = self._model.index(prop_row, 0, dev_idx)
                    prop = prop_idx.data(Qt.ItemDataRole.UserRole)
                    state = (
                        Qt.CheckState.Checked
                        if isinstance(prop, DevicePropertySetting)
                        and prop.property_name in dev_props
                        else Qt.CheckState.Unchecked
                    )
                    self._model.setData(prop_idx, state, Qt.ItemDataRole.CheckStateRole)
        self._checked_settings = list(props)
        self._emit_model_data_changed()
        self.checkedPropertiesChanged.emit(tuple(self._checked_settings))

    def _emit_model_data_changed(self) -> None:
        """Emit a single dataChanged covering all properties."""
        n = self._model.rowCount()
        if n > 0:
            top = self._model.index(0, 0)
            bottom = self._model.index(n - 1, 0)
            self._model.dataChanged.emit(top, bottom, [Qt.ItemDataRole.CheckStateRole])

    def setAvailableDevices(self, devices: Iterable[Device]) -> None:
        devices = list(devices)
        self._model.set_devices(devices)

        # Configure main tree view header
        if hh := self.tree.header():
            hh.setSectionResizeMode(hh.ResizeMode.ResizeToContents)

        dev_types = {d.type for d in devices}
        self._dev_type_btns.setVisibleDeviceTypes(dev_types)

        # hide some types that are often not immediately useful in this context
        dev_types.difference_update(
            {DeviceType.AutoFocus, DeviceType.Core, DeviceType.Camera}
        )
        self._dev_type_btns.setCheckedDeviceTypes(dev_types)

    @classmethod
    def promptForProperties(
        cls, parent: QWidget | None = None, devices: Iterable[Device] | None = None
    ) -> tuple[DevicePropertySetting, ...]:
        """Prompt the user to select properties from a dialog."""
        dialog = QDialog(
            parent,
            Qt.WindowType.Sheet
            | Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.FramelessWindowHint,
        )
        dialog.setWindowTitle("Select Properties")
        dialog.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        dialog.setModal(True)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)

        selector = cls(dialog)
        if devices:
            selector.setAvailableDevices(devices)

        layout = QVBoxLayout(dialog)
        layout.addWidget(selector)
        layout.addWidget(btns)

        # resize the dialog to fill 80% of the parent's size
        if parent:
            size = parent.size()
            dialog.resize(int(size.width() * 0.8), int(size.height() * 0.8))

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return tuple(selector.checkedProperties())
        return ()


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

        if not isinstance(index.data(Qt.ItemDataRole.UserRole), DevicePropertySetting):
            return

        current_state = index.data(Qt.ItemDataRole.CheckStateRole)
        if current_state is None:
            return

        new_state = (
            Qt.CheckState.Unchecked
            if current_state == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )

        # Unwrap proxy models to reach the source
        model = index.model()
        source_index = index
        while isinstance(model, QAbstractProxyModel):
            source_index = model.mapToSource(source_index)
            model = model.sourceModel()
        if model is not None:
            model.setData(source_index, new_state, Qt.ItemDataRole.CheckStateRole)
