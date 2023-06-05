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

from .._util import get_grid_type
from ._general_mda_widgets import _AutofocusZDeviceWidget
from ._grid_widget import GridWidget

if TYPE_CHECKING:
    from typing_extensions import TypedDict

    class PositionDict(TypedDict, total=False):
        """Position dictionary."""

        x: float | None
        y: float | None
        z: float | None
        z_device: str | None
        is_autofocus_z_device: bool
        name: str | None
        sequence: MDASequence | None


POS = "Pos"
P = 0
X = 1
Y = 2
Z = 3
AF = 4
GRID = 5
AlignCenter = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter


class PositionTable(QWidget):
    """Widget providing options for setting up a multi-position acquisition.

    The `value()` method returns a dictionary with the current state of the widget, in a
    format that matches one of the [useq-schema Position
    specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Position).

    Parameters
    ----------
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
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        group_layout = QGridLayout()
        group_layout.setSpacing(15)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        # autofocus
        af_groupbox = QGroupBox()
        af_groupbox_layout = QHBoxLayout()
        af_groupbox_layout.setSpacing(0)
        af_groupbox_layout.setContentsMargins(0, 0, 0, 0)
        af_groupbox.setLayout(af_groupbox_layout)
        self._autofocus_wdg = _AutofocusZDeviceWidget()
        self._autofocus_wdg.valueChanged.connect(self._on_autofocus_value_changed)
        af_groupbox_layout.addWidget(self._autofocus_wdg)
        group_layout.addWidget(af_groupbox, 0, 0, 1, 2)

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

        group_layout.addWidget(buttons_wdg, 1, 1)

        self.add_button.clicked.connect(self._add_position)
        self.replace_button.clicked.connect(self._replace_position)
        self.remove_button.clicked.connect(self._remove_position)
        self.clear_button.clicked.connect(self.clear)
        self.go_button.clicked.connect(self._move_to_position)
        self.save_positions_button.clicked.connect(self._save_positions)
        self.load_positions_button.clicked.connect(self._load_positions)

        # table
        self._table = QTableWidget()
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(hdr.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setTabKeyNavigation(True)
        self._table.setColumnCount(6)
        self._table.setRowCount(0)
        group_layout.addWidget(self._table, 1, 0)

        self._table.setMinimumHeight(buttons_wdg.sizeHint().height() + 5)
        self._table.selectionModel().selectionChanged.connect(self._enable_button)
        self._table.itemChanged.connect(self._rename_positions)

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.events.propertyChanged.connect(self._on_property_changed)

        self.destroyed.connect(self._disconnect)

        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:
        self.clear()
        self._set_table_header()
        xy = bool(self._mmc.getLoadedDevicesOfType(DeviceType.XYStageDevice))
        z = bool(self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice))
        self._advanced_cbox.setEnabled(xy)
        self.add_button.setEnabled(xy and z)
        self.save_positions_button.setEnabled(xy and z)
        advanced = self._advanced_cbox.isChecked()
        use_af = self._autofocus_wdg.value()["is_autofocus_z_device"]
        self._table.setColumnHidden(GRID, not advanced)
        self._table.setColumnHidden(AF, not use_af)

    def _on_property_changed(self, device: str, prop: str, value: str) -> None:
        # TODO: add 'propertyChanged.emit()' to pymmcore-plus setProperty() methods
        if not self._mmc.getLoadedDevicesOfType(
            DeviceType.XYStageDevice
        ) and not self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice):
            return

        if device != "Core" and prop not in {"Focus", "XYStage", "AutoFocus"}:
            return

        # hide XY or Z columns if ZStage or XYStage are not loaded + remove cell values
        indexes = (
            [Z]
            if prop == "Focus"
            else [X, Y]
            if prop == "XYStage"
            else [AF]
            if prop == "AutoFocus"
            else []
        )
        for idx in indexes:
            self._table.setColumnHidden(idx, not value)
            for r in range(self._table.rowCount()):
                self._table.removeCellWidget(r, idx)

            # rename column header with default ZStage or Autofocus
            if (
                idx not in {Z, AF}
                or self._autofocus_wdg.value()["is_autofocus_z_device"]
            ):
                continue
            name = self._mmc.getFocusDevice() if idx == Z else "Autofocus"
            self._table.setHorizontalHeaderItem(idx, QTableWidgetItem(name))

    def _set_table_header(self) -> None:
        self._table.setColumnCount(0)

        if not self._mmc.getLoadedDevicesOfType(
            DeviceType.XYStageDevice
        ) and not self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice):
            self.clear()
            return

        xy = self._mmc.getLoadedDevicesOfType(DeviceType.XYStageDevice)
        z = self._mmc.getFocusDevice() or None
        header = (
            [POS, "X", "Y"]
            + ([self._mmc.getFocusDevice()] if z else ["Z"])
            + ["Autofocus", "Grid"]
        )
        self._table.setColumnCount(len(header))
        self._table.setHorizontalHeaderLabels(header)

        # hide columns if no XY and/or Z stage
        if not xy:
            self._table.setColumnHidden(X, True)
            self._table.setColumnHidden(Y, True)
        if not z:
            self._table.setColumnHidden(Z, True)
        if not xy and not z:
            self._table.setColumnHidden(P, True)

    def _on_autofocus_value_changed(
        self, value: dict[str, bool | (str | None)]
    ) -> None:
        is_af = value["is_autofocus_z_device"]
        self._table.setColumnHidden(AF, not is_af)
        self._table.setHorizontalHeaderItem(AF, QTableWidgetItem(value["z_device"]))

        # if the signal is sent from the autofocus checkbox, do not delete cell widgets
        if isinstance(self.sender().sender(), QCheckBox):
            return

        # remove cell widgets in autofocus column
        for r in range(self._table.rowCount()):
            self._table.removeCellWidget(r, AF)

    def _on_advanced_toggled(self, state: bool) -> None:
        self._table.setColumnHidden(GRID, not state)

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
        if hasattr(self, "_grid_wdg"):
            self._grid_wdg.close()  # type: ignore

        name = f"Pos{self._table.rowCount():03d}"
        xpos = self._mmc.getXPosition() if self._mmc.getXYStageDevice() else None
        ypos = self._mmc.getYPosition() if self._mmc.getXYStageDevice() else None
        zpos = self._mmc.getZPosition() if self._mmc.getFocusDevice() else None
        z_device = cast("str", self._autofocus_wdg.value()["z_device"])
        z_pos_autofocus = self._mmc.getPosition(z_device) if z_device else None

        if z_pos_autofocus is not None and not self._mmc.isContinuousFocusLocked():
            warnings.warn("Autofocus Device is not Locked in Focus.", stacklevel=1)

        self._add_table_row(name, xpos, ypos, zpos, z_pos_autofocus)
        self._rename_positions()

    def _add_table_row(
        self,
        name: str | None,
        xpos: float | None,
        ypos: float | None,
        zpos: float | None,
        z_pos_autofocus: float | None,
        row: int | None = None,
    ) -> None:
        if not self._mmc.getXYStageDevice() and not self._mmc.getFocusDevice():
            raise ValueError("No XY and Z Stage devices selected.")

        if row is None:
            row = self._add_position_row()

        self._add_table_item(name, row, P)
        self._add_table_value(xpos, row, X)
        self._add_table_value(ypos, row, Y)
        self._add_table_value(zpos, row, Z)
        self._add_table_value(z_pos_autofocus, row, AF)

        self._add_grid_buttons(row, GRID)

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
        add_grid.clicked.connect(self._show_grid_widget)
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
        self._table.item(row, P).setData(self.GRID_ROLE, None)
        self._table.item(row, P).setToolTip("")
        add_grid, remove_grid = self._get_grid_buttons(row)
        add_grid.setText("")
        add_grid.setIcon(icon(MDI6.plus_thick, color=(0, 255, 0)))
        add_grid.setIconSize(QSize(25, 25))
        remove_grid.hide()
        self._enable_button()
        self.valueChanged.emit()

    def _get_grid_buttons(self, row: int) -> tuple[QPushButton, QPushButton]:
        return (
            self._table.cellWidget(row, GRID).layout().itemAt(0).widget(),
            self._table.cellWidget(row, GRID).layout().itemAt(1).widget(),
        )

    def _show_grid_widget(self) -> None:
        if hasattr(self, "_grid_wdg"):
            self._grid_wdg.close()  # type: ignore

        self._grid_wdg = GridWidget(
            mmcore=self._mmc,
            current_stage_pos=(self._mmc.getXPosition(), self._mmc.getYPosition()),
        )
        self._grid_wdg.setStyleSheet(self.parentWidget().styleSheet())

        row = self._table.indexAt(self.sender().parent().pos()).row()
        self._grid_wdg.valueChanged.connect(lambda x: self._add_grid_plan(x, row))

        item = self._table.item(row, P)
        if item.data(self.GRID_ROLE):
            self._grid_wdg.set_state(item.data(self.GRID_ROLE))

        self._grid_wdg.show()

    def _add_grid_plan(self, grid: dict, row: int | None = None) -> None:
        # sourcery skip: extract-method
        grid_type = get_grid_type(grid)

        if isinstance(grid_type, NoGrid):
            return

        if row is None:
            return

        self._table.item(row, P).setData(self.GRID_ROLE, grid)
        self._table.item(row, P).setToolTip(self._create_tooltip(grid))
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
            self._add_table_value(first_pos.x, row, X)
            self._add_table_value(first_pos.y, row, Y)

        self._enable_button()
        self.valueChanged.emit()

    def _create_tooltip(self, grid: dict) -> str:
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
        grid_role = self._table.item(row, P).data(self.GRID_ROLE)

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
        grid_plan = self._table.item(row, P).data(self.GRID_ROLE)
        for r in range(self._table.rowCount()):
            self._add_grid_plan(grid_plan, r)
        self.valueChanged.emit()

    def _replace_position(self) -> None:
        rows = [r.row() for r in self._table.selectedIndexes()]
        if len(set(rows)) > 1:
            return
        item = self._table.item(rows[0], P)
        name = item.text()
        xpos = self._mmc.getXPosition() if self._mmc.getXYStageDevice() else None
        ypos = self._mmc.getYPosition() if self._mmc.getXYStageDevice() else None
        zpos = self._mmc.getZPosition() if self._mmc.getFocusDevice() else None
        z_device = cast("str", self._autofocus_wdg.value()["z_device"])
        z_pos_autofocus = self._mmc.getPosition(z_device) if z_device else None

        self._add_table_row(name, xpos, ypos, zpos, z_pos_autofocus, rows[0])

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
            item = self._table.item(row, P)

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
        x, y = (self._get_table_value(curr_row, X), self._get_table_value(curr_row, Y))

        z_device = cast("str", self._autofocus_wdg.value()["z_device"])
        is_autofocus_z_device = self._autofocus_wdg.value()["is_autofocus_z_device"]
        z_col_idx = AF if is_autofocus_z_device else Z
        z = self._get_table_value(curr_row, z_col_idx)

        if x and y:
            self._mmc.setXYPosition(x, y)
        if is_autofocus_z_device and z_device and z is not None:
            self._mmc.setPosition(z_device, z)
            self._mmc.fullFocus()
        elif self._mmc.getFocusDevice() and z is not None:
            self._mmc.setPosition(self._mmc.getFocusDevice(), z)

    def _get_table_value(self, row: int, col: int | None) -> float | None:
        try:
            wdg = cast(QDoubleSpinBox, self._table.cellWidget(row, col))
            value = wdg.value()
        except (AttributeError, TypeError):
            value = None
        return value  # type: ignore

    def value(self) -> list[PositionDict]:
        """Return the current positions settings as a list of dictionaries.

        Note that the output will match the [useq-schema Positions
        specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Position).
        """
        if not self._table.rowCount():
            return []

        values: list = []

        for row in range(self._table.rowCount()):
            grid_role = self._table.item(row, P).data(self.GRID_ROLE)

            af = self._autofocus_wdg.value()
            z_col_idx = AF if af.get("is_autofocus_z_device") else Z

            values.append(
                {
                    "name": self._table.item(row, P).text(),
                    "x": self._get_table_value(row, X),
                    "y": self._get_table_value(row, Y),
                    "z": self._get_table_value(row, z_col_idx),
                    "sequence": {"grid_plan": grid_role} if grid_role else None,
                    **self._autofocus_wdg.value(),
                }
            )

        return values

    def set_state(
        self, positions: Sequence[PositionDict | Position], clear: bool = True
    ) -> None:
        """Set the state of the widget.

        Parameters
        ----------
        positions : Sequence[PositionDict | Position]
            A sequence of positions based on the [useq-schema Positions specifications](
            https://pymmcore-plus.github.io/useq-schema/schema/axes/#useq.Position).
        clear : bool
            By default True. If True, the current positions list is cleared before the
            specified one is added.
        """
        if clear:
            self.clear()

        if not isinstance(positions, Sequence):
            raise TypeError("The 'positions' arguments has to be a 'Sequence'.")

        if not self._mmc.getXYStageDevice() and not self._mmc.getFocusDevice():
            raise ValueError("No XY and Z Stage devices loaded.")

        for position in positions:
            if isinstance(position, Position):
                position = cast("PositionDict", position.dict())

            if not isinstance(position, dict):
                continue

            name = position.get("name")
            x, y, z = (position.get("x"), position.get("y"), position.get("z"))

            z_device = position.get("z_device", None)
            is_autofocus_z_device = position.get("is_autofocus_z_device", False)
            z, af = (None, z) if is_autofocus_z_device and z_device else (z, None)
            self._autofocus_wdg.setValue(
                {"z_device": z_device, "is_autofocus_z_device": is_autofocus_z_device}
            )

            self._add_table_row(name or f"{POS}000", x, y, z, af)

            if pos_seq := position.get("sequence"):
                self._advanced_cbox.setChecked(True)
                if isinstance(pos_seq, MDASequence):
                    grid_plan = pos_seq.grid_plan.dict()
                else:
                    grid_plan = pos_seq.get("grid_plan")
                if grid_plan:
                    self._add_grid_plan(grid_plan, GRID)

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
        self._mmc.events.propertyChanged.disconnect(self._on_property_changed)
