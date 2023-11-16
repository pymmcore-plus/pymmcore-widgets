from __future__ import annotations

from typing import Any, cast

from pymmcore_plus import CMMCorePlus, DeviceProperty
from pymmcore_plus.model import Setting
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

from pymmcore_widgets._device_property_table import DevicePropertyTable
from pymmcore_widgets._device_type_filter import DeviceTypeFilters
from pymmcore_widgets._property_widget import PropertyWidget

FIXED = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
PX = "px"
ID = "id"
PX_SIZE = "pixel_size"
PROP = "properties"
NEW = "New"
DEV_PROP_ROLE = QTableWidgetItem.ItemType.UserType + 1


class PropertySelector(QWidget):
    """A Widget to select and view a list of micromanager (device, property, value).

    Evertytime the checkbox of the DevicePropertyTable is checked or unchecked, or
    the value of the PropertyWidget in the table changes, a `valueChanged` signal is
    emitted with the list of checked (device, property, value).
    """

    valueChanged = Signal(object)

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ):
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        # property table (right wdg)
        self._prop_viewer = _PropertyViewerTable(mmcore=self._mmc)

        self._filter_text = QLineEdit()
        self._filter_text.setClearButtonEnabled(True)
        self._filter_text.setPlaceholderText("Filter by device or property name...")
        self._filter_text.textChanged.connect(self._update_filter)

        self._prop_table = DevicePropertyTable(
            connect_core=False, enable_property_widgets=False
        )
        self._prop_table.setRowsCheckable(True)

        table_and_filter = QWidget()
        table_and_filter_layout = QVBoxLayout(table_and_filter)
        table_and_filter_layout.addWidget(self._filter_text)
        table_and_filter_layout.addWidget(self._prop_table)

        splitter = QSplitter(Qt.Orientation.Vertical)
        # avoid splitter hiding completely widgets
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._prop_viewer)
        splitter.addWidget(table_and_filter)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(splitter)

        self._device_filters = DeviceTypeFilters()
        self._device_filters.filtersChanged.connect(self._update_filter)
        self._device_filters.setShowReadOnly(False)
        self._device_filters._read_only_checkbox.hide()
        self._device_filters.setShowPreInitProps(False)
        self._device_filters._pre_init_checkbox.hide()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self._device_filters)

        # central widget
        central_wdg = QWidget()
        central_layout = QHBoxLayout(central_wdg)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(left)
        central_layout.addWidget(right)

        # main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(central_wdg)

        self._prop_viewer.setMinimumHeight(int(right.minimumSizeHint().height() / 2))

        # connect
        self._mmc.events.systemConfigurationLoaded.connect(self._update_filter)
        self._prop_table.itemChanged.connect(self._on_item_changed)

        self.destroyed.connect(self._disconnect)

    # -------------- Public API --------------

    def value(self) -> list[Setting]:
        """Return the list of checked (device, property, value).

        Parameters
        ----------
        value : list[Setting][pymmcore_plus.model.Setting]
            List of (device, property, value) to be checked in the DevicePropertyTable.
        """
        return [
            Setting(dev, prop, val)
            for dev, prop, val in self._prop_table.getCheckedProperties()
        ]

    def setValue(self, value: list[Setting]) -> None:
        """Set the (device, property) to be checked in the DevicePropertyTable.

        Parameters
        ----------
        value : list[Setting][pymmcore_plus.model.Setting]
            List of (device, property, value) to be checked in the DevicePropertyTable.
        """
        # if value is empty, uncheck all the rows
        if not value:
            self._prop_table.uncheckAll()
            return

        # Convert value to a dictionary for faster lookups
        value_dict = {
            (setting.device_name, setting.property_name): setting.property_value
            for setting in value
        }

        # check only the rows that are in value
        for row in range(self._prop_table.rowCount()):
            dev_prop = cast(
                DeviceProperty,
                self._prop_table.item(row, 0).data(self._prop_table.PROP_ROLE),
            )
            val_wdg = cast(PropertyWidget, self._prop_table.cellWidget(row, 1))

            with signals_blocked(self._prop_table):
                # check if the device-property is in value
                if (dev_prop.device, dev_prop.name) in value_dict:
                    # get the value of the PropertyWidget from value
                    val = value_dict[(dev_prop.device, dev_prop.name)]
                    # update the value of the PropertyWidget
                    with signals_blocked(val_wdg._value_widget):
                        val_wdg.setValue(val)

                    self._prop_table.item(row, 0).setCheckState(Qt.CheckState.Checked)
                else:
                    self._prop_table.item(row, 0).setCheckState(Qt.CheckState.Unchecked)

        self._on_item_changed()

    # -------------- Private API --------------

    def _update_filter(self) -> None:
        filt = self._filter_text.text().lower()
        self._prop_table.filterDevices(
            filt,
            exclude_devices=self._device_filters.filters(),
            include_read_only=self._device_filters.showReadOnly(),
            include_pre_init=self._device_filters.showPreInitProps(),
        )

    def _on_item_changed(self) -> None:
        """Add [(device, property, value), ...] to the _PropertyValueViewer.

        Triggered when the checkbox of the DevicePropertyTable is checked or unchecked.
        """
        to_view_table: list[tuple[str, str, PropertyWidget]] = []

        for dev, prop, val in self.value():
            # create a PropertyWidget that will be added to the
            # _PropertyValueViewer table.
            wdg = PropertyWidget(
                dev,
                prop,
                mmcore=self._mmc,
                parent=self._prop_viewer,
                connect_core=False,
            )
            wdg.setValue(val)
            # connect the valueChanged signal of the PropertyWidget to the
            # _update_property_table method that will update the value of the
            # PropertyWidget in the DevicePropertyTable when the PropertyWidget changes.
            wdg._value_widget.valueChanged.connect(self._update_property_table)
            # to_view_table.append((dev, prop, val, wdg))
            to_view_table.append((dev, prop, wdg))

        # update the _PropertyValueViewer
        self._prop_viewer.setValue(to_view_table)

        self.valueChanged.emit(self.value())

    def _update_property_table(self, value: Any) -> None:
        """Update the value of the PropertyWidget in the DevicePropertyTable.

        Triggered when the value of the PropertyWidget in _PropertyValueViewer changes.
        """
        # row from the _PropertyValueViewer
        row = self._prop_viewer.indexAt(self.sender().parent().pos()).row()
        # get device and property from the _PropertyValueViewer using the row
        dev_prop = self._prop_viewer.item(row, 0).text()
        # get the row of device-property in the _PropertySelector table
        table_prop_item = self._prop_table.findItems(
            f"{dev_prop}", Qt.MatchFlag.MatchExactly
        )
        table_prop_row = table_prop_item[0].row()
        # get property widget and update the value
        wdg = cast("PropertyWidget", self._prop_table.cellWidget(table_prop_row, 1))
        with signals_blocked(wdg._value_widget):
            wdg.setValue(value)

        self.valueChanged.emit(self.value())

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._update_filter)


class _PropertyViewerTable(QTableWidget):
    """A table to view the properties of a selected pixel configuration."""

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ):
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self.setColumnCount(2)
        self.verticalHeader().setVisible(False)
        self.setHorizontalHeaderLabels(["Property", "Value"])
        self.horizontalHeader().setSectionResizeMode(
            self.horizontalHeader().ResizeMode.Stretch
        )
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

    def setValue(self, value: list[tuple[str, str, PropertyWidget]]) -> None:
        """Populate the table with (device, property, value_widget) info."""
        self.setRowCount(0)
        self.setRowCount(len(value))
        for row, (dev, prop, wdg) in enumerate(value):
            item = QTableWidgetItem(f"{dev}-{prop}")
            item.setData(DEV_PROP_ROLE, DeviceProperty(dev, prop, self._mmc))
            self.setItem(row, 0, item)
            self.setCellWidget(row, 1, wdg)
