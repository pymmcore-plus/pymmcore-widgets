from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pymmcore_plus import DeviceType
from qtpy.QtCore import QModelIndex, QSize, QSortFilterProxyModel, Qt, Signal
from qtpy.QtWidgets import (
    QLineEdit,
    QSizePolicy,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from superqt import QIconifyIcon

from pymmcore_widgets._icons import DEVICE_TYPE_ICON, PROPERTY_FLAG_ICON
from pymmcore_widgets._models import Device, DevicePropertySetting, QDevicePropertyModel

if TYPE_CHECKING:
    from collections.abc import Iterable

    from PyQt6.QtGui import QAction


# TODO: Allow GUI control of parameters
class DeviceTypeFilter(QSortFilterProxyModel):
    def __init__(self, allowed: set[DeviceType], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setRecursiveFilteringEnabled(True)
        self.allowed = allowed  # e.g. {"Camera", "Shutter"}
        self.show_read_only = False
        self.show_pre_init = False

    def _device_allowed_for_index(self, idx: QModelIndex) -> bool:
        """Walk up to the closest Device ancestor and check its type."""
        while idx.isValid():
            data = idx.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, Device):
                return DeviceType.Any in self.allowed or data.type in self.allowed
            idx = idx.parent()  # keep climbing
        return True  # no Device ancestor (root rows etc.)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if (sm := self.sourceModel()) is None:
            return super().filterAcceptsRow(source_row, source_parent)

        idx = sm.index(source_row, 0, source_parent)

        # 1. Bail out whole subtree when its Device type is disallowed
        if not self._device_allowed_for_index(idx):
            return False

        data = idx.data(Qt.ItemDataRole.UserRole)

        # 2. Per-property flags
        if isinstance(data, DevicePropertySetting):
            if data.is_read_only and not self.show_read_only:
                return False
            if data.is_pre_init and not self.show_pre_init:
                return False
            if data.is_advanced:
                return False

        # 3. Text / regex filter (superclass logic)
        text_match = super().filterAcceptsRow(source_row, source_parent)

        # 4. Special rule for Device rows: hide when it ends up child-less
        if isinstance(data, Device):
            # If the device name itself matches, keep it only if at least
            # one child survives *after all rules above*.
            if text_match:
                for i in range(sm.rowCount(idx)):
                    if self.filterAcceptsRow(i, idx):  # child survives
                        return True
                # no surviving children -> drop the device row
                return False

            # If the device row didn't match the text filter, just return
            # False here; Qt will re-accept it automatically if any child
            # is accepted (thanks to recursiveFilteringEnabled).
            return False

        # 5. For non-Device rows, the decision is simply the text match
        return text_match

    def setReadOnlyVisible(self, show: bool) -> None:
        """Set whether to show read-only properties."""
        if self.show_read_only != show:
            self.show_read_only = show
            self.invalidate()

    def setPreInitVisible(self, show: bool) -> None:
        """Set whether to show pre-init properties."""
        if self.show_pre_init != show:
            self.show_pre_init = show
            self.invalidate()

    def setAllowedDeviceTypes(self, allowed: set[DeviceType]) -> None:
        """Set the allowed device types."""
        if self.allowed != allowed:
            self.allowed = allowed
            self.invalidate()


class DeviceTypeButtons(QToolBar):
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
                QIconifyIcon(PROPERTY_FLAG_ICON["read-only"], color="gray"),
                "Show Read-Only Properties",
                self.readOnlyToggled,
            ),
        )
        self.act_show_pre_init = cast(
            "QAction",
            self.addAction(
                QIconifyIcon(PROPERTY_FLAG_ICON["pre-init"], color="gray"),
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


class DeviceFilterButtons(QToolBar):
    """A toolbar with buttons to filter device types."""

    expandAllToggled = Signal()
    collapseAllToggled = Signal()

    filterStringChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.act_expand = cast(
            "QAction",
            self.addAction(
                QIconifyIcon("mdi:expand-horizontal", color="gray"),
                "Expand all",
                self.expandAllToggled,
            ),
        )
        self.act_collapse = cast(
            "QAction",
            self.addAction(
                QIconifyIcon("mdi:collapse-horizontal", color="gray"),
                "Collapse all",
                self.collapseAllToggled,
            ),
        )
        self._le = QLineEdit(self)
        self._le.setMinimumWidth(160)
        self._le.setClearButtonEnabled(True)
        self._le.setPlaceholderText("Search properties...")
        self._le.textChanged.connect(self.filterStringChanged)
        self.addWidget(self._le)


class DevicePropertySelector(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = model = QDevicePropertyModel()
        self._proxy = proxy = DeviceTypeFilter(allowed={DeviceType.Any}, parent=self)
        proxy.setSourceModel(model)
        self._dev_type_btns = DeviceTypeButtons(self)
        self._dev_type_btns.setIconSize(QSize(16, 16))
        self._tb2 = DeviceFilterButtons(self)
        self._tb2.setIconSize(QSize(16, 16))
        self.setStyleSheet("QToolBar { border: none; };")
        self.tree = QTreeView(self)
        self.tree.setModel(proxy)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._dev_type_btns)
        layout.addWidget(self._tb2)
        layout.addWidget(self.tree)

        self._dev_type_btns.checkedDevicesChanged.connect(proxy.setAllowedDeviceTypes)
        self._dev_type_btns.readOnlyToggled.connect(self._proxy.setReadOnlyVisible)
        self._dev_type_btns.preInitToggled.connect(self._proxy.setPreInitVisible)
        self._tb2.expandAllToggled.connect(self._expand_all)
        self._tb2.collapseAllToggled.connect(self.tree.collapseAll)
        self._tb2.filterStringChanged.connect(proxy.setFilterFixedString)

    def _expand_all(self) -> None:
        """Expand all items in the tree view."""
        self.tree.expandRecursively(QModelIndex())

    def clear(self) -> None:
        """Clear the current selection."""
        # self.table.setValue([])

    def setChecked(self, settings: Iterable[tuple[str, str, str]]) -> None:
        """Set the checked state of the properties based on the given settings."""
        # self.table.setValue(settings)

    def setAvailableDevices(self, devices: Iterable[Device]) -> None:
        devices = list(devices)
        self._model.set_devices(devices)
        self.tree.setColumnHidden(1, True)  # Hide the second column (device type)
        self.tree.setHeaderHidden(True)

        dev_types = {d.type for d in devices}
        self._dev_type_btns.setVisibleDeviceTypes(dev_types)
        # # hide some types that are often not immediately useful in this context
        # dev_types.difference_update(
        #     {DeviceType.AutoFocus, DeviceType.Core, DeviceType.Camera}
        # )
        # self._device_type_buttons.setCheckedDeviceTypes(dev_types)
