from __future__ import annotations

import warnings

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets._util import block_core

from ._cfg_table import _CfgTable


class AddPresetWidget(QDialog):
    """A widget to add presets to a specified group."""

    def __init__(self, group: str, *, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        self._mmc = CMMCorePlus.instance()
        self._group = group

        self._create_gui()

        self._populate_table()

    def _create_gui(self) -> None:
        self.setWindowTitle(f"Add a new Preset to the '{self._group}' Group")

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

        self.table = _CfgTable()
        wdg_layout.addWidget(self.table)

        bottom_wdg = self._create_bottom_wdg()
        wdg_layout.addWidget(bottom_wdg)

        main_layout.addWidget(wdg)

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

        ps_lbl = QLabel(text="Preset:")
        ps_lbl.setSizePolicy(lbl_sizepolicy)
        self.preset_name_lineedit = QLineEdit()
        self.preset_name_lineedit.setPlaceholderText(self._get_placeholder_name())

        spacer = QSpacerItem(30, 10, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        wdg_layout.addWidget(gp_lbl)
        wdg_layout.addWidget(group_name_lbl)
        wdg_layout.addItem(spacer)
        wdg_layout.addWidget(ps_lbl)
        wdg_layout.addWidget(self.preset_name_lineedit)

        return wdg

    def _get_placeholder_name(self) -> str:
        idx = sum("NewPreset" in p for p in self._mmc.getAvailableConfigs(self._group))
        return f"NewPreset_{idx}" if idx > 0 else "NewPreset"

    def _create_bottom_wdg(self) -> QWidget:
        wdg = QWidget()
        wdg_layout = QHBoxLayout()
        wdg_layout.setSpacing(5)
        wdg_layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(wdg_layout)

        self.info_lbl = QLabel()
        self.add_preset_button = QPushButton(text="Add Preset")
        self.add_preset_button.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        )
        self.add_preset_button.clicked.connect(self._add_preset)

        wdg_layout.addWidget(self.info_lbl)
        wdg_layout.addWidget(self.add_preset_button)

        return wdg

    def _populate_table(self) -> None:
        dev_prop = []
        for preset in self._mmc.getAvailableConfigs(self._group):
            dev_prop.extend(
                [
                    (k[0], k[1])
                    for k in self._mmc.getConfigData(self._group, preset)
                    if (k[0], k[1]) not in dev_prop
                ]
            )
        self.table.populate_table(dev_prop)

    def _add_preset(self) -> None:
        preset_name = self.preset_name_lineedit.text()

        if preset_name in self._mmc.getAvailableConfigs(self._group):
            warnings.warn(
                f"There is already a preset called '{preset_name}'.", stacklevel=2
            )
            self.info_lbl.setStyleSheet("color: magenta;")
            self.info_lbl.setText(f"'{preset_name}' already exist!")
            return

        if not preset_name:
            preset_name = self.preset_name_lineedit.placeholderText()

        dev_prop_val = self.table.get_state()
        for p in self._mmc.getAvailableConfigs(self._group):
            dpv_preset = [
                (k[0], k[1], k[2]) for k in self._mmc.getConfigData(self._group, p)
            ]
            if dpv_preset == dev_prop_val:
                warnings.warn(
                    "There is already a preset with the same "
                    f"devices, properties and values: '{p}'.",
                    stacklevel=2,
                )
                self.info_lbl.setStyleSheet("color: magenta;")
                self.info_lbl.setText(f"'{p}' already has the same properties!")
                return

        with block_core(self._mmc.events):
            for dev, prop, val in dev_prop_val:
                self._mmc.defineConfig(self._group, preset_name, dev, prop, val)

        self._mmc.events.configDefined.emit(self._group, preset_name, dev, prop, val)

        self.info_lbl.setStyleSheet("")
        self.info_lbl.setText(f"'{preset_name}' has been added!")
        self.preset_name_lineedit.setPlaceholderText(self._get_placeholder_name())
