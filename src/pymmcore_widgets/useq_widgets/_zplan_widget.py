"""Redesigned Z-Plan widget with visual Z-axis indicator."""

from __future__ import annotations

import enum
from typing import Literal

import useq
from qtpy.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSignalBlocker,
    Qt,
    Signal,
)
from qtpy.QtGui import QBrush, QColor, QPainter, QPen
from qtpy.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from superqt.iconify import QIconifyIcon

from pymmcore_widgets.device_properties._property_widget import LabeledSlider

try:
    from PyQt6Qlementine import SegmentedControl
except ImportError:
    from qtpy.QtWidgets import QButtonGroup

    class SegmentedControl(QWidget):  # type: ignore[no-redef]
        """Fallback segmented button control."""

        currentIndexChanged = Signal()

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self._buttons: list[QPushButton] = []
            self._group = QButtonGroup(self)
            self._group.setExclusive(True)
            self._layout = QHBoxLayout(self)
            self._layout.setContentsMargins(2, 2, 2, 2)
            self._layout.setSpacing(2)
            self._group.idToggled.connect(self._on_toggled)

        def addItem(self, text: str) -> int:
            idx = len(self._buttons)
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._buttons.append(btn)
            self._group.addButton(btn, idx)
            self._layout.addWidget(btn)
            if idx == 0:
                btn.setChecked(True)
            return idx

        def _on_toggled(self, id: int, checked: bool) -> None:
            if checked:
                self.currentIndexChanged.emit()

        def setCurrentIndex(self, idx: int) -> None:
            self._buttons[idx].setChecked(True)

        def currentIndex(self) -> int:
            return int(self._group.checkedId())


UM = "\u00b5m"


class Mode(enum.Enum):
    TOP_BOTTOM = "top_bottom"
    RANGE_AROUND = "range_around"
    ABOVE_BELOW = "above_below"


# ---------------------------------------------------------------------------
# Z-axis visualization (custom painted)
# ---------------------------------------------------------------------------


class ZStackViz(QWidget):
    """Custom-painted Z-axis stack visualization."""

    # Animated properties
    _bar_top: float = 0.5
    _bar_height: float = 0.0
    _center_frac: float = 0.5

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(110)
        self.setMaximumWidth(140)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self._mode: Mode = Mode.RANGE_AROUND
        self._n_slices: int = 1
        self._top_label: str = ""
        self._bot_label: str = ""
        self._center_label: str = ""
        self._range_label: str = ""

        # Colors
        self._accent = QColor("#3b82f6")
        self._accent_dim = QColor(59, 130, 246, 20)
        self._accent_border = QColor(59, 130, 246, 80)
        self._accent_line = QColor(96, 165, 250)
        self._center_color = QColor("#f59e0b")
        self._track_color = QColor("#3f3f46")
        self._text_color = QColor("#9ca3af")
        self._text_dim = QColor("#6b7280")

        # Animations
        self._anim_bar_top = self._make_anim(b"barTop")
        self._anim_bar_h = self._make_anim(b"barHeight")
        self._anim_center = self._make_anim(b"centerFrac")

    def _make_anim(self, prop: bytes) -> QPropertyAnimation:
        anim = QPropertyAnimation(self, prop)
        anim.setDuration(200)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        return anim

    # --- Animated properties ---

    def _get_bar_top(self) -> float:
        return self._bar_top

    def _set_bar_top(self, v: float) -> None:
        self._bar_top = v
        self.update()

    barTop = Property(float, _get_bar_top, _set_bar_top)

    def _get_bar_height(self) -> float:
        return self._bar_height

    def _set_bar_height(self, v: float) -> None:
        self._bar_height = v
        self.update()

    barHeight = Property(float, _get_bar_height, _set_bar_height)

    def _get_center_frac(self) -> float:
        return self._center_frac

    def _set_center_frac(self, v: float) -> None:
        self._center_frac = v
        self.update()

    centerFrac = Property(float, _get_center_frac, _set_center_frac)

    # --- Public API ---

    def setParams(
        self,
        *,
        mode: Mode,
        n_slices: int,
        bar_top: float,
        bar_height: float,
        center_frac: float,
        top_label: str = "",
        bot_label: str = "",
        center_label: str = "",
        range_label: str = "",
    ) -> None:
        """Update visualization parameters (fractions of track height 0..1)."""
        self._mode = mode
        self._n_slices = n_slices
        self._top_label = top_label
        self._bot_label = bot_label
        self._center_label = center_label
        self._range_label = range_label

        self._animate(self._anim_bar_top, self._bar_top, bar_top)
        self._animate(self._anim_bar_h, self._bar_height, bar_height)
        self._animate(self._anim_center, self._center_frac, center_frac)

    def _animate(self, anim: QPropertyAnimation, old: float, new: float) -> None:
        anim.stop()
        anim.setStartValue(old)
        anim.setEndValue(new)
        anim.start()

    # --- Paint ---

    def paintEvent(self, event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin_top = 22
        margin_bot = 28
        margin_right = 10
        track_h = h - margin_top - margin_bot

        # Measure label width to determine left margin
        font = p.font()
        font.setPixelSize(10)
        fm = p.fontMetrics()
        labels = [self._top_label, self._bot_label, self._center_label]
        max_chars = max((len(t) for t in labels if t), default=0)
        label_w = fm.horizontalAdvance("8" * max_chars) if max_chars else 0
        margin_left = max(label_w + 8, 22.0)

        # Center bar and track between left margin and right margin
        track_x = (margin_left + w - margin_right) / 2
        bar_x = margin_left
        bar_w = w - margin_left - margin_right

        # Track line
        p.setPen(
            QPen(self._track_color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        p.drawLine(QPointF(track_x, margin_top), QPointF(track_x, margin_top + track_h))

        # Tick marks
        p.setPen(QPen(self._track_color, 1))
        for frac in (0, 0.25, 0.5, 0.75, 1.0):
            y = margin_top + frac * track_h
            p.drawLine(QPointF(track_x - 3, y), QPointF(track_x + 3, y))

        # Bar geometry (in pixels)
        bar_y = margin_top + self._bar_top * track_h
        bar_h = self._bar_height * track_h
        center_y = margin_top + self._center_frac * track_h

        if bar_h < 2:
            p.end()
            return

        # Outer glow rect
        outer = QRectF(bar_x, bar_y, bar_w, bar_h)
        p.setPen(QPen(self._accent_border, 1))
        p.setBrush(QBrush(self._accent_dim))
        p.drawRoundedRect(outer, 4, 4)

        # Inner fill rect
        inner = outer.adjusted(3, 2, -3, -2)
        p.setPen(QPen(QColor(59, 130, 246, 30), 1))
        p.setBrush(QBrush(QColor(59, 130, 246, 25)))
        p.drawRoundedRect(inner, 2, 2)

        # Slice lines
        n = self._n_slices
        if 2 <= n <= 60:
            plane_x = bar_x + 6
            plane_w = bar_w - 12
            for i in range(n):
                frac = i / (n - 1)
                py = bar_y + 3 + frac * (bar_h - 6)
                dist = abs(frac - 0.5) * 2
                alpha = int((0.45 - dist * 0.2) * 255)
                line_color = QColor(self._accent_line)
                line_color.setAlpha(alpha)
                p.setPen(QPen(line_color, 1))
                p.drawLine(QPointF(plane_x, py), QPointF(plane_x + plane_w, py))
                # Endpoint dots
                dot_color = QColor(self._accent_line)
                dot_color.setAlpha(130)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(dot_color)
                p.drawEllipse(QPointF(plane_x, py), 1.5, 1.5)
                p.drawEllipse(QPointF(plane_x + plane_w, py), 1.5, 1.5)

        # Center marker (amber pill with glow)
        center_w = 18
        center_rect = QRectF(track_x - center_w / 2, center_y - 2, center_w, 4)
        # Glow
        glow_color = QColor(self._center_color)
        glow_color.setAlpha(60)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow_color)
        p.drawRoundedRect(center_rect.adjusted(-3, -3, 3, 3), 5, 5)
        # Solid
        p.setBrush(self._center_color)
        p.drawRoundedRect(center_rect, 2, 2)

        # Labels (font already set above for measuring)
        p.setFont(font)

        label_x = bar_x - 4  # right edge of label area
        # Slice count above bar (slightly right of track line)
        p.setPen(self._text_dim)
        p.drawText(
            QRectF(track_x + 4, bar_y - 16, bar_w / 2, 14),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
            f"{n}\u00d7",
        )
        # Top/bottom labels
        if self._top_label:
            p.setPen(self._accent_line)
            p.drawText(
                QRectF(0, bar_y - 1, label_x, 14),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
                self._top_label,
            )
        if self._bot_label:
            p.setPen(self._accent_line)
            p.drawText(
                QRectF(0, bar_y + bar_h - 13, label_x, 14),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
                self._bot_label,
            )
        # Center label
        if self._center_label:
            p.setPen(self._center_color)
            font.setWeight(font.Weight.Medium)
            p.setFont(font)
            p.drawText(
                QRectF(0, center_y - 7, label_x, 14),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                self._center_label,
            )

        # Range label at bottom
        if self._range_label:
            font.setWeight(font.Weight.Normal)
            p.setFont(font)
            p.setPen(self._text_dim)
            p.drawText(
                QRectF(0, h - 20, w, 16),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                self._range_label,
            )

        p.end()


# ---------------------------------------------------------------------------
# Main ZPlanWidget
# ---------------------------------------------------------------------------

MAX_VIZ_RANGE = 50.0  # µm range that maps to full track height


class ZPlanWidget(QWidget):
    """Widget to edit a useq Z-plan with visual feedback."""

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode = Mode.TOP_BOTTOM
        self._suggested: float | None = None
        self._step_locked: bool = True  # True = step is fixed, range adjusts

        # ---- Visualization ----
        self._viz = ZStackViz()

        # ---- Mode switcher ----
        self._mode_control = SegmentedControl()
        self._mode_control.addItem("Top / Bottom")
        self._mode_control.addItem("Range")
        self._mode_control.addItem("Above / Below")
        self._mode_control.currentIndexChanged.connect(self._on_mode_changed)

        # ---- Mode panels (stacked) ----
        self._stack = QStackedWidget()

        # --- Range Around panel ---
        range_panel = QWidget()
        range_lay = QVBoxLayout(range_panel)
        range_lay.setContentsMargins(0, 0, 0, 0)
        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Range"))
        self.range = LabeledSlider(is_float=True, auto_expand=True)
        self.range.spinBox().setMaxDecimals(2)
        self.range.setRange(0, 50)
        self.range.setValue(10.0)
        range_row.addWidget(self.range, 1)
        range_lay.addLayout(range_row)
        self._range_info = QLabel()
        self._range_info.setStyleSheet("color: gray; font-size: 11px;")
        range_lay.addWidget(self._range_info)

        # --- Top/Bottom panel ---
        tb_panel = QWidget()
        tb_grid = QGridLayout(tb_panel)
        tb_grid.setContentsMargins(0, 0, 0, 0)

        self.top = QDoubleSpinBox()
        self.top.setRange(-10_000, 10_000)
        self.top.setDecimals(3)
        self.top.setSingleStep(0.1)
        self.top.setSuffix(f" {UM}")
        self._btn_mark_top = QPushButton("Mark \u2191")
        self._btn_mark_top.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_mark_top.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        tb_grid.addWidget(QLabel("Top"), 0, 0)
        tb_grid.addWidget(self.top, 0, 1)
        tb_grid.addWidget(self._btn_mark_top, 0, 2)

        self.bottom = QDoubleSpinBox()
        self.bottom.setRange(-10_000, 10_000)
        self.bottom.setDecimals(3)
        self.bottom.setSingleStep(0.1)
        self.bottom.setSuffix(f" {UM}")
        self._btn_mark_bot = QPushButton("Mark \u2193")
        self._btn_mark_bot.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_mark_bot.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        tb_grid.addWidget(QLabel("Bottom"), 1, 0)
        tb_grid.addWidget(self.bottom, 1, 1)
        tb_grid.addWidget(self._btn_mark_bot, 1, 2)

        tb_grid.setColumnStretch(1, 1)

        # --- Above/Below panel ---
        ab_panel = QWidget()
        ab_lay = QVBoxLayout(ab_panel)
        ab_lay.setContentsMargins(0, 0, 0, 0)

        above_row = QHBoxLayout()
        above_row.addWidget(QLabel("Above"))
        self.above = LabeledSlider(is_float=True, auto_expand=True)
        self.above.spinBox().setMaxDecimals(2)
        self.above.setRange(0, 50)
        self.above.setValue(5.0)
        above_row.addWidget(self.above, 1)
        ab_lay.addLayout(above_row)

        below_row = QHBoxLayout()
        below_row.addWidget(QLabel("Below"))
        self.below = LabeledSlider(is_float=True, auto_expand=True)
        self.below.spinBox().setMaxDecimals(2)
        self.below.setRange(0, 50)
        self.below.setValue(5.0)
        below_row.addWidget(self.below, 1)
        ab_lay.addLayout(below_row)

        self._stack.addWidget(tb_panel)  # index 0 = TOP_BOTTOM
        self._stack.addWidget(range_panel)  # index 1 = RANGE_AROUND
        self._stack.addWidget(ab_panel)  # index 2 = ABOVE_BELOW

        # ---- Step / Slices row ----
        step_row = QHBoxLayout()
        step_row.addWidget(QLabel("Step"))
        self.step = QDoubleSpinBox()
        self.step.setRange(0.001, 1000)
        self.step.setDecimals(3)
        self.step.setSingleStep(0.125)
        self.step.setSuffix(f" {UM}")
        self.step.setValue(1.0)
        step_row.addWidget(self.step)

        self._icon_locked = QIconifyIcon("lucide:lock-keyhole", color="white")
        self._icon_unlocked = QIconifyIcon("lucide:lock-keyhole-open", color="gray")
        self._lock_step_btn = QPushButton(self._icon_locked, "")
        self._lock_step_btn.setCheckable(True)
        self._lock_step_btn.setChecked(True)  # locked by default
        self._lock_step_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._lock_step_btn.setFixedWidth(28)
        self._lock_step_btn.setToolTip("Lock step size (slices adjust range)")
        self._lock_step_btn.toggled.connect(self._on_lock_toggled)
        step_row.addWidget(self._lock_step_btn)

        self._suggested_btn = QPushButton()
        self._suggested_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._suggested_btn.setVisible(False)
        self._suggested_btn.clicked.connect(self._use_suggested)
        step_row.addWidget(self._suggested_btn)

        step_row.addStretch()

        self.steps = QSpinBox()
        self.steps.setRange(1, 10_000)
        self.steps.setSuffix(" slices")
        self.steps.setValue(11)
        step_row.addWidget(self.steps)

        # ---- Direction toggle ----
        bottom_row = QHBoxLayout()
        self._dir_btn = QPushButton("Bottom \u2192 Top")
        self._dir_btn.setCheckable(True)
        self._dir_btn.setChecked(True)  # True = go_up
        self._dir_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._dir_btn.toggled.connect(self._on_dir_toggled)
        bottom_row.addWidget(self._dir_btn)
        bottom_row.addStretch()
        self._summary_label = QLabel()
        self._summary_label.setStyleSheet("color: gray;")
        bottom_row.addWidget(self._summary_label)

        # ---- Right-side controls layout ----
        controls = QVBoxLayout()
        controls.addWidget(self._mode_control)
        controls.addWidget(self._stack)
        controls.addStretch()
        controls.addLayout(step_row)
        controls.addLayout(bottom_row)

        # ---- Main layout: viz | controls ----
        main = QHBoxLayout(self)
        main.addWidget(self._viz)
        main.addLayout(controls, 1)

        # ---- Connections ----
        self.range.valueChanged.connect(self._on_value_changed)
        self.top.valueChanged.connect(self._on_value_changed)
        self.bottom.valueChanged.connect(self._on_value_changed)
        self.above.valueChanged.connect(self._on_value_changed)
        self.below.valueChanged.connect(self._on_value_changed)
        self.step.valueChanged.connect(self._on_value_changed)
        self.steps.valueChanged.connect(self._on_steps_edited)

        # ---- Initialize ----
        self._on_mode_changed()

    # ---- Public API (compatible with original) ----

    def mode(self) -> Mode:
        return self._mode

    def setMode(
        self, mode: Mode | Literal["top_bottom", "range_around", "above_below"]
    ) -> None:
        if isinstance(mode, str):
            mode = Mode(mode)
        self._mode = mode
        idx = {Mode.TOP_BOTTOM: 0, Mode.RANGE_AROUND: 1, Mode.ABOVE_BELOW: 2}[mode]
        with QSignalBlocker(self._mode_control):
            self._mode_control.setCurrentIndex(idx)
        self._stack.setCurrentIndex(idx)
        self._on_value_changed()

    def value(self) -> useq.ZAboveBelow | useq.ZRangeAround | useq.ZTopBottom | None:
        if self.step.value() == 0:
            return None
        common = {"step": self.step.value(), "go_up": self._dir_btn.isChecked()}
        if self._mode is Mode.TOP_BOTTOM:
            return useq.ZTopBottom(
                top=round(self.top.value(), 4),
                bottom=round(self.bottom.value(), 4),
                **common,
            )
        elif self._mode is Mode.RANGE_AROUND:
            return useq.ZRangeAround(range=round(self.range.value(), 4), **common)
        else:
            return useq.ZAboveBelow(
                above=round(self.above.value(), 4),
                below=round(self.below.value(), 4),
                **common,
            )

    def setValue(
        self, value: useq.ZAboveBelow | useq.ZRangeAround | useq.ZTopBottom
    ) -> None:
        if isinstance(value, useq.ZTopBottom):
            self.top.setValue(value.top)
            self.bottom.setValue(value.bottom)
            self.setMode(Mode.TOP_BOTTOM)
        elif isinstance(value, useq.ZRangeAround):
            self.range.setValue(value.range)
            self.setMode(Mode.RANGE_AROUND)
        elif isinstance(value, useq.ZAboveBelow):
            self.above.setValue(value.above)
            self.below.setValue(value.below)
            self.setMode(Mode.ABOVE_BELOW)
        self.step.setValue(value.step)
        self._dir_btn.setChecked(value.go_up)

    def currentZRange(self) -> float:
        if self._mode is Mode.TOP_BOTTOM:
            return float(abs(self.top.value() - self.bottom.value()))
        elif self._mode is Mode.RANGE_AROUND:
            return float(self.range.value())
        else:
            return float(self.above.value() + self.below.value())

    def isGoUp(self) -> bool:
        return bool(self._dir_btn.isChecked())

    def setGoUp(self, up: bool) -> None:
        self._dir_btn.setChecked(up)

    def setSuggestedStep(self, value: float | None) -> None:
        self._suggested = value
        if value:
            self._suggested_btn.setText(f"\u2190 {value} {UM}")
            self._suggested_btn.setVisible(True)
        else:
            self._suggested_btn.setVisible(False)

    def suggestedStep(self) -> float | None:
        return float(self._suggested) if self._suggested else None

    # ---- Private ----

    def _on_mode_changed(self) -> None:
        idx = self._mode_control.currentIndex()
        mode_map = {0: Mode.TOP_BOTTOM, 1: Mode.RANGE_AROUND, 2: Mode.ABOVE_BELOW}
        self._mode = mode_map[idx]
        self._stack.setCurrentIndex(idx)
        self._on_value_changed()

    def _on_dir_toggled(self, checked: bool) -> None:
        self._dir_btn.setText("Bottom \u2192 Top" if checked else "Top \u2192 Bottom")
        self._on_value_changed()

    def _use_suggested(self) -> None:
        if self._suggested:
            self.step.setValue(self._suggested)

    def _on_lock_toggled(self, locked: bool) -> None:
        self._step_locked = locked
        self._lock_step_btn.setIcon(
            self._icon_locked if locked else self._icon_unlocked
        )
        self._lock_step_btn.setToolTip(
            "Lock step size (slices adjust range)"
            if locked
            else "Unlock step size (slices adjust step)"
        )

    def _on_value_changed(self) -> None:
        z_range = self.currentZRange()
        step = self.step.value()
        slices = max(1, round(z_range / step) + 1) if step > 0 else 1

        with QSignalBlocker(self.steps):
            self.steps.setValue(slices)

        self._update_display()
        self.valueChanged.emit(self.value())

    def _on_steps_edited(self, steps: int) -> None:
        """When the user directly edits the steps spinbox."""
        if self._step_locked:
            # Step is fixed, adjust range to match
            step_val = self.step.value()
            new_range = step_val * (steps - 1) if steps > 1 else 0
            self._set_range_from_slices(new_range)
        else:
            # Range is fixed, adjust step to match
            z_range = self.currentZRange()
            if steps > 1 and z_range > 0:
                with QSignalBlocker(self.step):
                    self.step.setValue(z_range / (steps - 1))
        self._update_display()
        self.valueChanged.emit(self.value())

    def _set_range_from_slices(self, new_range: float) -> None:
        """Set the range/above/below widgets to match a desired total range."""
        if self._mode is Mode.RANGE_AROUND:
            with QSignalBlocker(self.range):
                self.range.setValue(new_range)
        elif self._mode is Mode.TOP_BOTTOM:
            mid = (self.top.value() + self.bottom.value()) / 2
            with QSignalBlocker(self.top), QSignalBlocker(self.bottom):
                self.top.setValue(mid + new_range / 2)
                self.bottom.setValue(mid - new_range / 2)
        else:  # ABOVE_BELOW
            above_val = self.above.value()
            below_val = self.below.value()
            total = above_val + below_val
            if total > 0:
                ratio = above_val / total
            else:
                ratio = 0.5
            with QSignalBlocker(self.above), QSignalBlocker(self.below):
                self.above.setValue(new_range * ratio)
                self.below.setValue(new_range * (1 - ratio))

    def _update_display(self) -> None:
        """Update labels, summary, and visualization from current state."""
        z_range = self.currentZRange()
        slices = self.steps.value()

        # Update info labels
        if self._mode is Mode.RANGE_AROUND:
            half = z_range / 2
            self._range_info.setText(f"\u00b1{half:.2f} {UM} from center")

        self._summary_label.setText(
            f"{slices} slice{'s' if slices != 1 else ''} \u00b7 {z_range:.2f} {UM}"
        )

        # Update visualization
        frac = min(z_range / MAX_VIZ_RANGE, 0.92) if z_range > 0 else 0
        center_frac = 0.5
        bar_top = 0.5 - frac / 2

        if self._mode is Mode.ABOVE_BELOW:
            a, b = self.above.value(), self.below.value()
            total = a + b
            if total > 0:
                above_frac = a / total
                bar_top = center_frac - above_frac * frac
                bar_top = max(0, min(1 - frac, bar_top))
                center_frac = bar_top + above_frac * frac

        # Build labels per mode
        if self._mode is Mode.RANGE_AROUND:
            half = z_range / 2
            top_lbl = f"+{half:.1f}"
            bot_lbl = f"\u2212{half:.1f}"
            ctr_lbl = "0"
        elif self._mode is Mode.TOP_BOTTOM:
            top_lbl = f"{self.top.value():.1f}"
            bot_lbl = f"{self.bottom.value():.1f}"
            ctr_lbl = ""
        else:
            top_lbl = f"+{self.above.value():.1f}"
            bot_lbl = f"\u2212{self.below.value():.1f}"
            ctr_lbl = "0"

        self._viz.setParams(
            mode=self._mode,
            n_slices=slices,
            bar_top=bar_top,
            bar_height=frac,
            center_frac=center_frac,
            top_label=top_lbl,
            bot_label=bot_lbl,
            center_label=ctr_lbl,
            range_label=f"{z_range:.2f} {UM}",
        )


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    w = ZPlanWidget()
    w.setSuggestedStep(0.5)
    w.setWindowTitle("Z-Plan")
    w.resize(480, 280)
    w.show()
    w.valueChanged.connect(lambda v: print(v))
    sys.exit(app.exec())
