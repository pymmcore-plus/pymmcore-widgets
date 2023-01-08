from __future__ import annotations

from typing import Any

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets._presets_widget import PresetsWidget
from pymmcore_widgets._property_widget import PropertyWidget

from .._core import load_system_config
from .._util import block_core
from ._add_group_widget import AddGroupWidget
from ._add_preset_widget import AddPresetWidget
from ._edit_group_widget import EditGroupWidget
from ._edit_preset_widget import EditPresetWidget

UNNAMED_PRESET = "NewPreset"


class _MainTable(QTableWidget):
    """Set table properties for Group and Preset TableWidget."""

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
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Group", "Preset"])
        self.setMinimumHeight(200)


class GroupPresetTableWidget(QGroupBox):
    """A Widget to create, edit, delete and set micromanager group presets.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget. By default, None.
    mmcore : CMMCorePlus | None
        Optional `CMMCorePlus` micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new) `CMMCorePlus.instance()`.
    """

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._mmc.events.systemConfigurationLoaded.connect(self._populate_table)

        self._mmc.events.configGroupDeleted.connect(self._on_group_deleted)
        self._mmc.events.configDefined.connect(self._on_new_group_preset)

        self._create_gui()

        self._populate_table()

        self.destroyed.connect(self._disconnect)

    def _create_gui(self) -> None:

        self.setLayout(QVBoxLayout())
        self.layout().setSpacing(5)
        self.setContentsMargins(0, 0, 0, 0)

        save_btn = self._add_save_button()
        self.layout().addWidget(save_btn)

        self.table_wdg = _MainTable()
        self.table_wdg.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.layout().addWidget(self.table_wdg)

        btns = self._add_groups_presets_buttons()
        self.layout().addWidget(btns)

        self._enable_buttons(False)

    def _add_groups_presets_buttons(self) -> QWidget:

        main_wdg = QWidget()
        main_wdg_layout = QHBoxLayout()
        main_wdg_layout.setSpacing(10)
        main_wdg_layout.setContentsMargins(0, 0, 0, 0)
        main_wdg.setLayout(main_wdg_layout)

        lbl_sizepolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # groups
        groups_btn_wdg = QWidget()
        groups_layout = QHBoxLayout()
        groups_layout.setSpacing(5)
        groups_layout.setContentsMargins(0, 0, 0, 0)
        groups_btn_wdg.setLayout(groups_layout)

        groups_lbl = QLabel(text="Group:")
        groups_lbl.setSizePolicy(lbl_sizepolicy)
        self.groups_add_btn = QPushButton(text="+")
        self.groups_add_btn.clicked.connect(self._add_group)
        self.groups_remove_btn = QPushButton(text="-")
        self.groups_remove_btn.clicked.connect(self._delete_group)
        self.groups_edit_btn = QPushButton(text="Edit")
        self.groups_edit_btn.clicked.connect(self._edit_group)
        groups_layout.addWidget(groups_lbl)
        groups_layout.addWidget(self.groups_add_btn)
        groups_layout.addWidget(self.groups_remove_btn)
        groups_layout.addWidget(self.groups_edit_btn)

        main_wdg_layout.addWidget(groups_btn_wdg)

        # presets
        presets_btn_wdg = QWidget()
        presets_layout = QHBoxLayout()
        presets_layout.setSpacing(5)
        presets_layout.setContentsMargins(0, 0, 0, 0)
        presets_btn_wdg.setLayout(presets_layout)

        presets_lbl = QLabel(text="Preset:")
        presets_lbl.setSizePolicy(lbl_sizepolicy)
        self.presets_add_btn = QPushButton(text="+")
        self.presets_add_btn.clicked.connect(self._add_preset)
        self.presets_remove_btn = QPushButton(text="-")
        self.presets_remove_btn.clicked.connect(self._delete_preset)
        self.presets_edit_btn = QPushButton(text="Edit")
        self.presets_edit_btn.clicked.connect(self._edit_preset)
        presets_layout.addWidget(presets_lbl)
        presets_layout.addWidget(self.presets_add_btn)
        presets_layout.addWidget(self.presets_remove_btn)
        presets_layout.addWidget(self.presets_edit_btn)

        main_wdg_layout.addWidget(presets_btn_wdg)

        return main_wdg

    def _add_save_button(self) -> QWidget:

        save_btn_wdg = QWidget()
        save_btn_layout = QHBoxLayout()
        save_btn_layout.setSpacing(5)
        save_btn_layout.setContentsMargins(0, 0, 0, 0)
        save_btn_wdg.setLayout(save_btn_layout)

        spacer = QSpacerItem(
            10, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        save_btn_layout.addItem(spacer)
        self.save_btn = QPushButton(text="Save cfg")
        self.save_btn.clicked.connect(self._save_cfg)
        save_btn_layout.addWidget(self.save_btn)
        self.load_btn = QPushButton(text="Load cfg")
        self.load_btn.clicked.connect(self._load_cfg)
        save_btn_layout.addWidget(self.load_btn)

        return save_btn_wdg

    def _on_table_selection_changed(self) -> None:
        selected_rows = {r.row() for r in self.table_wdg.selectedIndexes()}
        if not selected_rows:
            self._enable_buttons(False)
        elif len(selected_rows) > 1:
            self._enable_buttons(False)
            self.groups_remove_btn.setEnabled(True)
            self.presets_remove_btn.setEnabled(True)
        else:
            self._enable_buttons(True)

    def _enable_buttons(self, enabled: bool) -> None:
        self.groups_remove_btn.setEnabled(enabled)
        self.groups_edit_btn.setEnabled(enabled)
        self.presets_add_btn.setEnabled(enabled)
        self.presets_remove_btn.setEnabled(enabled)
        self.presets_edit_btn.setEnabled(enabled)

    def _on_system_cfg_loaded(self) -> None:
        self._populate_table()

    def _on_new_group_preset(
        self, group: str, preset: str, device: str, property: str, value: str
    ) -> None:

        if not device or not property or not value:
            return

        if matching_item := self.table_wdg.findItems(group, Qt.MatchFlag.MatchExactly):
            row = matching_item[0].row()

            if isinstance(self.table_wdg.cellWidget(row, 1), PropertyWidget):

                dev_prop_val = [
                    (k[0], k[1], k[2]) for k in self._mmc.getConfigData(group, preset)
                ]

                self._mmc.deleteConfigGroup(group)

                if not preset:
                    idx = sum(
                        UNNAMED_PRESET in p for p in self.getAvailableConfigs(group)
                    )
                    preset = f"{UNNAMED_PRESET}_{idx}" if idx > 0 else UNNAMED_PRESET

                with block_core(self._mmc.events):
                    for d, p, v in dev_prop_val:
                        self._mmc.defineConfig(group, preset, d, p, v)

        self._populate_table()

    def _reset_table(self) -> None:
        self._disconnect_wdgs()
        self.table_wdg.clearContents()
        self.table_wdg.setRowCount(0)

    def _disconnect_wdgs(self) -> None:
        for r in range(self.table_wdg.rowCount()):
            wdg = self.table_wdg.cellWidget(r, 1)
            if isinstance(wdg, PresetsWidget):
                wdg._disconnect()

    def _populate_table(self) -> None:
        self._reset_table()
        if groups := self._mmc.getAvailableConfigGroups():
            for row, group in enumerate(groups):
                self.table_wdg.insertRow(row)
                self.table_wdg.setItem(row, 0, QTableWidgetItem(str(group)))
                wdg = self._create_group_widget(group)
                self.table_wdg.setCellWidget(row, 1, wdg)
                if isinstance(wdg, PresetsWidget):
                    wdg = wdg._combo
                elif isinstance(wdg, PropertyWidget):
                    wdg = wdg._value_widget  # type: ignore

    def _get_cfg_data(self, group: str, preset: str) -> tuple[str, str, str, int]:
        # Return last device-property-value for the preset and the
        # total number of device-property-value included in the preset.
        data = list(self._mmc.getConfigData(group, preset))
        if not data:
            return "", "", "", 0
        assert len(data), "No config data"
        dev, prop, val = data[-1]
        return dev, prop, val, len(data)

    def _create_group_widget(self, group: str) -> PresetsWidget | PropertyWidget:
        """Return a widget depending on presets and device-property."""
        # get group presets
        presets = list(self._mmc.getAvailableConfigs(group))

        if not presets:
            return  # type: ignore

        # use only the first preset since device
        # and property are the same for the presets
        device, prop, _, dev_prop_val_count = self._get_cfg_data(group, presets[0])

        if len(presets) > 1 or dev_prop_val_count > 1 or dev_prop_val_count == 0:
            return PresetsWidget(group)
        else:
            return PropertyWidget(device, prop)

    def _close_if_hasattr(self) -> None:
        attr_list = [
            "_add_group_wdg",
            "_edit_preset_wgd",
            "_add_preset_wdg",
            "_edit_group_wdg",
        ]
        for i in attr_list:
            if hasattr(self, i):
                getattr(self, i).close()

    def _add_group(self) -> None:
        self._close_if_hasattr()
        self._add_group_wdg = AddGroupWidget(parent=self)
        self._add_group_wdg.show()

    def _delete_group(self) -> None:
        selected_rows = {r.row() for r in self.table_wdg.selectedIndexes()}

        if not selected_rows:
            return

        groups = [
            self.table_wdg.item(row, 0).text()
            for row in sorted(selected_rows, reverse=True)
        ]

        msg = self._msg_box(f"Delete '{',  '.join(groups)}'?")

        if msg == QMessageBox.StandardButton.Ok:
            for row, group in enumerate(groups):
                self.table_wdg.removeRow(row)
                self._mmc.deleteConfigGroup(group)

    def _msg_box(self, msg: str) -> Any:
        msgBox = QMessageBox(parent=self)
        msgBox.setIcon(QMessageBox.Icon.Warning)
        msgBox.setWindowTitle("Delete")
        msgBox.setText(msg)
        msgBox.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        return msgBox.exec()

    def _on_group_deleted(self, group: str) -> None:
        if matching_item := self.table_wdg.findItems(group, Qt.MatchFlag.MatchExactly):
            self.table_wdg.removeRow(matching_item[0].row())

    def _edit_group(self) -> None:
        selected_rows = {r.row() for r in self.table_wdg.selectedIndexes()}
        if not selected_rows or len(selected_rows) > 1:
            return

        row = list(selected_rows)[0]
        group = self.table_wdg.item(row, 0).text()
        self._close_if_hasattr()
        self._edit_group_wdg = EditGroupWidget(group, parent=self)
        self._edit_group_wdg.show()

    def _add_preset(self) -> None:
        selected_rows = {r.row() for r in self.table_wdg.selectedIndexes()}
        if not selected_rows or len(selected_rows) > 1:
            return

        row = list(selected_rows)[0]
        group = self.table_wdg.item(row, 0).text()
        wdg = self.table_wdg.cellWidget(row, 1)

        if isinstance(wdg, PropertyWidget):
            return

        self._close_if_hasattr()
        self._add_preset_wdg = AddPresetWidget(group, parent=self)
        self._add_preset_wdg.show()

    def _delete_preset(self) -> None:
        selected_rows = {r.row() for r in self.table_wdg.selectedIndexes()}

        if not selected_rows:
            return

        groups_preset = [
            (row, self.table_wdg.item(row, 0).text(), self.table_wdg.cellWidget(row, 1))
            for row in sorted(selected_rows, reverse=True)
        ]

        _text = []
        for _, group, wdg in groups_preset:
            if isinstance(wdg, PresetsWidget):
                _text.append(f"({group},  {wdg._combo.currentText()})")
            else:
                _text.append(f"({group})")

        msg = self._msg_box(f"Delete '{',  '.join(_text)}'?")

        if msg == QMessageBox.StandardButton.Ok:
            for row, group, wdg in groups_preset:
                if isinstance(wdg, PresetsWidget):
                    preset = wdg._combo.currentText()

                    if len(wdg.allowedValues()) > 1:
                        self._mmc.deleteConfig(group, preset)
                    else:
                        self.table_wdg.removeRow(row)
                        self._mmc.deleteConfigGroup(group)

                elif isinstance(wdg, PropertyWidget):
                    self.table_wdg.removeRow(row)
                    self._mmc.deleteConfigGroup(group)

    def _edit_preset(self) -> None:
        selected_rows = {r.row() for r in self.table_wdg.selectedIndexes()}
        if not selected_rows or len(selected_rows) > 1:
            return

        row = list(selected_rows)[0]
        group = self.table_wdg.item(row, 0).text()
        wdg = self.table_wdg.cellWidget(row, 1)
        if isinstance(wdg, PropertyWidget):
            return
        if isinstance(wdg, PresetsWidget):
            preset = wdg._combo.currentText()
        self._close_if_hasattr()
        self._edit_preset_wgd = EditPresetWidget(group, preset, parent=self)
        self._edit_preset_wgd.show()

    def _save_cfg(self) -> None:
        (filename, _) = QFileDialog.getSaveFileName(
            self, "Save Micro-Manager Configuration."
        )
        if filename:
            self._mmc.saveSystemConfiguration(filename)

    def _load_cfg(self) -> None:
        """Open file dialog to select a config file."""
        (filename, _) = QFileDialog.getOpenFileName(
            self, "Select a Micro-Manager configuration file", "", "cfg(*.cfg)"
        )
        if filename:
            load_system_config(filename, mmcore=self._mmc)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._populate_table)
        self._mmc.events.configGroupDeleted.disconnect(self._on_group_deleted)
        self._mmc.events.configDefined.disconnect(self._on_new_group_preset)
