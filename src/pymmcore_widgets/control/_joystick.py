from __future__ import annotations

import math
from typing import TYPE_CHECKING

from qtpy.QtCore import QPointF, QSize, Qt, QTimer, Signal
from qtpy.QtGui import QBrush, QColor, QPainter, QPen, QRadialGradient
from qtpy.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from pymmcore_widgets.control._q_stage_controller import QStageMoveAccumulator

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtGui import QMouseEvent, QPaintEvent


class JoystickWidget(QWidget):
    """Virtual joystick pad. Emits normalized (dx, dy) in [-1, 1]."""

    # TODO: arrow-key / accessibility support

    deflectionChanged = Signal(float, float)  # dx, dy normalized
    released = Signal()

    def __init__(self, parent: QWidget | None = None, dead_zone: float = 0.05):
        super().__init__(parent)
        self._dead_zone = dead_zone
        self._knob_pos = QPointF(0, 0)  # relative to center, in pixels
        self._dragging = False
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # ---- geometry helpers ----

    def sizeHint(self) -> QSize:
        return QSize(140, 140)

    @property
    def _radius(self) -> float:
        """Radius of the usable pad area."""
        return float(min(self.width(), self.height())) / 2 - 6

    @property
    def _knob_radius(self) -> float:
        return self._radius * 0.12

    @property
    def _center(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    def _clamp_to_circle(self, pos: QPointF) -> QPointF:
        """Clamp a point (relative to center) to the pad radius."""
        r = self._radius - self._knob_radius
        dist = math.hypot(pos.x(), pos.y())
        if dist > r:
            scale = r / dist
            return QPointF(pos.x() * scale, pos.y() * scale)
        return pos

    def _normalized(self) -> tuple[float, float]:
        r = self._radius - self._knob_radius
        if r <= 0:
            return (0.0, 0.0)
        dx = self._knob_pos.x() / r
        dy = -self._knob_pos.y() / r
        mag = math.hypot(dx, dy)
        if mag < self._dead_zone:
            return (0.0, 0.0)
        # remap [dead_zone, 1] → [0, 1] so there's no jump at the edge
        scale = (mag - self._dead_zone) / (1.0 - self._dead_zone) / mag
        return (dx * scale, dy * scale)

    # ---- mouse handling ----

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._update_knob(ev.position())
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        if self._dragging:
            self._update_knob(ev.position())
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._knob_pos = QPointF(0, 0)
            self.update()
            self.deflectionChanged.emit(0.0, 0.0)
            self.released.emit()
        super().mouseReleaseEvent(ev)

    def _update_knob(self, global_pos: QPointF) -> None:
        rel = global_pos - self._center
        self._knob_pos = self._clamp_to_circle(rel)
        self.update()
        dx, dy = self._normalized()
        self.deflectionChanged.emit(dx, dy)

    # ---- painting ----

    def paintEvent(self, ev: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self._center
        radius = self._radius
        pal = self.palette()

        # background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0)))
        p.drawRect(self.rect())

        # outer ring
        ring_color = pal.mid().color()
        p.setPen(QPen(ring_color, 2))
        bg = pal.dark().color()
        bg.setAlpha(180)
        p.setBrush(QBrush(bg))
        p.drawEllipse(center, radius, radius)

        # crosshair
        cross = pal.mid().color()
        cross.setAlpha(120)
        p.setPen(QPen(cross, 1, Qt.PenStyle.DashLine))
        p.drawLine(center + QPointF(-radius, 0), center + QPointF(radius, 0))
        p.drawLine(center + QPointF(0, -radius), center + QPointF(0, radius))

        # knob
        knob_center = center + self._knob_pos
        kr = self._knob_radius
        grad = QRadialGradient(knob_center, kr)
        if self._dragging:
            grad.setColorAt(0, QColor(100, 180, 255))
            grad.setColorAt(1, QColor(40, 100, 200))
        else:
            fg = pal.windowText().color()
            fg.setAlpha(200)
            grad.setColorAt(0, fg)
            fg.setAlpha(120)
            grad.setColorAt(1, fg)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(knob_center, kr, kr)

        p.end()


class StageJoystick(QWidget):
    """Joystick widget that drives an XY stage via QStageMoveAccumulator."""

    # TODO: Z support via vertical slider or modifier-key+drag for focus.
    # QStageMoveAccumulator already supports single-axis StageDevice.

    def __init__(
        self,
        xy_device: str,
        mmcore: CMMCorePlus | None = None,
        max_um_per_sec: float = 500.0,
        speed_exponent: float = 2.0,
        tick_ms: int = 50,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._acc = QStageMoveAccumulator.for_device(xy_device, mmcore)
        self._max_speed = max_um_per_sec
        self._speed_exponent = speed_exponent
        self._tick_ms = tick_ms
        self._dx = 0.0
        self._dy = 0.0

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(tick_ms)
        self._tick_timer.timeout.connect(self._on_tick)

        self._joystick = JoystickWidget(self)
        self._joystick.deflectionChanged.connect(self._on_deflection)
        self._joystick.released.connect(self._on_release)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._joystick)

    @property
    def max_um_per_sec(self) -> float:
        return self._max_speed

    @max_um_per_sec.setter
    def max_um_per_sec(self, value: float) -> None:
        self._max_speed = value

    @property
    def speed_exponent(self) -> float:
        return self._speed_exponent

    @speed_exponent.setter
    def speed_exponent(self, value: float) -> None:
        self._speed_exponent = value

    def _on_deflection(self, dx: float, dy: float) -> None:
        self._dx = dx
        self._dy = dy
        if not self._tick_timer.isActive() and (dx or dy):
            self._tick_timer.start()

    def _on_release(self) -> None:
        self._tick_timer.stop()

    def _on_tick(self) -> None:
        mag = min(math.hypot(self._dx, self._dy), 1.0)
        if mag < 0.05:
            return
        speed = mag**self._speed_exponent * self._max_speed
        ux, uy = self._dx / mag, self._dy / mag
        dt = self._tick_ms / 1000.0
        self._acc.move_relative((ux * speed * dt, uy * speed * dt))
