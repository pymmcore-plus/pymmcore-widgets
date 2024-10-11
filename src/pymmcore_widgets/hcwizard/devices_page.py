from __future__ import annotations

import logging
from contextlib import suppress
from typing import TYPE_CHECKING, cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, DeviceType
from pymmcore_plus.model import AvailableDevice, Device, Microscope
from qtpy.QtCore import QRegularExpression, Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon, setTextIcon
from superqt.utils import exceptions_as_dialog, signals_blocked

from pymmcore_widgets._icons import ICONS

from ._base_page import ConfigWizardPage
from ._dev_setup_dialog import DeviceSetupDialog
from ._peripheral_setup_dialog import PeripheralSetupDlg

if TYPE_CHECKING:
    from qtpy.QtGui import QKeyEvent

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
                wdg = QPushButton(icon(type_icon, color="blue"), "")
                wdg.setToolTip("Add peripheral device")
                wdg.setCursor(Qt.CursorShape.PointingHandCursor)
                wdg.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                wdg.clicked.connect(
                    lambda *_, d=device, m=model: self._edit_peripherals(d, m)
                )
                wdg.setMaximumWidth(28)

            else:
                wdg = QLabel()
                setTextIcon(wdg, type_icon, size=14)
                wdg.setStyleSheet("QLabel { color: gray; }")

            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(wdg, 0, Qt.AlignmentFlag.AlignCenter)
            self.setCellWidget(i, 0, container)

            item = QTableWidgetItem(device.name)
            item.setData(Qt.ItemDataRole.UserRole, device)
            self.setItem(i, 1, item)
            self.setItem(i, 2, QTableWidgetItem(device.adapter_name))
            self.setItem(i, 3, QTableWidgetItem(device.description))

            if device.device_type == DeviceType.Core:  # pragma: no cover
                # shouldn't be possible to have a core device in this list
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
            super().keyPressEvent(event)  # pragma: no cover

    def _on_selection_changed(self) -> None:
        selected_rows = {x.row() for x in self.table.selectedItems()}
        n_selected = len(selected_rows)
        self.edit_btn.setEnabled(n_selected == 1)
        self.remove_btn.setEnabled(n_selected > 0)

    def _remove_selected_devices(self) -> None:
        if not (selected_items := self.table.selectedItems()):
            return None  # pragma: no cover

        to_remove: set[Device] = set()
        asked = False
        for item in selected_items:
            data = self.table.item(item.row(), 1).data(Qt.ItemDataRole.UserRole)
            device = cast("Device", data)
            if device.device_type == DeviceType.Hub:
                children: set[Device] = set()
                for dev in list(self._model.devices):
                    if dev.parent_label == device.name:
                        children.add(dev)
                if children and not asked:
                    child = f'{"child" if len(children) == 1 else "children"}'
                    response = QMessageBox.question(
                        self,
                        "Remove Children?",
                        f"Remove {len(children)} {child} of device {device.name!r}?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes,
                    )
                    if response == QMessageBox.StandardButton.Yes:
                        to_remove.update(children)
                    asked = True

            to_remove.add(device)

        for dev in to_remove:
            self._model.devices.remove(dev)
            with suppress(RuntimeError):
                self._core.unloadDevice(dev.name)

        self.rebuild_table()

    def _edit_selected_device(self) -> None:
        if not (selected_items := self.table.selectedItems()):
            return None  # pragma: no cover

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
            return  # pragma: no cover

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

        title = QLabel("Available Devices:")
        font = title.font()
        font.setBold(True)
        title.setFont(font)

        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_selected_device)
        add_btn.setEnabled(False)
        self.table.itemSelectionChanged.connect(
            lambda: add_btn.setEnabled(len(self.table.selectedItems()) > 0)
        )
        self._show_children = QCheckBox("Show Hub Children")
        self._show_children.stateChanged.connect(self._updateVisibleItems)

        bot_row = QHBoxLayout()
        bot_row.addWidget(self._show_children)
        bot_row.addStretch()
        bot_row.addWidget(add_btn)

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
        show_children = self._show_children.isChecked()

        opt = QRegularExpression.PatternOption.CaseInsensitiveOption
        expressions = tuple(QRegularExpression(p, opt) for p in pattern.split())
        cols = self.table.columnCount()
        for row in range(self.table.rowCount()):
            dev = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            dev = cast("AvailableDevice", dev)
            if (
                dev_type not in (DeviceType.Any, DeviceType.Unknown)
                and dev.device_type != dev_type
            ) or (dev.library_hub and not show_children):
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
            # -----------
            item0 = QTableWidgetItem(device.library)
            item0.setData(Qt.ItemDataRole.UserRole, device)
            self.table.setItem(i, 0, item0)
            # -----------
            item = QTableWidgetItem(device.adapter_name)
            if device.library_hub:
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setText(f"[{device.library_hub.adapter_name}] {item.text()}")
            self.table.setItem(i, 1, item)
            # -----------
            item = QTableWidgetItem(str(device.device_type))
            icon_string = ICONS.get(device.device_type, None)
            if icon_string:
                item.setIcon(icon(icon_string, color="Gray"))
            if device.library_hub:
                item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.table.setItem(i, 2, item)
            # -----------
            self.table.setItem(i, 3, QTableWidgetItem(device.description))

        current = self.dev_type.currentData()
        with signals_blocked(self.dev_type):
            self.dev_type.clear()
            _avail = {x.device_type for x in self._model.available_devices}
            avail = sorted(x for x in _avail if x != DeviceType.Any)
            for x in (DeviceType.Any, *avail):
                self.dev_type.addItem(icon(ICONS.get(x, "")), str(x), x)
            if current in avail:
                self.dev_type.setCurrentText(str(current))

        self._updateVisibleItems()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self._add_selected_device()
        else:
            super().keyPressEvent(event)  # pragma: no cover

    def _add_selected_device(self) -> None:
        if not (selected_items := self.table.selectedItems()):
            return  # pragma: no cover

        # get selected device.
        # This will have been one of the devices in model.available_devices
        item = self.table.item(selected_items[0].row(), 0)
        if not item:
            return  # pragma: no cover
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
            return  # pragma: no cover

        # getting here means that a new device was successfully loaded AND initialized
        dev = Device.create_from_core(
            self._core, name=dlg.deviceLabel(), initialized=True
        )

        self._model.devices.append(dev)
        if dev.port:
            for port_dev in self._model.available_serial_devices:
                if dev.port == port_dev.name:
                    port_dev.update_from_core(self._core)

        self.touchedModel.emit()

        if dev.device_type == DeviceType.Hub:
            # if a new hub was added to the loaded Devices, we need to reload
            # the available devices list to include any new child peripherals
            # (load_available_devices will call core.getInstalledDevices() on all hubs)
            # NOTE: this is less efficient than it could be, since this triggers a
            # complete reload of the available devices list, rather than simply adding
            # new available devices that are children of the Hub...
            # but that could come in a later PR if it becomes performance limiting.
            self._model.load_available_devices(self._core)
            dlg2 = PeripheralSetupDlg(dev, self._model, self._core, self)
            if dlg2.exec():
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
        # TODO: there are errors that occur outside of this call that could also be
        # shown in the tooltip above...
        self._model.initialize(
            self._core, on_fail=lambda d, e: err.update({d.name: str(e)})
        )
        self._model.mark_clean()
        self.current.rebuild_table(err)
        self.available.rebuild_table()
        return
