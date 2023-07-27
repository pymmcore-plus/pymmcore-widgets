from __future__ import annotations

import math
import warnings
from typing import TYPE_CHECKING, Literal, cast

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked
from useq import AnyGridPlan, GridFromEdges, GridRelative
from useq._grid import OrderMode, RelativeTo

from .._util import get_grid_type

if TYPE_CHECKING:
    from typing_extensions import TypedDict

    class GridDict(TypedDict, total=False):
        """Grid dictionary."""

        overlap: float | tuple[float, float]
        mode: OrderMode | str
        rows: int
        columns: int
        relative_to: RelativeTo | str
        top: float
        left: float
        bottom: float
        right: float


fixed_sizepolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class _TabWidget(QTabWidget):
    """Main Tab Widget containing all the grid options...

    ...Rows and Columns, Grid from Edges and Grid from Corners.
    """

    valueChanged = Signal()

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # rows and columns
        self._rowcol = _RowsColsWdg()
        self._rowcol.valueChanged.connect(self.valueChanged.emit)
        self.addTab(self._rowcol, "Rows x Columns")

        # grid from edges
        self.edges = _FromEdgesWdg(mmcore=self._mmc)
        self.edges.valueChanged.connect(self.valueChanged.emit)
        self.addTab(self.edges, "Grid from Edges")

        # grid from corners
        self.corners = _FromCornersWdg(mmcore=self._mmc)
        self.corners.valueChanged.connect(self.valueChanged)
        self.addTab(self.corners, "Grid from Corners")

        self.currentChanged.connect(self._on_tab_changed)

    def value(self) -> GridDict:
        if self.currentIndex() == 0:
            return self._rowcol.value()
        elif self.currentIndex() == 1:
            return self.edges.value()
        else:
            return self.corners.value()

    def setValue(self, grid: GridDict) -> None:
        grid_type = get_grid_type(grid)  # type: ignore
        if isinstance(grid_type, GridRelative):
            self._rowcol.setValue(grid)
        elif isinstance(grid_type, GridFromEdges):
            self.edges.setValue(grid)
        self.valueChanged.emit()

    def _on_tab_changed(self) -> None:
        self.valueChanged.emit()


class _RowsColsWdg(QWidget):
    """Widget for setting the grid's number of rows and columns."""

    valueChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        group_layout = QGridLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(10, 10, 10, 10)

        # rows
        row_wdg = QWidget()
        row_wdg_lay = QHBoxLayout()
        row_wdg_lay.setSpacing(10)
        self.n_rows = self._general_label_spin_wdg(row_wdg, row_wdg_lay, "Rows:")
        # cols
        col_wdg = QWidget()
        col_wdg_lay = QHBoxLayout()
        col_wdg_lay.setSpacing(10)
        self.n_columns = self._general_label_spin_wdg(col_wdg, col_wdg_lay, "Columns:")

        # relative to combo
        relative_wdg = QWidget()
        relative_layout = QHBoxLayout()
        relative_layout.setSpacing(10)
        relative_layout.setContentsMargins(0, 0, 0, 0)
        relative_wdg.setLayout(relative_layout)
        relative_lbl = QLabel("Relative to:")
        relative_lbl.setSizePolicy(fixed_sizepolicy)
        self.relative_combo = QComboBox()
        self.relative_combo.addItems([r.value for r in RelativeTo])
        relative_layout.addWidget(relative_lbl)
        relative_layout.addWidget(self.relative_combo)

        group_layout.addWidget(row_wdg, 0, 0)
        group_layout.addWidget(col_wdg, 1, 0)
        group_layout.addWidget(relative_wdg, 0, 1)

        self.setLayout(group_layout)

    def _general_label_spin_wdg(
        self, wdg: QWidget, layout: QLayout, text: str
    ) -> QSpinBox:
        layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(layout)
        label = QLabel(text=text)
        label.setSizePolicy(fixed_sizepolicy)
        label.setMinimumWidth(65)
        spin = QSpinBox()
        spin.setMinimum(1)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setKeyboardTracking(False)
        spin.valueChanged.connect(lambda: self.valueChanged.emit())
        layout.addWidget(label)
        layout.addWidget(spin)
        return spin

    def value(self) -> GridDict:
        """Return the _RowsColsWdg grid dictionary."""
        return {
            "rows": self.n_rows.value(),
            "columns": self.n_columns.value(),
            "relative_to": self.relative_combo.currentText(),
        }

    def setValue(self, grid: GridDict) -> None:
        """Set the _RowsColsWdg grid dictionary."""
        keys = ["rows", "columns"]
        if any(item not in grid.keys() for item in keys):
            warnings.warn(f"Grid dictionary must contain {keys} keys", stacklevel=2)
            return

        self.n_rows.setValue(grid["rows"])
        self.n_columns.setValue(grid["columns"])

        if "relative_to" in grid:
            self.relative_combo.setCurrentText(
                grid["relative_to"]
                if isinstance(grid["relative_to"], str)
                else grid["relative_to"].value
            )

        self.valueChanged.emit()


class _FromEdgesWdg(QWidget):
    """Widget for setting the grid's edges."""

    valueChanged = Signal()

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        mmcore = mmcore or CMMCorePlus.instance()

        group_layout = QGridLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        # top, left, bottom, right
        self.top = _DoubleSpinboxWidget("top", mmcore=mmcore)
        self.top.valueChanged.connect(self.valueChanged.emit)
        self.bottom = _DoubleSpinboxWidget("bottom", mmcore=mmcore)
        self.bottom.valueChanged.connect(self.valueChanged.emit)
        self.top.label.setMinimumWidth(self.bottom.label.sizeHint().width())
        self.left = _DoubleSpinboxWidget("left", mmcore=mmcore)
        self.left.valueChanged.connect(self.valueChanged.emit)
        self.right = _DoubleSpinboxWidget("right", mmcore=mmcore)
        self.right.valueChanged.connect(self.valueChanged.emit)

        self.top.label.setFixedWidth(self.bottom.label.sizeHint().width() + 5)
        self.bottom.label.setFixedWidth(self.bottom.label.sizeHint().width() + 5)
        self.right.label.setFixedWidth(self.right.label.sizeHint().width() + 5)
        self.left.label.setFixedWidth(self.right.label.sizeHint().width() + 5)

        group_layout.addWidget(self.top, 0, 0)
        group_layout.addWidget(self.bottom, 1, 0)
        group_layout.addWidget(self.left, 0, 1)
        group_layout.addWidget(self.right, 1, 1)

    def value(self) -> GridDict:
        """Return the _FromEdgesWdg grid dictionary."""
        return {
            "top": cast("float", self.top.value()),
            "bottom": cast("float", self.bottom.value()),
            "left": cast("float", self.left.value()),
            "right": cast("float", self.right.value()),
        }

    def setValue(self, grid: GridDict) -> None:
        """Set the _FromEdgesWdg grid dictionary."""
        keys = ["top", "bottom", "left", "right"]
        if any(item not in grid.keys() for item in keys):
            warnings.warn(f"Grid dictionary must contain {keys} keys", stacklevel=2)
            return

        self.top.setValue(grid["top"])
        self.bottom.setValue(grid["bottom"])
        self.left.setValue(grid["left"])
        self.right.setValue(grid["right"])

        self.valueChanged.emit()


class _FromCornersWdg(QWidget):
    """Widget for setting the grid's corners."""

    valueChanged = Signal()

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        mmcore = mmcore or CMMCorePlus.instance()

        group_layout = QVBoxLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        self.corner_1 = _DoubleSpinboxWidget("corner1", mmcore=mmcore)
        self.corner_1.valueChanged.connect(self.valueChanged.emit)
        self.corner_2 = _DoubleSpinboxWidget("corner2", mmcore=mmcore)
        self.corner_2.valueChanged.connect(self.valueChanged.emit)

        self.corner_1.label.setFixedWidth(self.corner_2.label.sizeHint().width() + 5)
        self.corner_2.label.setFixedWidth(self.corner_2.label.sizeHint().width() + 5)

        group_layout.addWidget(self.corner_1)
        group_layout.addWidget(self.corner_2)

    def value(self) -> GridDict:
        """Return the _FromCornersWdg grid dictionary."""
        corner1_x, corner1_y = cast("tuple[float, float]", self.corner_1.value())
        corner2_x, corner2_y = cast("tuple[float, float]", self.corner_2.value())
        return {
            "top": max(corner1_y, corner2_y),
            "bottom": min(corner1_y, corner2_y),
            "left": min(corner1_x, corner2_x),
            "right": max(corner1_x, corner2_x),
        }

    def setValue(self, grid: GridDict) -> None:
        """Set the _FromCornersWdg grid dictionary."""
        keys = ["top", "bottom", "left", "right"]
        if any(item not in grid.keys() for item in keys):
            warnings.warn(f"Grid dictionary must contain {keys} keys", stacklevel=2)
            return

        self.corner_1.setValue((grid["left"], grid["top"]))
        self.corner_2.setValue((grid["right"], grid["bottom"]))

        self.valueChanged.emit()


class _DoubleSpinboxWidget(QWidget):
    """Double spinbox widget used by _FromEdgesWdg and _FromCornersWdg.

    It allows to set the grid's top, bottom, left, right, positions
    or the two corners position.
    """

    valueChanged = Signal()

    def __init__(
        self,
        label: Literal["top", "bottom", "left", "right", "corner1", "corner2"],
        mmcore: CMMCorePlus,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore
        self._label = label

        self._corners = label in {"corner1", "corner2"}

        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.label = QLabel(text=f"{self._label}:")
        self.label.setSizePolicy(fixed_sizepolicy)

        self.set_button = QPushButton(text="Set")
        self.set_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.set_button.setMinimumWidth(75)
        self.set_button.setSizePolicy(fixed_sizepolicy)
        self.set_button.clicked.connect(self._on_click)

        layout.addWidget(self.label)

        if self._corners:
            x_label = QLabel(text="x:")
            x_label.setSizePolicy(fixed_sizepolicy)
            self.x_spinbox = self._doublespinbox()
            y_label = QLabel(text="y:")
            y_label.setSizePolicy(fixed_sizepolicy)
            self.y_spinbox = self._doublespinbox()
            layout.addWidget(x_label)
            layout.addWidget(self.x_spinbox)
            layout.addWidget(y_label)
            layout.addWidget(self.y_spinbox)
        else:
            self.spinbox = self._doublespinbox()
            layout.addWidget(self.spinbox)

        layout.addWidget(self.set_button)

    def _doublespinbox(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setMaximum(1000000)
        spin.setMinimum(-1000000)
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setKeyboardTracking(False)
        spin.valueChanged.connect(lambda: self.valueChanged.emit())
        return spin

    def _on_click(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        if self._corners:
            self.x_spinbox.setValue(self._mmc.getXPosition())
            self.y_spinbox.setValue(self._mmc.getYPosition())
        elif self._label in {"top", "bottom"}:
            self.spinbox.setValue(self._mmc.getYPosition())
        elif self._label in {"left", "right"}:
            self.spinbox.setValue(self._mmc.getXPosition())

    def value(self) -> float | tuple[float, float]:
        if self._corners:
            return self.x_spinbox.value(), self.y_spinbox.value()
        return self.spinbox.value()  # type: ignore

    def setValue(self, value: float | tuple[float, float]) -> None:
        if isinstance(value, tuple):
            self.x_spinbox.setValue(value[0])
            self.y_spinbox.setValue(value[1])
        else:
            self.spinbox.setValue(value)
        self.valueChanged.emit()


class _OverlapAndOrderModeWdg(QGroupBox):
    """Widget to set the grid overlap and order mode."""

    valueChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        group_layout = QGridLayout()
        group_layout.setSpacing(15)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        # overlap x
        wdg_x = self._general_wdg_with_label("Overlap x (%):")
        self.overlap_spinbox_x = self._create_overlap_spinbox()
        wdg_x.layout().addWidget(self.overlap_spinbox_x)
        group_layout.addWidget(wdg_x, 0, 0)

        # overlap y
        wdg_y = self._general_wdg_with_label("Overlap y (%):")
        self.overlap_spinbox_y = self._create_overlap_spinbox()
        wdg_y.layout().addWidget(self.overlap_spinbox_y)
        group_layout.addWidget(wdg_y, 1, 0)

        # order mode
        wdg_mode = self._general_wdg_with_label("Order mode:")
        self.ordermode_combo = QComboBox()
        self.ordermode_combo.addItems([mode.value for mode in OrderMode])
        self.ordermode_combo.setCurrentText("snake_row_wise")
        wdg_mode.layout().addWidget(self.ordermode_combo)
        group_layout.addWidget(wdg_mode, 0, 1)

    def _general_wdg_with_label(self, label_text: str) -> QWidget:
        wdg = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(layout)
        label = QLabel(text=label_text)
        label.setSizePolicy(fixed_sizepolicy)
        layout.addWidget(label)
        return wdg

    def _create_overlap_spinbox(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setMinimumWidth(100)
        spin.setMaximum(100)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setKeyboardTracking(False)
        spin.valueChanged.connect(lambda: self.valueChanged.emit())
        return spin

    def value(self) -> GridDict:
        return {
            "overlap": (self.overlap_spinbox_x.value(), self.overlap_spinbox_y.value()),
            "mode": self.ordermode_combo.currentText(),
        }

    def setValue(self, value: GridDict) -> None:
        if "overlap" not in value:
            return

        over_x, over_y = (
            value["overlap"]
            if isinstance(value["overlap"], tuple)
            else (value["overlap"], value["overlap"])
        )
        self.overlap_spinbox_x.setValue(over_x)
        self.overlap_spinbox_y.setValue(over_y)

        if "mode" in value:
            self.ordermode_combo.setCurrentText(
                value["mode"] if isinstance(value["mode"], str) else value["mode"].value
            )

        self.valueChanged.emit()


class _MoveToWidget(QGroupBox):
    """Widget used to move to a specific grid position.

    It requires a _TabWidget to be able to access the selected grid plan.

    If using a Relative plan, the widget also needs the 'current position'
    coordinates to be able to calculate the absolute position where to move. If
    not provided, the current position will be the current stage position.
    """

    def __init__(
        self,
        tabwidget: _TabWidget,
        parent: QWidget | None = None,
        current_position: tuple[float, float] | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._current_position = current_position
        self._tabwidget = tabwidget

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        group_layout = QHBoxLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        lbl_policy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        row_lbl = QLabel("Row:")
        row_lbl.setSizePolicy(lbl_policy)
        col_lbl = QLabel("Column:")
        col_lbl.setSizePolicy(lbl_policy)

        self._move_to_row = QComboBox()
        self._move_to_row.setEditable(True)
        self._move_to_row.lineEdit().setReadOnly(True)
        self._move_to_row.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._move_to_col = QComboBox()
        self._move_to_col.setEditable(True)
        self._move_to_col.lineEdit().setReadOnly(True)
        self._move_to_col.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._move_button = QPushButton("Go")
        self._move_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._move_button.clicked.connect(self._move_to_row_col)

        group_layout.addWidget(row_lbl)
        group_layout.addWidget(self._move_to_row)
        group_layout.addWidget(col_lbl)
        group_layout.addWidget(self._move_to_col)
        group_layout.addWidget(self._move_button)

    def _clear(self) -> None:
        self._move_to_row.clear()
        self._move_to_col.clear()

    def _add_items(self, rows_items: list, cols_items: list) -> None:
        self._move_to_row.addItems(rows_items)
        self._move_to_col.addItems(cols_items)

    def _move_to_row_col(self) -> None:
        """Move to a selected position depending on the used grid plan."""
        if self._current_position is None:
            curr_x, curr_y = (self._mmc.getXPosition(), self._mmc.getYPosition())
        else:
            curr_x, curr_y = self._current_position

        grid = get_grid_type(self._tabwidget.value())  # type: ignore

        if grid is None:
            return

        if isinstance(grid, GridRelative) and (curr_x is None or curr_y is None):
            return

        _move_to_row = int(self._move_to_row.currentText())
        _move_to_col = int(self._move_to_col.currentText())

        row = _move_to_row - 1 if _move_to_row > 0 else 0
        col = _move_to_col - 1 if _move_to_col > 0 else 0

        _, _, width, height = self._mmc.getROI(self._mmc.getCameraDevice())
        width = int(width * self._mmc.getPixelSizeUm())
        height = int(height * self._mmc.getPixelSizeUm())

        for pos in grid.iter_grid_positions(width, height):
            if pos.row == row and pos.col == col:
                if isinstance(grid, GridRelative):
                    xpos = curr_x + pos.x
                    ypos = curr_y + pos.y
                else:
                    xpos = pos.x
                    ypos = pos.y
                self._mmc.setXYPosition(xpos, ypos)
                return


class GridWidget(QWidget):
    """A subwidget to setup the acquisition of a grid of images.

    The `value()` method returns a dictionary with the current state of the widget, in a
    format that matches one of the [useq-schema Grid Plan
    specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans).

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget, by default None.
    current_stage_pos : tuple[float | None, float | None]
        Optional current stage position. By default None.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    valueChanged = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        current_stage_pos: tuple[float, float] | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._current_stage_pos = current_stage_pos

        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(main_layout)

        # tab widget
        wdg = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(layout)
        self.tab = _TabWidget(mmcore=self._mmc)
        self.tab.valueChanged.connect(self._update_info)
        layout.addWidget(self.tab)
        main_layout.addWidget(wdg)

        # overlap and order mode
        self.overlap_and_mode = _OverlapAndOrderModeWdg()
        self.overlap_and_mode.valueChanged.connect(self._update_info)
        main_layout.addWidget(self.overlap_and_mode)

        # move to
        self.move_to = _MoveToWidget(
            tabwidget=self.tab, current_position=self._current_stage_pos
        )
        main_layout.addWidget(self.move_to)

        # info label
        label_info_group = QGroupBox()
        label_info_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        label_group_layout = QHBoxLayout()
        label_group_layout.setSpacing(0)
        label_group_layout.setContentsMargins(10, 10, 10, 10)
        label_info_group.setLayout(label_group_layout)
        self.info_lbl = QLabel()
        self.info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        label_group_layout.addWidget(self.info_lbl)
        main_layout.addWidget(label_info_group)

        # add button
        btn_wdg = QWidget()
        btn_wdg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_wdg_layout = QHBoxLayout()
        btn_wdg_layout.setSpacing(20)
        btn_wdg_layout.setContentsMargins(0, 0, 0, 0)
        btn_wdg.setLayout(btn_wdg_layout)

        spacer = QSpacerItem(
            5, 5, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        btn_wdg_layout.addSpacerItem(spacer)

        self.add_button = QPushButton(text="Add Grid")
        self.add_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.add_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.add_button.clicked.connect(self._emit_grid_positions)
        btn_wdg_layout.addWidget(self.add_button)
        main_layout.addWidget(btn_wdg)

        self.setFixedHeight(self.sizeHint().height())

        self._update_info()

        self._mmc.events.systemConfigurationLoaded.connect(self._update_info)
        self._mmc.events.pixelSizeChanged.connect(self._update_info)

        self.destroyed.connect(self._disconnect)

    def _update_info(self) -> None:
        """Update the info label with the current grid size."""
        if not self._mmc.getPixelSizeUm():
            self.info_lbl.setText(
                "Height: _ mm    Width: _ mm    (Rows: _    Columns: _)"
            )
            return

        _, _, width, height = self._mmc.getROI(self._mmc.getCameraDevice())
        width = int(width * self._mmc.getPixelSizeUm())
        height = int(height * self._mmc.getPixelSizeUm())
        overlap_xcent_x, overlap_xcent_y = cast(
            "tuple[float, float]", self.overlap_and_mode.value()["overlap"]
        )
        overlap_xcent_x = width * overlap_xcent_x / 100
        overlap_xcent_y = height * overlap_xcent_y / 100

        if self.tab.currentIndex() == 0:
            rows, cols = (self.tab.value()["rows"], self.tab.value()["columns"])
            x = ((width - overlap_xcent_x) * cols) / 1000
            y = ((height - overlap_xcent_y) * rows) / 1000
        else:
            top, bottom, left, right = cast(
                "tuple[float, ...]", self.tab.value().values()
            )

            rows = math.ceil((abs(top - bottom) + height) / height)
            cols = math.ceil((abs(right - left) + width) / width)

            x = (abs(left - right) + width) / 1000
            y = (abs(top - bottom) + height) / 1000

        self.info_lbl.setText(
            f"Height: {round(y, 3)} mm    Width: {round(x, 3)} mm    "
            f"(Rows: {rows}    Columns: {cols})"
        )

        self.move_to._clear()
        self.move_to._add_items(
            [str(r) for r in range(1, rows + 1)], [str(r) for r in range(1, cols + 1)]
        )

    # note: this really ought to be GridDict, but it makes typing harder
    def value(self) -> dict:
        """Return the current GridPlan settings.

        Note that output dict will match the Channel from useq schema:
        <https://pymmcore-plus.github.io/useq-schema/schema/axes/#grid-plans>
        """
        return {**self.tab.value(), **self.overlap_and_mode.value()}

    def set_state(self, grid: dict | AnyGridPlan) -> None:
        """Set the state of the widget from a useq AnyGridPlan or dictionary."""
        with signals_blocked(self):
            grid_plan = get_grid_type(grid) if isinstance(grid, dict) else grid

            self.overlap_and_mode.setValue(grid_plan.dict())  # type: ignore
            self.tab.setValue(grid_plan.dict())  # type: ignore
            self.tab.setCurrentIndex(0) if isinstance(
                grid_plan, GridRelative
            ) else self.tab.setCurrentIndex(1)
            self._update_info()
        self.valueChanged.emit(self.value())

    def _emit_grid_positions(self) -> None:
        """Emit the grid positions if the pixel size is set."""
        if self._mmc.getPixelSizeUm() <= 0:
            raise ValueError("Pixel Size Not Set.")

        if self.tab.currentIndex() > 0 and any(
            str(v) == "0.0" for v in self.tab.value().values()
        ):
            self._show_warning()
        else:
            self.valueChanged.emit(self.value())

    def _show_warning(self) -> None:
        """Show a warning message if the user has not set all the grid positions."""
        if self.tab.currentIndex() == 1:
            msg = (
                "Did you set all four 'top',  'bottom',  'left', and  'right'  "
                "positions?"
            )
        elif self.tab.currentIndex() == 2:
            msg = "Did you set the both corner positions?"

        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Warning)
        msgBox.setText(msg)
        msgBox.setWindowTitle("Grid from Edges")
        msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)

        if msgBox.exec() == QMessageBox.Ok:
            self.valueChanged.emit(self.value())

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._update_info)
        self._mmc.events.pixelSizeChanged.disconnect(self._update_info)
