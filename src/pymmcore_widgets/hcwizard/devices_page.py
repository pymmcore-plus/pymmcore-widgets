import logging
from typing import cast

from pymmcore_plus import CMMCorePlus, DeviceType
from pymmcore_plus.model import Device, Microscope
from qtpy.QtCore import QRegularExpression, Qt
from qtpy.QtWidgets import (
    QErrorMessage,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt import QEnumComboBox
from superqt.fonticon import icon

from pymmcore_widgets._device_property_table import ICONS

from ._base_page import _ConfigWizardPage
from ._dev_setup_dialog import _DeviceSetupDialog
from ._peripheral_setup_dialog import PeripheralSetupDlg

logger = logging.getLogger(__name__)


class _DeviceTable(QTableWidget):
    """Table of currently configured devices."""

    def __init__(self, model: Microscope):
        super().__init__()
        self._model = model
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        h = self.horizontalHeader()
        h.setSectionResizeMode(h.ResizeMode.Stretch)

        headers = ["Name", "Adapter/Module", "Description", "Status"]
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)


class _CurrentDevicesTable(QWidget):
    ...


class _AvailableDeviceTable(QWidget):
    """Table of all available devices."""

    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__()
        self._model = model
        self._core = core

        self.filter: QLineEdit = QLineEdit(self)
        self.filter.setPlaceholderText("Filter by text in any column")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._updateVisibleItems)

        self.dev_type: QEnumComboBox = QEnumComboBox(self, DeviceType)
        self.dev_type.removeItem(0)  # Remove "Unknown" option
        self.dev_type.currentIndexChanged.connect(self._updateVisibleItems)

        self.table = QTableWidget(self)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self._add_selected_device)
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setSortIndicatorShown(True)
        hh.setSectionResizeMode(hh.ResizeMode.Stretch)
        hh.sectionClicked.connect(self._sort_by_col)

        headers = ["Module", "Adapter", "Type", "Description"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.rebuild_table()

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addLayout(filter_row)
        layout.addWidget(self.table)
        layout.addLayout(bot_row)

    def _sort_by_col(self, col: int):
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
        dev_type = DeviceType[self.dev_type.currentText()]

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

    def rebuild_table(self):
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

    def keyPressEvent(self, event):
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self._add_selected_device()
        else:
            super().keyPressEvent(event)

    def _add_selected_device(self):
        if not (selected_items := self.table.selectedItems()):
            return

        # get selected device.
        # This will have been one of the devices in model.available_devices
        row = selected_items[0].row()
        device = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        device = cast("Device", device)

        # generate a unique name for the device
        new_name = device.adapter_name
        count = 0
        while any(d.name == new_name for d in self._model.devices):
            new_name = f"{device.adapter_name}-{count}"
            count += 1

        try:
            # try to load the device
            self._core.loadDevice(new_name, device.library, device.adapter_name)
            # get the device with info loaded from core
            dev = Device(new_name, from_core=self._core)
        except Exception as e:
            logger.exception(e)
            em = QErrorMessage()
            em.showMessage(str(e))
            return

        # TODO: feels like this should be a context manager
        self._model.devices.append(dev)
        # show the setup dialog
        dlg = _DeviceSetupDialog(dev, self._model, self._core, parent=self)
        dlg.setWindowFlags(Qt.WindowType.Sheet)
        if not dlg.exec():
            return

        if not dev.initialized:
            # user cancelled or things didn't work out
            self._model.devices.remove(dev)
            try:
                self._core.unloadDevice(new_name)
            except Exception as e:
                logger.exception(e)
                return

        # device is initialized and in the model
        assert dev.initialized and dev in self._model.devices
        # TODO refresh the devices table

        if dev.device_type == DeviceType.Hub:
            peripherals: list[Device] = []
            for child in dev.children:
                if self._model.has_adapter_name(dev.library, dev.name, child):
                    description = next(
                        (
                            d.description
                            for d in self._model.available_devices
                            if d.library == dev.library and d.adapter_name == child
                        ),
                        "",
                    )
                    new_dev = Device(
                        name=child,
                        library=dev.library,
                        adapter_name=child,
                        description=description,
                    )
                    peripherals.append(new_dev)

            if peripherals:
                dlg = PeripheralSetupDlg(dev, self._model, self._core)
                if not dlg.exec():
                    return


class DevicesPage(_ConfigWizardPage):
    """Page for adding and removing devices."""

    def __init__(self, model: Microscope, core: CMMCorePlus):
        super().__init__(model, core)
        self.setTitle("Add or remove devices")
        self.setSubTitle(
            'Select devices from the "Available Devices" list to include in '
            "this configuration."
        )

        self.table = _DeviceTable(model)
        self.available = _AvailableDeviceTable(model, core)

        splitter = QSplitter(Qt.Orientation.Vertical)
        top = QWidget()
        layout = QVBoxLayout(top)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Installed Devices:"))
        layout.addWidget(self.table)

        splitter.addWidget(top)
        splitter.addWidget(self.available)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)
