from __future__ import annotations

import warnings

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

from pymmcore_widgets._property_widget import PropertyWidget

from .._util import block_core


class EditPresetWidget(QDialog):
    """A widget to edit a specified group's presets."""

    def __init__(
        self, group: str, preset: str, *, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = CMMCorePlus.instance()
        self._group = group
        self._preset = preset

        self._create_gui()

        self._populate_table_and_combo()

    def _create_gui(self) -> None:  # sourcery skip: class-extract-method

        self.setWindowTitle(
            f"Edit the '{self._preset}' Preset from the '{self._group}' Group"
        )

        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(main_layout)

        wdg = QWidget()
        wdg_layout = QVBoxLayout()
        wdg_layout.setSpacing(10)
        wdg_layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(wdg_layout)

        top_wdg = self._create_top_wdg()
        wdg_layout.addWidget(top_wdg)

        self.table = _Table()
        wdg_layout.addWidget(self.table)

        bottom_wdg = self._create_bottom_wdg()
        wdg_layout.addWidget(bottom_wdg)

        main_layout.addWidget(wdg)

        self._resize()

    def _resize(self) -> None:
        self.resize(
            self.minimumSizeHint().width()
            + self._presets_combo.minimumSizeHint().width(),
            self.sizeHint().height(),
        )

    def _create_top_wdg(self) -> QGroupBox:
        wdg = QGroupBox()
        wdg_layout = QHBoxLayout()
        wdg_layout.setSpacing(5)
        wdg_layout.setContentsMargins(5, 5, 5, 5)
        wdg.setLayout(wdg_layout)

        lbl_sizepolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        gp_lbl = QLabel(text="Group:")
        gp_lbl.setSizePolicy(lbl_sizepolicy)
        group_name_lbl = QLabel(text=f"{self._group}")
        group_name_lbl.setSizePolicy(lbl_sizepolicy)

        self._presets_combo = QComboBox()
        self._presets_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._presets_combo.currentTextChanged.connect(self._on_combo_changed)

        ps_lbl = QLabel(text="Preset:")
        ps_lbl.setSizePolicy(lbl_sizepolicy)
        self.preset_name_lineedit = QLineEdit()
        self.preset_name_lineedit.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )
        self.preset_name_lineedit.setText(f"{self._preset}")

        spacer = QSpacerItem(30, 10, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        wdg_layout.addWidget(gp_lbl)
        wdg_layout.addWidget(group_name_lbl)
        wdg_layout.addItem(spacer)
        wdg_layout.addWidget(ps_lbl)
        wdg_layout.addWidget(self._presets_combo)
        wdg_layout.addWidget(self.preset_name_lineedit)

        return wdg

    def _create_bottom_wdg(self) -> QWidget:

        wdg = QWidget()
        wdg_layout = QHBoxLayout()
        wdg_layout.setSpacing(5)
        wdg_layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(wdg_layout)

        self.info_lbl = QLabel()
        self.apply_button = QPushButton(text="Apply Changes")
        self.apply_button.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        )
        self.apply_button.clicked.connect(self._apply_changes)

        wdg_layout.addWidget(self.info_lbl)
        wdg_layout.addWidget(self.apply_button)

        return wdg

    def _update_combo(self) -> None:

        presets = self._mmc.getAvailableConfigs(self._group)
        with signals_blocked(self._presets_combo):
            self._presets_combo.clear()
            self._presets_combo.addItems(presets)
            self._presets_combo.setCurrentText(self._preset)
            self.preset_name_lineedit.setText(f"{self._preset}")
            self._resize_combo_height(len(presets))
        self._resize()

    def _resize_combo_height(self, max_items: int) -> None:
        self._presets_combo.setEditable(True)
        self._presets_combo.setMaxVisibleItems(max_items)
        self._presets_combo.setEditable(False)

    def _populate_table_and_combo(self) -> None:

        self._update_combo()

        self.table.clearContents()

        dev_prop_val = [
            (k[0], k[1], k[2])
            for k in self._mmc.getConfigData(self._group, self._preset)
        ]
        self.table.setRowCount(len(dev_prop_val))
        for idx, (dev, prop, val) in enumerate(dev_prop_val):
            item = QTableWidgetItem(f"{dev}-{prop}")
            wdg = PropertyWidget(dev, prop, mmcore=self._mmc)
            wdg._value_widget.valueChanged.disconnect()  # type: ignore
            wdg.setValue(val)
            self.table.setItem(idx, 0, item)
            self.table.setCellWidget(idx, 1, wdg)

    def _on_combo_changed(self, preset: str) -> None:

        self._preset = preset
        self.info_lbl.setStyleSheet("")
        self.info_lbl.setText("")
        self._populate_table_and_combo()

    def _apply_changes(self) -> None:

        dev_prop_val = []
        for row in range(self.table.rowCount()):
            device_property = self.table.item(row, 0).text()
            dev = device_property.split("-")[0]
            prop = device_property.split("-")[1]
            value = str(self.table.cellWidget(row, 1).value())
            dev_prop_val.append((dev, prop, value))

        for p in self._mmc.getAvailableConfigs(self._group):
            dpv_preset = [
                (k[0], k[1], k[2]) for k in self._mmc.getConfigData(self._group, p)
            ]
            if (
                dpv_preset == dev_prop_val
                and self._preset == self.preset_name_lineedit.text()
            ):
                if p == self._preset:
                    return
                warnings.warn(
                    "Threre is already a preset with the same "
                    f"devices, properties and values: '{p}'."
                )
                self.info_lbl.setStyleSheet("color: magenta;")
                self.info_lbl.setText(f"'{p}' already has the same properties!")
                return

        self._mmc.deleteConfig(self._group, self._preset)

        self._preset = self.preset_name_lineedit.text()

        with block_core(self._mmc.events):
            for d, p, v in dev_prop_val:
                self._mmc.defineConfig(self._group, self._preset, d, p, v)

        self._mmc.events.configDefined.emit(self._group, self._preset, d, p, v)

        self._update_combo()

        self.info_lbl.setStyleSheet("")
        self.info_lbl.setText(f"'{self._preset}' has been modified!")


class _Table(QTableWidget):
    """Set table properties for EditPresetWidget."""

    def __init__(self) -> None:
        super().__init__()
        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(hdr.ResizeMode.Stretch)
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignHCenter)
        vh = self.verticalHeader()
        vh.setVisible(False)
        vh.setSectionResizeMode(vh.ResizeMode.Fixed)
        vh.setDefaultSectionSize(24)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Device-Property", "Value"])
