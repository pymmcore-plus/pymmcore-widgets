from __future__ import annotations

import os
import platform
import shutil
import signal
import subprocess

from pymmcore_plus import find_micromanager
from pymmcore_plus.install import available_versions
from qtpy.QtCore import Qt, QThread, Signal
from qtpy.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from superqt import QSearchableComboBox

LOC_ROLE = Qt.ItemDataRole.UserRole + 1


class InstallWidget(QWidget):
    """Widget to manage installation of MicroManager.

    This widget will let you download and install a specific version of MicroManager
    from <https://micro-manager.org/downloads>. It will also manage the currently
    installed versions.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cmd_thread: SubprocessThread | None = None

        self.table = _InstallTable(self)

        # Toolbar ------------------------

        self.toolbar = QToolBar(self)
        self.toolbar.addAction("Refresh", self.table.refresh)
        self._act_reveal = self.toolbar.addAction("Reveal", self.table.reveal)
        self._act_reveal.setEnabled(False)
        self._act_uninstall = self.toolbar.addAction("Uninstall", self.table.uninstall)
        self._act_uninstall.setEnabled(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        # # install row ------------------------

        self.version_combo = QSearchableComboBox()
        self.version_combo.lineEdit().setReadOnly(True)
        self.version_combo.addItem("latest")
        self.version_combo.addItems(available_versions())

        self.install_btn = QPushButton("Install")
        self.install_btn.clicked.connect(self._on_install_clicked)

        # # feedback ------------------------

        self.feedback_textbox = QTextEdit()
        self.feedback_textbox.setReadOnly(True)
        self.feedback_textbox.hide()

        # # Layout ------------------------

        layout = QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        row.addWidget(QLabel("Install release:"), 0)
        row.addWidget(self.version_combo, 1)
        row.addWidget(self.install_btn, 1)
        layout.addLayout(row)
        layout.addWidget(self.feedback_textbox)

    def _on_selection_changed(self) -> None:
        """Hide/Show reveal uninstall buttons based on selection."""
        has_selection = bool(self.table.selectedIndexes())
        self._act_reveal.setEnabled(has_selection)
        self._act_uninstall.setEnabled(has_selection)

    def _on_install_clicked(self) -> None:
        if self._cmd_thread:
            self._cmd_thread.send_interrupt()
            self.install_btn.setText("Install")
            return

        selected_version = self.version_combo.currentText()
        cmd = ["mmcore", "install", "--release", selected_version, "--plain-output"]
        if dest := getattr(self, "_install_dest", None):  # for pytest, could expose
            cmd = [*cmd, "--dest", dest]

        self.feedback_textbox.append(f'Running:\n{" ".join(cmd)}')
        self._cmd_thread = SubprocessThread(cmd)
        self._cmd_thread.stdout_ready.connect(self.feedback_textbox.append)
        self._cmd_thread.process_finished.connect(self._on_finished)

        self.feedback_textbox.show()
        self.install_btn.setText("Cancel")
        self._cmd_thread.start()

    def _on_finished(self, returncode: int) -> None:
        status = "successful" if returncode == 0 else "failed"
        self.feedback_textbox.append(f"\nInstallation {status}.")
        self.install_btn.setText("Install")
        self.table.refresh()
        self._cmd_thread = None


class _InstallTable(QTableWidget):
    """Table of installed versions."""

    LOC_COL = 1

    def __init__(self, parent: QWidget | None = None) -> None:
        headers = ["Version", "Location"]
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(headers)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.verticalHeader().hide()
        if hh := self.horizontalHeader():
            hh.setSectionResizeMode(0, hh.ResizeMode.ResizeToContents)
            hh.setStretchLastSection(True)
        self.refresh()

    def refresh(self) -> None:
        self.setRowCount(0)
        for i, full_path in enumerate(find_micromanager(return_first=False)):
            location, version = full_path.rsplit(os.path.sep, 1)
            self.insertRow(i)

            ver = QTableWidgetItem(version)
            if i == 0:
                f = ver.font()
                f.setBold(True)
                ver.setFont(f)
            self.setItem(i, 0, ver)

            loc = QTableWidgetItem(location)
            loc.setData(LOC_ROLE, full_path)
            self.setItem(i, self.LOC_COL, loc)

    def reveal(self) -> None:
        """Reveal the currently selected row in the file explorer."""
        selected_rows = {x.row() for x in self.selectedIndexes()}
        for row in sorted(selected_rows):
            if loc := self.item(row, self.LOC_COL):
                if full_path := loc.data(LOC_ROLE):
                    _reveal(full_path)

    def uninstall(self) -> None:
        """Delete the currently selected path(s)."""
        if not (selected_rows := {x.row() for x in self.selectedIndexes()}):
            return

        msg = QMessageBox.warning(
            self,
            "Uninstall",
            "Are you sure you want to delete the selected path(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if not msg == QMessageBox.StandardButton.Yes:
            return

        for row in sorted(selected_rows, reverse=True):
            if loc := self.item(row, self.LOC_COL):
                if full_path := loc.data(LOC_ROLE):
                    shutil.rmtree(full_path, ignore_errors=True)

        self.refresh()


class SubprocessThread(QThread):
    """Run a python subprocess in a thread."""

    stdout_ready = Signal(str)
    process_finished = Signal(int)

    def __init__(self, cmd: list[str]) -> None:
        super().__init__()
        self.cmd = cmd
        self.process: subprocess.Popen | None = None

    def run(self) -> None:  # pragma: no cover
        """Run the command and emit stdout and returncode."""
        self.process = process = subprocess.Popen(
            self.cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )

        # Emit the read line for every line from stdout
        for line in iter(process.stdout.readline, ""):  # type: ignore
            self.stdout_ready.emit(line.strip())
        process.communicate()  # Ensure process completes
        self.process_finished.emit(process.returncode)

    def send_interrupt(self) -> None:
        """Cancel the process."""
        if self.process:
            self.process.send_signal(signal.SIGINT)


def _reveal(path: str) -> None:  # pragma: no cover
    """Reveal a path in the file explorer."""
    if hasattr(os, "startfile"):
        os.startfile(path)
    elif platform.system() == "Darwin":
        subprocess.run(["open", path])
    else:
        subprocess.run(["xdg-open", path])
