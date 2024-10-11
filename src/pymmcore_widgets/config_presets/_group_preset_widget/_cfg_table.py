from __future__ import annotations

from typing import Any, Sequence, cast

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QTableWidget, QTableWidgetItem

from pymmcore_widgets.device_properties._property_widget import PropertyWidget

DEV_PROP_ROLE = Qt.ItemDataRole.UserRole + 1


class _CfgTable(QTableWidget):
    """Set table properties for EditPresetWidget."""

    def __init__(self) -> None:
        super().__init__()
        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(hdr.ResizeMode.Stretch)
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignHCenter)
        vh = self.verticalHeader()
        vh.setVisible(False)
        vh.setSectionResizeMode(vh.ResizeMode.Fixed)
        vh.setDefaultSectionSize(24)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Device-Property", "Value"])

    def populate_table(self, dev_prop_val: Sequence[Sequence[Any]]) -> None:
        self.clearContents()
        self.setRowCount(len(dev_prop_val))
        for idx, (dev, prop, *_) in enumerate(dev_prop_val):
            item = QTableWidgetItem(f"{dev}-{prop}")
            item.setData(DEV_PROP_ROLE, (dev, prop))
            wdg = PropertyWidget(dev, prop, connect_core=False)
            self.setItem(idx, 0, item)
            self.setCellWidget(idx, 1, wdg)

    def get_state(self) -> list[tuple[str, str, str]]:
        dev_prop_val = []
        for row in range(self.rowCount()):
            if (dev_prop_item := self.item(row, 0)) and (
                wdg := cast("PropertyWidget", self.cellWidget(row, 1))
            ):
                dev, prop = dev_prop_item.data(DEV_PROP_ROLE)
                dev_prop_val.append((dev, prop, str(wdg.value())))
        return dev_prop_val
