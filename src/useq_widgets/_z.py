from __future__ import annotations

import enum
from typing import Final, Literal

import useq
from fonticon_mdi6 import MDI6
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon
from superqt.utils import signals_blocked

from pymmcore_widgets._util import SeparatorWidget


class ZMode(enum.Enum):
    """Recognized ZPlanWidget modes."""

    TOP_BOTTOM = "top_bottom"
    RANGE_AROUND = "range_around"
    ABOVE_BELOW = "above_below"


ROW_STEPS = 0
ROW_RANGE_AROUND = 2
ROW_TOP_BOTTOM = 4
ROW_ABOVE_BELOW = 6

UM = "\u00b5m"  # MICRO SIGN


class ZPlanWidget(QWidget):
    """Widget to edit a [useq.ZPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#z-plans)."""

    valueChanged = Signal(object)

    # public widgets
    top: QDoubleSpinBox
    bottom: QDoubleSpinBox
    step: QDoubleSpinBox
    steps: QSpinBox
    range: QDoubleSpinBox
    above: QDoubleSpinBox
    below: QDoubleSpinBox
    # leave_shutter_open: QCheckBox

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # to store a "suggested" step size
        self._suggested: float | None = None

        self._mode: ZMode = ZMode.TOP_BOTTOM

        # #################### Mode Buttons ####################

        self._btn_top_bot = QRadioButton("Top/Bottom")
        self._btn_top_bot.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_top_bot.setIcon(icon(MDI6.arrow_expand_vertical))
        self._btn_top_bot.setToolTip("Mark top and bottom.")
        self._btn_range = QRadioButton("Range Around (Symmetric)")
        self._btn_range.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_range.setIcon(icon(MDI6.arrow_split_horizontal))
        self._btn_range.setToolTip("Range symmetric around reference.")
        self._button_above_below = QRadioButton("Range Asymmetric")
        self._button_above_below.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._button_above_below.setIcon(icon(MDI6.arrow_expand_up))
        self._button_above_below.setToolTip(
            "Range asymmetrically above/below reference."
        )

        self._mode_btn_group = QButtonGroup()
        self._mode_btn_group.addButton(self._btn_top_bot)
        self._mode_btn_group.addButton(self._btn_range)
        self._mode_btn_group.addButton(self._button_above_below)
        self._mode_btn_group.buttonToggled.connect(self.setMode)

        # radio buttons on the top row
        btn_wdg = QWidget()
        btn_layout = QHBoxLayout(btn_wdg)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(self._btn_top_bot, 0)
        btn_layout.addWidget(self._btn_range, 0)
        btn_layout.addWidget(self._button_above_below, 1)

        # FIXME: On Windows 11, buttons within an inner widget of a ScrollArea
        # are filled in with the accent color, making it very difficult to see
        # which radio button is checked. This HACK solves the issue. It's
        # likely future Qt versions will fix this.
        btn_wdg.setStyleSheet("QRadioButton {color: none}")

        # #################### Value Widgets ####################

        # all the widgets live in this top widget, with mode buttons that switch
        # visibility of the various rows.  This was done to make the public API
        # a bit simpler... we give direct access to these widgets.

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
        self.step.setSingleStep(0.125)
        self.step.setDecimals(3)
        self.step.setSpecialValueText("N/A")
        self.step.setValue(1)

        self.steps = QSpinBox()
        self.steps.setRange(0, 1000)
        self.steps.setValue(1)
        self.steps.setSpecialValueText("N/A")
        self.steps.setValue(0)

        self.range = QDoubleSpinBox()
        self.range.setRange(0, 10_000)
        self.range.setSingleStep(0.1)
        self.range.setDecimals(3)
        self.range.setValue(0)
        self.range.setSingleStep(0.5)
        self._range_div2_lbl = QLabel("")  # shows +/- range

        self.above = QDoubleSpinBox()
        self.above.setRange(0, 10_000)
        self.above.setSingleStep(0.1)
        self.above.setDecimals(3)
        self.above.setSingleStep(0.5)
        self.above.setPrefix("+")
        self.above.setValue(0)

        self.below = QDoubleSpinBox()
        self.below.setRange(0, 10_000)
        self.below.setSingleStep(0.1)
        self.below.setDecimals(3)
        self.below.setSingleStep(0.5)
        self.below.setPrefix("-")
        self.below.setValue(0)

        self._bottom_to_top = QRadioButton("Bottom to Top")
        self._top_to_bottom = QRadioButton("Top to Bottom")
        self._direction_group = QButtonGroup()
        self._direction_group.addButton(self._bottom_to_top)
        self._direction_group.addButton(self._top_to_bottom)
        self._bottom_to_top.setChecked(True)

        # #################### Other Widgets ####################

        self._use_suggested_btn = QPushButton()
        self._use_suggested_btn.setIcon(icon(MDI6.arrow_left_thick))
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
        self._direction_group.buttonToggled.connect(self._on_change)
        # self.leave_shutter_open.toggled.connect(self._on_change)

        self.range.valueChanged.connect(self._on_range_changed)
        self.steps.valueChanged.connect(self._on_steps_changed)

        # #################### Grid ####################
        self._grid_layout = grid = QGridLayout()
        row = ROW_STEPS  # --------------- Step size parameters
        grid.addWidget(QLabel("Step:"), row, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.step, row, 1)
        grid.addWidget(QLabel(UM), row, 2, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self._use_suggested_btn, row, 3, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self.steps, row, 4)
        grid.addWidget(QLabel("steps"), row, 5, Qt.AlignmentFlag.AlignLeft)
        row = ROW_RANGE_AROUND  # --------------- Range Around parameters
        grid.addWidget(QLabel("Range:"), row, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.range, row, 1)
        grid.addWidget(QLabel(UM), row, 2, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self._range_div2_lbl, row, 3, 1, 3)
        row = ROW_TOP_BOTTOM  # --------------- Bottom / Top parameters
        grid.addWidget(QLabel("Bottom:"), row, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.bottom, row, 1)
        grid.addWidget(QLabel(UM), row, 2, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(QLabel("Top:"), row, 3, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.top, row, 4)
        grid.addWidget(QLabel(UM), row, 5, Qt.AlignmentFlag.AlignLeft)
        row = ROW_ABOVE_BELOW  # --------------- Above / Below parameters
        grid.addWidget(QLabel("Below:"), row, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.below, row, 1)
        grid.addWidget(QLabel(UM), row, 2, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(QLabel("Above:"), row, 3, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.above, row, 4)
        grid.addWidget(QLabel(UM), row, 5, Qt.AlignmentFlag.AlignLeft)

        # these hard-coded values make it so that the grid is not resized when the
        # various rows are hidden/shown
        grid.setColumnMinimumWidth(0, 50)
        grid.setColumnMinimumWidth(1, 95)
        grid.setColumnMinimumWidth(4, 95)
        grid.setColumnStretch(3, 20)

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

        right_half = QVBoxLayout()
        right_half.addWidget(self._bottom_to_top)
        right_half.addWidget(self._top_to_bottom)

        below_grid = QHBoxLayout()
        below_grid.addLayout(left_half)
        below_grid.addStretch()
        below_grid.addWidget(QLabel("Direction:"))
        below_grid.addLayout(right_half)

        layout = QVBoxLayout(self)
        layout.addWidget(btn_wdg)
        layout.addWidget(SeparatorWidget())
        layout.addLayout(self._grid_layout)
        layout.addStretch()
        layout.addLayout(below_grid)

        # #################### Defaults ####################

        self.setMode(ZMode.TOP_BOTTOM)

    # ------------------------- Public API -------------------------

    def setMode(
        self,
        mode: ZMode | Literal["top_bottom", "range_around", "above_below"],
    ) -> None:
        """Set the current mode.

        One of "top_bottom", "range_around", or "above_below".

        Parameters
        ----------
        mode : Mode | Literal["top_bottom", "range_around", "above_below"] | None
            The mode to set. By default, None.
            If None, the mode is determined by the sender().data(), for internal usage.
        """
        if isinstance(mode, QRadioButton):
            btn_map: dict[QAbstractButton, ZMode] = {
                self._btn_top_bot: ZMode.TOP_BOTTOM,
                self._btn_range: ZMode.RANGE_AROUND,
                self._button_above_below: ZMode.ABOVE_BELOW,
            }
            self._mode = btn_map[mode]
        elif isinstance(mode, str):
            self._mode = ZMode(mode)
        else:
            self._mode = mode

        if self._mode is ZMode.TOP_BOTTOM:
            with signals_blocked(self._mode_btn_group):
                self._btn_top_bot.setChecked(True)
            self._set_row_visible(ROW_RANGE_AROUND, False)
            self._set_row_visible(ROW_ABOVE_BELOW, False)
            self._set_row_visible(ROW_TOP_BOTTOM, True)

        elif self._mode is ZMode.RANGE_AROUND:
            with signals_blocked(self._mode_btn_group):
                self._btn_range.setChecked(True)
            self._set_row_visible(ROW_TOP_BOTTOM, False)
            self._set_row_visible(ROW_ABOVE_BELOW, False)
            self._set_row_visible(ROW_RANGE_AROUND, True)

        elif self._mode is ZMode.ABOVE_BELOW:
            with signals_blocked(self._mode_btn_group):
                self._button_above_below.setChecked(True)
            self._set_row_visible(ROW_RANGE_AROUND, False)
            self._set_row_visible(ROW_TOP_BOTTOM, False)
            self._set_row_visible(ROW_ABOVE_BELOW, True)

        self._on_change()

    def mode(self) -> ZMode:
        """Return the current mode.

        One of "top_bottom", "range_around", or "above_below".
        """
        return self._mode

    def setSuggestedStep(self, value: float | None) -> None:
        """Set the suggested z step size and update the button text."""
        self._suggested = value
        if value:
            self._use_suggested_btn.setText(f"{value} {UM}")
            self._use_suggested_btn.show()
        else:
            self._use_suggested_btn.setText("")
            self._use_suggested_btn.hide()

    def suggestedStep(self) -> float | None:
        """Return suggested z step size."""
        return float(self._suggested) if self._suggested else None

    def useSuggestedStep(self) -> None:
        """Apply the suggested z step size to the step field."""
        if self._suggested:
            self.step.setValue(float(self._suggested))

    def value(self) -> useq.ZAboveBelow | useq.ZRangeAround | useq.ZTopBottom | None:
        """Return the current value of the widget as a [useq.ZPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#z-plans).

        Returns
        -------
        useq.ZAboveBelow | useq.ZRangeAround | useq.ZTopBottom | None
        The current [useq.ZPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#z-plans)
        value of the widget.
        """
        if self.step.value() == 0:
            return None

        common = {"step": self.step.value(), "go_up": self._bottom_to_top.isChecked()}
        if self._mode is ZMode.TOP_BOTTOM:
            return useq.ZTopBottom(
                top=round(self.top.value(), 4),
                bottom=round(self.bottom.value(), 4),
                **common,
            )
        elif self._mode is ZMode.RANGE_AROUND:
            return useq.ZRangeAround(range=round(self.range.value(), 4), **common)
        elif self._mode is ZMode.ABOVE_BELOW:
            return useq.ZAboveBelow(
                above=round(self.above.value(), 4),
                below=round(self.below.value(), 4),
                **common,
            )

    def setValue(
        self, value: useq.ZAboveBelow | useq.ZRangeAround | useq.ZTopBottom
    ) -> None:
        """Set the current value of the widget from a [useq.ZPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#z-plans).

        Parameters
        ----------
        value : useq.ZAboveBelow | useq.ZRangeAround | useq.ZTopBottom
            The
            [useq.ZPlan](https://pymmcore-plus.github.io/useq-schema/schema/axes/#z-plans)
            to set.
        """
        if isinstance(value, useq.ZTopBottom):
            self.top.setValue(value.top)
            self.bottom.setValue(value.bottom)
            self.setMode(ZMode.TOP_BOTTOM)
        elif isinstance(value, useq.ZRangeAround):
            self.range.setValue(value.range)
            self.setMode(ZMode.RANGE_AROUND)
        elif isinstance(value, useq.ZAboveBelow):
            self.above.setValue(value.above)
            self.below.setValue(value.below)
            self.setMode(ZMode.ABOVE_BELOW)
        else:
            raise TypeError(f"Invalid value type: {type(value)}")

        self.step.setValue(value.step)
        self._bottom_to_top.setChecked(value.go_up)

    def isGoUp(self) -> bool:
        """Return True if the acquisition direction is up (bottom to top)."""
        return self._bottom_to_top.isChecked()  # type: ignore

    def setGoUp(self, up: bool) -> None:
        """Set the acquisition direction."""
        self._bottom_to_top.setChecked(up)
        self._top_to_bottom.setChecked(not up)

    def currentZRange(self) -> float:
        """Return the current Z range in microns."""
        if self._mode is ZMode.TOP_BOTTOM:
            return abs(self.top.value() - self.bottom.value())  # type: ignore
        elif self._mode is ZMode.RANGE_AROUND:
            return self.range.value()  # type: ignore
        else:  # _Mode.ABOVE_BELOW
            return self.above.value() + self.below.value()  # type: ignore

    Mode: Final[type[ZMode]] = ZMode

    # ------------------------- Private API -------------------------

    def _on_change(self, update_steps: bool = True) -> None:
        """Called when any of the widgets change."""
        val = self.value()

        # update range readout
        self._range_readout.setText(f"Range: {self.currentZRange():.2f} {UM}")
        # update steps readout
        if update_steps:
            with signals_blocked(self.steps):
                if val is None:
                    self.steps.setValue(0)
                else:
                    self.steps.setValue(val.num_positions())

        self.valueChanged.emit(val)

    def _on_steps_changed(self, steps: int) -> None:
        if steps:
            with signals_blocked(self.step):
                self.step.setValue(self.currentZRange() / steps)
        self._on_change(update_steps=False)

    def _on_range_changed(self, steps: int) -> None:
        self._range_div2_lbl.setText(f"(+/- {steps / 2:.2f} {UM})")

    def _set_row_visible(self, idx: int, visible: bool) -> None:
        grid = self._grid_layout
        for col in range(grid.columnCount()):
            if (item := grid.itemAtPosition(idx, col)) and (wdg := item.widget()):
                wdg.setVisible(visible)
