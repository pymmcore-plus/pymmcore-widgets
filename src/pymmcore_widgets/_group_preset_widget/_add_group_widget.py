import warnings
from typing import Optional, cast

from pymmcore_plus import CMMCorePlus
from qtpy.QtGui import QCloseEvent, QColor
from qtpy.QtWidgets import (
    QAbstractScrollArea,
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets._core import iter_dev_props
from pymmcore_widgets._device_type_filter import DeviceTypeFilters
from pymmcore_widgets._property_widget import PropertyWidget

from ._add_first_preset_widget import AddFirstPresetWidget


class _PropertyTable(QTableWidget):
    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(0, 3, parent=parent)
        self._mmc = CMMCorePlus.instance()
        self._mmc.events.systemConfigurationLoaded.connect(self._rebuild_table)
        self.destroyed.connect(self._disconnect)

        self.setHorizontalHeaderLabels([" ", "Property", "Value"])
        self.setColumnWidth(0, 250)
        self.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        vh = self.verticalHeader()
        vh.setSectionResizeMode(vh.ResizeMode.Fixed)
        vh.setDefaultSectionSize(24)
        vh.setVisible(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionMode(self.SelectionMode.NoSelection)
        self._rebuild_table()

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._rebuild_table)

    def _rebuild_table(self) -> None:
        self.clearContents()
        props = list(iter_dev_props(self._mmc))
        self.setRowCount(len(props))
        for i, (dev, prop) in enumerate(props):
            _checkbox = QCheckBox()
            _checkbox.setProperty("row", i)
            self.setCellWidget(i, 0, _checkbox)
            item = QTableWidgetItem(f"{dev}-{prop}")
            wdg = PropertyWidget(dev, prop, mmcore=self._mmc)
            wdg.setEnabled(False)
            self.setItem(i, 1, item)
            self.setCellWidget(i, 2, wdg)
            if wdg.isReadOnly():
                # TODO: make this more theme aware
                item.setBackground(QColor("#AAA"))
                wdg.setStyleSheet("QLabel { background-color : #AAA }")

        self.resizeColumnsToContents()

        # TODO: install eventFilter to prevent mouse wheel from scrolling sliders


class AddGroupWidget(QDialog):
    """Widget to create a new group."""

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)
        self._mmc = CMMCorePlus.instance()
        self._mmc.events.systemConfigurationLoaded.connect(self._update_filter)

        self._create_gui()

        self.destroyed.connect(self._disconnect)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Close also 'AddFirstPresetWidget' if is open."""
        if hasattr(self, "_first_preset_wdg"):
            self._first_preset_wdg.close()  # type: ignore
        event.accept()

    def _create_gui(self) -> None:

        self.setWindowTitle("Create a new Group")

        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(main_layout)

        group_lineedit = self._create_group_lineedit_wdg()
        main_layout.addWidget(group_lineedit)

        table = self._create_table_wdg()
        main_layout.addWidget(table)

        btn = self._create_button_wdg()
        main_layout.addWidget(btn)

    def _create_group_lineedit_wdg(self) -> QGroupBox:

        wdg = QGroupBox()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        wdg.setLayout(layout)

        group_lbl = QLabel(text="Group name:")
        group_lbl.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        )

        self.group_lineedit = QLineEdit()

        layout.addWidget(group_lbl)
        layout.addWidget(self.group_lineedit)

        return wdg

    def _create_table_wdg(self) -> QGroupBox:

        wdg = QGroupBox()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)
        wdg.setLayout(layout)

        self._prop_table = _PropertyTable()
        self._device_filters = DeviceTypeFilters()
        self._device_filters._set_show_read_only(False)
        self._device_filters.filtersChanged.connect(self._update_filter)

        self._filter_text = QLineEdit()
        self._filter_text.setClearButtonEnabled(True)
        self._filter_text.setPlaceholderText("Filter by device or property name...")
        self._filter_text.textChanged.connect(self._update_filter)

        right = QWidget()
        right.setLayout(QVBoxLayout())
        right.layout().addWidget(self._filter_text)
        right.layout().addWidget(self._prop_table)

        left = QWidget()
        left.setLayout(QVBoxLayout())
        left.layout().addWidget(self._device_filters)

        self.layout().addWidget(left)
        self.layout().addWidget(right)
        layout.addWidget(left)
        layout.addWidget(right)

        return wdg

    def _create_button_wdg(self) -> QWidget:

        wdg = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        wdg.setLayout(layout)

        self.info_lbl = QLabel()

        self.new_group_btn = QPushButton(text="Create New Group")
        self.new_group_btn.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        )
        self.new_group_btn.clicked.connect(self._add_group)

        layout.addWidget(self.info_lbl)
        layout.addWidget(self.new_group_btn)

        return wdg

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._update_filter)

    def _update_filter(self) -> None:
        filt = self._filter_text.text().lower()
        for r in range(self._prop_table.rowCount()):
            wdg = cast(PropertyWidget, self._prop_table.cellWidget(r, 2))
            if wdg.isReadOnly() and not self._device_filters.showReadOnly():
                self._prop_table.hideRow(r)
            elif wdg.deviceType() in self._device_filters.filters():
                self._prop_table.hideRow(r)
            elif filt and filt not in self._prop_table.item(r, 1).text().lower():
                self._prop_table.hideRow(r)
            else:
                self._prop_table.showRow(r)

    def _add_group(self) -> None:

        cbox = [
            self._prop_table.cellWidget(r, 0)
            for r in range(self._prop_table.rowCount())
            if self._prop_table.cellWidget(r, 0).isChecked()
        ]

        if not cbox:
            warnings.warn("Select at lest one property!")
            self.info_lbl.setStyleSheet("color: magenta;")
            self.info_lbl.setText("Select at lest one property!")
            return

        group = self.group_lineedit.text()

        if not group:
            warnings.warn("Give a name to the group!")
            self.info_lbl.setStyleSheet("color: magenta;")
            self.info_lbl.setText("Give a name to the group!")
            return

        if group in self._mmc.getAvailableConfigGroups():
            warnings.warn(f"There is already a preset called '{group}'.")
            self.info_lbl.setStyleSheet("color: magenta;")
            self.info_lbl.setText(f"'{group}' already exist!")
            return

        dev_prop_val_list = []
        for r in range(self._prop_table.rowCount()):
            checkbox = cast(QCheckBox, self._prop_table.cellWidget(r, 0))
            if checkbox.isChecked():
                row = checkbox.property("row")
                dev_prop = self._prop_table.item(row, 1).text()
                dev = dev_prop.split("-")[0]
                prop = dev_prop.split("-")[1]
                value = self._prop_table.cellWidget(row, 2).value()

                dev_prop_val_list.append((dev, prop, str(value)))

        if hasattr(self, "_first_preset_wdg"):
            self._first_preset_wdg.close()  # type: ignore
        self._first_preset_wdg = AddFirstPresetWidget(
            group, dev_prop_val_list, parent=self
        )
        self._first_preset_wdg.show()

        self.info_lbl.setStyleSheet("")
        self.info_lbl.setText("")
