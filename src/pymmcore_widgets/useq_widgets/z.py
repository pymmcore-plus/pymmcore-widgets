import enum
from typing import TYPE_CHECKING, Literal, cast

import useq
from fonticon_mdi6 import MDI6
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon
from superqt.utils import signals_blocked

if TYPE_CHECKING:
    from PyQt6.QtGui import QAction
else:
    from qtpy.QtGui import QAction


class Mode(enum.Enum):
    TOP_BOTTOM = "top_bottom"
    RANGE_AROUND = "range_around"
    ABOVE_BELOW = "above_below"


ROW_STEPS = 0
ROW_RANGE_AROUND = 1
ROW_TOP_BOTTOM = 2
ROW_ABOVE_BELOW = 3

UM = "\u00B5m"  # MICRO SIGN
L_ARR = "\u2B05"  # LEFTWARDS BLACK ARROW


class ZPlanWidget(QWidget):
    """Widget representing a useq Zplan sequence."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # to store a "suggested" step size
        self._suggested: float | None = None

        # #################### Mode Buttons ####################
        color = "#555"

        self.mode_top_bot = QAction(
            icon(MDI6.arrow_expand_vertical, color=color), "Top/Bottom"
        )
        self.mode_top_bot.setData(Mode.TOP_BOTTOM)
        self.mode_top_bot.triggered.connect(self.setMode)

        self.mode_range = QAction(
            icon(MDI6.arrow_split_horizontal, color=color), "Range Around"
        )
        self.mode_range.setData(Mode.RANGE_AROUND)
        self.mode_range.triggered.connect(self.setMode)

        self.mode_above_below = QAction(
            icon(MDI6.arrow_expand_up, color=color), "Above/Below"
        )
        self.mode_above_below.setData(Mode.ABOVE_BELOW)
        self.mode_above_below.triggered.connect(self.setMode)

        btn_top_bot = QToolButton()
        btn_top_bot.setDefaultAction(self.mode_top_bot)
        btn_range = QToolButton()
        btn_range.setDefaultAction(self.mode_range)
        button_above_below = QToolButton()
        button_above_below.setDefaultAction(self.mode_above_below)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_top_bot)
        btn_layout.addWidget(btn_range)
        btn_layout.addWidget(button_above_below)
        btn_layout.addStretch()

        # #################### Value Widgets ####################

        self.top = QDoubleSpinBox()
        self.top.setRange(-10_000, 10_000)
        self.top.setSingleStep(0.1)
        self.top.setDecimals(3)
        self.top.setValue(0)

        self.bottom = QDoubleSpinBox()
        self.bottom.setRange(-10_000, 10_000)
        self.bottom.setSingleStep(0.1)
        self.bottom.setDecimals(3)
        self.bottom.setValue(0)

        self.step = QDoubleSpinBox()
        self.step.setRange(0, 1000)
        self.step.setSingleStep(0.1)
        self.step.setDecimals(3)
        self.step.setSpecialValueText("N/A")
        self.step.setValue(0)

        self.steps = QSpinBox()
        self.steps.setRange(0, 1000)
        self.steps.setValue(1)
        self.steps.setSpecialValueText("N/A")
        self.steps.setValue(0)

        self.range = QDoubleSpinBox()
        self.range.setRange(-10_000, 10_000)
        self.range.setSingleStep(0.1)
        self.range.setDecimals(3)
        self.range.setValue(0)
        self._range_div2_lbl = QLabel("")  # shows +/- range

        self.above = QDoubleSpinBox()
        self.above.setRange(0, 10_000)
        self.above.setSingleStep(0.1)
        self.above.setDecimals(3)
        self.above.setValue(0)

        self.below = QDoubleSpinBox()
        self.below.setRange(0, 10_000)
        self.below.setSingleStep(0.1)
        self.below.setDecimals(3)
        self.below.setValue(0)

        self.bottom_to_top = QRadioButton("Bottom to Top")
        self.top_to_bottom = QRadioButton("Top to Bottom")
        self.direction_group = QButtonGroup()
        self.direction_group.addButton(self.bottom_to_top)
        self.direction_group.addButton(self.top_to_bottom)
        self.bottom_to_top.setChecked(True)

        self.close_shutter = QCheckBox("Close shutter during move")
        self.close_shutter.setChecked(True)

        # #################### Other Widgets ####################

        self._use_suggested_btn = QPushButton()
        self._use_suggested_btn.clicked.connect(self.useSuggestedStep)
        self._use_suggested_btn.hide()

        self._range_readout = QLabel(f"Range: 1 {UM}")
        self._range_readout.setStyleSheet("QLabel { color: #666; }")

        # #################### connections ####################

        self.top.valueChanged.connect(self._on_change)
        self.bottom.valueChanged.connect(self._on_change)
        self.step.valueChanged.connect(self._on_change)
        self.range.valueChanged.connect(self._on_change)
        self.above.valueChanged.connect(self._on_change)
        self.below.valueChanged.connect(self._on_change)
        self.direction_group.buttonToggled.connect(self._on_change)
        self.close_shutter.toggled.connect(self._on_change)

        self.range.valueChanged.connect(self._on_range_changed)
        self.steps.valueChanged.connect(self._on_steps_changed)

        # #################### Grid ####################

        grid = QGridLayout()
        row = ROW_STEPS  # --------------- Steps
        grid.addWidget(QLabel("Step:"), row, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.step, row, 1)
        grid.addWidget(QLabel(UM), row, 2, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self._use_suggested_btn, row, 3, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self.steps, row, 4)
        grid.addWidget(QLabel("steps"), row, 5, Qt.AlignmentFlag.AlignLeft)
        row = ROW_RANGE_AROUND  # --------------- Range Around
        grid.addWidget(QLabel("Range:"), row, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.range, row, 1)
        grid.addWidget(QLabel(UM), row, 2, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self._range_div2_lbl, row, 3)
        grid.addWidget(QWidget(), row, 4)
        grid.addWidget(QWidget(), row, 5)
        row = ROW_TOP_BOTTOM  # --------------- Bottom / Top
        grid.addWidget(QLabel("Bottom:"), row, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.bottom, row, 1)
        grid.addWidget(QLabel(UM), row, 2, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(QLabel("Top:"), row, 3, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.top, row, 4)
        grid.addWidget(QLabel(UM), row, 5, Qt.AlignmentFlag.AlignLeft)
        row = ROW_ABOVE_BELOW  # --------------- Above / Below
        grid.addWidget(QLabel("Below:"), row, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.below, row, 1)
        grid.addWidget(QLabel(UM), row, 2, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(QLabel("Above:"), row, 3, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.above, row, 4)
        grid.addWidget(QLabel(UM), row, 5, Qt.AlignmentFlag.AlignLeft)

        grid.setColumnMinimumWidth(0, 50)
        grid.setColumnMinimumWidth(1, 95)
        grid.setColumnMinimumWidth(4, 95)
        grid.setColumnStretch(3, 20)
        self._grid_layout = grid

        # #################### Layout ####################

        # Mode Buttons
        # -----------
        # Step size selection
        # Current Mode Spin boxes
        # -----------
        # Range: 0.00 um                       x Bot to Top
        # X Close shutter during move          x Top to Bot

        left_half = QVBoxLayout()
        left_half.addWidget(self._range_readout)
        left_half.addWidget(self.close_shutter)

        direction_buttons = QVBoxLayout()
        direction_buttons.addWidget(self.bottom_to_top)
        direction_buttons.addWidget(self.top_to_bottom)

        below_grid = QHBoxLayout()
        below_grid.addLayout(left_half)
        below_grid.addStretch()
        below_grid.addWidget(QLabel("Direction:"))
        below_grid.addLayout(direction_buttons)

        layout = QVBoxLayout(self)
        layout.addLayout(btn_layout)
        layout.addLayout(self._grid_layout)
        layout.addLayout(below_grid)

        # #################### Defaults ####################

        self.setMode(Mode.ABOVE_BELOW)
        # self.setSuggestedStep(1)

    def _set_row_visible(self, idx: int, visible: bool) -> None:
        grid = cast(QGridLayout, self._grid_layout)
        for col in range(grid.columnCount()):
            if (item := grid.itemAtPosition(idx, col)) and (wdg := item.widget()):
                wdg.setVisible(visible)

    def setMode(
        self,
        mode: Mode | Literal["top_bottom", "range_around", "above_below", None] = None,
    ) -> None:
        """Set the current mode."""
        if isinstance(mode, str):
            mode = Mode(mode)
        elif isinstance(mode, (bool, type(None))):
            mode = cast("QAction", self.sender()).data()

        self._mode = cast(Mode, mode)

        if self._mode is Mode.TOP_BOTTOM:
            self._set_row_visible(ROW_RANGE_AROUND, False)
            self._set_row_visible(ROW_ABOVE_BELOW, False)
            self._set_row_visible(ROW_TOP_BOTTOM, True)

        elif self._mode is Mode.RANGE_AROUND:
            self._set_row_visible(ROW_TOP_BOTTOM, False)
            self._set_row_visible(ROW_ABOVE_BELOW, False)
            self._set_row_visible(ROW_RANGE_AROUND, True)

        elif self._mode is Mode.ABOVE_BELOW:
            self._set_row_visible(ROW_RANGE_AROUND, False)
            self._set_row_visible(ROW_TOP_BOTTOM, False)
            self._set_row_visible(ROW_ABOVE_BELOW, True)

        self._on_change()

    def setSuggestedStep(self, value: float | None) -> None:
        """Set the suggested step size and update the button text."""
        self._suggested = value
        if value:
            self._use_suggested_btn.setText(f"{L_ARR} {value} {UM}")
            self._use_suggested_btn.show()
        else:
            self._use_suggested_btn.setText("")
            self._use_suggested_btn.hide()

    def useSuggestedStep(self) -> None:
        """Apply the suggested step size to the step field."""
        if self._suggested:
            self.step.setValue(float(self._suggested))

    def _current_range(self) -> float:
        if self._mode is Mode.TOP_BOTTOM:
            return abs(self.top.value() - self.bottom.value())
        elif self._mode is Mode.RANGE_AROUND:
            return self.range.value()
        elif self._mode is Mode.ABOVE_BELOW:
            return self.above.value() + self.below.value()

    def _on_change(self) -> None:
        val = self.value()

        # update range readout
        self._range_readout.setText(f"Range: {self._current_range():.2f} {UM}")
        # update steps readout
        with signals_blocked(self.steps):
            try:
                self.steps.setValue(val.num_positions())
            except ZeroDivisionError:
                self.steps.setValue(0)

        self.valueChanged.emit(val)

    def _on_steps_changed(self, steps: int) -> None:
        self.step.setValue(self._current_range() / steps)

    def _on_range_changed(self, steps: int) -> None:
        self._range_div2_lbl.setText(f"(+/- {steps / 2:.2f} {UM})")

    def value(self) -> useq.ZAboveBelow | useq.ZRangeAround | useq.ZTopBottom:
        """Return the current value."""
        common = {"step": self.step.value(), "go_up": self.bottom_to_top.isChecked()}
        if self._mode is Mode.TOP_BOTTOM:
            return useq.ZTopBottom(
                top=self.top.value(), bottom=self.bottom.value(), **common
            )
        elif self._mode is Mode.RANGE_AROUND:
            return useq.ZRangeAround(range=self.range.value(), **common)
        elif self._mode is Mode.ABOVE_BELOW:
            return useq.ZAboveBelow(
                above=self.above.value(), below=self.below.value(), **common
            )


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    w = ZPlanWidget()
    w.show()
    w.valueChanged.connect(print)
    app.exec_()
