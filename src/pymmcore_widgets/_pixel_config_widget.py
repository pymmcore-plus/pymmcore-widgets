from typing import TYPE_CHECKING, Any, cast

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
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

from pymmcore_widgets._device_property_table import DevicePropertyTable
from pymmcore_widgets._device_type_filter import DeviceTypeFilters
from pymmcore_widgets.useq_widgets import DataTableWidget
from pymmcore_widgets.useq_widgets._column_info import FloatColumn, TextColumn

if TYPE_CHECKING:
    from pymmcore_widgets._property_widget import PropertyWidget

FIXED = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
ROW = "row"
PX = "px"
ID = "id"
PROPS = "props"
ID_ROLE = QTableWidgetItem.ItemType.UserType + 1


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
        self._px_table.valueChanged.connect(self._on_px_table_value_changed)
        self._px_table._table.itemSelectionChanged.connect(
            self._on_px_table_selection_changed
        )
        self._px_table._table.itemChanged.connect(
            lambda: self.valueChanged.emit(self.value())
        )
        self._px_table.table().model().rowsInserted.connect(self._on_rows_inserted)
        self._props_selector.valueChanged.connect(self._on_props_selector_value_changed)
        apply_btn.clicked.connect(self._on_apply)
        cancel_btn.clicked.connect(self.close)

        self._on_sys_config_loaded()

    # -------------- Public API --------------

    def value(self) -> dict:
        """Return the value of the widget.

        Example:
        -------
            output = {
                Res10x: {
                    'px': 0.325,
                    'props': [('dev1', 'prop1', 'val1'), ...],
                },
                ...
        """
        value = {}
        for row, rec in enumerate(self._px_table.table().iterRecords()):
            props = self._px_table._table.item(row, 0).data(ID_ROLE)
            value[rec[ID]] = {PX: rec[PX], PROPS: props}
        return value

    # -------------- Private API --------------

    def _on_rows_inserted(self, parent: Any, start: int, end: int) -> None:
        """Set the data of the new resolutionID.

        When a new row is inserted, set the data of the new resolutionID with the
        properties that are checked in the properties table.
        """
        self._update_current_resolutionID_data(end)
        # connect the valueChanged signal of the spinbox
        wdg = cast(QDoubleSpinBox, self._px_table._table.cellWidget(end, 1))
        wdg.valueChanged.connect(lambda: self.valueChanged.emit(self.value()))

    def _on_sys_config_loaded(self) -> None:
        self._px_table._remove_all()

        # add pixel size configurations to table
        cfgs = [
            {ID: c, PX: self._mmc.getPixelSizeUmByID(c)}
            for c in self._mmc.getAvailablePixelSizeConfigs()
        ]
        self._px_table.setValue(cfgs)

        # set dict of 'devs props vals' as data for each resolutionID
        for row in range(self._px_table._table.rowCount()):
            resolutionID = cast(str, cfgs[row][ID])
            props = list(self._mmc.getPixelSizeConfigData(resolutionID))
            self._px_table._table.item(row, 0).setData(ID_ROLE, props)
            # connect the valueChanged signal of the spinbox
            wdg = cast(QDoubleSpinBox, self._px_table._table.cellWidget(row, 1))
            wdg.valueChanged.connect(lambda: self.valueChanged.emit(self.value()))

        # select first config
        self._px_table._table.selectRow(0)

    def _on_px_table_selection_changed(self) -> None:
        """Update the widget when the selection in the px table changes."""
        items = self._px_table._table.selectedItems()

        # hide if no resolutionID is selected
        self._props_selector.setEnabled(bool(items))

        if len(items) != 1:
            return

        self._update_used_properties_and_data(items[0].row())

    def _on_props_selector_value_changed(self) -> None:
        """Update the data of the pixel table when props selection changes."""
        items = self._px_table._table.selectedItems()
        if len(items) != 1:
            return
        self._update_current_resolutionID_data(items[0].row())
        self._update_resolutionIDs_data(items[0].row())

    def _on_px_table_value_changed(self) -> None:
        # unchecked all properties rows if the table is empty
        if not self._px_table.value():
            self._update_used_properties_and_data()
            self._props_selector._device_filters.setShowCheckedOnly(False)

    def _update_current_resolutionID_data(self, row: int) -> None:
        """Set the data of the resolutionID item in the pixel table."""
        data = self._props_selector._prop_table.getCheckedProperties()
        new_item = self._px_table._table.item(row, 0)
        new_item.setData(ID_ROLE, data)

    def _update_resolutionIDs_data(self, selected_resID_row: int) -> None:
        """Update the data of in all resolutionIDs if different than the data of the
        selected resolutionID. All the resolutionIDs should have the same devices and
        properties.
        """  # noqa: D205
        selected_resID = self._px_table._table.item(selected_resID_row, 0)
        selected_resID_data = selected_resID.data(ID_ROLE)

        for r in range(self._px_table._table.rowCount()):
            # skip the selected resolutionID
            if r == selected_resID_row:
                continue

            item = self._px_table._table.item(r, 0)

            # get the dev-prop-val of the resolutionID
            data = cast(list, item.data(ID_ROLE))

            # remove the devs-props that are not in the selected resolutionID (not data)
            data_dp = [(dev, prop) for dev, prop, _ in selected_resID_data]
            for dev, prop, val in data:
                if (dev, prop) not in data_dp:
                    data.remove((dev, prop, val))

            # add the missing devices and properties
            res_id_dp = [(dev, prop) for dev, prop, _ in data]
            for dev, prop, val in selected_resID_data:
                if (dev, prop) not in res_id_dp:
                    data.append((dev, prop, val))

            item.setData(ID_ROLE, sorted(data, key=lambda x: x[0]))

    def _update_used_properties_and_data(self, resID_row: int | None = None) -> None:
        """Update the properties and data for the pixel configuration.

        Check the properties that are included in the specified configuration and
        update the data of the pixel table.
        """
        included = [] if resID_row is None else self._get_properties_to_use(resID_row)
        for row_props_table in range(self._props_selector._prop_table.rowCount()):
            item = self._props_selector._prop_table.item(row_props_table, 0)
            prop = cast(
                DeviceProperty,
                item.data(self._props_selector._prop_table.PROP_ROLE),
            )
            if (prop.device, prop.name) in included:
                # set the property as checked
                item.setCheckState(Qt.CheckState.Checked)
                # update the value of the property widget
                self._update_property_widget_value(prop, row_props_table, resID_row)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
        # unchecked the 'show checked-only' checkbox if 'included' is empty
        if not included:
            self._props_selector._device_filters.setShowCheckedOnly(False)

    def _get_properties_to_use(self, resID_row: int) -> list[tuple[str, str]]:
        """Get the list of (device, property) to include."""
        data = self._px_table._table.item(resID_row, 0).data(ID_ROLE)
        included = [(d, p) for d, p, _ in data] if data is not None else []
        # update included list with the checked properties if not already included
        for d, p, _ in self._props_selector._prop_table.getCheckedProperties():
            if (d, p) not in included:
                included.append((d, p))
        return included

    def _update_property_widget_value(
        self, property: DeviceProperty, row_props_table: int, resID_row: int | None
    ) -> None:
        """Update the value of the property widget."""
        if resID_row is None:
            return
        data = self._px_table._table.item(resID_row, 0).data(ID_ROLE)
        for dev, prop, val in data:
            if dev == property.device and prop == property.name:
                wdg = cast(
                    "PropertyWidget",
                    self._props_selector._prop_table.cellWidget(row_props_table, 1),
                )
                with signals_blocked(wdg._value_widget):
                    wdg.setValue(val)

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
            data = self._px_table._table.item(row, 0).data(ID_ROLE)
            for dev, prop, val in data:
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
            data = self._px_table._table.item(row, 0).data(ID_ROLE)
            if len(data) != len(set(data)):
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

    def _dict_to_list_of_tuples(self, data: dict) -> list[tuple[str, str, str]]:
        """Return a list of dev-prop-val from a 'data' dict.

        Example:
        -------
        data = {'Objective': {'Label': 'Nikon 10X S Fluor'}}
        returns: [('Objective', 'Label', 'Nikon 10X S Fluor')]
        """
        data_list: list[tuple[str, str, str]] = []
        for key, value in data.items():
            data_list.extend(
                (key, sub_key, sub_value) for sub_key, sub_value in value.items()
            )
        return data_list


class _PixelTable(DataTableWidget):
    ID = TextColumn(key=ID, header="pixel configuration name", is_row_selector=False)
    VALUE = FloatColumn(
        key=PX, header="pixel value [µm]", default=0, is_row_selector=False
    )

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, parent)

        self._toolbar.removeAction(self.act_check_all)
        self._toolbar.removeAction(self.act_check_none)
        self._toolbar.actions()[2].setVisible(False)  # separator


class _PropertySelector(QWidget):
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

        self._prop_table = DevicePropertyTable(connect_core=False)
        self._prop_table.setRowsCheckable(True)
        self._connect_property_widgets()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self._filter_text)
        right_layout.addWidget(self._prop_table)

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

        self._prop_table.itemChanged.connect(self._emit_checked_properties)

    def _update_filter(self) -> None:
        filt = self._filter_text.text().lower()
        self._prop_table.filterDevices(
            filt,
            exclude_devices=self._device_filters.filters(),
            include_read_only=self._device_filters.showReadOnly(),
            include_pre_init=self._device_filters.showPreInitProps(),
            include_checked_only=self._device_filters.showCheckedOnly(),
        )

    def _connect_property_widgets(self) -> None:
        """Connect the valueChanged signal of all the the property widgets."""
        for row in range(self._prop_table.rowCount()):
            wdg = cast("PropertyWidget", self._prop_table.cellWidget(row, 1))
            wdg._value_widget.valueChanged.connect(self._emit_checked_properties)

    def _emit_checked_properties(self) -> None:
        """Emit all the chacked properties."""
        self.valueChanged.emit(self._prop_table.getCheckedProperties())
