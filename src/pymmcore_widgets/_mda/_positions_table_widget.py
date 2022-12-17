from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, cast

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ._grid_widget import GridWidget

if TYPE_CHECKING:
    from typing_extensions import TypedDict

    class PositionDict(TypedDict, total=False):
        """Position dictionary."""

        x: float | None
        y: float | None
        z: float | None
        name: str | None


AlignCenter = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter


class PositionTable(QGroupBox):
    """Widget providing options for setting up a multi-position acquisition.

    The `value()` method returns a dictionary with the current state of the widget, in a
    format that matches one of the [useq-schema Position
    specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Position).
    """

    valueChanged = Signal()

    def __init__(
        self,
        title: str = "Stage Positions",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = CMMCorePlus.instance()

        self.setTitle(title)

        self.setCheckable(True)
        self.setChecked(False)

        group_layout = QHBoxLayout()
        group_layout.setSpacing(15)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        # table
        self.stage_tableWidget = QTableWidget()
        self.stage_tableWidget.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        hdr = self.stage_tableWidget.horizontalHeader()
        hdr.setSectionResizeMode(hdr.ResizeMode.Stretch)
        self.stage_tableWidget.verticalHeader().setVisible(False)
        self.stage_tableWidget.setTabKeyNavigation(True)
        self.stage_tableWidget.setColumnCount(4)
        self.stage_tableWidget.setRowCount(0)
        self.stage_tableWidget.setHorizontalHeaderLabels(["Pos", "X", "Y", "Z"])
        group_layout.addWidget(self.stage_tableWidget)

        # buttons
        wdg = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(layout)

        btn_sizepolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        min_size = 100
        self.add_pos_button = QPushButton(text="Add")
        self.add_pos_button.setMinimumWidth(min_size)
        self.add_pos_button.setSizePolicy(btn_sizepolicy)
        self.remove_pos_button = QPushButton(text="Remove")
        self.remove_pos_button.setMinimumWidth(min_size)
        self.remove_pos_button.setSizePolicy(btn_sizepolicy)
        self.clear_pos_button = QPushButton(text="Clear")
        self.clear_pos_button.setMinimumWidth(min_size)
        self.clear_pos_button.setSizePolicy(btn_sizepolicy)
        self.grid_button = QPushButton(text="Grid")
        self.grid_button.setMinimumWidth(min_size)
        self.grid_button.setSizePolicy(btn_sizepolicy)
        self.go_button = QPushButton(text="Go")
        self.go_button.setMinimumWidth(min_size)
        self.go_button.setSizePolicy(btn_sizepolicy)

        spacer = QSpacerItem(
            10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        layout.addWidget(self.add_pos_button)
        layout.addWidget(self.remove_pos_button)
        layout.addWidget(self.clear_pos_button)
        layout.addWidget(self.grid_button)
        layout.addWidget(self.go_button)
        layout.addItem(spacer)

        group_layout.addWidget(wdg)

        self.add_pos_button.clicked.connect(self._add_position)
        self.remove_pos_button.clicked.connect(self._remove_position)
        self.clear_pos_button.clicked.connect(self._clear_positions)
        self.grid_button.clicked.connect(self._grid_widget)
        self.go_button.clicked.connect(self._move_to_position)

        self.stage_tableWidget.selectionModel().selectionChanged.connect(
            self._enable_go_button
        )

        self._mmc.events.systemConfigurationLoaded.connect(self._clear_positions)

        self.destroyed.connect(self._disconnect)

    def _enable_go_button(self) -> None:
        rows = {r.row() for r in self.stage_tableWidget.selectedIndexes()}
        self.go_button.setEnabled(len(rows) == 1)

    def _add_position(self) -> None:

        if not self._mmc.getXYStageDevice():
            raise ValueError("No XY Stage device loaded.")

        count = self.stage_tableWidget.rowCount() - 1
        name = f"Pos{count:03d}"
        xpos = str(self._mmc.getXPosition())
        ypos = str(self._mmc.getXPosition())
        if self._mmc.getFocusDevice():
            zpos = str(self._mmc.getZPosition())

        self._create_new_row(name, xpos, ypos, zpos)

        self._rename_positions(["Pos"])

    def _create_new_row(
        self, name: str | None, xpos: str | None, ypos: str | None, zpos: str | None
    ) -> None:

        if not self._mmc.getXYStageDevice():
            raise ValueError("No XY Stage device loaded.")

        row = self._add_position_row()

        self._add_table_item(name, row, 0, True)
        self._add_table_item(xpos, row, 1)
        self._add_table_item(ypos, row, 2)
        if zpos is None or not self._mmc.getFocusDevice():
            self.valueChanged.emit()
            return
        self._add_table_item(zpos, row, 3)

        self.valueChanged.emit()

    def _add_position_row(self) -> int:
        idx = self.stage_tableWidget.rowCount()
        self.stage_tableWidget.insertRow(idx)
        return cast(int, idx)

    def _add_table_item(
        self, table_item: str | None, row: int, col: int, whatsthis: bool = False
    ) -> None:
        item = QTableWidgetItem(table_item)
        if whatsthis:
            item.setWhatsThis(table_item)
        item.setTextAlignment(AlignCenter)
        self.stage_tableWidget.setItem(row, col, item)

    def _remove_position(self) -> None:

        rows = {r.row() for r in self.stage_tableWidget.selectedIndexes()}
        removed = []
        grid_to_delete = []

        for idx in sorted(rows, reverse=True):

            whatsthis = self.stage_tableWidget.item(idx, 0).whatsThis()
            if "Grid" in whatsthis:
                grid_name = whatsthis.split("_")[0]
                grid_to_delete.append(grid_name)

            else:
                name = self.stage_tableWidget.item(idx, 0).text().split("_")[0]

                if "Pos" in name:
                    if "Pos" not in removed:
                        removed.append("Pos")

                elif name not in removed:
                    removed.append(name)

                self.stage_tableWidget.removeRow(idx)

        for gridname in grid_to_delete:
            self._delete_grid_positions(gridname)

        self._rename_positions(removed)
        self.valueChanged.emit()

    def _delete_grid_positions(self, name: list[str]) -> None:
        """Remove all positions related to the same grid."""
        for row in reversed(range(self.stage_tableWidget.rowCount())):
            if name in self.stage_tableWidget.item(row, 0).whatsThis():
                self.stage_tableWidget.removeRow(row)

    def _rename_positions(self, names: list) -> None:
        for _ in names:
            pos_count = 0
            for r in range(self.stage_tableWidget.rowCount()):
                name = self.stage_tableWidget.item(r, 0).text()
                if "Grid" in name or "Pos" not in name:
                    continue
                new_name = f"Pos{pos_count:03d}"
                pos_count += 1
                self._add_table_item(new_name, r, 0)

    def _clear_positions(self) -> None:
        """clear all positions."""
        self.stage_tableWidget.clearContents()
        self.stage_tableWidget.setRowCount(0)
        self.valueChanged.emit()

    def _grid_widget(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        if not hasattr(self, "_grid_wdg"):
            self._grid_wdg = GridWidget(parent=self)
            self._grid_wdg.sendPosList.connect(self._add_grid_positions_to_table)
        self._grid_wdg.show()
        self._grid_wdg.raise_()

    def _add_grid_positions_to_table(self, position_list: list, clear: bool) -> None:

        grid_number = 0

        if clear:
            self._clear_positions()
        else:
            for r in range(self.stage_tableWidget.rowCount()):
                pos_name = self.stage_tableWidget.item(r, 0).whatsThis()
                grid_name = pos_name.split("_")[0]
                if "Grid" in grid_name:
                    grid_n = grid_name[-3:]
                    if int(grid_n) > grid_number:
                        grid_number = int(grid_n)
            grid_number += 1

        for idx, position in enumerate(position_list):
            name = f"Grid{grid_number:03d}_Pos{idx:03d}"
            if len(position) == 3:
                x, y, z = position
            else:
                x, y = position
                z = None

            self._create_new_row(name, str(x), str(y), str(z))

    def _move_to_position(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        curr_row = self.stage_tableWidget.currentRow()
        self._mmc.setXYPosition(
            self.value()[curr_row].get("x"), self.value()[curr_row].get("y")
        )
        if self._mmc.getFocusDevice() and self.value()[curr_row].get("z"):
            self._mmc.setPosition(self.value()[curr_row].get("z"))

    def value(self) -> list[PositionDict]:
        """Return the current positions settings.

        Note that output dict will match the Positions from useq schema:
        <https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Position>
        """
        values: list[PositionDict] = []
        for row in range(self.stage_tableWidget.rowCount()):
            z_text = self.stage_tableWidget.item(row, 3).text()
            z = float(z_text) if z_text else None
            values.append(
                {
                    "name": self.stage_tableWidget.item(row, 0).text(),
                    "x": float(self.stage_tableWidget.item(row, 1).text()),
                    "y": float(self.stage_tableWidget.item(row, 2).text()),
                    "z": z,
                }
            )
        return values

    # note: this should to be PositionDict, but it makes typing elsewhere harder
    def set_state(self, positions: list[dict]) -> None:
        """Set the state of the widget from a useq position dictionary."""
        self._clear_positions()

        if not self._mmc.getXYStageDevice():
            raise ValueError("No XY Stage device loaded.")

        self.setChecked(True)

        for idx, pos in enumerate(positions):
            name = pos.get("name") or f"Pos{idx:03d}"
            x = pos.get("x")
            y = pos.get("y")
            z = pos.get("z")

            if x is None or y is None:
                continue

            if z and not self._mmc.getFocusDevice():
                warnings.warn("No Focus device loaded.")

            self._add_position_row()

            self._add_table_item(name, idx, 0)
            self._add_table_item(str(x), idx, 1)
            self._add_table_item(str(y), idx, 2)
            if z is None or not self._mmc.getFocusDevice():
                continue
            self._add_table_item(str(z), idx, 3)

        self.valueChanged.emit()

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._clear_positions)
