from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any, Sequence

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from pymmcore_plus._logger import logger
from pymmcore_plus._util import retry
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QMessageBox,
    QPushButton,
    QWidget,
    QWidgetAction,
    QWizard,
)
from superqt.utils import signals_blocked
from useq import WellPlatePlan

from pymmcore_widgets import HCSWizard
from pymmcore_widgets.useq_widgets import PositionTable
from pymmcore_widgets.useq_widgets._column_info import (
    ButtonColumn,
)
from pymmcore_widgets.useq_widgets._positions import AF_DEFAULT_TOOLTIP

if TYPE_CHECKING:
    from useq import Position

UPDATE_POSITIONS = "Update Positions List"
ADD_POSITIONS = "Add to Positions List"


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

        # -------------- HCS Wizard ----------------
        self._hcs_wizard: HCSWizard | None = None
        self._plate_plan: WellPlatePlan | None = None

        self._hcs_button = QPushButton("Well Plate...")
        # self._hcs_button.setIcon(icon(MDI6.view_comfy))
        self._hcs_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._hcs_button.setToolTip("Open the HCS wizard.")
        self._hcs_button.clicked.connect(self._show_hcs)

        self._edit_hcs_pos = QPushButton("Make Editable")
        self._edit_hcs_pos.setToolTip(
            "Convert HCS positions to regular editable positions."
        )
        self._edit_hcs_pos.setStyleSheet("color: red")
        self._edit_hcs_pos.hide()
        self._edit_hcs_pos.clicked.connect(self._show_pos_editing_dialog)

        self._btn_row.insertWidget(3, self._hcs_button)
        self._btn_row.insertWidget(3, self._edit_hcs_pos)
        # ------------------------------------------

        self.move_to_selection = QCheckBox("Move Stage to Selected Point")
        # add a button to update XY to the current position
        self._xy_btn_col = ButtonColumn(
            key="xy_btn", glyph=MDI6.arrow_right, on_click=self._set_xy_from_core
        )
        self._z_btn_col = ButtonColumn(
            key="z_btn", glyph=MDI6.arrow_left, on_click=self._set_z_from_core
        )
        table = self.table()
        table.addColumn(self._xy_btn_col, table.indexOf(self.X))
        table.addColumn(self._z_btn_col, table.indexOf(self.Z) + 1)
        table.addColumn(self._af_btn_col, table.indexOf(self.AF) + 1)

        # when a new row is inserted, call _on_rows_inserted
        # to update the new values from the core position
        table.model().rowsInserted.connect(self._on_rows_inserted)

        # add move_to_selection to toolbar and link up callback
        toolbar = self.toolBar()
        action0 = next(x for x in toolbar.children() if isinstance(x, QWidgetAction))
        toolbar.insertWidget(action0, self.move_to_selection)
        table.itemSelectionChanged.connect(self._on_selection_change)

        # connect
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_config_loaded)
        self._mmc.events.propertyChanged.connect(self._on_property_changed)

        self.destroyed.connect(self._disconnect)

        self._on_sys_config_loaded()
        # hide the set-AF-offset button to begin with.
        self._on_af_per_position_toggled(self.af_per_position.isChecked())

    # ---------------------- public methods -----------------------

    def value(
        self, exclude_unchecked: bool = True, exclude_hidden_cols: bool = True
    ) -> tuple[Position, ...] | WellPlatePlan:
        """Return the current state of the positions table."""
        if self._plate_plan is not None:
            return self._plate_plan
        return super().value(exclude_unchecked, exclude_hidden_cols)

    def setValue(self, value: Sequence[Position] | WellPlatePlan) -> None:
        """Set the value of the positions table."""
        if isinstance(value, WellPlatePlan):
            self._plate_plan = value
            self._hcs.setValue(value)
            self._set_position_table_editable(False)
            value = tuple(value)
        super().setValue(value)

    # ----------------------- private methods -----------------------

    def _show_hcs(self) -> None:
        """Show or raise the HCS wizard."""
        self._hcs.raise_() if self._hcs.isVisible() else self._hcs.show()

    @property
    def _hcs(self) -> HCSWizard:
        """Get the HCS wizard, initializing it if it doesn't exist."""
        if self._hcs_wizard is None:
            self._hcs_wizard = HCSWizard(self)
            self._rename_hcs_position_button(ADD_POSITIONS)
            self._hcs_wizard.accepted.connect(self._on_hcs_accepted)
        return self._hcs_wizard

    def _on_hcs_accepted(self) -> None:
        """Add the positions from the HCS wizard to the stage positions."""
        self._plate_plan = self._hcs.value()
        if self._plate_plan is not None:
            # show a ovwerwrite warning dialog if the table is not empty
            if self.table().rowCount() > 0:
                dialog = QMessageBox(
                    QMessageBox.Icon.Warning,
                    "Overwrite Positions",
                    "This will replace the positions currently stored in the table."
                    "\nWould you like to proceed?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    self,
                )
                dialog.setDefaultButton(QMessageBox.StandardButton.Yes)
                if dialog.exec() != QMessageBox.StandardButton.Yes:
                    return
            self._update_table_positions(self._plate_plan)

    def _update_table_positions(self, plan: WellPlatePlan) -> None:
        """Update the table with the positions from the HCS wizard."""
        self.setValue(list(plan))
        self._set_position_table_editable(False)

    def _rename_hcs_position_button(self, text: str) -> None:
        if wiz := self._hcs_wizard:
            wiz.points_plan_page.setButtonText(QWizard.WizardButton.FinishButton, text)

    def _show_pos_editing_dialog(self) -> None:
        dialog = QMessageBox(
            QMessageBox.Icon.Warning,
            "Reset HCS",
            "Positions are currently autogenerated from the HCS Wizard."
            "\n\nWould you like to cast them to a list of stage positions?"
            "\n\nNOTE: you will no longer be able to edit them using the HCS Wizard "
            "widget.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            self,
        )
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        if dialog.exec() == QMessageBox.StandardButton.Yes:
            self._plate_plan = None
            self._set_position_table_editable(True)

    def _set_position_table_editable(self, state: bool) -> None:
        """Enable/disable the position table depending on the use of the HCS wizard."""
        self._edit_hcs_pos.setVisible(not state)
        self.include_z.setVisible(state)
        self.af_per_position.setVisible(state)

        # Hide or show all columns that are irrelevant when using the HCS wizard
        table = self.table()
        inc_z = self.include_z.isChecked()
        table.setColumnHidden(table.indexOf(self._xy_btn_col), not state)
        table.setColumnHidden(table.indexOf(self._z_btn_col), not state or not inc_z)
        table.setColumnHidden(table.indexOf(self.Z), not state or not inc_z)
        table.setColumnHidden(table.indexOf(self.SEQ), not state)

        # Enable or disable the toolbar
        for action in self.toolBar().actions()[1:]:
            action.setEnabled(state)

        self._enable_table_items(state)
        # connect/disconnect the double click event and rename the button
        if state:
            self._rename_hcs_position_button(ADD_POSITIONS)
            with suppress(RuntimeError):
                self.table().cellDoubleClicked.disconnect(self._show_pos_editing_dialog)
        else:
            self._rename_hcs_position_button(UPDATE_POSITIONS)
            # using UniqueConnection to avoid multiple connections
            # but catching the TypeError if the connection is already made
            with suppress(TypeError, RuntimeError):
                self.table().cellDoubleClicked.connect(
                    self._show_pos_editing_dialog, Qt.ConnectionType.UniqueConnection
                )

    def _enable_table_items(self, state: bool) -> None:
        """Enable or disable the table items depending on the use of the HCS wizard."""
        table = self.table()
        name_col = table.indexOf(self.NAME)
        x_col = table.indexOf(self.X)
        y_col = table.indexOf(self.Y)
        with signals_blocked(table):
            for row in range(table.rowCount()):
                table.cellWidget(row, x_col).setEnabled(state)
                table.cellWidget(row, y_col).setEnabled(state)
                # enable/disable the name cells
                name_item = table.item(row, name_col)
                flags = name_item.flags() | Qt.ItemFlag.ItemIsEnabled
                if state:
                    flags |= Qt.ItemFlag.ItemIsEditable
                else:
                    # keep the name column enabled but NOT editable. We do not disable
                    # to keep available the "Move Stage to Selected Point" option
                    flags &= ~Qt.ItemFlag.ItemIsEditable
                name_item.setFlags(flags)

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
            af_engaged = self._mmc.isContinuousFocusLocked()
            af_offset = self._mmc.getAutoFocusOffset() if af_engaged else None

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
                    self._mmc.enableContinuousFocus(False)
                    self._perform_autofocus()
                    self._mmc.enableContinuousFocus(af_engaged)
                    self._mmc.waitForSystem()
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
