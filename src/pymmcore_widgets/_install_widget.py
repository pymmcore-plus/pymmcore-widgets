from __future__ import annotations

import ctypes
import os
import platform
import shutil
import signal
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pymmcore_plus import find_micromanager
from pymmcore_plus.install import available_versions
from qtpy.QtCore import QSize, Qt, QThread, Signal
from qtpy.QtWidgets import (
    QAction,
    QComboBox,
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

if TYPE_CHECKING:
    from qtpy.QtGui import QKeyEvent

CAN_INSTALL = platform.system() == "Windows" or (
    platform.system() == "Darwin" and platform.machine() == "x86_64"
)
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
        self._act_reveal = cast(
            "QAction", self.toolbar.addAction("Reveal", self.table.reveal)
        )
        self._act_reveal.setEnabled(False)
        self._act_uninstall = cast(
            "QAction", self.toolbar.addAction("Uninstall", self.table.uninstall)
        )
        self._act_uninstall.setEnabled(False)
        self._act_use = cast(
            "QAction", self.toolbar.addAction("Set Active", self.table.set_active)
        )
        self._act_use.setEnabled(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        # # install row ------------------------

        self.version_combo = QComboBox()
        self.version_combo.addItems(["latest-compatible", "latest"])
        with suppress(Exception):
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
        with suppress(ImportError):
            from pymmcore_plus import _pymmcore

            if ver := getattr(_pymmcore, "__version__", ""):
                label = QLabel(f"pymmcore version: {ver}")
                font = label.font()
                font.setItalic(True)
                label.setFont(font)
                layout.addWidget(label)

        install_row = QWidget()
        row = QHBoxLayout(install_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Install release:"), 0)
        row.addWidget(self.version_combo, 1)
        row.addWidget(self.install_btn, 1)
        layout.addWidget(install_row)
        layout.addWidget(self.feedback_textbox)

        if not CAN_INSTALL:  # if we're not on windows or macos-x86_64...
            install_row.hide()

    def _on_selection_changed(self) -> None:
        """Hide/Show reveal uninstall buttons based on selection."""
        rows = {x.row() for x in self.table.selectedItems()}
        if len(rows) == 1:
            row = next(iter(rows))
            in_use = (item := self.table.item(row, self.table.USE_COL)) and item.text()
            self._act_use.setEnabled(not in_use)
        else:
            self._act_use.setEnabled(False)

        has_selection = bool(rows)
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

        self.feedback_textbox.append(f"Running:\n{' '.join(cmd)}")
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

    USE_COL = 0
    VER_COL = 1
    DIV_COL = 2
    LOC_COL = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        headers = ["Active", "Version", "Device Interface", "Location"]
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(headers)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        if vh := self.verticalHeader():
            vh.hide()
        if hh := self.horizontalHeader():
            hh.setSectionResizeMode(self.USE_COL, hh.ResizeMode.ResizeToContents)
            hh.setSectionResizeMode(self.VER_COL, hh.ResizeMode.ResizeToContents)
            hh.setStretchLastSection(True)

        self.refresh()

    def keyPressEvent(self, e: QKeyEvent | None) -> None:
        if e and e.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.uninstall()

    def sizeHint(self) -> QSize:
        return super().sizeHint().expandedTo(QSize(750, 150))

    def refresh(self) -> None:
        self.setRowCount(0)
        using = find_micromanager(return_first=True)
        mms = sorted(find_micromanager(return_first=False), reverse=True)
        for i, full_path in enumerate(mms):
            location, version = full_path.rsplit(os.path.sep, 1)
            self.insertRow(i)

            ver = QTableWidgetItem(version)
            if full_path == using:
                item = QTableWidgetItem("✓")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(i, self.USE_COL, item)
            self.setItem(i, self.VER_COL, ver)
            div = _try_get_device_interface_version(full_path)
            self.setItem(i, self.DIV_COL, QTableWidgetItem(div))

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

    def set_active(self) -> None:
        """Set the currently selected path(s) as the active MicroManager path."""
        if (
            not (selected_rows := {x.row() for x in self.selectedIndexes()})
            or len(selected_rows) > 1
        ):
            return

        row = next(iter(selected_rows))
        with suppress(ImportError):
            from pymmcore_plus import _pymmcore

            installed_div = _pymmcore.version_info.device_interface
            requested_div = (item := self.item(row, self.DIV_COL)) and item.text()

            if str(installed_div) != str(requested_div):
                msg = QMessageBox.warning(
                    self,
                    "Warning",
                    f"Device interface version mismatch:\n\n"
                    f"You are activating version: {requested_div}\n"
                    f"pymmcore wants: {installed_div}\n\n"
                    "Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if not msg == QMessageBox.StandardButton.Yes:
                    return

        if loc := self.item(row, self.LOC_COL):
            if full_path := loc.data(LOC_ROLE):
                from pymmcore_plus import use_micromanager

                use_micromanager(full_path)

        self.refresh()

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


def _try_get_device_interface_version(lib_dir: str) -> str:
    """Return the device interface version from the given library path."""
    for n, lib_path in enumerate(Path(lib_dir).glob("*mmgr_dal*")):
        try:
            if sys.platform.startswith("win"):
                lib = ctypes.WinDLL(str(lib_path))
            else:
                lib = ctypes.CDLL(str(lib_path))

            return str(lib.GetDeviceInterfaceVersion())
        except Exception:
            if n < 10:  # try up to 10 times
                continue
    return ""


def _reveal(path: str) -> None:  # pragma: no cover
    """Reveal a path in the file explorer."""
    if hasattr(os, "startfile"):
        os.startfile(path)
    elif platform.system() == "Darwin":
        subprocess.run(["open", path])
    else:
        subprocess.run(["xdg-open", path])
