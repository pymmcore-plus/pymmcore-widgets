from __future__ import annotations

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
    from useq import (
        NoZ,
        ZAboveBelow,
        ZAbsolutePositions,
        ZRangeAround,
        ZRelativePositions,
        ZTopBottom,
    )

    class PositionDict(TypedDict, total=False):
        """Position dictionary."""

        x: float | None
        y: float | None
        z: float | None
        name: str | None
        z_plan: (
            ZTopBottom
            | ZRangeAround
            | ZAboveBelow
            | ZRelativePositions
            | ZAbsolutePositions
            | NoZ
            | None
        )


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
        self.go = QPushButton(text="Go")
        self.go.clicked.connect(self._move_to_position)
        self.go.setMinimumWidth(min_size)
        self.go.setSizePolicy(btn_sizepolicy)

        spacer = QSpacerItem(
            10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        layout.addWidget(self.add_pos_button)
        layout.addWidget(self.remove_pos_button)
        layout.addWidget(self.clear_pos_button)
        layout.addWidget(self.grid_button)
        layout.addWidget(self.go)
        layout.addItem(spacer)

        group_layout.addWidget(wdg)

        self.add_pos_button.clicked.connect(self._add_position)
        self.remove_pos_button.clicked.connect(self._remove_position)
        self.clear_pos_button.clicked.connect(self._clear_positions)
        self.grid_button.clicked.connect(self._grid_widget)

        self._mmc.events.systemConfigurationLoaded.connect(self._clear_positions)

        self.destroyed.connect(self._disconnect)

    def _add_position(self) -> None:

        if not self._mmc.getXYStageDevice():
            return

        if len(self._mmc.getLoadedDevices()) > 1:
            idx = self._add_position_row()

            for c, ax in enumerate("PXYZ"):

                if ax == "P":
                    count = self.stage_tableWidget.rowCount() - 1
                    item = QTableWidgetItem(f"Pos{count:03d}")
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                    self.stage_tableWidget.setItem(idx, c, item)
                    self._rename_positions(["Pos"])
                    continue

                if not self._mmc.getFocusDevice() and ax == "Z":
                    continue
                cur = getattr(self._mmc, f"get{ax}Position")()
                item = QTableWidgetItem(str(cur))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                )
                self.stage_tableWidget.setItem(idx, c, item)

            self.valueChanged.emit()

    def _add_position_row(self) -> int:
        idx = self.stage_tableWidget.rowCount()
        self.stage_tableWidget.insertRow(idx)
        return cast(int, idx)

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
        for row in reversed(range(self.stage_tableWidget.rowCount())):
            if name in self.stage_tableWidget.item(row, 0).whatsThis():
                self.stage_tableWidget.removeRow(row)

    def _rename_positions(self, names: list) -> None:
        for name in names:
            pos_count = 0
            for r in range(self.stage_tableWidget.rowCount()):
                if "Grid" in name or "Pos" not in name:
                    continue
                new_name = f"Pos{pos_count:03d}"
                pos_count += 1
                item = QTableWidgetItem(new_name)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                )
                self.stage_tableWidget.setItem(r, 0, item)

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
            self._grid_wdg.sendPosList.connect(self._add_to_position_table)
        self._grid_wdg.show()
        self._grid_wdg.raise_()

    def _add_to_position_table(self, position_list: list, clear: bool) -> None:

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
            rows = self.stage_tableWidget.rowCount()
            self.stage_tableWidget.insertRow(rows)

            item = QTableWidgetItem(f"Grid{grid_number:03d}_Pos{idx:03d}")
            item.setWhatsThis(f"Grid{grid_number:03d}_Pos{idx:03d}")
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )
            x = QTableWidgetItem(str(position[0]))
            x.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )
            y = QTableWidgetItem(str(position[1]))
            y.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )
            z = QTableWidgetItem(str(position[2]))
            z.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )

            self.stage_tableWidget.setItem(rows, 0, item)
            self.stage_tableWidget.setItem(rows, 1, x)
            self.stage_tableWidget.setItem(rows, 2, y)
            self.stage_tableWidget.setItem(rows, 3, z)

    def _move_to_position(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        curr_row = self.stage_tableWidget.currentRow()
        x_val = self.stage_tableWidget.item(curr_row, 1).text()
        y_val = self.stage_tableWidget.item(curr_row, 2).text()
        z_val = self.stage_tableWidget.item(curr_row, 3).text()
        self._mmc.setXYPosition(float(x_val), float(y_val))
        self._mmc.setPosition(self._mmc.getFocusDevice(), float(z_val))

    # def value(self) -> list[PositionDict]:
    #     """Return the current channels settings.

    #     Note that output dict will match the Positions from useq schema:
    #     <https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Position>
    #     """
    #     ...

    # def set_state(self, positions: list[dict]) -> None:
    #     """Set the state of the widget from a useq position dictionary."""
    #     ...

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._clear_positions)
