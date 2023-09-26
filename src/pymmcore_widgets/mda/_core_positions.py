from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtWidgets import (
    QCheckBox,
    QWidget,
    QWidgetAction,
)

from pymmcore_widgets.useq_widgets import PositionTable
from pymmcore_widgets.useq_widgets._column_info import ButtonColumn

if TYPE_CHECKING:
    from typing import TypedDict

    class SaveInfo(TypedDict):
        save_dir: str
        file_name: str
        split_positions: bool
        should_save: bool


class CoreConnectedPositionTable(PositionTable):
    def __init__(
        self,
        rows: int = 0,
        mmcore: CMMCorePlus | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(rows, parent)
        self._mmc = mmcore or CMMCorePlus.instance()

        self.move_to_selection = QCheckBox("Move Stage to Selected Point")
        # add a button to update XY to the current position
        self._xy_btn_col = ButtonColumn(
            key="xy_btn", glyph=MDI6.arrow_right, on_click=self._set_xy_from_core
        )
        self._z_btn_col = ButtonColumn(
            key="z_btn", glyph=MDI6.arrow_left, on_click=self._set_z_from_core
        )
        self._af_btn_col = ButtonColumn(
            key="af_btn", glyph=MDI6.arrow_left, on_click=self._set_af_from_core
        )
        self.table().addColumn(self._xy_btn_col, self.table().indexOf(self.X))
        self.table().addColumn(self._z_btn_col, self.table().indexOf(self.Z) + 1)
        self.table().addColumn(self._af_btn_col, self.table().indexOf(self.AF) + 1)

        self.use_af.af_combo.setEditable(False)

        # add move_to_selection to toolbar and link up callback
        toolbar = self.toolBar()
        action0 = next(x for x in toolbar.children() if isinstance(x, QWidgetAction))
        toolbar.insertWidget(action0, self.move_to_selection)
        self.table().itemSelectionChanged.connect(self._on_selection_change)

        # connect
        self._mmc.events.systemConfigurationLoaded.connect(self._update_use_af_combo)
        self._mmc.events.propertyChanged.connect(self._on_property_changed)

        self.destroyed.connect(self._disconnect)

        # update the autofocus widget
        self._update_use_af_combo()
        self.use_af._on_checkbox_toggled(False)

    def _update_use_af_combo(self) -> None:
        """Update the autofocus device combo box."""
        self.use_af.af_combo.clear()
        self.use_af.af_checkbox.setChecked(False)
        self.use_af.af_checkbox.setToolTip("")
        af_device = self._mmc.getAutoFocusDevice()

        self.use_af.setEnabled(bool(af_device))

        if not af_device:
            self.use_af.af_checkbox.setToolTip("No Core Autofocus device selected.")
            return

        stage_devices = list(self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice))
        self.use_af.af_combo.addItems(stage_devices)
        self.use_af.af_checkbox.setChecked(False)
        # if more than one device, set the autofocus device to the first stage device
        # that is not the current focus device
        if len(stage_devices) == 1:
            return
        for dev in stage_devices:
            if dev != self._mmc.getFocusDevice():
                self.use_af.af_combo.setCurrentText(dev)
                break

    def _on_property_changed(self, device: str, prop: str, value: str) -> None:
        """Update the autofocus device combo box when the autofocus device changes."""
        if device != "Core" or prop != "AutoFocus":
            return
        self.use_af.af_checkbox.setChecked(False)
        self.use_af.af_checkbox.setEnabled(bool(value))
        self._update_use_af_combo()

    def _set_xy_from_core(self, row: int, col: int) -> None:
        data = {
            self.X.key: self._mmc.getXPosition(),
            self.Y.key: self._mmc.getYPosition(),
        }
        self.table().setRowData(row, data)

    def _set_z_from_core(self, row: int, col: int) -> None:
        data = {self.Z.key: self._mmc.getPosition(self._mmc.getFocusDevice())}
        self.table().setRowData(row, data)

    def _set_af_from_core(self, row: int, col: int) -> None:
        af_z_device = self.use_af.value()
        if af_z_device is None:
            return
        data = {self.AF.key: self._mmc.getPosition(af_z_device)}
        self.table().setRowData(row, data)

    def _on_selection_change(self) -> None:
        if not self.move_to_selection.isChecked():
            return

        selected_rows: set[int] = {i.row() for i in self.table().selectedItems()}
        if len(selected_rows) == 1:
            row = next(iter(selected_rows))
            data = self.table().rowData(row)

            x = data.get(self.X.key, self._mmc.getXPosition())
            y = data.get(self.Y.key, self._mmc.getYPosition())
            z = data.get(self.Z.key, self._mmc.getZPosition())
            af = data.get(self.AF.key, 0.0)

            try:
                self._mmc.setXYPosition(x, y)
                self._mmc.setZPosition(z)
                self._perform_autofocus(af)

            except RuntimeError:
                logging.error("Failed to move stage to selected position.")
            self._mmc.waitForSystem()

    def _perform_autofocus(self, af: float | None) -> None:
        af_z_device = self.use_af.value()
        if not af or not af_z_device:
            return

        # get if af is on
        _af_enabled = self._mmc.isContinuousFocusEnabled()

        # switch off autofocus device before performing fullFocus()
        # or fullFocus() doe not perform well
        if _af_enabled:
            self._mmc.enableContinuousFocus(False)

        # set af position
        self._mmc.setPosition(af_z_device, af)
        self._mmc.waitForSystem()

        # run autofocus
        # self._mmc.fullFocus()
        self._mmc.setZPosition(100)
        self._mmc.waitForSystem()

        # if was on, switch back on
        if _af_enabled:
            self._mmc.enableContinuousFocus(True)

    def _get_z_focus_device(self) -> tuple[str, str]:
        """Return the key and device name for the Z position."""
        if self.use_af.af_checkbox.isChecked():
            focus_device = self.use_af.value()
            if focus_device is None:
                return self.Z.key, self._mmc.getFocusDevice()
            else:
                return self.AF.key, focus_device
        else:
            focus_device = self._mmc.getFocusDevice()
            return self.Z.key, self._mmc.getFocusDevice()

    def _on_include_z_toggled(self, checked: bool) -> None:
        super()._on_include_z_toggled(checked)
        z_btn_col = self.table().indexOf(self._z_btn_col)
        self.table().setColumnHidden(z_btn_col, not checked)

    def _on_use_af_toggled(self, checked: bool) -> None:
        super()._on_use_af_toggled(checked)
        af_btn_col = self.table().indexOf(self._af_btn_col)
        self.table().setColumnHidden(af_btn_col, not checked)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._update_use_af_combo)
        self._mmc.events.propertyChanged.disconnect(self._on_property_changed)
