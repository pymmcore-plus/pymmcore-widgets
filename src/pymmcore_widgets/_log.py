from __future__ import annotations

import os
from collections import deque
from contextlib import suppress
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from PyQt6.QtCore import QSize, QTimerEvent
from qtpy.QtCore import QFileSystemWatcher, QObject, QTimer, QUrl, Signal
from qtpy.QtGui import QCloseEvent, QDesktopServices, QFontDatabase, QPalette
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from superqt import QElidingLabel, QIconifyIcon

if TYPE_CHECKING:
    from io import TextIOWrapper


class _LogReader(QObject):
    """Watches a log file and emits new lines as they arrive."""

    new_lines: Signal = Signal(str)
    finished: Signal = Signal()

    def __init__(
        self,
        path: str,
        interval: int = 200,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._interval = interval
        self._file: TextIOWrapper | None = None

        # Unfortunately, on Windows, QFileSystemWatcher does not detect file changes
        # unless the file is flushed from cache to disk. This does NOT happen
        # when CMMCorePlus.logMessage() is called. So we need to poll the file for
        # Windows' sake.
        self._timer_id: int | None = None

        # Watcher for rotation/truncate events
        self._watcher = QFileSystemWatcher(self)
        self._watcher.addPath(self._path)
        self._watcher.fileChanged.connect(self._on_file_changed)

    def __del__(self) -> None:
        """Ensure file is closed when object is deleted."""
        with suppress(RuntimeError):
            self._stop()

    def timerEvent(self, event: QTimerEvent | None) -> None:
        if event and event.timerId() == self._timer_id:
            self._read_new()

    def start(self) -> None:
        """Open the file and start polling."""
        if self._timer_id is None:
            self._file = open(self._path, encoding="utf-8", errors="replace")
            self._file.seek(0, os.SEEK_END)
            self._timer_id = self.startTimer(self._interval)

    def _stop(self) -> None:
        """Stop polling and close the file."""
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None
        if self._file is not None:
            with suppress(Exception):
                self._file.close()
            self._file = None
        self.finished.emit()

    def _on_file_changed(self, path: str) -> None:
        """Handle log rotation or truncation."""
        try:
            real_size = os.path.getsize(path)
            current_pos = self._file.tell() if self._file else 0
            if real_size < current_pos:
                # rotated or truncated
                if self._file:
                    self._file.close()
                self._file = open(self._path, encoding="utf-8", errors="replace")
            self._read_new()
        except Exception:
            pass

    def _read_new(self) -> None:
        """Read and emit any new lines."""
        if not self._file:
            return
        for line in self._file:
            self.new_lines.emit(line.rstrip("\n"))


class CoreLogWidget(QWidget):
    """High-performance log console with pause, follow-tail, clear, and initial load."""

    def __init__(
        self,
        path: str | None = None,
        max_lines: int = 5_000,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent)
        self._mmcore = mmcore or CMMCorePlus().instance()
        self.setWindowTitle("Log Console")

        # --- Log path ---
        self._log_path = QElidingLabel()
        self._log_path.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )

        self._clear_btn = QPushButton("Clear Display")
        self._clear_btn.setToolTip(
            "Clears this view. Does not delete lines from the log file."
        )

        self._log_btn = QPushButton()
        color = QApplication.palette().color(QPalette.ColorRole.WindowText).name()
        self._log_btn.setIcon(QIconifyIcon("majesticons:open", color=color))
        self._log_btn.setToolTip("Open log file in native editor")

        # --- Log view ---
        self._log_view = QPlainTextEdit(self)
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(max_lines)
        self._log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        # Monospaced font
        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fixed_font.setPixelSize(12)
        self._log_view.setFont(fixed_font)

        path = path or self._mmcore.getPrimaryLogFile()
        self._log_path.setText(path)
        # Load the last `max_lines` from file
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in deque(f, maxlen=max_lines):
                    self._log_view.appendPlainText(line.rstrip("\n"))
        except Exception:
            pass

        # --- Reader thread setup ---
        self._reader = _LogReader(path)

        # --- Layout ---
        file_layout = QHBoxLayout()
        file_layout.setContentsMargins(5, 5, 5, 0)
        file_layout.addWidget(self._log_path)
        file_layout.addWidget(self._clear_btn)
        file_layout.addWidget(self._log_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(file_layout)
        layout.addWidget(self._log_view)

        # --- Connections ---
        self._reader.new_lines.connect(self._append_line)
        self._clear_btn.clicked.connect(self.clear)
        self._log_btn.clicked.connect(self._open_native)
        self._reader.start()

        # scroll left to begin
        def _scroll_left() -> None:
            if sb := self._log_view.horizontalScrollBar():
                sb.setValue(0)

        QTimer.singleShot(0, _scroll_left)

    def clear(self) -> None:
        """Clear the log view."""
        self._log_view.clear()

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return hint.expandedTo(QSize(1000, 800))

    def _append_line(self, line: str) -> None:
        """Append a line, respecting pause/follow settings."""
        self._log_view.appendPlainText(line)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Clean up thread on close."""
        self._reader._stop()
        super().closeEvent(event)

    def _open_native(self) -> None:
        """Open the log file in the system's default text editor."""
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._mmcore.getPrimaryLogFile()))
