from collections import Counter
from dataclasses import dataclass
from typing import Any, cast

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidgetItem,
    QWidget,
)

from pymmcore_widgets._property_selector import PropertySelector
from pymmcore_widgets.useq_widgets import DataTable, DataTableWidget
from pymmcore_widgets.useq_widgets._column_info import FloatColumn, TextColumn

FIXED = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
PX = "px"
ID = "id"
PX_SIZE = "pixel_size"
PROP = "properties"
NEW = "New"
DEV_PROP_ROLE = QTableWidgetItem.ItemType.UserType + 1


@dataclass
class ConfigMap:
    """A dataclass to store the data of a pixel configuration.

    Attributes
    ----------
    resolutionID : str
        The name of the pixel configuration.
    px_size : float
        The pixel size in µm.
    properties : list[tuple[str, str, str]]
        The list of (device, property, value) of the pixel configuration.
    """

    resolutionID: str
    px_size: float
    properties: list[tuple[str, str, str]]


class PixelConfigurationWidget(QWidget):
    """A Widget to define the pixel size configurations."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle("Pixel Configuration Widget")

        self._mmc = mmcore or CMMCorePlus.instance()

        self._resID_map: dict[int, ConfigMap] = {}

        self._px_table = _PixelTable()
        self._props_selector = PropertySelector(mmcore=self._mmc)

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
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_config_loaded)
        self._px_table._table.itemChanged.connect(self._on_resolutionID_name_changed)
        self._px_table.valueChanged.connect(self._on_px_table_value_changed)
        self._px_table._table.itemSelectionChanged.connect(
            self._on_px_table_selection_changed
        )
        self._px_table.table().model().rowsInserted.connect(self._on_rows_inserted)
        self._props_selector.valueChanged.connect(self._on_viewer_value_changed)
        apply_btn.clicked.connect(self._on_apply)
        cancel_btn.clicked.connect(self.close)

        self.destroyed.connect(self._disconnect)

        self._on_sys_config_loaded()

    # -------------- Public API --------------

    def value(self) -> list[ConfigMap]:
        """Return the current state of the widget describing the pixel configurations.

        Returns
        -------
        list[ConfigMap][pymmcore_widgets._pixel_configuration_widget.ConfigMap]
            A list of pixel configurations data.

        Example:
        -------
            output = [
                ConfigMap(Res10x, 0.65, [('dev1', 'prop1', 'val1'), ...]),
                ConfigMap(Res20x, 0.325, [('dev1', 'prop1', 'val2'), ...]),
                ...
            ]
        """
        return [self._resID_map[row] for row in self._resID_map]

    def setValue(self, value: list[ConfigMap]) -> None:
        """Set the state of the widget describing the pixel configurations.

        Parameters
        ----------
        value : list[ConfigMap][pymmcore_widgets._pixel_configuration_widget.ConfigMap]
            The list of pixel configurations data to set.

        Example:
        -------
            input = [
                ConfigMap(Res10x, 0.65, [('dev1', 'prop1', 'val1'), ...]),
                ConfigMap(Res20x, 0.325, [('dev1', 'prop1', 'val2'), ...]),
                ...
            ]
        """
        self._px_table._remove_all()
        self._resID_map.clear()

        if not value:
            self._props_selector._prop_table.uncheckAll()
            self._props_selector.setEnabled(False)
            return

        for row, rec in enumerate(value):
            self._resID_map[row] = value[row]
            self._px_table._add_row()
            data = {
                self._px_table.ID.key: rec.resolutionID,
                self._px_table.VALUE.key: rec.px_size,
            }
            self._px_table.table().setRowData(row, data)

        self._px_table._table.selectRow(0)

    # -------------- Private API --------------

    def _on_sys_config_loaded(self) -> None:
        self._px_table._remove_all()
        self._resID_map.clear()

        px_configs = self._mmc.getAvailablePixelSizeConfigs()
        if not px_configs:
            self._props_selector._prop_table.uncheckAll()
            self._props_selector.setEnabled(False)
            return

        # set dict of 'devs props vals' as data for each resolutionID
        for row, resolutionID in enumerate(px_configs):
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
                self._props_selector.setValue(dev_prop_val)
                # select first row of px_table corresponding to the first resolutionID
                self._px_table._table.selectRow(row)

    def _on_viewer_value_changed(self, value: Any) -> None:
        # get row of the selected resolutionID
        items = self._px_table._table.selectedItems()
        if len(items) != 1:
            return
        self._resID_map[items[0].row()].properties = value
        self._update_other_resolutionIDs(items[0].row(), value)

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
        self._props_selector.setValue(self._resID_map[row].properties)

    def _on_resolutionID_name_changed(self, item: QTableWidgetItem) -> None:
        """Update the resolutionID name in the configuration map."""
        self._resID_map[item.row()].resolutionID = item.text()

    def _on_px_value_changed(self) -> None:
        """Update the pixel size value in the configuration map."""
        spin = cast(QDoubleSpinBox, self.sender())
        table = cast(DataTable, self.sender().parent().parent())
        row = table.indexAt(spin.pos()).row()
        self._resID_map[row].px_size = spin.value()

    def _on_px_table_value_changed(self) -> None:
        """Update the data of the pixel table when the value changes."""
        # if the table is empty clear the configuration map and unchecked all rows
        if not self._px_table.value():
            self._resID_map.clear()
            self._props_selector._prop_table.uncheckAll()

    def _on_rows_inserted(self, parent: Any, start: int, end: int) -> None:
        """Set the data of a newly inserted resolutionID in the _px_table."""
        # "end" is the last row inserted.
        # if "self._config_map[end]" exists, it means it is a row added by
        # "_on_sys_config_loaded" so we don't need to set the data and we return.
        if self._resID_map.get(end):
            return

        # Otherwise it is a new row added by clicking on the "add" button and we need to
        # set the data. If there are already resolutionIDs, get the properties of the
        # first one, if there are no resolutionIDs, set props to an empty list
        props = self._resID_map[0].properties if self._resID_map else []
        self._resID_map[end] = ConfigMap(NEW, 0, props)

        # connect the valueChanged signal of the spinbox
        wdg = cast(QDoubleSpinBox, self._px_table._table.cellWidget(end, 1))
        wdg.valueChanged.connect(self._on_px_value_changed)

        # select the added row
        self._px_table._table.selectRow(end)

    def _update_other_resolutionIDs(
        self, selected_resID_row: int, selected_resID_props: list[tuple[str, str, str]]
    ) -> None:
        """Update the data of in all resolutionIDs if different than the data of the
        selected resolutionID. All the resolutionIDs should have the same devices and
        properties.
        """  # noqa: D205
        selected_dev_prop = [(dev, prop) for dev, prop, _ in selected_resID_props]

        for row in range(self._px_table._table.rowCount()):
            # skip the selected resolutionID
            if row == selected_resID_row:
                continue

            # get the dev-prop-val of the resolutionID
            properties = self._resID_map[row].properties

            # remove the devs-props that are not in the selected resolutionID
            properties = [
                (dev, prop, val)
                for dev, prop, val in properties
                if (dev, prop) in selected_dev_prop
            ]

            # add the missing devices and properties
            res_id_dev_prop = {(dev, prop) for dev, prop, _ in properties}
            properties += [
                (dev, prop, val)
                for dev, prop, val in selected_resID_props
                if (dev, prop) not in res_id_dev_prop
            ]

            self._resID_map[row].properties = sorted(properties, key=lambda x: x[0])

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
            props = self._resID_map[row].properties
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
        if [item for item, count in Counter(resolutionIDs).items() if count > 1]:
            return self._show_error_message(
                "There are duplicated resolutionIDs: "
                f"{list({x for x in resolutionIDs if resolutionIDs.count(x) > 1})}"
            )

        # check if there are duplicated devices and properties
        for row in range(self._px_table._table.rowCount()):
            props = self._resID_map[row].properties
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

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(
            self._on_sys_config_loaded
        )


class _PixelTable(DataTableWidget):
    """A table to add and display the pixel size configurations."""

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
