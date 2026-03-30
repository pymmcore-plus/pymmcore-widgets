from __future__ import annotations

import os
import re
from collections import deque
from contextlib import suppress
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import (
    QFileSystemWatcher,
    QObject,
    QSize,
    QTimer,
    QTimerEvent,
    QUrl,
    Signal,
)
from qtpy.QtGui import (
    QCloseEvent,
    QColor,
    QDesktopServices,
    QFontDatabase,
    QPalette,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from superqt import QElidingLabel, QIconifyIcon

if TYPE_CHECKING:
    from io import TextIOWrapper


# (regex, foreground color) — checked in order, first match wins
_LEVEL_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\berr(?:or)?\b|\[err", re.IGNORECASE), "#e55555"),
    (re.compile(r"\bwarn(?:ing)?\b|\[wrn", re.IGNORECASE), "#ddaa55"),
    (re.compile(r"\bdebug\b|\[dbg", re.IGNORECASE), "#A2A2A2"),
]

# MMCore log prefix: "2026-03-30T17:36:38.454177 tid0x20517b100 ..."
_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+")
_THREAD_RE = re.compile(r"\btid\S+")

# Log level ordering for the minimum-level filter
DEBUG, INFO, WARNING, ERROR = 0, 1, 2, 3
_LEVEL_NAMES = ["Debug", "Info", "Warning", "Error"]
_LEVEL_PATTERNS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"\berr(?:or)?\b|\[err", re.IGNORECASE), ERROR),
    (re.compile(r"\bwarn(?:ing)?\b|\[wrn", re.IGNORECASE), WARNING),
    (re.compile(r"\bdebug\b|\[dbg", re.IGNORECASE), DEBUG),
    (re.compile(r"\binfo\b|\[ifo", re.IGNORECASE), INFO),
]


def _line_level(line: str) -> int:
    """Return the log level of a line (DEBUG=0, INFO=1, WARNING=2, ERROR=3)."""
    for pattern, level in _LEVEL_PATTERNS:
        if pattern.search(line):
            return level
    return INFO


class _LogHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for log-level coloring and search-term highlighting."""

    def __init__(self, parent: QTextDocument) -> None:
        super().__init__(parent)
        self._search_text: str = ""
        self._search_fmt = QTextCharFormat()

        # Pre-build level formats
        self._level_rules: list[tuple[re.Pattern[str], QTextCharFormat]] = []
        for pattern, color in _LEVEL_RULES:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            self._level_rules.append((pattern, fmt))

        # Timestamp and thread-id formats
        self._timestamp_fmt = QTextCharFormat()
        self._timestamp_fmt.setForeground(QColor("#6A9955"))
        self._thread_fmt = QTextCharFormat()
        self._thread_fmt.setForeground(QColor("#808080"))

    def set_search_text(self, text: str) -> None:
        """Update the search term and re-highlight."""
        if text != self._search_text:
            self._search_text = text
            highlight = QApplication.palette().color(QPalette.ColorRole.Highlight)
            highlight.setAlpha(100)
            self._search_fmt.setBackground(highlight)
            self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        # Log-level coloring (whole line)
        for pattern, fmt in self._level_rules:
            if pattern.search(text):
                self.setFormat(0, len(text), fmt)
                break

        # Timestamp and thread-id (overlay on top of level color)
        if m := _TIMESTAMP_RE.match(text):
            self.setFormat(m.start(), m.end() - m.start(), self._timestamp_fmt)
        if m := _THREAD_RE.search(text):
            self.setFormat(m.start(), m.end() - m.start(), self._thread_fmt)

        # Search-term highlighting
        if self._search_text:
            needle = self._search_text.lower()
            lower = text.lower()
            nlen = len(needle)
            start = 0
            while True:
                idx = lower.find(needle, start)
                if idx == -1:
                    break
                self.setFormat(idx, nlen, self._search_fmt)
                start = idx + nlen


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
        # Seek to current position to clear Python's internal read buffers,
        # ensuring we see data written externally since the last read.
        self._file.seek(self._file.tell())
        for line in self._file:
            self.new_lines.emit(line.rstrip("\n"))


class CoreLogWidget(QWidget):
    """Log console with level coloring, search/filter, and follow-tail."""

    def __init__(
        self,
        path: str | None = None,
        max_lines: int = 5_000,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent)
        self._mmcore = mmcore or CMMCorePlus.instance()
        self._max_lines = max_lines
        self.setWindowTitle("Log Console")

        self._line_buffer: deque[str] = deque(maxlen=max_lines)
        self._search_text: str = ""

        # --- Top bar widgets ---
        self._log_path = QElidingLabel()
        self._log_path.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )

        self._debug_box = QCheckBox("Debug Logging")
        self._debug_box.setToolTip("Enables debug logging within the core.")
        self._debug_box.setChecked(self._mmcore.debugLogEnabled())

        self._clear_btn = QPushButton("Clear Display")
        self._clear_btn.setToolTip(
            "Clears this view. Does not delete lines from the log file."
        )

        self._log_btn = QPushButton()
        color = QApplication.palette().color(QPalette.ColorRole.WindowText).name()
        self._log_btn.setIcon(QIconifyIcon("majesticons:open", color=color))
        self._log_btn.setToolTip("Open log file in native editor")

        # --- Search bar widgets ---
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Filter...")
        self._search_input.setClearButtonEnabled(True)

        self._level_combo = QComboBox()
        self._level_combo.addItems(_LEVEL_NAMES)
        self._level_combo.setToolTip("Minimum log level to display")

        self._follow_check = QCheckBox("Follow")
        self._follow_check.setToolTip("Auto-scroll to new log lines")
        self._follow_check.setChecked(True)

        # --- Log view ---
        self._log_view = QPlainTextEdit(self)
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(max_lines)
        self._log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fixed_font.setPixelSize(12)
        self._log_view.setFont(fixed_font)

        # --- Syntax highlighter ---
        self._highlighter = _LogHighlighter(self._log_view.document())

        # --- Debounce timers ---
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._apply_search)

        # --- Load initial content ---
        path = path or self._mmcore.getPrimaryLogFile()
        self._log_path.setText(path)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in deque(f, maxlen=max_lines):
                    stripped = line.rstrip("\n")
                    self._line_buffer.append(stripped)
                    self._log_view.appendPlainText(stripped)
        except Exception:
            pass

        # --- Reader ---
        self._reader = _LogReader(path)

        # --- Layout ---
        file_layout = QHBoxLayout()
        file_layout.setContentsMargins(5, 5, 5, 0)
        file_layout.addWidget(self._log_path)
        file_layout.addWidget(self._debug_box)
        file_layout.addWidget(self._clear_btn)
        file_layout.addWidget(self._log_btn)

        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(5, 0, 5, 0)
        search_layout.addWidget(self._search_input)
        search_layout.addWidget(self._level_combo)
        search_layout.addWidget(self._follow_check)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(file_layout)
        layout.addLayout(search_layout)
        layout.addWidget(self._log_view)

        # --- Connections ---
        self._reader.new_lines.connect(self._append_line)
        self._debug_box.toggled.connect(self._mmcore.enableDebugLog)
        self._clear_btn.clicked.connect(self.clear)
        self._log_btn.clicked.connect(self._open_native)
        self._search_input.textChanged.connect(self._on_search_changed)
        self._level_combo.currentIndexChanged.connect(self._on_level_changed)
        self._follow_check.toggled.connect(self._on_follow_toggled)

        scrollbar = self._log_view.verticalScrollBar()
        if scrollbar:
            scrollbar.valueChanged.connect(self._on_scroll_changed)

        self._reader.start()

        # scroll left to begin
        def _scroll_left() -> None:
            if sb := self._log_view.horizontalScrollBar():
                sb.setValue(0)

        QTimer.singleShot(0, _scroll_left)

    # --- Public API ---

    def clear(self) -> None:
        """Clear the log view and line buffer."""
        self._line_buffer.clear()
        self._log_view.clear()

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return hint.expandedTo(QSize(1000, 800))

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Clean up on close."""
        self._reader._stop()
        super().closeEvent(event)

    # --- Follow-tail ---

    def _on_follow_toggled(self, checked: bool) -> None:
        if checked:
            self._scroll_to_bottom()

    def _on_scroll_changed(self, value: int) -> None:
        scrollbar = self._log_view.verticalScrollBar()
        if not scrollbar:
            return
        at_bottom = value >= scrollbar.maximum() - 3
        if at_bottom != self._follow_check.isChecked():
            self._follow_check.blockSignals(True)
            self._follow_check.setChecked(at_bottom)
            self._follow_check.blockSignals(False)

    def _scroll_to_bottom(self) -> None:
        if scrollbar := self._log_view.verticalScrollBar():
            scrollbar.setValue(scrollbar.maximum())

    # --- Search / filter / level ---

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text
        self._search_timer.start()

    def _on_level_changed(self, _index: int) -> None:
        self._rebuild_view()

    def _apply_search(self) -> None:
        """React to search text changes."""
        self._highlighter.set_search_text(self._search_text)
        self._rebuild_view()

    def _should_show(self, line: str) -> bool:
        """Return True if a line passes the current level and text filters."""
        if _line_level(line) < self._level_combo.currentIndex():
            return False
        search = self._search_text.lower()
        if search and search not in line.lower():
            return False
        return True

    def _rebuild_view(self) -> None:
        """Rebuild the view from the line buffer, applying current filters."""
        self._log_view.setUpdatesEnabled(False)
        self._log_view.clear()
        for line in self._line_buffer:
            if self._should_show(line):
                self._log_view.appendPlainText(line)
        self._log_view.setUpdatesEnabled(True)
        if self._follow_check.isChecked():
            self._scroll_to_bottom()

    # --- Line handling ---

    def _append_line(self, line: str) -> None:
        """Handle a new line from the log reader."""
        self._line_buffer.append(line)
        if self._should_show(line):
            self._log_view.appendPlainText(line)

    def _open_native(self) -> None:
        """Open the log file in the system's default text editor."""
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._mmcore.getPrimaryLogFile()))
