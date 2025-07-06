from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pymmcore_plus import DeviceType
from qtpy.QtCore import QModelIndex, QSize, Signal
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
from pymmcore_widgets._models import Device, QDevicePropertyModel
from pymmcore_widgets._models._q_device_prop_model import DevicePropertyFlatProxy

from ._device_type_filter_proxy import DeviceTypeFilter

if TYPE_CHECKING:
    from collections.abc import Iterable

    from PyQt6.QtGui import QAction


# TODO: Allow GUI control of parameters
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

        self._dev_type_btns = DeviceTypeButtons(self)
        self._dev_type_btns.setIconSize(QSize(16, 16))
        self._tb2 = DeviceFilterButtons(self)
        self._tb2.setIconSize(QSize(16, 16))
        self.setStyleSheet("QToolBar { border: none; };")

        self.tree = QTreeView(self)

        self._model = QDevicePropertyModel()

        # 1. Filter first - keeps device/property semantics intact
        self._proxy = DeviceTypeFilter(allowed={DeviceType.Any}, parent=self)
        self._proxy.setSourceModel(self._model)

        # 2. Then optionally flatten the (already-filtered) tree
        self._flat_proxy = DevicePropertyFlatProxy()
        self._flat_proxy.setSourceModel(self._proxy)

        # 3. The view consumes the flattening proxy
        self.tree.setModel(self._flat_proxy)
        self.tree.setSortingEnabled(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._dev_type_btns)
        layout.addWidget(self._tb2)
        layout.addWidget(self.tree)

        self._dev_type_btns.checkedDevicesChanged.connect(
            self._proxy.setAllowedDeviceTypes
        )
        self._dev_type_btns.readOnlyToggled.connect(self._proxy.setReadOnlyVisible)
        self._dev_type_btns.preInitToggled.connect(self._proxy.setPreInitVisible)
        self._tb2.expandAllToggled.connect(self._expand_all)
        self._tb2.collapseAllToggled.connect(self.tree.collapseAll)
        self._tb2.filterStringChanged.connect(self._proxy.setFilterFixedString)

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
        # self.tree.setColumnHidden(1, True)  # Hide the second column (device type)
        # self.tree.setHeaderHidden(True)
        if hh := self.tree.header():
            hh.setSectionResizeMode(hh.ResizeMode.ResizeToContents)

        dev_types = {d.type for d in devices}
        self._dev_type_btns.setVisibleDeviceTypes(dev_types)

        # # hide some types that are often not immediately useful in this context
        # dev_types.difference_update(
        #     {DeviceType.AutoFocus, DeviceType.Core, DeviceType.Camera}
        # )
        # self._device_type_buttons.setCheckedDeviceTypes(dev_types)
