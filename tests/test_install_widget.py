import os
import platform
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from pytestqt.qtbot import QtBot

from pymmcore_widgets import InstallWidget, _install_widget

LINUX = platform.system() == "Linux"
PY311 = sys.version_info[:2] == (3, 11)
CI = os.getenv("CI", True)


@pytest.mark.skipif(bool(LINUX or not PY311 or not CI), reason="minimize downloads")
def test_install_widget_download(qtbot: QtBot, tmp_path: Path):
    wdg = InstallWidget()
    qtbot.addWidget(wdg)

    # mock the process of downloading
    with patch.object(_install_widget.QThread, "start"):
        wdg._install_dest = str(tmp_path)
        wdg._on_install_clicked()
        wdg._cmd_thread.stdout_ready.emit("emitting stdout")
        wdg._cmd_thread.process_finished.emit(0)

    qtbot.waitUntil(lambda: wdg._cmd_thread is None)
    assert "emitting stdout" in wdg.feedback_textbox.toPlainText()


@pytest.mark.skipif(bool(LINUX or not PY311 or not CI), reason="minimize downloads")
def test_install_widget(qtbot: QtBot, tmp_path: Path):
    wdg = InstallWidget()
    qtbot.addWidget(wdg)
    wdg.show()

    dest = tmp_path / "MicroManager-2.0.0-gamma"
    dest.mkdir()
    assert dest.exists()

    with patch.object(_install_widget, "find_micromanager") as mock1:
        with patch.object(_install_widget, "_reveal") as rev_mock:
            mock1.return_value = [str(dest)]
            wdg.table.refresh()

            # test reveal
            wdg.table.selectRow(0)
            assert wdg._act_reveal.isEnabled()
            wdg.table.reveal()
            rev_mock.assert_called_once_with(str(dest))

    with patch.object(_install_widget.QMessageBox, "warning") as mock2:
        mock2.return_value = _install_widget.QMessageBox.StandardButton.Yes
        wdg.table.uninstall()

    assert not dest.exists()
