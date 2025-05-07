import os

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import (
    QCheckBox,
    QLineEdit,
    QMessageBox,
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
        # self._file = open(self._path)
        # self._file.re
        self.current_file = None
        self.last_position = 0
        self.setup_ui()

        self.update_timer = QTimer(self)
        # Set up a timer to check for file changes
        self.update_timer.timeout.connect(self.check_for_updates)
        self.load_file()

    def close(self) -> None:
        """Close the file when the widget is closed."""
        if self._file:
            self._file.close()
        super().close()

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # File selection controls
        self.path_input = QLineEdit()
        self.path_input.setText(self._path)
        self.path_input.setReadOnly(True)

        # Text display area with monospace font for log files
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        font = self.text_area.font()
        font.setFamily("Courier")
        self.text_area.setFont(font)

        # Auto-scroll checkbox
        self.auto_scroll = QCheckBox("Auto-scroll to new content")
        self.auto_scroll.setChecked(True)

        layout.addWidget(self.path_input)
        layout.addWidget(self.text_area)
        layout.addWidget(self.auto_scroll)

    def load_file(self) -> None:
        file_path = self._path
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(
                self, "File Error", "The specified file does not exist."
            )
            return

        try:
            # If we were monitoring a previous file, stop
            if self.update_timer.isActive():
                self.update_timer.stop()

            self.current_file = file_path
            self.last_position = 0
            self.text_area.clear()

            # Initial read of the file
            with open(file_path) as f:
                content = f.read()
                self.text_area.setPlainText(content)
                self.last_position = len(content)

            # Start monitoring for changes
            self.update_timer.start(1000)  # Check every 1 second

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file: {e!s}")

    def check_for_updates(self) -> None:
        """Check if the file has new content and update the display."""
        if not self.current_file:
            return

        try:
            if not os.path.exists(self.current_file):
                # File was deleted or moved
                self.update_timer.stop()
                self.text_area.append("\n[FILE NO LONGER EXISTS]")
                return

            # Get current file size
            file_size = os.path.getsize(self.current_file)

            if file_size < self.last_position:
                # File was truncated, reload entire content
                with open(self.current_file) as f:
                    content = f.read()
                    self.text_area.setPlainText(content)
                    self.last_position = len(content)
            elif file_size > self.last_position:
                # New content was added
                with open(self.current_file) as f:
                    f.seek(self.last_position)
                    new_content = f.read()
                    self.text_area.append(new_content)
                    self.last_position = file_size

                # Auto-scroll if enabled
                if self.auto_scroll.isChecked():
                    scrollbar = self.text_area.verticalScrollBar()
                    scrollbar.setValue(scrollbar.maximum())

        except Exception as e:
            self.text_area.append(f"\n[ERROR READING FILE: {e!s}]")
