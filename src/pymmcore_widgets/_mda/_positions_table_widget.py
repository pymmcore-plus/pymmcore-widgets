from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Sequence, cast

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
        top: float  # top_left y
        left: float  # top_left x
        bottom: float  # bottom_right y
        right: float  # bottom_right x


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
        self.clear_button.clicked.connect(self._clear_positions)
        self.grid_button.clicked.connect(self._grid_widget)
        self.go_button.clicked.connect(self._move_to_position)

        self.grid_groupbox = QGroupBox("Rows x Columns")
        self.grid_groupbox.setCheckable(True)
        self.grid_groupbox.setChecked(False)
        grid_group_layout = QGridLayout()
        grid_group_layout.setSpacing(10)
        grid_group_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_groupbox.setLayout(grid_group_layout)
        # rows and cols
        self._rows = QSpinBox()
        self._rows.setMinimum(1)
        rows_wdg = self._create_spin_with_label("Rows:", self._rows)
        self._cols = QSpinBox()
        self._cols.setMinimum(1)
        cols_wdg = self._create_spin_with_label("Columns:", self._cols)
        cols_label = cols_wdg.layout().itemAt(0).widget()
        rows_wdg.layout().itemAt(0).widget().setMinimumWidth(
            cols_label.sizeHint().width()
        )
        grid_group_layout.addWidget(rows_wdg, 0, 0)
        grid_group_layout.addWidget(cols_wdg, 1, 0)
        # overlap
        self._overlap_x = QDoubleSpinBox()
        self._overlap_x.setMinimum(0.0)
        overlap_x_wdg = self._create_spin_with_label("Overlap x:", self._overlap_x)
        self._overlap_y = QDoubleSpinBox()
        self._overlap_y.setMinimum(0.0)
        overlap_y_wdg = self._create_spin_with_label("Overlap y:", self._overlap_y)
        grid_group_layout.addWidget(overlap_x_wdg, 0, 1)
        grid_group_layout.addWidget(overlap_y_wdg, 1, 1)
        # relative to and mode
        self.relative_to_combo = QComboBox()
        relative_wdg = self._create_combo_with_label(
            "Relative to:", self.relative_to_combo, [r.value for r in RelativeTo]
        )
        self.mode_combo = QComboBox()
        mode_wdg = self._create_combo_with_label(
            "Order mode:", self.mode_combo, [mode.value for mode in OrderMode]
        )
        self.mode_combo.setCurrentText("row_wise_snake")
        grid_group_layout.addWidget(relative_wdg, 2, 0)
        grid_group_layout.addWidget(mode_wdg, 2, 1)

        group_layout.addWidget(self.grid_groupbox, 1, 0, 1, 2)

        self._table.selectionModel().selectionChanged.connect(self._enable_go_button)
        self._table.selectionModel().selectionChanged.connect(
            self._enable_remove_button
        )

        self._table.itemChanged.connect(self._rename_positions)

        self._mmc.events.roiSet.connect(self._on_roi_set)
        self._mmc.events.systemConfigurationLoaded.connect(self._clear_positions)

        self.destroyed.connect(self._disconnect)

    def _on_roi_set(self, *args: Any) -> None:
        width, height = (args[-2], args[-1])
        # update grid tooltip with new camera ROI
        for row in range(self._table.rowCount()):
            grid_role = self._table.item(row, 0).data(self.GRID_ROLE)
            if not grid_role:
                continue
            _, grid, grid_type = grid_role
            position_list = list(grid_type.iter_grid_positions(width, height))
            z_pos = self._get_table_value(row, 3)
            tooltip = self._create_grid_tooltip(grid, position_list, z_pos)
            self._table.item(row, 0).setToolTip(tooltip)

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
        spin.wheelEvent = lambda event: None  # block mouse scroll
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
            self._grid_wdg.valueChanged.connect(self._add_grid_position)
        self._grid_wdg.show()
        self._grid_wdg.raise_()

    def _add_grid_position(self, grid: GridDict) -> None:
        grid_type = self._get_grid_type(grid)
        _, _, width, height = self._mmc.getROI(self._mmc.getCameraDevice())
        position_list = list(grid_type.iter_grid_positions(width, height))

        grid_number = f"{GRID}{self._get_grid_number():03d}"
        x_pos = (
            self._mmc.getXPosition()
            if isinstance(grid_type, GridRelative)
            else position_list[0].x
        )
        y_pos = (
            self._mmc.getYPosition()
            if isinstance(grid_type, GridRelative)
            else position_list[0].y
        )
        z_pos = self._mmc.getZPosition() if self._mmc.getFocusDevice() else None
        self._add_table_row(grid_number, x_pos, y_pos, z_pos)

        row = self._table.rowCount() - 1
        self._table.item(row, 0).setData(self.GRID_ROLE, (grid_number, grid, grid_type))
        tooltip = self._create_grid_tooltip(grid, position_list, z_pos)
        self._table.item(row, 0).setToolTip(tooltip)

        self.valueChanged.emit()

    def _get_grid_type(self, grid: GridDict) -> AnyGridPlan:
        try:
            grid_type = GridRelative(**grid)
        except ValidationError:
            try:
                grid_type = GridFromEdges(**grid)
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
            "GridRelative"
            if isinstance(self._get_grid_type(grid), GridRelative)
            else "GridFromEdges"
        )
        tooltip = f"{tooltip} - {grid['mode']}\n"
        for idx, pos in enumerate(position):
            new_line = "" if idx + 1 == len(position) else "\n"
            tooltip = f"{tooltip}Pos{idx:03d}:  ({pos.x},  {pos.y},  {z_pos}){new_line}"
        return tooltip

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

        values: list = []
        for row in range(self._table.rowCount()):

            name = self._table.item(row, 0).text()
            x, y = (self._get_table_value(row, 1), self._get_table_value(row, 2))
            z = self._get_table_value(row, 3)

            if grid_role := self._table.item(row, 0).data(self.GRID_ROLE):
                _, grid, grid_type = grid_role
                values.append(
                    {
                        "name": name,
                        "x": x if isinstance(grid_type, GridRelative) else None,
                        "y": y if isinstance(grid_type, GridRelative) else None,
                        "z": z,
                        "sequence": MDASequence(grid_plan=grid),
                    }
                )
            else:
                values.append({"name": name, "x": x, "y": y, "z": z})

        return values

    def grid_value(self) -> GridDict:
        """Return the current general GridRelative settings."""
        value: GridDict = {"overlap": (0.0, 0.0), "mode": "row_wise"}

        if self.grid_groupbox.isChecked():
            value["overlap"] = (self._overlap_x.value(), self._overlap_y.value())
            value["mode"] = self.mode_combo.currentText()
            value["rows"] = self._rows.value()
            value["columns"] = self._cols.value()
            value["relative_to"] = self.relative_to_combo.currentText()

        return value

    def set_state(
        self, positions: Sequence[PositionDict | Position | GridDict | GridRelative]
    ) -> None:
        """Set the state of the widget from a useq position dictionary."""
        self._clear_positions()
        self.setChecked(True)

        if not isinstance(positions, Sequence):
            raise TypeError("The 'positions' arguments has to be a 'Sequence'.")

        if not self._mmc.getXYStageDevice() and not self._mmc.getFocusDevice():
            raise ValueError("No XY and Z Stage devices loaded.")

        for row, position in enumerate(positions):

            if isinstance(position, GridRelative):
                self._set_grid_groupbox_state(position)
                self.valueChanged.emit()
                continue

            if isinstance(position, dict):
                with contextlib.suppress(ValidationError):
                    self._set_grid_groupbox_state(GridRelative(**position))
                    self.valueChanged.emit()
                    continue

            if isinstance(position, Position):
                position = position.dict()

            name = position.get("name")
            x, y, z = (position.get("x"), position.get("y"), position.get("z"))

            pos_seq = position.get("sequence")

            # at the moment only grid_plan will be considered
            if pos_seq and not isinstance(pos_seq.grid_plan, NoGrid):
                self._add_grid_position(pos_seq.grid_plan.dict())
                if name:
                    self._table.item(row, 0).setText(name)
                self._add_table_value(x, row, 1)
                self._add_table_value(y, row, 2)
                self._add_table_value(z, row, 3)
            else:
                self._add_table_row(name or f"{POS}000", x, y, z)

            self.valueChanged.emit()

    def _set_grid_groupbox_state(self, values: GridRelative) -> None:
        self._rows.setValue(values.rows)
        self._cols.setValue(values.columns)
        self._overlap_x.setValue(values.overlap[0])
        self._overlap_y.setValue(values.overlap[1])
        self.mode_combo.setCurrentText(values.mode.value)
        self.relative_to_combo.setCurrentText(values.relative_to.value)
        self.grid_groupbox.setChecked(True)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._clear_positions)
        self._mmc.events.roiSet.disconnect(self._on_roi_set)
