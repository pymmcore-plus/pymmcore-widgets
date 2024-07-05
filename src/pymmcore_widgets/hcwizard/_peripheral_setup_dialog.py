from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, cast

from pymmcore_plus.model import Device, Microscope
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import exceptions_as_dialog

from ._dev_setup_dialog import DeviceSetupDialog

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus

FLAGS = Qt.WindowType.MSWindowsFixedSizeDialogHint | Qt.WindowType.Sheet


class PeripheralSetupDlg(QDialog):
    def __init__(
        self,
        device: Device,
        model: Microscope,
        core: CMMCorePlus,
        parent: QWidget | None = None,
        flags: Qt.WindowType = FLAGS,
    ):
        super().__init__(parent, flags)
        self._device = device
        self._model = model
        self._core = core
        self.setWindowTitle(f"Add {device.name} Peripherals")
        self.btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.btns.accepted.connect(self.accept)
        self.btns.rejected.connect(self.reject)

        headers = ["Label (editable)", "Adapter", "Description"]
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.itemChanged.connect(self._on_selection_changed)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(hh.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(0, hh.ResizeMode.Stretch)
        self.table.verticalHeader().hide()

        self._select_all = QCheckBox("Select All")
        self._select_all.setTristate(True)
        self._select_all.setCheckState(Qt.CheckState.Unchecked)
        self._select_all.clicked.connect(self._on_select_all_clicked)

        bot_row = QHBoxLayout()
        bot_row.setContentsMargins(0, 0, 0, 0)
        bot_row.addWidget(self._select_all)
        bot_row.addStretch()
        bot_row.addWidget(self.btns)

        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.addWidget(QLabel(f"Add peripherals for {device.name}"))
        layout.addWidget(self.table)
        layout.addLayout(bot_row)

        self.rebuild_table()

    def sizeHint(self) -> QSize:
        height = self.table.rowCount() * self.table.rowHeight(0) + 130
        return super().sizeHint().expandedTo(QSize(600, height))

    def rebuild_table(self) -> None:
        """Rebuild the table of available peripherals."""
        peripherals = list(self._device.available_peripherals(self._model))
        self.table.setRowCount(len(peripherals))
        for row, child in enumerate(peripherals):
            item = QTableWidgetItem(child.adapter_name)
            item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEditable
                | Qt.ItemFlag.ItemIsEnabled,
            )
            item.setData(Qt.ItemDataRole.UserRole, child)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, item)

            item = QTableWidgetItem(child.adapter_name)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.table.setItem(row, 1, item)

            item = QTableWidgetItem(child.description)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.table.setItem(row, 2, item)

    def selectedPeripherals(self) -> Iterable[Device]:
        """Return a list of the selected peripherals."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                dev = cast("Device", item.data(Qt.ItemDataRole.UserRole))
                yield dev.replace(name=item.text(), parent_label=self._device.name)

    def accept(self) -> None:
        """Accept the dialog and add the selected peripherals."""
        for dev in self.selectedPeripherals():
            with exceptions_as_dialog(use_error_message=True):
                self._init_device(dev)
        super().accept()

    def _init_device(self, dev: Device) -> None:
        """Initialize the device with the current core state."""
        dev.load(self._core)
        dev.apply_to_core(self._core)
        if any(p.is_pre_init for p in dev.properties):
            dlg = DeviceSetupDialog(
                self._core, dev.name, dev.library, dev.adapter_name, self
            )
            if not dlg.exec():
                return
            dev = Device.create_from_core(
                self._core, name=dlg.deviceLabel(), initialized=True
            )
        else:
            dev.initialize(self._core)

        self._model.devices.append(dev)

    def _on_select_all_clicked(self, state: bool) -> None:
        """Select or deselect all peripherals."""
        if self._select_all.checkState() == Qt.CheckState.PartiallyChecked:
            state = Qt.CheckState.Checked
            self._select_all.setCheckState(Qt.CheckState.Checked)
        else:
            state = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState(state))

    def _on_selection_changed(self) -> None:
        self._select_all.setCheckState(self._table_selection_state())

    def _table_selection_state(self) -> Qt.CheckState:
        # determine how many of the items are checked
        num_checked = 0
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                num_checked += 1

        if num_checked == 0:
            return Qt.CheckState.Unchecked
        if num_checked == self.table.rowCount():
            return Qt.CheckState.Checked
        return Qt.CheckState.PartiallyChecked
