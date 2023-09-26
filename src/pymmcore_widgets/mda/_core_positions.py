from __future__ import annotations

from typing import TYPE_CHECKING

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
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
        self.table().addColumn(self._xy_btn_col, self.table().indexOf(self.X))
        self.table().addColumn(self._z_btn_col, self.table().indexOf(self.Z) + 1)

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

    def _on_sys_config_loaded(self) -> None:
        """Update the table when the system configuration is loaded."""
        self._enable_xy()
        self._enable_z()

    def _enable_xy(self) -> None:
        """Enable/disable the XY columns and button."""
        xy_device = self._mmc.getXYStageDevice()
        x_col = self.table().indexOf(self.X)
        y_col = self.table().indexOf(self.Y)
        self.table().setColumnHidden(x_col, not bool(xy_device))
        self.table().setColumnHidden(y_col, not bool(xy_device))
        xy_btn_col = self.table().indexOf(self._xy_btn_col)
        self.table().setColumnHidden(xy_btn_col, not bool(xy_device))

    def _enable_z(self) -> None:
        """Enable/disable the Z columns and button."""
        z_device = self._mmc.getFocusDevice()
        self.include_z.setChecked(bool(z_device))
        self.include_z.setEnabled(bool(z_device))
        self.include_z.setToolTip("" if z_device else "No Focus device selected.")

    def _on_property_changed(self, device: str, prop: str, value: str) -> None:
        """Update the autofocus device combo box when the autofocus device changes."""
        if device != "Core" or prop not in {"XYStage", "Focus"}:
            return
        if prop == "XYStage":
            self._enable_xy()
        elif prop == "Focus":
            self._enable_z()

    def _add_row(self) -> None:
        """Add a new to the end of the table."""
        super()._add_row()
        row = self.table().rowCount() - 1
        if self._mmc.getXYStageDevice():
            self._set_xy_from_core(row, self.table().indexOf(self.X))
        if self._mmc.getFocusDevice():
            self._set_z_from_core(row, self.table().indexOf(self.Z))

    def _set_xy_from_core(self, row: int, col: int = 0) -> None:
        data = {
            self.X.key: self._mmc.getXPosition(),
            self.Y.key: self._mmc.getYPosition(),
        }
        self.table().setRowData(row, data)

    def _set_z_from_core(self, row: int, col: int = 0) -> None:
        data = {self.Z.key: self._mmc.getPosition(self._mmc.getFocusDevice())}
        self.table().setRowData(row, data)

    def _on_selection_change(self) -> None:
        if not self.move_to_selection.isChecked():
            return

        if not self._mmc.getXYStageDevice() and not self._mmc.getFocusDevice():
            return

        selected_rows: set[int] = {i.row() for i in self.table().selectedItems()}
        if len(selected_rows) == 1:
            row = next(iter(selected_rows))
            data = self.table().rowData(row)

            if self._mmc.getXYStageDevice():
                x = data.get(self.X.key, self._mmc.getXPosition())
                y = data.get(self.Y.key, self._mmc.getYPosition())
                self._mmc.setXYPosition(x, y)

            if self._mmc.getFocusDevice():
                z = data.get(self.Z.key, self._mmc.getZPosition())
                self._mmc.setZPosition(z)

            self._mmc.waitForSystem()

    def _on_include_z_toggled(self, checked: bool) -> None:
        super()._on_include_z_toggled(checked)
        z_btn_col = self.table().indexOf(self._z_btn_col)
        self.table().setColumnHidden(z_btn_col, not checked)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(
            self._on_sys_config_loaded
        )
        self._mmc.events.propertyChanged.disconnect(self._on_property_changed)
