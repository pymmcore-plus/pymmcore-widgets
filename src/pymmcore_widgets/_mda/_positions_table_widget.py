from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Sequence, cast

from pydantic import ValidationError
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QDoubleSpinBox,
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
from useq import (  # type: ignore
    AnyGridPlan,
    GridFromCorners,
    GridRelative,
    NoGrid,
    Position,
)
from useq._grid import Coordinate, GridPosition, OrderMode, RelativeTo

from ._grid_widget import GridWidget

if TYPE_CHECKING:
    from typing_extensions import Required, TypedDict

    class PositionDict(TypedDict, total=False):
        """Position dictionary."""

        x: float | None
        y: float | None
        z: float | None
        name: str | None

    class GridDict(TypedDict, total=False):
        """Grid dictionary."""

        overlap: Required[float | tuple[float, float]]
        order_mode: Required[OrderMode | str]
        rows: int
        cols: int
        relative_to: RelativeTo | str
        corner1: Coordinate
        corner2: Coordinate


GRID = "Grid"
POS = "Pos"
AlignCenter = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter


class PositionTable(QGroupBox):
    """Widget providing options for setting up a multi-position acquisition.

    The `value()` method returns a dictionary with the current state of the widget, in a
    format that matches one of the [useq-schema Position
    specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Position).
    """

    valueChanged = Signal()
    GRID_ROLE = QTableWidgetItem.ItemType.UserType + 1
    # POS_ROLE = QTableWidgetItem.ItemType.UserType + 1

    def __init__(
        self,
        title: str = "Stage Positions",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = CMMCorePlus.instance()

        self.setTitle(title)

        self.setCheckable(True)

        group_layout = QHBoxLayout()
        group_layout.setSpacing(15)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        # table
        self._table = QTableWidget()
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(hdr.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setTabKeyNavigation(True)
        self._table.setColumnCount(4)
        self._table.setRowCount(0)
        self._table.setHorizontalHeaderLabels(["Pos", "X", "Y", "Z"])
        group_layout.addWidget(self._table)

        # buttons
        wdg = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(layout)

        btn_sizepolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        min_size = 100
        self.add_button = QPushButton(text="Add")
        self.add_button.setMinimumWidth(min_size)
        self.add_button.setSizePolicy(btn_sizepolicy)
        self.remove_button = QPushButton(text="Remove")
        self.remove_button.setEnabled(False)
        self.remove_button.setMinimumWidth(min_size)
        self.remove_button.setSizePolicy(btn_sizepolicy)
        self.clear_button = QPushButton(text="Clear")
        self.clear_button.setMinimumWidth(min_size)
        self.clear_button.setSizePolicy(btn_sizepolicy)
        self.grid_button = QPushButton(text="Grid")
        self.grid_button.setMinimumWidth(min_size)
        self.grid_button.setSizePolicy(btn_sizepolicy)
        self.go_button = QPushButton(text="Go")
        self.go_button.setEnabled(False)
        self.go_button.setMinimumWidth(min_size)
        self.go_button.setSizePolicy(btn_sizepolicy)

        spacer = QSpacerItem(
            10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        layout.addWidget(self.add_button)
        layout.addWidget(self.remove_button)
        layout.addWidget(self.clear_button)
        layout.addWidget(self.grid_button)
        layout.addWidget(self.go_button)
        layout.addItem(spacer)

        group_layout.addWidget(wdg)

        self.add_button.clicked.connect(self._add_position)
        self.remove_button.clicked.connect(self._remove_position)
        self.clear_button.clicked.connect(self._clear_positions)
        self.grid_button.clicked.connect(self._grid_widget)
        self.go_button.clicked.connect(self._move_to_position)

        self._table.selectionModel().selectionChanged.connect(self._enable_go_button)
        self._table.selectionModel().selectionChanged.connect(
            self._enable_remove_button
        )

        self._table.itemChanged.connect(self._rename_positions)

        self._mmc.events.systemConfigurationLoaded.connect(self._clear_positions)

        self.destroyed.connect(self._disconnect)

    def _enable_go_button(self) -> None:
        rows = {r.row() for r in self._table.selectedIndexes()}
        self.go_button.setEnabled(len(rows) == 1)

    def _enable_remove_button(self) -> None:
        rows = {r.row() for r in self._table.selectedIndexes()}
        self.remove_button.setEnabled(len(rows) >= 1)

    def _add_position(self) -> None:

        if not self._mmc.getXYStageDevice() and not self._mmc.getFocusDevice():
            raise ValueError("No XY and Z Stage devices loaded.")

        name = f"Pos{self._table.rowCount():03d}"
        xpos = self._mmc.getXPosition() if self._mmc.getXYStageDevice() else None
        ypos = self._mmc.getYPosition() if self._mmc.getXYStageDevice() else None
        zpos = self._mmc.getZPosition() if self._mmc.getFocusDevice() else None
        self._add_table_row(name, xpos, ypos, zpos)
        self._rename_positions()

    def _add_table_row(
        self,
        name: str | None,
        xpos: float | None,
        ypos: float | None,
        zpos: float | None,
    ) -> None:

        if not self._mmc.getXYStageDevice() and not self._mmc.getFocusDevice():
            raise ValueError("No XY and Z Stage devices loaded.")

        row = self._add_position_row()

        self._add_table_item(name, row, 0)
        self._add_table_value(xpos, row, 1)
        self._add_table_value(ypos, row, 2)
        if zpos is None or not self._mmc.getFocusDevice():
            self.valueChanged.emit()
            return
        self._add_table_value(zpos, row, 3)

        self.valueChanged.emit()

    def _add_position_row(self) -> int:
        idx = self._table.rowCount()
        self._table.insertRow(idx)
        return cast(int, idx)

    def _add_table_item(self, table_item: str | None, row: int, col: int) -> None:
        item = QTableWidgetItem(table_item)
        item.setTextAlignment(AlignCenter)
        self._table.setItem(row, col, item)

    def _add_table_value(
        self, value: float | None, row: int | None, col: int | None
    ) -> None:
        if value is None or row is None or col is None:
            return
        spin = QDoubleSpinBox()
        spin.setAlignment(AlignCenter)
        spin.setMaximum(1000000.0)
        spin.setMinimum(-1000000.0)
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spin.setValue(value)
        # block mouse scroll
        spin.wheelEvent = lambda event: None
        self._table.setCellWidget(row, col, spin)

    def _remove_position(self) -> None:
        rows = {r.row() for r in self._table.selectedIndexes()}
        for idx in sorted(rows, reverse=True):
            self._table.removeRow(idx)
        self._rename_positions()
        self.valueChanged.emit()

    def _rename_positions(self) -> None:
        single_pos_count = 0
        grid_count = 0
        single_pos_rows: list[int] = []
        grid_rows: list[int] = []

        for row in range(self._table.rowCount()):
            if not self._has_default_name(self._table.item(row, 0).text()):
                continue

            if self._table.item(row, 0).data(self.GRID_ROLE):
                grid_number = self._update_number(grid_count, grid_rows)
                new_name = f"{GRID}{grid_number:03d}"
                grid_count = grid_number + 1
            else:
                pos_number = self._update_number(single_pos_count, single_pos_rows)
                new_name = f"{POS}{pos_number:03d}"
                single_pos_count = pos_number + 1

            self._table.item(row, 0).setText(new_name)

    def _has_default_name(self, name: str) -> bool:
        if POS in name or GRID in name:
            with contextlib.suppress(ValueError):
                int(name[-3:])
                return True
        return False

    def _update_table_item(
        self, name: str, row: int, col: int, update_name: bool = True
    ) -> None:
        if update_name:
            self._table.item(row, col).setText(name)
        self._table.item(row, col).setData(self.POS_ROLE, name)
        self._table.item(row, col).setToolTip(name)

    def _update_number(self, number: int, exixting_numbers: list[int]) -> int:
        loop = True
        while loop:
            if number in exixting_numbers:
                number += 1
            else:
                loop = False
        return number

    def _clear_positions(self) -> None:
        """clear all positions."""
        self._table.clearContents()
        self._table.setRowCount(0)
        self.valueChanged.emit()

    def _grid_widget(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        if not hasattr(self, "_grid_wdg"):
            self._grid_wdg = GridWidget(parent=self, mmcore=self._mmc)
            self._grid_wdg.valueChanged.connect(self._add_grid_positions_to_table)
        self._grid_wdg.show()
        self._grid_wdg.raise_()

    def _add_grid_positions_to_table(self, grid: GridDict, clear: bool) -> None:
        _, _, width, height = self._mmc.getROI(self._mmc.getCameraDevice())
        position_list = list(self._get_grid_type(grid).iter_grid_pos(width, height))

        if clear:
            self._clear_positions()

        grid_name = f"{GRID}{self._get_grid_number():03d}"
        z_pos = self._mmc.getZPosition() if self._mmc.getFocusDevice() else None

        self._add_table_row(grid_name, position_list[0].x, position_list[0].y, z_pos)

        row = self._table.rowCount() - 1
        self._table.item(row, 0).setData(self.GRID_ROLE, grid)
        tooltip = self._create_grid_tooltip(grid, position_list, z_pos)
        self._table.item(row, 0).setToolTip(tooltip)

        self.valueChanged.emit()

    def _get_grid_type(self, grid: GridDict) -> AnyGridPlan:
        try:
            grid_type = GridRelative(**grid)
        except ValidationError:
            try:
                grid_type = GridFromCorners(**grid)
            except ValidationError:
                grid_type = NoGrid()
        return grid_type

    def _get_grid_number(self) -> int:
        return sum(
            bool(
                self._table.item(r, 0).data(self.GRID_ROLE)
                and self._has_default_name(self._table.item(r, 0).text())
            )
            for r in range(self._table.rowCount())
        )

    def _create_grid_tooltip(
        self,
        grid: GridDict,
        position: list[GridPosition],
        z_pos: float | None = None,
    ) -> str:
        tooltip = (
            "GridRelative\n"
            if isinstance(self._get_grid_type(grid), GridRelative)
            else "GridFromCorners\n"
        )
        for idx, pos in enumerate(position):
            new_line = "" if idx + 1 == len(position) else "\n"
            tooltip = f"{tooltip}Pos{idx:03d}:  ({pos.x},  {pos.y},  {z_pos}){new_line}"
        return tooltip

    def _get_table_value(self, row: int, col: int | None) -> float | None:
        try:
            wdg = cast(QDoubleSpinBox, self._table.cellWidget(row, col))
            value = wdg.value()
        except (AttributeError, TypeError):
            value = None
        return value  # type: ignore

    def _move_to_position(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        curr_row = self._table.currentRow()
        x, y = (self._get_table_value(curr_row, 1), self._get_table_value(curr_row, 2))
        z = self._get_table_value(curr_row, 3)
        if x and y:
            self._mmc.setXYPosition(x, y)
        if self._mmc.getFocusDevice() and z:
            self._mmc.setPosition(z)

    def value(self) -> list[PositionDict | GridDict]:
        # TODO: update docstring
        """Return the current positions settings.

        Note that output dict will match the Positions from useq schema:
        <https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Position>
        """
        if not self._table.rowCount():
            return []

        values: list = []
        for row in range(self._table.rowCount()):
            if grid := self._table.item(row, 0).data(self.GRID_ROLE):
                values.append(grid)
            else:
                name = self._table.item(row, 0).text()
                x, y = (self._get_table_value(row, 1), self._get_table_value(row, 2))
                z = self._get_table_value(row, 3)
                values.append({"name": name, "x": x, "y": y, "z": z})

        return values

    def set_state(
        self, positions: Sequence[PositionDict | Position | GridDict | AnyGridPlan]
    ) -> None:
        """Set the state of the widget from a useq position dictionary."""
        self._clear_positions()

        if not isinstance(positions, Sequence):
            raise TypeError("The 'positions' arguments has to be a 'Sequence'.")

        if not self._mmc.getXYStageDevice() and not self._mmc.getFocusDevice():
            raise ValueError("No XY and Z Stage devices loaded.")

        pos_number = 0
        for position in positions:

            if isinstance(position, (Position, AnyGridPlan)):
                position = position.dict()

            grid = self._get_grid_type(position)
            if isinstance(grid, (GridRelative, GridFromCorners)):
                self._add_grid_positions_to_table(position, False)
            else:
                name = position.get("name")
                if not name:
                    name = f"{POS}{pos_number:03d}"
                    pos_number += 1
                self._add_table_row(
                    name, position.get("x"), position.get("y"), position.get("z")
                )
            self.valueChanged.emit()

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._clear_positions)
