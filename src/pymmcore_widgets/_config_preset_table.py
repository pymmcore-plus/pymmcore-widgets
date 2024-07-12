from typing import DefaultDict, cast

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize
from qtpy.QtWidgets import QTableWidget, QTableWidgetItem, QWidget

from pymmcore_widgets import PropertyWidget


class ConfigPresetTable(QTableWidget):
    def __init__(
        self, parent: QWidget | None = None, core: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)
        self._core = core or CMMCorePlus.instance()
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(hh.ResizeMode.Stretch)

    def sizeHint(self) -> QSize:
        return QSize(1000, 200)

    def loadGroup(self, group: str) -> None:
        self._rebuild_table(group)

    def _rebuild_table(self, group: str) -> None:
        # Get all presets and their properties
        # Mapping {preset -> {(dev, prop) -> val}}
        preset2props: DefaultDict[str, dict[tuple[str, str], str]] = DefaultDict(dict)
        for preset in self._core.getAvailableConfigs(group):
            for dev, prop, _val in self._core.getConfigData(group, preset):
                preset2props[preset][(dev, prop)] = _val

        all_props = set.union(*[set(props.keys()) for props in preset2props.values()])
        self.setColumnCount(len(preset2props))
        self.setRowCount(len(all_props))

        # store which device/property is in which row
        ROWS: dict[tuple[str, str], int] = {}

        for row, (dev, prop) in enumerate(sorted(all_props)):
            ROWS[(dev, prop)] = row
            name = "Active" if dev == "Core" else dev
            self.setVerticalHeaderItem(row, QTableWidgetItem(f"{name}-{prop}"))

        for col, (preset, props) in enumerate(preset2props.items()):
            self.setHorizontalHeaderItem(col, QTableWidgetItem(preset))
            for (dev, prop), val in props.items():
                wdg = PropertyWidget(dev, prop, mmcore=self._core, connect_core=False)
                wdg._preset = preset
                wdg.setValue(val)
                wdg.valueChanged.connect(self._on_value_changed)
                self.setCellWidget(ROWS[(dev, prop)], col, wdg)

    def _on_value_changed(self, val) -> None:
        wdg = cast("PropertyWidget", self.sender())
        print("preset", wdg._preset, "changed", wdg._dp, "to", val)
