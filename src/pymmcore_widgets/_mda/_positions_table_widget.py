from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Sequence, cast
from uuid import UUID, uuid4

from pydantic import ValidationError
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked
from useq import (  # type: ignore
    AnyGridPlan,
    GridFromEdges,
    GridRelative,
    MDASequence,
    NoGrid,
    Position,
)
from useq._grid import GridPosition, OrderMode, RelativeTo

from ._grid_widget import GridWidget

if TYPE_CHECKING:
    from typing_extensions import Required, TypedDict

    class PositionDict(TypedDict, total=False):
        """Position dictionary."""

        x: float | None
        y: float | None
        z: float | None
        name: str | None
        sequence: MDASequence | None

    class GridDict(TypedDict, total=False):
        """Grid dictionary."""

        overlap: Required[float | tuple[float, float]]
        mode: Required[OrderMode | str]
        rows: int
        columns: int
        relative_to: RelativeTo | str
        top: float
        left: float
        bottom: float
        right: float


POS = "Pos"
AlignCenter = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter


class PositionTable(QGroupBox):
    """Widget providing options for setting up a multi-position acquisition.

    The `value()` method returns a dictionary with the current state of the widget, in a
    format that matches one of the [useq-schema Position
    specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Position).

    When using the [GridWidget](), a list of stage positions will be added to
    the table with a default name in the form:
    "position_row_column_acquisition-order-index" (e.g. "Pos000_000_000_0",
    "Pos000_000_001_1", ...)
    """

    valueChanged = Signal()
    GRID_ROLE = QTableWidgetItem.ItemType.UserType + 1

    def __init__(
        self,
        title: str = "Stage Positions",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = CMMCorePlus.instance()

        self.setTitle(title)

        self.setCheckable(True)

        group_layout = QGridLayout()
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
        group_layout.addWidget(self._table, 0, 0)

        # buttons
        buttons_wdg = QWidget()
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(10)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_wdg.setLayout(buttons_layout)

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
        self.grid_button = QPushButton(text="Grids")
        self.grid_button.setMinimumWidth(min_size)
        self.grid_button.setSizePolicy(btn_sizepolicy)
        self.go_button = QPushButton(text="Go")
        self.go_button.setEnabled(False)
        self.go_button.setMinimumWidth(min_size)
        self.go_button.setSizePolicy(btn_sizepolicy)

        spacer = QSpacerItem(
            10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        buttons_layout.addWidget(self.add_button)
        buttons_layout.addWidget(self.remove_button)
        buttons_layout.addWidget(self.clear_button)
        buttons_layout.addWidget(self.go_button)
        buttons_layout.addWidget(self.grid_button)
        buttons_layout.addItem(spacer)

        group_layout.addWidget(buttons_wdg, 0, 1)

        self.add_button.clicked.connect(self._add_position)
        self.remove_button.clicked.connect(self._remove_position)
        self.clear_button.clicked.connect(self.clear)
        self.grid_button.clicked.connect(self._grid_widget)
        self.go_button.clicked.connect(self._move_to_position)

        self._table.selectionModel().selectionChanged.connect(self._enable_go_button)
        self._table.selectionModel().selectionChanged.connect(
            self._enable_remove_button
        )
        self._table.selectionModel().selectionChanged.connect(
            self._select_all_grid_positions
        )

        self._table.itemChanged.connect(self._rename_positions)

        self._mmc.events.systemConfigurationLoaded.connect(self.clear)

        self.destroyed.connect(self._disconnect)

    def _create_spin_with_label(
        self, label: str, spin: QSpinBox | QDoubleSpinBox
    ) -> QWidget:
        wdg = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        wdg.setLayout(layout)
        _label = QLabel(text=label)
        _label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        spin.setMaximum(100)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(_label)
        layout.addWidget(spin)
        return wdg

    def _create_combo_with_label(
        self, label: str, combo: QComboBox, items: list
    ) -> QWidget:
        wdg = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(layout)
        lbl = QLabel(label)
        lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        combo.addItems(items)
        layout.addWidget(lbl)
        layout.addWidget(combo)
        return wdg

    def _enable_go_button(self) -> None:
        rows = {r.row() for r in self._table.selectedIndexes()}
        self.go_button.setEnabled(len(rows) == 1)

    def _enable_remove_button(self) -> None:
        rows = {r.row() for r in self._table.selectedIndexes()}
        self.remove_button.setEnabled(len(rows) >= 1)

    def _select_all_grid_positions(self) -> None:
        """Select all grid positions from the same 'Gridnnn'."""
        rows = {r.row() for r in self._table.selectedIndexes()}

        # get grids id
        _ids = [
            self._table.item(row, 0).data(self.GRID_ROLE)[0]
            for row in rows
            if self._table.item(row, 0).data(self.GRID_ROLE)
        ]

        # select all positions from the same grid
        # activate MultiSelection
        self._table.setSelectionMode(QAbstractItemView.MultiSelection)
        for row in range(self._table.rowCount()):
            role = self._table.item(row, 0).data(self.GRID_ROLE)
            if (
                role
                and role[0] in _ids
                and not self._table.selectionModel().isRowSelected(row)
            ):
                self._table.selectRow(row)
        # revert back to ExtendedSelection
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)

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
        spin.wheelEvent = lambda event: None  # block mouse scroll
        self._table.setCellWidget(row, col, spin)

    def _remove_position(self) -> None:
        rows = {r.row() for r in self._table.selectedIndexes()}
        grids_id = []
        for r in sorted(rows, reverse=True):
            if data := self._table.item(r, 0).data(self.GRID_ROLE):
                grids_id.append(data[0])
            self._table.removeRow(r)

        for row in reversed(range(self._table.rowCount())):
            grid_role = self._table.item(row, 0).data(self.GRID_ROLE)
            if grid_role and grid_role[0] in grids_id:
                self._table.removeRow(row)

        self._rename_positions()
        self.valueChanged.emit()

    def _rename_positions(self) -> None:
        pos_count = 0
        pos_rows: list[int] = []
        grid_rows: list[int] = []

        grid_row_list = self._get_same_grid_rows()

        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)

            if not self._has_default_name(item.text()):
                continue

            pos_number = self._update_number(pos_count, pos_rows)

            if item.data(self.GRID_ROLE):
                _id = item.data(self.GRID_ROLE)[0]
                if row in grid_rows:
                    continue
                for r in grid_row_list[_id]:
                    grid_item = self._table.item(r, 0)
                    if not self._has_default_name(grid_item.text()):
                        continue
                    new_name = f"{POS}{pos_number:03d}{grid_item.text()[6:]}"
                    with signals_blocked(self._table):
                        grid_item.setText(new_name)
                    grid_rows.append(r)
                pos_count = pos_number + 1
            else:
                new_name = f"{POS}{pos_number:03d}{item.text()[6:]}"
                pos_count = pos_number + 1
                with signals_blocked(self._table):
                    item.setText(new_name)

    def _get_same_grid_rows(self) -> dict[UUID, list[int]]:
        grids: dict[UUID, list[int]] = {}
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)

            if not item.data(self.GRID_ROLE):
                continue

            _id = item.data(self.GRID_ROLE)[0]
            if grids.get(_id):
                grids[_id].append(row)
            else:
                grids[_id] = [row]
        return grids

    def _has_default_name(self, name: str) -> bool:
        with contextlib.suppress(ValueError):
            int(name[3:6])
            return True
        return False

    def _update_number(self, number: int, exixting_numbers: list[int]) -> int:
        loop = True
        while loop:
            if number in exixting_numbers:
                number += 1
            else:
                loop = False
        return number

    def clear(self) -> None:
        """clear all positions."""
        self._table.clearContents()
        self._table.setRowCount(0)
        self.valueChanged.emit()

    def _grid_widget(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        if not hasattr(self, "_grid_wdg"):
            self._grid_wdg = GridWidget(parent=self, mmcore=self._mmc)
            self._grid_wdg.valueChanged.connect(self._add_grid_position)
        self._grid_wdg.show()
        self._grid_wdg.raise_()

    def _add_grid_position(
        self,
        grid: GridDict,
        name: str | None = None,
        xpos: float | None = None,
        ypos: float | None = None,
        zpos: float | None = None,
    ) -> None:
        grid_type = self._get_grid_type(grid)

        if isinstance(grid_type, NoGrid):
            return

        _, _, width, height = self._mmc.getROI(self._mmc.getCameraDevice())
        position_list = list(grid_type.iter_grid_positions(width, height))

        if isinstance(grid_type, GridRelative):
            xpos = self._mmc.getXPosition() if xpos is None else xpos
            ypos = self._mmc.getYPosition() if ypos is None else ypos
            position_list = [
                GridPosition(
                    x=xpos + p.x,
                    y=ypos + p.y,
                    row=p.row,
                    col=p.col,
                    is_relative=p.is_relative,
                )
                for p in position_list
            ]

        name = name or f"{POS}000"
        z_pos = zpos or self._mmc.getZPosition() if self._mmc.getFocusDevice() else None
        _id = uuid4()
        for idx, pos in enumerate(position_list):
            x_pos, y_pos, row, col, _ = pos
            with signals_blocked(self._table):
                self._add_table_row(
                    f"{name}_{row:03d}_{col:03d}_{idx}", x_pos, y_pos, z_pos
                )
                row = self._table.rowCount() - 1
                self._table.item(row, 0).setData(
                    self.GRID_ROLE, (_id, grid, grid_type, xpos, ypos, z_pos)
                )
                self._table.item(row, 0).setToolTip(str(grid_type))

        self._rename_positions()

        self.valueChanged.emit()

    def _get_grid_type(self, grid: GridDict | AnyGridPlan) -> AnyGridPlan:
        if isinstance(grid, AnyGridPlan):
            grid = grid.dict()
        try:
            grid_type = GridRelative(**grid)
        except ValidationError:
            try:
                grid_type = GridFromEdges(**grid)
            except ValidationError:
                grid_type = NoGrid()
        return grid_type

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

    def _get_table_value(self, row: int, col: int | None) -> float | None:
        try:
            wdg = cast(QDoubleSpinBox, self._table.cellWidget(row, col))
            value = wdg.value()
        except (AttributeError, TypeError):
            value = None
        return value  # type: ignore

    def value(self) -> list[PositionDict]:
        # TODO: update docstring
        """Return the current positions settings.

        Note that output dict will match the Positions from useq schema:
        <https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Position>
        """
        if not self._table.rowCount():
            return []

        grids = self._get_same_grid_rows()
        grids_rows: list[int] = []
        values: list = []
        for row in range(self._table.rowCount()):
            name = self._table.item(row, 0).text()

            if grid_role := self._table.item(row, 0).data(self.GRID_ROLE):

                if row in grids_rows:
                    continue

                _id, grid, _, xpos, ypos, zpos = grid_role
                values.append(
                    {
                        "name": name[:6] if self._has_default_name(name) else name,
                        "x": xpos,
                        "y": ypos,
                        "z": zpos,
                        "sequence": MDASequence(grid_plan=grid),
                    }
                )
                grids_rows.extend(grids[_id])

            else:
                x, y = (self._get_table_value(row, 1), self._get_table_value(row, 2))
                z = self._get_table_value(row, 3)
                values.append({"name": name, "x": x, "y": y, "z": z})

        return values

    def set_state(self, positions: Sequence[PositionDict | Position]) -> None:
        """Set the state of the widget from a useq position dictionary."""
        self.clear()
        self.setChecked(True)

        if not isinstance(positions, Sequence):
            raise TypeError("The 'positions' arguments has to be a 'Sequence'.")

        if not self._mmc.getXYStageDevice() and not self._mmc.getFocusDevice():
            raise ValueError("No XY and Z Stage devices loaded.")

        for position in positions:

            if isinstance(position, Position):
                position = position.dict()  # type: ignore

            if not isinstance(position, dict):
                continue

            name = position.get("name")
            pos_seq = position.get("sequence")

            if pos_seq and pos_seq.grid_plan:  # type: ignore
                grid_type = self._get_grid_type(pos_seq.grid_plan)  # type: ignore
                if not isinstance(grid_type, NoGrid):
                    self._add_grid_position(
                        pos_seq.grid_plan.dict(),  # type: ignore
                        name,
                        position.get("x"),
                        position.get("x"),
                        position.get("z"),
                    )
            else:
                x, y, z = (position.get("x"), position.get("y"), position.get("z"))
                self._add_table_row(name or f"{POS}000", x, y, z)

            self.valueChanged.emit()

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self.clear)
