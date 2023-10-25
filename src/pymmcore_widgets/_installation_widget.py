import os
import signal
import subprocess

from pymmcore_plus import find_micromanager
from pymmcore_plus.install import available_versions
from qtpy.QtCore import QThread, Signal
from qtpy.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from superqt import QSearchableComboBox

from pymmcore_widgets.useq_widgets import DataTableWidget, TextColumn


class InstallTable(DataTableWidget):
    VERSION = TextColumn("version", is_row_selector=True)
    LOCATION = TextColumn("location")

    def __init__(self, rows: int = 0, parent: QWidget | None = None):
        super().__init__(rows, parent)
        self.update()

    def update(self):
        rows: list[dict] = []
        for x in find_micromanager(return_first=False):
            location, version = x.rsplit(os.path.sep, 1)
            rows.append({"version": version, "location": location})
        self.setValue(rows)


class InstallWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._installing = False

        self.table = InstallTable()

        self.version_combo = QSearchableComboBox()
        self.version_combo.lineEdit().setReadOnly(True)
        self.version_combo.addItem("latest")
        self.version_combo.addItems(available_versions())

        self.install_btn = QPushButton("Install")
        self.install_btn.clicked.connect(self._on_install_clicked)

        self.feedback_textbox = QTextEdit()
        self.feedback_textbox.setReadOnly(True)
        self.feedback_textbox.hide()

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        row.addWidget(QLabel("Release:"), 0)
        row.addWidget(self.version_combo, 1)
        row.addWidget(self.install_btn, 1)
        layout.addLayout(row)
        layout.addWidget(self.feedback_textbox)

        self.resize(500, 300)

    def _on_install_clicked(self) -> None:
        if self._installing:
            self.cmd_thread.send_interrupt()
            self.install_btn.setText("Install")
            return

        selected_version = self.version_combo.currentText()
        cmd = ["mmcore", "install", "--release", selected_version]
        self.feedback_textbox.append(f'Running: {" ".join(cmd)}')

        self.cmd_thread = SubprocessThread([*cmd, "--plain-output"])
        self.cmd_thread.stdout_ready.connect(self.feedback_textbox.append)
        self.cmd_thread.process_finished.connect(self._on_finished)

        self.feedback_textbox.show()
        self._installing = True
        self.install_btn.setText("Cancel")
        self.cmd_thread.start()

    def _on_finished(self, returncode):
        status = "successful" if returncode == 0 else "failed"
        self.feedback_textbox.append(f"\nInstallation {status}.")
        self.install_btn.setText("Install")
        self.table.update()
        self._installing = False


class SubprocessThread(QThread):
    """Run a python subprocess in a thread."""

    stdout_ready = Signal(str)
    process_finished = Signal(int)

    def __init__(self, cmd: list[str]) -> None:
        super().__init__()
        self.cmd = cmd
        self.process = None

    def run(self) -> None:
        """Run the command and emit stdout and returncode."""
        self.process = subprocess.Popen(
            self.cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )

        # Emit the read line for every line from stdout
        for line in iter(self.process.stdout.readline, ""):
            self.stdout_ready.emit(line.strip())

        self.process.communicate()  # Ensure process completes
        self.process_finished.emit(self.process.returncode)

    def send_interrupt(self) -> None:
        """Cancel the process."""
        if self.process:
            self.process.send_signal(signal.SIGINT)
