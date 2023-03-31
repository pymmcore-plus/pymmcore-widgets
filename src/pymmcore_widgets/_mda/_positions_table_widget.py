from __future__ import annotations

import warnings
from itertools import groupby
from typing import TYPE_CHECKING, cast

from pymmcore_plus import CMMCorePlus, DeviceType
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked

from ._grid_widget import GridWidget

if TYPE_CHECKING:
    from typing_extensions import TypedDict

    class PositionDict(TypedDict, total=False):
        """Position dictionary."""

        x: float | None
        y: float | None
        z: float | None
        name: str | None


POS = "Pos"
AlignCenter = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter


class PositionTable(QGroupBox):
    """Widget providing options for setting up a multi-position acquisition.

    The `value()` method returns a dictionary with the current state of the widget, in a
    format that matches one of the [useq-schema Position
    specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Position).
    """

    valueChanged = Signal()
    POS_ROLE = QTableWidgetItem.ItemType.UserType + 1

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
        group_layout.addWidget(self._table, 0, 0)

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

        group_layout.addWidget(wdg, 0, 1)

        self.add_button.clicked.connect(self._add_position)
        self.remove_button.clicked.connect(self._remove_position)
        self.clear_button.clicked.connect(self._clear_positions)
        self.grid_button.clicked.connect(self._grid_widget)
        self.go_button.clicked.connect(self._move_to_position)

        self._table.selectionModel().selectionChanged.connect(self._enable_go_button)
        self._table.selectionModel().selectionChanged.connect(
            self._enable_remove_button
        )
        self._table.selectionModel().selectionChanged.connect(
            self._select_all_grid_positions
        )

        # bottom widget
        bottom_wdg = QWidget()
        bottom_wdg.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        bottom_wdg_layout = QHBoxLayout()
        bottom_wdg_layout.setSpacing(15)
        bottom_wdg_layout.setContentsMargins(0, 0, 0, 0)
        bottom_wdg.setLayout(bottom_wdg_layout)
        group_layout.addWidget(bottom_wdg, 1, 0, 1, 2)
        # z stage combo widget
        combo_wdg = QWidget()
        combo_wdg_layout = QHBoxLayout()
        combo_wdg_layout.setSpacing(5)
        combo_wdg_layout.setContentsMargins(0, 0, 0, 0)
        combo_wdg.setLayout(combo_wdg_layout)
        bottom_wdg_layout.addWidget(combo_wdg)
        # focus
        focus_lbl = QLabel("Z Focus:")
        focus_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.z_focus_combo = QComboBox()
        self.z_focus_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.z_focus_combo.currentTextChanged.connect(self._on_z_focus_changed)
        combo_wdg_layout.addWidget(focus_lbl)
        combo_wdg_layout.addWidget(self.z_focus_combo)
        spacer = QSpacerItem(15, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        combo_wdg_layout.addSpacerItem(spacer)
        # autofocus
        self.autofocus_lbl = QLabel("Z AutoFocus:")
        self.autofocus_lbl.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.z_autofocus_combo = QComboBox()
        self.z_autofocus_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.z_autofocus_combo.currentTextChanged.connect(self._on_z_autofocus_changed)
        self.autofocus_lbl.hide()
        self.z_autofocus_combo.hide()
        combo_wdg_layout.addWidget(self.autofocus_lbl)
        combo_wdg_layout.addWidget(self.z_autofocus_combo)

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.events.propertyChanged.connect(self._on_property_changed)

        self.destroyed.connect(self._disconnect)

        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:
        self._clear_positions()
        self._set_table_header()
        self._populate_combo()
        if self._mmc.getLoadedDevicesOfType(DeviceType.AutoFocus):
            self.autofocus_lbl.show()
            self.z_autofocus_combo.show()

    def _on_property_changed(self, device: str, prop: str, value: str) -> None:
        if device != "Core" or prop != "Focus":
            return

        if self.z_autofocus_combo.currentText() == "None":
            with signals_blocked(self.z_focus_combo):
                self.z_focus_combo.setCurrentText(value or "None")

        if (
            self.z_autofocus_combo.currentText() != "None"
            and value != self.z_autofocus_combo.currentText()
        ):
            with signals_blocked(self.z_autofocus_combo):
                self.z_autofocus_combo.setCurrentText(value)

        _range = (
            None
            if self._mmc.getLoadedDevicesOfType(DeviceType.XYStageDevice)
            else (0, self._table.columnCount() - 1)
        )
        if _range:
            for i in range(_range[0], _range[1]):
                if not value:
                    self._table.setColumnHidden(i, True)
                elif i == 0:
                    self._table.setColumnHidden(i, False)
                else:
                    col_name = self._table.horizontalHeaderItem(i).text()
                    self._table.setColumnHidden(i, col_name != value)

        else:
            self._table.setColumnHidden(3, not value)

    def _set_table_header(self) -> None:
        self._table.setColumnCount(0)

        if not self._mmc.getLoadedDevicesOfType(
            DeviceType.XYStageDevice
        ) and not self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice):
            self._clear_positions()
            return

        header = (
            [POS]
            + (
                ["X", "Y"]
                if self._mmc.getLoadedDevicesOfType(DeviceType.XYStageDevice)
                else []
            )
            + list(self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice))
        )

        self._table.setColumnCount(len(header))
        self._table.setHorizontalHeaderLabels(header)
        self._hide_header_columns(header)

    def _hide_header_columns(self, header: list[str]) -> None:
        for idx, c in enumerate(header):
            if c == POS and (
                not self._mmc.getLoadedDevicesOfType(DeviceType.XYStageDevice)
                and not self._mmc.getFocusDevice()
            ):
                self._table.setColumnHidden(idx, True)

            elif c in {"X", "Y"} and not self._mmc.getLoadedDevicesOfType(
                DeviceType.XYStageDevice
            ):
                self._table.setColumnHidden(idx, True)

            elif c not in {POS, "X", "Y"}:
                self._table.setColumnHidden(idx, self._mmc.getFocusDevice() != c)

    def _populate_combo(self) -> None:
        items = [
            "None",
            *list(self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice)),
        ]
        with signals_blocked(self.z_focus_combo):
            self.z_focus_combo.clear()
            self.z_focus_combo.addItems(items)
            self.z_focus_combo.setCurrentText(self._mmc.getFocusDevice() or "None")
        with signals_blocked(self.z_autofocus_combo):
            self.z_autofocus_combo.clear()
            self.z_autofocus_combo.addItems(items)
            self.z_autofocus_combo.setCurrentText("None")

    def _on_z_focus_changed(self, focus_stage: str) -> None:
        if self.z_autofocus_combo.currentText() != "None":
            return

        if focus_stage == "None":
            _range = (
                None
                if self._mmc.getLoadedDevicesOfType(DeviceType.XYStageDevice)
                else (0, self._table.columnCount() - 1)
            )
            if _range:
                for c in range(_range[0], _range[1]):
                    self._table.setColumnHidden(c, True)
            else:
                self._table.setColumnHidden(3, True)
            focus_stage = ""

        self._mmc.setFocusDevice(focus_stage)

    def _on_z_autofocus_changed(self, autofocus_stage: str) -> None:
        if autofocus_stage == "None":
            self._on_z_focus_changed(self.z_focus_combo.currentText())
        else:
            self._mmc.setFocusDevice(autofocus_stage)

    def _enable_go_button(self) -> None:
        rows = {r.row() for r in self._table.selectedIndexes()}
        self.go_button.setEnabled(len(rows) == 1)

    def _enable_remove_button(self) -> None:
        rows = {r.row() for r in self._table.selectedIndexes()}
        self.remove_button.setEnabled(len(rows) >= 1)

    def _select_all_grid_positions(self) -> None:
        """Select all grid positions from the same 'Gridnnn'."""
        rows = {r.row() for r in self._table.selectedIndexes()}

        # get all the grid selected in the table
        grid_to_select = []
        for row in rows:
            pos = self._table.item(row, 0).data(self.POS_ROLE).split("_")[0]
            if "Grid" not in pos:
                continue
            if pos not in grid_to_select:
                grid_to_select.append(pos)

        # select all positions from the same grid
        # activate MultiSelection
        self._table.setSelectionMode(QAbstractItemView.MultiSelection)
        for row in range(self._table.rowCount()):
            n_grid = self._table.item(row, 0).data(self.POS_ROLE).split("_")[0]
            if (
                n_grid in grid_to_select
                and not self._table.selectionModel().isRowSelected(row)
            ):
                with signals_blocked(self._table.selectionModel()):
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

        self._create_new_row(name, xpos, ypos, zpos)

        self._rename_positions()

    def _create_new_row(
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

    def _add_table_value(self, value: float | None, row: int, col: int) -> None:
        if value is None:
            return
        spin = QDoubleSpinBox()
        spin.setAlignment(AlignCenter)
        spin.setMaximum(1000000.0)
        spin.setMinimum(-1000000.0)
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spin.setValue(value)
        self._table.setCellWidget(row, col, spin)

    def _add_table_item(self, table_item: str | None, row: int, col: int) -> None:
        item = QTableWidgetItem(table_item)
        # data(self.POS_ROLE) is used to keep track of grid and/or position
        # even when the user changed the name in the table.
        item.setData(self.POS_ROLE, table_item)
        item.setToolTip(table_item)
        item.setTextAlignment(AlignCenter)
        self._table.setItem(row, col, item)

    def _remove_position(self) -> None:
        rows = {r.row() for r in self._table.selectedIndexes()}
        grid_to_delete = []

        for idx in sorted(rows, reverse=True):
            pos_role = self._table.item(idx, 0).data(self.POS_ROLE)
            # store grid name if is a grid position
            if "Grid" in pos_role:
                grid_name = pos_role.split("_")[0]
                grid_to_delete.append(grid_name)
            else:
                # remove if is a single position
                self._table.removeRow(idx)

        # remove grid positions
        for gridname in grid_to_delete:
            self._delete_grid_positions(gridname)

        self._rename_positions()
        self.valueChanged.emit()

    def _delete_grid_positions(self, name: list[str]) -> None:
        """Remove all positions related to the same grid."""
        for row in reversed(range(self._table.rowCount())):
            if name in self._table.item(row, 0).data(self.POS_ROLE):
                self._table.removeRow(row)

    def _rename_positions(self) -> None:
        single_pos_count = 0
        single_pos_rows: list[int] = []
        grid_info: list[tuple[str, str, int]] = []
        for row in range(self._table.rowCount()):
            name = self._table.item(row, 0).text()
            pos_role = self._table.item(row, 0).data(self.POS_ROLE)

            if "Grid" in pos_role.split("_")[0]:
                grid_info.append((name, pos_role, row))
                continue

            if name == pos_role:  # name = Posnnn and pos_role = Posnnn
                pos_number = self._update_number(single_pos_count, single_pos_rows)
                new_name = f"Pos{pos_number:03d}"
                single_pos_count = pos_number + 1
                self._update_table_item(new_name, row, 0)

            elif "Grid" not in pos_role:  # pos_role = Posnnn
                single_pos_rows.append(row)
                new_pos_role = f"Pos{row:03d}"
                self._update_table_item(new_pos_role, row, 0, False)

        if not grid_info:
            return

        self._rename_grid_positions(grid_info)

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

    def _rename_grid_positions(self, grid_info: list[tuple[str, str, int]]) -> None:
        """Rename postions created with the GridWidget.

        grid_info = [(name, pos_role, row), ...].
        By default, name is 'Gridnnn_Posnnn' but users can rename.

        Example
        -------
        grid_info = [
            (Grid000_Pos000, Grid000_Pos000, 1),
            (Grid000_Pos001, Grid000_Pos001, 2),
            (test0, Grid001_Pos000, 3),
            (test1, Grid001_Pos001, 4),
        ]
        """
        # first create a new list with items grouped by grid pos_role property
        ordered_by_grid_n = [
            list(grid_n)
            for _, grid_n in groupby(grid_info, lambda x: x[1].split("_")[0])
        ]

        # then rename each grid with new neame and new pos_role
        for idx, i in enumerate(ordered_by_grid_n):
            for pos_idx, n in enumerate(i):
                name, pos_role, row = n
                new_name = f"Grid{idx:03d}_Pos{pos_idx:03d}"
                self._update_table_item(new_name, row, 0, name == pos_role)

    def _clear_positions(self) -> None:
        """Clear all positions."""
        self._table.clearContents()
        self._table.setRowCount(0)
        self.valueChanged.emit()

    def _grid_widget(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        if not hasattr(self, "_grid_wdg"):
            self._grid_wdg = GridWidget(parent=self)
            self._grid_wdg.sendPosList.connect(self._add_grid_positions_to_table)
        self._grid_wdg.show()
        self._grid_wdg.raise_()

    def _add_grid_positions_to_table(
        self, position_list: list[tuple[float, ...]], clear: bool
    ) -> None:
        grid_number = -1

        if clear:
            self._clear_positions()
        else:
            for r in range(self._table.rowCount()):
                pos_name = self._table.item(r, 0).data(self.POS_ROLE)
                grid_name = pos_name.split("_")[0]  # e.g. Grid000
                if "Grid" in grid_name:
                    grid_n = grid_name[-3:]
                    if int(grid_n) > grid_number:
                        grid_number = int(grid_n)

        grid_number = 0 if grid_number < 0 else grid_number + 1

        for idx, position in enumerate(position_list):
            name = f"Grid{grid_number:03d}_Pos{idx:03d}"
            if len(position) == 3:
                x, y, z = position
            else:
                x, y = position
                z = None

            self._create_new_row(name, x, y, z)

    def _move_to_position(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        curr_row = self._table.currentRow()
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
        values: list[PositionDict] = [
            {
                "name": self._table.item(row, 0).text() or None,
                "x": self._get_table_value(row, 1),
                "y": self._get_table_value(row, 2),
                "z": self._get_table_value(row, 3),
            }
            for row in range(self._table.rowCount())
        ]
        return values

    def _get_table_value(self, row: int, col: int) -> float | None:
        try:
            wdg = cast(QDoubleSpinBox, self._table.cellWidget(row, col))
            value = wdg.value()
        except AttributeError:
            value = None
        return value  # type: ignore

    # note: this should to be PositionDict, but it makes typing elsewhere harder
    def set_state(self, positions: list[dict]) -> None:
        """Set the state of the widget from a useq position dictionary."""
        self._clear_positions()

        if not self._mmc.getXYStageDevice() and not self._mmc.getFocusDevice():
            raise ValueError("No XY and Z Stage devices loaded.")

        self.setChecked(True)

        for idx, pos in enumerate(positions):
            name = pos.get("name") or f"Pos{idx:03d}"
            x = pos.get("x")
            y = pos.get("y")
            z = pos.get("z")

            if (x is not None or y is not None) and not self._mmc.getXYStageDevice():
                x, y = (None, None)
                warnings.warn("No XY Stage device loaded.")

            if z and not self._mmc.getFocusDevice():
                z = None
                warnings.warn("No Focus device loaded.")

            self._add_position_row()

            self._add_table_item(name, idx, 0)
            self._add_table_value(x, idx, 1)
            self._add_table_value(y, idx, 2)
            self._add_table_value(z, idx, 3)

        self.valueChanged.emit()

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)
