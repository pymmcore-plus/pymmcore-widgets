from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import (
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class CoreLogWidget(QWidget):
    """A widget that displays the current Micro-Manager Core Log."""

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)
        self._mmc = mmcore or CMMCorePlus().instance()
        self._path = self._mmc.getPrimaryLogFile()
        self._file = open(self._path)
        self._last_max = 0

        self._layout = QVBoxLayout(self)

        self._log_path = QLineEdit()
        self._log_path.setText(self._path)
        self._log_path.setReadOnly(True)

        self._text_area = QTextEdit()
        self._text_area.setReadOnly(True)
        if sb := self._text_area.verticalScrollBar():
            sb.rangeChanged.connect(self._auto_scroll)

        font = self._text_area.font()
        font.setFamily("Courier")
        self._text_area.setFont(font)

        self._layout.addWidget(self._log_path)
        self._layout.addWidget(self._text_area)

        # Initialize with the current core log content
        self._update()
        # Begin polling for file changes
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update)
        self._update_timer.start(100)

    def __del__(self) -> None:
        self._file.close()

    def _update(self) -> None:
        """Check if the file has new content and update the display."""
        new_lines = "".join(self._file.readlines())
        if not new_lines:
            return
        self._text_area.append(new_lines.strip())

    def _auto_scroll(self, min: int, max: int) -> None:
        """Stays at the bottom of the scroll area when already there."""
        sb = self._text_area.verticalScrollBar()
        if sb is None:
            return
        if sb.value() == self._last_max:
            sb.setValue(max)
        self._last_max = max
