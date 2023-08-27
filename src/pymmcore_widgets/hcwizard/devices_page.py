import logging
from contextlib import suppress
from typing import cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, DeviceType
from pymmcore_plus.model import Device, Microscope
from qtpy.QtCore import QRegularExpression, Qt, Signal
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon
from superqt.utils import exceptions_as_dialog

from pymmcore_widgets._device_property_table import ICONS

from ._base_page import ConfigWizardPage
from ._dev_setup_dialog import DeviceSetupDialog
from ._peripheral_setup_dialog import PeripheralSetupDlg

logger = logging.getLogger(__name__)


class _DeviceTable(QTableWidget):
    """Table of currently configured devices."""

    def __init__(self, core: CMMCorePlus, parent: QWidget | None = None):
        headers = ["", "Name", "Adapter/Module", "Description", "Status"]
        super().__init__(0, len(headers), parent)
        self._core = core

        self.setHorizontalHeaderLabels(headers)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        self.verticalHeader().setVisible(False)
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(hh.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, hh.ResizeMode.Stretch)

    def rebuild(self, model: Microscope, errs: dict[str, str] | None = None) -> None:
        errs = errs or {}
        self.clearContents()
        self.setRowCount(len(model.devices))
        for i, device in enumerate(model.devices):
            type_icon = ICONS.get(device.device_type, "")
            if device.device_type == DeviceType.Hub:
                btn = QPushButton(icon(type_icon, color="blue"), "")
                btn.setToolTip("Add peripheral device")
                btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                btn.clicked.connect(
                    lambda _, d=device, m=model: self._edit_peripherals(d, m)
                )
                self.setCellWidget(i, 0, btn)
            else:
                item = QTableWidgetItem(icon(type_icon, color="Gray"), "")
                self.setItem(i, 0, item)

            item = QTableWidgetItem(device.name)
            item.setData(Qt.ItemDataRole.UserRole, device)
            self.setItem(i, 1, item)
            self.setItem(i, 2, QTableWidgetItem(device.adapter_name))
            self.setItem(i, 3, QTableWidgetItem(device.description))

            if device.device_type == DeviceType.Core:
                status = "Core"
                _icon = icon(MDI6.heart_cog, color="gray")
            elif device.initialized:
                status = "OK"
                _icon = icon(MDI6.check_circle, color="green")
            else:
                status = "Failed"
                _icon = icon(MDI6.alert, color="Red")
            item = QTableWidgetItem(_icon, status)
            if info := errs.get(device.name):
                item.setToolTip(str(info))
            self.setItem(i, 4, item)

    def _edit_peripherals(self, device: Device, model: Microscope) -> None:
        dlg = PeripheralSetupDlg(device, model, self._core, self)
        if dlg.exec():
            self.rebuild(model)


class _CurrentDevicesWidget(QWidget):
    def __init__(
        self, model: Microscope, core: CMMCorePlus, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._core = core
        self.table = _DeviceTable(core, self)
        self.table.cellDoubleClicked.connect(self._edit_selected_device)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        self.edit_btn = QPushButton(icon(MDI6.pencil), "Edit")
        self.edit_btn.setDisabled(True)
        self.edit_btn.clicked.connect(self._edit_selected_device)

        self.remove_btn = QPushButton(icon(MDI6.delete), "Remove")
        self.remove_btn.setDisabled(True)
        self.remove_btn.clicked.connect(self._remove_selected_devices)

        row = QHBoxLayout()
        lbl = QLabel("Installed Devices:")
        font = lbl.font()
        font.setBold(True)
        lbl.setFont(font)
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(self.edit_btn)
        row.addWidget(self.remove_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(row)
        layout.addWidget(self.table)

    def rebuild_table(self, errs: dict[str, str] | None = None) -> None:
        self.table.rebuild(self._model, errs)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event and event.key() in {Qt.Key.Key_Backspace, Qt.Key.Key_Delete}:
            self._remove_selected_devices()
        else:
            super().keyPressEvent(event)

    def _on_selection_changed(self) -> None:
        selected_rows = {x.row() for x in self.table.selectedItems()}
        n_selected = len(selected_rows)
        self.edit_btn.setEnabled(n_selected == 1)
        self.remove_btn.setEnabled(n_selected > 0)

    def _selected_device(self) -> Device | None:
        if not (selected_items := self.table.selectedItems()):
            return None

        # get selected device.
        # This will have been one of the devices in model.available_devices
        row = selected_items[0].row()
        device = self.table.item(row, 1).data(Qt.ItemDataRole.UserRole)
        return cast("Device", device)

    def _remove_selected_devices(self) -> None:
        if not (selected_items := self.table.selectedItems()):
            return None

        to_remove: set[Device] = set()
        for item in selected_items:
            data = self.table.item(item.row(), 1).data(Qt.ItemDataRole.UserRole)
            device = cast("Device", data)
            if device.device_type == DeviceType.Hub:
                for dev in list(self._model.devices):
                    if dev.parent_label == device.name:
                        to_remove.add(dev)
            to_remove.add(device)

        for dev in to_remove:
            self._model.devices.remove(dev)
            with suppress(RuntimeError):
                self._core.unloadDevice(dev.name)

        self.rebuild_table()

    def _edit_selected_device(self) -> None:
        if not (selected_items := self.table.selectedItems()):
            return None

        # get selected device.
        # This will have been one of the devices in model.available_devices
        row = selected_items[0].row()
        data = self.table.item(row, 1).data(Qt.ItemDataRole.UserRole)
        device = cast("Device", data)

        coms = [
            (a.library, a.adapter_name) for a in self._model.available_serial_devices
        ]
        with exceptions_as_dialog(use_error_message=True) as ctx:
            # open device setup dialog
            dlg = DeviceSetupDialog.for_loaded_device(
                self._core,
                device_label=device.name,
                available_com_ports=coms,
                parent=self,
            )
        if ctx.exception or not dlg.exec():
            return

        dev = Device.create_from_core(
            self._core, name=dlg.deviceLabel(), initialized=True
        )
        idx = self._model.devices.index(device)
        self._model.devices[idx] = dev
        self.rebuild_table()


class _AvailableDevicesWidget(QWidget):
    """Table of all available devices."""

    touchedModel = Signal()

    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__()
        self._model = model
        self._core = core

        self.filter: QLineEdit = QLineEdit(self)
        self.filter.setPlaceholderText("Filter by text in any column")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._updateVisibleItems)

        self.dev_type = QComboBox()
        avail = {x.device_type for x in self._model.available_devices}
        for x in (DeviceType.Any, *sorted(avail)):
            self.dev_type.addItem(icon(ICONS.get(x, "")), str(x), x)
        self.dev_type.currentIndexChanged.connect(self._updateVisibleItems)

        headers = ["Module", "Adapter", "Type", "Description"]
        self.table = QTableWidget(0, len(headers), self)
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self._add_selected_device)

        hh = self.table.horizontalHeader()
        hh.setSortIndicatorShown(True)
        hh.setSectionResizeMode(hh.ResizeMode.Stretch)
        hh.sectionClicked.connect(self._sort_by_col)
        self.table.verticalHeader().setVisible(False)

        # Initialize sorting order as ascending for the first column
        self._sorted_col = 0
        self._sort_order = Qt.SortOrder.AscendingOrder

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Search:"))
        filter_row.addWidget(self.filter)
        filter_row.addWidget(QLabel("DeviceType:"))
        filter_row.addWidget(self.dev_type)

        bot_row = QHBoxLayout()
        bot_row.addStretch()
        # bot_row.addWidget(QLabel("double-click or ->"))
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_selected_device)
        bot_row.addWidget(add_btn)
        add_btn.setEnabled(False)
        self.table.itemSelectionChanged.connect(
            lambda: add_btn.setEnabled(len(self.table.selectedItems()) > 0)
        )

        title = QLabel("Available Devices:")
        font = title.font()
        font.setBold(True)
        title.setFont(font)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(title)
        layout.addLayout(filter_row)
        layout.addWidget(self.table)
        layout.addLayout(bot_row)

    def _sort_by_col(self, col: int) -> None:
        # Toggle sorting order if clicking on the same column
        if col == self._sorted_col:
            self._sort_order = (
                Qt.SortOrder.DescendingOrder
                if self._sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            self._sorted_col = col
            self._sort_order = Qt.SortOrder.AscendingOrder

        # Sort the table
        tbl = self.table
        tbl.sortItems(self._sorted_col, self._sort_order)
        tbl.horizontalHeader().setSortIndicator(self._sorted_col, self._sort_order)

    def _updateVisibleItems(self) -> None:
        """Recursively update the visibility of items based on the given pattern."""
        pattern = self.filter.text()
        dev_type = cast("DeviceType", self.dev_type.currentData())

        opt = QRegularExpression.PatternOption.CaseInsensitiveOption
        expressions = {QRegularExpression(p, opt) for p in pattern.split()}
        cols = self.table.columnCount()
        for row in range(self.table.rowCount()):
            if dev_type not in (DeviceType.Any, DeviceType.Unknown):
                dev = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                if cast("Device", dev).device_type != dev_type:
                    self.table.hideRow(row)
                    continue

            for col in range(cols):
                text = self.table.item(row, col).text()
                if all(ex.match(text).hasMatch() for ex in expressions):
                    self.table.showRow(row)
                    break
            else:
                self.table.hideRow(row)

    def rebuild_table(self) -> None:
        self.table.setRowCount(len(self._model.available_devices))
        for i, device in enumerate(self._model.available_devices):
            item0 = QTableWidgetItem(device.library)
            item0.setData(Qt.ItemDataRole.UserRole, device)
            self.table.setItem(i, 0, item0)
            self.table.setItem(i, 1, QTableWidgetItem(device.adapter_name))
            item = QTableWidgetItem(str(device.device_type))
            icon_string = ICONS.get(device.device_type, None)
            if icon_string:
                item.setIcon(icon(icon_string, color="Gray"))

            self.table.setItem(i, 2, item)
            self.table.setItem(i, 3, QTableWidgetItem(device.description))

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self._add_selected_device()
        else:
            print("keyPressEvent", event.key())
            super().keyPressEvent(event)

    def _add_selected_device(self) -> None:
        if not (selected_items := self.table.selectedItems()):
            return

        # get selected device.
        # This will have been one of the devices in model.available_devices
        item = self.table.item(selected_items[0].row(), 0)
        if not item:
            return
        device = cast("Device", item.data(Qt.ItemDataRole.UserRole))

        coms = [
            (a.library, a.adapter_name) for a in self._model.available_serial_devices
        ]
        with exceptions_as_dialog(use_error_message=True) as ctx:
            # open device setup dialog
            dlg = DeviceSetupDialog.for_new_device(
                self._core,
                library_name=device.library,
                device_name=device.adapter_name,
                available_com_ports=coms,
                parent=self,
            )
        if ctx.exception or not dlg.exec():
            return

        dev = Device.create_from_core(
            self._core, name=dlg.deviceLabel(), initialized=True
        )

        self._model.devices.append(dev)
        self.touchedModel.emit()

        if (
            dev.device_type == DeviceType.Hub
            and PeripheralSetupDlg(dev, self._model, self._core, self).exec()
        ):
            self.touchedModel.emit()


class DevicesPage(ConfigWizardPage):
    """Page for adding and removing devices."""

    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__(model, core)
        self.setTitle("Add or remove devices")
        self.setSubTitle(
            'Select devices from the "Available Devices" list to include in '
            "this configuration."
        )

        self.current = _CurrentDevicesWidget(model, core)
        self.available = _AvailableDevicesWidget(model, core)
        self.available.touchedModel.connect(self.current.rebuild_table)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.current)
        splitter.addWidget(self.available)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    def initializePage(self) -> None:
        """Called to prepare the page just before it is shown."""
        err = {}
        self._model.initialize(self._core, on_fail=lambda d, e: err.update({d.name: e}))
        self.current.rebuild_table(err)
        self.available.rebuild_table()
        return
