from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Mapping, cast

from qtpy.QtCore import QRect, QRectF, Qt
from qtpy.QtGui import QColor, QLinearGradient, QPainter
from qtpy.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from typing import TypeAlias

    from qtpy.QtGui import QPaintEvent

    ColorLike: TypeAlias = Qt.GlobalColor | QColor | int | str


def draw_chunks(
    painter: QPainter,
    rect: QRect | QRectF,
    total: int,
    current_value: int,
    color_pending: QColor,
    color_complete: QColor,
    max_chunk_width: float | None = None,
    padding: float = 1,
) -> None:
    # Calculate the number of chunks to draw based on the current_units
    while padding > 0:
        # this while loop allows us to collapse the padding to zero if the
        # chunks are too small
        chunk_width = (rect.width() - padding) / total
        if max_chunk_width is not None:
            chunk_width = min(chunk_width, max_chunk_width)
        if chunk_width >= (padding * 8):
            break
        padding -= 0.5

    # color gradients for the chunks
    g_pending = QLinearGradient(0, 0, 0, 1)
    g_pending.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectMode)
    g_pending.setColorAt(0, color_pending.lighter(140))
    g_pending.setColorAt(1, color_pending.darker(120))
    g_complete = QLinearGradient(0, 0, 0, 1)
    g_complete.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectMode)
    g_complete.setColorAt(0, color_complete.lighter(140))
    g_complete.setColorAt(1, color_complete.darker(120))

    # Draw each chunk
    for i in range(total):
        painter.fillRect(
            QRectF(
                rect.x() + i * chunk_width,
                rect.y() + padding + 0.5,  # seems to look better w/ 0.5
                chunk_width - padding,
                rect.height() - padding * 2,
            ),
            g_complete if i <= current_value else g_pending,
        )


# QWidgets version
class DimensionBar(QWidget):
    def __init__(
        self,
        total: int,
        color_pending: ColorLike = "#587BB5",
        color_complete: ColorLike = "#AD9B50",
        max_chunk_width: float | None = 50,
        padding: float = 1.5,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.total = total
        self.color_pending = QColor(color_pending)
        self.color_complete = QColor(color_complete)
        self._max_chunk_width = max_chunk_width
        self._current_value = 0
        self._padding = padding
        self._border_color = QColor("white")
        self._background_color = QColor("#E6E6E6")
        self.setFixedHeight(20)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        draw_chunks(
            QPainter(self),
            self.rect(),
            self.total,
            self._current_value,
            self.color_pending,
            self.color_complete,
            self._max_chunk_width,
            self._padding,
        )

    def set_progress(self, value: int) -> None:
        """Set the current progress `value` (chunks completed out of self.total)."""
        self._current_value = value
        self.update()


class MultiDimensionProgressWidget(QFrame):
    """Widget for displaying progress across multiple dimensions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dimension_bars: dict[str, DimensionBar] = {}
        self._bar_height = 20

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Raised)

        layout = QGridLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(0)
        layout.setColumnStretch(1, 1)

    def setBarHeight(self, height: int) -> None:
        self._bar_height = height
        for bar in self._dimension_bars.values():
            bar.setFixedHeight(height)

    def add_dimensions(self, dimensions: dict[str, int]) -> None:
        """Add multiple dimensions at once."""
        for label, total in dimensions.items():
            self.add_dimension(label, total)

    def add_dimension(self, label: str, total: int) -> None:
        """Add a dimension to the progress view."""
        if not total:
            return
        self._dimension_bars[label] = bar = DimensionBar(total)
        bar.setFixedHeight(self._bar_height)

        if not label.endswith(":"):
            label += ":"
        text = QLabel(label)

        layout = cast("QGridLayout", self.layout())
        layout.addWidget(text, layout.rowCount(), 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(bar, layout.rowCount() - 1, 1)

    def set_progress(self, dimension_values: Mapping[str, int]) -> None:
        """Set the progress for each dimension."""
        for label, units in dimension_values.items():
            self._dimension_bars[label].set_progress(units)


if __name__ == "__main__":
    import useq
    from pymmcore_plus import CMMCorePlus

    app = QApplication(sys.argv)

    widget = QWidget()
    widget.resize(600, 150)
    widget.show()
    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel("Progress:"))

    progress_view = MultiDimensionProgressWidget()
    layout.addWidget(progress_view)

    core = CMMCorePlus()
    core.loadSystemConfiguration()
    core.setExposure(100)
    seq = useq.MDASequence(
        time_plan=useq.TIntervalLoops(interval=0.1, loops=20),
        channels=["DAPI", "FITC"],
        stage_positions=[(0, 0), (100, 100), (200, 200)],
        z_plan=useq.ZRangeAround(range=10, step=2),
        axis_order="tpzc",
    )

    progress_view.add_dimensions(seq.sizes)

    @core.mda.events.frameReady.connect
    def _on_frame(_ary: Any, event: useq.MDAEvent) -> None:
        progress_view.set_progress(event.index)

    core.run_mda(seq)

    sys.exit(app.exec())
