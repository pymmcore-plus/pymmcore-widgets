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
    QFont,
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


# Theme-adaptive color palettes (dark_bg, light_bg)
# Designed for colorblind accessibility: levels distinguished by luminance + weight,
# not just hue.  ERROR is bright+bold+bg, WARNING is medium+italic, DEBUG is dim.
_CLR_ERROR = ("#F44747", "#CD3131")
_CLR_WARNING = ("#569CD6", "#1976D2")  # blue — distinct from red in all CVD types
_CLR_DEBUG = ("#6A6A6A", "#9A9A9A")
_CLR_TIMESTAMP = ("#5F8787", "#4E7A7A")
_CLR_THREAD = ("#555555", "#999999")

# Subtle background tint alpha for error lines
_ERROR_BG_ALPHA = 25

# Regexes for log-level line coloring (first match wins)
_RE_ERROR = re.compile(r"\berr(?:or)?\b|\[err", re.IGNORECASE)
_RE_WARNING = re.compile(r"\bwarn(?:ing)?\b|\[wrn", re.IGNORECASE)
_RE_DEBUG = re.compile(r"\bdebug\b|\[dbg", re.IGNORECASE)
# MMCore log prefix: "2026-03-30T17:36:38.454177 tid0x20517b100 ..."
_RE_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+")
_RE_THREAD = re.compile(r"\btid\S+")

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


def _make_fmt(
    color_pair: tuple[str, str], dark: bool, *, bold: bool = False
) -> QTextCharFormat:
    """Build a QTextCharFormat from a (dark_color, light_color) pair."""
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color_pair[0] if dark else color_pair[1]))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    return fmt


class _LogHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for log-level coloring and search-term highlighting."""

    def __init__(self, parent: QTextDocument, dark: bool = False) -> None:
        super().__init__(parent)
        self._search_text: str = ""
        self._search_fmt = QTextCharFormat()

        # Level formats — ERROR is bold with a subtle background tint
        self._error_fmt = _make_fmt(_CLR_ERROR, dark, bold=True)
        err_bg = QColor(_CLR_ERROR[0] if dark else _CLR_ERROR[1])
        err_bg.setAlpha(_ERROR_BG_ALPHA)
        self._error_fmt.setBackground(err_bg)

        self._warning_fmt = _make_fmt(_CLR_WARNING, dark)
        self._debug_fmt = _make_fmt(_CLR_DEBUG, dark)

        # Metadata formats (muted, visually recessive)
        self._timestamp_fmt = _make_fmt(_CLR_TIMESTAMP, dark)
        self._thread_fmt = _make_fmt(_CLR_THREAD, dark)

        # Level rules: (regex, fmt) — first match wins, colors whole line
        self._level_rules = [
            (_RE_ERROR, self._error_fmt),
            (_RE_WARNING, self._warning_fmt),
            (_RE_DEBUG, self._debug_fmt),
        ]
        # Span rules: (regex, fmt) — all applied, color only the match
        self._span_rules = [
            (_RE_TIMESTAMP, self._timestamp_fmt),
            (_RE_THREAD, self._thread_fmt),
        ]

    def set_search_text(self, text: str) -> None:
        """Update the search term and re-highlight."""
        if text != self._search_text:
            self._search_text = text
            highlight = QApplication.palette().color(QPalette.ColorRole.Highlight)
            highlight.setAlpha(100)
            self._search_fmt.setBackground(highlight)
            self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        # Level coloring (whole line, first match wins) — level color dominates
        level_matched = False
        for pattern, fmt in self._level_rules:
            if pattern.search(text):
                self.setFormat(0, len(text), fmt)
                level_matched = True
                break

        # Metadata spans only on neutral (INFO) lines
        if not level_matched:
            for pattern, fmt in self._span_rules:
                if m := pattern.search(text):
                    self.setFormat(m.start(), m.end() - m.start(), fmt)

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

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setToolTip(
            "Clears this view. Does not delete lines from the log file."
        )

        self._log_btn = QPushButton()
        color = self.palette().color(QPalette.ColorRole.WindowText).name()
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
        bg = self.palette().color(QPalette.ColorRole.Base)
        dark = bg.lightnessF() < 0.5
        self._highlighter = _LogHighlighter(self._log_view.document(), dark=dark)

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
        file_layout.setSpacing(10)
        file_layout.addWidget(self._log_path)
        file_layout.addWidget(self._debug_box)
        file_layout.addWidget(self._log_btn)

        search_layout = QHBoxLayout()
        search_layout.addWidget(self._search_input)
        search_layout.addWidget(self._level_combo)
        search_layout.addWidget(self._clear_btn)
        search_layout.addWidget(self._follow_check)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)
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
