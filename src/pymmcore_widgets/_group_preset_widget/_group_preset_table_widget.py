import warnings
from typing import List, Tuple, Union

from pymmcore_plus import CMMCorePlus
from qtpy import QtWidgets as QtW
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QVBoxLayout

from pymmcore_widgets._group_preset_widget._add_group_widget import AddGroupWidget
from pymmcore_widgets._group_preset_widget._add_preset_widget import AddPresetWidget
from pymmcore_widgets._group_preset_widget._edit_group_widget import EditGroupWidget
from pymmcore_widgets._group_preset_widget._edit_preset_widget import EditPresetWidget
from pymmcore_widgets._presets_widget import PresetsWidget
from pymmcore_widgets._property_widget import PropertyWidget

# from ._add_group_widget import AddGroupWidget
# from ._add_preset_widget import AddPresetWidget
# from ._edit_group_widget import EditGroupWidget
# from ._edit_preset_widget import EditPresetWidget


class _MainTable(QtW.QTableWidget):
    """Set table properties for Group and Preset TableWidget."""

    def __init__(self) -> None:
        super().__init__()
        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(hdr.Stretch)
        hdr.setDefaultAlignment(Qt.AlignHCenter)
        vh = self.verticalHeader()
        vh.setVisible(False)
        vh.setSectionResizeMode(vh.Fixed)
        vh.setDefaultSectionSize(24)
        self.setEditTriggers(QtW.QTableWidget.NoEditTriggers)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Group", "Preset"])
        self.setMinimumHeight(200)


class GroupPresetTableWidget(QtW.QGroupBox):
    """Widget to get/set group presets."""

    def __init__(self) -> None:
        super().__init__()

        self._mmc = CMMCorePlus.instance()
        self._mmc.events.systemConfigurationLoaded.connect(self._populate_table)

        # connections to the new pymmcore-plus groupDeleted signal
        self._mmc.events.groupDeleted.connect(self._on_group_deleted)
        # presetDeleted signal is handled by the "PresetsWidget"/"PropertyWidget"
        self._mmc.events.newGroupPreset.connect(self._on_new_group_preset)

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
        self.layout().addWidget(self.table_wdg)

        btns = self._add_groups_presets_buttons()
        self.layout().addWidget(btns)

    def _add_groups_presets_buttons(self) -> QtW.QWidget:

        main_wdg = QtW.QWidget()
        main_wdg_layout = QtW.QHBoxLayout()
        main_wdg_layout.setSpacing(10)
        main_wdg_layout.setContentsMargins(0, 0, 0, 0)
        main_wdg.setLayout(main_wdg_layout)

        lbl_sizepolicy = QtW.QSizePolicy(QtW.QSizePolicy.Fixed, QtW.QSizePolicy.Fixed)

        # groups
        groups_btn_wdg = QtW.QWidget()
        groups_layout = QtW.QHBoxLayout()
        groups_layout.setSpacing(5)
        groups_layout.setContentsMargins(0, 0, 0, 0)
        groups_btn_wdg.setLayout(groups_layout)

        groups_lbl = QtW.QLabel(text="Group:")
        groups_lbl.setSizePolicy(lbl_sizepolicy)
        self.groups_add_btn = QtW.QPushButton(text="+")
        self.groups_add_btn.clicked.connect(self._add_group)
        self.groups_remove_btn = QtW.QPushButton(text="-")
        self.groups_remove_btn.clicked.connect(self._delete_group)
        self.groups_edit_btn = QtW.QPushButton(text="Edit")
        self.groups_edit_btn.clicked.connect(self._edit_group)
        groups_layout.addWidget(groups_lbl)
        groups_layout.addWidget(self.groups_add_btn)
        groups_layout.addWidget(self.groups_remove_btn)
        groups_layout.addWidget(self.groups_edit_btn)

        main_wdg_layout.addWidget(groups_btn_wdg)

        # presets
        presets_btn_wdg = QtW.QWidget()
        presets_layout = QtW.QHBoxLayout()
        presets_layout.setSpacing(5)
        presets_layout.setContentsMargins(0, 0, 0, 0)
        presets_btn_wdg.setLayout(presets_layout)

        presets_lbl = QtW.QLabel(text="Preset:")
        presets_lbl.setSizePolicy(lbl_sizepolicy)
        self.presets_add_btn = QtW.QPushButton(text="+")
        self.presets_add_btn.clicked.connect(self._add_preset)
        self.presets_remove_btn = QtW.QPushButton(text="-")
        self.presets_remove_btn.clicked.connect(self._delete_preset)
        self.presets_edit_btn = QtW.QPushButton(text="Edit")
        self.presets_edit_btn.clicked.connect(self._edit_preset)
        presets_layout.addWidget(presets_lbl)
        presets_layout.addWidget(self.presets_add_btn)
        presets_layout.addWidget(self.presets_remove_btn)
        presets_layout.addWidget(self.presets_edit_btn)

        main_wdg_layout.addWidget(presets_btn_wdg)

        return main_wdg

    def _add_save_button(self) -> QtW.QWidget:

        save_btn_wdg = QtW.QWidget()
        save_btn_layout = QtW.QHBoxLayout()
        save_btn_layout.setSpacing(0)
        save_btn_layout.setContentsMargins(0, 0, 0, 0)
        save_btn_wdg.setLayout(save_btn_layout)

        spacer = QtW.QSpacerItem(
            10, 10, QtW.QSizePolicy.Expanding, QtW.QSizePolicy.Fixed
        )
        save_btn_layout.addItem(spacer)
        self.save_btn = QtW.QPushButton(text="Save cfg")
        self.save_btn.clicked.connect(self._save_cfg)
        save_btn_layout.addWidget(self.save_btn)

        return save_btn_wdg

    def _on_system_cfg_loaded(self) -> None:
        self._populate_table()

    def _on_new_group_preset(
        self, group: str, preset: str, dev_prop_val_list: List[Tuple[str, str, str]]
    ) -> None:

        if matching_item := self.table_wdg.findItems(group, Qt.MatchExactly):
            row = matching_item[0].row()

            if isinstance(self.table_wdg.cellWidget(row, 1), PropertyWidget):
                _presets = self._mmc.getAvailableConfigs(group)
                if len(_presets) > 1:
                    dev_prop_0 = [
                        (k[0], k[1])
                        for k in self._mmc.getConfigData(group, _presets[0])
                    ]
                    dev_prop_1 = [(k[0], k[1]) for k in dev_prop_val_list]
                    if dev_prop_1 != dev_prop_0:
                        warnings.warn(
                            f"{dev_prop_1} are not included in the group "
                            "and will not be added!"
                        )
                        self._mmc.deletePresetDeviceProperties(  # type: ignore
                            group, preset, dev_prop_1, emit=False
                        )
                    else:
                        self._mmc.deleteConfig(group, preset)

                self._populate_table()

        else:
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
                self.table_wdg.setItem(row, 0, QtW.QTableWidgetItem(str(group)))
                wdg = self._create_group_widget(group)
                self.table_wdg.setCellWidget(row, 1, wdg)
                if isinstance(wdg, PresetsWidget):
                    wdg = wdg._combo
                elif isinstance(wdg, PropertyWidget):
                    wdg = wdg._value_widget  # type: ignore

    def _get_cfg_data(self, group: str, preset: str) -> Tuple[str, str, str, int]:
        # Return last device-property-value for the preset and the
        # total number of device-property-value included in the preset.
        data = list(self._mmc.getConfigData(group, preset))
        if not data:
            return "", "", "", 0
        assert len(data), "No config data"
        dev, prop, val = data[-1]
        return dev, prop, val, len(data)

    def _create_group_widget(self, group: str) -> Union[PresetsWidget, PropertyWidget]:
        """Return a widget depending on presets and device-property."""
        # get group presets
        presets = list(self._mmc.getAvailableConfigs(group))

        if not presets:
            return  # type: ignore

        # use only the first preset since device
        # and property are the same for the presets
        device, property, _, dev_prop_val_count = self._get_cfg_data(group, presets[0])

        if len(presets) > 1 or dev_prop_val_count > 1 or dev_prop_val_count == 0:
            return PresetsWidget(group)
        else:
            return PropertyWidget(device, property)

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

        for row_idx in sorted(selected_rows, reverse=True):
            group = self.table_wdg.item(row_idx, 0).text()
            self.table_wdg.removeRow(row_idx)
            self._mmc.deleteConfigGroup(group)  # emitted delete group

    def _on_group_deleted(self, group: str) -> None:
        if matching_item := self.table_wdg.findItems(group, Qt.MatchExactly):
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

        for row_idx in sorted(selected_rows, reverse=True):
            group = self.table_wdg.item(row_idx, 0).text()
            wdg = self.table_wdg.cellWidget(row_idx, 1)

            if isinstance(wdg, PresetsWidget):
                preset = wdg._combo.currentText()

                if len(wdg.allowedValues()) > 1:
                    self._mmc.deleteConfig(group, preset)  # emitted delete preset
                else:
                    self.table_wdg.removeRow(row_idx)
                    self._mmc.deleteConfigGroup(group)  # emitted delete group

            elif isinstance(wdg, PropertyWidget):
                self.table_wdg.removeRow(row_idx)
                self._mmc.deleteConfigGroup(group)  # emitted delete group

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
        (filename, _) = QtW.QFileDialog.getSaveFileName(
            self, "Save Micro-Manager Configuration."
        )
        if filename:
            self._mmc.saveSystemConfiguration(filename)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._populate_table)
        self._mmc.events.groupDeleted.disconnect(self._on_group_deleted)
        self._mmc.events.newGroupPreset.disconnect(self._on_new_group_preset)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    cfg = "/Users/FG/Dropbox/git/pymmcore-widgets/tests/test_config.cfg"
    mmc = CMMCorePlus.instance()
    mmc.loadSystemConfiguration(cfg)
    app = QApplication([])
    table = GroupPresetTableWidget()
    table.show()
    app.exec_()
