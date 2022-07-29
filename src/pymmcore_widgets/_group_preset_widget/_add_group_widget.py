import warnings
from functools import partial
from typing import Dict, Optional, Set, Tuple, cast

from pymmcore_plus import DeviceType
from qtpy.QtCore import Qt
from qtpy.QtGui import QCloseEvent, QColor
from qtpy.QtWidgets import (
    QAbstractScrollArea,
    QCheckBox,
    QDialog,
    QGridLayout,
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

from pymmcore_widgets._core import get_core_singleton, iter_dev_props
from pymmcore_widgets._property_widget import PropertyWidget

from ._add_first_preset_widget import AddFirstPresetWidget


class _PropertyTable(QTableWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(0, 3, parent=parent)
        self._mmc = get_core_singleton()
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
            wdg = PropertyWidget(dev, prop, core=self._mmc)
            wdg.setEnabled(False)
            self.setItem(i, 1, item)
            self.setCellWidget(i, 2, wdg)
            if wdg.isReadOnly():
                # TODO: make this more theme aware
                item.setBackground(QColor("#AAA"))
                wdg.setStyleSheet("QLabel { background-color : #AAA }")

        self.resizeColumnsToContents()

        # TODO: install eventFilter to prevent mouse wheel from scrolling sliders


DevTypeLabels: Dict[str, Tuple[DeviceType, ...]] = {
    "cameras": (DeviceType.CameraDevice,),
    "shutters": (DeviceType.ShutterDevice,),
    "stages": (DeviceType.StageDevice,),
    "wheels, turrets, etc.": (DeviceType.StateDevice,),
}
_d: Set[DeviceType] = set.union(*(set(i) for i in DevTypeLabels.values()))
DevTypeLabels["other devices"] = tuple(set(DeviceType) - _d)


class AddGroupWidget(QDialog):
    """Widget to create a new group."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._mmc = get_core_singleton()
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

        self._set_show_read_only(False)

    def _create_group_lineedit_wdg(self) -> QGroupBox:

        wdg = QGroupBox()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        wdg.setLayout(layout)

        group_lbl = QLabel(text="Group name:")
        group_lbl.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))

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
        self._show_read_only: bool = False

        self._filters: Set[DeviceType] = set()
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
        left.layout().addWidget(self._make_checkboxes())

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
            QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
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
            if wdg.isReadOnly() and not self._show_read_only:  # sourcery skip
                self._prop_table.hideRow(r)
            elif wdg.deviceType() in self._filters:
                self._prop_table.hideRow(r)
            elif filt and filt not in self._prop_table.item(r, 1).text().lower():
                self._prop_table.hideRow(r)
            else:
                self._prop_table.showRow(r)

    def _toggle_filter(self, label: str) -> None:
        self._filters.symmetric_difference_update(DevTypeLabels[label])
        self._update_filter()

    def _make_checkboxes(self) -> QWidget:
        dev_gb = QGroupBox("Device Type")
        dev_gb.setLayout(QGridLayout())
        dev_gb.layout().setSpacing(6)
        all_btn = QPushButton("All")
        dev_gb.layout().addWidget(all_btn, 0, 0, 1, 1)
        none_btn = QPushButton("None")
        dev_gb.layout().addWidget(none_btn, 0, 1, 1, 1)
        for i, (label, devtypes) in enumerate(DevTypeLabels.items()):
            cb = QCheckBox(label)
            cb.setChecked(devtypes[0] not in self._filters)
            cb.toggled.connect(partial(self._toggle_filter, label))
            dev_gb.layout().addWidget(cb, i + 1, 0, 1, 2)

        @all_btn.clicked.connect  # type: ignore
        def _check_all() -> None:
            for cxbx in dev_gb.findChildren(QCheckBox):
                cxbx.setChecked(True)

        @none_btn.clicked.connect  # type: ignore
        def _check_none() -> None:
            for cxbx in dev_gb.findChildren(QCheckBox):
                cxbx.setChecked(False)

        for i in dev_gb.findChildren(QWidget):
            i.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # type: ignore

        ro = QCheckBox("Show read-only")
        ro.setChecked(self._show_read_only)
        ro.toggled.connect(self._set_show_read_only)
        ro.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        c = QWidget()
        c.setLayout(QVBoxLayout())
        c.layout().addWidget(dev_gb)
        c.layout().addWidget(ro)
        c.layout().addStretch()
        return c

    def _set_show_read_only(self, state: bool) -> None:
        self._show_read_only = state
        self._update_filter()

    def _add_group(self) -> None:

        group = self.group_lineedit.text()

        if not group:
            warnings.warn("Give a name to the group!")
            self.info_lbl.setStyleSheet("color: magenta;")
            self.info_lbl.setText("Give a name to the group!")
            return

        if group in self._mmc.getAvailableConfigGroups():
            warnings.warn(f"There is already a preset called {group}.")
            self.info_lbl.setStyleSheet("color: magenta;")
            self.info_lbl.setText(f"{group} already exist!")
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
            group, "NewPreset", dev_prop_val_list, parent=self
        )
        self._first_preset_wdg.show()

        self.info_lbl.setStyleSheet("")
        self.info_lbl.setText("")
