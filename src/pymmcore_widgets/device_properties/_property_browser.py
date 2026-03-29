from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtCore import Slot
from qtpy.QtWidgets import QLineEdit, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from collections.abc import Iterable

from ._device_property_table import DevicePropertyTable
from ._device_type_toolbar import DeviceButtonToolbar


class PropertyBrowser(QWidget):
    """A Widget to browse and change properties of all devices.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget. By default, None.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
        exclude_device_types: Iterable[DeviceType] = (),
    ):
        super().__init__(parent=parent)
        self._mmc = mmcore or CMMCorePlus.instance()

        self._prop_table = DevicePropertyTable(mmcore=self._mmc)
        self._device_toolbar = DeviceButtonToolbar()
        if exclude_device_types:
            self._device_toolbar.setVisibleDeviceTypes(
                set(DeviceType) - set(exclude_device_types)
            )
        self._device_toolbar.checkedDevicesChanged.connect(self._update_filter)
        self._device_toolbar.readOnlyToggled.connect(self._update_filter)
        self._device_toolbar.preInitToggled.connect(self._update_filter)

        self._filter_text = QLineEdit()
        self._filter_text.setClearButtonEnabled(True)
        self._filter_text.setPlaceholderText("Filter by device or property name...")
        self._filter_text.textChanged.connect(self._update_filter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._device_toolbar)
        layout.addWidget(self._filter_text)
        layout.addWidget(self._prop_table)

        self._mmc.events.systemConfigurationLoaded.connect(self._update_filter)
        self.destroyed.connect(self._disconnect)
        self._update_filter()

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._update_filter)

    @Slot()
    def _update_filter(self) -> None:
        included = self._device_toolbar.checkedDeviceTypes()
        if not included:
            # no device types selected -> hide all rows
            for row in range(self._prop_table.rowCount()):
                self._prop_table.hideRow(row)
            return
        filt = self._filter_text.text().lower()
        self._prop_table.filterDevices(
            filt,
            include_devices=included,
            include_read_only=self._device_toolbar.act_show_read_only.isChecked(),
            include_pre_init=self._device_toolbar.act_show_pre_init.isChecked(),
        )


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    CMMCorePlus.instance().loadSystemConfiguration()
    app = QApplication([])
    table = PropertyBrowser()
    table.show()

    app.exec()
