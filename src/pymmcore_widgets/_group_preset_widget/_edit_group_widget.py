from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets._device_property_table import DevicePropertyTable
from pymmcore_widgets._device_type_filter import DeviceTypeFilters

from .._util import block_core


class EditGroupWidget(QDialog):
    """Widget to edit the specified Group."""

    def __init__(self, group: str, *, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
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

        self._filter_text = QLineEdit()
        self._filter_text.setClearButtonEnabled(True)
        self._filter_text.setPlaceholderText("Filter by device or property name...")
        self._filter_text.textChanged.connect(self._update_filter)

        self._prop_table = DevicePropertyTable(enable_property_widgets=False)
        self._prop_table.setRowsCheckable(True)
        self._prop_table.checkGroup(self._group)
        self._device_filters = DeviceTypeFilters()
        self._device_filters.filtersChanged.connect(self._update_filter)
        self._device_filters.setShowReadOnly(False)
        self._device_filters._read_only_checkbox.hide()

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

        self.modify_group_btn = QPushButton(text="Modify Group")
        self.modify_group_btn.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        )
        self.modify_group_btn.clicked.connect(self._add_group)

        layout.addWidget(self.info_lbl)
        layout.addWidget(self.modify_group_btn)

        return wdg

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._update_filter)

    def _update_filter(self) -> None:
        filt = self._filter_text.text().lower()
        self._prop_table.filterDevices(
            filt, self._device_filters.filters(), self._device_filters.showReadOnly()
        )

    def _add_group(self) -> None:
        # [(device, property, value), ...], need to remove the value
        new_dev_prop = [x[:2] for x in self._prop_table.getCheckedProperties()]

        presets = self._mmc.getAvailableConfigs(self._group)
        preset_dev_prop = [
            (k[0], k[1]) for k in self._mmc.getConfigData(self._group, presets[0])
        ]

        if preset_dev_prop == new_dev_prop:
            return

        # get any new dev prop to add to each preset
        _to_add: list[tuple[str, str, str]] = []
        for d, p in new_dev_prop:
            if (d, p) not in preset_dev_prop:
                value = self._mmc.getProperty(d, p)
                _to_add.append((d, p, value))

        # get the dev prop val to keep per preset
        _prop_to_keep: list[list[tuple[str, str, str]]] = []
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
