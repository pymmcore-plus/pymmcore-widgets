from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Slot
from qtpy.QtWidgets import (
    QAbstractScrollArea,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets._models import set_config_groups
from pymmcore_widgets._util import load_system_config
from pymmcore_widgets.control._presets_widget import PresetsWidget
from pymmcore_widgets.device_properties._property_widget import PropertyWidget

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent

    from pymmcore_widgets._models import ConfigGroup
    from pymmcore_widgets.config_presets._views._config_groups_editor import (
        ConfigGroupsEditor,
    )


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
    """A Widget to view and set micromanager group presets.

    Shows a table of config groups with their current preset values.
    Provides an "Edit Groups and Presets" button that opens a
    `ConfigGroupsEditor` dialog for editing.

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

        self.table_wdg = _MainTable()

        self.save_btn = QPushButton(text="Save cfg")
        self.save_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.save_btn.clicked.connect(self._save_cfg)
        self.load_btn = QPushButton(text="Load cfg")
        self.load_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.load_btn.clicked.connect(self._load_cfg)

        self.edit_groups_btn = QPushButton(text="Edit Groups and Presets")
        self.edit_groups_btn.clicked.connect(self._open_config_groups_editor)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(self.edit_groups_btn)
        btn_layout.addItem(
            QSpacerItem(20, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        )
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.load_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(5)
        layout.addWidget(self.table_wdg)
        layout.addLayout(btn_layout)

        self._populate_table()
        self.destroyed.connect(self._disconnect)

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

        self.table_wdg.resizeColumnToContents(0)

    def _get_cfg_data(self, group: str, preset: str) -> tuple[str, str, str, int]:
        data = list(self._mmc.getConfigData(group, preset))
        if not data:
            return "", "", "", 0
        assert len(data), "No config data"
        dev, prop, val = data[-1]
        return dev, prop, val, len(data)

    def _create_group_widget(self, group: str) -> PresetsWidget | PropertyWidget:
        """Return a widget depending on presets and device-property."""
        presets = list(self._mmc.getAvailableConfigs(group))

        if not presets:
            return  # type: ignore

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

        mmc = self._mmc

        def _apply(
            groups: list[ConfigGroup], deleted: list[str], channel: str | None
        ) -> None:
            set_config_groups(
                mmc, groups, deleted_groups=deleted, channel_group=channel
            )
            editor.setClean()

        editor = ConfigGroupsEditor.create_from_core(mmc)
        editor.applyRequested.connect(_apply)
        dlg = _ConfigEditorDialog(editor, parent=self)
        dlg.resize(1000, 600)
        dlg.exec()

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


class _ConfigEditorDialog(QDialog):
    """Dialog that hosts a ConfigGroupsEditor and prompts on dirty close."""

    def __init__(
        self, editor: ConfigGroupsEditor, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Groups and Presets")
        self._editor = editor
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(editor)

    def reject(self) -> None:
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._editor.isClean():
            result = QMessageBox.question(
                self._editor,
                "Unsaved Changes",
                "You have unsaved changes. Would you like to apply them?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if result == QMessageBox.StandardButton.Yes:
                self._editor._emit_apply_requested()
            elif result == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        event.accept()
