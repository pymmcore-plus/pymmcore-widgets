from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pymmcore_plus import DeviceType
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import QSizePolicy, QToolBar, QWidget

from pymmcore_widgets._icons import StandardIcon

if TYPE_CHECKING:
    from collections.abc import Iterable

    from PyQt6.QtGui import QAction
    from qtpy.QtCore import Signal
else:
    from qtpy.QtCore import Signal


class DeviceButtonToolbar(QToolBar):
    """Toolbar with icon buttons for filtering by device type."""

    checkedDevicesChanged = Signal(set)
    readOnlyToggled = Signal(bool)
    preInitToggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setIconSize(QSize(16, 16))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        _priority = [
            DeviceType.Core,
            DeviceType.CameraDevice,
            DeviceType.StageDevice,
            DeviceType.XYStageDevice,
            DeviceType.StateDevice,
            DeviceType.ShutterDevice,
        ]
        _priority_set = set(_priority)
        _rest = sorted(
            (
                d
                for d in DeviceType
                if d not in _priority_set | {DeviceType.Any, DeviceType.Unknown}
            ),
            key=lambda x: x.name,
        )
        for device_type in _priority + _rest:
            label = device_type.name.replace("Device", "")
            icon = StandardIcon.for_device_type(device_type)
            action = cast(
                "QAction",
                self.addAction(icon.icon(), label, self._emit_selection),
            )
            action.setCheckable(True)
            action.setChecked(True)
            action.setData(device_type)

        self.addSeparator()
        self.addAction("All", self._select_all)
        self.addAction("None", self._select_none)

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
        # Show these two as icon-only
        for act in (self.act_show_read_only, self.act_show_pre_init):
            if btn := self.widgetForAction(act):
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

    def _emit_selection(self) -> None:
        """Emit the checkedDevicesChanged signal."""
        self.checkedDevicesChanged.emit(self.checkedDeviceTypes())

    def setVisibleDeviceTypes(self, device_types: Iterable[DeviceType]) -> None:
        """Set the visibility of the device type buttons."""
        for action in self.actions():
            if isinstance(data := action.data(), DeviceType):
                action.setVisible(data in device_types)

    def setCheckedDeviceTypes(self, device_types: Iterable[DeviceType]) -> None:
        """Set the checked state of the device type buttons."""
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

    def _select_all(self) -> None:
        """Check all visible device type buttons."""
        for action in self.actions():
            if isinstance(action.data(), DeviceType) and action.isVisible():
                action.setChecked(True)
        self._emit_selection()

    def _select_none(self) -> None:
        """Uncheck all device type buttons."""
        for action in self.actions():
            if isinstance(action.data(), DeviceType):
                action.setChecked(False)
        self._emit_selection()
