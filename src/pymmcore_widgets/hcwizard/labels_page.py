from typing import cast

from pymmcore_plus import CMMCorePlus, DeviceType
from pymmcore_plus.model import Device, Microscope
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from superqt.utils import signals_blocked

from ._base_page import ConfigWizardPage


class _LabelTable(QTableWidget):
    def __init__(self, model: Microscope):
        headers = ["State", "Label"]
        super().__init__(0, len(headers))
        self._model = model

        self.setSelectionMode(self.SelectionMode.NoSelection)
        self.setHorizontalHeaderLabels(headers)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)

        self.itemChanged.connect(self._on_item_changed)

    def rebuild(self, dev_name: str) -> None:
        """Rebuild the table for the given device."""
        if not dev_name:
            return

        self.clearContents()
        dev = self._model.get_device(dev_name)
        self.setRowCount(len(dev.labels))
        for i, label in enumerate(dev.labels):
            state = QTableWidgetItem(str(i))
            state.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            state.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.setItem(i, 0, state)
            lbl = QTableWidgetItem(label)
            lbl.setData(Qt.ItemDataRole.UserRole, dev)
            self.setItem(i, 1, lbl)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 1:
            return
        dev = cast(Device, item.data(Qt.ItemDataRole.UserRole))
        dev.set_label(item.row(), item.text())


class LabelsPage(ConfigWizardPage):
    """Provide a table for defining position labels for state devices."""

    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__(model, core)
        self.setTitle("Define position labels for state devices")
        self.setSubTitle(
            "Some devices, such as filter wheels and objective turrets, have discrete "
            "positions that can have names assigned to them. For example, position 1 "
            "of a filter wheel could be the DAPI channel, position 2 the FITC channel, "
            "etc.<br><br>You may assign names to positions here."
        )

        self.labels_table = _LabelTable(self._model)

        self.dev_combo = QComboBox()
        self.dev_combo.currentTextChanged.connect(self.labels_table.rebuild)

        row = QHBoxLayout()
        row.addWidget(QLabel("Device:"))
        row.addWidget(self.dev_combo, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self.labels_table)

    def initializePage(self) -> None:
        """Called to prepare the page just before it is shown."""
        with signals_blocked(self.dev_combo):
            txt = self.dev_combo.currentText()
            self.dev_combo.clear()
            items = [
                d.name for d in self._model.devices if d.device_type == DeviceType.State
            ]
            self.dev_combo.addItems(items)
            if txt in items:
                self.dev_combo.setCurrentText(txt)

        self.labels_table.rebuild(self.dev_combo.currentText())
        super().initializePage()
