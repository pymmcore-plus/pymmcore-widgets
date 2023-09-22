from __future__ import annotations

import logging
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
        """Move stage to (single) selected row if move_to_selection enabled."""
        if not self.move_to_selection.isChecked():
            return

        selected_rows: set[int] = {i.row() for i in self.table().selectedItems()}
        if len(selected_rows) == 1:
            row = next(iter(selected_rows))
            data = self.table().rowData(row)
            x = data.get(self.X.key, self._mmc.getXPosition())
            y = data.get(self.Y.key, self._mmc.getYPosition())
            z = data.get(self.Z.key, self._mmc.getZPosition())
            try:
                self._mmc.setXYPosition(x, y)
                self._mmc.setZPosition(z)
            except RuntimeError:
                logging.error("Failed to move stage to selected position.")
            self._mmc.waitForSystem()

    def _on_include_z_toggled(self, checked: bool) -> None:
        super()._on_include_z_toggled(checked)
        z_btn_col = self.table().indexOf(self._z_btn_col)
        self.table().setColumnHidden(z_btn_col, not checked)
