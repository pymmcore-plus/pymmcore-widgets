import logging
from typing import cast

from pymmcore_plus import CMMCorePlus, DeviceType
from pymmcore_plus.model import Device, Microscope
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from superqt.utils import signals_blocked

from ._base_page import ConfigWizardPage

logger = logging.getLogger(__name__)


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
        dev = cast("Device", item.data(Qt.ItemDataRole.UserRole))
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

        self._read_hw_btn = QPushButton("Read from Hardware")
        self._read_hw_btn.setToolTip(
            "Read the current state labels from the hardware device"
        )
        self._read_hw_btn.clicked.connect(self._read_labels_from_hardware)

        row = QHBoxLayout()
        row.addWidget(QLabel("Device:"))
        row.addWidget(self.dev_combo, 1)
        row.addWidget(self._read_hw_btn)

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

    def _read_labels_from_hardware(self) -> None:
        """Read state labels from the hardware device and update the table."""
        dev_name = self.dev_combo.currentText()
        if not dev_name:
            return

        try:
            hw_labels = self._core.getStateLabels(dev_name)
        except Exception:  # pragma: no cover
            logger.exception("Failed to read labels from hardware for %s", dev_name)
            return

        dev = self._model.get_device(dev_name)
        for i, label in enumerate(hw_labels):
            if i < len(dev.labels):
                dev.set_label(i, label)

        self.labels_table.rebuild(dev_name)
