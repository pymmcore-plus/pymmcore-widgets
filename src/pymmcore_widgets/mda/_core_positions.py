from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from pymmcore_plus._logger import logger
from pymmcore_plus._util import retry
from qtpy.QtWidgets import QCheckBox, QMessageBox, QWidget, QWidgetAction
from superqt.utils import signals_blocked

from pymmcore_widgets.useq_widgets import PositionTable
from pymmcore_widgets.useq_widgets._column_info import (
    ButtonColumn,
)
from pymmcore_widgets.useq_widgets._positions import AF_DEFAULT_TOOLTIP

if TYPE_CHECKING:
    from typing import TypedDict

    class SaveInfo(TypedDict):
        save_dir: str
        file_name: str
        split_positions: bool
        should_save: bool


class CoreConnectedPositionTable(PositionTable):
    """[PositionTable](../PositionTable#) connected to a Micro-Manager core instance.

    Parameters
    ----------
    rows : int
        Number of rows to initialize the table with, by default 0.
    mmcore : CMMCorePlus | None
        Optional [`CMMCorePlus`][pymmcore_plus.CMMCorePlus] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    parent : QWidget | None
        Optional parent widget, by default None.
    """

    def __init__(
        self,
        rows: int = 0,
        mmcore: CMMCorePlus | None = None,
        parent: QWidget | None = None,
    ):
        # must come before __init__ since it is used in super()._on_use_af_toggled
        self._af_btn_col = ButtonColumn(
            key="af_btn", glyph=MDI6.arrow_left, on_click=self._set_af_from_core
        )
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
        self.table().addColumn(self._xy_btn_col, self.table().indexOf(self.X))
        self.table().addColumn(self._z_btn_col, self.table().indexOf(self.Z) + 1)
        self.table().addColumn(self._af_btn_col, self.table().indexOf(self.AF) + 1)

        # when a new row is inserted, call _on_rows_inserted
        # to update the new values from the core position
        self.table().model().rowsInserted.connect(self._on_rows_inserted)

        # add move_to_selection to toolbar and link up callback
        toolbar = self.toolBar()
        action0 = next(x for x in toolbar.children() if isinstance(x, QWidgetAction))
        toolbar.insertWidget(action0, self.move_to_selection)
        self.table().itemSelectionChanged.connect(self._on_selection_change)

        # connect
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_config_loaded)
        self._mmc.events.propertyChanged.connect(self._on_property_changed)

        self.destroyed.connect(self._disconnect)

        self._on_sys_config_loaded()
        # hide the set-AF-offset button to begin with.
        self._on_af_per_position_toggled(self.af_per_position.isChecked())

    # ----------------------- private methods -----------------------

    def _on_sys_config_loaded(self) -> None:
        """Update the table when the system configuration is loaded."""
        self._update_xy_enablement()
        self._update_z_enablement()
        self._update_autofocus_enablement()

    def _on_property_changed(self, device: str, prop: str, _val: str = "") -> None:
        """Update the autofocus device combo box when the autofocus device changes."""
        if device == "Core":
            if prop == "XYStage":
                self._update_xy_enablement()
            elif prop == "Focus":
                self._update_z_enablement()
            elif prop == "AutoFocus":
                self._update_autofocus_enablement()

    def _update_xy_enablement(self) -> None:
        """Enable/disable the XY columns and button."""
        xy_device = self._mmc.getXYStageDevice()
        x_col = self.table().indexOf(self.X)
        y_col = self.table().indexOf(self.Y)
        xy_btn_col = self.table().indexOf(self._xy_btn_col)
        self.table().setColumnHidden(x_col, not bool(xy_device))
        self.table().setColumnHidden(y_col, not bool(xy_device))
        self.table().setColumnHidden(xy_btn_col, not bool(xy_device))

    def _update_z_enablement(self) -> None:
        """Enable/disable the Z columns and button."""
        z_device = bool(self._mmc.getFocusDevice())
        self.include_z.setEnabled(z_device)
        if not z_device:
            # but don't recheck it if it's already unchecked
            self.include_z.setChecked(False)
        self.include_z.setToolTip("" if z_device else "Focus device unavailable.")

    def _update_autofocus_enablement(self) -> None:
        """Update the autofocus device combo box."""
        af_device = self._mmc.getAutoFocusDevice()
        self.af_per_position.setEnabled(bool(af_device))
        self.af_per_position.setToolTip(
            AF_DEFAULT_TOOLTIP if af_device else "AutoFocus device unavailable."
        )

    def _add_row(self) -> None:
        """Add a new to the end of the table and use the current core position."""
        # note: _add_row is only called when act_add_row is triggered
        # (e.g. when the + button is clicked). Not when a row is added programmatically

        # block the signal that's going to be emitted until _on_rows_inserted
        # has had a chance to update the values from the current stage position
        with signals_blocked(self):
            super()._add_row()
        self.valueChanged.emit()

    def _on_rows_inserted(self, parent: Any, start: int, end: int) -> None:
        # when a new row is inserted by any means, populate it with default values
        # this is connected above in __init_ with self.model().rowsInserted.connect
        with signals_blocked(self):
            for row_idx in range(start, end + 1):
                self._set_xy_from_core(row_idx)
                self._set_z_from_core(row_idx)
                self._set_af_from_core(row_idx)
        self.valueChanged.emit()

    def _set_xy_from_core(self, row: int, col: int = 0) -> None:
        if self._mmc.getXYStageDevice():
            data = {
                self.X.key: self._mmc.getXPosition(),
                self.Y.key: self._mmc.getYPosition(),
            }
            self.table().setRowData(row, data)

    def _set_z_from_core(self, row: int, col: int = 0) -> None:
        if self._mmc.getFocusDevice():
            data = {self.Z.key: self._mmc.getZPosition()}
            self.table().setRowData(row, data)

    def _set_af_from_core(self, row: int, col: int = 0) -> None:
        if not self._mmc.getAutoFocusDevice():
            return  # AF offset automatically set to 0.0

        # 'Set AF Offset per Position' checked but the autofocus isn't locked in focus
        if self.af_per_position.isChecked() and not self._mmc.isContinuousFocusLocked():
            # delete last added row
            self.table().removeRow(row)
            # show warning message
            af = f"'{self._mmc.getAutoFocusDevice()!r}'"
            title = f"Warning: {af}"
            msg = (
                f"'{self.af_per_position.text()!r}' is checked, but the {af} autofocus "
                f"device is not engaged. \n\nEngage the {af} device before "
                "adding the position."
            )
            QMessageBox.warning(self, title, msg, QMessageBox.StandardButton.Ok)
            return

        # only if the autofocus device is locked in focus we can get the current offset
        elif self._mmc.isContinuousFocusLocked():
            data = {self.AF.key: self._mmc.getAutoFocusOffset()}
            self.table().setRowData(row, data)

    def _on_selection_change(self) -> None:
        if not self.move_to_selection.isChecked():
            return

        if not self._mmc.getXYStageDevice() and not self._mmc.getFocusDevice():
            return

        selected_rows: set[int] = {i.row() for i in self.table().selectedItems()}

        if len(selected_rows) == 1:
            row = next(iter(selected_rows))
            data = self.table().rowData(row, exclude_hidden_cols=True)

            # check if autofocus is locked before moving
            af_locked = self._mmc.isContinuousFocusLocked()
            af_offset = self._mmc.getAutoFocusOffset() if af_locked else None

            if self._mmc.getXYStageDevice():
                x = data.get(self.X.key, self._mmc.getXPosition())
                y = data.get(self.Y.key, self._mmc.getYPosition())
                self._mmc.setXYPosition(x, y)

            if self.include_z.isChecked() and self._mmc.getFocusDevice():
                z = data.get(self.Z.key, self._mmc.getZPosition())
                self._mmc.setZPosition(z)

            # HANDLE AUTOFOCUS OFFSET___________________________________________________

            # if 'af_per_position' is not checked, 'AF.key' will not be in 'data and
            # 'table_af' will be None. here we get the autofocus offset from the table
            table_af_offset = data.get(self.AF.key, None)

            # if 'af_per_position' is checked, 'table_af' is not 'None' and we use it.
            # if 'af_per_position' is not checked but the autofocus was locked before
            # moving, we use the 'af_offset' (from before moving). Otherwise,
            # if 'af_per_position' is not checked and the autofocus was not locked
            # before moving, we do not use autofocus.
            if table_af_offset is not None or af_offset is not None:
                self._mmc.setAutoFocusOffset(
                    table_af_offset if table_af_offset is not None else af_offset
                )
                try:
                    self._perform_autofocus()
                    self._mmc.enableContinuousFocus(af_locked)
                except RuntimeError as e:
                    logger.warning("Hardware autofocus failed. %s", e)

            self._mmc.waitForSystem()

    def _perform_autofocus(self) -> None:
        # run autofocus (run 3 times in case it fails)
        @retry(exceptions=RuntimeError, tries=3, logger=logger.warning)
        def _perform_full_focus() -> None:
            self._mmc.fullFocus()
            self._mmc.waitForSystem()

        self._mmc.waitForSystem()
        _perform_full_focus()

    def _on_include_z_toggled(self, checked: bool) -> None:
        z_btn_col = self.table().indexOf(self._z_btn_col)
        self.table().setColumnHidden(z_btn_col, not checked)
        super()._on_include_z_toggled(checked)

    def _on_af_per_position_toggled(self, checked: bool) -> None:
        af_btn_col = self.table().indexOf(self._af_btn_col)
        self.table().setColumnHidden(af_btn_col, not checked)
        super()._on_af_per_position_toggled(checked)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(
            self._on_sys_config_loaded
        )
        self._mmc.events.propertyChanged.disconnect(self._on_property_changed)
