from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Slot
from qtpy.QtWidgets import (
    QAbstractScrollArea,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets._util import load_system_config
from pymmcore_widgets.control._presets_widget import PresetsWidget
from pymmcore_widgets.device_properties._property_widget import PropertyWidget


class _MainTable(QTableWidget):
    """Set table properties for Group and Preset TableWidget."""

    def __init__(self) -> None:
        super().__init__()
        if (hdr := self.horizontalHeader()) is not None:
            hdr.setStretchLastSection(True)
            hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignHCenter)
        if (vh := self.verticalHeader()) is not None:
            vh.setVisible(False)
            vh.setSectionResizeMode(vh.ResizeMode.Fixed)
            vh.setDefaultSectionSize(24)
        self.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Group", "Preset"])
        self.setMinimumHeight(200)


class GroupPresetTableWidget(QWidget):
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
        self._mmc.events.configDefined.connect(self._on_config_defined)

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

        self.edit_groups_btn = QPushButton(text="Edit Groups and Presets")
        self.edit_groups_btn.clicked.connect(self._open_config_groups_editor)
        self.layout().addWidget(self.edit_groups_btn)

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
        self.save_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.save_btn.clicked.connect(self._save_cfg)
        save_btn_layout.addWidget(self.save_btn)
        self.load_btn = QPushButton(text="Load cfg")
        self.load_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.load_btn.clicked.connect(self._load_cfg)
        save_btn_layout.addWidget(self.load_btn)

        return save_btn_wdg

    def _reset_table(self) -> None:
        self._disconnect_wdgs()
        self.table_wdg.clearContents()
        self.table_wdg.setRowCount(0)

    def _disconnect_wdgs(self) -> None:
        for r in range(self.table_wdg.rowCount()):
            wdg = self.table_wdg.cellWidget(r, 1)
            if isinstance(wdg, PresetsWidget):
                wdg._disconnect()

    @Slot()
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
                    wdg = wdg.inner_widget

        # resize to contents the table
        self.table_wdg.resizeColumnToContents(0)

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
            return PresetsWidget(group, mmcore=self._mmc)
        else:
            return PropertyWidget(device, prop, mmcore=self._mmc)

    @Slot(str)
    def _on_group_deleted(self, group: str) -> None:
        if matching_item := self.table_wdg.findItems(group, Qt.MatchFlag.MatchExactly):
            self.table_wdg.removeRow(matching_item[0].row())

    @Slot(str, str, str, str, str)
    def _on_config_defined(
        self, group: str, preset: str, device: str, property: str, value: str
    ) -> None:
        if not device or not property or not value:
            return
        self._populate_table()

    def _open_config_groups_editor(self) -> None:
        from pymmcore_widgets.config_presets import ConfigGroupsEditor

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Groups and Presets")
        layout = QVBoxLayout(dlg)
        editor = ConfigGroupsEditor.create_from_core(self._mmc, parent=dlg)
        editor.configChanged.connect(self._populate_table)
        layout.addWidget(editor)
        dlg.resize(800, 600)
        dlg.show()

    @Slot()
    def _save_cfg(self) -> None:
        (filename, _) = QFileDialog.getSaveFileName(
            self, "Save Micro-Manager Configuration."
        )
        if filename:
            self._mmc.saveSystemConfiguration(
                filename if str(filename).endswith(".cfg") else f"{filename}.cfg"
            )

    @Slot()
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
        self._mmc.events.configDefined.disconnect(self._on_config_defined)
