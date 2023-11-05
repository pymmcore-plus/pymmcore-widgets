from typing import TYPE_CHECKING, cast

from pymmcore_plus import CMMCorePlus, DeviceProperty
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
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


class PixelConfigurationWidget(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str = "",
        mmcore: CMMCorePlus | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle(title)

        self._px_cfg_map: dict = {}

        self._mmc = mmcore or CMMCorePlus.instance()

        self._px_table = _PixelTable()
        self._props = _Properties(mmcore=self._mmc)

        # buttons
        ok_btn = QPushButton("Save")
        ok_btn.setSizePolicy(FIXED)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setSizePolicy(FIXED)
        btns_layout = QHBoxLayout()
        btns_layout.setContentsMargins(0, 0, 0, 0)
        btns_layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        )
        btns_layout.addWidget(ok_btn)
        btns_layout.addWidget(cancel_btn)

        # main layout
        main_layout = QGridLayout(self)
        main_layout.addWidget(self._px_table, 0, 0)
        main_layout.addWidget(self._props, 0, 1)
        main_layout.addLayout(btns_layout, 2, 1)

        # connect signals
        self._px_table._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._px_table.valueChanged.connect(self._on_value_changed)
        ok_btn.clicked.connect(self._on_save)
        cancel_btn.clicked.connect(self.close)

        # self._px_table.valueChanged.connect(self._p)
        # self._props.valueChanged.connect(self._p)

        self._on_sys_config_loaded()

    # def _p(self, args):
    #     print("\nchanged")
    #     if args:
    #         print(args)

    def _on_sys_config_loaded(self) -> None:
        self._px_cfg_map = {}
        self._px_table._remove_all()
        cfgs = [
            {"id": c, "px": self._mmc.getPixelSizeUmByID(c)}
            for c in self._mmc.getAvailablePixelSizeConfigs()
        ]
        self._px_table.setValue(cfgs)

        # select first config
        self._px_table._table.selectRow(0)
        self._check_and_update(self._mmc.getAvailablePixelSizeConfigs()[0])

        for c in self._mmc.getAvailablePixelSizeConfigs():
            self._px_cfg_map[c] = {
                "px": self._mmc.getPixelSizeUmByID(c),
                **self._mmc.getPixelSizeConfigData(c).dict(),
            }

        from rich import print

        print(self._px_cfg_map)

    def _on_value_changed(self) -> None:
        # unchecked all properties rows if the table is empty
        if not self._px_table.value():
            self._check_and_update("")
            self._props._device_filters.setShowCheckedOnly(False)

        # delete pixel size configurations that are not in the table
        current_cfg = self._mmc.getAvailablePixelSizeConfigs()
        value = [v["id"] for v in self._px_table.value()]
        for resolutionID in current_cfg:
            if resolutionID not in value:
                self._mmc.deletePixelSizeConfig(resolutionID)

    def _on_selection_changed(self) -> None:
        rows = self._px_table._table.selectedItems()
        if len(rows) != 1:
            return
        self._check_and_update(rows[0].text())

    def _check_and_update(self, px_cfg: str) -> None:
        """Check the properties that are included in the specified configuration."""
        # if the configuration does not have a name or it does not exist, the
        # 'included' list should be empty so that all properties are unchecked
        if not px_cfg:
            included = []
        else:
            try:
                included = [
                    tuple(c)[:2] for c in self._mmc.getPixelSizeConfigData(px_cfg)
                ]
            except ValueError:
                included = []

        for row in range(self._props._prop_table.rowCount()):
            prop = cast(
                DeviceProperty,
                self._props._prop_table.item(row, 0).data(
                    self._props._prop_table.PROP_ROLE
                ),
            )
            if (prop.device, prop.name) in included:
                self._props._prop_table.item(row, 0).setCheckState(
                    Qt.CheckState.Checked
                )
                self._update_wdg_value(px_cfg, prop, row)
            else:
                self._props._prop_table.item(row, 0).setCheckState(
                    Qt.CheckState.Unchecked
                )
        # unchecked the 'show checked-only' checkbox if 'included' is empty
        if not included:
            self._props._device_filters.setShowCheckedOnly(False)

    def _update_wdg_value(self, px_cfg: str, prop: DeviceProperty, row: int) -> None:
        """Update the value of the property widget."""
        dpv = [tuple(c) for c in self._mmc.getPixelSizeConfigData(px_cfg)]
        for d, p, v in dpv:
            if d == prop.device and p == prop.name:
                wdg = cast("PropertyWidget", self._props._prop_table.cellWidget(row, 1))
                wdg.setValue(v)
                break

    def _delete_px_config(self, resolutionID: str) -> None:
        if resolutionID in self._mmc.getAvailablePixelSizeConfigs():
            self._mmc.deletePixelSizeConfig(resolutionID)

    def _on_save(self) -> None:
        from rich import print

        print(self._px_table.value())
        print(self._props._prop_table.getCheckedProperties())

    def value(self) -> None:
        ...

    def setValue(self, value: list[dict[str, str]]) -> None:
        ...


class _PixelTable(DataTableWidget):
    ID = TextColumn(
        key="id", header="pixel configuration name", default=None, is_row_selector=False
    )
    VALUE = FloatColumn(
        key="px", header="pixel value [µm]", default=0, is_row_selector=False
    )

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, parent)

        self._toolbar.removeAction(self.act_check_all)
        self._toolbar.removeAction(self.act_check_none)
        self._toolbar.actions()[2].setVisible(False)  # separator


class _Properties(QWidget):
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

    def _update_filter(self) -> None:
        filt = self._filter_text.text().lower()
        self._prop_table.filterDevices(
            filt,
            exclude_devices=self._device_filters.filters(),
            include_read_only=self._device_filters.showReadOnly(),
            include_pre_init=self._device_filters.showPreInitProps(),
            include_checked_only=self._device_filters.showCheckedOnly(),
        )


class GroupPresetWidget(QWidget):
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

        self._gp_table = _GroupPresetTable()

        self._props = _Properties(mmcore=self._mmc)

        main_layout = QGridLayout(self)
        main_layout.addWidget(self._gp_table, 0, 0)
        main_layout.addWidget(self._props, 0, 1)

        self._gp_table._table.itemSelectionChanged.connect(self._on_selection_changed)

        self._on_sys_config_loaded()

    def _on_sys_config_loaded(self) -> None:
        self._gp_table._remove_all()
        groups = [{"group": gp} for gp in self._mmc.getAvailableConfigGroups()]
        self._gp_table.setValue(groups)

        # select first group
        self._gp_table._table.selectRow(0)
        self._props._prop_table.checkGroup(self._mmc.getAvailableConfigGroups()[0])

    def _on_selection_changed(self) -> None:
        rows = self._gp_table._table.selectedItems()
        if len(rows) != 1:
            return
        print("selection changed:", rows[0].text())
        self._props._prop_table.checkGroup(rows[0].text())


class _GroupPresetTable(DataTableWidget):
    ID = TextColumn(key="group", header="group", default=None, is_row_selector=False)

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, parent)

        self._toolbar.removeAction(self.act_check_all)
        self._toolbar.removeAction(self.act_check_none)
        self._toolbar.actions()[2].setVisible(False)  # separator


app = QApplication([])
mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()
px = PixelConfigurationWidget(title="Pixel Configuration Widget")
px.show()
# gp = GroupPresetWidget(title="Group Preset Widget")
# gp.show()
app.exec_()
