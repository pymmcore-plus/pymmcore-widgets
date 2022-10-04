from functools import partial
from typing import Dict, List, Optional, Set, Tuple, cast

from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
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

from pymmcore_widgets._core import iter_dev_props
from pymmcore_widgets._property_widget import PropertyWidget

from .._util import block_core


class _PropertyTable(QTableWidget):
    def __init__(
        self, group: str = None, *, parent: Optional[QWidget] = None  # type: ignore
    ) -> None:
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

        self._rebuild_table(group)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._rebuild_table)

    def _get_group_dev_prop(self, group: str) -> List[Tuple[str, str]]:
        presets = self._mmc.getAvailableConfigs(group)
        return [(k[0], k[1]) for k in self._mmc.getConfigData(group, presets[0])]

    def _rebuild_table(self, group: str = None) -> None:  # type: ignore

        self.clearContents()

        if group:
            dev_prop = self._get_group_dev_prop(group)

        props = list(iter_dev_props(self._mmc))
        self.setRowCount(len(props))
        for i, (dev, prop) in enumerate(props):
            item = QTableWidgetItem(f"{dev}-{prop}")
            _checkbox = QCheckBox()
            _checkbox.setProperty("row", i)
            if group and (dev, prop) in dev_prop:
                _checkbox.setChecked(True)
            self.setCellWidget(i, 0, _checkbox)
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


class EditGroupWidget(QDialog):
    """Widget to edit the specified Group."""

    def __init__(self, group: str, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._mmc = CMMCorePlus.instance()

        self._group = group

        if self._group not in self._mmc.getAvailableConfigGroups():
            return

        self._mmc.events.systemConfigurationLoaded.connect(self._update_filter)

        self._create_gui()

        self.group_lineedit.setText(self._group)
        self.group_lineedit.setEnabled(False)

        self.destroyed.connect(self._disconnect)

    def _create_gui(self) -> None:

        self.setWindowTitle(f"Edit the '{self._group}' Group.")

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

        self._prop_table = _PropertyTable(self._group)
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

        self.new_group_btn = QPushButton(text="Modify Group")
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

        new_dev_prop: List[Tuple[str, str]] = []
        for row in range(self._prop_table.rowCount()):
            _checkbox = cast(QCheckBox, self._prop_table.cellWidget(row, 0))

            if not _checkbox.isChecked():
                continue

            device_property = self._prop_table.item(row, 1).text()
            dev = device_property.split("-")[0]
            prop = device_property.split("-")[1]
            new_dev_prop.append((dev, prop))

        presets = self._mmc.getAvailableConfigs(self._group)
        preset_dev_prop = [
            (k[0], k[1]) for k in self._mmc.getConfigData(self._group, presets[0])
        ]

        if preset_dev_prop == new_dev_prop:
            return

        # get any new dev prop to add to each preset
        _to_add: List[Tuple[str, str, str]] = []
        for d, p in new_dev_prop:
            if (d, p) not in preset_dev_prop:
                value = self._mmc.getProperty(d, p)
                _to_add.append((d, p, value))

        # get the dev prop val to keep per preset
        _prop_to_keep: List[List[Tuple[str, str, str]]] = []
        for preset in presets:
            preset_dev_prop_val = [
                (k[0], k[1], k[2]) for k in self._mmc.getConfigData(self._group, preset)
            ]
            _to_keep = [
                (d, p, v) for d, p, v in preset_dev_prop_val if (d, p) in new_dev_prop
            ]
            _prop_to_keep.append(_to_keep)

        self._mmc.deleteConfigGroup(self._group)

        for idx, preset in enumerate(presets):

            preset_dpv = _prop_to_keep[idx]
            if _to_add:
                preset_dpv.extend(_to_add)

            with block_core(self._mmc.events):
                for d, p, v in preset_dpv:
                    self._mmc.defineConfig(self._group, preset, d, p, v)

            self._mmc.events.configDefined.emit(self._group, preset, d, p, v)

        self.info_lbl.setText(f"'{self._group}' Group Modified.")
