from __future__ import annotations

import contextlib
import warnings
from typing import TYPE_CHECKING, Any, Sequence, cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtCore import QPoint, QSize, Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QAction,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt import fonticon
from superqt.fonticon import icon
from superqt.utils import signals_blocked
from useq import (
    GridFromEdges,
    GridRelative,
    MDASequence,
    NoGrid,
    Position,
)
from useq._grid import OrderMode, RelativeTo

from .._util import get_grid_type
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

    Parameters
    ----------
    title: str
        Title of the widget, by default "Stage Positions".
    parent : QWidget | None
        Optional parent widget, by default None.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    valueChanged = Signal()
    GRID_ROLE = QTableWidgetItem.ItemType.UserType + 1

    def __init__(
        self,
        title: str = "Stage Positions",
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(title, parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._z_stages: dict[str, str] = {"Z Focus": "", "Z AutoFocus": ""}

        self.setCheckable(True)

        group_layout = QGridLayout()
        group_layout.setSpacing(15)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        # buttons
        buttons_wdg = QWidget()
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(10)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_wdg.setLayout(buttons_layout)

        btn_sizepolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.add_button = QPushButton(text="Add")
        self.add_button.setSizePolicy(btn_sizepolicy)
        self.replace_button = QPushButton(text="Replace")
        self.replace_button.setEnabled(False)
        self.replace_button.setSizePolicy(btn_sizepolicy)
        self.remove_button = QPushButton(text="Remove")
        self.remove_button.setEnabled(False)
        self.remove_button.setSizePolicy(btn_sizepolicy)
        self.clear_button = QPushButton(text="Clear")
        self.clear_button.setSizePolicy(btn_sizepolicy)
        self.go_button = QPushButton(text="Go")
        self.go_button.setEnabled(False)
        self.go_button.setSizePolicy(btn_sizepolicy)
        self.save_positions_button = QPushButton(text="Save")
        self.save_positions_button.setSizePolicy(btn_sizepolicy)
        self.load_positions_button = QPushButton(text="Load")
        self.load_positions_button.setSizePolicy(btn_sizepolicy)

        advanced_wdg = QWidget()
        advanced_wdg.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        advanced_layout = QHBoxLayout()
        advanced_layout.setSpacing(5)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_wdg.setLayout(advanced_layout)
        self._advanced_cbox = QCheckBox("Advanced")
        self._advanced_cbox.toggled.connect(self._on_advanced_toggled)
        self._warn_icon = QLabel()
        self._warn_icon.setToolTip("Warning: some 'Advanced' values are selected!")
        _icon = fonticon.icon(MDI6.alert_outline, color="magenta")
        self._warn_icon.setPixmap(_icon.pixmap(QSize(25, 25)))
        advanced_layout.addWidget(self._advanced_cbox)
        advanced_layout.addWidget(self._warn_icon)
        _w = (
            self._advanced_cbox.sizeHint().width()
            + self._warn_icon.sizeHint().width()
            + advanced_layout.spacing()
        )
        advanced_wdg.setMinimumWidth(_w)
        advanced_wdg.setMinimumHeight(advanced_wdg.sizeHint().height())
        self._warn_icon.hide()

        self.add_button.setMinimumWidth(_w)
        self.replace_button.setMinimumWidth(_w)
        self.remove_button.setMinimumWidth(_w)
        self.clear_button.setMinimumWidth(_w)
        self.go_button.setMinimumWidth(_w)
        self.save_positions_button.setMinimumWidth(_w)
        self.load_positions_button.setMinimumWidth(_w)

        buttons_layout.addWidget(self.add_button)
        buttons_layout.addWidget(self.replace_button)
        buttons_layout.addWidget(self.remove_button)
        buttons_layout.addWidget(self.clear_button)
        buttons_layout.addWidget(self.go_button)
        buttons_layout.addWidget(self.save_positions_button)
        buttons_layout.addWidget(self.load_positions_button)
        spacer_fix = QSpacerItem(
            0, 5, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        buttons_layout.addItem(spacer_fix)
        buttons_layout.addWidget(advanced_wdg)
        spacer = QSpacerItem(
            10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        buttons_layout.addItem(spacer)

        group_layout.addWidget(buttons_wdg, 0, 1)

        self.add_button.clicked.connect(self._add_position)
        self.replace_button.clicked.connect(self._replace_position)
        self.remove_button.clicked.connect(self._remove_position)
        self.clear_button.clicked.connect(self.clear)
        self.go_button.clicked.connect(self._move_to_position)
        self.save_positions_button.clicked.connect(self._save_positions)
        self.load_positions_button.clicked.connect(self._load_positions)

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

        # table
        self._table = QTableWidget()
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(hdr.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setTabKeyNavigation(True)
        self._table.setColumnCount(5)
        self._table.setRowCount(0)
        group_layout.addWidget(self._table, 0, 0)

        self._table.setMinimumHeight(buttons_wdg.sizeHint().height() + 5)
        self._table.selectionModel().selectionChanged.connect(self._enable_button)
        self._table.itemChanged.connect(self._rename_positions)

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)

        self.destroyed.connect(self._disconnect)

        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:
        self._z_stages["Z Focus"] = self._mmc.getFocusDevice() or ""
        self._z_stages["Z AutoFocus"] = ""
        self.clear()
        self._set_table_header()
        self._table.setColumnHidden(self._table.columnCount() - 1, True)
        self._populate_combo()
        if self._mmc.getLoadedDevicesOfType(DeviceType.AutoFocus):
            self.autofocus_lbl.show()
            self.z_autofocus_combo.show()
        else:
            self.autofocus_lbl.hide()
            self.z_autofocus_combo.hide()
        self._advanced_cbox.setEnabled(
            bool(self._mmc.getLoadedDevicesOfType(DeviceType.XYStageDevice))
        )

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

    def _on_combo_changed(self, value: str) -> None:
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
            (3, self._table.columnCount() - 1)
            if self._mmc.getLoadedDevicesOfType(DeviceType.XYStageDevice)
            else (0, self._table.columnCount() - 1)
        )
        for i in range(_range[0], _range[1]):
            if not value:
                self._table.setColumnHidden(i, True)
            elif i == 0:
                self._table.setColumnHidden(i, False)
            else:
                col_name = self._table.horizontalHeaderItem(i).text()
                self._table.setColumnHidden(i, col_name != value)

    def _on_z_focus_changed(self, focus_stage: str) -> None:
        if self.z_autofocus_combo.currentText() != "None":
            self._z_stages["Z Focus"] = focus_stage if focus_stage != "None" else ""
            return

        if focus_stage == "None":
            _range = (
                (3, self._table.columnCount() - 1)
                if self._mmc.getLoadedDevicesOfType(DeviceType.XYStageDevice)
                else (0, self._table.columnCount() - 1)
            )
            for c in range(_range[0], _range[1]):
                self._table.setColumnHidden(c, True)
            focus_stage = ""

        self._z_stages["Z Focus"] = focus_stage
        self._on_combo_changed(focus_stage)

    def _on_z_autofocus_changed(self, autofocus_stage: str) -> None:
        _autofocus = "" if autofocus_stage == "None" else autofocus_stage
        self._z_stages["Z AutoFocus"] = _autofocus
        if _autofocus:
            self._on_combo_changed(_autofocus)
        else:
            self._on_z_focus_changed(self.z_focus_combo.currentText())

    def _set_table_header(self) -> None:
        self._table.setColumnCount(0)

        if not self._mmc.getLoadedDevicesOfType(
            DeviceType.XYStageDevice
        ) and not self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice):
            self.clear()
            return

        header = (
            [POS]
            + (
                ["X", "Y"]
                if self._mmc.getLoadedDevicesOfType(DeviceType.XYStageDevice)
                else []
            )
            + list(self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice))
            + ["Grid"]
        )

        self._table.setColumnCount(len(header))
        self._table.setHorizontalHeaderLabels(header)
        self._hide_header_columns(header)

    def _hide_header_columns(self, header: list[str]) -> None:
        for idx, c in enumerate(header):
            if c == "Grid":
                continue

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

    def _get_z_stage_column(self) -> int | None:
        for i in range(self._table.columnCount()):
            col_name = self._table.horizontalHeaderItem(i).text()
            _z = self._z_stages["Z AutoFocus"] or self._z_stages["Z Focus"]
            if col_name == _z:
                return i
        return None

    def _on_advanced_toggled(self, state: bool) -> None:
        self._table.setColumnHidden(self._table.columnCount() - 1, not state)

        if not state:
            for v in self.value():
                if v["sequence"]:
                    self._warn_icon.show()
                    return
        self._warn_icon.hide()

    def _enable_button(self) -> None:
        rows = {r.row() for r in self._table.selectedIndexes()}
        self.go_button.setEnabled(len(rows) == 1)
        self.remove_button.setEnabled(len(rows) >= 1)

        self.replace_button.setEnabled(len(rows) == 1)
        if len(rows) == 1:
            grid_role = self._table.item(list(rows)[0], 0).data(self.GRID_ROLE)
            if grid_role and isinstance(get_grid_type(grid_role), GridFromEdges):
                self.replace_button.setEnabled(False)

    def _add_position(self) -> None:
        if not self._mmc.getLoadedDevicesOfType(
            DeviceType.XYStageDevice
        ) and not self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice):
            raise ValueError("No XY and Z Stages devices loaded.")

        if hasattr(self, "_grid_wdg"):
            self._grid_wdg.close()  # type: ignore

        name = f"Pos{self._table.rowCount():03d}"
        xpos = self._mmc.getXPosition() if self._mmc.getXYStageDevice() else None
        ypos = self._mmc.getYPosition() if self._mmc.getXYStageDevice() else None
        _z_stage = self._z_stages["Z AutoFocus"] or self._z_stages["Z Focus"]
        zpos = self._mmc.getPosition(_z_stage) if _z_stage else None

        if xpos is None and ypos is None and zpos is None:
            return

        self._add_table_row(name, xpos, ypos, zpos)
        self._rename_positions()

    def _add_table_row(
        self,
        name: str | None,
        xpos: float | None,
        ypos: float | None,
        zpos: float | None,
        row: int | None = None,
    ) -> None:
        if row is None:
            row = self._add_position_row()
        self._add_table_item(name, row, 0)
        self._add_table_value(xpos, row, 1)
        self._add_table_value(ypos, row, 2)
        self._add_table_value(zpos, row, self._get_z_stage_column())
        self._add_grid_buttons(row, self._table.columnCount() - 1)

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

    def _add_grid_buttons(self, row: int | None, col: int | None) -> None:
        wdg = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(layout)
        add_grid = QPushButton()
        add_grid.setIcon(icon(MDI6.plus_thick, color=(0, 255, 0)))
        add_grid.setIconSize(QSize(25, 25))
        add_grid.setFixedHeight(25)
        add_grid.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        add_grid.setContextMenuPolicy(Qt.CustomContextMenu)
        # for righ-click menu
        add_grid.customContextMenuRequested.connect(self._show_apply_to_all_menu)
        add_grid.clicked.connect(self._grid_widget)
        remove_grid = QPushButton()
        remove_grid.setIcon(icon(MDI6.close_thick, color="magenta"))
        remove_grid.setIconSize(QSize(25, 25))
        remove_grid.setFixedHeight(25)
        remove_grid.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        remove_grid.clicked.connect(self._remove_grid_plan)
        layout.addWidget(add_grid)
        layout.addWidget(remove_grid)
        remove_grid.hide()
        self._table.setCellWidget(row, col, wdg)

    def _remove_grid_plan(self) -> None:
        row = self._table.indexAt(self.sender().parent().pos()).row()
        self._table.item(row, 0).setData(self.GRID_ROLE, None)
        self._table.item(row, 0).setToolTip("")
        add_grid, remove_grid = self._get_grid_buttons(row)
        add_grid.setText("")
        add_grid.setIcon(icon(MDI6.plus_thick, color=(0, 255, 0)))
        add_grid.setIconSize(QSize(25, 25))
        remove_grid.hide()
        self._enable_button()
        self.valueChanged.emit()

    def _get_grid_buttons(self, row: int) -> tuple[QPushButton, QPushButton]:
        return (
            self._table.cellWidget(row, self._table.columnCount() - 1)
            .layout()
            .itemAt(0)
            .widget(),
            self._table.cellWidget(row, self._table.columnCount() - 1)
            .layout()
            .itemAt(1)
            .widget(),
        )

    def _grid_widget(self) -> None:
        if not self._mmc.getXYStageDevice():
            return

        if hasattr(self, "_grid_wdg"):
            self._grid_wdg.close()  # type: ignore

        self._grid_wdg = GridWidget(
            parent=self,
            mmcore=self._mmc,
            current_stage_pos=(self._mmc.getXPosition(), self._mmc.getYPosition()),
        )
        row = self._table.indexAt(self.sender().parent().pos()).row()
        self._grid_wdg.valueChanged.connect(lambda x: self._add_grid_plan(x, row))

        item = self._table.item(row, 0)
        if item.data(self.GRID_ROLE):
            self._grid_wdg.set_state(item.data(self.GRID_ROLE))

        self._grid_wdg.show()

    def _add_grid_plan(self, grid: GridDict, row: int | None = None) -> None:
        # sourcery skip: extract-method
        grid_type = get_grid_type(grid)

        if isinstance(grid_type, NoGrid):
            return

        if row is None:
            return

        self._table.item(row, 0).setData(self.GRID_ROLE, grid)
        self._table.item(row, 0).setToolTip(self._create_tooltip(grid))
        add_grid, remove_grid = self._get_grid_buttons(row)
        add_grid.setText("Edit")
        add_grid.setIcon(QIcon())
        remove_grid.show()
        if hasattr(self, "_grid_wdg"):
            self._grid_wdg.close()

        if isinstance(grid_type, GridFromEdges):
            _, _, width, height = self._mmc.getROI(self._mmc.getCameraDevice())
            width = int(width * self._mmc.getPixelSizeUm())
            height = int(height * self._mmc.getPixelSizeUm())
            first_pos = list(grid_type.iter_grid_positions(width, height))[0]
            self._add_table_value(first_pos.x, row, 1)
            self._add_table_value(first_pos.y, row, 2)

        self._enable_button()
        self.valueChanged.emit()

    def _create_tooltip(self, grid: GridDict) -> str:
        grid_type = get_grid_type(grid)

        if isinstance(grid_type, NoGrid):
            return ""

        tooltip: dict[str, Any] = {}
        if isinstance(grid_type, GridRelative):
            tooltip["rows"] = grid["rows"]
            tooltip["columns"] = grid["columns"]
            tooltip["relative_to"] = grid["relative_to"]
        elif isinstance(grid_type, GridFromEdges):
            tooltip["top"] = grid["top"]
            tooltip["bottom"] = grid["bottom"]
            tooltip["left"] = grid["left"]
            tooltip["right"] = grid["right"]

        tooltip["overlap"] = (
            tuple(grid["overlap"])
            if isinstance(grid["overlap"], (tuple, list))
            else grid["overlap"]
        )
        tooltip["mode"] = grid["mode"]

        return ",  ".join(f"{k}: {v}" for k, v in tooltip.items())

    def _show_apply_to_all_menu(self, QPos: QPoint) -> None:
        """Create right-click popup menu...

        to apply a relative grid_plan to all positions.
        """
        btn = cast(QPushButton, self.sender())
        row = self._table.indexAt(btn.parent().pos()).row()
        grid_role = self._table.item(row, 0).data(self.GRID_ROLE)

        # return if not grid or if absolute grid_plan
        if not grid_role:
            return
        if isinstance(get_grid_type(grid_role), GridFromEdges):
            return

        # define where the menu appear on click
        parentPosition = btn.mapToGlobal(QPoint(0, 0))
        menuPosition = parentPosition + QPos

        popMenu = QMenu(self)
        popMenu.addAction(QAction("Apply to All", self, checkable=True))
        popMenu.triggered.connect(lambda: self._apply_grid_to_all_positions(row))
        popMenu.move(menuPosition)
        popMenu.show()

    def _apply_grid_to_all_positions(self, row: int) -> None:
        grid_plan = self._table.item(row, 0).data(self.GRID_ROLE)
        for r in range(self._table.rowCount()):
            self._add_grid_plan(grid_plan, r)
        self.valueChanged.emit()

    def _replace_position(self) -> None:
        rows = [r.row() for r in self._table.selectedIndexes()]
        if len(set(rows)) > 1:
            return
        item = self._table.item(rows[0], 0)
        name = item.text()
        xpos = self._mmc.getXPosition() if self._mmc.getXYStageDevice() else None
        ypos = self._mmc.getYPosition() if self._mmc.getXYStageDevice() else None
        _z_stage = self._z_stages["Z AutoFocus"] or self._z_stages["Z Focus"]
        zpos = self._mmc.getPosition(_z_stage) if _z_stage else None

        if xpos is None and ypos is None and zpos is None:
            return

        self._add_table_row(name, xpos, ypos, zpos, rows[0])

    def _remove_position(self) -> None:
        rows = {r.row() for r in self._table.selectedIndexes()}
        for r in sorted(rows, reverse=True):
            self._table.removeRow(r)

        self._rename_positions()
        self.valueChanged.emit()

    def _rename_positions(self) -> None:
        pos_count = 0
        pos_rows: list[int] = []

        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)

            if not self._has_default_name(item.text()):
                continue

            pos_number = self._update_number(pos_count, pos_rows)
            new_name = f"{POS}{pos_number:03d}{item.text()[6:]}"
            pos_count = pos_number + 1
            with signals_blocked(self._table):
                item.setText(new_name)

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
        """Clear all positions."""
        self._table.clearContents()
        self._table.setRowCount(0)
        self.valueChanged.emit()

    def _move_to_position(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        curr_row = self._table.currentRow()
        x, y = (self._get_table_value(curr_row, 1), self._get_table_value(curr_row, 2))
        z = self._get_table_value(curr_row, self._get_z_stage_column())
        if x is not None and y is not None:
            self._mmc.setXYPosition(x, y)
        if z is not None:
            self._mmc.setPosition(
                self._z_stages["Z AutoFocus"] or self._z_stages["Z Focus"], z
            )

    def _get_table_value(self, row: int, col: int | None) -> float | None:
        if col is None:
            return None
        try:
            wdg = cast(QDoubleSpinBox, self._table.cellWidget(row, col))
            value = wdg.value()
        except AttributeError:
            value = None
        return value  # type: ignore

    def value(self) -> list[PositionDict]:
        """Return the current positions settings.

        Note that output dict will match the Positions from useq schema:
        <https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Position>.
        """
        # TODO: if we add zFocus and zAutoFocus info in the Position object,
        # expand the PositionDict
        if not self._table.rowCount():
            return []

        values: list[PositionDict] = []

        for row in range(self._table.rowCount()):
            grid_role = self._table.item(row, 0).data(self.GRID_ROLE)
            values.append(
                {
                    "name": self._table.item(row, 0).text(),
                    "x": self._get_table_value(row, 1),
                    "y": self._get_table_value(row, 2),
                    "z": self._get_table_value(row, self._get_z_stage_column()),
                    "sequence": (
                        {"grid_plan": grid_role} if grid_role else None  # type: ignore
                    ),
                }
            )

        return values

    def get_used_z_stages(self) -> dict[str, str]:
        """Return a dictionary of the used Z Focus and Z AutoFocus stages.

        e.g. {"Z Focus": Z", "Z AutoFocus": "Z1"}
        """
        return self._z_stages

    def set_state(
        self, positions: Sequence[PositionDict | Position], clear: bool = True
    ) -> None:
        """Set the state of the widget from a useq position dictionary."""
        # TODO: when we add the ability to store z stage name to MDASequence or Position
        # objects, we should also add the ability to set the z stage name here
        if clear:
            self.clear()

        self.setChecked(True)

        if not isinstance(positions, Sequence):
            raise TypeError("The 'positions' arguments has to be a 'Sequence'.")

        if not self._mmc.getLoadedDevicesOfType(
            DeviceType.XYStageDevice
        ) and not self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice):
            raise ValueError("No XY and Z Stages devices loaded.")

        for position in positions:
            if isinstance(position, Position):
                position = cast("PositionDict", position.dict())

            if not isinstance(position, dict):
                continue

            name = position.get("name")
            x, y, z = (position.get("x"), position.get("y"), position.get("z"))

            if x and y and not self._mmc.getXYStageDevice():
                warnings.warn("No XY Stage devices selected.")
                x = y = None

            if x is None and y is None and z is None:
                continue

            self._add_table_row(name or f"{POS}000", x, y, z)
            if pos_seq := position.get("sequence"):
                self._advanced_cbox.setChecked(True)
                if isinstance(pos_seq, MDASequence):
                    grid_plan = cast(GridDict, pos_seq.grid_plan.dict())
                else:
                    grid_plan = pos_seq.get("grid_plan")
                if grid_plan:
                    self._add_grid_plan(grid_plan, self._table.rowCount() - 1)

            self.valueChanged.emit()

    def _save_positions(self) -> None:
        if not self._table.rowCount() or not self.value():
            return

        (dir_file, _) = QFileDialog.getSaveFileName(
            self, "Saving directory and filename.", "", "json(*.json)"
        )
        if not dir_file:
            return

        import json

        with open(str(dir_file), "w") as file:
            json.dump(self.value(), file)

    def _load_positions(self) -> None:
        (filename, _) = QFileDialog.getOpenFileName(
            self, "Select a position list file", "", "json(*.json)"
        )
        if filename:
            import json

            with open(filename) as file:
                self.set_state(json.load(file))

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)
