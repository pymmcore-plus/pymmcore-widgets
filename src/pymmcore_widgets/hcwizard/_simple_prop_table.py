"""Simple Property Table, with no connections to core like in DevicePropertyBrowser."""

from __future__ import annotations

from typing import Iterator, Sequence

from pymmcore_plus import CMMCorePlus, Keyword
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QComboBox, QTableWidget, QTableWidgetItem, QWidget

from pymmcore_widgets.device_properties._property_widget import PropertyWidget


class PortSelector(QComboBox):
    """Simple combobox that emits (device_name, library_name) when changed."""

    portChanged = Signal(str, str)  # device_name, library_name

    def __init__(
        self,
        allowed_values: Sequence[tuple[str | None, str]],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        for library, device_name in allowed_values:
            self.addItem(device_name, library)
        self.currentTextChanged.connect(self._on_current_text_changed)

    def _on_current_text_changed(self, text: str) -> None:
        self.portChanged.emit(text, self.currentData())

    def value(self) -> str:
        """Implement ValueWidget interface."""
        return self.currentText()  # type: ignore


class PropTable(QTableWidget):
    """Simple Property Table."""

    portChanged = Signal(str, str)

    def __init__(self, core: CMMCorePlus, parent: QWidget | None = None) -> None:
        super().__init__(0, 2, parent)
        self._core = core
        self.setHorizontalHeaderLabels(["Property", "Value"])
        self.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionMode(self.SelectionMode.NoSelection)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(24)
        self.setColumnWidth(0, 200)

    def iterRows(self) -> Iterator[tuple[str, str]]:
        """Iterate over rows, yielding (prop_name, prop_value)."""
        for r in range(self.rowCount()):
            wdg = self.cellWidget(r, 1)
            if isinstance(wdg, PortSelector):
                yield Keyword.Port, wdg.value()
            elif isinstance(wdg, PropertyWidget):
                yield self.item(r, 0).text(), wdg.value()

    def rebuild(
        self,
        device_props: Sequence[tuple[str, str]],
        available_com_ports: Sequence[tuple[str, str]] = (),
    ) -> None:
        """Rebuild the table for the given device and prop_names."""
        self.setRowCount(len(device_props))
        for i, (device, prop_name) in enumerate(device_props):
            self.setItem(i, 0, QTableWidgetItem(prop_name))
            if prop_name == Keyword.Port:
                # add the current property if it's not already in there
                # it might be something like "Undefined"
                allow: list[tuple[str | None, str]] = sorted(
                    available_com_ports, key=lambda x: x[1]
                )
                current = self._core.getProperty(device, prop_name)
                if not any(x[1] == current for x in allow):
                    allow = [(None, current), *allow]
                wdg = PortSelector(allow)
                wdg.setCurrentText(current)
                wdg.portChanged.connect(self.portChanged)
            else:
                wdg = PropertyWidget(
                    device, prop_name, mmcore=self._core, connect_core=False
                )
            self.setCellWidget(i, 1, wdg)
