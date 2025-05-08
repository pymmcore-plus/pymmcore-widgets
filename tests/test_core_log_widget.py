from __future__ import annotations

import time
from typing import TYPE_CHECKING

from qtpy.QtWidgets import QApplication

from pymmcore_widgets import CoreLogWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_core_log_widget_update(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    wdg = CoreLogWidget()

    # Assert log path is in the widget LineEdit
    log_path = global_mmcore.getPrimaryLogFile()
    assert log_path == wdg._log_path.text()

    # Assert log content is in the widget TextEdit
    with open(log_path) as f:
        log_content = "".join(f.readlines()).strip()
    assert log_content == wdg._text_area.toPlainText()

    # Log something new
    new_message = "Test message"
    global_mmcore.logMessage(new_message)
    # Wait for log to update
    time.sleep(0.1)
    # Wait for widget to check for updates
    wdg.check_for_updates()

    # Assert the new log message is in the TextEdit
    last_line = wdg._text_area.toPlainText().splitlines()[-1]
    last_line = last_line.split(" ", 2)[-1]  # Remove timestamp
    assert f"[IFO,App] {new_message}" == last_line


def test_core_log_widget_autoscroll(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    wdg = CoreLogWidget()
    qtbot.addWidget(wdg)
    wdg.show()
    sb = wdg._text_area.verticalScrollBar()
    assert sb is not None

    def add_new_line() -> None:
        wdg._text_area.append("Test message")
        QApplication.processEvents()

    # Make sure we have a scrollbar with nonzero size to test with
    while sb.maximum() == 0:
        add_new_line()

    # Assert that adding a new line does not scroll if not at the bottom
    sb.setValue(sb.minimum())
    add_new_line()
    assert sb.value() == sb.minimum()

    # Assert that adding a new line does not scroll if not at the bottom
    old_max = sb.maximum()
    sb.setValue(old_max)
    add_new_line()
    assert sb.maximum() > old_max
    assert sb.value() == sb.maximum()
