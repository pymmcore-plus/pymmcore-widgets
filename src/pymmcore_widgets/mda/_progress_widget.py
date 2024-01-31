from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Mapping
from PyQt6.QtCore import QSize

from qtpy.QtCore import QRectF, Qt
from qtpy.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen
from qtpy.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QLabel,
    QSizePolicy,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from PyQt6.QtGui import QResizeEvent

    ColorLike = Qt.GlobalColor | QColor | int | str


class DimensionBar(QGraphicsRectItem):
    """A single dimension bar in the MultiDimensionProgressWidget."""

    def __init__(
        self,
        label: str,
        total: int,
        color_pending: ColorLike = "#587BB5",
        color_complete: ColorLike = "#AD9B50",
        max_chunk_width: float | None = 45,
        padding: int = 2,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)

        # these are public attributes
        # not bothering with getters/setters to match Qt-style here.
        self.label = label
        self.total = total
        self.color_pending = color_pending  # type: ignore
        self.color_complete = color_complete  # type: ignore

        self.max_chunk_width = max_chunk_width
        self._current_value = 0
        self.padding = padding

        self.border_color = QColor("white")
        self.background_color = QColor("#E6E6E6")

    @property
    def color_pending(self) -> QColor:
        """Color of chunks that have not been completed yet."""
        return self._color_pending

    @color_pending.setter
    def color_pending(self, color: ColorLike) -> None:
        self._color_pending = QColor(color)

    @property
    def color_complete(self) -> QColor:
        """Color of chunks that have been completed."""
        return self._color_complete

    @color_complete.setter
    def color_complete(self, color: ColorLike) -> None:
        self._color_complete = QColor(color)

    def set_progress(self, value: int) -> None:
        """Set the current progress `value` (chunks completed out of self.total)."""
        self._current_value = value
        self.update()

    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        """Paint the bar."""
        # Call the parent class paint function to draw the base rectangle
        self.setBrush(QBrush(QColor(self.background_color)))
        self.setPen(QPen(QColor(self.border_color), 1))
        super().paint(painter, option, widget)
        if painter is None:
            return
        # Calculate the number of chunks to draw based on the current_units
        chunk_width = (self.rect().width() - self.padding) / self.total
        if self.max_chunk_width is not None:
            chunk_width = min(chunk_width, self.max_chunk_width)

        # color gradients for the chunks
        g_pending = QLinearGradient(0, 0, 0, 1)
        g_pending.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectMode)
        g_pending.setColorAt(0, self.color_pending.lighter(140))
        g_pending.setColorAt(1, self.color_pending.darker(120))
        g_complete = QLinearGradient(0, 0, 0, 1)
        g_complete.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectMode)
        g_complete.setColorAt(0, self.color_complete.lighter(140))
        g_complete.setColorAt(1, self.color_complete.darker(120))

        # Draw each chunk
        for i in range(self.total):
            painter.fillRect(
                QRectF(
                    self.rect().x() + i * chunk_width + self.padding,
                    self.rect().y() + self.padding + 0.5,  # seems to look better w/ 0.5
                    chunk_width - self.padding,
                    self.rect().height() - self.padding * 2,
                ),
                g_complete if i < self._current_value else g_pending,
            )


class MultiDimensionProgressWidget(QGraphicsView):
    """Widget for displaying progress across multiple dimensions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene()
        self.setScene(self._scene)
        self._dimension_bars: dict[str, DimensionBar] = {}
        self._vert_spacing = 21
        self._bar_height = self._vert_spacing - 1
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def add_dimensions(self, dimensions: dict[str, int]) -> None:
        """Add multiple dimensions at once."""
        for label, total in dimensions.items():
            self.add_dimension(label, total)

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)
        if not event:
            return
        # FIXME:
        # I'm not really sure about this logic, just a hack for now
        scene_width = event.size().width() - 20
        for i, bar in enumerate(self._dimension_bars.values()):
            bar.setRect(0, i * self._vert_spacing, scene_width - 20, self._bar_height)
        self._scene.setSceneRect(
            -30, -5, scene_width, self._bar_height * len(self._dimension_bars) + 40
        )

    def sizeHint(self) -> QSize:
        # HACK!
        hint = super().sizeHint()
        return hint.expandedTo(
            QSize(200, self._bar_height * len(self._dimension_bars) + 110)
        )

    def add_dimension(self, label: str, total: int) -> None:
        """Add a dimension to the progress view."""
        bar = DimensionBar(label, total)
        y_offset = len(self._dimension_bars) * self._vert_spacing
        bar.setRect(0, y_offset, self.width() - 40, self._bar_height)
        self._scene.addItem(bar)
        self._dimension_bars[label] = bar

        # Add label
        if not label.endswith(":"):
            label += ":"
        text = QGraphicsTextItem(label)
        text.setPos(-25, y_offset)
        self._scene.addItem(text)

    def set_progress(self, dimension_values: Mapping[str, int]) -> None:
        """Set the progress for each dimension."""
        for label, units in dimension_values.items():
            self._dimension_bars[label].set_progress(units)


app = QApplication(sys.argv)

# Create the multi-dimensional progress view
progress_view = MultiDimensionProgressWidget()

# Create the main widget
widget = QWidget()
widget.resize(600, 150)
layout = QVBoxLayout(widget)
layout.addWidget(QLabel("Progress:"))
layout.addWidget(progress_view)
layout.addWidget(QLabel("Time:"))
layout.addStretch()
widget.show()

# Add dimensions (label, color, max_units)
progress_view.add_dimensions({"T": 4, "Z": 75, "M": 10, "λ": 20})
# Example of setting progress
progress_view.set_progress({"T": 2, "M": 5, "Z": 50, "λ": 5})

sys.exit(app.exec())
