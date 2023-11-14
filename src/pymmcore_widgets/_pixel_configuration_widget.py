from dataclasses import dataclass
from typing import Any, cast

from pymmcore_plus import CMMCorePlus, DeviceProperty
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
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
from pymmcore_widgets.useq_widgets import DataTable, DataTableWidget
from pymmcore_widgets.useq_widgets._column_info import FloatColumn, TextColumn

FIXED = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
ROW = "row"
PX = "px"
ID = "id"
PROPS = "props"
NEW = "New"
DEV_PROP_ROLE = QTableWidgetItem.ItemType.UserType + 1


@dataclass
class ConfigMap:
    """A dataclass to store the data of the pixel configurations."""

    resolutionID: str
    px_size: float
    props: list[tuple[str, str, str]]


class PixelConfigurationWidget(QWidget):
    """A Widget to define the pixel size configurations."""

    valueChanged = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str = "",
        mmcore: CMMCorePlus | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle(title)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._resID_map: dict[int, ConfigMap] = {}

        self._px_table = _PixelTable()
        self._props_selector = _PropertySelector(mmcore=self._mmc)

        # buttons
        apply_btn = QPushButton("Apply and Close")
        apply_btn.setSizePolicy(FIXED)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setSizePolicy(FIXED)
        btns_layout = QHBoxLayout()
        btns_layout.setContentsMargins(0, 0, 0, 0)
        btns_layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        )
        btns_layout.addWidget(apply_btn)
        btns_layout.addWidget(cancel_btn)

        # main layout
        main_layout = QGridLayout(self)
        main_layout.addWidget(self._px_table, 0, 0)
        main_layout.addWidget(self._props_selector, 0, 1)
        main_layout.addLayout(btns_layout, 2, 1)

        # connect signals
        self._px_table.table().model().rowsInserted.connect(self._on_rows_inserted)
        self._px_table._table.itemChanged.connect(self._on_resolutionID_name_changed)
        self._px_table.valueChanged.connect(self._on_px_table_value_changed)
        self._px_table._table.itemSelectionChanged.connect(
            self._on_px_table_selection_changed
        )
        self._props_selector.valueChanged.connect(self._on_viewer_value_changed)
        apply_btn.clicked.connect(self._on_apply)
        cancel_btn.clicked.connect(self.close)

        self._on_sys_config_loaded()

    # -------------- Public API --------------

    def value(self) -> dict:
        """Return the current state of the widget describing the pixel configurations.

        Example:
        -------
            output = {
                Res10x: {
                    'px': 0.65,
                    'props': [('dev1', 'prop1', 'val1'), ...],
                },
                Res20x: {
                    'px': 0.325,
                    'props': [('dev1', 'prop1', 'val2'), ...],
                },
                ...
        """
        return {
            self._resID_map[row].resolutionID: {
                PX: self._resID_map[row].px_size,
                PROPS: self._resID_map[row].props,
            }
            for row in self._resID_map
        }

    # -------------- Private API --------------

    def _on_sys_config_loaded(self) -> None:
        self._px_table._remove_all()

        # set dict of 'devs props vals' as data for each resolutionID
        for row, resolutionID in enumerate(self._mmc.getAvailablePixelSizeConfigs()):
            # get the data of the resolutionID
            px_size = self._mmc.getPixelSizeUmByID(resolutionID)
            dev_prop_val = list(self._mmc.getPixelSizeConfigData(resolutionID))
            # store the data in the configuration map
            self._resID_map[row] = ConfigMap(resolutionID, px_size, dev_prop_val)
            # add pixel size configurations to table
            data = {
                self._px_table.ID.key: resolutionID,
                self._px_table.VALUE.key: px_size,
            }
            self._px_table._add_row()
            self._px_table.table().setRowData(row, data)
            # connect the valueChanged signal of the px table spinboxes.
            wdg = cast(QDoubleSpinBox, self._px_table._table.cellWidget(row, 1))
            wdg.valueChanged.connect(self._on_px_value_changed)

            if row == 0:
                # check all the device-property for the first resolutionID
                self.checkResolutionIDProperties(row)
                # select first row of px_table corresponding to the first resolutionID
                self._px_table._table.selectRow(row)

    def checkResolutionIDProperties(self, row: int) -> None:
        """Check all properties that are in the given resolutionID (pixel configuration)."""  # noqa: E501
        for dev, prop, _ in self._resID_map[row].props:
            for row in range(self._props_selector._prop_table.rowCount()):
                p = cast(
                    DeviceProperty,
                    self._props_selector._prop_table.item(row, 0).data(
                        self._props_selector._prop_table.PROP_ROLE
                    ),
                )
                if p.device == dev and p.name == prop:
                    self._props_selector._prop_table.item(row, 0).setCheckState(
                        Qt.CheckState.Checked
                    )
                else:
                    self._props_selector._prop_table.item(row, 0).setCheckState(
                        Qt.CheckState.Unchecked
                    )

    def _on_px_table_selection_changed(self) -> None:
        """Update property and viewer table when selection in the px table changes."""
        items = self._px_table._table.selectedItems()
        # disable if no resolutionID is selected
        self._props_selector.setEnabled(bool(items))
        if not items:
            self._props_selector._device_filters._check_all()
        if len(items) != 1:
            return
        row = items[0].row()
        # check the resolutionID props in the _prop_table
        with signals_blocked(self._props_selector._prop_table):
            self.checkResolutionIDProperties(row)
        # update the value in _prop_viewer
        for r, (_, _, val) in enumerate(self._resID_map[row].props):
            wdg = cast(
                "PropertyWidget", self._props_selector._prop_viewer.cellWidget(r, 1)
            )
            wdg.setValue(val)

    def _on_viewer_value_changed(self, value: Any) -> None:
        # get row of the selected resolutionID
        items = self._px_table._table.selectedItems()
        if len(items) != 1:
            return
        self._resID_map[items[0].row()].props = value
        self._update_other_resolutionIDs(items[0].row(), value)

    def _on_resolutionID_name_changed(self, item: QTableWidgetItem) -> None:
        """Update the resolutionID name in the configuration map."""
        self._resID_map[item.row()].resolutionID = item.text()

        self.valueChanged.emit(self.value())

    def _on_px_value_changed(self) -> None:
        """Update the pixel size value in the configuration map."""
        spin = cast(QDoubleSpinBox, self.sender())
        table = cast(DataTable, self.sender().parent().parent())
        row = table.indexAt(spin.pos()).row()
        self._resID_map[row].px_size = spin.value()

        self.valueChanged.emit(self.value())

    def _on_px_table_value_changed(self) -> None:
        """Update the data of the pixel table when the value changes."""
        # if the table is empty clear the configuration map and unchecked all rows
        if not self._px_table.value():
            self._resID_map.clear()
            for row in range(self._props_selector._prop_table.rowCount()):
                item = self._props_selector._prop_table.item(row, 0)
                item.setCheckState(Qt.CheckState.Unchecked)

    def _update_other_resolutionIDs(
        self, selected_resID_row: int, selected_resID_props: list[tuple[str, str, str]]
    ) -> None:
        """Update the data of in all resolutionIDs if different than the data of the
        selected resolutionID. All the resolutionIDs should have the same devices and
        properties.
        """  # noqa: D205
        # selected_resID_props = self._config_map[selected_resID_row].props
        selected_dev_prop = {(dev, prop) for dev, prop, _ in selected_resID_props}

        for r in range(self._px_table._table.rowCount()):
            # skip the selected resolutionID
            if r == selected_resID_row:
                continue

            # get the dev-prop-val of the resolutionID
            props = self._resID_map[r].props

            # remove the devs-props that are not in the selected resolutionID (not data)
            props_to_remove = [
                (d, p, v) for d, p, v in props if (d, p) not in selected_dev_prop
            ]
            for dpv in props_to_remove:
                props.remove(dpv)

            # add the missing devices and properties
            res_id_dp = {(dev, prop) for dev, prop, _ in props}
            props_to_add = [
                (d, p, v) for d, p, v in selected_resID_props if (d, p) not in res_id_dp
            ]
            for dpv in props_to_add:
                props.append(dpv)

            self._resID_map[r].props = sorted(props, key=lambda x: x[0])

    def _on_rows_inserted(self, parent: Any, start: int, end: int) -> None:
        """Set the data of a newly inserted resolutionID in the _px_table."""
        # "end" is the last row inserted. if "self._config_map[end]" exists, it means it
        #  is not a new row added by clicking on the "add" button but is a row added by
        # "_on_sys_config_loaded". so we don't need to set the data.
        if self._resID_map.get(end):
            return

        fist_resID = self._resID_map[0]
        props = fist_resID.props if fist_resID else []
        self._resID_map[end] = ConfigMap(NEW, 0, props)

        # connect the valueChanged signal of the spinbox
        wdg = cast(QDoubleSpinBox, self._px_table._table.cellWidget(end, 1))
        wdg.valueChanged.connect(self._on_px_value_changed)

        self._px_table._table.selectRow(end)

        self.valueChanged.emit(self.value())

    def _on_apply(self) -> None:
        """Update the current pixel size configurations."""
        # check if there are errors in the pixel configurations
        if self._check_for_errors():
            return

        # delete all the pixel size configurations
        for resolutionID in self._mmc.getAvailablePixelSizeConfigs():
            self._mmc.deletePixelSizeConfig(resolutionID)

        # define the new pixel size configurations
        for row, rec in enumerate(self._px_table.table().iterRecords()):
            props = self._config_map[row].props
            for dev, prop, val in props:
                self._mmc.definePixelSizeConfig(rec[ID], dev, prop, val)
                self._mmc.setPixelSizeUm(rec[ID], rec[PX])

        self.close()

    def _check_for_errors(self) -> bool:
        """Check for errors in the pixel configurations."""
        resolutionIDs = [rec[ID] for rec in self._px_table.table().iterRecords()]

        # check that all the resolutionIDs have a valid name
        for resolutionID in resolutionIDs:
            if not resolutionID:
                return self._show_error_message("All resolutionIDs must have a name.")

        # check if there are duplicated resolutionIDs
        if len(resolutionIDs) != len(set(resolutionIDs)):
            return self._show_error_message(
                "There are duplicated resolutionIDs: "
                f"{list({x for x in resolutionIDs if resolutionIDs.count(x) > 1})}"
            )

        # check if there are duplicated devices and properties
        for row in range(self._px_table._table.rowCount()):
            props = self._resID_map[row].props
            if len(props) != len(set(props)):
                return self._show_error_message(
                    "There are duplicated devices and properties in resolutionID: "
                    f"{resolutionIDs[row]}"
                )

        return False

    def _show_error_message(self, msg: str) -> bool:
        """Show an error message."""
        response = QMessageBox.critical(
            self, "Configuration Error", msg, QMessageBox.StandardButton.Close
        )
        return bool(response == QMessageBox.StandardButton.Close)


class _PixelTable(DataTableWidget):
    ID = TextColumn(
        key=ID, header="pixel configuration name", default=NEW, is_row_selector=False
    )
    VALUE = FloatColumn(
        key=PX, header="pixel value [µm]", default=0, is_row_selector=False
    )

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, parent)

        self._toolbar.removeAction(self.act_check_all)
        self._toolbar.removeAction(self.act_check_none)
        self._toolbar.actions()[2].setVisible(False)  # separator


class _PropertyViewer(QTableWidget):
    """A table to view the properties of a selected pixel configuration."""

    valueChanged = Signal(object)

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

    def value(self) -> list[tuple[str, str, str]]:
        """Return the list of (device, property, value) of the table."""
        value = []
        for row in range(self.rowCount()):
            item_data = cast(DeviceProperty, self.item(row, 0).data(DEV_PROP_ROLE))
            dev, prop = item_data.device, item_data.name
            wdg = cast("PropertyWidget", self.cellWidget(row, 1))
            val = wdg.value()
            value.append((dev, prop, val))
        return value

    def setValue(self, value: list[tuple[str, str, str, PropertyWidget]]) -> None:
        """Populate the table with (device, property, value_widget) info."""
        self.setRowCount(0)
        self.setRowCount(len(value))
        for row, (dev, prop, val, wdg) in enumerate(value):
            item = QTableWidgetItem(f"{dev}-{prop}")
            item.setData(DEV_PROP_ROLE, DeviceProperty(dev, prop, self._mmc))
            self.setItem(row, 0, item)
            self.setCellWidget(row, 1, wdg)
            with signals_blocked(wdg._value_widget):
                wdg.setValue(val)
        self.valueChanged.emit(self.value())


class _PropertySelector(QWidget):
    """A widget to select the properties to be assigned to the pixel configurations."""

    valueChanged = Signal(object)

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ):
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        # property table (right wdg)
        self._filter_text = QLineEdit()
        self._filter_text.setClearButtonEnabled(True)
        self._filter_text.setPlaceholderText("Filter by device or property name...")
        self._filter_text.textChanged.connect(self._update_filter)

        self._prop_viewer = _PropertyViewer(mmcore=self._mmc)

        self._prop_table = DevicePropertyTable(
            connect_core=False, enable_property_widgets=False
        )
        self._prop_table.setRowsCheckable(True)
        # self._connect_property_widgets()

        splitter = QSplitter(Qt.Orientation.Vertical)
        # avoid splitter hiding completely widgets
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._prop_viewer)
        splitter.addWidget(self._prop_table)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self._filter_text)
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

        self._prop_viewer.setMinimumHeight(right.minimumSizeHint().height() / 2)

        self._prop_table.itemChanged.connect(self._on_item_changed)
        self._prop_viewer.valueChanged.connect(self.valueChanged)

    def _update_filter(self) -> None:
        filt = self._filter_text.text().lower()
        self._prop_table.filterDevices(
            filt,
            exclude_devices=self._device_filters.filters(),
            include_read_only=self._device_filters.showReadOnly(),
            include_pre_init=self._device_filters.showPreInitProps(),
        )

    def _on_item_changed(self, value: Any) -> None:
        """Add [(device, property, value), ...] to the _PropertyValueViewer.

        Triggered when the checkbox of the DevicePropertyTable is checked or unchecked.
        """
        to_view_table: list[tuple[str, str, str, PropertyWidget]] = []
        for dev, prop, val in self._prop_table.getCheckedProperties():
            # create a PropertyWidget that will be added to the
            # _PropertyValueViewer.
            wdg = PropertyWidget(
                dev,
                prop,
                mmcore=self._mmc,
                parent=self._prop_viewer,
                connect_core=False,
            )
            # connect the valueChanged signal of the PropertyWidget to the
            # _update_property_table method that will update the value of the
            # PropertyWidget in the DevicePropertyTable when the PropertyWidget changes.
            wdg._value_widget.valueChanged.connect(self._update_property_table)
            to_view_table.append((dev, prop, val, wdg))

        # update the _PropertyValueViewer
        self._prop_viewer.setValue(to_view_table)

        self.valueChanged.emit(self._prop_viewer.value())

    def _update_property_table(self, value: Any) -> None:
        """Update the value of the PropertyWidget in the DevicePropertyTable."""
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

        self.valueChanged.emit(self._prop_viewer.value())
