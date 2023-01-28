from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from useq import AnyGridPlan, GridFromCorners, GridRelative  # type: ignore
from useq._grid import Coordinate, OrderMode, RelativeTo

if TYPE_CHECKING:
    from typing_extensions import TypedDict

    class PGridDict(TypedDict, total=False):
        """Grid dictionary."""

        overlap: float
        order_mode: OrderMode | str
        rows: int
        cols: int
        relative_to: RelativeTo | str
        corner1: Coordinate
        corner2: Coordinate


fixed_sizepolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class _CornerSpinbox(QWidget):

    valueChanged = Signal()

    def __init__(
        self, label: str, parent: QWidget | None = None, *, mmcore: CMMCorePlus
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore

        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        lbl = QLabel(text=label)
        lbl.setSizePolicy(fixed_sizepolicy)

        lbl_x = QLabel(text="x:")
        lbl_x.setSizePolicy(fixed_sizepolicy)
        lbl_y = QLabel(text="y:")
        lbl_y.setSizePolicy(fixed_sizepolicy)

        self.x_spinbox = self._doublespinbox()
        self.y_spinbox = self._doublespinbox()

        self.set_button = QPushButton(text="Set")
        self.set_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.set_button.setMinimumWidth(75)
        self.set_button.setSizePolicy(fixed_sizepolicy)
        self.set_button.clicked.connect(self._on_click)

        layout.addWidget(lbl)
        layout.addWidget(lbl_x)
        layout.addWidget(self.x_spinbox)
        layout.addWidget(lbl_y)
        layout.addWidget(self.y_spinbox)
        layout.addWidget(self.set_button)

    def _doublespinbox(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setMaximum(1000000)
        spin.setMinimum(-1000000)
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.valueChanged.connect(self.valueChanged)
        return spin

    def _on_click(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        self.x_spinbox.setValue(self._mmc.getXPosition())
        self.y_spinbox.setValue(self._mmc.getYPosition())

    def set_values(self, x: float, y: float) -> None:
        self.x_spinbox.setValue(x)
        self.y_spinbox.setValue(y)

    def values(self) -> tuple[float, float]:
        return self.x_spinbox.value(), self.y_spinbox.value()


class GridWidget(QDialog):
    """A subwidget to setup the acquisition of a grid of images."""

    valueChanged = Signal(object, bool)

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)

        tab = self._create_tab()
        layout.addWidget(tab)

        overlap_and_size = self._create_overlap_and_ordermode()
        layout.addWidget(overlap_and_size)

        label_info = self._create_label_info()
        layout.addWidget(label_info)

        button = self._create_generate_list_button()
        layout.addWidget(button)

        self.setFixedHeight(self.sizeHint().height())

        self._update_info_label()

        self._mmc.events.systemConfigurationLoaded.connect(self._update_info_label)

        self.destroyed.connect(self._disconnect)

    def _create_tab(self) -> QWidget:
        wdg = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(layout)
        self.tab = QTabWidget()
        self.tab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        rc = self._create_row_cols_wdg()
        self.tab.addTab(rc, "Rows x Columns")

        cr = self._create_corner_wdg()
        self.tab.addTab(cr, "Grid from Corners")

        layout.addWidget(self.tab)
        return wdg

    def _create_row_cols_wdg(self) -> QWidget:
        group = QWidget()
        group_layout = QGridLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(10, 10, 10, 10)
        group.setLayout(group_layout)

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

        return group

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
        spin.valueChanged.connect(self._update_info_label)
        layout.addWidget(label)
        layout.addWidget(spin)
        return spin

    def _create_corner_wdg(self) -> QWidget:
        group = QWidget()
        group_layout = QVBoxLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(10, 10, 10, 10)
        group.setLayout(group_layout)

        self.corner1 = _CornerSpinbox("Corner 1", mmcore=self._mmc)
        self.corner1.valueChanged.connect(self._update_info_label)
        self.corner2 = _CornerSpinbox("Corner 2", mmcore=self._mmc)
        self.corner2.valueChanged.connect(self._update_info_label)

        group_layout.addWidget(self.corner1)
        group_layout.addWidget(self.corner2)

        return group

    def _create_overlap_and_ordermode(self) -> QGroupBox:
        group = QGroupBox()
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        group_layout = QHBoxLayout()
        group_layout.setSpacing(15)
        group_layout.setContentsMargins(10, 10, 10, 10)
        group.setLayout(group_layout)

        # overlap
        ovl_wdg = QWidget()
        ovl_wdg_lay = QHBoxLayout()
        ovl_wdg_lay.setSpacing(10)
        ovl_wdg_lay.setContentsMargins(0, 0, 0, 0)
        ovl_wdg.setLayout(ovl_wdg_lay)
        overlap_label = QLabel(text="Overlap (%):")
        overlap_label.setSizePolicy(fixed_sizepolicy)
        self.overlap_spinbox = QDoubleSpinBox()
        self.overlap_spinbox.setMinimumWidth(100)
        self.overlap_spinbox.setMaximum(100)
        self.overlap_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlap_spinbox.valueChanged.connect(self._update_info_label)
        ovl_wdg_lay.addWidget(overlap_label)
        ovl_wdg_lay.addWidget(self.overlap_spinbox)
        group_layout.addWidget(ovl_wdg)

        # order mode
        mode_wdg = QWidget()
        mode_wdg_lay = QHBoxLayout()
        mode_wdg_lay.setSpacing(10)
        mode_wdg_lay.setContentsMargins(0, 0, 0, 0)
        mode_wdg.setLayout(mode_wdg_lay)
        mode_label = QLabel(text="Order mode:")
        mode_label.setSizePolicy(fixed_sizepolicy)
        self.ordermode_combo = QComboBox()
        self.ordermode_combo.addItems([mode.value for mode in OrderMode])
        self.ordermode_combo.setCurrentText("Snake RowWise")
        mode_wdg_lay.addWidget(mode_label)
        mode_wdg_lay.addWidget(self.ordermode_combo)
        group_layout.addWidget(mode_wdg)

        return group

    def _create_label_info(self) -> QGroupBox:
        group = QGroupBox()
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        group_layout = QHBoxLayout()
        group_layout.setSpacing(0)
        group_layout.setContentsMargins(10, 10, 10, 10)
        group.setLayout(group_layout)

        self.info_lbl = QLabel(text="Width: _ mm    Height: _ mm")
        self.info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        group_layout.addWidget(self.info_lbl)

        return group

    def _create_generate_list_button(self) -> QWidget:
        wdg = QWidget()
        wdg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        wdg_layout = QHBoxLayout()
        wdg_layout.setSpacing(20)
        wdg_layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(wdg_layout)

        self.clear_checkbox = QCheckBox(text="Delete Current Position List")
        self.clear_checkbox.setChecked(False)
        wdg_layout.addWidget(self.clear_checkbox)

        self.generate_position_btn = QPushButton(text="Generate Position List")
        self.generate_position_btn.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.generate_position_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.generate_position_btn.clicked.connect(self._send_positions_grid)
        wdg_layout.addWidget(self.generate_position_btn)

        return wdg

    def _update_info_label(self) -> None:
        if not self._mmc.getPixelSizeUm():
            self.info_lbl.setText("Width: _ mm    Height: _ mm")
            return

        px_size = self._mmc.getPixelSizeUm()
        _, _, width, height = self._mmc.getROI(self._mmc.getCameraDevice())
        overlap_percentage = self.overlap_spinbox.value()
        overlap_x = width * overlap_percentage / 100
        overlap_y = height * overlap_percentage / 100

        if self.tab.currentIndex() == 0:  # rows and cols
            rows = self.n_rows.value()
            cols = self.n_columns.value()
        else:  # corners
            total_width = (
                abs(self.corner1.values()[0] - self.corner2.values()[0]) + width
            )
            total_height = (
                abs(self.corner1.values()[1] - self.corner2.values()[1]) + height
            )
            rows = math.ceil(total_width / width) if total_width > width else 1
            cols = math.ceil(total_height / height) if total_height > height else 1

        y = ((height - overlap_y) * rows) * px_size / 1000
        x = ((width - overlap_x) * cols) * px_size / 1000

        self.info_lbl.setText(f"Width: {round(y, 3)} mm    Height: {round(x, 3)} mm")

    def value(self) -> AnyGridPlan:
        # TODO: update docstring when useq GridPlan will be added to the docs.
        """Return the current grid settings."""
        if self.tab.currentIndex() == 0:  # rows and cols
            return GridRelative(
                overlap=self.overlap_spinbox.value(),
                rows=self.n_rows.value(),
                cols=self.n_columns.value(),
                relative_to=self.relative_combo.currentText(),
                order_mode=self.ordermode_combo.currentText(),
            )
        else:  # corners
            return GridFromCorners(
                overlap=(self.overlap_spinbox.value()),
                corner1=(self.corner1.values()),
                corner2=self.corner2.values(),
                order_mode=self.ordermode_combo.currentText(),
            )

    def set_state(self, grid: AnyGridPlan | dict) -> None:
        """Set the state of the widget from a useq AnyGridPlan or dictionary."""
        if isinstance(grid, dict):
            self.overlap_spinbox.setValue(grid["overlap"][0])
            ordermode = (
                grid["order_mode"].value
                if isinstance(grid.get("order_mode"), OrderMode)
                else grid["order_mode"]
            )
            self.ordermode_combo.setCurrentText(ordermode)
            try:
                self.n_rows.setValue(grid.get("rows"))
                self.n_columns.setValue(grid.get("cols"))
                relative = (
                    grid["relative_to"].value
                    if isinstance(grid.get("relative_to"), RelativeTo)
                    else grid["relative_to"]
                )
                self.relative_combo.setCurrentText(relative)
                self.tab.setCurrentIndex(0)
            except TypeError:
                self._set_corners(grid["corner1"], grid["corner2"])
                self.tab.setCurrentIndex(1)

        elif isinstance(grid, AnyGridPlan):
            self.overlap_spinbox.value(AnyGridPlan.overlap)
            self.ordermode_combo.setCurrentText(AnyGridPlan.order_mode.value)
            if isinstance(grid, GridRelative):
                self.n_rows.setValue(GridRelative.rows)
                self.n_columns.setValue(GridRelative.cols)
                self.relative_combo.setCurrentText(GridRelative.relative_to.value)
            elif isinstance(grid, GridFromCorners):
                self.corner1.set_values(
                    GridFromCorners.corner1.x, GridFromCorners.corner1.y
                )
                self.corner2.set_values(
                    GridFromCorners.corner2.x, GridFromCorners.corner2.y
                )

    def _set_corners(
        self, corner1: dict | list | tuple, corner2: dict | list | tuple
    ) -> None:
        corner1_x = corner1.get("x") if isinstance(corner1, dict) else corner1[0]
        corner1_y = corner1.get("y") if isinstance(corner1, dict) else corner1[1]
        corner2_x = corner2.get("x") if isinstance(corner2, dict) else corner2[0]
        corner2_y = corner2.get("y") if isinstance(corner2, dict) else corner2[1]
        self.corner1.set_values(corner1_x, corner1_y)
        self.corner2.set_values(corner2_x, corner2_y)

    def _send_positions_grid(self) -> AnyGridPlan:
        if self._mmc.getPixelSizeUm() <= 0:
            raise ValueError("Pixel Size Not Set.")
        self.valueChanged.emit(self.value(), self.clear_checkbox.isChecked())

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._update_info_label)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    CMMCorePlus.instance().loadSystemConfiguration()
    app = QApplication([])
    table = GridWidget()
    table.show()

    app.exec_()
