from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING, Any, Mapping, cast

from qtpy.QtCore import QRect, QRectF, Qt
from qtpy.QtGui import QColor, QLinearGradient, QPainter
from qtpy.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from typing import TypeAlias

    from pymmcore_plus.mda import MDARunner
    from PySide6.QtCore import QTimerEvent
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
            # by using <=, the first chunk will be drawn as complete
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


class MDAProgress(QWidget):
    def __init__(
        self, runner: MDARunner | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._t0: float = 0.0
        self._sizes: dict[str, int] = {}
        self._runner: MDARunner | None = runner
        self.connect_runner(runner)

        self._progress_widget = MultiDimensionProgressWidget()
        prog_group = QGroupBox("Sequence Progress", self)
        prog_group.setLayout(QVBoxLayout())
        prog_group.layout().addWidget(self._progress_widget)

        self._status = QLabel("Idle")
        status = QGroupBox("Status", self)
        status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        status.setLayout(QHBoxLayout())
        status.layout().addWidget(self._status)

        self._elapsed_time = QLabel("Time elapsed: 0:00:00")
        self._remaining_time = QLabel("Time remaining: 0:00:00")
        time_row = QHBoxLayout()
        time_row.addWidget(self._elapsed_time)
        time_row.addWidget(self._remaining_time)

        self._pause_button = QPushButton("Pause")
        self._abort_button = QPushButton("Abort")
        self._pause_button.clicked.connect(self._on_pause_clicked)
        self._abort_button.clicked.connect(self._on_abort_clicked)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._pause_button)
        btn_row.addWidget(self._abort_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.addWidget(prog_group)
        layout.addLayout(time_row)
        layout.addWidget(status)
        layout.addLayout(btn_row)

    def _on_pause_clicked(self) -> None:
        if self._runner is not None:
            self._runner.toggle_pause()

    def _on_abort_clicked(self) -> None:
        if self._runner is None:
            return

        # pause if not already paused while we ask the user
        if not (was_paused := self._runner.is_paused()):
            self._runner.toggle_pause()

        msg = QMessageBox.warning(
            self,
            "Abort Sequence",
            "Are you sure you want to abort the sequence?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        if msg == QMessageBox.StandardButton.Ok:
            self._runner.cancel()
            return

        if not was_paused:
            # resume
            self._runner.toggle_pause()

    def disconnect_runner(self) -> None:
        runner, self._runner = self._runner, None
        if runner is None:
            return

        runner.events.sequenceStarted.disconnect(self._on_sequence_started)
        runner.events.sequencePauseToggled.disconnect(self._on_sequence_pause_toggled)
        runner.events.sequenceFinished.disconnect(self._on_sequence_finished)
        runner.events.frameReady.disconnect(self._on_frame)

        if hasattr(runner.events, "awaitingEvent"):
            runner.events.awaitingEvent.disconnect(self._on_awaiting_event)
        if hasattr(runner.events, "eventStarted"):
            runner.events.eventStarted.disconnect(self._on_event_started)

    def connect_runner(self, runner: MDARunner | None) -> None:
        self.disconnect_runner()
        self._runner = runner
        if runner is None:
            return

        runner.events.sequenceStarted.connect(self._on_sequence_started)
        runner.events.sequencePauseToggled.connect(self._on_sequence_pause_toggled)
        runner.events.sequenceFinished.connect(self._on_sequence_finished)
        runner.events.frameReady.connect(self._on_frame)

        if hasattr(runner.events, "awaitingEvent"):
            runner.events.awaitingEvent.connect(self._on_awaiting_event)
        if hasattr(runner.events, "eventStarted"):
            runner.events.eventStarted.connect(self._on_event_started)

    def _on_sequence_started(self, seq: useq.MDASequence) -> None:
        self._t0 = time.perf_counter()
        self._sizes = seq.sizes
        if seq.sizes:
            self._progress_widget.add_dimensions(seq.sizes)
        self.startTimer(1)

    def timerEvent(self, event: QTimerEvent) -> None:
        elapsed = time.perf_counter() - self._t0
        msg = "Time elapsed: " + time.strftime("%H:%M:%S", time.gmtime(elapsed))
        self._elapsed_time.setText(msg)

    def _on_sequence_pause_toggled(self, paused: bool) -> None:
        if self._runner is not None:
            if self._runner.is_paused():
                self._pause_button.setText("Resume")
            else:
                self._pause_button.setText("Pause")

    def _on_sequence_finished(self, seq: useq.MDASequence) -> None:
        pass

    def _on_awaiting_event(self, event: useq.MDAEvent, remaining_sec: float) -> None:
        pass

    def _on_event_started(self, event: useq.MDAEvent) -> None:
        pass

    def _on_frame(self, _ary: Any, event: useq.MDAEvent) -> None:
        self._progress_widget.set_progress(event.index)


if __name__ == "__main__":
    import useq
    from pymmcore_plus import CMMCorePlus

    app = QApplication(sys.argv)

    widget = MDAProgress()
    widget.resize(600, 150)
    widget.show()

    core = CMMCorePlus()
    core.loadSystemConfiguration()
    core.setExposure(100)

    widget.connect_runner(core.mda)

    seq = useq.MDASequence(
        time_plan=useq.TIntervalLoops(interval=0.1, loops=20),
        channels=["DAPI", "FITC"],
        stage_positions=[(0, 0), (100, 100), (200, 200)],
        z_plan=useq.ZRangeAround(range=10, step=2),
        axis_order="tpzc",
    )

    core.run_mda(seq)

    sys.exit(app.exec())
