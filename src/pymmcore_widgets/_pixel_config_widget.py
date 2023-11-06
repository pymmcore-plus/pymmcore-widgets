from typing import TYPE_CHECKING, cast

from pymmcore_plus import CMMCorePlus, DeviceProperty
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

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
ID_ROLE = QTableWidgetItem.ItemType.UserType + 1


class PixelConfigurationWidget(QWidget):
    """A Widget to configure the pixel size configurations."""

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
        self._props = _Properties(mmcore=self._mmc)

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
        main_layout.addWidget(self._props, 0, 1)
        main_layout.addLayout(btns_layout, 2, 1)

        # connect signals
        self._px_table._table.itemSelectionChanged.connect(
            self._on_px_table_selection_changed
        )
        self._px_table.valueChanged.connect(self._on_px_table_value_changed)
        self._props.valueChanged.connect(self._on_props_value_changed)

        apply_btn.clicked.connect(self._on_apply)
        cancel_btn.clicked.connect(self.close)

        self._on_sys_config_loaded()

    # -------------- Public API --------------

    def value(self) -> dict:
        """Return the value of the widget.

        Example:
        -------
        output = {
            resolutionID: {
                'px': 0.325,
                'dev1': {'prop1': 'val1', 'prop2': 'val2', ...},
                'dev2': {'prop1': 'val1', 'prop2': 'val2', ...},
                ...
            },
            ...
        }
        """
        return {
            resolutionID[ID]: {
                PX: resolutionID[PX],
                **self._px_table._table.item(row, 0).data(ID_ROLE),
            }
            for row, resolutionID in enumerate(self._px_table.value())
        }

    # -------------- Private API --------------

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
            self._px_table._table.item(row, 0).setData(
                ID_ROLE, self._mmc.getPixelSizeConfigData(resolutionID).dict()
            )

        # select first config
        self._px_table._table.selectRow(0)
        resolutionID = cast(str, cfgs[0][ID])
        self._update(resolutionID, 0)

    def _on_px_table_value_changed(self) -> None:
        # unchecked all properties rows if the table is empty
        if not self._px_table.value():
            self._update()
            self._props._device_filters.setShowCheckedOnly(False)

        self.valueChanged.emit(self.value())

    def _on_props_value_changed(self) -> None:
        """Update the data of the pixel table when props selection changes."""
        items = self._px_table._table.selectedItems()
        if len(items) != 1:
            return
        self._update_pixel_table_data(items[0].row())

        self.valueChanged.emit(self.value())

    def _on_px_table_selection_changed(self) -> None:
        """Update the widget when the selection changes."""
        items = self._px_table._table.selectedItems()
        if len(items) != 1:
            return
        resolutionID, row = items[0].text(), items[0].row()
        self._update(resolutionID, row)

    def _update(self, px_cfg: str = "", row: int | None = None) -> None:
        """Update the widget.

        Check the properties that are included in the specified configuration and
        update the data of the pixel table.
        """
        # if the configuration does not have a name or it does not exist, the
        # 'included' list should be empty so that all properties are unchecked
        if not px_cfg or row is None:
            included = []
        else:
            # get the devices, properties to included from the px_table data
            data = self._px_table._table.item(row, 0).data(ID_ROLE)
            included = [(k, next(iter(data[k].keys()))) for k in data]

        for r in range(self._props._prop_table.rowCount()):
            item = self._props._prop_table.item(r, 0)
            prop = cast(
                DeviceProperty,
                item.data(self._props._prop_table.PROP_ROLE),
            )
            if (prop.device, prop.name) in included:
                item.setCheckState(Qt.CheckState.Checked)
                # update the value of the property widget
                self._update_wdg_value(px_cfg, prop, r)
                # update the data of the pixel table
                self._update_pixel_table_data(row)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
        # unchecked the 'show checked-only' checkbox if 'included' is empty
        if not included:
            self._props._device_filters.setShowCheckedOnly(False)

        self.valueChanged.emit(self.value())

    def _update_wdg_value(
        self, px_cfg: str, property: DeviceProperty, row: int
    ) -> None:
        """Update the value of the property widget."""
        dpv = [tuple(c) for c in self._mmc.getPixelSizeConfigData(px_cfg)]
        for dev, prop, val in dpv:
            if dev == property.device and prop == property.name:
                wdg = cast("PropertyWidget", self._props._prop_table.cellWidget(row, 1))
                wdg.setValue(val)

    def _update_pixel_table_data(self, row: int | None) -> None:
        """Update the data of the pixel table."""
        if row is None:
            return
        props = self._props._prop_table.getCheckedProperties()
        item = self._px_table._table.item(row, 0)
        data = self._get_data(props)
        item.setData(ID_ROLE, data)

        # check if the current devices and properties are the same in all the px cfgs
        self._update_all_px_props(row, data)

    def _get_data(self, props: list[tuple[str, str, str]]) -> dict:
        """Return the updated data dictionary for the pixel table."""
        data: dict = {}
        for dev, prop, val in props:
            # if the device is already in the data dict, just add the property
            if dev in data:
                data[dev][prop] = val
            else:
                data[dev] = {prop: val}
        return data

    def _update_all_px_props(self, row: int, data: dict) -> None:
        """Update the data of in all resolutionIDs if different than 'data'.

        All the resolutionIDs should have the same devices and properties.
        """
        # get the dev-prop-val of the selected resolutionID (data)
        data_dpv = self._get_dpv_list(data)

        for r in range(self._px_table._table.rowCount()):
            # skip the selected resolutionID
            if r == row:
                continue
            item = self._px_table._table.item(r, 0)
            # get the dev-prop-val of the resolutionID
            res_id_dpv = self._get_dpv_list(item.data(ID_ROLE))

            # remove the devs-props that are not in the selected resolutionID (not data)
            data_dp = [(dev, prop) for dev, prop, _ in data_dpv]
            for dev, prop, val in res_id_dpv:
                if (dev, prop) not in data_dp:
                    res_id_dpv.remove((dev, prop, val))

            # add the missing devices and properties
            res_id_dp = [(dev, prop) for dev, prop, _ in res_id_dpv]
            for dev, prop, val in data_dpv:
                if (dev, prop) not in res_id_dp:
                    res_id_dpv.append((dev, prop, val))
            item.setData(ID_ROLE, self._get_data(res_id_dpv))

    def _get_dpv_list(self, data: dict) -> list[tuple[str, str, str]]:
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

    def _on_apply(self) -> None:
        """Update the current pixel size configurations."""
        # delete all the pixel size configurations
        for res_id in self._mmc.getAvailablePixelSizeConfigs():
            self._mmc.deletePixelSizeConfig(res_id)

        # define the new pixel size configurations
        for resolutionID, data in self.value().items():
            data = cast(dict, data)
            px_size = data.pop(PX)

            for dev, prop, val in self._get_dpv_list(data):
                self._mmc.definePixelSizeConfig(resolutionID, dev, prop, val)
                self._mmc.setPixelSizeUm(resolutionID, px_size)

        self.close()


class _PixelTable(DataTableWidget):
    ID = TextColumn(
        key=ID, header="pixel configuration name", default=None, is_row_selector=False
    )
    VALUE = FloatColumn(
        key=PX, header="pixel value [µm]", default=0, is_row_selector=False
    )

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, parent)

        self._toolbar.removeAction(self.act_check_all)
        self._toolbar.removeAction(self.act_check_none)
        self._toolbar.actions()[2].setVisible(False)  # separator


class _Properties(QWidget):
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
        self._connect_widgets()

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

    def _connect_widgets(self) -> None:
        """Connect the valueChanged signal of all the the property widgets."""
        for row in range(self._prop_table.rowCount()):
            wdg = cast("PropertyWidget", self._prop_table.cellWidget(row, 1))
            wdg._value_widget.valueChanged.connect(self._emit_checked_properties)

    def _emit_checked_properties(self) -> None:
        """Emit all the chacked properties."""
        self.valueChanged.emit(self._prop_table.getCheckedProperties())
