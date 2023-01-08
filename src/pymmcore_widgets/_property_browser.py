from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from ._device_property_table import DevicePropertyTable
from ._device_type_filter import DeviceTypeFilters


class PropertyBrowser(QDialog):
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
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ):
        super().__init__(parent=parent)
        self._mmc = mmcore or CMMCorePlus.instance()

        self._prop_table = DevicePropertyTable(mmcore=mmcore)
        self._device_filters = DeviceTypeFilters()
        self._device_filters.filtersChanged.connect(self._update_filter)

        self._filter_text = QLineEdit()
        self._filter_text.setClearButtonEnabled(True)
        self._filter_text.setPlaceholderText("Filter by device or property name...")
        self._filter_text.textChanged.connect(self._update_filter)

        right = QWidget()
        right.setLayout(QVBoxLayout())
        right.layout().addWidget(self._filter_text)
        right.layout().addWidget(self._prop_table)

        left = QWidget()
        left.setLayout(QVBoxLayout())
        left.layout().addWidget(self._device_filters)

        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(6, 12, 12, 12)
        self.layout().setSpacing(0)
        self.layout().addWidget(left)
        self.layout().addWidget(right)
        self._mmc.events.systemConfigurationLoaded.connect(self._update_filter)

        self.destroyed.connect(self._disconnect)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._update_filter)

    def _update_filter(self) -> None:
        filt = self._filter_text.text().lower()
        self._prop_table.filterDevices(
            filt, self._device_filters.filters(), self._device_filters.showReadOnly()
        )


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    CMMCorePlus.instance().loadSystemConfiguration()
    app = QApplication([])
    table = PropertyBrowser()
    table.show()

    app.exec_()
