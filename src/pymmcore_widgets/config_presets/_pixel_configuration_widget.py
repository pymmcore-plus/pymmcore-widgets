from __future__ import annotations

import itertools
import warnings
from collections import Counter
from typing import Any, Sequence, cast

from pymmcore_plus import CMMCorePlus, DeviceProperty
from pymmcore_plus.model import PixelSizeGroup, PixelSizePreset, Setting
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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

from pymmcore_widgets.device_properties._device_property_table import (
    DevicePropertyTable,
)
from pymmcore_widgets.device_properties._device_type_filter import DeviceTypeFilters
from pymmcore_widgets.device_properties._property_widget import PropertyWidget
from pymmcore_widgets.useq_widgets import DataTable, DataTableWidget
from pymmcore_widgets.useq_widgets._column_info import FloatColumn, TextColumn

FIXED = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
PX = "px"
ID = "id"
PX_SIZE = "pixel_size"
PROP = "properties"
NEW = "New"
DEV_PROP_ROLE = QTableWidgetItem.ItemType.UserType + 1
DEFAULT_AFFINE = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)


class PixelConfigurationWidget(QWidget):
    """A Widget to define the pixel size configurations.

    Each pixel size configuration can be linked to any device and property. However,
    it's important to note that all pixel size configurations must include the same
    devices and properties. The only variation allowed between different configurations
    is in the values of the device properties.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget, by default None
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle("Pixel Configuration Widget")

        self._mmc = mmcore or CMMCorePlus.instance()

        self._resID_map: dict[int, PixelSizePreset] = {}

        # pixel and affine tables widget
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)
        self._px_table = _PixelTable()
        affine_lbl = QLabel("Affine Transformation:")
        self._affine_table = AffineTable()
        left_layout.addWidget(self._px_table, 1)
        left_layout.addWidget(affine_lbl, 0)
        left_layout.addWidget(self._affine_table, 0)

        self._props_selector = _PropertySelector(mmcore=self._mmc)

        splitter = QSplitter()
        splitter.setContentsMargins(0, 0, 0, 0)
        # avoid splitter hiding completely widgets
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(left)
        splitter.addWidget(self._props_selector)

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
        btns_layout.addWidget(cancel_btn)
        btns_layout.addWidget(apply_btn)

        # main layout
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(splitter)
        main_layout.addLayout(btns_layout)

        # connect signals
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_config_loaded)
        self._px_table._table.itemChanged.connect(self._on_resolutionID_name_changed)
        self._px_table.valueChanged.connect(self._on_px_table_value_changed)
        self._px_table._table.itemSelectionChanged.connect(
            self._on_px_table_selection_changed
        )
        self._px_table.table().model().rowsInserted.connect(self._on_rows_inserted)
        self._props_selector.valueChanged.connect(self._on_viewer_value_changed)
        self._affine_table.valueChanged.connect(self._on_affine_value_changed)
        apply_btn.clicked.connect(self._on_apply)
        cancel_btn.clicked.connect(self.close)

        self.destroyed.connect(self._disconnect)

        self._on_sys_config_loaded()

    # -------------- Public API --------------

    def value(self) -> list[PixelSizePreset]:
        """Return the current state of the widget describing the pixel configurations.

        Returns
        -------
        list[PixelSizePreset][pymmcore_plus.model.PixelSizePreset]
            A list of pixel configurations data.

        Example:
        -------
            output = [
                PixelSizePreset(
                    name='Res10x',
                    settings=[Setting('Objective', 'Label', 'Nikon 10X S Fluor')],
                    pixel_size_um=1.0
                ),
                ...
            ]
        """
        return list(self._resID_map.values())

    def setValue(self, value: list[PixelSizePreset]) -> None:
        """Set the state of the widget describing the pixel configurations.

        Parameters
        ----------
        value : list[PixelSizePreset][pymmcore_plus.model.PixelSizePreset]
            The list of pixel configurations data to set.

        Example:
        -------
            input = [
                PixelSizePreset(
                    name='Res10x',
                    settings=[Setting('Objective', 'Label', 'Nikon 10X S Fluor')],
                    pixel_size_um=1.0
                ),
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
                self._px_table.ID.key: rec.name,
                self._px_table.VALUE.key: rec.pixel_size_um,
            }
            self._px_table.table().setRowData(row, data)

        self._px_table._table.selectRow(0)

    # -------------- Private API --------------

    def _on_sys_config_loaded(self) -> None:
        self._px_table._remove_all()
        self._resID_map.clear()

        px_groups = PixelSizeGroup.create_from_core(self._mmc)
        if not px_groups.presets:
            self._props_selector._prop_table.uncheckAll()
            self._props_selector.setEnabled(False)
            return

        for row, px_preset in enumerate(px_groups.presets.values()):
            self._resID_map[row] = px_preset
            data = {
                self._px_table.ID.key: px_preset.name,
                self._px_table.VALUE.key: px_preset.pixel_size_um,
            }
            self._px_table._add_row()
            self._px_table.table().setRowData(row, data)
            # connect the valueChanged signal of the px table spinboxes.
            wdg = cast(QDoubleSpinBox, self._px_table._table.cellWidget(row, 1))
            wdg.valueChanged.connect(self._on_px_value_changed)

            if row == 0:
                # check all the device-property for the first resolutionID
                self._props_selector.setValue(px_preset.settings)
                # select first row of px_table corresponding to the first resolutionID
                self._px_table._table.selectRow(row)

    def _on_viewer_value_changed(self, value: list[Setting]) -> None:
        # get row of the selected resolutionID
        items = self._px_table._table.selectedItems()
        if len(items) != 1:
            return
        self._resID_map[items[0].row()].settings = value
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
        self._props_selector.setValue(self._resID_map[row].settings)
        with signals_blocked(self._affine_table):
            self._affine_table.setValue(self._resID_map[row].affine)

    def _on_resolutionID_name_changed(self, item: QTableWidgetItem) -> None:
        """Update the resolutionID name in the configuration map."""
        res_ID_row, res_ID_name = item.row(), item.text()

        # get the old res_ID_name
        old_res_ID_name = self._resID_map[res_ID_row].name

        # if the name is the same as the current one, return
        if res_ID_name == old_res_ID_name:
            return

        # if the name already exists, raise a warning and return
        # if res_ID_name in self.value():
        if res_ID_name in self._value_to_dict(self.value()):
            warnings.warn(f"ResolutionID '{res_ID_name}' already exists.", stacklevel=2)
            self._px_table.table().item(res_ID_row, 0).setText(old_res_ID_name)
            return

        self._resID_map[item.row()].name = res_ID_name

    def _value_to_dict(
        self, value: list[PixelSizePreset]
    ) -> dict[str, PixelSizePreset]:
        """list[PixelSizePreset] to dict[PixelSizePreset.name: PixelSizePreset]."""
        return {rec.name: rec for rec in value}

    def _on_px_value_changed(self) -> None:
        """Update the pixel size value in the configuration map."""
        spin = cast(QDoubleSpinBox, self.sender())
        table = cast(DataTable, self.sender().parent().parent())
        row = table.indexAt(spin.pos()).row()
        self._resID_map[row].pixel_size_um = spin.value()
        self._update_affine_transformations(spin.value())

    def _update_affine_transformations(self, px_value: float) -> None:
        """Update the affine transformations."""
        self._affine_table.setValue([px_value, 0.0, 0.0, 0.0, px_value, 0.0])
        affine = self._affine_table.value()
        items = self._px_table._table.selectedItems()
        if len(items) != 1:
            return
        self._resID_map[items[0].row()].affine = affine

    def _on_affine_value_changed(self) -> None:
        """Update the affine transformations in the configuration map."""
        affine = self._affine_table.value()
        items = self._px_table._table.selectedItems()
        if len(items) != 1:
            return
        self._resID_map[items[0].row()].affine = affine

    def _on_px_table_value_changed(self) -> None:
        """Update the data of the pixel table when the value changes."""
        # if the table is empty clear the configuration map and unchecked all rows
        if not self._px_table.value():
            self._resID_map.clear()
            self._props_selector._prop_table.uncheckAll()
            self._affine_table.setValue(DEFAULT_AFFINE)
            return

        # if an item is deleted, remove it from the configuration map
        if len(self._px_table.value()) != len(self._resID_map):
            # get the resolutionIDs in the pixel table
            res_IDs = [rec[ID] for rec in self._px_table.value()]
            # get the resolutionIDs to delete
            to_delete: list[int] = [
                row
                for row in self._resID_map
                if self._resID_map[row].name not in res_IDs
            ]
            # delete the resolutionIDs from the configuration map
            for row in to_delete:
                del self._resID_map[row]

            # renumber the keys in the configuration map
            self._resID_map = {
                new_key: self._resID_map[old_key]
                for new_key, old_key in enumerate(self._resID_map)
            }

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
        props = self._resID_map[0].settings if self._resID_map else []
        self._resID_map[end] = PixelSizePreset(NEW, props)

        # connect the valueChanged signal of the spinbox
        wdg = cast(QDoubleSpinBox, self._px_table._table.cellWidget(end, 1))
        wdg.valueChanged.connect(self._on_px_value_changed)

        # select the added row
        self._px_table._table.selectRow(end)

    def _update_other_resolutionIDs(
        self,
        selected_resID_row: int,
        selected_resID_props: list[Setting],
    ) -> None:
        """Update the data of in all resolutionIDs if different than the data of the
        selected resolutionID. All the resolutionIDs should have the same devices and
        properties.
        """  # noqa: D205
        # selected_dev_prop = [(dev, prop) for dev, prop, _ in selected_resID_props]
        selected_dev_prop = [
            (setting.device_name, setting.property_name)
            for setting in selected_resID_props
        ]

        for row in range(self._px_table._table.rowCount()):
            # skip the selected resolutionID
            if row == selected_resID_row:
                continue

            # get the dev-prop-val of the resolutionID
            properties = self._resID_map[row].settings

            # remove the devs-props that are not in the selected resolutionID
            properties = [
                setting
                for setting in properties
                if (setting.device_name, setting.property_name) in selected_dev_prop
            ]

            # add the missing devices and properties
            res_id_dev_prop = {
                (setting.device_name, setting.property_name) for setting in properties
            }
            properties += [
                setting
                for setting in selected_resID_props
                if (setting.device_name, setting.property_name) not in res_id_dev_prop
            ]

            self._resID_map[row].settings = sorted(
                properties, key=lambda x: x.device_name
            )

    def _on_apply(self) -> None:
        """Update the current pixel size configurations."""
        # check if there are errors in the pixel configurations
        if self._check_for_errors():
            return

        # delete all the pixel size configurations
        for resolutionID in self._mmc.getAvailablePixelSizeConfigs():
            self._mmc.deletePixelSizeConfig(resolutionID)

        # create the new pixel size configurations
        # px_groups = PixelSizeGroup(presets=self.value())
        px_groups = PixelSizeGroup(presets=self._value_to_dict(self.value()))
        px_groups.apply_to_core(self._mmc)
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

        # check that each resolutionID have at least one property
        if not all(self._resID_map[row].settings for row in range(len(resolutionIDs))):
            return self._show_error_message(
                "Each resolutionID must have at least one property."
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

    ID = TextColumn(key=ID, header="ResolutionID", default=NEW, is_row_selector=False)
    VALUE = FloatColumn(
        key=PX, header="pixel value [µm]", default=0, is_row_selector=False
    )

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, parent)

        self._toolbar.removeAction(self.act_check_all)
        self._toolbar.removeAction(self.act_check_none)
        self._toolbar.actions()[2].setVisible(False)  # separator

        h_header = cast("QHeaderView", self._table.horizontalHeader())
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)


class AffineTable(QTableWidget):
    """A table to display the affine transformations matrix."""

    valueChanged = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(20)
        self.verticalHeader().setVisible(False)

        self.setColumnCount(3)
        self.setRowCount(3)

        # add a spinbox in each cell of the table
        self._add_table_spinboxes()
        self.setValue(DEFAULT_AFFINE)

    def sizeHint(self) -> Any:
        sz = self.minimumSizeHint()
        rc = self.rowCount()
        sz.setHeight(self.rowHeight(0) * rc + (rc - 1))
        return sz

    def _add_table_spinboxes(self) -> None:
        """Add a spinbox in each cell of the table."""
        for row, col in itertools.product(range(3), range(3)):
            spin = QDoubleSpinBox()
            spin.setRange(-100000, 100000)
            spin.setDecimals(1)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            self.setCellWidget(row, col, spin)
            # disable the spinboxes in the last row
            if row == 2:
                spin.setReadOnly(True)
                spin.setEnabled(False)
                # set the value of the last row to 1.0
                if col == 2:
                    spin.setValue(1.0)
            # connect the valueChanged signal of the spinboxes to global valueChanged
            else:
                spin.valueChanged.connect(self.valueChanged)

    def value(self) -> tuple[float, float, float, float, float, float]:
        """Return the current widget value describing the affine transformation."""
        value: list[float] = []
        for row, col in itertools.product(range(2), range(3)):
            spin = cast(QDoubleSpinBox, self.cellWidget(row, col))
            value.append(spin.value())
        return tuple(value)  # type: ignore

    def setValue(self, value: Sequence[float]) -> None:
        """Set the current widget value describing the affine transformation."""
        if len(value) != 6:
            raise ValueError("The affine transformation must have 6 values.")

        for row, col in itertools.product(range(2), range(3)):
            spin = cast(QDoubleSpinBox, self.cellWidget(row, col))
            spin.setValue(value[row * 3 + col])


class _PropertySelector(QWidget):
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
        table_and_filter_layout.setContentsMargins(0, 0, 0, 0)
        table_and_filter_layout.addWidget(self._filter_text)
        table_and_filter_layout.addWidget(self._prop_table)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setContentsMargins(0, 0, 0, 0)
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
        left.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

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
