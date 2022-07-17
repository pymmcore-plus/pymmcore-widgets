from typing import Tuple, Union

from qtpy import QtWidgets as QtW
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QVBoxLayout

# from ._core import get_core_singleton
# from ._presets_widget import PresetsWidget
# from ._property_widget import PropertyWidget
from pymmcore_widgets._core import get_core_singleton
from pymmcore_widgets._presets_widget import PresetsWidget
from pymmcore_widgets._property_widget import PropertyWidget


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


class GroupPresetTableWidget(QtW.QWidget):
    """Widget to get/set group presets."""

    def __init__(self) -> None:
        super().__init__()

        self._mmc = get_core_singleton()
        self._mmc.events.systemConfigurationLoaded.connect(self._populate_table)

        self._create_gui()

        self._populate_table()

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
        self.groups_remove_btn = QtW.QPushButton(text="-")
        self.groups_edit_btn = QtW.QPushButton(text="Edit")
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
        self.presets_remove_btn = QtW.QPushButton(text="-")
        self.presets_edit_btn = QtW.QPushButton(text="Edit")
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
        self.save_btn = QtW.QPushButton(text="Save")
        save_btn_layout.addWidget(self.save_btn)

        return save_btn_wdg

    def _on_system_cfg_loaded(self) -> None:
        self._populate_table()

    def _reset_table(self) -> None:
        self._disconnect_wdgs()
        self.table_wdg.clearContents()
        self.table_wdg.setRowCount(0)

    def _disconnect_wdgs(self) -> None:
        for r in range(self.table_wdg.rowCount()):
            wdg = self.table_wdg.cellWidget(r, 1)
            if isinstance(wdg, PresetsWidget):
                wdg.disconnect()

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

        if len(presets) > 1 or dev_prop_val_count > 1:
            # return PresetsWidget(group, text_color="white")
            return PresetsWidget(group)
        else:
            return PropertyWidget(device, property)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    mmc = get_core_singleton()
    mmc.loadSystemConfiguration()
    app = QApplication([])
    table = GroupPresetTableWidget()
    table.show()
    app.exec_()
