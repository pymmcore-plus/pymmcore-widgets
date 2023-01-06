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

        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(self.main_layout)

        table_and_btns = QWidget()
        table_and_btns_layout = QHBoxLayout()
        table_and_btns_layout.setSpacing(15)
        table_and_btns_layout.setContentsMargins(0, 0, 0, 0)
        table_and_btns.setLayout(table_and_btns_layout)
        self.main_layout.addWidget(table_and_btns)

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
        self._set_table_header()
        table_and_btns_layout.addWidget(self.stage_tableWidget)

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
        self.replace_button = QPushButton(text="Replace")
        self.replace_button.setEnabled(False)
        self.replace_button.setMinimumWidth(min_size)
        self.replace_button.setSizePolicy(btn_sizepolicy)
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
        layout.addWidget(self.replace_button)
        layout.addWidget(self.remove_button)
        layout.addWidget(self.clear_button)
        layout.addWidget(self.grid_button)
        layout.addWidget(self.go_button)
        layout.addItem(spacer)

        table_and_btns_layout.addWidget(wdg)

        self.add_button.clicked.connect(self._add_position)
        self.replace_button.clicked.connect(self._replace_position)
        self.remove_button.clicked.connect(self._remove_position)
        self.clear_button.clicked.connect(self._clear_positions)
        self.grid_button.clicked.connect(self._grid_widget)
        self.go_button.clicked.connect(self._move_to_position)

        # bottom widget
        bottom_wdg = QWidget()
        bottom_wdg.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        bottom_wdg_layout = QHBoxLayout()
        bottom_wdg_layout.setSpacing(15)
        bottom_wdg_layout.setContentsMargins(0, 0, 0, 0)
        bottom_wdg.setLayout(bottom_wdg_layout)
        self.main_layout.addWidget(bottom_wdg)

        # z stage combo widget
        combo_wdg = QWidget()
        combo_wdg.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        cbox_wdg_layout = QHBoxLayout()
        cbox_wdg_layout.setSpacing(3)
        cbox_wdg_layout.setContentsMargins(0, 0, 0, 0)
        combo_wdg.setLayout(cbox_wdg_layout)
        bottom_wdg_layout.addWidget(combo_wdg)
        lbl = QLabel("Z Stage:")
        lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.z_stage_combo = QComboBox()
        self.z_stage_combo.currentTextChanged.connect(self._on_z_stage_combo_changed)
        cbox_wdg_layout.addWidget(lbl)
        cbox_wdg_layout.addWidget(self.z_stage_combo)
        self._populate_stage_combo()

        self.stage_tableWidget.selectionModel().selectionChanged.connect(
            self._enable_go_replace_button
        )
        self.stage_tableWidget.selectionModel().selectionChanged.connect(
            self._enable_remove_button
        )

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.events.propertyChanged.connect(self._on_prop_changed)

        self.destroyed.connect(self._disconnect)

    def _on_sys_cfg_loaded(self) -> None:
        self._clear_positions()
        self._set_table_header()
        self._populate_stage_combo()

    def _on_prop_changed(self, device: str, prop: str, value: str) -> None:
        if device == "Core" and prop == "Focus":

            with signals_blocked(self.z_stage_combo):
                self.z_stage_combo.setCurrentText(value or "None")

            for i in range(3, self.stage_tableWidget.columnCount()):
                if not value:
                    self.stage_tableWidget.setColumnHidden(i, True)
                else:
                    col_name = self.stage_tableWidget.horizontalHeaderItem(i).text()
                    self.stage_tableWidget.setColumnHidden(i, col_name != value)

    def _populate_stage_combo(self) -> None:
        with signals_blocked(self.z_stage_combo):
            self.z_stage_combo.clear()
            items = ["None"] + list(
                self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice)
            )
            self.z_stage_combo.addItems(items)
        self.z_stage_combo.setCurrentText(self._mmc.getFocusDevice() or "None")

    def _on_z_stage_combo_changed(self, stage: str) -> None:
        if stage == "None":
            for c in range(3, self.stage_tableWidget.columnCount()):
                self.stage_tableWidget.setColumnHidden(c, True)
            stage = ""
        self._mmc.setFocusDevice(stage)

    def _enable_go_replace_button(self) -> None:
        rows = {r.row() for r in self.stage_tableWidget.selectedIndexes()}
        self.go_button.setEnabled(len(rows) == 1)
        self.replace_button.setEnabled(len(rows) == 1)
        if (
            len(rows) == 1
            and "Grid" in self.stage_tableWidget.item(list(rows)[0], 0).whatsThis()
        ):
            self.replace_button.setEnabled(False)

    def _enable_remove_button(self) -> None:
        rows = {r.row() for r in self.stage_tableWidget.selectedIndexes()}
        self.remove_button.setEnabled(len(rows) >= 1)

    def _set_table_header(self) -> None:
        header = ["Pos", "X", "Y"] + list(
            self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice)
        )
        self.stage_tableWidget.setColumnCount(len(header))
        self.stage_tableWidget.setHorizontalHeaderLabels(header)
        for idx, c in enumerate(header):
            if idx <= 2:
                continue
            if self._mmc.getFocusDevice() != c:
                self.stage_tableWidget.setColumnHidden(idx, True)
                self.stage_tableWidget.isColumnHidden(idx)

    def _add_position(self) -> None:

        if not self._mmc.getXYStageDevice() and not self._mmc.getFocusDevice():
            raise ValueError("No XY and Z Stage devices loaded.")

        name = f"Pos{self.stage_tableWidget.rowCount():03d}"
        xpos = self._mmc.getXPosition() if self._mmc.getXYStageDevice() else None
        ypos = self._mmc.getYPosition() if self._mmc.getXYStageDevice() else None
        zpos = self._mmc.getZPosition() if self._mmc.getFocusDevice() else None

        self._create_row(name, xpos, ypos, zpos)

        self._rename_positions()

    def _create_row(
        self,
        name: str | None,
        xpos: float | None,
        ypos: float | None,
        zpos: float | None,
        row: int | None = None,
    ) -> None:

        if not self._mmc.getXYStageDevice() and not self._mmc.getFocusDevice():
            raise ValueError("No XY and Z Stage selected.")

        if row is None:
            row = self._add_position_row()

        self._add_table_item(name, row, 0)
        self._add_table_value(xpos, row, 1)
        self._add_table_value(ypos, row, 2)
        if zpos is None or not self._mmc.getFocusDevice():
            self.valueChanged.emit()
            return
        self._add_table_value(zpos, row, self._get_z_stage_column())

        self.valueChanged.emit()

    def _get_z_stage_column(self) -> int | None:
        for i in range(self.stage_tableWidget.columnCount()):
            col_name = self.stage_tableWidget.horizontalHeaderItem(i).text()
            if col_name == self._mmc.getFocusDevice():
                return i
        return None

    def _add_position_row(self) -> int:
        idx = self.stage_tableWidget.rowCount()
        self.stage_tableWidget.insertRow(idx)
        return cast(int, idx)

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
        self.stage_tableWidget.setCellWidget(row, col, spin)

    def _add_table_item(self, table_item: str | None, row: int, col: int) -> None:
        item = QTableWidgetItem(table_item)
        # whatsthis is used to keep track of grid and/or position
        # even when the user changed the name in the table.
        item.setWhatsThis(table_item)
        item.setToolTip(table_item)
        item.setTextAlignment(AlignCenter)
        self.stage_tableWidget.setItem(row, col, item)

    def _replace_position(self) -> None:

        rows = [r.row() for r in self.stage_tableWidget.selectedIndexes()]
        if len(set(rows)) > 1:
            return

        name = self.stage_tableWidget.item(rows[0], 0).text()
        xpos = self._mmc.getXPosition() if self._mmc.getXYStageDevice() else None
        ypos = self._mmc.getYPosition() if self._mmc.getXYStageDevice() else None
        zpos = self._mmc.getZPosition() if self._mmc.getFocusDevice() else None

        self._create_row(name, xpos, ypos, zpos, rows[0])

    def _remove_position(self) -> None:

        rows = {r.row() for r in self.stage_tableWidget.selectedIndexes()}
        grid_to_delete = []

        for idx in sorted(rows, reverse=True):

            whatsthis = self.stage_tableWidget.item(idx, 0).whatsThis()
            # store grid name if is a grid position
            if "Grid" in whatsthis:
                grid_name = whatsthis.split("_")[0]
                grid_to_delete.append(grid_name)
            else:
                # remove if is a single position
                self.stage_tableWidget.removeRow(idx)

        # remove grid positions
        for gridname in grid_to_delete:
            self._delete_grid_positions(gridname)

        self._rename_positions()
        self.valueChanged.emit()

    def _delete_grid_positions(self, name: list[str]) -> None:
        """Remove all positions related to the same grid."""
        for row in reversed(range(self.stage_tableWidget.rowCount())):
            if name in self.stage_tableWidget.item(row, 0).whatsThis():
                self.stage_tableWidget.removeRow(row)

    def _rename_positions(self) -> None:
        single_pos_count = 0
        single_pos_rows: list[int] = []
        grid_info: list[tuple[str, str, int]] = []
        for row in range(self.stage_tableWidget.rowCount()):
            name = self.stage_tableWidget.item(row, 0).text()
            whatsthis = self.stage_tableWidget.item(row, 0).whatsThis()

            if "Grid" in whatsthis.split("_")[0]:
                grid_info.append((name, whatsthis, row))
                continue

            if name == whatsthis:  # name = Posnnn and whatsthis = Posnnn
                pos_number = self._update_number(single_pos_count, single_pos_rows)
                new_name = f"Pos{pos_number:03d}"
                single_pos_count = pos_number + 1
                self._update_table_item(new_name, row, 0)

            elif "Grid" not in whatsthis:  # whatsthis = Posnnn
                single_pos_rows.append(row)
                new_whatsthis = f"Pos{row:03d}"
                self._update_table_item(new_whatsthis, row, 0, False)

        if not grid_info:
            return

        self._rename_grid_positions(grid_info)

    def _update_table_item(
        self, name: str, row: int, col: int, update_name: bool = True
    ) -> None:
        if update_name:
            self.stage_tableWidget.item(row, col).setText(name)
        self.stage_tableWidget.item(row, col).setWhatsThis(name)
        self.stage_tableWidget.item(row, col).setToolTip(name)

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

        grid_info = [(name, whatsthis, row), ...].
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
        # first create a new list with items grouped by grid WhatsThis property
        ordered_by_grid_n = [
            list(grid_n)
            for _, grid_n in groupby(grid_info, lambda x: x[1].split("_")[0])
        ]

        # then rename each grid with new neame and new whatsthis
        for idx, i in enumerate(ordered_by_grid_n):
            for pos_idx, n in enumerate(i):
                name, whatsthis, row = n
                new_name = f"Grid{idx:03d}_Pos{pos_idx:03d}"
                self._update_table_item(new_name, row, 0, name == whatsthis)

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

    def _add_grid_positions_to_table(
        self, position_list: list[tuple[float, ...]], clear: bool
    ) -> None:

        grid_number = -1

        if clear:
            self._clear_positions()
        else:
            for r in range(self.stage_tableWidget.rowCount()):
                pos_name = self.stage_tableWidget.item(r, 0).whatsThis()
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

            self._create_row(name, x, y, z)

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
        return [
            {
                "name": self.stage_tableWidget.item(row, 0).text() or None,
                "x": self._get_table_value(row, 1),
                "y": self._get_table_value(row, 2),
                "z": self._get_table_value(row, self._get_z_stage_column()),
            }
            for row in range(self.stage_tableWidget.rowCount())
        ]

    def _get_table_value(self, row: int, col: int | None) -> float | None:
        try:
            wdg = cast(QDoubleSpinBox, self.stage_tableWidget.cellWidget(row, col))
            value = wdg.value()
        except (AttributeError, TypeError):
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
            self._add_table_value(z, idx, self._get_z_stage_column())

        self.valueChanged.emit()

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)
        self._mmc.events.propertyChanged.disconnect(self._on_prop_changed)
