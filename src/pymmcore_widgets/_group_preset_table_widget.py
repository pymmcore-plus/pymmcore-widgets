from typing import Tuple, Union

from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets as QtW
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QVBoxLayout

from ._presets_widget import PresetsWidget
from ._property_widget import PropertyWidget


class _MainTable(QtW.QTableWidget):
    """Set table properties for Group and Preset TableWidget."""

    def __init__(self) -> None:
        super().__init__()
        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(hdr.Stretch)
        hdr.setDefaultAlignment(Qt.AlignHCenter)
        vh = self.verticalHeader()
        vh.setVisible(False)
        vh.setSectionResizeMode(vh.Fixed)
        vh.setDefaultSectionSize(24)
        self.setEditTriggers(QtW.QTableWidget.NoEditTriggers)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Group", "Preset"])


class GroupPresetTableWidget(QtW.QWidget):
    """Widget to get/set group presets."""

    def __init__(self) -> None:
        super().__init__()

        self._mmc = CMMCorePlus.instance()
        self._mmc.events.systemConfigurationLoaded.connect(self._populate_table)
        self.table_wdg = _MainTable()
        self.table_wdg.show()
        self.setLayout(QVBoxLayout())
        self.setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.table_wdg)

        self._populate_table()

    def _on_system_cfg_loaded(self) -> None:
        self._populate_table()

    def _reset_table(self) -> None:
        self._disconnect_wdgs()
        self.table_wdg.clearContents()
        self.table_wdg.setRowCount(0)

    def _disconnect_wdgs(self) -> None:
        for r in range(self.table_wdg.rowCount()):
            wdg = self.table_wdg.cellWidget(r, 1)
            if isinstance(wdg, PresetsWidget):
                wdg.disconnect()

    def _populate_table(self) -> None:
        self._reset_table()
        if groups := self._mmc.getAvailableConfigGroups():
            for row, group in enumerate(groups):
                self.table_wdg.insertRow(row)
                self.table_wdg.setItem(row, 0, QtW.QTableWidgetItem(str(group)))
                wdg = self._create_group_widget(group)
                self.table_wdg.setCellWidget(row, 1, wdg)
                if isinstance(wdg, PresetsWidget):
                    wdg = wdg._combo
                elif isinstance(wdg, PropertyWidget):
                    wdg = wdg._value_widget  # type: ignore

    def _get_cfg_data(self, group: str, preset: str) -> Tuple[str, str, str, int]:
        # Return last device-property-value for the preset and the
        # total number of device-property-value included in the preset.
        data = list(self._mmc.getConfigData(group, preset))
        assert len(data), "No config data"
        dev, prop, val = data[-1]
        return dev, prop, val, len(data)

    def _create_group_widget(self, group: str) -> Union[PresetsWidget, PropertyWidget]:
        """Return a widget depending on presets and device-property."""
        # get group presets
        presets = list(self._mmc.getAvailableConfigs(group))

        if not presets:
            return  # type: ignore

        # use only the first preset since device
        # and property are the same for the presets
        device, property, _, dev_prop_val_count = self._get_cfg_data(group, presets[0])

        if len(presets) > 1 or dev_prop_val_count > 1:
            # return PresetsWidget(group, text_color="white")
            return PresetsWidget(group)
        else:
            return PropertyWidget(device, property)
