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

        self.log_path = QLineEdit()
        self.log_path.setText(self._path)
        self.log_path.setReadOnly(True)

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        if sb := self.text_area.verticalScrollBar():
            sb.rangeChanged.connect(self._auto_scroll)

        font = self.text_area.font()
        font.setFamily("Courier")
        self.text_area.setFont(font)

        self._layout.addWidget(self.log_path)
        self._layout.addWidget(self.text_area)

        # Initialize with the current core log content
        self.check_for_updates()
        # Begin polling for file changes
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.check_for_updates)
        self.update_timer.start(100)

    def __del__(self) -> None:
        self._file.close()

    def check_for_updates(self) -> None:
        """Check if the file has new content and update the display."""
        new_lines = "".join(self._file.readlines())
        if not new_lines:
            return
        self.text_area.append(new_lines.strip())

    def _auto_scroll(self, min: int, max: int) -> None:
        """Stays at the bottom of the scroll area when already there."""
        sb = self.text_area.verticalScrollBar()
        if sb is None:
            return
        if sb.value() == self._last_max:
            sb.setValue(max)
        self._last_max = max
