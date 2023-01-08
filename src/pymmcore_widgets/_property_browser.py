from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon

from pymmcore_widgets._channel_group_widget import ChannelGroupWidget
from pymmcore_widgets._property_widget import PropertyWidget

from ._device_property_table import ICONS, DevicePropertyTable
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

        self._prop_table = PropTable(mmcore=mmcore)

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


class PropTable(DevicePropertyTable):
    """Use 'ChannelGroupWidget' for the "Core-ChannelGroup" property.

    This way the "Core-ChannelGroup" property widget in the PropertyBrowser
    if fully connected to the necessary core signals: propertyChanged,
    channelGroupChanged, configGroupDeleted and configDefined.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        enable_property_widgets: bool = True,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(
            parent=parent,
            enable_property_widgets=enable_property_widgets,
            mmcore=mmcore,
        )

    def _rebuild_table(self) -> None:
        self.clearContents()
        props = list(self._mmc.iterProperties(as_object=True))
        self.setRowCount(len(props))
        for i, prop in enumerate(props):

            item = QTableWidgetItem(f"{prop.device}-{prop.name}")
            item.setData(self.PROP_ROLE, prop)
            # TODO: make sure to add icons for all possible device types
            icon_string = ICONS.get(prop.deviceType(), None)
            if icon_string:
                item.setIcon(icon(icon_string, color="Gray"))
            self.setItem(i, 0, item)

            if prop.device == "Core" and prop.name == "ChannelGroup":
                wdg = ChannelGroupWidget(mmcore=self._mmc)
            else:
                wdg = PropertyWidget(prop.device, prop.name, mmcore=self._mmc)
            self.setCellWidget(i, 1, wdg)
            if not self._prop_widgets_enabled:
                wdg.setEnabled(False)

            if prop.isReadOnly():
                # TODO: make this more theme aware
                item.setBackground(QColor("#AAA"))
                wdg.setStyleSheet("QLabel { background-color : #AAA }")

        self.resizeColumnsToContents()
        self.setRowsCheckable(self._rows_checkable)
        # TODO: install eventFilter to prevent mouse wheel from scrolling sliders
